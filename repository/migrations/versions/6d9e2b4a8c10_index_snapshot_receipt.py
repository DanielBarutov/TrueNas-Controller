"""Index latest heartbeat lookup by controller receipt time.

Revision ID: 6d9e2b4a8c10
Revises: 4f6a2b9c1d07
Create Date: 2026-09-08 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "6d9e2b4a8c10"
down_revision: str | None = "4f6a2b9c1d07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_process_snapshots_station_received",
        "process_snapshots",
        ["station_id", "received_at", "captured_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_process_snapshots_station_received", table_name="process_snapshots")
