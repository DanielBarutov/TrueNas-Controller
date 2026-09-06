"""Dependency-free JSON-RPC 2.0 transport boundary for TrueNAS WebSocket calls."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
import json
import math
from typing import Protocol


class WebSocketConnection(Protocol):
    """Small connection contract so tests never need a real WebSocket."""

    async def send(self, message: str) -> None:
        """Send one serialized JSON-RPC message."""

    async def recv(self) -> str | bytes:
        """Receive one serialized JSON-RPC message or notification."""

    async def close(self) -> None:
        """Close the current connection."""


ConnectionFactory = Callable[[], Awaitable[WebSocketConnection]]


class JSONRPCError(RuntimeError):
    """Base class for safe transport failures."""


class JSONRPCConnectionError(JSONRPCError):
    """The connection could not be opened or was lost after retries."""


class JSONRPCTimeoutError(JSONRPCError):
    """A correlated response did not arrive before the configured timeout."""


class JSONRPCProtocolError(JSONRPCError):
    """The peer returned malformed or non-JSON-RPC data."""


class JSONRPCRemoteError(JSONRPCError):
    """The peer returned an error response without leaking its raw payload."""

    def __init__(self, method: str, code: int | None) -> None:
        self.method = method
        self.code = code
        code_text = "unknown" if code is None else str(code)
        super().__init__(f"TrueNAS JSON-RPC method failed: {method} (code={code_text})")


class JsonRpcWebSocketTransport:
    """Correlate JSON-RPC responses over an injected WebSocket connection.

    The class deliberately has no WebSocket library dependency and never logs
    request parameters. A production composition root can inject its chosen
    client, while contract tests use a deterministic fake connection.
    """

    _MAX_RETRY_ATTEMPTS = 10

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        *,
        timeout_seconds: float = 10.0,
        reconnect_attempts: int | None = None,
        retry_attempts: int | None = None,
        retry_backoff_seconds: float = 0.25,
        retry_backoff_max_seconds: float = 2.0,
    ) -> None:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if reconnect_attempts is not None and retry_attempts is not None:
            raise ValueError("configure only one of reconnect_attempts or retry_attempts")
        configured_attempts = (
            retry_attempts
            if retry_attempts is not None
            else reconnect_attempts
            if reconnect_attempts is not None
            else 2
        )
        if (
            not isinstance(configured_attempts, int)
            or isinstance(configured_attempts, bool)
            or not 0 <= configured_attempts <= self._MAX_RETRY_ATTEMPTS
        ):
            raise ValueError("retry_attempts must be an integer from 0 to 10")
        if not math.isfinite(retry_backoff_seconds) or retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds cannot be negative")
        if not math.isfinite(retry_backoff_max_seconds) or retry_backoff_max_seconds < 0:
            raise ValueError("retry_backoff_max_seconds cannot be negative")
        if retry_backoff_max_seconds < retry_backoff_seconds:
            raise ValueError("retry_backoff_max_seconds cannot be less than retry_backoff_seconds")
        self._connection_factory = connection_factory
        self._timeout_seconds = timeout_seconds
        self._retry_attempts = configured_attempts
        self._retry_backoff_seconds = retry_backoff_seconds
        self._retry_backoff_max_seconds = retry_backoff_max_seconds
        self._connection: WebSocketConnection | None = None
        self._next_request_id = 1
        self._closed = False

    async def request(self, method: str, params: object | None = None) -> object:
        """Send a request and return only its correlated result value."""

        if self._closed:
            raise JSONRPCConnectionError("JSON-RPC transport is closed")
        request_id = self._allocate_request_id()
        try:
            payload = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params if params is not None else [],
                },
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as exc:
            raise JSONRPCProtocolError("JSON-RPC parameters are not serializable") from exc

        for attempt in range(self._retry_attempts + 1):
            try:
                return await asyncio.wait_for(
                    self._request_once(payload, request_id, method), self._timeout_seconds
                )
            except (
                TimeoutError,
                ConnectionError,
                OSError,
                EOFError,
                JSONRPCConnectionError,
            ) as exc:
                await self._reset_connection()
                if attempt >= self._retry_attempts:
                    if isinstance(exc, TimeoutError):
                        raise JSONRPCTimeoutError(
                            f"TrueNAS JSON-RPC request timed out: {method}"
                        ) from exc
                    raise JSONRPCConnectionError(
                        f"TrueNAS JSON-RPC connection failed: {method}"
                    ) from exc
                await self._wait_before_retry(attempt)

        raise AssertionError("request retry loop must return or raise")

    async def close(self) -> None:
        """Close the injected connection and reject future requests."""

        self._closed = True
        await self._reset_connection()

    async def _request_once(self, payload: str, request_id: int, method: str) -> object:
        connection = await self._get_connection()
        await connection.send(payload)
        while True:
            raw_message = await connection.recv()
            message = self._decode_message(raw_message)
            if message.get("id") != request_id:
                continue
            if message.get("jsonrpc") != "2.0":
                raise JSONRPCProtocolError("TrueNAS returned a non-JSON-RPC response")
            if "error" in message:
                error = message["error"]
                if not isinstance(error, Mapping):
                    raise JSONRPCProtocolError("TrueNAS returned an invalid JSON-RPC error")
                code = error.get("code")
                if not isinstance(code, int) or isinstance(code, bool):
                    code = None
                raise JSONRPCRemoteError(method, code)
            if "result" not in message:
                raise JSONRPCProtocolError("TrueNAS response has neither result nor error")
            return message["result"]

    async def _get_connection(self) -> WebSocketConnection:
        if self._connection is None:
            try:
                self._connection = await self._connection_factory()
            except (ConnectionError, OSError) as exc:
                raise JSONRPCConnectionError("TrueNAS WebSocket connection failed") from exc
        return self._connection

    async def _reset_connection(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is not None:
            with suppress(TimeoutError, ConnectionError, OSError, EOFError):
                await connection.close()

    async def _wait_before_retry(self, attempt: int) -> None:
        if self._retry_backoff_seconds == 0:
            return
        delay = min(
            self._retry_backoff_seconds * (2**attempt),
            self._retry_backoff_max_seconds,
        )
        await asyncio.sleep(delay)

    def _allocate_request_id(self) -> int:
        request_id = self._next_request_id
        self._next_request_id += 1
        return request_id

    @staticmethod
    def _decode_message(raw_message: str | bytes) -> Mapping[str, object]:
        if isinstance(raw_message, bytes):
            try:
                raw_message = raw_message.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise JSONRPCProtocolError("TrueNAS returned invalid UTF-8") from exc
        if not isinstance(raw_message, str):
            raise JSONRPCProtocolError("TrueNAS returned a non-text JSON-RPC message")
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError as exc:
            raise JSONRPCProtocolError("TrueNAS returned malformed JSON") from exc
        if not isinstance(message, Mapping):
            raise JSONRPCProtocolError("TrueNAS returned a non-object JSON-RPC message")
        return message
