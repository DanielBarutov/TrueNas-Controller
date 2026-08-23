import json
from pathlib import Path
from typing import Any

import pytest

from truenas_adapter.read_only import TrueNASAdapterError, TrueNASReadOnlyAdapter
from truenas_adapter.registry import TrueNASMethodRegistry

FIXTURE_PATH = (
    Path(__file__).parents[2] / "truenas_adapter" / "fixtures" / "25.10" / "read_only.json"
)


class FixtureTransport:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, object | None]] = []

    async def request(self, method: str, params: object | None = None) -> object:
        self.calls.append((method, params))
        operation = {
            "core.ping": "ping",
            "pool.dataset.query": "query_datasets",
            "pool.snapshot.query": "query_snapshots",
            "iscsi.target.query": "query_targets",
            "iscsi.extent.query": "query_extents",
            "iscsi.targetextent.query": "query_target_extents",
        }[method]
        return self.responses[operation]

    async def close(self) -> None:
        pass


@pytest.fixture
def fixture_responses() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text())["responses"]


@pytest.mark.asyncio
async def test_read_only_adapter_maps_fixture_without_write_capabilities(
    fixture_responses: dict[str, Any],
) -> None:
    transport = FixtureTransport(fixture_responses)
    adapter = TrueNASReadOnlyAdapter(transport, TrueNASMethodRegistry("25.10"))

    await adapter.ping()
    datasets = await adapter.query_datasets()
    snapshots = await adapter.query_snapshots()
    targets = await adapter.query_targets()
    extents = await adapter.query_extents()
    target_extents = await adapter.query_target_extents()

    assert datasets[1].path == "/dev/zvol/tank/iscsi/game-zvol"
    assert snapshots[0].dataset == "tank/iscsi/game-zvol"
    assert targets[0].id == 7
    assert extents[0].extent_type == "DISK"
    assert target_extents[0].lun_id == 0
    assert [method for method, _ in transport.calls] == [
        "core.ping",
        "pool.dataset.query",
        "pool.snapshot.query",
        "iscsi.target.query",
        "iscsi.extent.query",
        "iscsi.targetextent.query",
    ]


@pytest.mark.asyncio
async def test_read_only_adapter_rejects_malformed_remote_data() -> None:
    transport = FixtureTransport({"query_datasets": {"unexpected": True}})
    adapter = TrueNASReadOnlyAdapter(transport, TrueNASMethodRegistry("25.10"))

    with pytest.raises(TrueNASAdapterError):
        await adapter.query_datasets()


@pytest.mark.asyncio
async def test_read_only_adapter_does_not_turn_false_ping_into_success() -> None:
    transport = FixtureTransport({"ping": False})
    adapter = TrueNASReadOnlyAdapter(transport, TrueNASMethodRegistry("25.10"))

    with pytest.raises(TrueNASAdapterError):
        await adapter.ping()
