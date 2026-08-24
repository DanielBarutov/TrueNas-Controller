import base64
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from agent.config import AgentConfig, AgentConfigError
from agent.credentials import MemoryCredentialStore
from agent.entrypoint import build_service_runtime
from agent.runtime import build_agent_service
from agent.service import AgentService
from agent.windows_service import PyWin32ServiceRuntime


class FakeTransport:
    async def send(self, payload, credential: str) -> tuple:
        return ()

    async def acknowledge(self, command_id, credential: str) -> None:
        return None


def make_config(*, command_verify_key: str | None) -> AgentConfig:
    return AgentConfig(
        api_base_url="https://controller.example",
        station_id=uuid4(),
        agent_version="0.1.0",
        hostname="CLIENT-01",
        credential_path=Path("credential"),
        command_verify_key=command_verify_key,
    )


def test_agent_runtime_works_without_public_command_key() -> None:
    service = build_agent_service(
        make_config(command_verify_key=None),
        "credential-for-test",
        transport=FakeTransport(),
    )

    assert isinstance(service, AgentService)


def test_agent_runtime_wires_verifier_and_local_components() -> None:
    public_key = Ed25519PrivateKey.generate().public_key().public_bytes_raw()
    encoded_key = base64.urlsafe_b64encode(public_key).rstrip(b"=").decode("ascii")

    service = build_agent_service(
        make_config(command_verify_key=encoded_key),
        "credential-for-test",
        transport=FakeTransport(),
    )

    assert isinstance(service, AgentService)


def test_service_entrypoint_requires_enrollment_credential() -> None:
    config = make_config(command_verify_key="public-key-for-test")

    with pytest.raises(AgentConfigError, match="credential is missing"):
        build_service_runtime(config, credential_store=MemoryCredentialStore())


def test_service_entrypoint_builds_scm_runtime_after_enrollment() -> None:
    public_key = Ed25519PrivateKey.generate().public_key().public_bytes_raw()
    encoded_key = base64.urlsafe_b64encode(public_key).rstrip(b"=").decode("ascii")
    store = MemoryCredentialStore()
    store.save("credential-for-test")

    runtime = build_service_runtime(
        make_config(command_verify_key=encoded_key),
        credential_store=store,
    )

    assert isinstance(runtime, PyWin32ServiceRuntime)


def test_service_entrypoint_defers_credential_load_for_scm_registration() -> None:
    config = make_config(command_verify_key="public-key-for-test")

    runtime = build_service_runtime(
        config,
        credential_store=MemoryCredentialStore(),
        require_credential=False,
    )

    assert isinstance(runtime, PyWin32ServiceRuntime)
