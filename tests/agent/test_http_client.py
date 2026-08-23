from collections.abc import Mapping

import pytest

from agent.http_client import HttpHeartbeatTransport
from agent.protocol import HeartbeatTransportError


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class FakeHttpClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, Mapping[str, object], dict[str, str]]] = []
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

    await transport.send({"station_id": "station-1"}, "credential-for-test")
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
