from pathlib import PureWindowsPath

import pytest

from agent.drive_monitor import DiskUsage, DriveSnapshotCollector


def test_drive_collector_reports_present_drive_and_free_bytes() -> None:
    seen: list[str] = []

    def disk_usage(path: str) -> DiskUsage:
        seen.append(path)
        return DiskUsage(total=100, used=40, free=60)

    result = DriveSnapshotCollector("d:", disk_usage).collect()

    assert result.letter == "D:"
    assert result.present is True
    assert result.free_bytes == 60
    assert seen == [str(PureWindowsPath("D:/"))]


def test_drive_collector_maps_missing_or_denied_drive_to_not_present() -> None:
    def missing(_: str) -> DiskUsage:
        raise FileNotFoundError("drive is missing")

    result = DriveSnapshotCollector(disk_usage=missing).collect()

    assert result.present is False
    assert result.free_bytes is None


def test_drive_collector_rejects_invalid_drive_letter() -> None:
    with pytest.raises(ValueError):
        DriveSnapshotCollector("games")
