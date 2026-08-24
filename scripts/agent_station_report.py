"""Create a safe client-side station report for operator onboarding.

This helper intentionally uses only the Python standard library. It never
contacts the Controller, asks for Basic Auth, or prints an enrollment token or
agent credential. The generated agent UUID is persisted locally so a later
enrollment step can use the same identity.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import ipaddress
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import uuid

REPORT_VERSION = "1"
DEFAULT_AGENT_VERSION = "0.1.0"


@dataclass(frozen=True, slots=True)
class DriveReport:
    letter: str
    present: bool
    free_bytes: int | None


@dataclass(frozen=True, slots=True)
class StationReport:
    report_version: str
    station: dict[str, str]
    agent: dict[str, str]
    network: dict[str, list[str]]
    drives: tuple[DriveReport, ...]
    collected_at: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def default_identity_path() -> Path:
    """Return a stable per-machine path for the non-secret agent UUID."""

    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", r"C:\Users\Public\AppData\Local"))
    else:
        root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "TrueNasController" / "agent" / "identity.json"


def load_or_create_agent_uuid(path: Path) -> uuid.UUID:
    """Keep the same UUID across report reruns without storing a secret."""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        agent_uuid = uuid.uuid4()
        _write_identity(path, agent_uuid)
        return agent_uuid
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read agent identity file: {path}") from exc

    try:
        return uuid.UUID(str(data["agent_uuid"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"agent identity file is invalid: {path}") from exc


def collect_station_report(
    *,
    identity_path: Path | None = None,
    agent_version: str = DEFAULT_AGENT_VERSION,
) -> StationReport:
    """Collect only the fields required to create and enroll a client station."""

    hostname = socket.gethostname().strip() or "UNKNOWN"
    agent_uuid = load_or_create_agent_uuid(identity_path or default_identity_path())
    return StationReport(
        report_version=REPORT_VERSION,
        station={
            "display_name": hostname,
            "hostname": hostname,
            "role": "client",
        },
        agent={
            "agent_uuid": str(agent_uuid),
            "agent_version": agent_version,
            "hostname": hostname,
            "platform": f"{platform.system()} {platform.release()}".strip(),
        },
        network={
            "ip_addresses": _local_ip_addresses(hostname),
            "mac_addresses": [_mac_address()],
        },
        drives=(_drive_report("D:"),),
        collected_at=datetime.now(UTC).isoformat(),
    )


def _local_ip_addresses(hostname: str) -> list[str]:
    addresses: set[str] = set()
    try:
        records = socket.getaddrinfo(hostname, None, family=socket.AF_INET)
    except OSError:
        records = []
    for record in records:
        address = record[4][0]
        parsed = ipaddress.ip_address(address)
        if not parsed.is_loopback and not parsed.is_link_local:
            addresses.add(address)
    return sorted(addresses)


def _mac_address() -> str:
    node = uuid.getnode()
    return ":".join(f"{node >> shift & 0xFF:02X}" for shift in range(40, -1, -8))


def _drive_report(letter: str) -> DriveReport:
    root = f"{letter}\\" if os.name == "nt" else letter
    try:
        free_bytes = shutil.disk_usage(root).free
    except OSError:
        return DriveReport(letter=letter, present=False, free_bytes=None)
    return DriveReport(letter=letter, present=True, free_bytes=free_bytes)


def _write_identity(path: Path, agent_uuid: uuid.UUID) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(
        json.dumps({"agent_uuid": str(agent_uuid)}, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_path, path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Print safe station data for Controller onboarding.",
    )
    parser.add_argument(
        "--identity-path",
        type=Path,
        help="Path for the non-secret persisted agent UUID.",
    )
    parser.add_argument(
        "--agent-version",
        default=DEFAULT_AGENT_VERSION,
        help=f"Agent version shown in the report (default: {DEFAULT_AGENT_VERSION}).",
    )
    parser.add_argument(
        "--text",
        action="store_true",
        help="Print a human-readable summary instead of JSON.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    report = collect_station_report(
        identity_path=args.identity_path,
        agent_version=args.agent_version,
    )
    if args.text:
        print(f"display_name: {report.station['display_name']}")
        print(f"hostname: {report.station['hostname']}")
        print(f"role: {report.station['role']}")
        print(f"agent_uuid: {report.agent['agent_uuid']}")
        print(f"agent_version: {report.agent['agent_version']}")
        print("\nJSON для вставки в Controller UI:\n")
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
