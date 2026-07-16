from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from ..auth import authenticate, create_token, require_admin
from ..database import get_db
from ..errors import api_error
from ..models import ParkingSession, ParkingSpot, Reservation, ReservationStatus, SessionStatus, SpotType, Tariff
from ..schemas import (
    BlockRequest,
    ExtensionRequest,
    LoginRequest,
    MoveRequest,
    ReservationCreate,
    ReservationRead,
    ReservationUpdate,
    SessionRead,
    SpotCreate,
    SpotBulkCreate,
    SpotBulkCreateResult,
    SpotRead,
    SpotUpdate,
    TariffRead,
    TariffBulkUpsert,
    TariffUpsert,
)
from ..services import QUICK_LIMIT, as_utc, assign_spot, complete_session, count_available_capacity, ensure_capacity, ensure_extension_allowed, ensure_spot_can_leave_capacity, ensure_vehicle_has_no_active_session, ensure_vehicle_has_no_overlapping_reservation, get_session, refresh_statuses, require_tariff, utc_now, validate_period


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/login")
def login(data: LoginRequest):
    if not authenticate(data.username, data.password):
        raise api_error(401, "invalid_credentials", "The administrator credentials are incorrect.")
    return {"access_token": create_token(), "token_type": "bearer"}


@router.get("/dashboard", dependencies=[Depends(require_admin)])
def dashboard(db: Session = Depends(get_db)):
    refresh_statuses(db)
    spots = db.scalars(select(ParkingSpot).order_by(ParkingSpot.number)).all()
    active_sessions = db.scalars(
        select(ParkingSession).options(joinedload(ParkingSession.spot)).where(
            ParkingSession.status.in_([SessionStatus.ACTIVE, SessionStatus.OVERDUE])
        )
    ).all()
    now = utc_now()
    available = sum(count_available_capacity(db, spot_type, now, now + QUICK_LIMIT) for spot_type in SpotType)
    return {
        "total_spots": len(spots),
        "available_spots": available,
        "blocked_spots": sum(1 for spot in spots if spot.is_blocked),
        "active_sessions": len(active_sessions),
        "overdue_sessions": sum(1 for item in active_sessions if item.status == SessionStatus.OVERDUE),
    }


@router.get("/spots", response_model=list[SpotRead], dependencies=[Depends(require_admin)])
def list_spots(db: Session = Depends(get_db)):
    return db.scalars(select(ParkingSpot).order_by(ParkingSpot.number)).all()


@router.post("/spots", response_model=SpotRead, status_code=201, dependencies=[Depends(require_admin)])
def create_spot(data: SpotCreate, db: Session = Depends(get_db)):
    item = ParkingSpot(**data.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise api_error(409, "spot_number_exists", "A parking spot with this number already exists.") from exc
    db.refresh(item)
    return item


@router.post("/spots/bulk", response_model=SpotBulkCreateResult, status_code=201, dependencies=[Depends(require_admin)])
def create_spots_bulk(data: SpotBulkCreate, db: Session = Depends(get_db)):
    if data.start_number is None:
        last_number = db.scalar(select(func.max(ParkingSpot.number))) or 0
        requested_numbers = list(range(last_number + 1, last_number + data.quantity + 1))
        existing_numbers: set[int] = set()
        created_numbers = requested_numbers
    else:
        requested_numbers = list(range(data.start_number, data.start_number + data.quantity))
        existing_numbers = set(db.scalars(select(ParkingSpot.number).where(ParkingSpot.number.in_(requested_numbers))).all())
        created_numbers = [number for number in requested_numbers if number not in existing_numbers]

    if created_numbers:
        db.add_all([ParkingSpot(number=number, spot_type=data.spot_type) for number in created_numbers])
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise api_error(409, "spot_number_exists", "One or more parking spot numbers already exist.") from exc

    return SpotBulkCreateResult(created_numbers=created_numbers, skipped_numbers=sorted(existing_numbers))


@router.put("/spots/{spot_id}", response_model=SpotRead, dependencies=[Depends(require_admin)])
def update_spot(spot_id: int, data: SpotUpdate, db: Session = Depends(get_db)):
    item = db.get(ParkingSpot, spot_id)
    if item is None:
        raise api_error(404, "spot_not_found", "Parking spot was not found.")
    if data.is_active != item.is_active or data.spot_type != item.spot_type:
        raise api_error(409, "spot_update_restricted", "Use the dedicated activation controls; changing a spot type is not supported.")
    item.number = data.number
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise api_error(409, "spot_number_exists", "A parking spot with this number already exists.") from exc
    db.refresh(item)
    return item


@router.delete("/spots/{spot_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_spot(spot_id: int, db: Session = Depends(get_db)):
    item = db.get(ParkingSpot, spot_id)
    if item is None:
        raise api_error(404, "spot_not_found", "Parking spot was not found.")
    used = db.scalar(select(ParkingSession.id).where(ParkingSession.spot_id == spot_id).limit(1))
    if used:
        raise api_error(409, "spot_in_use", "A parking spot with session history cannot be deleted; deactivate it instead.")
    refresh_statuses(db)
    ensure_spot_can_leave_capacity(db, item)
    db.delete(item); db.commit()


@router.post("/spots/{spot_id}/deactivate", response_model=SpotRead, dependencies=[Depends(require_admin)])
def deactivate_spot(spot_id: int, db: Session = Depends(get_db)):
    item = db.get(ParkingSpot, spot_id)
    if item is None:
        raise api_error(404, "spot_not_found", "Parking spot was not found.")
    if not item.is_active:
        return item
    active = db.scalar(select(ParkingSession.id).where(ParkingSession.spot_id == spot_id, ParkingSession.status.in_([SessionStatus.ACTIVE, SessionStatus.OVERDUE])))
    if active:
        raise api_error(409, "spot_occupied", "An occupied parking spot cannot be deactivated.")
    refresh_statuses(db)
    ensure_spot_can_leave_capacity(db, item)
    item.is_active = False
    db.commit(); db.refresh(item)
    return item


@router.post("/spots/{spot_id}/activate", response_model=SpotRead, dependencies=[Depends(require_admin)])
def activate_spot(spot_id: int, db: Session = Depends(get_db)):
    item = db.get(ParkingSpot, spot_id)
    if item is None:
        raise api_error(404, "spot_not_found", "Parking spot was not found.")
    item.is_active = True
    db.commit(); db.refresh(item)
    return item


@router.post("/spots/{spot_id}/block", response_model=SpotRead, dependencies=[Depends(require_admin)])
def block_spot(spot_id: int, data: BlockRequest, db: Session = Depends(get_db)):
    item = db.get(ParkingSpot, spot_id)
    if item is None:
        raise api_error(404, "spot_not_found", "Parking spot was not found.")
    active = db.scalar(select(ParkingSession.id).where(ParkingSession.spot_id == spot_id, ParkingSession.status.in_([SessionStatus.ACTIVE, SessionStatus.OVERDUE])))
    if active:
        raise api_error(409, "spot_occupied", "An occupied parking spot cannot be blocked.")
    refresh_statuses(db)
    ensure_spot_can_leave_capacity(db, item)
    item.is_blocked, item.block_reason = True, data.reason
    db.commit(); db.refresh(item)
    return item


@router.post("/spots/{spot_id}/unblock", response_model=SpotRead, dependencies=[Depends(require_admin)])
def unblock_spot(spot_id: int, db: Session = Depends(get_db)):
    item = db.get(ParkingSpot, spot_id)
    if item is None:
        raise api_error(404, "spot_not_found", "Parking spot was not found.")
    item.is_blocked, item.block_reason = False, None
    db.commit(); db.refresh(item)
    return item


@router.get("/tariffs", response_model=list[TariffRead], dependencies=[Depends(require_admin)])
def list_tariffs(db: Session = Depends(get_db)):
    return db.scalars(select(Tariff).order_by(Tariff.spot_type)).all()


@router.put("/tariffs", response_model=TariffRead, dependencies=[Depends(require_admin)])
def upsert_tariff(data: TariffUpsert, db: Session = Depends(get_db)):
    item = db.scalar(select(Tariff).where(Tariff.spot_type == data.spot_type))
    if item is None:
        item = Tariff(**data.model_dump()); db.add(item)
    else:
        item.price_per_30_minutes = data.price_per_30_minutes
    db.commit(); db.refresh(item)
    return item


@router.put("/tariffs/bulk", response_model=list[TariffRead], dependencies=[Depends(require_admin)])
def upsert_tariffs_bulk(data: TariffBulkUpsert, db: Session = Depends(get_db)):
    values = {item.spot_type: item.price_per_30_minutes for item in data.tariffs}
    if set(values) != set(SpotType):
        raise api_error(422, "tariff_types_incomplete", "Provide one tariff for every parking spot type.")
    existing = {item.spot_type: item for item in db.scalars(select(Tariff)).all()}
    for spot_type, price in values.items():
        if spot_type in existing:
            existing[spot_type].price_per_30_minutes = price
        else:
            db.add(Tariff(spot_type=spot_type, price_per_30_minutes=price))
    db.commit()
    return db.scalars(select(Tariff).order_by(Tariff.spot_type)).all()


@router.get("/reservations", response_model=list[ReservationRead], dependencies=[Depends(require_admin)])
def list_reservations(db: Session = Depends(get_db)):
    refresh_statuses(db)
    return db.scalars(select(Reservation).order_by(Reservation.starts_at)).all()


@router.post("/reservations", response_model=ReservationRead, status_code=201, dependencies=[Depends(require_admin)])
def admin_create_reservation(data: ReservationCreate, db: Session = Depends(get_db)):
    starts_at, ends_at = validate_period(data.starts_at, data.ends_at)
    ensure_vehicle_has_no_overlapping_reservation(db, data.license_plate, starts_at, ends_at)
    ensure_capacity(db, data.spot_type, starts_at, ends_at)
    values = data.model_dump(exclude={"starts_at", "ends_at"})
    item = Reservation(**values, starts_at=starts_at, ends_at=ends_at)
    db.add(item); db.commit(); db.refresh(item)
    return item


@router.put("/reservations/{reservation_id}", response_model=ReservationRead, dependencies=[Depends(require_admin)])
def admin_update_reservation(reservation_id: int, data: ReservationUpdate, db: Session = Depends(get_db)):
    item = db.get(Reservation, reservation_id)
    if item is None:
        raise api_error(404, "reservation_not_found", "Reservation was not found.")
    if item.status != ReservationStatus.CONFIRMED:
        raise api_error(409, "reservation_not_editable", "Only confirmed reservations can be changed.")
    starts_at, ends_at = validate_period(data.starts_at, data.ends_at)
    ensure_vehicle_has_no_overlapping_reservation(db, item.license_plate, starts_at, ends_at, item.id)
    ensure_capacity(db, data.spot_type, starts_at, ends_at, item.id)
    item.spot_type, item.starts_at, item.ends_at = data.spot_type, starts_at, ends_at
    db.commit(); db.refresh(item)
    return item


@router.post("/reservations/{reservation_id}/cancel", response_model=ReservationRead, dependencies=[Depends(require_admin)])
def admin_cancel_reservation(reservation_id: int, db: Session = Depends(get_db)):
    item = db.get(Reservation, reservation_id)
    if item is None:
        raise api_error(404, "reservation_not_found", "Reservation was not found.")
    if item.status != ReservationStatus.CONFIRMED:
        raise api_error(409, "reservation_not_cancellable", "Only confirmed reservations can be cancelled.")
    item.status = ReservationStatus.CANCELLED
    db.commit(); db.refresh(item)
    return item


@router.post("/reservations/{reservation_id}/check-in", response_model=SessionRead, dependencies=[Depends(require_admin)])
def admin_check_in(reservation_id: int, db: Session = Depends(get_db)):
    refresh_statuses(db)
    item = db.get(Reservation, reservation_id)
    if item is None:
        raise api_error(404, "reservation_not_found", "Reservation was not found.")
    now = utc_now()
    if item.status != ReservationStatus.CONFIRMED or now < as_utc(item.starts_at):
        raise api_error(409, "check_in_unavailable", "Check-in opens at the reservation start time.")
    ensure_vehicle_has_no_active_session(db, item.license_plate)
    spot = assign_spot(db, item.spot_type, now, item.ends_at)
    rate = require_tariff(db, item.spot_type).price_per_30_minutes
    session = ParkingSession(reservation_id=item.id, spot_id=spot.id, phone=item.phone, license_plate=item.license_plate, started_at=now, expected_end_at=item.ends_at, rate_per_30_minutes=rate)
    item.status = ReservationStatus.CHECKED_IN
    db.add(session); db.commit()
    return get_session(db, session.id)


@router.get("/sessions", response_model=list[SessionRead], dependencies=[Depends(require_admin)])
def list_sessions(db: Session = Depends(get_db)):
    refresh_statuses(db)
    return db.scalars(select(ParkingSession).options(joinedload(ParkingSession.spot)).order_by(ParkingSession.started_at.desc())).all()


@router.post("/sessions/{session_id}/complete", response_model=SessionRead, dependencies=[Depends(require_admin)])
def admin_complete_session(session_id: int, db: Session = Depends(get_db)):
    return complete_session(db, get_session(db, session_id))


@router.post("/sessions/{session_id}/extend", response_model=SessionRead, dependencies=[Depends(require_admin)])
def admin_extend_session(session_id: int, data: ExtensionRequest, db: Session = Depends(get_db)):
    refresh_statuses(db)
    item = get_session(db, session_id)
    new_end = as_utc(data.expected_end_at)
    ensure_extension_allowed(item, new_end)
    ensure_capacity(db, item.spot.spot_type, as_utc(item.expected_end_at), new_end, exclude_session_id=item.id)
    if item.reservation_id is None:
        item.extension_count += 1
    item.expected_end_at = new_end
    item.status = SessionStatus.ACTIVE
    db.commit()
    return get_session(db, item.id)


@router.post("/sessions/{session_id}/move", response_model=SessionRead, dependencies=[Depends(require_admin)])
def move_session(session_id: int, data: MoveRequest, db: Session = Depends(get_db)):
    item = get_session(db, session_id)
    if item.status not in [SessionStatus.ACTIVE, SessionStatus.OVERDUE]:
        raise api_error(409, "session_not_movable", "Only active or overdue parking sessions can be moved.")
    target = db.get(ParkingSpot, data.spot_id)
    if target is None or not target.is_active or target.is_blocked or target.spot_type != item.spot.spot_type:
        raise api_error(409, "invalid_target_spot", "The target parking spot must be available and have the same type.")
    occupied = db.scalar(select(ParkingSession.id).where(ParkingSession.spot_id == target.id, ParkingSession.id != item.id, ParkingSession.status.in_([SessionStatus.ACTIVE, SessionStatus.OVERDUE])))
    if occupied:
        raise api_error(409, "target_spot_occupied", "The target parking spot is occupied.")
    item.spot_id = target.id; db.commit()
    return get_session(db, item.id)


@router.get("/statistics", dependencies=[Depends(require_admin)])
def statistics(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(ParkingSession.id))) or 0
    completed = db.scalar(select(func.count(ParkingSession.id)).where(ParkingSession.status == SessionStatus.COMPLETED)) or 0
    revenue = db.scalar(select(func.coalesce(func.sum(ParkingSession.total_cost), 0))) or 0
    return {"total_sessions": total, "completed_sessions": completed, "simulated_revenue_usd": str(revenue)}
