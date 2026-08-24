from argparse import Namespace
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import scripts.install_windows_agent as installer
from scripts.install_windows_agent import (
    AgentInstallConfig,
    InstallerError,
    build_install_config,
    load_station_report,
)


def test_installer_reads_identity_from_station_report(tmp_path: Path) -> None:
    report_path = tmp_path / "station-report.json"
    report_path.write_text(
        json.dumps(
            {
                "report_version": "1",
                "station": {
                    "station_id": str(uuid4()),
                    "display_name": "CLIENT-01",
                    "hostname": "CLIENT-01",
                    "role": "client",
                },
                "agent": {
                    "agent_uuid": str(uuid4()),
                    "agent_version": "0.1.0",
                    "hostname": "CLIENT-01",
                },
            }
        ),
        encoding="utf-8-sig",
    )

    identity = load_station_report(report_path)

    assert UUID(identity["agent_uuid"])
    assert UUID(identity["station_id"])
    assert identity["agent_version"] == "0.1.0"
    assert identity["hostname"] == "CLIENT-01"


def test_installer_uses_station_uuid_from_report(tmp_path: Path) -> None:
    station_id = uuid4()
    agent_uuid = uuid4()
    report_path = tmp_path / "station-report.json"
    report_path.write_text(
        json.dumps(
            {
                "report_version": "1",
                "station": {
                    "station_id": str(station_id),
                    "display_name": "CLIENT-01",
                    "hostname": "CLIENT-01",
                    "role": "client",
                },
                "agent": {
                    "agent_uuid": str(agent_uuid),
                    "agent_version": "0.1.0",
                    "hostname": "CLIENT-01",
                },
            }
        ),
        encoding="utf-8",
    )
    source_dir = tmp_path / "source"
    for name in ("agent", "domain"):
        (source_dir / name).mkdir(parents=True)
    (source_dir / "pyproject.toml").write_text("", encoding="utf-8")
    (source_dir / "uv.lock").write_text("", encoding="utf-8")

    config = build_install_config(
        Namespace(
            controller_url="http://controller.example:8000",
            station_id=None,
            report=report_path,
            agent_uuid=None,
            agent_version=None,
            hostname=None,
            command_verify_key=None,
            source_dir=source_dir,
            install_dir=tmp_path / "install",
            service_account=".\\client",
            allow_insecure_http=True,
        )
    )

    assert config.station_id == station_id
    assert config.agent_uuid == agent_uuid


def test_enrollment_token_is_requested_with_visible_input(monkeypatch, tmp_path: Path) -> None:
    prompts: list[str] = []
    calls: list[dict[str, str]] = []

    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: prompts.append(prompt) or "one-shot-token",
    )
    monkeypatch.setattr(
        installer,
        "_run",
        lambda _command, *, cwd, env: calls.append(env.copy()),
    )

    installer._enroll(Path("python.exe"), tmp_path, {"AGENT_API_BASE_URL": "https://controller"})

    assert "visible" in prompts[0]
    assert calls == [
        {
            "AGENT_API_BASE_URL": "https://controller",
            "AGENT_ENROLLMENT_TOKEN": "one-shot-token",
        }
    ]


def test_service_scm_commands_use_target_runtime_and_stdin_password(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        installer,
        "_run",
        lambda command, *, cwd, env, input_text=None: calls.append(
            {
                "command": command,
                "cwd": cwd,
                "env": env.copy(),
                "input_text": input_text,
            }
        ),
    )
    python_path = tmp_path / ".venv" / "Scripts" / "python.exe"
    service_runner = tmp_path / "scripts" / "windows_agent_service.py"

    installer._install_service(python_path, service_runner, ".\\client", "service-password")

    assert calls[0]["command"] == [
        str(python_path),
        str(service_runner),
        "install",
    ]
    assert calls[0]["cwd"] == tmp_path
    assert calls[0]["input_text"] == "service-password"
    assert calls[0]["env"]["AGENT_SERVICE_ACCOUNT"] == ".\\client"
    assert "AGENT_SERVICE_PASSWORD" not in calls[0]["env"]


def test_installer_rejects_passwordless_windows_service_account(tmp_path: Path) -> None:
    with pytest.raises(InstallerError, match="password cannot be empty"):
        installer._install_service(
            tmp_path / ".venv" / "Scripts" / "python.exe",
            tmp_path / "scripts" / "windows_agent_service.py",
            ".\\client",
            "",
        )


def test_installer_environment_contains_no_enrollment_token(tmp_path: Path) -> None:
    config = AgentInstallConfig(
        controller_url="https://controller.example",
        station_id=uuid4(),
        agent_uuid=uuid4(),
        agent_version="0.1.0",
        hostname="CLIENT-01",
        command_verify_key="public-key",
        source_dir=tmp_path / "source",
        install_dir=tmp_path / "install",
        service_account=".\\client",
    )

    environment = config.machine_environment()

    assert "AGENT_ENROLLMENT_TOKEN" not in environment
    assert environment["AGENT_COMMAND_VERIFY_KEY"] == "public-key"
    assert environment["AGENT_STATION_ID"] == str(config.station_id)
    assert environment["AGENT_CREDENTIAL_PATH"].endswith("agent.credential")


def test_installer_can_omit_optional_command_verify_key(tmp_path: Path) -> None:
    config = AgentInstallConfig(
        controller_url="http://controller.example:8000",
        station_id=uuid4(),
        agent_uuid=uuid4(),
        agent_version="0.1.0",
        hostname="CLIENT-01",
        command_verify_key=None,
        source_dir=tmp_path / "source",
        install_dir=tmp_path / "install",
        service_account=".\\client",
        allow_insecure_http=True,
    )

    assert "AGENT_COMMAND_VERIFY_KEY" not in config.machine_environment()


def test_installer_rejects_source_inside_install_directory(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    for name in ("agent", "domain"):
        (source_dir / name).mkdir(parents=True)
    (source_dir / "pyproject.toml").write_text("", encoding="utf-8")
    (source_dir / "uv.lock").write_text("", encoding="utf-8")
    args = Namespace(
        controller_url="https://controller.example",
        station_id=str(uuid4()),
        report=None,
        agent_uuid=str(uuid4()),
        agent_version="0.1.0",
        hostname="CLIENT-01",
        command_verify_key="public-key",
        source_dir=source_dir,
        install_dir=source_dir / "installed",
        service_account=".\\client",
        allow_insecure_http=False,
    )

    with pytest.raises(InstallerError, match="inside source-dir"):
        build_install_config(args)
