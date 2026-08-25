import pytest

from truenas_adapter.registry import TrueNASMethodRegistry
from truenas_adapter.write import TrueNASWriteAdapter


class RecordingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object | None]] = []

    async def request(self, method: str, params: object | None = None) -> object:
        self.calls.append((method, params))
        if method == "pool.snapshot.create":
            return {
                "id": "games/master-games@build-001",
                "name": "games/master-games@build-001",
                "dataset": "games/master-games",
            }
        if method == "pool.snapshot.clone":
            return True
        if method == "iscsi.extent.update":
            return {
                "id": 12,
                "name": "PC1",
                "type": "DISK",
                "disk": "/dev/zvol/games/master-games-v002-clone-pc1",
            }
        raise AssertionError(f"unexpected method: {method}")

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_write_adapter_uses_existing_extent_and_preserves_association() -> None:
    transport = RecordingTransport()
    adapter = TrueNASWriteAdapter(transport, TrueNASMethodRegistry("25.10", allow_writes=True))

    snapshot = await adapter.create_snapshot("games/master-games", "build-001")
    await adapter.clone_snapshot(snapshot.name, "games/master-games-v002-clone-pc1")
    extent = await adapter.update_extent_device(
        12,
        "/dev/zvol/games/master-games-v002-clone-pc1",
    )

    assert snapshot.dataset == "games/master-games"
    assert extent.id == 12
    assert extent.path == "/dev/zvol/games/master-games-v002-clone-pc1"
    assert [method for method, _ in transport.calls] == [
        "pool.snapshot.create",
        "pool.snapshot.clone",
        "iscsi.extent.update",
    ]
    assert transport.calls[2][1] == [
        12,
        {"disk": "/dev/zvol/games/master-games-v002-clone-pc1"},
    ]


@pytest.mark.parametrize(
    ("operation", "arguments"),
    [
        ("snapshot", ("games/../master-games", "build-001")),
        ("snapshot", ("games/master-games", "build/001")),
        ("clone", ("games/master-games@build-001", "games/../clone")),
        ("extent", (12, "/dev/zvol/games/../clone")),
    ],
)
@pytest.mark.asyncio
async def test_write_adapter_rejects_unsafe_paths(
    operation: str,
    arguments: tuple[object, ...],
) -> None:
    adapter = TrueNASWriteAdapter(
        RecordingTransport(),
        TrueNASMethodRegistry("25.10", allow_writes=True),
    )

    with pytest.raises(ValueError):
        if operation == "snapshot":
            await adapter.create_snapshot(*arguments)  # type: ignore[arg-type]
        elif operation == "clone":
            await adapter.clone_snapshot(*arguments)  # type: ignore[arg-type]
        else:
            await adapter.update_extent_device(*arguments)  # type: ignore[arg-type]
