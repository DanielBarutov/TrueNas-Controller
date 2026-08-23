from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from agent.protocol import (
    AgentCommandValidator,
    AgentIdentity,
    HeartbeatPayloadBuilder,
    InvalidAgentCommand,
    ServerCommand,
)
from domain.snapshot import DriveInfo, ProcessInfo, ProcessSnapshot


def test_heartbeat_payload_is_versioned_and_contains_no_credential() -> None:
    station_id = uuid4()
    snapshot = ProcessSnapshot(
        station_id=station_id,
        captured_at=datetime(2026, 8, 23, 12, tzinfo=UTC),
        agent_version="0.1.0",
        processes=(ProcessInfo("game.exe", 42, "D:\\game.exe"),),
        drives=(DriveInfo("D:", True, 100),),
        game_version_marker="build-001",
    )
    payload = HeartbeatPayloadBuilder(
        AgentIdentity(station_id, "CLIENT-01", "0.1.0", ("192.0.2.10",), ("00:11:22:33:44:55",))
    ).build(snapshot)

    assert payload["protocol_version"] == "1"
    assert payload["station_id"] == str(station_id)
    assert payload["processes"] == [{"name": "game.exe", "pid": 42, "path": "D:\\game.exe"}]
    assert "credential" not in payload


def test_payload_builder_rejects_snapshot_for_another_station() -> None:
    snapshot = ProcessSnapshot(uuid4(), datetime.now(UTC), "0.1.0")
    builder = HeartbeatPayloadBuilder(AgentIdentity(uuid4(), "CLIENT-01", "0.1.0"))

    with pytest.raises(ValueError):
        builder.build(snapshot)


def test_command_validator_accepts_only_signed_unexpired_refresh() -> None:
    now = datetime(2026, 8, 23, 12, tzinfo=UTC)
    command = ServerCommand(uuid4(), "refresh_process_snapshot", now + timedelta(minutes=1), "sig")

    validated = AgentCommandValidator(lambda candidate: candidate.signature == "sig").validate(
        command, now=now
    )

    assert validated == command


@pytest.mark.parametrize(
    "command",
    [
        ServerCommand(uuid4(), "run_shell", datetime(2026, 8, 23, 13, tzinfo=UTC), "sig"),
        ServerCommand(
            uuid4(), "refresh_process_snapshot", datetime(2026, 8, 23, 11, tzinfo=UTC), "sig"
        ),
        ServerCommand(
            uuid4(), "refresh_process_snapshot", datetime(2026, 8, 23, 13, tzinfo=UTC), "bad"
        ),
    ],
)
def test_command_validator_rejects_unsafe_expired_or_invalid_command(
    command: ServerCommand,
) -> None:
    with pytest.raises(InvalidAgentCommand):
        AgentCommandValidator(lambda _: False).validate(
            command,
            now=datetime(2026, 8, 23, 12, tzinfo=UTC),
        )
