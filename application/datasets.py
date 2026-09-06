"""Application use cases for the operator dataset inventory."""

from dataclasses import dataclass
from uuid import UUID

from application.ports import DatasetCleanupTaskQueue, UnitOfWorkFactory
from domain.publish import PublishArtifact


class DatasetSelectionError(ValueError):
    """The operator selected an unknown or unsafe dataset record."""


@dataclass(frozen=True, slots=True)
class DatasetDeletionDispatch:
    """Minimal acknowledgement returned after a worker task is queued."""

    artifact_ids: tuple[UUID, ...]


class ListDatasetsUseCase:
    """Load tracked publish artifacts for the operator inventory."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, include_deleted: bool = False) -> tuple[PublishArtifact, ...]:
        async with self._uow_factory() as uow:
            return await uow.publish_artifacts.list_all(include_deleted=include_deleted)


class QueueDatasetCleanupUseCase:
    """Validate selected tracked artifacts and hand deletion to the worker.

    The API only queues stable database IDs. TrueNAS credentials and the remote
    delete operation remain in the worker process.
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        queue: DatasetCleanupTaskQueue,
    ) -> None:
        self._uow_factory = uow_factory
        self._queue = queue

    async def execute(self, *, artifact_ids: tuple[UUID, ...]) -> DatasetDeletionDispatch:
        normalized_ids = tuple(dict.fromkeys(artifact_ids))
        if not normalized_ids:
            raise DatasetSelectionError("at least one dataset must be selected")

        async with self._uow_factory() as uow:
            artifacts = await uow.publish_artifacts.list_by_ids(normalized_ids)
        by_id = {artifact.id: artifact for artifact in artifacts}
        missing = tuple(artifact_id for artifact_id in normalized_ids if artifact_id not in by_id)
        if missing:
            raise DatasetSelectionError("one or more selected datasets were not found")
        if any(by_id[artifact_id].is_current for artifact_id in normalized_ids):
            raise DatasetSelectionError("the dataset currently used by a station cannot be deleted")
        if any(by_id[artifact_id].deleted_at is not None for artifact_id in normalized_ids):
            raise DatasetSelectionError("one or more selected datasets were already deleted")

        self._queue.enqueue(artifact_ids=normalized_ids)
        return DatasetDeletionDispatch(normalized_ids)
