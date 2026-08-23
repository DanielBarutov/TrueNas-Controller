"""Deterministic fake storage adapter for publish tests.

This module never calls TrueNAS. Its state is intentionally inspectable so tests
can prove old mapping retention, idempotency and partial failure behavior.
"""

from uuid import UUID

from application.publish import UnknownStorageOutcome


class FakePublishStorageAdapter:
    """In-memory master/clone/mapping model implementing the publish port."""

    def __init__(self, initial_mappings: dict[UUID, str] | None = None) -> None:
        self.masters: dict[UUID, str] = {}
        self.clones: dict[tuple[UUID, UUID], str] = {}
        self.mappings = dict(initial_mappings or {})
        self.fail_clone_for: set[UUID] = set()
        self.fail_switch_for: set[UUID] = set()
        self.unknown_switch_for: set[UUID] = set()
        self.fail_verify_for: set[UUID] = set()
        self.create_master_calls = 0
        self.create_clone_calls = 0

    async def create_master(self, job_id: UUID, label: str) -> str:
        self.create_master_calls += 1
        if job_id not in self.masters:
            self.masters[job_id] = f"master:{job_id}"
        return self.masters[job_id]

    async def create_clone(self, master_mapping: str, station_id: UUID) -> str:
        self.create_clone_calls += 1
        if station_id in self.fail_clone_for:
            raise RuntimeError("injected clone failure")
        job_id = UUID(master_mapping.split(":", maxsplit=1)[1])
        key = (job_id, station_id)
        if key not in self.clones:
            self.clones[key] = f"clone:{job_id}:{station_id}"
        return self.clones[key]

    async def read_mapping(self, station_id: UUID) -> str | None:
        return self.mappings.get(station_id, f"old:{station_id}")

    async def switch_mapping(self, station_id: UUID, clone_mapping: str) -> None:
        if station_id in self.fail_switch_for:
            raise RuntimeError("injected switch failure")
        self.mappings[station_id] = clone_mapping
        if station_id in self.unknown_switch_for:
            self.unknown_switch_for.remove(station_id)
            raise UnknownStorageOutcome("switch request outcome is unknown")

    async def verify_mapping(self, station_id: UUID, clone_mapping: str) -> bool:
        if station_id in self.fail_verify_for:
            return False
        return self.mappings.get(station_id) == clone_mapping
