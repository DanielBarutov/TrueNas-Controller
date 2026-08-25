"""set live publish as the new default for newly created jobs

Revision ID: b1d3e7f4a902
Revises: 8a9c2d7e4f11
Create Date: 2026-08-25 17:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "b1d3e7f4a902"
down_revision: str | None = "8a9c2d7e4f11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "publish_jobs",
        "dry_run",
        existing_type=sa.Boolean(),
        server_default=sa.false(),
    )


def downgrade() -> None:
    op.alter_column(
        "publish_jobs",
        "dry_run",
        existing_type=sa.Boolean(),
        server_default=sa.true(),
    )
