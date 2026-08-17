from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class SpotType(StrEnum):
    STANDARD = "standard"
    EV = "ev"
    ACCESSIBLE = "accessible"


class ReservationStatus(StrEnum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    CHECKED_IN = "checked_in"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    OVERDUE = "overdue"
    COMPLETED = "completed"


class ParkingSpot(Base):
    __tablename__ = "parking_spots"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(unique=True, index=True)
    spot_type: Mapped[SpotType] = mapped_column(Enum(SpotType), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    block_reason: Mapped[str | None] = mapped_column(String(250))


class Tariff(Base):
    __tablename__ = "tariffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    spot_type: Mapped[SpotType] = mapped_column(Enum(SpotType), unique=True)
    price_per_30_minutes: Mapped[Decimal] = mapped_column(Numeric(10, 2))


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(30), index=True)
    license_plate: Mapped[str] = mapped_column(String(20), index=True)
    spot_type: Mapped[SpotType] = mapped_column(Enum(SpotType), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus), default=ReservationStatus.CONFIRMED, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now().astimezone())
    session: Mapped["ParkingSession | None"] = relationship(back_populates="reservation")


class ParkingSession(Base):
    __tablename__ = "parking_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int | None] = mapped_column(ForeignKey("reservations.id"), unique=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("parking_spots.id"), index=True)
    phone: Mapped[str] = mapped_column(String(30), index=True)
    license_plate: Mapped[str] = mapped_column(String(20), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expected_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), default=SessionStatus.ACTIVE, index=True)
    extension_count: Mapped[int] = mapped_column(default=0)
    rate_per_30_minutes: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    reservation: Mapped[Reservation | None] = relationship(back_populates="session")
    spot: Mapped[ParkingSpot] = relationship()
