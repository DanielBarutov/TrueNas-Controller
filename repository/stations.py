"""SQLAlchemy implementation of the application station port."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from application.ports import StationRepository
from domain.station import Station, StationStatus
from repository.models import AgentCommandRecord, AgentRecord, EnrollmentTokenRecord, StationRecord


class SqlAlchemyStationRepository(StationRepository):
    """Persist and read stations within the current UoW session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, station_id: UUID) -> Station | None:
        statement = select(StationRecord).where(StationRecord.station_id == station_id)
        record = await self._session.scalar(statement)
        return None if record is None else self._to_domain(record)

    async def list(self, *, include_disabled: bool = False) -> list[Station]:
        statement = select(StationRecord).where(StationRecord.deleted_at.is_(None))
        if not include_disabled:
            statement = statement.where(StationRecord.enabled.is_(True))
        statement = statement.order_by(StationRecord.display_name, StationRecord.station_id)
        records = (await self._session.scalars(statement)).all()
        return [self._to_domain(record) for record in records]

    async def add(self, station: Station) -> None:
        self._session.add(
            StationRecord(
                id=station.id,
                station_id=station.station_id,
                display_name=station.display_name,
                hostname=station.hostname,
                role=station.role,
                state=station.status,
                enabled=station.enabled,
                deleted_at=station.deleted_at,
            )
        )

    async def restore(self, station: Station) -> None:
        statement = select(StationRecord).where(StationRecord.station_id == station.station_id)
        record = await self._session.scalar(statement)
        if record is None or record.deleted_at is None:
            raise ValueError("deleted station not found")
        record.display_name = station.display_name
        record.hostname = station.hostname
        record.role = station.role
        record.state = station.status
        record.enabled = station.enabled
        record.deleted_at = station.deleted_at
        record.state_reason = None

    async def update_hostname(self, station_id: UUID, hostname: str) -> None:
        statement = select(StationRecord).where(StationRecord.station_id == station_id)
        record = await self._session.scalar(statement)
        if record is None:
            raise ValueError("station not found")
        record.hostname = hostname

    async def delete(self, station_id: UUID, deleted_at: datetime) -> bool:
        """Hide a station while removing credentials and pending agent work."""

        statement = select(StationRecord).where(
            StationRecord.station_id == station_id,
            StationRecord.deleted_at.is_(None),
        )
        record = await self._session.scalar(statement)
        if record is None:
            return False

        agent_ids = select(AgentRecord.id).where(AgentRecord.station_id == record.id)
        await self._session.execute(
            delete(AgentCommandRecord).where(AgentCommandRecord.agent_id.in_(agent_ids))
        )
        await self._session.execute(delete(AgentRecord).where(AgentRecord.station_id == record.id))
        await self._session.execute(
            update(EnrollmentTokenRecord)
            .where(
                EnrollmentTokenRecord.station_id == record.id,
                EnrollmentTokenRecord.revoked_at.is_(None),
            )
            .values(revoked_at=deleted_at)
        )
        record.enabled = False
        record.state = StationStatus.DISABLED
        record.state_reason = "removed by operator"
        record.deleted_at = deleted_at
        return True

    @staticmethod
    def _to_domain(record: StationRecord) -> Station:
        return Station(
            id=record.id,
            station_id=record.station_id,
            display_name=record.display_name,
            hostname=record.hostname,
            role=record.role,
            status=record.state,
            enabled=record.enabled,
            deleted_at=record.deleted_at,
        )
