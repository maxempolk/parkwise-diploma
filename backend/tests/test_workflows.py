from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import ParkingSession, ParkingSpot, Reservation, ReservationStatus, SessionStatus, SpotType, Tariff
from app.services import calculate_cost, refresh_statuses


def next_slot(hours: int = 2) -> datetime:
    value = datetime.now(timezone.utc) + timedelta(hours=hours)
    return value.replace(minute=0 if value.minute < 30 else 30, second=0, microsecond=0) + timedelta(minutes=30)


def check_in_slot() -> datetime:
    value = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    if value.minute < 30:
        return value.replace(minute=30)
    return (value + timedelta(hours=1)).replace(minute=0)


def configure(client, headers, count: int = 1):
    client.put("/api/admin/tariffs", headers=headers, json={"spot_type": "standard", "price_per_30_minutes": "5.00"})
    for number in range(1, count + 1):
        assert client.post("/api/admin/spots", headers=headers, json={"number": number, "spot_type": "standard"}).status_code == 201


def test_admin_routes_require_a_token(client):
    assert client.get("/api/admin/spots").status_code == 401
    assert client.post("/api/admin/login", json={"username": "admin", "password": "wrong"}).status_code == 401


def test_quick_parking_complete_workflow(client, admin_headers):
    configure(client, admin_headers)
    started = client.post("/api/parking/quick", json={"phone": "+15550100", "license_plate": "abc123", "spot_type": "standard"})
    assert started.status_code == 201
    session = started.json()
    assert session["spot"]["number"] == 1
    assert session["license_plate"] == "ABC123"
    assert datetime.fromisoformat(session["started_at"]).tzinfo is not None
    assert datetime.fromisoformat(session["expected_end_at"]).tzinfo is not None

    duplicate = client.post("/api/parking/quick", json={"phone": "+15550101", "license_plate": "XYZ999", "spot_type": "standard"})
    assert duplicate.status_code == 409

    original_end = datetime.fromisoformat(session["expected_end_at"])
    extended = client.post(
        f"/api/sessions/{session['id']}/extend?phone=%2B15550100&license_plate=ABC123",
        json={"expected_end_at": (original_end + timedelta(minutes=30)).isoformat()},
    )
    assert extended.status_code == 200
    assert datetime.fromisoformat(extended.json()["expected_end_at"]) > original_end
    assert extended.json()["status"] == "active"

    overview = client.get("/api/me?phone=%2B15550100&license_plate=ABC123")
    assert overview.status_code == 200
    assert overview.json()["sessions"][0]["id"] == session["id"]
    assert overview.json()["sessions"][0]["status"] == "active"

    completed = client.post(f"/api/sessions/{session['id']}/complete?phone=%2B15550100&license_plate=ABC123")
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert Decimal(completed.json()["total_cost"]) >= Decimal("5.00")


def test_vehicle_cannot_start_two_active_sessions(client, admin_headers):
    configure(client, admin_headers, count=2)
    payload = {"phone": "+15550100", "license_plate": "ABC123", "spot_type": "standard"}
    assert client.post("/api/parking/quick", json=payload).status_code == 201
    duplicate = client.post("/api/parking/quick", json={**payload, "phone": "+15550101"})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "active_session_exists"


def test_reservation_conflict_buffer_and_check_in(client, admin_headers, db_session):
    configure(client, admin_headers)
    start = check_in_slot()
    end = start + timedelta(hours=1)
    payload = {"phone": "+15550100", "license_plate": "ONE1", "spot_type": "standard", "starts_at": start.isoformat(), "ends_at": end.isoformat()}
    first = client.post("/api/reservations", json=payload)
    assert first.status_code == 201

    touching = {**payload, "license_plate": "TWO2", "starts_at": end.isoformat(), "ends_at": (end + timedelta(minutes=30)).isoformat()}
    assert client.post("/api/reservations", json=touching).status_code == 409

    early_check_in = client.post(f"/api/admin/reservations/{first.json()['id']}/check-in", headers=admin_headers)
    assert early_check_in.status_code == 409
    assert early_check_in.json()["detail"]["code"] == "check_in_unavailable"

    reservation = db_session.get(Reservation, first.json()["id"])
    reservation.starts_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    reservation.ends_at = datetime.now(timezone.utc) + timedelta(hours=1)
    db_session.commit()
    checked_in = client.post(f"/api/admin/reservations/{first.json()['id']}/check-in", headers=admin_headers)
    assert checked_in.status_code == 200
    assert checked_in.json()["spot"]["number"] == 1


def test_vehicle_cannot_hold_overlapping_reservations(client, admin_headers):
    configure(client, admin_headers, count=3)
    start = next_slot()
    payload = {
        "phone": "+15550100",
        "license_plate": "ONE1",
        "spot_type": "standard",
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=1)).isoformat(),
    }
    assert client.post("/api/reservations", json=payload).status_code == 201
    duplicate = client.post("/api/reservations", json={**payload, "spot_type": "ev"})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "overlapping_vehicle_reservation"


def test_blocked_spot_is_not_available(client, admin_headers):
    configure(client, admin_headers)
    spot = client.get("/api/admin/spots", headers=admin_headers).json()[0]
    assert client.post(f"/api/admin/spots/{spot['id']}/block", headers=admin_headers, json={"reason": "Maintenance"}).status_code == 200
    response = client.post("/api/parking/quick", json={"phone": "+15550100", "license_plate": "ABC123", "spot_type": "standard"})
    assert response.status_code == 409


def test_spot_cannot_be_removed_from_capacity_when_a_confirmed_reservation_needs_it(client, admin_headers):
    configure(client, admin_headers)
    start = next_slot()
    reservation = client.post("/api/reservations", json={
        "phone": "+15550100", "license_plate": "ONE1", "spot_type": "standard",
        "starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=1)).isoformat(),
    })
    assert reservation.status_code == 201
    spot_id = client.get("/api/admin/spots", headers=admin_headers).json()[0]["id"]
    assert client.post(f"/api/admin/spots/{spot_id}/block", headers=admin_headers, json={"reason": "Maintenance"}).status_code == 409
    assert client.post(f"/api/admin/spots/{spot_id}/deactivate", headers=admin_headers).status_code == 409
    assert client.delete(f"/api/admin/spots/{spot_id}", headers=admin_headers).status_code == 409


def test_guest_availability_uses_real_capacity(client, admin_headers):
    configure(client, admin_headers, count=2)
    client.put("/api/admin/tariffs", headers=admin_headers, json={"spot_type": "ev", "price_per_30_minutes": "6.00"})
    client.post("/api/admin/spots", headers=admin_headers, json={"number": 10, "spot_type": "ev"})

    availability = client.get("/api/availability")
    assert availability.status_code == 200
    assert availability.json() == {"standard": 2, "ev": 1, "accessible": 0, "total": 3}


def test_guest_availability_for_a_selected_period_uses_reservations_and_buffer(client, admin_headers):
    configure(client, admin_headers, count=2)
    start = next_slot()
    end = start + timedelta(hours=1)
    reservation = client.post("/api/reservations", json={
        "phone": "+15550100", "license_plate": "ONE1", "spot_type": "standard",
        "starts_at": start.isoformat(), "ends_at": end.isoformat(),
    })
    assert reservation.status_code == 201

    during = client.get("/api/availability", params={"starts_at": start.isoformat(), "ends_at": end.isoformat()})
    assert during.status_code == 200
    assert during.json()["standard"] == 1

    buffered = client.get("/api/availability", params={
        "starts_at": (start - timedelta(minutes=10)).isoformat(),
        "ends_at": (start - timedelta(minutes=5)).isoformat(),
    })
    assert buffered.status_code == 200
    assert buffered.json()["standard"] == 1


def test_guest_tariffs_and_session_estimate_use_configured_price(client, admin_headers):
    configure(client, admin_headers)
    client.put("/api/admin/tariffs", headers=admin_headers, json={"spot_type": "standard", "price_per_30_minutes": "7.00"})
    tariffs = client.get("/api/tariffs")
    assert tariffs.status_code == 200
    assert tariffs.json()[0]["price_per_30_minutes"] == "7.00"

    started = client.post("/api/parking/quick", json={"phone": "+15550100", "license_plate": "ABC123", "spot_type": "standard"}).json()
    estimate = client.get(f"/api/sessions/{started['id']}/estimate?phone=%2B15550100&license_plate=ABC123")
    assert estimate.status_code == 200
    assert estimate.json()["estimated_cost"] == "7.00"


def test_session_keeps_its_starting_tariff_when_the_admin_changes_prices(client, admin_headers):
    configure(client, admin_headers)
    started = client.post("/api/parking/quick", json={"phone": "+15550100", "license_plate": "ABC123", "spot_type": "standard"}).json()
    assert started["rate_per_30_minutes"] == "5.00"
    client.put("/api/admin/tariffs", headers=admin_headers, json={"spot_type": "standard", "price_per_30_minutes": "9.00"})
    estimate = client.get(f"/api/sessions/{started['id']}/estimate?phone=%2B15550100&license_plate=ABC123")
    assert estimate.status_code == 200
    assert estimate.json()["estimated_cost"] == "5.00"


def test_admin_saves_all_tariffs_atomically(client, admin_headers):
    configure(client, admin_headers)
    incomplete = client.put("/api/admin/tariffs/bulk", headers=admin_headers, json={"tariffs": [
        {"spot_type": "standard", "price_per_30_minutes": "9.00"},
        {"spot_type": "ev", "price_per_30_minutes": "8.00"},
        {"spot_type": "standard", "price_per_30_minutes": "7.00"},
    ]})
    assert incomplete.status_code == 422
    assert client.get("/api/admin/tariffs", headers=admin_headers).json()[0]["price_per_30_minutes"] == "5.00"


def test_admin_can_bulk_create_spots_and_skip_existing_numbers(client, admin_headers):
    first = client.post("/api/admin/spots/bulk", headers=admin_headers, json={"start_number": 1, "quantity": 3, "spot_type": "standard"})
    assert first.status_code == 201
    assert first.json() == {"created_numbers": [1, 2, 3], "skipped_numbers": []}

    second = client.post("/api/admin/spots/bulk", headers=admin_headers, json={"start_number": 2, "quantity": 3, "spot_type": "ev"})
    assert second.status_code == 201
    assert second.json() == {"created_numbers": [4], "skipped_numbers": [2, 3]}


def test_admin_can_bulk_create_spots_with_automatic_numbers(client, admin_headers):
    client.post("/api/admin/spots", headers=admin_headers, json={"number": 4, "spot_type": "standard"})
    response = client.post("/api/admin/spots/bulk", headers=admin_headers, json={"quantity": 3, "spot_type": "ev"})
    assert response.status_code == 201
    assert response.json() == {"created_numbers": [5, 6, 7], "skipped_numbers": []}


def test_admin_can_cancel_reservation_complete_and_move_an_active_session(client, admin_headers):
    configure(client, admin_headers, count=2)
    start = next_slot()
    reservation = client.post("/api/reservations", json={
        "phone": "+15550100", "license_plate": "ONE1", "spot_type": "standard",
        "starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=1)).isoformat(),
    }).json()
    cancelled = client.post(f"/api/admin/reservations/{reservation['id']}/cancel", headers=admin_headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    session = client.post("/api/parking/quick", json={"phone": "+15550101", "license_plate": "CAR2", "spot_type": "standard"}).json()
    original_end = datetime.fromisoformat(session["expected_end_at"])
    extended = client.post(f"/api/admin/sessions/{session['id']}/extend", headers=admin_headers, json={"expected_end_at": (original_end + timedelta(hours=1)).isoformat()})
    assert extended.status_code == 200
    assert datetime.fromisoformat(extended.json()["expected_end_at"]) == original_end + timedelta(hours=1)

    moved = client.post(f"/api/admin/sessions/{session['id']}/move", headers=admin_headers, json={"spot_id": 2})
    assert moved.status_code == 200
    assert moved.json()["spot_id"] == 2

    completed = client.post(f"/api/admin/sessions/{session['id']}/complete", headers=admin_headers)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert client.post(f"/api/admin/sessions/{session['id']}/move", headers=admin_headers, json={"spot_id": 1}).status_code == 409


def test_status_refresh_and_reserved_cost(db_session):
    spot = ParkingSpot(number=1, spot_type=SpotType.STANDARD)
    tariff = Tariff(spot_type=SpotType.STANDARD, price_per_30_minutes=Decimal("5.00"))
    start = datetime.now(timezone.utc) - timedelta(hours=2)
    reservation = Reservation(phone="1", license_plate="A", spot_type=SpotType.STANDARD, starts_at=start, ends_at=start + timedelta(hours=1), status=ReservationStatus.CONFIRMED)
    db_session.add_all([spot, tariff, reservation]); db_session.commit()
    session = ParkingSession(reservation_id=reservation.id, spot_id=spot.id, phone="1", license_plate="A", started_at=start, expected_end_at=start + timedelta(minutes=30), status=SessionStatus.ACTIVE)
    db_session.add(session); db_session.commit()
    refresh_statuses(db_session)
    assert reservation.status == ReservationStatus.NO_SHOW
    assert session.status == SessionStatus.OVERDUE
    assert calculate_cost(db_session, session, start + timedelta(minutes=10)) == Decimal("10.00")
