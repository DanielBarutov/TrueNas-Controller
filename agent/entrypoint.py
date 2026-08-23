"""Agent process entrypoint and Windows Service composition boundary."""

from agent.config import AgentConfig, AgentConfigError
from agent.credentials import CredentialStore, build_credential_store
from agent.runtime import build_agent_service
from agent.windows_service import PyWin32ServiceRuntime

SERVICE_NAME = "TrueNasControllerAgent"
SERVICE_DISPLAY_NAME = "TrueNAS Controller Agent"


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
    """Delegate install/start/stop command handling to the Windows SCM adapter."""

    build_service_runtime().run()
