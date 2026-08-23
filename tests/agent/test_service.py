import asyncio

import pytest

from agent.service import AgentService


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
