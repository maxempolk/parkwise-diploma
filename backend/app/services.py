from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from .errors import api_error
from .models import (
    ParkingSession,
    ParkingSpot,
    Reservation,
    ReservationStatus,
    SessionStatus,
    SpotType,
    Tariff,
)

BUFFER = timedelta(minutes=10)
NO_SHOW_GRACE = timedelta(minutes=30)
QUICK_LIMIT = timedelta(hours=4)
QUICK_MAX_DURATION = timedelta(hours=6)
QUICK_MAX_EXTENSION = timedelta(hours=2)


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def validate_period(starts_at: datetime, ends_at: datetime, *, reservation: bool = True) -> tuple[datetime, datetime]:
    starts_at, ends_at = as_utc(starts_at), as_utc(ends_at)
    duration = ends_at - starts_at
    if ends_at <= starts_at:
        raise api_error(422, "invalid_period", "The end time must be later than the start time.")
    if reservation:
        if starts_at < utc_now() - timedelta(minutes=1):
            raise api_error(422, "past_start", "A reservation cannot start in the past.")
        if starts_at > utc_now() + timedelta(days=30):
            raise api_error(422, "too_far_ahead", "A reservation can be made up to 30 days ahead.")
        if duration < timedelta(minutes=30) or duration > timedelta(hours=24):
            raise api_error(422, "invalid_duration", "A reservation must last between 30 minutes and 24 hours.")
        if starts_at.minute % 30 or ends_at.minute % 30 or starts_at.second or ends_at.second:
            raise api_error(422, "invalid_time_step", "Reservation times must use 30-minute steps.")
    return starts_at, ends_at


def refresh_statuses(db: Session, now: datetime | None = None) -> None:
    now = as_utc(now or utc_now())
    reservations = db.scalars(select(Reservation).where(Reservation.status == ReservationStatus.CONFIRMED)).all()
    for item in reservations:
        if as_utc(item.starts_at) + NO_SHOW_GRACE < now:
            item.status = ReservationStatus.NO_SHOW
    sessions = db.scalars(select(ParkingSession).where(ParkingSession.status == SessionStatus.ACTIVE)).all()
    for item in sessions:
        if as_utc(item.expected_end_at) < now:
            item.status = SessionStatus.OVERDUE
    db.commit()


def require_tariff(db: Session, spot_type: SpotType) -> Tariff:
    tariff = db.scalar(select(Tariff).where(Tariff.spot_type == spot_type))
    if tariff is None:
        raise api_error(409, "tariff_missing", "No tariff is configured for this parking spot type.")
    return tariff


def ensure_vehicle_has_no_active_session(db: Session, license_plate: str) -> None:
    existing = db.scalar(
        select(ParkingSession.id).where(
            ParkingSession.license_plate == license_plate.strip().upper(),
            ParkingSession.status.in_([SessionStatus.ACTIVE, SessionStatus.OVERDUE]),
        )
    )
    if existing is not None:
        raise api_error(409, "active_session_exists", "This vehicle already has an active parking session.")


def ensure_vehicle_has_no_overlapping_reservation(
    db: Session,
    license_plate: str,
    starts_at: datetime,
    ends_at: datetime,
    exclude_reservation_id: int | None = None,
) -> None:
    query = select(Reservation.id).where(
        Reservation.license_plate == license_plate.strip().upper(),
        Reservation.status == ReservationStatus.CONFIRMED,
        Reservation.starts_at < ends_at,
        Reservation.ends_at > starts_at,
    )
    if exclude_reservation_id is not None:
        query = query.where(Reservation.id != exclude_reservation_id)
    if db.scalar(query) is not None:
        raise api_error(
            409, "overlapping_vehicle_reservation", "This vehicle already has a reservation for part of this time."
        )


def count_available_capacity(
    db: Session,
    spot_type: SpotType,
    starts_at: datetime,
    ends_at: datetime,
    exclude_reservation_id: int | None = None,
    exclude_session_id: int | None = None,
) -> int:
    spots = db.scalars(
        select(ParkingSpot).where(
            ParkingSpot.spot_type == spot_type,
            ParkingSpot.is_active.is_(True),
            ParkingSpot.is_blocked.is_(False),
        )
    ).all()
    if not spots:
        return 0
    query = select(func.count(Reservation.id)).where(
        Reservation.spot_type == spot_type,
        Reservation.status == ReservationStatus.CONFIRMED,
        Reservation.starts_at < ends_at + BUFFER,
        Reservation.ends_at > starts_at - BUFFER,
    )
    if exclude_reservation_id is not None:
        query = query.where(Reservation.id != exclude_reservation_id)
    reserved = db.scalar(query) or 0
    active_query = (
        select(func.count(ParkingSession.id))
        .join(ParkingSpot)
        .where(
            ParkingSpot.spot_type == spot_type,
            ParkingSession.status.in_([SessionStatus.ACTIVE, SessionStatus.OVERDUE]),
            ParkingSession.started_at < ends_at + BUFFER,
            ParkingSession.expected_end_at > starts_at - BUFFER,
        )
    )
    if exclude_session_id is not None:
        active_query = active_query.where(ParkingSession.id != exclude_session_id)
    active = db.scalar(active_query) or 0
    return max(0, len(spots) - reserved - active)


def ensure_capacity(
    db: Session,
    spot_type: SpotType,
    starts_at: datetime,
    ends_at: datetime,
    exclude_id: int | None = None,
    exclude_session_id: int | None = None,
) -> None:
    require_tariff(db, spot_type)
    if count_available_capacity(db, spot_type, starts_at, ends_at, exclude_id, exclude_session_id) < 1:
        raise api_error(409, "no_availability", "No parking spot of the selected type is available for this period.")


def ensure_spot_can_leave_capacity(db: Session, spot: ParkingSpot) -> None:
    """Prevent reducing physical capacity below already confirmed reservations."""
    if not spot.is_active or spot.is_blocked:
        return
    now = utc_now()
    reservations = db.scalars(
        select(Reservation).where(
            Reservation.spot_type == spot.spot_type,
            Reservation.status == ReservationStatus.CONFIRMED,
            Reservation.ends_at > now - BUFFER,
        )
    ).all()
    for reservation in reservations:
        if (
            count_available_capacity(db, spot.spot_type, as_utc(reservation.starts_at), as_utc(reservation.ends_at))
            <= 0
        ):
            raise api_error(
                409,
                "spot_capacity_required",
                "This spot is required to fulfill confirmed reservations and cannot be removed from capacity.",
            )


def assign_spot(db: Session, spot_type: SpotType, starts_at: datetime, ends_at: datetime) -> ParkingSpot:
    spots = db.scalars(
        select(ParkingSpot)
        .where(
            ParkingSpot.spot_type == spot_type,
            ParkingSpot.is_active.is_(True),
            ParkingSpot.is_blocked.is_(False),
        )
        .order_by(ParkingSpot.number)
    ).all()
    candidates: list[tuple[datetime, int, ParkingSpot]] = []
    for spot in spots:
        occupied = db.scalar(
            select(ParkingSession.id).where(
                ParkingSession.spot_id == spot.id,
                ParkingSession.status.in_([SessionStatus.ACTIVE, SessionStatus.OVERDUE]),
                ParkingSession.started_at < ends_at,
                ParkingSession.expected_end_at > starts_at,
            )
        )
        if occupied:
            continue
        next_reservation = db.scalar(
            select(Reservation.starts_at)
            .where(
                Reservation.spot_type == spot_type,
                Reservation.status == ReservationStatus.CONFIRMED,
                Reservation.starts_at >= ends_at,
            )
            .order_by(Reservation.starts_at)
            .limit(1)
        )
        candidates.append(
            (as_utc(next_reservation) if next_reservation else datetime.max.replace(tzinfo=UTC), spot.number, spot)
        )
    if not candidates:
        raise api_error(409, "no_spot_available", "No physical parking spot can be assigned right now.")
    # Prefer the spot with the most distant next reservation, then the lowest number.
    candidates.sort(key=lambda item: (-item[0].timestamp(), item[1]))
    return candidates[0][2]


def calculate_cost(db: Session, session: ParkingSession, ended_at: datetime) -> Decimal:
    rate = session.rate_per_30_minutes or require_tariff(db, session.spot.spot_type).price_per_30_minutes
    started_at, ended_at = as_utc(session.started_at), as_utc(ended_at)
    billable_seconds = max(0, (ended_at - started_at).total_seconds())
    if session.reservation is not None:
        reserved_seconds = (as_utc(session.reservation.ends_at) - as_utc(session.reservation.starts_at)).total_seconds()
        billable_seconds = max(billable_seconds, reserved_seconds)
    blocks = max(1, int((Decimal(str(billable_seconds)) / Decimal("1800")).to_integral_value(rounding=ROUND_CEILING)))
    return (Decimal(blocks) * rate).quantize(Decimal("0.01"))


def ensure_extension_allowed(session: ParkingSession, new_end: datetime) -> None:
    """Apply the stricter extension policy for quick-parking sessions."""
    current_end = as_utc(session.expected_end_at)
    if session.status == SessionStatus.COMPLETED or new_end <= current_end:
        raise api_error(422, "invalid_extension", "The new end time must extend an active session.")
    if session.reservation_id is not None:
        return
    if session.status != SessionStatus.ACTIVE:
        raise api_error(
            409, "quick_extension_closed", "Quick parking can only be extended before its expected end time."
        )
    if session.extension_count >= 1:
        raise api_error(409, "quick_extension_used", "Quick parking can only be extended once.")
    if new_end - current_end > QUICK_MAX_EXTENSION:
        raise api_error(422, "quick_extension_too_long", "Quick parking can be extended by up to 2 hours.")
    if new_end > as_utc(session.started_at) + QUICK_MAX_DURATION:
        raise api_error(422, "quick_duration_limit", "Quick parking cannot exceed 6 hours in total.")


def get_session(db: Session, session_id: int) -> ParkingSession:
    item = db.scalar(
        select(ParkingSession)
        .options(joinedload(ParkingSession.spot), joinedload(ParkingSession.reservation))
        .where(ParkingSession.id == session_id)
    )
    if item is None:
        raise api_error(404, "session_not_found", "Parking session was not found.")
    return item


def complete_session(db: Session, item: ParkingSession, now: datetime | None = None) -> ParkingSession:
    if item.status == SessionStatus.COMPLETED:
        raise api_error(409, "session_completed", "This parking session is already completed.")
    ended_at = as_utc(now or utc_now())
    item.total_cost = calculate_cost(db, item, ended_at)
    item.ended_at = ended_at
    item.status = SessionStatus.COMPLETED
    db.commit()
    db.refresh(item)
    return get_session(db, item.id)
