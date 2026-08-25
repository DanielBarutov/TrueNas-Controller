"""rename publish source field to dataset terminology

Revision ID: 8a9c2d7e4f11
Revises: 7f5d0f1c9b42
Create Date: 2026-08-25 14:10:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "8a9c2d7e4f11"
down_revision: str | None = "7f5d0f1c9b42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "publish_jobs",
        "game_name",
        new_column_name="source_dataset",
    )


def downgrade() -> None:
    op.alter_column(
        "publish_jobs",
        "source_dataset",
        new_column_name="game_name",
    )
