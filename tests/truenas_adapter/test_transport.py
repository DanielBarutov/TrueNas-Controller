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
async def test_transport_retries_timeout_with_same_request_id_and_reconnects() -> None:
    first = FakeConnection([TimeoutError()])
    second = FakeConnection(['{"jsonrpc":"2.0","id":1,"result":true}'])
    connections = iter((first, second))

    async def factory() -> FakeConnection:
        return next(connections)

    transport = JsonRpcWebSocketTransport(
        factory,
        timeout_seconds=1,
        retry_attempts=1,
        retry_backoff_seconds=0,
    )

    assert await transport.request("pool.snapshot.create", ["games/master"]) is True
    assert first.closed is True
    assert first.sent[0]["id"] == second.sent[0]["id"] == 1
    assert first.sent[0]["method"] == second.sent[0]["method"] == "pool.snapshot.create"
    assert first.sent[0]["params"] == second.sent[0]["params"] == ["games/master"]


@pytest.mark.asyncio
async def test_transport_retries_timeout_while_opening_connection() -> None:
    connection = FakeConnection(['{"jsonrpc":"2.0","id":1,"result":true}'])
    outcomes: list[BaseException | FakeConnection] = [TimeoutError(), connection]

    async def factory() -> FakeConnection:
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    transport = JsonRpcWebSocketTransport(
        factory,
        retry_attempts=1,
        retry_backoff_seconds=0,
    )

    assert await transport.request("core.ping") is True
    assert connection.sent[0]["id"] == 1


@pytest.mark.asyncio
async def test_transport_reconnects_once_after_connection_loss() -> None:
    first = FakeConnection([ConnectionError("lost")])
    second = FakeConnection(['{"jsonrpc":"2.0","id":1,"result":true}'])
    connections = iter((first, second))

    async def factory() -> FakeConnection:
        return next(connections)

    transport = JsonRpcWebSocketTransport(factory, retry_backoff_seconds=0)

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
    transport = JsonRpcWebSocketTransport(
        lambda: _resolved(connection), reconnect_attempts=0, retry_backoff_seconds=0
    )

    with pytest.raises(JSONRPCConnectionError):
        await transport.request("core.ping")


@pytest.mark.asyncio
async def test_transport_does_not_retry_permanent_remote_error() -> None:
    connection = FakeConnection(
        ['{"jsonrpc":"2.0","id":1,"error":{"code":-32602,"message":"invalid"}}']
    )
    transport = JsonRpcWebSocketTransport(
        lambda: _resolved(connection), retry_attempts=3, retry_backoff_seconds=0
    )

    with pytest.raises(JSONRPCRemoteError):
        await transport.request("pool.snapshot.create")

    assert len(connection.sent) == 1


async def _resolved(connection: FakeConnection) -> FakeConnection:
    return connection
