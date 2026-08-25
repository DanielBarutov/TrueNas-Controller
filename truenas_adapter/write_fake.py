"""Deterministic write fake; it never contacts a TrueNAS instance."""

from application.truenas import (
    TrueNASDataset,
    TrueNASExtent,
    TrueNASSnapshot,
    TrueNASTarget,
    TrueNASTargetExtent,
)


class FakeTrueNASWriteClient:
    """Record approved calls and model existing extent device replacement."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.datasets: dict[str, TrueNASDataset] = {}
        self.snapshots: dict[str, TrueNASSnapshot] = {}
        self.clones: set[tuple[str, str]] = set()
        self.targets: dict[int, TrueNASTarget] = {}
        self.target_extents: list[TrueNASTargetExtent] = []
        self.extents: dict[int, TrueNASExtent] = {}
        self.extent_devices: dict[int, str] = {}

    async def query_datasets(self) -> tuple[TrueNASDataset, ...]:
        self.calls.append(("query_datasets", ()))
        return tuple(self.datasets.values())

    async def query_snapshots(self) -> tuple[TrueNASSnapshot, ...]:
        self.calls.append(("query_snapshots", ()))
        return tuple(self.snapshots.values())

    async def query_targets(self) -> tuple[TrueNASTarget, ...]:
        self.calls.append(("query_targets", ()))
        return tuple(self.targets.values())

    async def query_extents(self) -> tuple[TrueNASExtent, ...]:
        self.calls.append(("query_extents", ()))
        return tuple(self.extents.values())

    async def query_target_extents(self) -> tuple[TrueNASTargetExtent, ...]:
        self.calls.append(("query_target_extents", ()))
        return tuple(self.target_extents)

    async def create_snapshot(self, dataset: str, snapshot_name: str) -> TrueNASSnapshot:
        self.calls.append(("create_snapshot", (dataset, snapshot_name)))
        full_name = f"{dataset}@{snapshot_name}"
        snapshot = self.snapshots.setdefault(
            full_name,
            TrueNASSnapshot(id=full_name, name=full_name, dataset=dataset),
        )
        self.datasets.setdefault(
            dataset,
            TrueNASDataset(dataset, dataset, f"/mnt/{dataset}", "FILESYSTEM"),
        )
        return snapshot

    async def clone_snapshot(self, snapshot: str, dataset_dst: str) -> None:
        self.calls.append(("clone_snapshot", (snapshot, dataset_dst)))
        self.clones.add((snapshot, dataset_dst))
        self.datasets.setdefault(
            dataset_dst,
            TrueNASDataset(
                dataset_dst,
                dataset_dst,
                f"/dev/zvol/{dataset_dst}",
                "VOLUME",
            ),
        )

    async def update_extent_device(self, extent_id: int, device: str) -> TrueNASExtent:
        self.calls.append(("update_extent_device", (extent_id, device)))
        self.extent_devices[extent_id] = device
        current = self.extents.get(extent_id)
        updated = TrueNASExtent(
            extent_id,
            current.name if current is not None else f"extent-{extent_id}",
            device.removeprefix("/dev/"),
            current.extent_type if current is not None else "DISK",
        )
        self.extents[extent_id] = updated
        return updated

    async def close(self) -> None:
        return None
