"""Composition root for the platform-neutral Windows-agent runtime."""

from agent.command_signing import Ed25519CommandVerifier
from agent.commands import AgentCommandHandler
from agent.config import AgentConfig
from agent.drive_monitor import DriveSnapshotCollector
from agent.heartbeat import HeartbeatAgent
from agent.http_client import HttpHeartbeatTransport
from agent.process_monitor import ProcessSnapshotCollector
from agent.protocol import AgentCommandValidator, AgentIdentity, HeartbeatPayloadBuilder
from agent.service import AgentService
from agent.snapshot import AgentSnapshotCollector


def build_agent_service(
    config: AgentConfig,
    credential: str,
    *,
    process_collector: ProcessSnapshotCollector | None = None,
    drive_collector: DriveSnapshotCollector | None = None,
    transport: HttpHeartbeatTransport | None = None,
) -> AgentService:
    """Assemble collectors, signed-command validation, transport and lifecycle."""

    verifier = None
    if config.command_verify_key:
        verifier = Ed25519CommandVerifier.from_base64(config.command_verify_key)
    snapshot_collector = AgentSnapshotCollector(
        station_id=config.station_id,
        agent_version=config.agent_version,
        process_collector=process_collector or ProcessSnapshotCollector(),
        drive_collector=drive_collector or DriveSnapshotCollector(config.drive_letter),
    )
    heartbeat = HeartbeatAgent(
        snapshot_source=snapshot_collector.collect,
        payload_builder=HeartbeatPayloadBuilder(
            AgentIdentity(
                station_id=config.station_id,
                hostname=config.hostname,
                agent_version=config.agent_version,
            )
        ),
        transport=transport
        or HttpHeartbeatTransport(
            config.heartbeat_url,
            allow_insecure_http=config.allow_insecure_http,
        ),
        credential=credential,
        interval_seconds=config.heartbeat_interval_seconds,
        process_commands=verifier is not None,
    )
    if verifier is not None:
        command_handler = AgentCommandHandler(
            AgentCommandValidator(verifier),
            lambda: heartbeat.run_once(process_commands=False),
        )
        heartbeat.attach_command_receiver(command_handler)
    return AgentService(heartbeat)
