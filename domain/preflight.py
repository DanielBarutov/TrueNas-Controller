"""Pure process, drive and freshness preflight evaluation."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from domain.snapshot import ProcessInfo, ProcessSnapshot
from domain.station import Station, StationRole
from domain.time import ensure_utc


class CheckStatus(StrEnum):
    """Severity/status of one preflight check."""

    PASS = "pass"
    BLOCK = "block"
    UNKNOWN = "unknown"
    WARNING = "warning"


class RuleSeverity(StrEnum):
    """Configured severity when a process rule is violated."""

    BLOCKING = "blocking"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ProcessRule:
    """Rule matching a normalized process name for a station role."""

    name: str
    role: StationRole | None = None
    required_closed: bool = True
    severity: RuleSeverity = RuleSeverity.BLOCKING
    enabled: bool = True
    persistent_policy: bool = False
    id: UUID | None = None

    def matches(self, station: Station, process_name: str) -> bool:
        return (
            self.enabled
            and (self.role is None or self.role is station.role)
            and self.name.casefold() == process_name.casefold()
        )


@dataclass(frozen=True, slots=True)
class PreflightPolicy:
    """Read-only checks required before a station can become ready."""

    max_snapshot_age: timedelta = timedelta(seconds=30)
    required_drive_letter: str = "D:"
    min_free_bytes: int = 0


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One explainable preflight result."""

    status: CheckStatus
    code: str
    message: str
    observed_at: datetime
    source_snapshot_id: UUID | None = None
    matched_processes: tuple[ProcessInfo, ...] = ()


@dataclass(frozen=True, slots=True)
class PreflightReport:
    """Aggregate report used by later wizard/application gates."""

    station_id: UUID
    status: CheckStatus
    checks: tuple[CheckResult, ...]
    evaluated_at: datetime

    @property
    def can_publish(self) -> bool:
        return self.status in {CheckStatus.PASS, CheckStatus.WARNING}


def evaluate_preflight(
    station: Station,
    snapshot: ProcessSnapshot | None,
    rules: tuple[ProcessRule, ...],
    policy: PreflightPolicy,
    *,
    now: datetime | None = None,
) -> PreflightReport:
    """Evaluate process, drive and freshness gates without performing IO."""

    evaluated_at = ensure_utc(now or datetime.now(UTC))
    if not station.enabled or station.deleted_at is not None:
        disabled = CheckResult(
            status=CheckStatus.BLOCK,
            code="station_disabled",
            message="station is disabled or soft-deleted",
            observed_at=evaluated_at,
        )
        return PreflightReport(station.station_id, CheckStatus.BLOCK, (disabled,), evaluated_at)
    if snapshot is None:
        unknown = CheckResult(
            status=CheckStatus.UNKNOWN,
            code="snapshot_missing",
            message="agent snapshot is missing",
            observed_at=evaluated_at,
        )
        return PreflightReport(station.station_id, CheckStatus.UNKNOWN, (unknown,), evaluated_at)

    if snapshot.station_id != station.station_id:
        mismatch = CheckResult(
            status=CheckStatus.BLOCK,
            code="snapshot_station_mismatch",
            message="agent snapshot belongs to another station",
            observed_at=evaluated_at,
        )
        return PreflightReport(station.station_id, CheckStatus.BLOCK, (mismatch,), evaluated_at)

    normalized_snapshot = snapshot
    snapshot_age = evaluated_at - ensure_utc(normalized_snapshot.captured_at)
    checks = [
        _freshness_check(snapshot_age, policy, evaluated_at),
        _drive_check(normalized_snapshot, policy, evaluated_at),
        _process_check(station, normalized_snapshot, rules, evaluated_at),
    ]
    status = _aggregate_status(checks)
    return PreflightReport(station.station_id, status, tuple(checks), evaluated_at)


def _freshness_check(
    snapshot_age: timedelta,
    policy: PreflightPolicy,
    observed_at: datetime,
) -> CheckResult:
    if snapshot_age < timedelta(0) or snapshot_age > policy.max_snapshot_age:
        return CheckResult(
            CheckStatus.UNKNOWN,
            "snapshot_stale",
            "agent snapshot is stale or from the future",
            observed_at,
        )
    return CheckResult(CheckStatus.PASS, "snapshot_fresh", "agent snapshot is fresh", observed_at)


def _drive_check(
    snapshot: ProcessSnapshot,
    policy: PreflightPolicy,
    observed_at: datetime,
) -> CheckResult:
    expected = policy.required_drive_letter.casefold()
    drive = next((item for item in snapshot.drives if item.letter.casefold() == expected), None)
    if drive is None or not drive.present:
        return CheckResult(
            CheckStatus.BLOCK,
            "drive_missing",
            f"required drive {policy.required_drive_letter} is not present",
            observed_at,
        )
    if drive.free_bytes is None:
        return CheckResult(
            CheckStatus.UNKNOWN,
            "drive_free_space_unknown",
            f"free space for {policy.required_drive_letter} is unknown",
            observed_at,
        )
    if drive.free_bytes < policy.min_free_bytes:
        return CheckResult(
            CheckStatus.BLOCK,
            "drive_low_space",
            f"free space for {policy.required_drive_letter} is below threshold",
            observed_at,
        )
    return CheckResult(CheckStatus.PASS, "drive_ready", "required drive is ready", observed_at)


def _process_check(
    station: Station,
    snapshot: ProcessSnapshot,
    rules: tuple[ProcessRule, ...],
    observed_at: datetime,
) -> CheckResult:
    required_rules = tuple(rule for rule in rules if rule.required_closed)
    matched_processes = tuple(
        process
        for process in snapshot.processes
        if any(rule.matches(station, process.name) for rule in required_rules)
    )
    violations = [
        rule
        for rule in required_rules
        if any(rule.matches(station, process.name) for process in snapshot.processes)
    ]
    if not violations:
        return CheckResult(
            CheckStatus.PASS,
            "processes_closed",
            "required processes are closed",
            observed_at,
            matched_processes=matched_processes,
        )
    if any(rule.severity is RuleSeverity.BLOCKING for rule in violations):
        return CheckResult(
            CheckStatus.BLOCK,
            "blocking_process",
            "a required process is still running",
            observed_at,
            matched_processes=matched_processes,
        )
    return CheckResult(
        CheckStatus.WARNING,
        "warning_process",
        "a warning-level process rule matched",
        observed_at,
        matched_processes=matched_processes,
    )


def _aggregate_status(checks: list[CheckResult]) -> CheckStatus:
    statuses = {check.status for check in checks}
    if CheckStatus.BLOCK in statuses:
        return CheckStatus.BLOCK
    if CheckStatus.UNKNOWN in statuses:
        return CheckStatus.UNKNOWN
    if CheckStatus.WARNING in statuses:
        return CheckStatus.WARNING
    return CheckStatus.PASS
