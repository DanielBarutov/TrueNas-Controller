"""Stable script path used by the Windows Service Control Manager."""

import importlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
main = importlib.import_module("agent.entrypoint").main


if __name__ == "__main__":
    command = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if command == "install":
        from agent.windows_service_control import install_windows_service

        install_windows_service(
            command_line=f'"{sys.executable}" "{Path(__file__).resolve()}"',
        )
    elif command == "start":
        from agent.windows_service_control import start_windows_service

        start_windows_service()
    else:
        main()
