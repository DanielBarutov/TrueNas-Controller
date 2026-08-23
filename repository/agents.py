"""SQLAlchemy agent enrollment and heartbeat repository."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.agent import AgentBinding
from domain.snapshot import ProcessSnapshot
from repository.models import AgentRecord, ProcessSnapshotRecord, StationRecord


class SqlAlchemyAgentRepository:
    """Persist agent credentials and normalized heartbeat snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, agent: AgentBinding) -> None:
        station = await self._session.scalar(
            select(StationRecord).where(StationRecord.station_id == agent.station_id)
        )
        if station is None:
            raise ValueError("station not found")
        self._session.add(
            AgentRecord(
                id=agent.id,
                station_id=station.id,
                agent_uuid=agent.agent_uuid,
                agent_version=agent.agent_version,
                credential_hash=agent.credential_hash,
                credential_created_at=agent.credential_created_at,
                revoked_at=agent.revoked_at,
                last_ip_addresses=list(agent.last_ip_addresses),
                last_mac_addresses=list(agent.last_mac_addresses),
                status="enrolled",
            )
        )

    async def get_by_credential_hash(self, credential_hash: str) -> AgentBinding | None:
        statement = (
            select(AgentRecord, StationRecord)
            .join(StationRecord, AgentRecord.station_id == StationRecord.id)
            .where(AgentRecord.credential_hash == credential_hash)
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        record, station = row
        return AgentBinding(
            id=record.id,
            station_id=station.station_id,
            agent_uuid=record.agent_uuid,
            agent_version=record.agent_version,
            credential_hash=record.credential_hash or "",
            credential_created_at=record.credential_created_at,
            revoked_at=record.revoked_at,
            station_enabled=station.enabled,
            station_deleted_at=station.deleted_at,
            last_ip_addresses=tuple(record.last_ip_addresses),
            last_mac_addresses=tuple(record.last_mac_addresses),
        )

    async def record_heartbeat(
        self,
        agent_id: UUID,
        snapshot: ProcessSnapshot,
        received_at: datetime,
        *,
        hostname: str | None = None,
        ip_addresses: tuple[str, ...] | None = None,
        mac_addresses: tuple[str, ...] | None = None,
    ) -> None:
        statement = (
            select(AgentRecord, StationRecord)
            .join(StationRecord, AgentRecord.station_id == StationRecord.id)
            .where(
                AgentRecord.id == agent_id,
                StationRecord.station_id == snapshot.station_id,
            )
            .with_for_update()
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            raise ValueError("agent/station binding not found")

        agent, station = row
        agent.agent_version = snapshot.agent_version
        agent.last_seen_at = received_at
        agent.last_heartbeat_at = received_at
        agent.last_process_snapshot_at = snapshot.captured_at
        agent.last_drive_snapshot_at = snapshot.captured_at
        if hostname is not None:
            station.hostname = hostname
        if ip_addresses is not None:
            agent.last_ip_addresses = list(ip_addresses)
        if mac_addresses is not None:
            agent.last_mac_addresses = list(mac_addresses)
        agent.status = "online"
        if station.enabled and station.deleted_at is None:
            station.state = "online"
        self._session.add(
            ProcessSnapshotRecord(
                station_id=station.id,
                captured_at=snapshot.captured_at,
                received_at=received_at,
                processes=[
                    {"name": item.name, "pid": item.pid, "path": item.path}
                    for item in snapshot.processes
                ],
                drives=[
                    {
                        "letter": item.letter,
                        "present": item.present,
                        "free_bytes": item.free_bytes,
                    }
                    for item in snapshot.drives
                ],
                game_version_marker=snapshot.game_version_marker,
                agent_version=snapshot.agent_version,
                freshness_status="fresh",
            )
        )
