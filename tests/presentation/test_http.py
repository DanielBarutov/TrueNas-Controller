from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from application.lifecycle import EnrollmentResult, HeartbeatResult, StationRegistration
from application.publish_commands import (
    PublishDraftValidationError,
    PublishIdempotencyConflictError,
    PublishJobDraft,
    PublishJobNotFoundError,
)
from application.publish_confirmation import PublishPreflightResult
from application.publish_dispatch import PublishDispatchResult
from application.publish_queries import PublishJobView
from domain.agent_command import AgentCommand, AgentCommandName
from domain.preflight import CheckResult, CheckStatus, PreflightReport
from domain.publish import PublishJob, PublishJobStatus, PublishTarget
from domain.station import Station, StationRole, StationStatus
from domain.wizard import WizardGateResult, WizardGateStatus
from presentation.http import create_app

TEST_PASSWORD = "unit-test-password"


class FakeStationQuery:
    def __init__(self, stations: list[Station]) -> None:
        self._stations = stations
        self.requested_include_disabled: bool | None = None

    async def execute(self, *, include_disabled: bool = False) -> list[Station]:
        self.requested_include_disabled = include_disabled
        return self._stations


class FakeStationRegistry:
    def __init__(self, station: Station) -> None:
        self.station = station

    async def execute(self, **kwargs) -> StationRegistration:
        return StationRegistration(
            station=self.station,
            enrollment_token="token-for-test",
            enrollment_expires_at=datetime.now(UTC),
        )


class FakeEnrollment:
    async def execute(self, **kwargs) -> EnrollmentResult:
        return EnrollmentResult(
            station_id=kwargs["agent_uuid"],
            credential="credential-for-test",
            server_time=datetime.now(UTC),
        )


class FakeHeartbeat:
    def __init__(self) -> None:
        self.credential: str | None = None

    async def execute(self, *, credential: str, snapshot, **kwargs) -> HeartbeatResult:
        self.credential = credential
        return HeartbeatResult(station_id=snapshot.station_id, received_at=datetime.now(UTC))


class FakeIssueAgentCommand:
    def __init__(self, command: AgentCommand) -> None:
        self.command = command
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs) -> AgentCommand:
        self.calls.append(kwargs)
        return self.command


class FakeAcknowledgeAgentCommand:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs) -> None:
        self.calls.append(kwargs)


class FakePreflight:
    async def execute(self, **kwargs) -> PreflightReport:
        station_id = kwargs["station_id"]
        now = datetime.now(UTC)
        return PreflightReport(
            station_id=station_id,
            status=CheckStatus.BLOCK,
            checks=(
                CheckResult(
                    status=CheckStatus.BLOCK,
                    code="blocking_process",
                    message="game is running",
                    observed_at=now,
                ),
            ),
            evaluated_at=now,
        )


class FakePublishDraft:
    def __init__(self, result: PublishJobDraft | Exception) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs) -> PublishJobDraft:
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakePublishJobQuery:
    def __init__(self, result: PublishJobView | Exception) -> None:
        self.result = result

    async def execute(self, job_id):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakePublishPrepare:
    def __init__(self, result: PublishPreflightResult | Exception) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs) -> PublishPreflightResult:
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakePublishDispatch:
    def __init__(self, result: PublishDispatchResult | Exception) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs) -> PublishDispatchResult:
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def make_client(stations: list[Station]) -> tuple[TestClient, FakeStationQuery]:
    query = FakeStationQuery(stations)
    return TestClient(create_app(query)), query


def test_health_requires_valid_basic_auth(monkeypatch) -> None:
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", TEST_PASSWORD)
    client, _ = make_client([])

    assert client.get("/health").status_code == 401
    assert client.get("/health", auth=("wrong", TEST_PASSWORD)).status_code == 401
    response = client.get("/health", auth=("admin", TEST_PASSWORD))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_missing_basic_auth_password_fails_closed(monkeypatch) -> None:
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    client, _ = make_client([])

    response = client.get("/health", auth=("admin", TEST_PASSWORD))

    assert response.status_code == 401


def test_stations_route_uses_application_query(monkeypatch) -> None:
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", TEST_PASSWORD)
    station = Station(
        id=uuid4(),
        station_id=uuid4(),
        display_name="Client 01",
        hostname="client-01",
        role=StationRole.CLIENT,
        status=StationStatus.ONLINE,
    )
    client, query = make_client([station])

    response = client.get(
        "/api/v1/stations?include_disabled=true",
        auth=("admin", TEST_PASSWORD),
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(station.id),
            "station_id": str(station.station_id),
            "display_name": "Client 01",
            "hostname": "client-01",
            "role": "client",
            "status": "online",
            "enabled": True,
            "deleted_at": None,
        }
    ]
    assert query.requested_include_disabled is True


def test_agent_lifecycle_routes_use_their_auth_boundaries(monkeypatch) -> None:
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", TEST_PASSWORD)
    station = Station(
        id=uuid4(),
        station_id=uuid4(),
        display_name="Client 01",
        hostname="client-01",
        role=StationRole.CLIENT,
        status=StationStatus.OFFLINE,
    )
    heartbeat = FakeHeartbeat()
    client = TestClient(
        create_app(
            FakeStationQuery([station]),
            station_registry=FakeStationRegistry(station),
            enroll_agent=FakeEnrollment(),
            receive_heartbeat=heartbeat,
        )
    )

    station_response = client.post(
        "/api/v1/stations",
        json={"display_name": "Client 01", "hostname": "client-01", "role": "client"},
        auth=("admin", TEST_PASSWORD),
    )
    enroll_response = client.post(
        "/api/v1/agents/enroll",
        json={
            "enrollment_token": "token-for-test",
            "agent_uuid": str(uuid4()),
            "hostname": "client-01",
            "agent_version": "1.0.0",
        },
    )
    heartbeat_response = client.post(
        "/api/v1/agents/heartbeat",
        json={
            "station_id": str(station.station_id),
            "captured_at": datetime.now(UTC).isoformat(),
            "agent_version": "1.0.0",
            "processes": [],
            "drives": [],
        },
        headers={"Authorization": "Bearer credential-for-test"},
    )

    assert station_response.status_code == 201
    assert enroll_response.status_code == 200
    assert client.post("/api/v1/agents/heartbeat", json={}).status_code == 401
    assert heartbeat_response.status_code == 200
    assert heartbeat.credential == "credential-for-test"


def test_agent_command_routes_require_their_auth_boundaries(monkeypatch) -> None:
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", TEST_PASSWORD)
    agent_uuid = uuid4()
    command_id = uuid4()
    command = AgentCommand(
        id=command_id,
        agent_id=uuid4(),
        name=AgentCommandName.REFRESH_PROCESS_SNAPSHOT,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        signature="signed-command",
    )
    issue = FakeIssueAgentCommand(command)
    acknowledge = FakeAcknowledgeAgentCommand()
    client = TestClient(
        create_app(
            FakeStationQuery([]),
            issue_agent_command=issue,
            acknowledge_agent_command=acknowledge,
        )
    )

    assert (
        client.post(
            f"/api/v1/agents/{agent_uuid}/commands",
            json={"name": "refresh_process_snapshot"},
        ).status_code
        == 401
    )
    issue_response = client.post(
        f"/api/v1/agents/{agent_uuid}/commands",
        json={"name": "refresh_process_snapshot", "ttl_seconds": 60},
        auth=("admin", TEST_PASSWORD),
    )
    ack_response = client.post(
        f"/api/v1/agents/commands/{command_id}/ack",
        headers={"Authorization": "Bearer credential-for-test"},
    )

    assert issue_response.status_code == 201
    assert issue_response.json()["command_id"] == str(command_id)
    assert issue.calls[0]["agent_uuid"] == agent_uuid
    assert ack_response.status_code == 204
    assert acknowledge.calls[0]["credential"] == "credential-for-test"


def test_preflight_route_requires_operator_auth_and_returns_report(monkeypatch) -> None:
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", TEST_PASSWORD)
    station_id = uuid4()
    client = TestClient(create_app(FakeStationQuery([]), evaluate_preflight=FakePreflight()))

    unauthorized = client.post("/api/v1/preflight", json={"station_id": str(station_id)})
    authorized = client.post(
        "/api/v1/preflight",
        json={"station_id": str(station_id), "min_free_bytes": 50},
        auth=("admin", TEST_PASSWORD),
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json()["status"] == "block"
    assert authorized.json()["can_publish"] is False


def test_publish_draft_route_requires_auth_and_returns_safe_summary(monkeypatch) -> None:
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", TEST_PASSWORD)
    station_id = uuid4()
    job = PublishJob(
        id=uuid4(),
        idempotency_key="draft-key",
        correlation_id=uuid4(),
        label="build-001",
        game_name="game",
    )
    draft = PublishJobDraft(
        job=job,
        targets=(PublishTarget(id=uuid4(), job_id=job.id, station_id=station_id),),
    )
    use_case = FakePublishDraft(draft)
    client = TestClient(create_app(FakeStationQuery([]), create_publish_job=use_case))
    payload = {
        "label": "build-001",
        "game_name": "game",
        "station_ids": [str(station_id)],
        "idempotency_key": "draft-key",
        "correlation_id": str(job.correlation_id),
    }

    assert client.post("/api/v1/publish/jobs", json=payload).status_code == 401
    response = client.post(
        "/api/v1/publish/jobs",
        json=payload,
        auth=("admin", TEST_PASSWORD),
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": str(job.id),
        "idempotency_key": "draft-key",
        "correlation_id": str(job.correlation_id),
        "label": "build-001",
        "game_name": "game",
        "status": "draft",
        "dry_run": True,
        "allow_hot_switch": False,
        "station_ids": [str(station_id)],
    }
    assert "mapping" not in response.text
    assert len(use_case.calls) == 1


def test_publish_draft_route_maps_application_errors(monkeypatch) -> None:
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", TEST_PASSWORD)
    payload = {
        "label": "build-001",
        "game_name": "game",
        "station_ids": [str(uuid4())],
        "idempotency_key": "draft-key",
    }
    validation_client = TestClient(
        create_app(
            FakeStationQuery([]),
            create_publish_job=FakePublishDraft(PublishDraftValidationError("bad station")),
        )
    )
    conflict_client = TestClient(
        create_app(
            FakeStationQuery([]),
            create_publish_job=FakePublishDraft(PublishIdempotencyConflictError("already used")),
        )
    )

    assert (
        validation_client.post(
            "/api/v1/publish/jobs", json=payload, auth=("admin", TEST_PASSWORD)
        ).status_code
        == 422
    )
    assert (
        conflict_client.post(
            "/api/v1/publish/jobs", json=payload, auth=("admin", TEST_PASSWORD)
        ).status_code
        == 409
    )


def test_publish_job_route_returns_safe_target_status(monkeypatch) -> None:
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", TEST_PASSWORD)
    station_id = uuid4()
    job = PublishJob(
        id=uuid4(),
        idempotency_key="query-key",
        correlation_id=uuid4(),
        label="build",
        game_name="game",
        description="nightly",
    )
    target = PublishTarget(
        id=uuid4(),
        job_id=job.id,
        station_id=station_id,
        preflight_status="passed",
        switch_status="pending",
        verify_status="pending",
        error_code=None,
        progress_percent=25,
        old_mapping={"secret": "must-not-leak"},
    )
    client = TestClient(
        create_app(
            FakeStationQuery([]),
            get_publish_job=FakePublishJobQuery(PublishJobView(job, (target,))),
        )
    )

    response = client.get(
        f"/api/v1/publish/jobs/{job.id}",
        auth=("admin", TEST_PASSWORD),
    )

    assert response.status_code == 200
    assert response.json()["targets"] == [
        {
            "station_id": str(station_id),
            "selected": True,
            "preflight_status": "passed",
            "switch_status": "pending",
            "verify_status": "pending",
            "error_code": None,
            "error_message": None,
            "progress_percent": 25,
        }
    ]
    assert "must-not-leak" not in response.text
    assert client.get(f"/api/v1/publish/jobs/{job.id}").status_code == 401


def test_publish_job_route_maps_missing_job_to_404(monkeypatch) -> None:
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", TEST_PASSWORD)
    client = TestClient(
        create_app(
            FakeStationQuery([]),
            get_publish_job=FakePublishJobQuery(PublishJobNotFoundError("not found")),
        )
    )

    response = client.get(
        f"/api/v1/publish/jobs/{uuid4()}",
        auth=("admin", TEST_PASSWORD),
    )

    assert response.status_code == 404


def test_publish_prepare_route_returns_server_gate_and_reports(monkeypatch) -> None:
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", TEST_PASSWORD)
    admin_station_id = uuid4()
    client_station_id = uuid4()
    now = datetime.now(UTC)
    report = PreflightReport(
        station_id=client_station_id,
        status=CheckStatus.PASS,
        checks=(
            CheckResult(
                status=CheckStatus.PASS,
                code="snapshot_fresh",
                message="agent snapshot is fresh",
                observed_at=now,
            ),
        ),
        evaluated_at=now,
    )
    job = PublishJob(
        id=uuid4(),
        idempotency_key="prepare-key",
        correlation_id=uuid4(),
        label="build",
        game_name="game",
        status=PublishJobStatus.AWAITING_CONFIRMATION,
        client_confirmation=True,
    )
    result = PublishPreflightResult(
        job=job,
        gate=WizardGateResult(
            status=WizardGateStatus.READY,
            selected_station_ids=(client_station_id,),
            reasons=(),
        ),
        admin_report=PreflightReport(
            station_id=admin_station_id,
            status=CheckStatus.PASS,
            checks=report.checks,
            evaluated_at=now,
        ),
        client_reports={client_station_id: report},
    )
    prepare = FakePublishPrepare(result)
    client = TestClient(
        create_app(
            FakeStationQuery([]),
            prepare_publish_job=prepare,
        )
    )

    assert (
        client.post(
            f"/api/v1/publish/jobs/{job.id}/prepare",
            json={"admin_station_id": str(admin_station_id), "confirmation": True},
        ).status_code
        == 401
    )
    response = client.post(
        f"/api/v1/publish/jobs/{job.id}/prepare",
        json={"admin_station_id": str(admin_station_id), "confirmation": True},
        auth=("admin", TEST_PASSWORD),
    )

    assert response.status_code == 200
    assert response.json()["gate"] == {
        "status": "ready",
        "can_advance": True,
        "selected_station_ids": [str(client_station_id)],
        "reasons": [],
    }
    assert response.json()["admin_report"]["can_publish"] is True
    assert response.json()["client_reports"][0]["station_id"] == str(client_station_id)
    assert prepare.calls == [
        {
            "job_id": job.id,
            "admin_station_id": admin_station_id,
            "confirmation": True,
        }
    ]


def test_publish_dispatch_route_returns_publishing_status(monkeypatch) -> None:
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", TEST_PASSWORD)
    job = PublishJob(
        id=uuid4(),
        idempotency_key="dispatch-route-key",
        correlation_id=uuid4(),
        label="build",
        game_name="game",
        status=PublishJobStatus.PUBLISHING,
    )
    dispatch = FakePublishDispatch(PublishDispatchResult(job=job))
    client = TestClient(
        create_app(
            FakeStationQuery([]),
            dispatch_publish_job=dispatch,
        )
    )

    response = client.post(
        f"/api/v1/publish/jobs/{job.id}/dispatch",
        auth=("admin", TEST_PASSWORD),
    )

    assert response.status_code == 200
    assert response.json() == {
        "job_id": str(job.id),
        "status": "publishing",
        "accepted": True,
    }
    assert dispatch.calls == [{"job_id": job.id}]
