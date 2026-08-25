"""add station-less provisioning tokens

Revision ID: 7f5d0f1c9b42
Revises: bee81bac70cc
Create Date: 2026-08-25 14:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "7f5d0f1c9b42"
down_revision: str | None = "bee81bac70cc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provisioning_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provisioning_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_provisioning_tokens_token_hash")),
    )
    op.create_index(
        "ix_provisioning_tokens_expires_at",
        "provisioning_tokens",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_provisioning_tokens_expires_at", table_name="provisioning_tokens")
    op.drop_table("provisioning_tokens")
