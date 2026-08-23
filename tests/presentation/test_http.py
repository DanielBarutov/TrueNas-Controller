from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from application.lifecycle import EnrollmentResult, HeartbeatResult, StationRegistration
from domain.preflight import CheckResult, CheckStatus, PreflightReport
from domain.station import Station, StationRole, StationStatus
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

    async def execute(self, *, credential: str, snapshot) -> HeartbeatResult:
        self.credential = credential
        return HeartbeatResult(station_id=snapshot.station_id, received_at=datetime.now(UTC))


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
