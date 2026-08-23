from uuid import uuid4

import pytest

from agent.credentials import MemoryCredentialStore
from agent.enrollment import (
    EnrollmentCoordinator,
    EnrollmentRequest,
    EnrollmentResponse,
)


class FakeEnrollmentGateway:
    def __init__(self) -> None:
        self.calls: list[EnrollmentRequest] = []

    async def enroll(self, request: EnrollmentRequest) -> EnrollmentResponse:
        self.calls.append(request)
        return EnrollmentResponse(request.agent_uuid, "credential-for-test")


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
