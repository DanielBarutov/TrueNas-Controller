import asyncio
from threading import Event

import pytest

from agent.service import AgentService
from agent.windows_service import PyWin32ServiceRuntime, WindowsServiceError, WindowsServiceHost


class FakeHeartbeat:
    def __init__(self) -> None:
        self.stop_seen = False

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        await stop_event.wait()
        self.stop_seen = stop_event.is_set()


class ImmediateStopHost:
    async def wait_for_stop(self) -> None:
        return


@pytest.mark.asyncio
async def test_service_requests_graceful_heartbeat_shutdown() -> None:
    heartbeat = FakeHeartbeat()

    await AgentService(heartbeat).run(ImmediateStopHost())

    assert heartbeat.stop_seen is True


@pytest.mark.asyncio
async def test_windows_service_host_bridges_thread_stop_to_asyncio() -> None:
    stop_event = Event()
    host = WindowsServiceHost(stop_event)
    waiter = asyncio.create_task(host.wait_for_stop())

    await asyncio.sleep(0)
    assert waiter.done() is False
    host.request_stop()
    await waiter


def test_pywin32_runtime_is_fail_closed_outside_windows() -> None:
    runtime = PyWin32ServiceRuntime(
        service_name="TrueNasControllerAgent",
        display_name="TrueNAS Controller Agent",
        build_service=lambda: AgentService(FakeHeartbeat()),
    )

    with pytest.raises(WindowsServiceError, match="only on Windows"):
        runtime.run()
