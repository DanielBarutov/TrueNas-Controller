from uuid import uuid4

import pytest

from agent.config import AgentConfig, AgentConfigError
from agent.credentials import MemoryCredentialStore
from agent.enrollment import (
    EnrollmentCoordinator,
    EnrollmentError,
    EnrollmentRequest,
    EnrollmentResponse,
    HttpEnrollmentGateway,
)
from agent.entrypoint import enroll_agent, enroll_from_environment


class FakeEnrollmentGateway:
    def __init__(self) -> None:
        self.calls: list[EnrollmentRequest] = []

    async def enroll(self, request: EnrollmentRequest) -> EnrollmentResponse:
        self.calls.append(request)
        return EnrollmentResponse(request.agent_uuid, "credential-for-test")


class FakeHttpResponse:
    status_code = 409


class FakeHttpClient:
    async def post(self, *_args, **_kwargs) -> FakeHttpResponse:
        return FakeHttpResponse()

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_enrollment_coordinator_is_one_shot_when_credential_exists() -> None:
    store = MemoryCredentialStore()
    gateway = FakeEnrollmentGateway()
    coordinator = EnrollmentCoordinator(store, gateway)
    request = EnrollmentRequest("one-shot-token", uuid4(), "CLIENT-01", "0.1.0")

    first = await coordinator.ensure_credential(request)
    second = await coordinator.ensure_credential(request)

    assert first == second == "credential-for-test"
    assert len(gateway.calls) == 1


@pytest.mark.asyncio
async def test_enrollment_coordinator_rejects_empty_gateway_credential() -> None:
    class EmptyGateway:
        async def enroll(self, request: EnrollmentRequest) -> EnrollmentResponse:
            return EnrollmentResponse(request.agent_uuid, "")

    with pytest.raises(RuntimeError):
        await EnrollmentCoordinator(MemoryCredentialStore(), EmptyGateway()).ensure_credential(
            EnrollmentRequest("token", uuid4(), "CLIENT-01", "0.1.0")
        )


@pytest.mark.asyncio
async def test_http_enrollment_explains_consumed_or_expired_token() -> None:
    gateway = HttpEnrollmentGateway(
        "https://controller.example/api/v1/agents/enroll",
        client_factory=lambda **_: FakeHttpClient(),
    )

    with pytest.raises(EnrollmentError, match="invalid, expired, or already used"):
        await gateway.enroll(EnrollmentRequest("token", uuid4(), "CLIENT-01", "0.1.0"))

    await gateway.close()


@pytest.mark.asyncio
async def test_enroll_agent_persists_credential_without_logging_or_returning_it() -> None:
    station_id = uuid4()
    agent_uuid = uuid4()
    config = AgentConfig(
        api_base_url="https://controller.example",
        station_id=station_id,
        agent_version="0.1.0",
        hostname="CLIENT-01",
        credential_path="credential",
        agent_uuid=agent_uuid,
    )
    store = MemoryCredentialStore()
    gateway = FakeEnrollmentGateway()

    result = await enroll_agent(
        config,
        "one-shot-token",
        credential_store=store,
        gateway=gateway,
    )

    assert result is None
    assert store.load() == "credential-for-test"
    assert gateway.calls[0].agent_uuid == agent_uuid


@pytest.mark.asyncio
async def test_enroll_from_environment_uses_injected_boundaries() -> None:
    agent_uuid = uuid4()
    store = MemoryCredentialStore()
    gateway = FakeEnrollmentGateway()

    await enroll_from_environment(
        {
            "AGENT_API_BASE_URL": "https://controller.example",
            "AGENT_STATION_ID": str(uuid4()),
            "AGENT_VERSION": "0.1.0",
            "AGENT_HOSTNAME": "CLIENT-01",
            "AGENT_CREDENTIAL_PATH": "credential",
            "AGENT_UUID": str(agent_uuid),
            "AGENT_ENROLLMENT_TOKEN": "one-shot-token",
        },
        credential_store=store,
        gateway=gateway,
    )

    assert store.load() == "credential-for-test"
    assert gateway.calls[0].agent_uuid == agent_uuid


@pytest.mark.asyncio
async def test_enroll_from_environment_requires_agent_uuid_and_token() -> None:
    base_env = {
        "AGENT_API_BASE_URL": "https://controller.example",
        "AGENT_STATION_ID": str(uuid4()),
        "AGENT_VERSION": "0.1.0",
        "AGENT_HOSTNAME": "CLIENT-01",
        "AGENT_CREDENTIAL_PATH": "credential",
    }

    with pytest.raises(AgentConfigError, match="AGENT_UUID"):
        await enroll_from_environment(
            {**base_env, "AGENT_ENROLLMENT_TOKEN": "token"},
            credential_store=MemoryCredentialStore(),
            gateway=FakeEnrollmentGateway(),
        )
    with pytest.raises(AgentConfigError, match="AGENT_ENROLLMENT_TOKEN"):
        await enroll_from_environment(
            {**base_env, "AGENT_UUID": str(uuid4())},
            credential_store=MemoryCredentialStore(),
            gateway=FakeEnrollmentGateway(),
        )
