import asyncio
import json

import pytest

from truenas_adapter.transport import (
    JSONRPCConnectionError,
    JSONRPCProtocolError,
    JSONRPCRemoteError,
    JSONRPCTimeoutError,
    JsonRpcWebSocketTransport,
)


class FakeConnection:
    def __init__(self, responses: list[str | bytes | BaseException]) -> None:
        self.responses = list(responses)
        self.sent: list[dict[str, object]] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def recv(self) -> str | bytes:
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_transport_correlates_response_and_ignores_notifications() -> None:
    connection = FakeConnection(
        [
            '{"jsonrpc":"2.0","method":"notify","params":{}}',
            '{"jsonrpc":"2.0","id":999,"result":"wrong"}',
            '{"jsonrpc":"2.0","id":1,"result":{"ok":true}}',
        ]
    )
    transport = JsonRpcWebSocketTransport(lambda: _resolved(connection))

    result = await transport.request("core.ping", {"safe": True})

    assert result == {"ok": True}
    assert connection.sent == [
        {"jsonrpc": "2.0", "id": 1, "method": "core.ping", "params": {"safe": True}}
    ]


@pytest.mark.asyncio
async def test_transport_maps_timeout_and_remote_errors_without_raw_payload() -> None:
    async def never_responds() -> str:
        await asyncio.sleep(1)
        return "{}"

    class SlowConnection(FakeConnection):
        async def recv(self) -> str:
            return await never_responds()

    timeout_transport = JsonRpcWebSocketTransport(
        lambda: _resolved(SlowConnection([])), timeout_seconds=0.001, reconnect_attempts=0
    )
    with pytest.raises(JSONRPCTimeoutError):
        await timeout_transport.request("core.ping")

    error_connection = FakeConnection(
        ['{"jsonrpc":"2.0","id":1,"error":{"code":-1,"message":"secret detail"}}']
    )
    error_transport = JsonRpcWebSocketTransport(lambda: _resolved(error_connection))
    with pytest.raises(JSONRPCRemoteError) as error:
        await error_transport.request("core.ping")
    assert "secret detail" not in str(error.value)


@pytest.mark.asyncio
async def test_transport_reconnects_once_after_connection_loss() -> None:
    first = FakeConnection([ConnectionError("lost")])
    second = FakeConnection(['{"jsonrpc":"2.0","id":1,"result":true}'])
    connections = iter((first, second))

    async def factory() -> FakeConnection:
        return next(connections)

    transport = JsonRpcWebSocketTransport(factory)

    assert await transport.request("core.ping") is True
    assert first.closed is True
    assert second.sent[0]["id"] == 1


@pytest.mark.asyncio
async def test_transport_rejects_malformed_jsonrpc_response() -> None:
    connection = FakeConnection(["not-json"])
    transport = JsonRpcWebSocketTransport(lambda: _resolved(connection), reconnect_attempts=0)

    with pytest.raises(JSONRPCProtocolError):
        await transport.request("core.ping")


@pytest.mark.asyncio
async def test_transport_reports_connection_failure_after_retry_budget() -> None:
    connection = FakeConnection([ConnectionError("lost")])
    transport = JsonRpcWebSocketTransport(lambda: _resolved(connection), reconnect_attempts=0)

    with pytest.raises(JSONRPCConnectionError):
        await transport.request("core.ping")


async def _resolved(connection: FakeConnection) -> FakeConnection:
    return connection
