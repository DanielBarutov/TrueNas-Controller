"""HTTPS heartbeat transport for the Windows agent."""

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from httpx2 import AsyncClient, HTTPError

from agent.protocol import HeartbeatTransportError


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
        self._client = client_factory(
            timeout=timeout_seconds,
            verify=verify_tls,
            trust_env=False,
        )

    async def send(self, payload: Mapping[str, object], credential: str) -> None:
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

    async def close(self) -> None:
        await self._client.aclose()


def _validate_url(url: str, *, allow_insecure_http: bool) -> None:
    parsed = urlparse(url)
    allowed_schemes = {"https"}
    if allow_insecure_http:
        allowed_schemes.add("http")
    if parsed.scheme not in allowed_schemes or not parsed.netloc:
        raise ValueError("heartbeat URL must be a full HTTPS URL")
