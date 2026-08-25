from datetime import UTC, datetime, timedelta
from uuid import uuid4

from domain.preflight import (
    CheckStatus,
    PreflightPolicy,
    ProcessRule,
    RuleSeverity,
    evaluate_preflight,
)
from domain.snapshot import DriveInfo, ProcessInfo, ProcessSnapshot
from domain.station import Station, StationRole, StationStatus

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)


def make_station() -> Station:
    return Station(
        id=uuid4(),
        station_id=uuid4(),
        display_name="Client 01",
        hostname="client-01",
        role=StationRole.CLIENT,
        status=StationStatus.ONLINE,
    )


def test_blocking_process_prevents_publish() -> None:
    station = make_station()
    snapshot = ProcessSnapshot(
        station_id=station.station_id,
        captured_at=NOW,
        agent_version="1.0.0",
        processes=(ProcessInfo("game.exe", 42, "D:\\Games\\game.exe"),),
        drives=(DriveInfo("D:", True, 100),),
    )

    report = evaluate_preflight(
        station,
        snapshot,
        (ProcessRule("game.exe"),),
        PreflightPolicy(min_free_bytes=50),
        now=NOW,
    )

    assert report.status is CheckStatus.BLOCK
    assert report.can_publish is False
    assert {check.code for check in report.checks} == {
        "snapshot_fresh",
        "drive_ready",
        "blocking_process",
    }
    process_check = next(check for check in report.checks if check.code == "blocking_process")
    assert [(item.name, item.pid, item.path) for item in process_check.matched_processes] == [
        ("game.exe", 42, "D:\\Games\\game.exe"),
    ]


def test_warning_process_does_not_block_publish() -> None:
    station = make_station()
    snapshot = ProcessSnapshot(
        station_id=station.station_id,
        captured_at=NOW,
        agent_version="1.0.0",
        processes=(ProcessInfo("helper.exe"),),
        drives=(DriveInfo("D:", True, 100),),
    )

    report = evaluate_preflight(
        station,
        snapshot,
        (ProcessRule("helper.exe", severity=RuleSeverity.WARNING),),
        PreflightPolicy(min_free_bytes=50),
        now=NOW,
    )

    assert report.status is CheckStatus.WARNING
    assert report.can_publish is True
    process_check = next(check for check in report.checks if check.code == "warning_process")
    assert [item.name for item in process_check.matched_processes] == ["helper.exe"]


def test_missing_or_stale_snapshot_is_unknown() -> None:
    station = make_station()
    policy = PreflightPolicy(max_snapshot_age=timedelta(seconds=30))

    missing = evaluate_preflight(station, None, (), policy, now=NOW)
    stale = evaluate_preflight(
        station,
        ProcessSnapshot(
            station_id=station.station_id,
            captured_at=NOW - timedelta(minutes=1),
            agent_version="1.0.0",
            drives=(DriveInfo("D:", True, 100),),
        ),
        (),
        policy,
        now=NOW,
    )

    assert missing.status is CheckStatus.UNKNOWN
    assert stale.status is CheckStatus.UNKNOWN
    assert missing.can_publish is False
    assert stale.can_publish is False


def test_missing_or_low_space_drive_blocks() -> None:
    station = make_station()
    missing = ProcessSnapshot(
        station_id=station.station_id,
        captured_at=NOW,
        agent_version="1.0.0",
        drives=(),
    )
    low_space = ProcessSnapshot(
        station_id=station.station_id,
        captured_at=NOW,
        agent_version="1.0.0",
        drives=(DriveInfo("D:", True, 10),),
    )

    missing_report = evaluate_preflight(
        station, missing, (), PreflightPolicy(min_free_bytes=50), now=NOW
    )
    low_space_report = evaluate_preflight(
        station, low_space, (), PreflightPolicy(min_free_bytes=50), now=NOW
    )

    assert missing_report.status is CheckStatus.BLOCK
    assert low_space_report.status is CheckStatus.BLOCK


def test_all_preflight_checks_pass() -> None:
    station = make_station()
    snapshot = ProcessSnapshot(
        station_id=station.station_id,
        captured_at=NOW,
        agent_version="1.0.0",
        drives=(DriveInfo("D:", True, 100),),
    )

    report = evaluate_preflight(
        station,
        snapshot,
        (),
        PreflightPolicy(min_free_bytes=50),
        now=NOW,
    )

    assert report.status is CheckStatus.PASS
    assert report.can_publish is True


def test_snapshot_binding_and_disabled_station_are_blocking() -> None:
    station = make_station()
    wrong_snapshot = ProcessSnapshot(
        station_id=uuid4(),
        captured_at=NOW,
        agent_version="1.0.0",
        drives=(DriveInfo("D:", True, 100),),
    )
    disabled_station = Station(
        id=station.id,
        station_id=station.station_id,
        display_name=station.display_name,
        hostname=station.hostname,
        role=station.role,
        status=StationStatus.DISABLED,
        enabled=False,
    )

    mismatch = evaluate_preflight(station, wrong_snapshot, (), PreflightPolicy(), now=NOW)
    disabled = evaluate_preflight(
        disabled_station,
        wrong_snapshot,
        (),
        PreflightPolicy(),
        now=NOW,
    )

    assert mismatch.status is CheckStatus.BLOCK
    assert mismatch.checks[0].code == "snapshot_station_mismatch"
    assert disabled.status is CheckStatus.BLOCK
    assert disabled.checks[0].code == "station_disabled"
