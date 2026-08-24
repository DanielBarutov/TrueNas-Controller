from pathlib import Path
from uuid import uuid4

from agent import entrypoint
from agent.credentials import CredentialStoreError


class RecordingCredentialStore:
    def __init__(self) -> None:
        self.values: list[str] = []
        self.cleared = False

    def save(self, credential: str) -> None:
        self.values.append(credential)

    def load(self) -> str | None:
        return self.values[-1] if self.values else None

    def clear(self) -> None:
        self.cleared = True


def test_credential_store_preflight_round_trips_and_cleans_probe(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = RecordingCredentialStore()
    monkeypatch.setattr(entrypoint, "build_credential_store", lambda _path: store)
    env = {
        "AGENT_API_BASE_URL": "https://controller.example",
        "AGENT_STATION_ID": str(uuid4()),
        "AGENT_UUID": str(uuid4()),
        "AGENT_VERSION": "0.1.0",
        "AGENT_HOSTNAME": "CLIENT-01",
        "AGENT_CREDENTIAL_PATH": str(tmp_path / "agent.credential"),
    }

    entrypoint.check_credential_store_from_environment(env)

    assert store.values == ["credential-store-preflight"]
    assert store.cleared is True
    assert list(tmp_path.iterdir()) == []


def test_migrate_credential_store_reprotects_legacy_user_scope(
    tmp_path: Path,
) -> None:
    class MachineStore:
        def __init__(self) -> None:
            self.saved: list[str] = []

        def load(self) -> str | None:
            raise CredentialStoreError("legacy blob")

        def save(self, credential: str) -> None:
            self.saved.append(credential)

        def clear(self) -> None:
            pass

    class LegacyStore:
        def load(self) -> str | None:
            return "legacy-credential"

        def save(self, credential: str) -> None:
            raise AssertionError("legacy store must not be written")

        def clear(self) -> None:
            pass

    credential_path = tmp_path / "agent.credential"
    credential_path.write_bytes(b"legacy-protected-blob")
    env = {
        "AGENT_API_BASE_URL": "https://controller.example",
        "AGENT_STATION_ID": str(uuid4()),
        "AGENT_UUID": str(uuid4()),
        "AGENT_VERSION": "0.1.0",
        "AGENT_HOSTNAME": "CLIENT-01",
        "AGENT_CREDENTIAL_PATH": str(credential_path),
    }
    machine_store = MachineStore()

    entrypoint.migrate_credential_store_from_environment(
        env,
        machine_store=machine_store,
        legacy_store=LegacyStore(),
    )

    assert machine_store.saved == ["legacy-credential"]
