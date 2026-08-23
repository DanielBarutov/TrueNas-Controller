from datetime import UTC, datetime
from uuid import uuid4

import pytest

from application.lifecycle import ReceiveHeartbeatUseCase
from domain.snapshot import ProcessSnapshot


class UnusedFactory:
    def __call__(self):
        raise AssertionError("invalid metadata should fail before opening a UoW")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"hostname": ""},
        {"ip_addresses": ("not-an-ip",)},
        {"mac_addresses": ("not-a-mac",)},
    ],
)
async def test_heartbeat_rejects_invalid_identity_metadata(kwargs: dict[str, object]) -> None:
    use_case = ReceiveHeartbeatUseCase(UnusedFactory())

    with pytest.raises(ValueError):
        await use_case.execute(
            credential="credential-for-test",
            snapshot=ProcessSnapshot(uuid4(), datetime.now(UTC), "0.1.0"),
            **kwargs,
        )
