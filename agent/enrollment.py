"""One-shot enrollment coordination for the Windows agent."""

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from httpx2 import AsyncClient, HTTPError

from agent.credentials import CredentialStore
from agent.http_client import _validate_url


@dataclass(frozen=True, slots=True)
class EnrollmentRequest:
    """Non-secret enrollment data sent to the controller."""

    enrollment_token: str
    agent_uuid: UUID
    hostname: str
    agent_version: str
    ip_addresses: tuple[str, ...] = ()
    mac_addresses: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EnrollmentResponse:
    """Credential returned exactly once by the controller."""

    station_id: UUID
    credential: str


class EnrollmentGateway(Protocol):
    """Network boundary for the one-shot enrollment request."""

    async def enroll(self, request: EnrollmentRequest) -> EnrollmentResponse:
        """Exchange a one-shot token for an agent credential."""


class EnrollmentError(RuntimeError):
    """Enrollment failed without exposing token, credential or raw response."""


class EnrollmentCoordinator:
    """Load existing credential first and never enroll twice locally."""

    def __init__(self, store: CredentialStore, gateway: EnrollmentGateway) -> None:
        self._store = store
        self._gateway = gateway

    async def ensure_credential(self, request: EnrollmentRequest) -> str:
        existing = self._store.load()
        if existing:
            return existing
        response = await self._gateway.enroll(request)
        if not response.credential:
            raise EnrollmentError("controller returned an empty agent credential")
        self._store.save(response.credential)
        return response.credential


class HttpEnrollmentGateway:
    """HTTP(S) enrollment boundary; HTTPS is the default and secrets are never logged."""

    def __init__(
        self,
        enrollment_url: str,
        *,
        timeout_seconds: float = 10.0,
        allow_insecure_http: bool = False,
        client_factory: Any = AsyncClient,
    ) -> None:
        _validate_url(enrollment_url, allow_insecure_http=allow_insecure_http)
        self._enrollment_url = enrollment_url
        self._client = client_factory(
            timeout=timeout_seconds,
            verify=True,
            trust_env=False,
        )

    async def enroll(self, request: EnrollmentRequest) -> EnrollmentResponse:
        try:
            response = await self._client.post(
                self._enrollment_url,
                json={
                    "enrollment_token": request.enrollment_token,
                    "agent_uuid": str(request.agent_uuid),
                    "hostname": request.hostname,
                    "agent_version": request.agent_version,
                    "ip_addresses": list(request.ip_addresses),
                    "mac_addresses": list(request.mac_addresses),
                },
            )
        except HTTPError as exc:
            raise EnrollmentError(
                "agent enrollment request failed; check Controller URL, port, "
                "HTTP/HTTPS and firewall"
            ) from exc
        if response.status_code == 409:
            raise EnrollmentError(
                "agent enrollment rejected with HTTP 409: enrollment token is "
                "invalid, expired, or already used; create a new station and token"
            )
        if response.status_code < 200 or response.status_code >= 300:
            raise EnrollmentError(f"agent enrollment rejected with status {response.status_code}")
        try:
            data = response.json()
            station_id = UUID(data["station_id"])
            credential = data["credential"]
        except (KeyError, TypeError, ValueError) as exc:
            raise EnrollmentError("agent enrollment response is malformed") from exc
        if not isinstance(credential, str) or not credential:
            raise EnrollmentError("agent enrollment response has no credential")
        return EnrollmentResponse(station_id=station_id, credential=credential)

    async def close(self) -> None:
        await self._client.aclose()
