"""Safe local execution of the single supported agent refresh command."""

from datetime import datetime

from agent.heartbeat import HeartbeatAgent
from agent.protocol import AgentCommandValidator, ServerCommand


class AgentCommandHandler:
    """Validate a command, collect a fresh snapshot and send one heartbeat."""

    def __init__(self, validator: AgentCommandValidator, heartbeat: HeartbeatAgent) -> None:
        self._validator = validator
        self._heartbeat = heartbeat

    async def handle(self, command: ServerCommand, *, now: datetime) -> None:
        self._validator.validate(command, now=now)
        await self._heartbeat.run_once()
