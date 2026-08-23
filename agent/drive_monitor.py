"""Safe local drive availability collection for the Windows agent."""

from collections.abc import Callable
import re
import shutil
from typing import NamedTuple

from domain.snapshot import DriveInfo


class DiskUsage(NamedTuple):
    """Small platform-neutral subset returned by ``shutil.disk_usage``."""

    total: int
    used: int
    free: int


DiskUsageReader = Callable[[str], DiskUsage]


class DriveSnapshotCollector:
    """Read drive metadata without opening or scanning user files."""

    def __init__(
        self,
        drive_letter: str = "D:",
        disk_usage: DiskUsageReader = shutil.disk_usage,
    ) -> None:
        self.drive_letter = _normalize_drive_letter(drive_letter)
        self._disk_usage = disk_usage

    def collect(self) -> DriveInfo:
        """Return missing/unknown metadata when Windows denies the drive."""

        try:
            usage = self._disk_usage(_drive_root(self.drive_letter))
        except (FileNotFoundError, OSError, PermissionError):
            return DriveInfo(letter=self.drive_letter, present=False, free_bytes=None)
        free_bytes = usage.free if isinstance(usage.free, int) and usage.free >= 0 else None
        return DriveInfo(letter=self.drive_letter, present=True, free_bytes=free_bytes)


def _normalize_drive_letter(value: str) -> str:
    normalized = value.strip().upper()
    if re.fullmatch(r"[A-Z]:", normalized) is None:
        raise ValueError("drive letter must have the form C:")
    return normalized


def _drive_root(drive_letter: str) -> str:
    return f"{drive_letter}\\"
