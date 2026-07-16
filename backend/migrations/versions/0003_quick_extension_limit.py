"""Track the one allowed extension for a quick-parking session."""

from alembic import op
import sqlalchemy as sa


revision = "0003_quick_extension_limit"
down_revision = "0002_session_rate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "parking_sessions",
        sa.Column("extension_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("parking_sessions", "extension_count")
