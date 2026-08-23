from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from agent.commands import AgentCommandHandler
from agent.protocol import AgentCommandValidator, ServerCommand


class FakeHeartbeat:
    def __init__(self) -> None:
        self.calls = 0

    async def run_once(self, **kwargs) -> None:
        self.calls += 1


@pytest.mark.asyncio
async def test_command_handler_refreshes_only_after_validation() -> None:
    now = datetime(2026, 8, 23, 12, tzinfo=UTC)
    heartbeat = FakeHeartbeat()
    handler = AgentCommandHandler(
        AgentCommandValidator(lambda command: command.signature == "sig"),
        heartbeat.run_once,
    )

    await handler.handle(
        ServerCommand(uuid4(), "refresh_process_snapshot", now + timedelta(minutes=1), "sig"),
        now=now,
    )

    assert heartbeat.calls == 1


@pytest.mark.asyncio
async def test_command_handler_deduplicates_replayed_command_id() -> None:
    now = datetime(2026, 8, 23, 12, tzinfo=UTC)
    heartbeat = FakeHeartbeat()
    command = ServerCommand(uuid4(), "refresh_process_snapshot", now + timedelta(minutes=1), "sig")
    handler = AgentCommandHandler(
        AgentCommandValidator(lambda candidate: candidate.signature == "sig"),
        heartbeat.run_once,
    )

    await handler.handle(command, now=now)
    await handler.handle(command, now=now)

    assert heartbeat.calls == 1
