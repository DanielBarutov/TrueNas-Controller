from datetime import UTC, datetime
from uuid import uuid4

from agent.drive_monitor import DiskUsage, DriveSnapshotCollector
from agent.process_monitor import ProcessSnapshotCollector
from agent.snapshot import AgentSnapshotCollector


def test_agent_snapshot_collector_composes_collectors_and_handles_marker_failure() -> None:
    station_id = uuid4()
    captured_at = datetime(2026, 8, 23, 12, tzinfo=UTC)
    process_collector = ProcessSnapshotCollector(lambda **_: [])
    drive_collector = DriveSnapshotCollector(disk_usage=lambda _: DiskUsage(100, 10, 90))

    def unavailable_marker() -> str:
        raise OSError("marker source unavailable")

    snapshot = AgentSnapshotCollector(
        station_id,
        "0.1.0",
        process_collector,
        drive_collector,
        unavailable_marker,
    ).collect(captured_at)

    assert snapshot.station_id == station_id
    assert snapshot.captured_at == captured_at
    assert snapshot.agent_version == "0.1.0"
    assert snapshot.processes == ()
    assert snapshot.drives[0].free_bytes == 90
    assert snapshot.game_version_marker is None
