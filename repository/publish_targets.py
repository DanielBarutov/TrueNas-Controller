"""SQLAlchemy repository for materialized publish targets."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.ports import PublishTargetRepository
from domain.publish import PublishTarget
from repository.models import PublishTargetRecord, StationRecord, utc_now


class SqlAlchemyPublishTargetRepository(PublishTargetRepository):
    """Persist target rows while exposing stable station IDs to application."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_job(self, job_id: UUID) -> tuple[PublishTarget, ...]:
        statement = (
            select(PublishTargetRecord, StationRecord)
            .join(StationRecord, PublishTargetRecord.station_id == StationRecord.id)
            .where(PublishTargetRecord.job_id == job_id)
            .order_by(PublishTargetRecord.selected_at, StationRecord.station_id)
        )
        rows = (await self._session.execute(statement)).all()
        return tuple(self._to_domain(record, station) for record, station in rows)

    async def add(self, target: PublishTarget) -> None:
        station = await self._session.scalar(
            select(StationRecord).where(StationRecord.station_id == target.station_id)
        )
        if station is None:
            raise ValueError("station not found")
        selection_time = utc_now()
        selected_at = selection_time if target.selected else None
        deselected_at = None if target.selected else selection_time
        self._session.add(
            PublishTargetRecord(
                id=target.id,
                job_id=target.job_id,
                station_id=station.id,
                selected_at=selected_at,
                deselected_at=deselected_at,
                preflight_status=target.preflight_status,
                preflight_result=target.preflight_result,
                old_version_id=target.old_version_id,
                new_version_id=target.new_version_id,
                old_mapping=target.old_mapping,
                new_mapping=target.new_mapping,
                switch_status=target.switch_status,
                verify_status=target.verify_status,
                error_code=target.error_code,
                error_message=target.error_message,
                progress_percent=target.progress_percent,
            )
        )

    async def add_many(self, targets: tuple[PublishTarget, ...]) -> None:
        for target in targets:
            await self.add(target)

    async def update(self, target: PublishTarget) -> None:
        record = await self._session.get(PublishTargetRecord, target.id, with_for_update=True)
        if record is None or record.job_id != target.job_id:
            raise ValueError("publish target not found")
        record.preflight_status = target.preflight_status
        record.preflight_result = target.preflight_result
        record.old_version_id = target.old_version_id
        record.new_version_id = target.new_version_id
        record.old_mapping = target.old_mapping
        record.new_mapping = target.new_mapping
        record.switch_status = target.switch_status
        record.verify_status = target.verify_status
        record.error_code = target.error_code
        record.error_message = target.error_message
        record.progress_percent = target.progress_percent

    @staticmethod
    def _to_domain(record: PublishTargetRecord, station: StationRecord) -> PublishTarget:
        return PublishTarget(
            id=record.id,
            job_id=record.job_id,
            station_id=station.station_id,
            selected=record.deselected_at is None,
            preflight_status=record.preflight_status,
            preflight_result=record.preflight_result,
            old_version_id=record.old_version_id,
            new_version_id=record.new_version_id,
            old_mapping=record.old_mapping,
            new_mapping=record.new_mapping,
            switch_status=record.switch_status,
            verify_status=record.verify_status,
            error_code=record.error_code,
            error_message=record.error_message,
            progress_percent=record.progress_percent,
        )
