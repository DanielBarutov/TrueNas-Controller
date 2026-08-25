"""track datasets created by publish jobs

Revision ID: c2e8f5a19b03
Revises: b1d3e7f4a902
Create Date: 2026-08-25 17:15:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "c2e8f5a19b03"
down_revision: str | None = "b1d3e7f4a902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "publish_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("station_id", sa.Uuid(), nullable=False),
        sa.Column("source_dataset", sa.String(length=255), nullable=False),
        sa.Column("dataset_name", sa.String(length=255), nullable=False),
        sa.Column("snapshot_ref", sa.String(length=512), nullable=False),
        sa.Column("mapping_ref", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "current",
                "retired",
                "deleted",
                "cleanup_failed",
                name="storageartifactstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("is_current", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["publish_jobs.id"],
            name=op.f("fk_publish_artifacts_job_id_publish_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["station_id"],
            ["stations.station_id"],
            name=op.f("fk_publish_artifacts_station_id_stations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_publish_artifacts")),
        sa.UniqueConstraint("job_id", "station_id", name=op.f("uq_publish_artifacts_job_station")),
    )
    op.create_index(
        "ix_publish_artifacts_cleanup",
        "publish_artifacts",
        ["is_current", "status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_publish_artifacts_cleanup", table_name="publish_artifacts")
    op.drop_table("publish_artifacts")
