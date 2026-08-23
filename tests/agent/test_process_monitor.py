from typing import Any

import psutil

from agent.process_monitor import ProcessSnapshotCollector


class FakeProcess:
    def __init__(self, info: Any = None, error: BaseException | None = None) -> None:
        self.info = info
        self.error = error

    @property
    def info(self) -> Any:
        if self.error is not None:
            raise self.error
        return self._info

    @info.setter
    def info(self, value: Any) -> None:
        self._info = value


def test_process_collector_normalizes_and_sorts_safe_metadata() -> None:
    def process_iter(*, attrs: list[str]) -> list[FakeProcess]:
        assert attrs == ["name", "pid", "exe"]
        return [
            FakeProcess({"name": " Steam.exe ", "pid": 20, "exe": "C:\\Steam.exe"}),
            FakeProcess({"name": "game.exe", "pid": 10, "exe": None}),
            FakeProcess({"name": None, "pid": 30, "exe": "C:\\unknown.exe"}),
            FakeProcess({"name": "bad-pid.exe", "pid": True, "exe": 42}),
        ]

    result = ProcessSnapshotCollector(process_iter).collect()

    assert [(item.name, item.pid, item.path) for item in result] == [
        ("bad-pid.exe", None, None),
        ("game.exe", 10, None),
        ("Steam.exe", 20, "C:\\Steam.exe"),
    ]


def test_process_collector_skips_access_denied_and_disappeared_processes() -> None:
    def process_iter(**_: object) -> list[FakeProcess]:
        return [
            FakeProcess(error=psutil.AccessDenied(pid=1)),
            FakeProcess(error=psutil.NoSuchProcess(pid=2)),
            FakeProcess({"name": "visible.exe", "pid": 3, "exe": None}),
        ]

    result = ProcessSnapshotCollector(process_iter).collect()

    assert [(item.name, item.pid) for item in result] == [("visible.exe", 3)]
