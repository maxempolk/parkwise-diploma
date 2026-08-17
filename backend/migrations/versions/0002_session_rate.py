"""Store the tariff rate used when a parking session starts."""

import sqlalchemy as sa
from alembic import op

revision = "0002_session_rate"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("parking_sessions", sa.Column("rate_per_30_minutes", sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("parking_sessions", "rate_per_30_minutes")
