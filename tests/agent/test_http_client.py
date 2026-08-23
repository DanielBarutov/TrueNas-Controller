from collections.abc import Mapping
from uuid import UUID

import pytest

from agent.http_client import HttpHeartbeatTransport
from agent.protocol import HeartbeatTransportError


class FakeResponse:
    def __init__(self, status_code: int, payload: object | None = None) -> None:
        self.status_code = status_code
        self.payload = payload if payload is not None else {"commands": []}

    def json(self) -> object:
        return self.payload


class FakeHttpClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, Mapping[str, object], dict[str, str]]] = []
        self.acknowledgements: list[tuple[str, dict[str, str]]] = []
        self.closed = False

    async def post(
        self,
        url: str,
        *,
        json: Mapping[str, object],
        headers: dict[str, str],
    ) -> FakeResponse:
        self.calls.append((url, json, headers))
        return self.response

    async def aclose(self) -> None:
        self.closed = True


def test_http_transport_requires_https_by_default() -> None:
    with pytest.raises(ValueError):
        HttpHeartbeatTransport("http://controller.example/api/v1/agents/heartbeat")


@pytest.mark.asyncio
async def test_http_transport_sends_bearer_and_closes_client() -> None:
    client = FakeHttpClient(FakeResponse(202))
    transport = HttpHeartbeatTransport(
        "https://controller.example/api/v1/agents/heartbeat",
        client_factory=lambda **_: client,
    )

    assert await transport.send({"station_id": "station-1"}, "credential-for-test") == ()
    await transport.close()

    assert client.calls == [
        (
            "https://controller.example/api/v1/agents/heartbeat",
            {"station_id": "station-1"},
            {"Authorization": "Bearer credential-for-test"},
        )
    ]
    assert client.closed is True


@pytest.mark.asyncio
async def test_http_transport_acknowledges_command_with_bearer() -> None:
    client = FakeHttpClient(FakeResponse(204))
    transport = HttpHeartbeatTransport(
        "https://controller.example/api/v1/agents/heartbeat",
        client_factory=lambda **_: client,
    )

    command_id = UUID("11111111-1111-1111-1111-111111111111")
    await transport.acknowledge(command_id, "credential-for-test")

    assert client.calls[-1] == (
        "https://controller.example/api/v1/agents/commands/11111111-1111-1111-1111-111111111111/ack",
        {},
        {"Authorization": "Bearer credential-for-test"},
    )


@pytest.mark.asyncio
async def test_http_transport_maps_non_success_without_echoing_payload() -> None:
    client = FakeHttpClient(FakeResponse(401))
    transport = HttpHeartbeatTransport(
        "https://controller.example/api/v1/agents/heartbeat",
        client_factory=lambda **_: client,
    )

    with pytest.raises(HeartbeatTransportError) as error:
        await transport.send({"credential": "should-not-be-sent"}, "credential-for-test")

    assert "credential-for-test" not in str(error.value)
    assert "should-not-be-sent" not in str(error.value)


@pytest.mark.asyncio
async def test_http_transport_parses_signed_commands_from_heartbeat_response() -> None:
    command_id = "11111111-1111-1111-1111-111111111111"
    client = FakeHttpClient(
        FakeResponse(
            200,
            {
                "commands": [
                    {
                        "command_id": command_id,
                        "name": "refresh_process_snapshot",
                        "expires_at": "2026-08-23T12:01:00+00:00",
                        "signature": "signature",
                    }
                ]
            },
        )
    )
    transport = HttpHeartbeatTransport(
        "https://controller.example/api/v1/agents/heartbeat",
        client_factory=lambda **_: client,
    )

    commands = await transport.send({}, "credential-for-test")

    assert len(commands) == 1
    assert str(commands[0].command_id) == command_id
    assert commands[0].name == "refresh_process_snapshot"


@pytest.mark.asyncio
async def test_http_transport_rejects_malformed_command_response() -> None:
    client = FakeHttpClient(FakeResponse(200, {"commands": [{"name": "run_shell"}]}))
    transport = HttpHeartbeatTransport(
        "https://controller.example/api/v1/agents/heartbeat",
        client_factory=lambda **_: client,
    )

    with pytest.raises(HeartbeatTransportError, match="command is malformed"):
        await transport.send({}, "credential-for-test")
