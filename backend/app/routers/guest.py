from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..errors import api_error
from ..models import ParkingSession, Reservation, ReservationStatus, SessionStatus, Tariff
from ..schemas import (
    AvailabilityRead,
    ExtensionRequest,
    GuestOverview,
    QuickParkingCreate,
    ReservationCreate,
    ReservationRead,
    ReservationUpdate,
    SessionEstimateRead,
    SessionRead,
    TariffRead,
)
from ..services import (
    QUICK_LIMIT,
    as_utc,
    assign_spot,
    calculate_cost,
    complete_session,
    count_available_capacity,
    ensure_capacity,
    ensure_extension_allowed,
    ensure_vehicle_has_no_active_session,
    ensure_vehicle_has_no_overlapping_reservation,
    get_session,
    refresh_statuses,
    require_tariff,
    utc_now,
    validate_period,
)

router = APIRouter(prefix="/api", tags=["guest"])


def get_reservation(db: Session, reservation_id: int) -> Reservation:
    item = db.get(Reservation, reservation_id)
    if item is None:
        raise api_error(404, "reservation_not_found", "Reservation was not found.")
    return item


@router.post("/parking/quick", response_model=SessionRead, status_code=201)
def start_quick_parking(data: QuickParkingCreate, db: Session = Depends(get_db)):
    refresh_statuses(db)
    ensure_vehicle_has_no_active_session(db, data.license_plate)
    now = utc_now()
    expected_end = now + QUICK_LIMIT
    ensure_capacity(db, data.spot_type, now, expected_end)
    spot = assign_spot(db, data.spot_type, now, expected_end)
    rate = require_tariff(db, data.spot_type).price_per_30_minutes
    item = ParkingSession(
        spot_id=spot.id,
        phone=data.phone,
        license_plate=data.license_plate,
        started_at=now,
        expected_end_at=expected_end,
        status=SessionStatus.ACTIVE,
        rate_per_30_minutes=rate,
    )
    db.add(item)
    db.commit()
    return get_session(db, item.id)


@router.post("/reservations", response_model=ReservationRead, status_code=201)
def create_reservation(data: ReservationCreate, db: Session = Depends(get_db)):
    refresh_statuses(db)
    starts_at, ends_at = validate_period(data.starts_at, data.ends_at)
    ensure_vehicle_has_no_overlapping_reservation(db, data.license_plate, starts_at, ends_at)
    ensure_capacity(db, data.spot_type, starts_at, ends_at)
    values = data.model_dump(exclude={"starts_at", "ends_at"})
    item = Reservation(**values, starts_at=starts_at, ends_at=ends_at)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/me", response_model=GuestOverview)
def guest_overview(
    phone: str = Query(min_length=5), license_plate: str = Query(min_length=2), db: Session = Depends(get_db)
):
    refresh_statuses(db)
    plate = license_plate.strip().upper()
    reservations = db.scalars(
        select(Reservation)
        .where(Reservation.phone == phone.strip(), Reservation.license_plate == plate)
        .order_by(Reservation.starts_at.desc())
    ).all()
    sessions = db.scalars(
        select(ParkingSession)
        .options(joinedload(ParkingSession.spot))
        .where(ParkingSession.phone == phone.strip(), ParkingSession.license_plate == plate)
        .order_by(ParkingSession.started_at.desc())
    ).all()
    return GuestOverview(reservations=reservations, sessions=sessions)


@router.get("/availability", response_model=AvailabilityRead)
def parking_availability(
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    db: Session = Depends(get_db),
):
    refresh_statuses(db)
    if (starts_at is None) != (ends_at is None):
        raise api_error(422, "availability_period_incomplete", "Provide both start and end times to check a period.")
    start, end = (utc_now(), utc_now() + QUICK_LIMIT) if starts_at is None else (as_utc(starts_at), as_utc(ends_at))
    if end <= start:
        raise api_error(422, "invalid_period", "The end time must be later than the start time.")
    standard = count_available_capacity(db, "standard", start, end)
    ev = count_available_capacity(db, "ev", start, end)
    accessible = count_available_capacity(db, "accessible", start, end)
    return AvailabilityRead(standard=standard, ev=ev, accessible=accessible, total=standard + ev + accessible)


@router.get("/tariffs", response_model=list[TariffRead])
def guest_tariffs(db: Session = Depends(get_db)):
    return db.scalars(select(Tariff).order_by(Tariff.spot_type)).all()


@router.put("/reservations/{reservation_id}", response_model=ReservationRead)
def update_reservation(
    reservation_id: int, data: ReservationUpdate, phone: str, license_plate: str, db: Session = Depends(get_db)
):
    refresh_statuses(db)
    item = get_reservation(db, reservation_id)
    if item.phone != phone or item.license_plate != license_plate.upper():
        raise api_error(403, "identity_mismatch", "The guest details do not match this reservation.")
    if item.status != ReservationStatus.CONFIRMED or as_utc(item.starts_at) <= utc_now():
        raise api_error(409, "reservation_not_editable", "Only future confirmed reservations can be changed.")
    starts_at, ends_at = validate_period(data.starts_at, data.ends_at)
    ensure_vehicle_has_no_overlapping_reservation(db, item.license_plate, starts_at, ends_at, item.id)
    ensure_capacity(db, data.spot_type, starts_at, ends_at, item.id)
    item.spot_type, item.starts_at, item.ends_at = data.spot_type, starts_at, ends_at
    db.commit()
    db.refresh(item)
    return item


@router.post("/reservations/{reservation_id}/cancel", response_model=ReservationRead)
def cancel_reservation(reservation_id: int, phone: str, license_plate: str, db: Session = Depends(get_db)):
    item = get_reservation(db, reservation_id)
    if item.phone != phone or item.license_plate != license_plate.upper():
        raise api_error(403, "identity_mismatch", "The guest details do not match this reservation.")
    if item.status != ReservationStatus.CONFIRMED or as_utc(item.starts_at) <= utc_now():
        raise api_error(409, "reservation_not_cancellable", "Only future confirmed reservations can be cancelled.")
    item.status = ReservationStatus.CANCELLED
    db.commit()
    db.refresh(item)
    return item


@router.post("/reservations/{reservation_id}/check-in", response_model=SessionRead)
def check_in(reservation_id: int, phone: str, license_plate: str, db: Session = Depends(get_db)):
    refresh_statuses(db)
    item = get_reservation(db, reservation_id)
    if item.phone != phone or item.license_plate != license_plate.upper():
        raise api_error(403, "identity_mismatch", "The guest details do not match this reservation.")
    now = utc_now()
    if item.status != ReservationStatus.CONFIRMED or now < as_utc(item.starts_at):
        raise api_error(409, "check_in_unavailable", "Check-in opens at the reservation start time.")
    ensure_vehicle_has_no_active_session(db, item.license_plate)
    spot = assign_spot(db, item.spot_type, now, as_utc(item.ends_at))
    rate = require_tariff(db, item.spot_type).price_per_30_minutes
    session = ParkingSession(
        reservation_id=item.id,
        spot_id=spot.id,
        phone=item.phone,
        license_plate=item.license_plate,
        started_at=now,
        expected_end_at=item.ends_at,
        rate_per_30_minutes=rate,
    )
    item.status = ReservationStatus.CHECKED_IN
    db.add(session)
    db.commit()
    return get_session(db, session.id)


@router.post("/sessions/{session_id}/extend", response_model=SessionRead)
def extend_session(
    session_id: int, data: ExtensionRequest, phone: str, license_plate: str, db: Session = Depends(get_db)
):
    refresh_statuses(db)
    item = get_session(db, session_id)
    if item.phone != phone or item.license_plate != license_plate.upper():
        raise api_error(403, "identity_mismatch", "The guest details do not match this session.")
    new_end = as_utc(data.expected_end_at)
    ensure_extension_allowed(item, new_end)
    ensure_capacity(db, item.spot.spot_type, as_utc(item.expected_end_at), new_end, exclude_session_id=item.id)
    if item.reservation_id is None:
        item.extension_count += 1
    item.expected_end_at = new_end
    item.status = SessionStatus.ACTIVE
    db.commit()
    return get_session(db, item.id)


@router.post("/sessions/{session_id}/complete", response_model=SessionRead)
def finish_session(session_id: int, phone: str, license_plate: str, db: Session = Depends(get_db)):
    item = get_session(db, session_id)
    if item.phone != phone or item.license_plate != license_plate.upper():
        raise api_error(403, "identity_mismatch", "The guest details do not match this session.")
    return complete_session(db, item)


@router.get("/sessions/{session_id}/estimate", response_model=SessionEstimateRead)
def estimate_session_cost(session_id: int, phone: str, license_plate: str, db: Session = Depends(get_db)):
    refresh_statuses(db)
    item = get_session(db, session_id)
    if item.phone != phone or item.license_plate != license_plate.upper():
        raise api_error(403, "identity_mismatch", "The guest details do not match this session.")
    end = item.ended_at if item.status == SessionStatus.COMPLETED and item.ended_at else utc_now()
    return SessionEstimateRead(
        estimated_cost=calculate_cost(db, item, end),
        projected_total_cost=calculate_cost(db, item, as_utc(item.expected_end_at)),
    )
