import json
from pathlib import Path
from uuid import UUID

import scripts.agent_station_report as station_report
from scripts.agent_station_report import collect_station_report


def test_station_report_is_repeatable_and_contains_no_credentials(tmp_path: Path) -> None:
    identity_path = tmp_path / "identity.json"

    first = collect_station_report(identity_path=identity_path)
    second = collect_station_report(identity_path=identity_path)
    serialized = json.dumps(first.as_dict())

    assert first.station["role"] == "client"
    assert UUID(first.agent["agent_uuid"]) == UUID(second.agent["agent_uuid"])
    assert "credential" not in serialized
    assert "enrollment_token" not in serialized


def test_station_report_has_the_fields_needed_by_operator(tmp_path: Path) -> None:
    report = collect_station_report(identity_path=tmp_path / "identity.json")

    assert set(report.station) == {"display_name", "hostname", "role"}
    assert set(report.agent) >= {"agent_uuid", "agent_version", "hostname"}
    assert set(report.network) == {"ip_addresses", "mac_addresses"}
    assert report.drives[0].letter == "D:"


def test_station_report_ignores_loopback_and_link_local_addresses(monkeypatch) -> None:
    monkeypatch.setattr(
        station_report.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (2, 1, 6, "", ("127.0.1.1", 0)),
            (2, 1, 6, "", ("169.254.10.5", 0)),
            (2, 1, 6, "", ("192.0.2.10", 0)),
        ],
    )

    assert station_report._local_ip_addresses("CLIENT-01") == ["192.0.2.10"]
