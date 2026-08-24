"""Agent process entrypoint and Windows Service composition boundary."""

import asyncio
from collections.abc import Mapping
import os
from pathlib import Path
import sys
import tempfile

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
CHECK_CREDENTIAL_STORE_COMMAND = "check-credential-store"
SCM_COMMANDS = frozenset({"install", "update", "remove", "start", "stop", "restart", "debug"})
_CREDENTIAL_STORE_PROBE = "credential-store-preflight"


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


def check_credential_store_from_environment(env: Mapping[str, str] | None = None) -> None:
    """Check DPAPI and ACL storage locally before consuming an enrollment token."""

    source = os.environ if env is None else env
    config = AgentConfig.from_env(source)
    config.credential_path.parent.mkdir(parents=True, exist_ok=True)
    fd, probe_name = tempfile.mkstemp(
        prefix=f".{config.credential_path.name}.check.",
        dir=config.credential_path.parent,
    )
    os.close(fd)
    probe_path = Path(probe_name)
    probe_path.unlink(missing_ok=True)
    store = None
    try:
        store = build_credential_store(probe_path)
        store.save(_CREDENTIAL_STORE_PROBE)
        if store.load() != _CREDENTIAL_STORE_PROBE:
            raise AgentConfigError("credential store preflight did not round-trip")
    finally:
        if store is not None:
            store.clear()
        else:
            probe_path.unlink(missing_ok=True)


def build_service_runtime(
    config: AgentConfig | None = None,
    *,
    credential_store: CredentialStore | None = None,
    require_credential: bool = True,
) -> PyWin32ServiceRuntime:
    """Build the SCM adapter and defer credential loading for SCM commands."""

    resolved_config = config or AgentConfig.from_env()
    store = credential_store or build_credential_store(resolved_config.credential_path)
    if require_credential:
        credential = store.load()
        if not credential:
            raise AgentConfigError("agent credential is missing; enrollment is required")

        def build_service():
            return build_agent_service(resolved_config, credential)

    else:

        def build_service():
            return _build_enrolled_service(resolved_config, store)

    return PyWin32ServiceRuntime(
        service_name=SERVICE_NAME,
        display_name=SERVICE_DISPLAY_NAME,
        build_service=build_service,
    )


def _build_enrolled_service(config: AgentConfig, store: CredentialStore):
    credential = store.load()
    if not credential:
        raise AgentConfigError("agent credential is missing; enrollment is required")
    return build_agent_service(config, credential)


def main() -> None:
    """Run one-shot enrollment or delegate service commands to the Windows SCM."""

    if len(sys.argv) > 1 and sys.argv[1] == ENROLL_COMMAND:
        asyncio.run(enroll_from_environment())
        return
    command = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if command == CHECK_CREDENTIAL_STORE_COMMAND:
        check_credential_store_from_environment()
        return
    build_service_runtime(require_credential=command not in SCM_COMMANDS).run()


if __name__ == "__main__":
    main()
