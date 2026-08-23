"""Composition root for the platform-neutral Windows-agent runtime."""

from agent.command_signing import Ed25519CommandVerifier
from agent.commands import AgentCommandHandler
from agent.config import AgentConfig, AgentConfigError
from agent.drive_monitor import DriveSnapshotCollector
from agent.heartbeat import HeartbeatAgent
from agent.http_client import HttpHeartbeatTransport
from agent.process_monitor import ProcessSnapshotCollector
from agent.protocol import AgentCommandValidator, AgentIdentity, HeartbeatPayloadBuilder
from agent.service import AgentService
from agent.snapshot import AgentSnapshotCollector, MarkerReader


def build_agent_service(
    config: AgentConfig,
    credential: str,
    *,
    marker_reader: MarkerReader | None = None,
    process_collector: ProcessSnapshotCollector | None = None,
    drive_collector: DriveSnapshotCollector | None = None,
    transport: HttpHeartbeatTransport | None = None,
) -> AgentService:
    """Assemble collectors, signed-command validation, transport and lifecycle."""

    if not config.command_verify_key:
        raise AgentConfigError("AGENT_COMMAND_VERIFY_KEY is required for agent runtime")
    verifier = Ed25519CommandVerifier.from_base64(config.command_verify_key)
    snapshot_collector = AgentSnapshotCollector(
        station_id=config.station_id,
        agent_version=config.agent_version,
        process_collector=process_collector or ProcessSnapshotCollector(),
        drive_collector=drive_collector or DriveSnapshotCollector(config.drive_letter),
        marker_reader=marker_reader,
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
    )
    command_handler = AgentCommandHandler(
        AgentCommandValidator(verifier),
        lambda: heartbeat.run_once(process_commands=False),
    )
    heartbeat.attach_command_receiver(command_handler)
    return AgentService(heartbeat)
