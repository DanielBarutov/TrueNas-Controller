"""Agent heartbeat delivery and retry loop."""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime
import random

from agent.backoff import BackoffPolicy
from agent.protocol import (
    AgentCommandReceiver,
    HeartbeatPayloadBuilder,
    HeartbeatTransport,
    HeartbeatTransportError,
)
from domain.snapshot import ProcessSnapshot

SnapshotSource = Callable[[], ProcessSnapshot]
Sleep = Callable[[float], Awaitable[None]]


class HeartbeatAgent:
    """Send snapshots with bounded retries and no arbitrary command execution."""

    def __init__(
        self,
        snapshot_source: SnapshotSource,
        payload_builder: HeartbeatPayloadBuilder,
        transport: HeartbeatTransport,
        credential: str,
        *,
        interval_seconds: float = 10.0,
        backoff: BackoffPolicy | None = None,
        sleeper: Sleep = asyncio.sleep,
        random_value: Callable[[], float] = random.random,
        command_receiver: AgentCommandReceiver | None = None,
        process_commands: bool = True,
    ) -> None:
        if not credential:
            raise ValueError("agent credential cannot be empty")
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self._snapshot_source = snapshot_source
        self._payload_builder = payload_builder
        self._transport = transport
        self._credential = credential
        self._interval_seconds = interval_seconds
        self._backoff = backoff or BackoffPolicy()
        self._sleeper = sleeper
        self._random_value = random_value
        self._command_receiver = command_receiver
        self._process_commands = process_commands

    async def send_once(self, snapshot: ProcessSnapshot, *, process_commands: bool = True) -> None:
        """Build and send one heartbeat without retrying a duplicate payload."""

        payload = self._payload_builder.build(snapshot)
        commands = await self._transport.send(payload, self._credential)
        if not process_commands or not commands:
            return
        if self._command_receiver is None:
            raise HeartbeatTransportError("agent command receiver is not configured")
        for command in commands:
            await self._command_receiver.handle(command, now=datetime.now(UTC))
            await self._transport.acknowledge(command.command_id, self._credential)

    async def send_with_retry(
        self,
        snapshot: ProcessSnapshot,
        *,
        process_commands: bool = True,
    ) -> None:
        """Retry transient transport failures with bounded exponential backoff."""

        for attempt in range(self._backoff.max_attempts):
            try:
                await self.send_once(snapshot, process_commands=process_commands)
                return
            except HeartbeatTransportError:
                if attempt == self._backoff.max_attempts - 1:
                    raise
                await self._sleeper(self._backoff.delay(attempt, self._random_value()))

    async def run_once(self, *, process_commands: bool = True) -> None:
        """Collect and deliver one heartbeat; caller controls the scheduler."""

        await self.send_with_retry(
            self._snapshot_source(),
            process_commands=process_commands,
        )

    def attach_command_receiver(self, receiver: AgentCommandReceiver) -> None:
        """Attach the receiver once during composition, before the loop starts."""

        if self._command_receiver is not None:
            raise RuntimeError("agent command receiver is already attached")
        self._command_receiver = receiver

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        """Run until stopped; failed cycles become the next retry opportunity."""

        while not stop_event.is_set():
            with suppress(HeartbeatTransportError):
                await self.run_once(process_commands=self._process_commands)
            await self._sleeper(self._interval_seconds)
