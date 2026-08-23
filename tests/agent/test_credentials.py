from pathlib import Path

import pytest

from agent.credentials import (
    CredentialStoreError,
    FileCredentialStore,
    MemoryCredentialStore,
    ProtectedCredentialStore,
    build_credential_store,
)
from agent.windows_acl import WindowsCredentialAclError, WindowsCredentialFileSecurity
from agent.windows_credentials import DpapiCredentialError, DpapiCredentialProtector


class FakeCredentialProtector:
    def protect(self, value: bytes) -> bytes:
        return b"protected:" + value[::-1]

    def unprotect(self, value: bytes) -> bytes:
        if not value.startswith(b"protected:"):
            raise ValueError("invalid fake blob")
        return value.removeprefix(b"protected:")[::-1]


class RecordingFileSecurity:
    def __init__(self) -> None:
        self.paths: list[Path] = []

    def secure(self, path: Path) -> None:
        self.paths.append(path)


def test_file_credential_store_round_trips_and_clears(tmp_path: Path) -> None:
    store = FileCredentialStore(tmp_path / "agent" / "credential")

    assert store.load() is None
    store.save("credential-for-test")
    assert store.load() == "credential-for-test"
    store.clear()
    assert store.load() is None


def test_memory_credential_store_is_deterministic() -> None:
    store = MemoryCredentialStore()
    store.save("credential-for-test")
    assert store.load() == "credential-for-test"
    store.clear()
    assert store.load() is None


def test_protected_credential_store_round_trips_without_plaintext_on_disk(
    tmp_path: Path,
) -> None:
    path = tmp_path / "agent" / "credential"
    store = ProtectedCredentialStore(path, FakeCredentialProtector())

    store.save("credential-for-test")

    assert store.load() == "credential-for-test"
    assert b"credential-for-test" not in path.read_bytes()
    store.clear()
    assert store.load() is None


def test_protected_credential_store_secures_temporary_file_before_replace(
    tmp_path: Path,
) -> None:
    path = tmp_path / "credential"
    security = RecordingFileSecurity()

    ProtectedCredentialStore(
        path,
        FakeCredentialProtector(),
        file_security=security,
    ).save("credential-for-test")

    assert security.paths
    assert security.paths[0] != path
    assert security.paths[0].exists() is False
    assert path.exists() is True


@pytest.mark.parametrize("credential", ["", "line\nbreak", "line\rbreak"])
def test_protected_credential_store_rejects_invalid_credentials(
    tmp_path: Path,
    credential: str,
) -> None:
    store = ProtectedCredentialStore(tmp_path / "credential", FakeCredentialProtector())

    with pytest.raises(ValueError):
        store.save(credential)


def test_protected_credential_store_fails_closed_on_corrupt_blob(tmp_path: Path) -> None:
    path = tmp_path / "credential"
    path.write_bytes(b"corrupt")

    with pytest.raises(CredentialStoreError, match="cannot be recovered"):
        ProtectedCredentialStore(path, FakeCredentialProtector()).load()


def test_dpapi_protector_is_windows_only() -> None:
    with pytest.raises(DpapiCredentialError, match="only on Windows"):
        DpapiCredentialProtector()


def test_windows_acl_adapter_is_fail_closed_outside_windows(tmp_path: Path) -> None:
    with pytest.raises(WindowsCredentialAclError, match="only on Windows"):
        WindowsCredentialFileSecurity().secure(tmp_path / "credential")


def test_platform_store_requires_explicit_plaintext_dev_fallback(tmp_path: Path) -> None:
    with pytest.raises(CredentialStoreError, match="unavailable on this platform"):
        build_credential_store(tmp_path / "credential")

    assert (
        build_credential_store(
            tmp_path / "fallback",
            allow_plaintext_fallback=True,
        ).__class__
        is FileCredentialStore
    )
