from uuid import uuid4

import pytest

from application.publish import (
    FakePublishWorkflow,
    PublishPreconditionError,
    UnknownStorageOutcome,
)
from domain.publish import PublishJob, PublishJobStatus, TargetStatus
from truenas_adapter.mock_client import FakePublishStorageAdapter


def make_job(*, dry_run: bool) -> PublishJob:
    return PublishJob(
        id=uuid4(),
        idempotency_key="job-key",
        correlation_id=uuid4(),
        label="build-001",
        source_dataset="game",
        dry_run=dry_run,
    )


async def test_dry_run_never_changes_fake_mapping() -> None:
    first, second = uuid4(), uuid4()
    adapter = FakePublishStorageAdapter({first: "old:first", second: "old:second"})
    result = await FakePublishWorkflow(adapter).execute(
        make_job(dry_run=True),
        (first, second),
        confirmed=True,
    )

    assert result.job.status is PublishJobStatus.COMPLETED
    assert result.job.status_reason == "dry_run_simulation"
    assert [target.status for target in result.targets] == [
        TargetStatus.SIMULATED,
        TargetStatus.SIMULATED,
    ]
    assert adapter.masters == {}
    assert adapter.clones == {}
    assert adapter.mappings == {first: "old:first", second: "old:second"}


async def test_apply_is_idempotent_per_job_and_station() -> None:
    first, second = uuid4(), uuid4()
    adapter = FakePublishStorageAdapter()
    job = make_job(dry_run=False)
    result = await FakePublishWorkflow(adapter).execute(
        job,
        (first, second),
        confirmed=True,
    )

    assert result.job.status is PublishJobStatus.COMPLETED
    assert all(target.status is TargetStatus.VERIFIED for target in result.targets)
    assert len(adapter.masters) == 1
    assert len(adapter.clones) == 2
    assert adapter.mappings[first].startswith("clone:")
    assert adapter.mappings[second].startswith("clone:")


async def test_partial_failure_keeps_failed_station_old_mapping() -> None:
    first, second = uuid4(), uuid4()
    adapter = FakePublishStorageAdapter({first: "old:first", second: "old:second"})
    adapter.fail_clone_for.add(second)

    result = await FakePublishWorkflow(adapter).execute(
        make_job(dry_run=False),
        (first, second),
        confirmed=True,
    )

    assert result.job.status is PublishJobStatus.PARTIAL_FAILURE
    assert result.targets[0].status is TargetStatus.VERIFIED
    assert result.targets[1].status is TargetStatus.ERROR
    assert adapter.mappings[second] == "old:second"


async def test_unknown_switch_outcome_is_resolved_by_read_back() -> None:
    station_id = uuid4()
    adapter = FakePublishStorageAdapter()
    adapter.unknown_switch_for.add(station_id)

    result = await FakePublishWorkflow(adapter).execute(
        make_job(dry_run=False),
        (station_id,),
        confirmed=True,
    )

    assert result.job.status is PublishJobStatus.COMPLETED
    assert result.targets[0].status is TargetStatus.VERIFIED


async def test_unknown_switch_without_matching_read_back_requires_recovery() -> None:
    station_id = uuid4()

    class UnknownWithoutApplyAdapter(FakePublishStorageAdapter):
        async def switch_mapping(self, station_id, clone_mapping) -> None:
            raise UnknownStorageOutcome("no read-back match")

    result = await FakePublishWorkflow(UnknownWithoutApplyAdapter()).execute(
        make_job(dry_run=False),
        (station_id,),
        confirmed=True,
    )

    assert result.job.status is PublishJobStatus.FAILED
    assert result.targets[0].status is TargetStatus.RECOVERY_REQUIRED


async def test_publish_requires_confirmation_and_targets() -> None:
    workflow = FakePublishWorkflow(FakePublishStorageAdapter())

    with pytest.raises(PublishPreconditionError):
        await workflow.execute(make_job(dry_run=True), (), confirmed=True)
    with pytest.raises(PublishPreconditionError):
        await workflow.execute(make_job(dry_run=True), (uuid4(),), confirmed=False)
