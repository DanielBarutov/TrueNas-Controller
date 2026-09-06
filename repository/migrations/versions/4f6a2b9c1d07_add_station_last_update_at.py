"""record the last successfully verified update per station

Revision ID: 4f6a2b9c1d07
Revises: c2e8f5a19b03
Create Date: 2026-09-05 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "4f6a2b9c1d07"
down_revision: str | None = "c2e8f5a19b03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stations",
        sa.Column("last_update_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stations", "last_update_at")
