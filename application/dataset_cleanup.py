"""Retention use case for datasets created by successful publish jobs."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from application.ports import TrueNASWriteClient, UnitOfWorkFactory
from domain.publish import PublishArtifact


@dataclass(frozen=True, slots=True)
class DatasetCleanupResult:
    """Bounded outcome of one retention pass."""

    inspected: int
    deleted: int
    failed: int
    dry_run: bool


class DatasetCleanupUseCase:
    """Delete only old, non-current artifacts recorded by the controller.

    The repository is the source of truth for the allow-list of datasets. The
    use case never scans or constructs arbitrary TrueNAS paths and never
    deletes the current artifact for a station.
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        *,
        retention_days: int,
        batch_size: int,
        apply_enabled: bool,
    ) -> None:
        if retention_days < 1:
            raise ValueError("retention_days must be positive")
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self._uow_factory = uow_factory
        self._retention_days = retention_days
        self._batch_size = batch_size
        self._apply_enabled = apply_enabled

    async def execute(
        self,
        *,
        write_client: TrueNASWriteClient | None = None,
        now: datetime | None = None,
    ) -> DatasetCleanupResult:
        current_time = now or datetime.now(UTC)
        cutoff = current_time - timedelta(days=self._retention_days)
        async with self._uow_factory() as uow:
            candidates = await uow.publish_artifacts.list_cleanup_candidates(
                before=cutoff,
                limit=self._batch_size,
            )

        if not self._apply_enabled:
            return DatasetCleanupResult(
                inspected=len(candidates),
                deleted=0,
                failed=0,
                dry_run=True,
            )
        if write_client is None:
            raise ValueError("write_client is required when dataset cleanup is enabled")

        deleted = 0
        failed = 0
        for artifact in candidates:
            try:
                await write_client.delete_dataset(artifact.dataset_name)
            except Exception as error:
                failed += 1
                await self._mark_failed(artifact, error)
            else:
                deleted += 1
                await self._mark_deleted(artifact, current_time)
        return DatasetCleanupResult(
            inspected=len(candidates),
            deleted=deleted,
            failed=failed,
            dry_run=False,
        )

    async def _mark_deleted(self, artifact: PublishArtifact, deleted_at: datetime) -> None:
        async with self._uow_factory() as uow:
            await uow.publish_artifacts.mark_deleted(artifact.id, deleted_at)
            await uow.commit()

    async def _mark_failed(self, artifact: PublishArtifact, error: Exception) -> None:
        async with self._uow_factory() as uow:
            await uow.publish_artifacts.mark_cleanup_failed(
                artifact.id,
                _safe_error_detail(error),
            )
            await uow.commit()


def _safe_error_detail(error: Exception) -> str:
    detail = " ".join(str(error).split())
    return detail[:300] or error.__class__.__name__
