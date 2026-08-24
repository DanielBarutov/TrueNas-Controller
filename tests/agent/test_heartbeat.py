from datetime import UTC, datetime
from uuid import uuid4

import pytest

from agent.backoff import BackoffPolicy
from agent.heartbeat import HeartbeatAgent
from agent.protocol import (
    AgentIdentity,
    HeartbeatPayloadBuilder,
    HeartbeatTransportError,
    ServerCommand,
)
from domain.snapshot import ProcessSnapshot


class FakeTransport:
    def __init__(self, failures: int, commands: tuple = ()) -> None:
        self.failures = failures
        self.commands = commands
        self.calls: list[tuple[dict[str, object], str]] = []
        self.acknowledged: list[str] = []

    async def send(self, payload, credential: str) -> tuple:
        self.calls.append((dict(payload), credential))
        if self.failures:
            self.failures -= 1
            raise HeartbeatTransportError("temporary failure")
        return self.commands

    async def acknowledge(self, command_id, credential: str) -> None:
        self.acknowledged.append(str(command_id))


@pytest.mark.asyncio
async def test_heartbeat_retries_with_bounded_delays_and_keeps_credential_out_of_payload() -> None:
    station_id = uuid4()
    transport = FakeTransport(failures=2)
    delays: list[float] = []
    agent = HeartbeatAgent(
        lambda: ProcessSnapshot(station_id, datetime(2026, 8, 23, 12, tzinfo=UTC), "0.1.0"),
        HeartbeatPayloadBuilder(AgentIdentity(station_id, "CLIENT-01", "0.1.0")),
        transport,
        "credential-for-test",
        backoff=BackoffPolicy(base_delay_seconds=1, max_delay_seconds=2, jitter_ratio=0),
        sleeper=lambda delay: _record_delay(delays, delay),
    )

    await agent.run_once()

    assert delays == [1, 2]
    assert len(transport.calls) == 3
    assert all(call[1] == "credential-for-test" for call in transport.calls)
    assert all("credential" not in call[0] for call in transport.calls)


@pytest.mark.asyncio
async def test_heartbeat_can_run_without_signed_command_processing() -> None:
    station_id = uuid4()
    transport = FakeTransport(
        failures=0,
        commands=(
            ServerCommand(uuid4(), "refresh_process_snapshot", datetime.now(UTC), "signature"),
        ),
    )
    agent = HeartbeatAgent(
        lambda: ProcessSnapshot(station_id, datetime.now(UTC), "0.1.0"),
        HeartbeatPayloadBuilder(AgentIdentity(station_id, "CLIENT-01", "0.1.0")),
        transport,
        "credential-for-test",
        process_commands=False,
    )

    await agent.run_once(process_commands=False)


async def _record_delay(delays: list[float], delay: float) -> None:
    delays.append(delay)
