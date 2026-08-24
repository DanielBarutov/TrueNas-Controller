from pathlib import Path
from uuid import uuid4

from agent import entrypoint


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
