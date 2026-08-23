"""Platform-neutral service lifecycle boundary for a future Windows wrapper."""

import asyncio
from typing import Protocol

from agent.heartbeat import HeartbeatAgent


class ServiceHost(Protocol):
    """Windows Service/WinSW adapter boundary owned by the platform layer."""

    async def wait_for_stop(self) -> None:
        """Suspend until the service manager requests graceful shutdown."""


class AgentService:
    """Tie heartbeat lifetime to a host stop signal without global state."""

    def __init__(self, heartbeat: HeartbeatAgent) -> None:
        self._heartbeat = heartbeat

    async def run(self, host: ServiceHost) -> None:
        stop_event = asyncio.Event()
        heartbeat_task = asyncio.create_task(self._heartbeat.run_forever(stop_event))
        try:
            await host.wait_for_stop()
        finally:
            stop_event.set()
            await heartbeat_task
