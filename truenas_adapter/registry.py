"""Versioned allow-list of read and explicitly enabled TrueNAS API methods."""

from types import MappingProxyType
from typing import ClassVar


class UnsupportedTrueNASVersion(ValueError):
    """The configured API family has no verified method registry."""


class UnsupportedTrueNASOperation(ValueError):
    """The requested operation is not part of the read-only allow-list."""


class TrueNASMethodRegistry:
    """Resolve application operations to methods verified for one API family."""

    _METHODS_BY_VERSION: ClassVar[dict[str, dict[str, str]]] = {
        "25.10": {
            "authenticate": "auth.login_with_api_key",
            "ping": "core.ping",
            "query_datasets": "pool.dataset.query",
            "query_snapshots": "pool.snapshot.query",
            "query_targets": "iscsi.target.query",
            "query_extents": "iscsi.extent.query",
            "query_target_extents": "iscsi.targetextent.query",
        }
    }

    def __init__(self, version: str, *, allow_writes: bool = False) -> None:
        normalized = version.strip()
        family = ".".join(normalized.split(".")[:2])
        if family not in self._METHODS_BY_VERSION:
            raise UnsupportedTrueNASVersion(f"unsupported TrueNAS API version: {version}")
        self.version = normalized
        methods = dict(self._METHODS_BY_VERSION[family])
        if allow_writes:
            methods.update(
                {
                    "create_snapshot": "pool.snapshot.create",
                    "clone_snapshot": "pool.snapshot.clone",
                    "update_extent_device": "iscsi.extent.update",
                }
            )
        self._methods = MappingProxyType(methods)
        self.allow_writes = allow_writes

    @property
    def methods(self) -> MappingProxyType[str, str]:
        """Return an immutable operation-to-method mapping for inspection/tests."""

        return self._methods

    def resolve(self, operation: str) -> str:
        """Resolve only an operation enabled for this registry instance."""

        try:
            return self._methods[operation]
        except KeyError as exc:
            raise UnsupportedTrueNASOperation(
                f"unsupported TrueNAS read-only operation: {operation}"
            ) from exc
