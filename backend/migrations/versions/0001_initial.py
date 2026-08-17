"""Initial parking schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


spot_type = sa.Enum("STANDARD", "EV", "ACCESSIBLE", name="spottype")
reservation_status = sa.Enum("CONFIRMED", "CANCELLED", "NO_SHOW", "CHECKED_IN", name="reservationstatus")
session_status = sa.Enum("ACTIVE", "OVERDUE", "COMPLETED", name="sessionstatus")


def upgrade() -> None:
    op.create_table(
        "parking_spots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("spot_type", spot_type, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_blocked", sa.Boolean(), nullable=False),
        sa.Column("block_reason", sa.String(250)),
        sa.UniqueConstraint("number"),
    )
    op.create_index("ix_parking_spots_number", "parking_spots", ["number"])
    op.create_index("ix_parking_spots_spot_type", "parking_spots", ["spot_type"])
    op.create_table(
        "tariffs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("spot_type", spot_type, nullable=False, unique=True),
        sa.Column("price_per_30_minutes", sa.Numeric(10, 2), nullable=False),
    )
    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("license_plate", sa.String(20), nullable=False),
        sa.Column("spot_type", spot_type, nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", reservation_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name in ("phone", "license_plate", "spot_type", "starts_at", "ends_at", "status"):
        op.create_index(f"ix_reservations_{name}", "reservations", [name])
    op.create_table(
        "parking_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reservation_id", sa.Integer(), sa.ForeignKey("reservations.id"), unique=True),
        sa.Column("spot_id", sa.Integer(), sa.ForeignKey("parking_spots.id"), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("license_plate", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("status", session_status, nullable=False),
        sa.Column("total_cost", sa.Numeric(10, 2)),
    )
    for name in ("spot_id", "phone", "license_plate", "status"):
        op.create_index(f"ix_parking_sessions_{name}", "parking_sessions", [name])


def downgrade() -> None:
    op.drop_table("parking_sessions")
    op.drop_table("reservations")
    op.drop_table("tariffs")
    op.drop_table("parking_spots")
