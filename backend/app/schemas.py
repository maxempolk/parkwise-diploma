from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import ReservationStatus, SessionStatus, SpotType


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GuestIdentity(BaseModel):
    phone: str = Field(min_length=5, max_length=30)
    license_plate: str = Field(min_length=2, max_length=20)

    @field_validator("phone", "license_plate")
    @classmethod
    def strip_and_uppercase(cls, value: str, info) -> str:
        value = value.strip()
        return value.upper() if info.field_name == "license_plate" else value


class QuickParkingCreate(GuestIdentity):
    spot_type: SpotType


class ReservationCreate(GuestIdentity):
    spot_type: SpotType
    starts_at: datetime
    ends_at: datetime


class ReservationUpdate(BaseModel):
    spot_type: SpotType
    starts_at: datetime
    ends_at: datetime


class ExtensionRequest(BaseModel):
    expected_end_at: datetime


class SpotCreate(BaseModel):
    number: int = Field(gt=0)
    spot_type: SpotType


class SpotBulkCreate(BaseModel):
    start_number: int | None = Field(default=None, gt=0)
    quantity: int = Field(gt=0, le=200)
    spot_type: SpotType


class SpotBulkCreateResult(BaseModel):
    created_numbers: list[int]
    skipped_numbers: list[int]


class SpotUpdate(BaseModel):
    number: int = Field(gt=0)
    spot_type: SpotType
    is_active: bool = True


class BlockRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=250)


class MoveRequest(BaseModel):
    spot_id: int


class TariffUpsert(BaseModel):
    spot_type: SpotType
    price_per_30_minutes: Decimal = Field(gt=0, decimal_places=2)


class TariffBulkUpsert(BaseModel):
    tariffs: list[TariffUpsert] = Field(min_length=3, max_length=3)

class LoginRequest(BaseModel):
    username: str
    password: str


class SpotRead(ApiModel):
    id: int
    number: int
    spot_type: SpotType
    is_active: bool
    is_blocked: bool
    block_reason: str | None


class TariffRead(ApiModel):
    id: int
    spot_type: SpotType
    price_per_30_minutes: Decimal


class ReservationRead(ApiModel):
    id: int
    phone: str
    license_plate: str
    spot_type: SpotType
    starts_at: datetime
    ends_at: datetime
    status: ReservationStatus

    @field_validator("starts_at", "ends_at", mode="after")
    @classmethod
    def serialize_as_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class SessionRead(ApiModel):
    id: int
    reservation_id: int | None
    spot_id: int
    phone: str
    license_plate: str
    started_at: datetime
    expected_end_at: datetime
    ended_at: datetime | None
    status: SessionStatus
    extension_count: int
    rate_per_30_minutes: Decimal | None
    total_cost: Decimal | None
    spot: SpotRead

    @field_validator("started_at", "expected_end_at", "ended_at", mode="after")
    @classmethod
    def serialize_as_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class SessionEstimateRead(BaseModel):
    estimated_cost: Decimal
    projected_total_cost: Decimal


class GuestOverview(BaseModel):
    reservations: list[ReservationRead]
    sessions: list[SessionRead]


class AvailabilityRead(BaseModel):
    standard: int
    ev: int
    accessible: int
    total: int
