import pytest

from truenas_adapter.registry import (
    TrueNASMethodRegistry,
    UnsupportedTrueNASOperation,
    UnsupportedTrueNASVersion,
)


def test_registry_resolves_only_verified_read_methods() -> None:
    registry = TrueNASMethodRegistry("25.10.5")

    assert registry.resolve("authenticate") == "auth.login_with_api_key"
    assert registry.resolve("ping") == "core.ping"
    assert registry.resolve("query_datasets") == "pool.dataset.query"
    assert registry.resolve("query_target_extents") == "iscsi.targetextent.query"
    assert not any(
        forbidden in method
        for method in registry.methods.values()
        for forbidden in ("create", "delete", "destroy", "update", "switch", "clone")
    )


def test_registry_rejects_unsupported_version_and_write_operation() -> None:
    with pytest.raises(UnsupportedTrueNASVersion):
        TrueNASMethodRegistry("24.10")

    registry = TrueNASMethodRegistry("25.10")
    with pytest.raises(UnsupportedTrueNASOperation):
        registry.resolve("pool.snapshot.create")


def test_write_enabled_registry_resolves_only_approved_storage_writes() -> None:
    registry = TrueNASMethodRegistry("25.10.5", allow_writes=True)

    assert registry.resolve("create_snapshot") == "pool.snapshot.create"
    assert registry.resolve("clone_snapshot") == "pool.snapshot.clone"
    assert registry.resolve("update_extent_device") == "iscsi.extent.update"
    with pytest.raises(UnsupportedTrueNASOperation):
        registry.resolve("iscsi.extent.delete")
