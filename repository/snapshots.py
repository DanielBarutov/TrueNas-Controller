"""SQLAlchemy latest process-snapshot repository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.snapshot import DriveInfo, ProcessInfo, ProcessSnapshot
from repository.models import ProcessSnapshotRecord, StationRecord


class SqlAlchemyProcessSnapshotRepository:
    """Load only the newest snapshot for a stable station ID."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def latest(self, station_id: UUID) -> ProcessSnapshot | None:
        statement = (
            select(ProcessSnapshotRecord, StationRecord)
            .join(StationRecord, ProcessSnapshotRecord.station_id == StationRecord.id)
            .where(StationRecord.station_id == station_id)
            .order_by(ProcessSnapshotRecord.captured_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        record, station = row
        return ProcessSnapshot(
            station_id=station.station_id,
            captured_at=record.captured_at,
            agent_version=record.agent_version,
            processes=tuple(
                ProcessInfo(name=item["name"], pid=item.get("pid"), path=item.get("path"))
                for item in record.processes
            ),
            drives=tuple(
                DriveInfo(
                    letter=item["letter"],
                    present=item["present"],
                    free_bytes=item.get("free_bytes"),
                )
                for item in record.drives
            ),
        )
