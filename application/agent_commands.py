"""Operator command issuance for the safe Windows-agent command allow-list."""

from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from application.lifecycle import hash_secret
from application.ports import UnitOfWorkFactory
from domain.agent_command import AgentCommand, AgentCommandName
from domain.time import ensure_utc

COMMAND_TTL = timedelta(minutes=5)
MAX_COMMAND_TTL = timedelta(minutes=15)


class AgentCommandSigner(Protocol):
    """Signing port owned by the application command use case."""

    def sign(self, command_id: UUID, name: str, expires_at: datetime) -> str:
        """Sign the canonical command envelope without returning private key data."""


class AgentCommandIssueError(ValueError):
    """The requested command cannot be issued to the selected agent."""


class AgentCommandAgentNotFoundError(AgentCommandIssueError):
    """No active enrolled agent matches the requested stable agent UUID."""


class AgentCommandUnauthorizedError(ValueError):
    """The command acknowledgement credential is invalid or revoked."""


class AgentCommandAcknowledgementRejectedError(ValueError):
    """The command is unknown, expired or not currently leased to the agent."""


class IssueAgentCommandUseCase:
    """Persist one short-lived signed command for delivery on the next heartbeat."""

    def __init__(self, uow_factory: UnitOfWorkFactory, signer: AgentCommandSigner) -> None:
        self._uow_factory = uow_factory
        self._signer = signer

    async def execute(
        self,
        *,
        agent_uuid: UUID,
        name: str,
        ttl: timedelta = COMMAND_TTL,
        now: datetime | None = None,
    ) -> AgentCommand:
        if name != AgentCommandName.REFRESH_PROCESS_SNAPSHOT.value:
            raise AgentCommandIssueError("unsupported agent command")
        if ttl <= timedelta(0) or ttl > MAX_COMMAND_TTL:
            raise AgentCommandIssueError("agent command TTL is outside the allowed range")
        issued_at = ensure_utc(now or datetime.now(UTC))
        expires_at = issued_at + ttl
        async with self._uow_factory() as uow:
            agent = await uow.agents.get_by_agent_uuid(agent_uuid)
            if agent is None or not agent.can_accept_heartbeat():
                raise AgentCommandAgentNotFoundError("active agent binding was not found")
            command_id = uuid4()
            command = AgentCommand(
                id=command_id,
                agent_id=agent.id,
                name=AgentCommandName.REFRESH_PROCESS_SNAPSHOT,
                expires_at=expires_at,
                signature=self._signer.sign(
                    command_id,
                    AgentCommandName.REFRESH_PROCESS_SNAPSHOT.value,
                    expires_at,
                ),
            )
            await uow.agent_commands.add(command)
            await uow.commit()
        return command


class AcknowledgeAgentCommandUseCase:
    """Commit an acknowledgement only for the credential-owning agent."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        *,
        credential: str,
        command_id: UUID,
        now: datetime | None = None,
    ) -> None:
        acknowledged_at = ensure_utc(now or datetime.now(UTC))
        async with self._uow_factory() as uow:
            agent = await uow.agents.get_by_credential_hash(_hash_credential(credential))
            if agent is None or not agent.can_accept_heartbeat():
                raise AgentCommandUnauthorizedError("agent credential is invalid")
            acknowledged = await uow.agent_commands.acknowledge(
                agent.id,
                command_id,
                now=acknowledged_at,
            )
            if not acknowledged:
                raise AgentCommandAcknowledgementRejectedError(
                    "agent command acknowledgement was rejected"
                )
            await uow.commit()


def _hash_credential(credential: str) -> str:
    return hash_secret(credential)
