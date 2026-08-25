from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from application.publish_commands import PublishJobNotFoundError
from application.publish_confirmation import (
    PreparePublishJobUseCase,
    PublishConfirmationStateError,
)
from domain.preflight import CheckStatus, PreflightReport
from domain.publish import PublishJob, PublishJobStatus, PublishTarget

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)


def report(station_id: UUID, status: CheckStatus) -> PreflightReport:
    return PreflightReport(station_id, status, (), NOW)


class Store:
    def __init__(self, job: PublishJob | None, targets: tuple[PublishTarget, ...]) -> None:
        self.job = job
        self.targets = list(targets)

    def factory(self) -> "FakeUow":
        return FakeUow(self)


class FakeJobs:
    def __init__(self, store: Store) -> None:
        self._store = store

    async def get(self, job_id: UUID) -> PublishJob | None:
        if self._store.job is None or self._store.job.id != job_id:
            return None
        return self._store.job

    async def update(self, job: PublishJob) -> None:
        self._store.job = job


class FakeTargets:
    def __init__(self, store: Store) -> None:
        self._store = store

    async def list_for_job(self, job_id: UUID) -> tuple[PublishTarget, ...]:
        return tuple(target for target in self._store.targets if target.job_id == job_id)

    async def update(self, target: PublishTarget) -> None:
        for index, current in enumerate(self._store.targets):
            if current.id == target.id:
                self._store.targets[index] = target
                return
        raise ValueError("publish target not found")


class FakeUow:
    def __init__(self, store: Store) -> None:
        self.publish_jobs = FakeJobs(store)
        self.publish_targets = FakeTargets(store)

    async def __aenter__(self) -> "FakeUow":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        return None

    async def commit(self) -> None:
        return None


class FakePreflightQuery:
    def __init__(self, reports: dict[UUID, PreflightReport]) -> None:
        self.reports = reports
        self.calls: list[UUID] = []

    async def execute(self, *, station_id: UUID) -> PreflightReport:
        self.calls.append(station_id)
        return self.reports[station_id]


def make_job(*, status: PublishJobStatus = PublishJobStatus.DRAFT) -> PublishJob:
    job = PublishJob(
        id=uuid4(),
        idempotency_key="confirmation-key",
        correlation_id=uuid4(),
        label="build",
        source_dataset="game",
    )
    if status is PublishJobStatus.DRAFT:
        return job
    return replace(job, status=status)


def make_store(job_status: PublishJobStatus = PublishJobStatus.DRAFT) -> tuple[Store, UUID, UUID]:
    job = make_job(status=job_status)
    admin_id, client_id = uuid4(), uuid4()
    target = PublishTarget(id=uuid4(), job_id=job.id, station_id=client_id)
    return Store(job, (target,)), admin_id, client_id


async def test_prepare_persists_ready_preflight_and_confirmation() -> None:
    store, admin_id, client_id = make_store()
    query = FakePreflightQuery(
        {
            admin_id: report(admin_id, CheckStatus.PASS),
            client_id: report(client_id, CheckStatus.WARNING),
        }
    )
    result = await PreparePublishJobUseCase(store.factory, query).execute(
        job_id=store.job.id,  # type: ignore[union-attr]
        admin_station_id=admin_id,
        confirmation=True,
    )

    assert result.gate.can_advance is True
    assert result.job.status is PublishJobStatus.AWAITING_CONFIRMATION
    assert result.job.client_confirmation is True
    assert result.job.client_confirmation_at is not None
    assert query.calls == [admin_id, client_id]
    assert store.targets[0].preflight_status == "warning"
    assert store.targets[0].preflight_result == {
        "station_id": str(client_id),
        "status": "warning",
        "evaluated_at": NOW.isoformat(),
        "checks": [],
    }


async def test_blocked_preflight_never_becomes_ready() -> None:
    store, admin_id, client_id = make_store()
    query = FakePreflightQuery(
        {
            admin_id: report(admin_id, CheckStatus.BLOCK),
            client_id: report(client_id, CheckStatus.PASS),
        }
    )

    result = await PreparePublishJobUseCase(store.factory, query).execute(
        job_id=store.job.id,  # type: ignore[union-attr]
        admin_station_id=admin_id,
        confirmation=True,
    )

    assert result.gate.can_advance is False
    assert result.job.status is PublishJobStatus.PREFLIGHT
    assert "admin_preflight_blocked" in (result.job.status_reason or "")


async def test_missing_confirmation_moves_ready_reports_to_waiting_state() -> None:
    store, admin_id, client_id = make_store()
    query = FakePreflightQuery(
        {
            admin_id: report(admin_id, CheckStatus.PASS),
            client_id: report(client_id, CheckStatus.PASS),
        }
    )

    result = await PreparePublishJobUseCase(store.factory, query).execute(
        job_id=store.job.id,  # type: ignore[union-attr]
        admin_station_id=admin_id,
        confirmation=None,
    )

    assert result.gate.can_advance is False
    assert result.job.status is PublishJobStatus.AWAITING_CONFIRMATION
    assert result.job.status_reason == "operator_confirmation_required"
    assert result.job.client_confirmation is None


async def test_prepare_can_skip_admin_station_for_true_nas_workflow() -> None:
    store, _, client_id = make_store()
    query = FakePreflightQuery({client_id: report(client_id, CheckStatus.PASS)})

    result = await PreparePublishJobUseCase(store.factory, query).execute(
        job_id=store.job.id,  # type: ignore[union-attr]
        admin_station_id=None,
        confirmation=True,
    )

    assert result.admin_report is None
    assert result.gate.can_advance is True
    assert query.calls == [client_id]


async def test_prepare_rejects_terminal_job_before_preflight() -> None:
    store, admin_id, _ = make_store(PublishJobStatus.COMPLETED)
    query = FakePreflightQuery({})

    with pytest.raises(PublishConfirmationStateError, match="cannot accept preflight"):
        await PreparePublishJobUseCase(store.factory, query).execute(
            job_id=store.job.id,  # type: ignore[union-attr]
            admin_station_id=admin_id,
            confirmation=True,
        )
    assert query.calls == []


async def test_prepare_rejects_unknown_job() -> None:
    store, admin_id, _ = make_store()
    store.job = None

    with pytest.raises(PublishJobNotFoundError, match="publish job not found"):
        await PreparePublishJobUseCase(store.factory, FakePreflightQuery({})).execute(
            job_id=uuid4(),
            admin_station_id=admin_id,
            confirmation=True,
        )
