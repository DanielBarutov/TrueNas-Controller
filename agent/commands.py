"""Safe local execution of the single supported agent refresh command."""

from datetime import datetime
from uuid import UUID

from agent.heartbeat import HeartbeatAgent
from agent.protocol import AgentCommandValidator, ServerCommand


class AgentCommandHandler:
    """Validate a command, collect a fresh snapshot and send one heartbeat."""

    def __init__(self, validator: AgentCommandValidator, heartbeat: HeartbeatAgent) -> None:
        self._validator = validator
        self._heartbeat = heartbeat
        self._handled_commands: set[UUID] = set()

    async def handle(self, command: ServerCommand, *, now: datetime) -> None:
        self._validator.validate(command, now=now)
        if command.command_id in self._handled_commands:
            return
        await self._heartbeat.run_once(process_commands=False)
        self._handled_commands.add(command.command_id)
