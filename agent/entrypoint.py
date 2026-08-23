"""Agent process entrypoint and Windows Service composition boundary."""

import asyncio
from collections.abc import Mapping
import os
import sys

from agent.config import AgentConfig, AgentConfigError
from agent.credentials import CredentialStore, build_credential_store
from agent.enrollment import (
    EnrollmentCoordinator,
    EnrollmentGateway,
    EnrollmentRequest,
    HttpEnrollmentGateway,
)
from agent.runtime import build_agent_service
from agent.windows_service import PyWin32ServiceRuntime

SERVICE_NAME = "TrueNasControllerAgent"
SERVICE_DISPLAY_NAME = "TrueNAS Controller Agent"
ENROLL_COMMAND = "enroll"


async def enroll_agent(
    config: AgentConfig,
    enrollment_token: str,
    *,
    credential_store: CredentialStore,
    gateway: EnrollmentGateway,
) -> None:
    """Exchange a one-shot token and persist only the protected credential."""

    if config.agent_uuid is None:
        raise AgentConfigError("AGENT_UUID is required for enrollment")
    if not enrollment_token:
        raise AgentConfigError("AGENT_ENROLLMENT_TOKEN is required for enrollment")
    await EnrollmentCoordinator(credential_store, gateway).ensure_credential(
        EnrollmentRequest(
            enrollment_token=enrollment_token,
            agent_uuid=config.agent_uuid,
            hostname=config.hostname,
            agent_version=config.agent_version,
        )
    )


async def enroll_from_environment(
    env: Mapping[str, str] | None = None,
    *,
    credential_store: CredentialStore | None = None,
    gateway: EnrollmentGateway | None = None,
) -> None:
    """Run the explicit one-shot enrollment command from environment settings."""

    source = os.environ if env is None else env
    config = AgentConfig.from_env(source)
    enrollment_token = source.get("AGENT_ENROLLMENT_TOKEN", "").strip()
    if config.agent_uuid is None:
        raise AgentConfigError("AGENT_UUID is required for enrollment")
    if not enrollment_token:
        raise AgentConfigError("AGENT_ENROLLMENT_TOKEN is required for enrollment")

    store = credential_store or build_credential_store(config.credential_path)
    created_gateway: HttpEnrollmentGateway | None = None
    if gateway is None:
        created_gateway = HttpEnrollmentGateway(
            config.enrollment_url,
            allow_insecure_http=config.allow_insecure_http,
        )
        resolved_gateway: EnrollmentGateway = created_gateway
    else:
        resolved_gateway = gateway
    try:
        await enroll_agent(
            config,
            enrollment_token,
            credential_store=store,
            gateway=resolved_gateway,
        )
    finally:
        if created_gateway is not None:
            await created_gateway.close()


def build_service_runtime(
    config: AgentConfig | None = None,
    *,
    credential_store: CredentialStore | None = None,
) -> PyWin32ServiceRuntime:
    """Build the SCM adapter after loading an enrolled protected credential."""

    resolved_config = config or AgentConfig.from_env()
    store = credential_store or build_credential_store(resolved_config.credential_path)
    credential = store.load()
    if not credential:
        raise AgentConfigError("agent credential is missing; enrollment is required")
    return PyWin32ServiceRuntime(
        service_name=SERVICE_NAME,
        display_name=SERVICE_DISPLAY_NAME,
        build_service=lambda: build_agent_service(resolved_config, credential),
    )


def main() -> None:
    """Run one-shot enrollment or delegate service commands to the Windows SCM."""

    if len(sys.argv) > 1 and sys.argv[1] == ENROLL_COMMAND:
        asyncio.run(enroll_from_environment())
        return
    build_service_runtime().run()


if __name__ == "__main__":
    main()
