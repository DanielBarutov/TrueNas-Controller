"""Safe local execution of the single supported agent refresh command."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from uuid import UUID

from agent.protocol import AgentCommandValidator, ServerCommand

RefreshSnapshot = Callable[[], Awaitable[None]]


class AgentCommandHandler:
    """Validate a command, collect a fresh snapshot and send one heartbeat."""

    def __init__(self, validator: AgentCommandValidator, refresh_snapshot: RefreshSnapshot) -> None:
        self._validator = validator
        self._refresh_snapshot = refresh_snapshot
        self._handled_commands: set[UUID] = set()

    async def handle(self, command: ServerCommand, *, now: datetime) -> None:
        self._validator.validate(command, now=now)
        if command.command_id in self._handled_commands:
            return
        await self._refresh_snapshot()
        self._handled_commands.add(command.command_id)
