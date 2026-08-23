"""Fail-closed runtime configuration for the Windows agent."""

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID


class AgentConfigError(ValueError):
    """Agent configuration is missing or unsafe."""


@dataclass(frozen=True, slots=True)
class AgentConfig:
    """Non-secret settings; the credential is loaded separately from a store."""

    api_base_url: str
    station_id: UUID
    agent_version: str
    hostname: str
    credential_path: Path
    heartbeat_interval_seconds: float = 10.0
    drive_letter: str = "D:"
    allow_insecure_http: bool = False

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "AgentConfig":
        source = os.environ if env is None else env
        api_base_url = source.get("AGENT_API_BASE_URL", "").strip().rstrip("/")
        station_id_text = source.get("AGENT_STATION_ID", "").strip()
        agent_version = source.get("AGENT_VERSION", "").strip()
        hostname = source.get("AGENT_HOSTNAME", "").strip()
        credential_path_text = source.get("AGENT_CREDENTIAL_PATH", "").strip()
        allow_insecure = source.get("AGENT_ALLOW_INSECURE_HTTP") == "1"
        if not api_base_url or not station_id_text or not agent_version or not hostname:
            raise AgentConfigError("agent URL, station ID, version and hostname are required")
        if not credential_path_text:
            raise AgentConfigError("AGENT_CREDENTIAL_PATH is required")
        try:
            station_id = UUID(station_id_text)
        except ValueError as exc:
            raise AgentConfigError("AGENT_STATION_ID must be a UUID") from exc
        _validate_api_url(api_base_url, allow_insecure_http=allow_insecure)
        return cls(
            api_base_url=api_base_url,
            station_id=station_id,
            agent_version=agent_version,
            hostname=hostname,
            credential_path=Path(credential_path_text),
            allow_insecure_http=allow_insecure,
        )

    @property
    def heartbeat_url(self) -> str:
        """Return the own-controller heartbeat route, never a TrueNAS URL."""

        return f"{self.api_base_url}/api/v1/agents/heartbeat"

    @property
    def enrollment_url(self) -> str:
        """Return the own-controller enrollment route."""

        return f"{self.api_base_url}/api/v1/agents/enroll"


def _validate_api_url(url: str, *, allow_insecure_http: bool) -> None:
    parsed = urlparse(url)
    allowed_schemes = {"https"}
    if allow_insecure_http:
        allowed_schemes.add("http")
    if parsed.scheme not in allowed_schemes or not parsed.netloc:
        raise AgentConfigError("AGENT_API_BASE_URL must be a full HTTPS URL")
