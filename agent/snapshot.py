"""Build a domain snapshot from safe local agent collectors."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from agent.drive_monitor import DriveSnapshotCollector
from agent.process_monitor import ProcessSnapshotCollector
from domain.snapshot import ProcessSnapshot

MarkerReader = Callable[[], str | None]


class AgentSnapshotCollector:
    """Compose process, drive and optional marker readers into one snapshot."""

    def __init__(
        self,
        station_id: UUID,
        agent_version: str,
        process_collector: ProcessSnapshotCollector,
        drive_collector: DriveSnapshotCollector,
        marker_reader: MarkerReader | None = None,
    ) -> None:
        self._station_id = station_id
        self._agent_version = agent_version
        self._process_collector = process_collector
        self._drive_collector = drive_collector
        self._marker_reader = marker_reader

    def collect(self, captured_at: datetime | None = None) -> ProcessSnapshot:
        """Capture local state without guessing a game marker source."""

        marker = None
        if self._marker_reader is not None:
            try:
                marker = self._marker_reader()
            except OSError:
                marker = None
        return ProcessSnapshot(
            station_id=self._station_id,
            captured_at=captured_at or datetime.now(UTC),
            agent_version=self._agent_version,
            processes=self._process_collector.collect(),
            drives=(self._drive_collector.collect(),),
            game_version_marker=marker,
        )
