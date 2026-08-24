"""Install and enroll the Windows agent from a checked-out release folder.

The installer is intentionally an orchestration boundary. It does not call the
Controller with operator Basic Auth, puts the one-shot enrollment token only in
the child process environment, and never accepts a service-account password as
a command-line argument.
"""

from __future__ import annotations

import argparse
import contextlib
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlparse
from uuid import UUID

DEFAULT_AGENT_VERSION = "0.1.0"
DEFAULT_CREDENTIAL_NAME = "agent.credential"
DEFAULT_INSTALL_SUBPATH = Path("TrueNasController") / "agent"
SERVICE_NAME = "TrueNasControllerAgent"
SERVICE_DISPLAY_NAME = "TrueNAS Controller Agent"
SERVICE_ACCOUNT = "LocalSystem"
COPY_IGNORES = shutil.ignore_patterns(
    ".git",
    ".venv",
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
    "dist",
    "build",
    ".env",
    ".env.*",
    "*.credential",
)


class InstallerError(RuntimeError):
    """The installer cannot continue without weakening the deployment."""


@dataclass(frozen=True, slots=True)
class AgentInstallConfig:
    controller_url: str
    station_id: UUID
    agent_uuid: UUID
    agent_version: str
    hostname: str
    command_verify_key: str | None
    source_dir: Path
    install_dir: Path
    allow_insecure_http: bool = False

    @property
    def credential_path(self) -> Path:
        return self.install_dir / DEFAULT_CREDENTIAL_NAME

    @property
    def service_runner(self) -> Path:
        return self.install_dir / "scripts" / "windows_agent_service.py"

    def machine_environment(self) -> dict[str, str]:
        values = {
            "AGENT_API_BASE_URL": self.controller_url,
            "AGENT_STATION_ID": str(self.station_id),
            "AGENT_UUID": str(self.agent_uuid),
            "AGENT_VERSION": self.agent_version,
            "AGENT_HOSTNAME": self.hostname,
            "AGENT_CREDENTIAL_PATH": str(self.credential_path),
        }
        if self.command_verify_key:
            values["AGENT_COMMAND_VERIFY_KEY"] = self.command_verify_key
        if self.allow_insecure_http:
            values["AGENT_ALLOW_INSECURE_HTTP"] = "1"
        return values


def default_source_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def default_install_dir() -> Path:
    program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
    return Path(program_data) / DEFAULT_INSTALL_SUBPATH


def load_station_report(path: Path) -> dict[str, str]:
    """Read only identity fields from the report generated on the client."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallerError(f"cannot read station report: {path}") from exc
    if not isinstance(raw, dict) or raw.get("report_version") != "1":
        raise InstallerError("station report version is unsupported")
    station = _record(raw.get("station"), "station")
    agent = _record(raw.get("agent"), "agent")
    if station.get("role") != "client":
        raise InstallerError("station report must describe a client station")
    return {
        "station_id": _required_string(
            station.get("station_id") or agent.get("agent_uuid"),
            "station.station_id",
        ),
        "agent_uuid": _required_string(agent.get("agent_uuid"), "agent.agent_uuid"),
        "agent_version": _required_string(agent.get("agent_version"), "agent.agent_version"),
        "hostname": _required_string(agent.get("hostname"), "agent.hostname"),
    }


def build_install_config(args: argparse.Namespace) -> AgentInstallConfig:
    report = load_station_report(args.report) if args.report else {}
    station_id = _parse_uuid(
        args.station_id or report.get("station_id") or report.get("agent_uuid"),
        "station-id or report.station_id",
    )
    agent_uuid = _parse_uuid(
        args.agent_uuid or report.get("agent_uuid"),
        "agent-uuid or report.agent_uuid",
    )
    agent_version = args.agent_version or report.get("agent_version") or DEFAULT_AGENT_VERSION
    hostname = args.hostname or report.get("hostname") or ""
    source_dir = args.source_dir.resolve()
    install_dir = args.install_dir.resolve()
    _validate_non_empty(agent_version, "agent-version")
    _validate_non_empty(hostname, "hostname")
    if args.command_verify_key:
        _validate_non_empty(args.command_verify_key, "command-verify-key")
    _validate_controller_url(args.controller_url, allow_insecure_http=args.allow_insecure_http)
    _validate_source_dir(source_dir)
    if install_dir == source_dir or install_dir.is_relative_to(source_dir):
        raise InstallerError("install-dir must not be inside source-dir")
    return AgentInstallConfig(
        controller_url=args.controller_url.rstrip("/"),
        station_id=station_id,
        agent_uuid=agent_uuid,
        agent_version=agent_version,
        hostname=hostname,
        command_verify_key=args.command_verify_key or None,
        source_dir=source_dir,
        install_dir=install_dir,
        allow_insecure_http=args.allow_insecure_http,
    )


def install(config: AgentInstallConfig, *, uv_path: str = "uv") -> None:
    """Perform the Windows-only copy, enrollment and SCM registration flow."""

    _require_windows()
    _require_elevated()
    resolved_uv = shutil.which(uv_path) or uv_path
    if not shutil.which(resolved_uv) and not Path(resolved_uv).exists():
        raise InstallerError("uv is required; install it before running the agent installer")
    print(f"[1/6] Copying agent to {config.install_dir}")
    _copy_source(config.source_dir, config.install_dir)
    print("[2/6] Installing locked runtime dependencies")
    _run([resolved_uv, "sync", "--locked", "--no-dev"], cwd=config.install_dir)
    python_path = config.install_dir / ".venv" / "Scripts" / "python.exe"
    if not python_path.is_file():
        raise InstallerError(f"uv did not create the expected interpreter: {python_path}")

    machine_env = config.machine_environment()
    print("[3/6] Writing non-secret machine configuration")
    _write_machine_environment(machine_env)
    process_env = os.environ.copy()
    process_env.update(machine_env)
    process_env.pop("AGENT_ENROLLMENT_TOKEN", None)
    if not config.allow_insecure_http:
        process_env.pop("AGENT_ALLOW_INSECURE_HTTP", None)

    if config.credential_path.exists():
        print("[4/6] Checking/migrating credential for LocalSystem; enrollment skipped")
        _run(
            [str(python_path), "-m", "agent.entrypoint", "migrate-credential-store"],
            cwd=config.install_dir,
            env=process_env,
        )
    else:
        print("[4/6] Checking protected credential store before token use")
        _run(
            [str(python_path), "-m", "agent.entrypoint", "check-credential-store"],
            cwd=config.install_dir,
            env=process_env,
        )
        print("[4/6] Enrolling agent; the one-shot token is entered visibly")
        _enroll(python_path, config.install_dir, process_env)

    print("[5/6] Registering Windows Service")
    _install_service(python_path, config.service_runner)
    print("[6/6] Starting and checking Windows Service")
    _start_and_check_service(python_path, config.service_runner, config.install_dir)
    print(f"Agent installed and running: {SERVICE_NAME}")


def _enroll(python_path: Path, install_dir: Path, environment: dict[str, str]) -> None:
    token = input("One-shot enrollment token (visible; not the verify key): ").strip()
    if not token:
        raise InstallerError("enrollment token cannot be empty")
    child_environment = environment.copy()
    child_environment["AGENT_ENROLLMENT_TOKEN"] = token
    try:
        _run(
            [str(python_path), "-m", "agent.entrypoint", "enroll"],
            cwd=install_dir,
            env=child_environment,
        )
    finally:
        child_environment.pop("AGENT_ENROLLMENT_TOKEN", None)
        del token


def _copy_source(source_dir: Path, install_dir: Path) -> None:
    install_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, install_dir, dirs_exist_ok=True, ignore=COPY_IGNORES)


def _install_service(
    python_path: Path,
    service_runner: Path,
) -> None:
    service_environment = os.environ.copy()
    service_environment.pop("AGENT_ENROLLMENT_TOKEN", None)
    _run(
        [str(python_path), str(service_runner), "install"],
        cwd=service_runner.parents[1],
        env=service_environment,
    )


def _start_and_check_service(
    python_path: Path,
    service_runner: Path,
    install_dir: Path,
) -> None:
    _run(
        [str(python_path), str(service_runner), "start"],
        cwd=install_dir,
        env=os.environ.copy(),
    )


def _write_machine_environment(values: dict[str, str]) -> None:
    if os.name != "nt":
        raise InstallerError("machine environment is available only on Windows")
    import winreg

    key_path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
    with winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        key_path,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        for name, value in values.items():
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        for name in (
            "AGENT_ENROLLMENT_TOKEN",
            "AGENT_ALLOW_INSECURE_HTTP",
            "AGENT_COMMAND_VERIFY_KEY",
        ):
            if name not in values:
                with contextlib.suppress(FileNotFoundError):
                    winreg.DeleteValue(key, name)


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> None:
    try:
        subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=True,
        )
    except OSError as exc:
        raise InstallerError(f"could not execute {Path(command[0]).name}") from exc
    except subprocess.CalledProcessError as exc:
        raise InstallerError(f"command failed with exit code {exc.returncode}") from exc


def _validate_source_dir(source_dir: Path) -> None:
    required = ("agent", "domain", "pyproject.toml", "uv.lock")
    missing = [name for name in required if not (source_dir / name).exists()]
    if missing:
        missing_names = ", ".join(missing)
        raise InstallerError(f"source-dir is not a controller checkout; missing: {missing_names}")


def _validate_controller_url(url: str, *, allow_insecure_http: bool) -> None:
    parsed = urlparse(url)
    allowed = {"https"}
    if allow_insecure_http:
        allowed.add("http")
    if parsed.scheme not in allowed or not parsed.netloc:
        raise InstallerError(
            "controller-url must be a full HTTPS URL, or HTTP with --allow-insecure-http"
        )


def _parse_uuid(value: str | None, field: str) -> UUID:
    if not value:
        raise InstallerError(f"{field} is required or must be present in --report")
    try:
        return UUID(value)
    except ValueError as exc:
        raise InstallerError(f"{field} must be a UUID") from exc


def _record(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise InstallerError(f"{field} section is missing from station report")
    return value


def _required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InstallerError(f"{field} is missing from station report")
    return value.strip()


def _validate_non_empty(value: str, field: str) -> None:
    if not value.strip():
        raise InstallerError(f"{field} cannot be empty")


def _require_windows() -> None:
    if os.name != "nt":
        raise InstallerError("the Windows agent installer must run on Windows")


def _require_elevated() -> None:
    try:
        import ctypes

        elevated = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError) as exc:
        raise InstallerError("could not verify administrator privileges") from exc
    if not elevated:
        raise InstallerError("run the installer from an elevated PowerShell")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install and enroll TrueNAS Controller Windows agent"
    )
    parser.add_argument(
        "--controller-url",
        required=True,
        help="Controller base URL, for example https://controller.example",
    )
    parser.add_argument(
        "--station-id",
        help="station UUID; normally read from --report, use only as an override",
    )
    parser.add_argument("--report", type=Path, help="JSON file produced by agent_station_report.py")
    parser.add_argument("--agent-uuid", help="agent UUID; normally read from --report")
    parser.add_argument("--agent-version", help=f"agent version (default: {DEFAULT_AGENT_VERSION})")
    parser.add_argument("--hostname", help="agent hostname; normally read from --report")
    parser.add_argument(
        "--command-verify-key",
        help="Optional URL-safe base64 public Ed25519 key for signed refresh commands",
    )
    parser.add_argument("--source-dir", type=Path, default=default_source_dir())
    parser.add_argument("--install-dir", type=Path, default=default_install_dir())
    parser.add_argument("--uv-path", default="uv", help="uv executable or path")
    parser.add_argument("--allow-insecure-http", action="store_true", help="development only")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and print the plan without changing Windows",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    config = build_install_config(args)
    if args.dry_run:
        print(f"source: {config.source_dir}")
        print(f"install: {config.install_dir}")
        print(f"service: {SERVICE_NAME} ({SERVICE_ACCOUNT})")
        print(f"controller: {config.controller_url}")
        print(f"station: {config.station_id}")
        print(f"agent: {config.agent_uuid} / {config.hostname} / {config.agent_version}")
        print("dry-run: no token requested and no files or services changed")
        return
    install(config, uv_path=args.uv_path)


if __name__ == "__main__":
    main()
