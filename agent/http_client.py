"""HTTPS heartbeat transport for the Windows agent."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from httpx2 import AsyncClient, HTTPError

from agent.protocol import HeartbeatTransportError, ServerCommand


class HttpHeartbeatTransport:
    """Post agent payloads over HTTPS with an isolated client and Bearer auth."""

    def __init__(
        self,
        heartbeat_url: str,
        *,
        timeout_seconds: float = 10.0,
        verify_tls: bool = True,
        allow_insecure_http: bool = False,
        client_factory: Any = AsyncClient,
    ) -> None:
        _validate_url(heartbeat_url, allow_insecure_http=allow_insecure_http)
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._heartbeat_url = heartbeat_url
        self._command_ack_base_url = heartbeat_url.rsplit("/", 1)[0] + "/commands"
        self._client = client_factory(
            timeout=timeout_seconds,
            verify=verify_tls,
            trust_env=False,
        )

    async def send(
        self,
        payload: Mapping[str, object],
        credential: str,
    ) -> tuple[ServerCommand, ...]:
        if not credential:
            raise HeartbeatTransportError("agent credential is missing")
        try:
            response = await self._client.post(
                self._heartbeat_url,
                json=dict(payload),
                headers={"Authorization": f"Bearer {credential}"},
            )
        except HTTPError as exc:
            raise HeartbeatTransportError("heartbeat request failed") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise HeartbeatTransportError(
                f"heartbeat endpoint rejected request with status {response.status_code}"
            )
        try:
            response_data = response.json()
        except (AttributeError, TypeError, ValueError) as exc:
            raise HeartbeatTransportError("heartbeat response is malformed") from exc
        return _parse_commands(response_data)

    async def acknowledge(self, command_id: UUID, credential: str) -> None:
        if not credential:
            raise HeartbeatTransportError("agent credential is missing")
        try:
            response = await self._client.post(
                f"{self._command_ack_base_url}/{command_id}/ack",
                json={},
                headers={"Authorization": f"Bearer {credential}"},
            )
        except HTTPError as exc:
            raise HeartbeatTransportError("agent command acknowledgement failed") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise HeartbeatTransportError(
                f"agent command acknowledgement rejected with status {response.status_code}"
            )

    async def close(self) -> None:
        await self._client.aclose()


def _validate_url(url: str, *, allow_insecure_http: bool) -> None:
    parsed = urlparse(url)
    allowed_schemes = {"https"}
    if allow_insecure_http:
        allowed_schemes.add("http")
    if parsed.scheme not in allowed_schemes or not parsed.netloc:
        raise ValueError(
            "heartbeat URL must be a full HTTPS URL, or HTTP with allow_insecure_http=True"
        )


def _parse_commands(response_data: object) -> tuple[ServerCommand, ...]:
    if not isinstance(response_data, Mapping):
        raise HeartbeatTransportError("heartbeat response is malformed")
    raw_commands = response_data.get("commands", [])
    if not isinstance(raw_commands, list) or len(raw_commands) > 16:
        raise HeartbeatTransportError("heartbeat response commands are malformed")
    commands: list[ServerCommand] = []
    for raw_command in raw_commands:
        if not isinstance(raw_command, Mapping):
            raise HeartbeatTransportError("heartbeat response commands are malformed")
        try:
            command_id = UUID(raw_command["command_id"])
            name = raw_command["name"]
            expires_at = datetime.fromisoformat(raw_command["expires_at"])
            signature = raw_command["signature"]
        except (KeyError, TypeError, ValueError) as exc:
            raise HeartbeatTransportError("heartbeat response command is malformed") from exc
        if not isinstance(name, str) or not isinstance(signature, str):
            raise HeartbeatTransportError("heartbeat response command is malformed")
        commands.append(ServerCommand(command_id, name, expires_at, signature))
    return tuple(commands)
