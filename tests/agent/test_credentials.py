from pathlib import Path

from agent.credentials import FileCredentialStore, MemoryCredentialStore


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
