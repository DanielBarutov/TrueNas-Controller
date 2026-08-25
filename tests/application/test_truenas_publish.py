from uuid import uuid4

import pytest

from application.truenas import (
    TrueNASDataset,
    TrueNASExtent,
    TrueNASTarget,
    TrueNASTargetExtent,
)
from application.truenas_publish import TrueNASPublishError, TrueNASPublishWorkflow
from domain.publish import PublishJob, PublishJobStatus, TargetStatus
from domain.station import Station, StationRole, StationStatus
from truenas_adapter.write_fake import FakeTrueNASWriteClient


def make_station(*, target_name: str | None = "PC1") -> Station:
    return Station(
        id=uuid4(),
        station_id=uuid4(),
        display_name="PC1",
        hostname="pc1",
        role=StationRole.CLIENT,
        status=StationStatus.ONLINE,
        target_name=target_name,
    )


def make_job(*, dry_run: bool) -> PublishJob:
    return PublishJob(
        id=uuid4(),
        idempotency_key="truenas-job",
        correlation_id=uuid4(),
        label="build-001",
        source_dataset="games/master-games",
        dry_run=dry_run,
        status=PublishJobStatus.PUBLISHING,
        client_confirmation=True,
    )


def make_storage() -> FakeTrueNASWriteClient:
    storage = FakeTrueNASWriteClient()
    storage.datasets["games/master-games"] = TrueNASDataset(
        "games/master-games",
        "games/master-games",
        "/mnt/games/master-games",
        "FILESYSTEM",
    )
    storage.targets[7] = TrueNASTarget(7, "PC1", None)
    storage.extents[11] = TrueNASExtent(
        11,
        "PC1",
        "/dev/zvol/games/master-games-v001-clone-pc1",
        "DISK",
    )
    storage.target_extents.append(TrueNASTargetExtent(7, 11, 0))
    return storage


@pytest.mark.asyncio
async def test_workflow_updates_existing_extent_and_keeps_lun_association() -> None:
    station = make_station()
    storage = make_storage()

    result = await TrueNASPublishWorkflow(storage, storage).execute(
        make_job(dry_run=False),
        (station,),
        confirmed=True,
    )

    assert result.job.status is PublishJobStatus.COMPLETED
    assert result.targets[0].status is TargetStatus.VERIFIED
    assert len(storage.extents) == 1
    assert storage.extents[11].path == result.targets[0].new_mapping
    assert storage.target_extents == [TrueNASTargetExtent(7, 11, 0)]
    write_calls = [
        name
        for name, _ in storage.calls
        if name in {"create_snapshot", "clone_snapshot", "update_extent_device"}
    ]
    assert write_calls == [
        "create_snapshot",
        "clone_snapshot",
        "update_extent_device",
    ]


@pytest.mark.asyncio
async def test_dry_run_does_not_write_true_nas() -> None:
    storage = make_storage()
    result = await TrueNASPublishWorkflow(storage, storage).execute(
        make_job(dry_run=True),
        (make_station(),),
        confirmed=True,
    )

    assert result.job.status is PublishJobStatus.COMPLETED
    assert result.targets[0].status is TargetStatus.SIMULATED
    assert not any(
        name in {"create_snapshot", "clone_snapshot", "update_extent_device"}
        for name, _ in storage.calls
    )
    assert len(storage.extents) == 1


@pytest.mark.asyncio
async def test_workflow_requires_station_target_mapping() -> None:
    storage = make_storage()

    with pytest.raises(TrueNASPublishError, match="target_name"):
        await TrueNASPublishWorkflow(storage, storage).execute(
            make_job(dry_run=True),
            (make_station(target_name=None),),
            confirmed=True,
        )
