"""Build a domain snapshot from safe local agent collectors."""

from datetime import UTC, datetime
from uuid import UUID

from agent.drive_monitor import DriveSnapshotCollector
from agent.process_monitor import ProcessSnapshotCollector
from domain.snapshot import ProcessSnapshot


class AgentSnapshotCollector:
    """Compose process and drive readers into one snapshot."""

    def __init__(
        self,
        station_id: UUID,
        agent_version: str,
        process_collector: ProcessSnapshotCollector,
        drive_collector: DriveSnapshotCollector,
    ) -> None:
        self._station_id = station_id
        self._agent_version = agent_version
        self._process_collector = process_collector
        self._drive_collector = drive_collector

    def collect(self, captured_at: datetime | None = None) -> ProcessSnapshot:
        """Capture local process and drive state."""

        return ProcessSnapshot(
            station_id=self._station_id,
            captured_at=captured_at or datetime.now(UTC),
            agent_version=self._agent_version,
            processes=self._process_collector.collect(),
            drives=(self._drive_collector.collect(),),
        )
