"""Opt-in TrueNAS runtime wiring with a fail-closed write boundary."""

from collections.abc import Mapping
from dataclasses import dataclass
import os
import ssl
from urllib.parse import urlparse

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import WebSocketException

from application.ports import TrueNASJsonRpcTransport
from truenas_adapter.read_only import TrueNASReadOnlyAdapter
from truenas_adapter.registry import TrueNASMethodRegistry
from truenas_adapter.transport import (
    JsonRpcWebSocketTransport,
    WebSocketConnection,
)
from truenas_adapter.write import TrueNASWriteAdapter


class TrueNASRuntimeConfigError(ValueError):
    """Runtime configuration is incomplete or unsafe for API-key transport."""


class TrueNASAuthenticationError(RuntimeError):
    """TrueNAS rejected the API key without exposing the key or raw response."""


@dataclass(frozen=True, slots=True)
class TrueNASRuntimeConfig:
    """Secret-bearing infrastructure settings kept outside application DTOs."""

    websocket_url: str
    api_key: str
    api_version: str = "25.10"
    timeout_seconds: float = 10.0
    reconnect_attempts: int = 1
    open_timeout_seconds: float = 10.0
    apply_enabled: bool = False
    tls_verify: bool = True
    tls_ca_file: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "TrueNASRuntimeConfig":
        """Load an opt-in config; never provide a default endpoint or key."""

        source = os.environ if env is None else env
        websocket_url = source.get("TRUENAS_WS_URL", "").strip()
        api_key = source.get("TRUENAS_API_KEY", "").strip()
        api_version = source.get("TRUENAS_VERSION", "25.10").strip()
        _validate_websocket_url(websocket_url)
        if not api_key:
            raise TrueNASRuntimeConfigError("TRUENAS_API_KEY is required")
        apply_enabled = source.get("TRUENAS_APPLY_ENABLED", "false").strip().lower()
        if apply_enabled not in {"true", "false"}:
            raise TrueNASRuntimeConfigError("TRUENAS_APPLY_ENABLED must be true or false")
        tls_verify_value = source.get("TRUENAS_TLS_VERIFY", "true").strip().lower()
        if tls_verify_value not in {"true", "false"}:
            raise TrueNASRuntimeConfigError("TRUENAS_TLS_VERIFY must be true or false")
        tls_ca_file = source.get("TRUENAS_TLS_CA_FILE", "").strip() or None
        return cls(
            websocket_url=websocket_url,
            api_key=api_key,
            api_version=api_version,
            apply_enabled=apply_enabled == "true",
            tls_verify=tls_verify_value == "true",
            tls_ca_file=tls_ca_file,
        )


class ApiKeyJsonRpcTransport:
    """Authenticate each operation through the verified API-key RPC method.

    Re-authentication per request keeps reconnect semantics safe: if the
    underlying WebSocket is recreated, the next read cannot accidentally run
    on an unauthenticated session. The secret is passed only as JSON-RPC params
    and is never included in an exception or log message.
    """

    def __init__(
        self,
        transport: TrueNASJsonRpcTransport,
        *,
        api_key: str,
        authentication_method: str,
    ) -> None:
        if not api_key:
            raise ValueError("api_key cannot be empty")
        self._transport = transport
        self._api_key = api_key
        self._authentication_method = authentication_method

    async def request(self, method: str, params: object | None = None) -> object:
        if method == self._authentication_method:
            return await self._transport.request(method, params)
        authenticated = await self._transport.request(
            self._authentication_method,
            [self._api_key],
        )
        if authenticated is not True:
            raise TrueNASAuthenticationError("TrueNAS API key authentication failed")
        return await self._transport.request(method, params)

    async def close(self) -> None:
        await self._transport.close()


def build_read_only_client(config: TrueNASRuntimeConfig) -> TrueNASReadOnlyAdapter:
    """Build a real client only when the caller explicitly supplies config."""

    registry = TrueNASMethodRegistry(config.api_version)
    ssl_context = _build_ssl_context(config)

    async def connection_factory() -> WebSocketConnection:
        try:
            connection = await connect(
                config.websocket_url,
                open_timeout=config.open_timeout_seconds,
                proxy=None,
                ssl=ssl_context,
            )
        except ssl.SSLCertVerificationError as exc:
            raise ConnectionError(
                "TrueNAS TLS certificate verification failed; configure "
                "TRUENAS_TLS_CA_FILE or use TRUENAS_TLS_VERIFY=false only for a trusted LAN test"
            ) from exc
        except ssl.SSLError as exc:
            raise ConnectionError(
                "TrueNAS TLS handshake failed; check the HTTPS certificate"
            ) from exc
        except WebSocketException as exc:
            raise ConnectionError(
                "TrueNAS WebSocket handshake failed; check the wss URL, port and /api/current path"
            ) from exc
        except OSError as exc:
            raise ConnectionError(
                "TrueNAS WebSocket endpoint is unreachable; check the host, port and firewall"
            ) from exc
        return _WebsocketsConnection(connection)

    raw_transport = JsonRpcWebSocketTransport(
        connection_factory,
        timeout_seconds=config.timeout_seconds,
        reconnect_attempts=config.reconnect_attempts,
    )
    authenticated_transport = ApiKeyJsonRpcTransport(
        raw_transport,
        api_key=config.api_key,
        authentication_method=registry.resolve("authenticate"),
    )
    return TrueNASReadOnlyAdapter(authenticated_transport, registry)


def build_write_client(config: TrueNASRuntimeConfig) -> TrueNASWriteAdapter:
    """Build the write adapter only after an explicit runtime apply gate."""

    if not config.apply_enabled:
        raise TrueNASRuntimeConfigError(
            "TrueNAS write adapter is disabled; set TRUENAS_APPLY_ENABLED=true explicitly"
        )
    registry = TrueNASMethodRegistry(config.api_version, allow_writes=True)
    raw_transport = _build_transport(config)
    authenticated_transport = ApiKeyJsonRpcTransport(
        raw_transport,
        api_key=config.api_key,
        authentication_method=registry.resolve("authenticate"),
    )
    return TrueNASWriteAdapter(authenticated_transport, registry)


def _build_transport(config: TrueNASRuntimeConfig) -> JsonRpcWebSocketTransport:
    ssl_context = _build_ssl_context(config)

    async def connection_factory() -> WebSocketConnection:
        try:
            connection = await connect(
                config.websocket_url,
                open_timeout=config.open_timeout_seconds,
                proxy=None,
                ssl=ssl_context,
            )
        except ssl.SSLCertVerificationError as exc:
            raise ConnectionError(
                "TrueNAS TLS certificate verification failed; configure "
                "TRUENAS_TLS_CA_FILE or use TRUENAS_TLS_VERIFY=false only for a trusted LAN test"
            ) from exc
        except ssl.SSLError as exc:
            raise ConnectionError(
                "TrueNAS TLS handshake failed; check the HTTPS certificate"
            ) from exc
        except WebSocketException as exc:
            raise ConnectionError(
                "TrueNAS WebSocket handshake failed; check the wss URL, port and /api/current path"
            ) from exc
        except OSError as exc:
            raise ConnectionError(
                "TrueNAS WebSocket endpoint is unreachable; check the host, port and firewall"
            ) from exc
        return _WebsocketsConnection(connection)

    return JsonRpcWebSocketTransport(
        connection_factory,
        timeout_seconds=config.timeout_seconds,
        reconnect_attempts=config.reconnect_attempts,
    )


def _validate_websocket_url(websocket_url: str) -> None:
    parsed = urlparse(websocket_url)
    if parsed.scheme != "wss" or not parsed.netloc:
        raise TrueNASRuntimeConfigError(
            "TRUENAS_WS_URL must be a full wss:// URL; API-key authentication requires TLS"
        )


def _build_ssl_context(config: TrueNASRuntimeConfig) -> ssl.SSLContext:
    """Build an explicit TLS context for the authenticated TrueNAS WebSocket."""

    if config.tls_verify:
        return ssl.create_default_context(cafile=config.tls_ca_file)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


class _WebsocketsConnection:
    """Translate library-specific close errors into the transport contract."""

    def __init__(self, connection: ClientConnection) -> None:
        self._connection = connection

    async def send(self, message: str) -> None:
        try:
            await self._connection.send(message)
        except WebSocketException as exc:
            raise ConnectionError("TrueNAS WebSocket send failed") from exc

    async def recv(self) -> str | bytes:
        try:
            return await self._connection.recv()
        except WebSocketException as exc:
            raise ConnectionError("TrueNAS WebSocket receive failed") from exc

    async def close(self) -> None:
        try:
            await self._connection.close()
        except WebSocketException as exc:
            raise ConnectionError("TrueNAS WebSocket close failed") from exc
