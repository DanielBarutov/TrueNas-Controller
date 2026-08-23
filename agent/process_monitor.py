"""Safe local process collection for the Windows agent."""

from collections.abc import Callable, Iterable
from typing import Any

import psutil

from domain.snapshot import ProcessInfo

ProcessIterator = Callable[..., Iterable[Any]]


class ProcessSnapshotCollector:
    """Collect normalized process metadata without terminating processes."""

    def __init__(self, process_iter: ProcessIterator = psutil.process_iter) -> None:
        self._process_iter = process_iter

    def collect(self) -> tuple[ProcessInfo, ...]:
        """Return best-effort process data, skipping inaccessible processes."""

        collected: list[ProcessInfo] = []
        try:
            processes = self._process_iter(attrs=["name", "pid", "exe"])
            for process in processes:
                try:
                    info = process.info
                    if not isinstance(info, dict):
                        continue
                    name = _text_or_none(info.get("name"))
                    if name is None:
                        continue
                    collected.append(
                        ProcessInfo(
                            name=name,
                            pid=_pid_or_none(info.get("pid")),
                            path=_text_or_none(info.get("exe")),
                        )
                    )
                except (
                    psutil.AccessDenied,
                    psutil.NoSuchProcess,
                    psutil.ZombieProcess,
                    AttributeError,
                ):
                    continue
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            return ()
        return tuple(sorted(collected, key=lambda item: (item.name.casefold(), item.pid or -1)))


def _text_or_none(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _pid_or_none(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None
