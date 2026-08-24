"""Stable script path used by the Windows Service Control Manager."""

import importlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
main = importlib.import_module("agent.entrypoint").main


if __name__ == "__main__":
    main()
