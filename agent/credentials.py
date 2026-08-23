"""Credential storage boundary for the agent-only controller credential."""

from collections.abc import Callable
import os
from pathlib import Path
import tempfile
from typing import Protocol


class CredentialStore(Protocol):
    """Storage contract for the agent-only controller credential."""

    def load(self) -> str | None:
        """Return the credential or None when the agent is not enrolled."""

    def save(self, credential: str) -> None:
        """Persist one non-empty credential atomically."""

    def clear(self) -> None:
        """Remove the local credential for re-enrollment."""


class CredentialProtector(Protocol):
    """Byte protection boundary implemented by Windows DPAPI in production."""

    def protect(self, value: bytes) -> bytes:
        """Protect bytes without exposing the plaintext to the storage layer."""

    def unprotect(self, value: bytes) -> bytes:
        """Unprotect bytes or raise when the blob is invalid/unavailable."""


class CredentialFileSecurity(Protocol):
    """Filesystem security hook applied before an atomic credential replace."""

    def secure(self, path: Path) -> None:
        """Restrict access to the file or raise without continuing the write."""


class CredentialStoreError(RuntimeError):
    """The local credential cannot be safely protected or recovered."""


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


class ProtectedCredentialStore:
    """Atomic file store for credentials protected by an injected protector.

    The storage layer only handles bytes and never needs to know how protection
    is implemented.  Production Windows composition injects DPAPI; tests can
    inject a deterministic fake protector without pretending to be Windows.
    """

    def __init__(
        self,
        path: Path,
        protector: CredentialProtector,
        *,
        file_security: CredentialFileSecurity | None = None,
    ) -> None:
        self._path = path
        self._protector = protector
        self._file_security = file_security

    def load(self) -> str | None:
        try:
            encrypted = self._path.read_bytes()
        except FileNotFoundError:
            return None
        if not encrypted:
            raise CredentialStoreError("stored credential is empty")
        try:
            plaintext = self._protector.unprotect(encrypted)
            credential = plaintext.decode("utf-8")
            _validate_credential(credential)
        except Exception as exc:
            raise CredentialStoreError("stored credential cannot be recovered") from exc
        return credential

    def save(self, credential: str) -> None:
        _validate_credential(credential)
        try:
            encrypted = self._protector.protect(credential.encode("utf-8"))
        except Exception as exc:
            raise CredentialStoreError("credential protection failed") from exc
        if not isinstance(encrypted, bytes) or not encrypted:
            raise CredentialStoreError("credential protection returned an invalid blob")
        prepare = self._file_security.secure if self._file_security is not None else None
        _write_bytes_atomically(self._path, encrypted, prepare=prepare)

    def clear(self) -> None:
        self._path.unlink(missing_ok=True)


class MemoryCredentialStore:
    """Deterministic store for agent coordination tests."""

    def __init__(self) -> None:
        self._credential: str | None = None

    def load(self) -> str | None:
        return self._credential

    def save(self, credential: str) -> None:
        _validate_credential(credential)
        self._credential = credential

    def clear(self) -> None:
        self._credential = None


def _validate_credential(credential: str) -> None:
    if not credential or "\n" in credential or "\r" in credential:
        raise ValueError("credential must be a non-empty single-line value")


def _write_bytes_atomically(
    path: Path,
    value: bytes,
    *,
    prepare: Callable[[Path], None] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        else:
            os.chmod(temporary_path, 0o600)
        with os.fdopen(fd, "wb") as file:
            file.write(value)
            file.flush()
            os.fsync(file.fileno())
        if prepare is not None:
            prepare(temporary_path)
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def build_credential_store(
    path: Path,
    *,
    allow_plaintext_fallback: bool = False,
) -> CredentialStore:
    """Build the platform store and require explicit plaintext fallback in dev."""

    if os.name != "nt":
        if allow_plaintext_fallback:
            return FileCredentialStore(path)
        raise CredentialStoreError(
            "protected Windows credential store is unavailable on this platform"
        )
    from agent.windows_acl import WindowsCredentialFileSecurity
    from agent.windows_credentials import DpapiCredentialProtector

    return ProtectedCredentialStore(
        path,
        DpapiCredentialProtector(),
        file_security=WindowsCredentialFileSecurity(),
    )
