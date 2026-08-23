"""Credential storage boundary for the agent-only controller credential."""

import os
from pathlib import Path
import tempfile
from typing import Protocol


class CredentialStore(Protocol):
    """Storage contract implemented by an ACL/DPAPI-backed Windows store later."""

    def load(self) -> str | None:
        """Return the credential or None when the agent is not enrolled."""

    def save(self, credential: str) -> None:
        """Persist one non-empty credential atomically."""

    def clear(self) -> None:
        """Remove the local credential for re-enrollment."""


class FileCredentialStore:
    """Development fallback with atomic write and restrictive POSIX mode.

    Production Windows packaging must replace this implementation with an ACL
    or DPAPI-backed store; the agent never logs or serializes this value.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> str | None:
        try:
            value = self._path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return None
        return value or None

    def save(self, credential: str) -> None:
        if not credential or "\n" in credential or "\r" in credential:
            raise ValueError("credential must be a non-empty single-line value")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{self._path.name}.",
            dir=self._path.parent,
            text=True,
        )
        temporary_path = Path(temporary_name)
        try:
            if hasattr(os, "fchmod"):
                os.fchmod(fd, 0o600)
            else:
                os.chmod(temporary_path, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                file.write(credential)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self._path)
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise

    def clear(self) -> None:
        self._path.unlink(missing_ok=True)


class MemoryCredentialStore:
    """Deterministic store for agent coordination tests."""

    def __init__(self) -> None:
        self._credential: str | None = None

    def load(self) -> str | None:
        return self._credential

    def save(self, credential: str) -> None:
        if not credential:
            raise ValueError("credential cannot be empty")
        self._credential = credential

    def clear(self) -> None:
        self._credential = None
