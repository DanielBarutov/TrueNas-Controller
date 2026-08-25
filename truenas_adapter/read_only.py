"""Read-only TrueNAS adapter and strict fixture-to-DTO mappers."""

from collections.abc import Mapping, Sequence

from application.ports import TrueNASJsonRpcTransport, TrueNASReadOnlyClient
from application.truenas import (
    TrueNASDataset,
    TrueNASExtent,
    TrueNASSnapshot,
    TrueNASTarget,
    TrueNASTargetExtent,
)
from truenas_adapter.registry import TrueNASMethodRegistry


class TrueNASAdapterError(ValueError):
    """Remote data could not be mapped to a safe application DTO."""


class TrueNASReadOnlyAdapter(TrueNASReadOnlyClient):
    """Translate verified JSON-RPC read methods into application DTOs."""

    def __init__(self, transport: TrueNASJsonRpcTransport, registry: TrueNASMethodRegistry) -> None:
        self._transport = transport
        self._registry = registry

    async def ping(self) -> None:
        result = await self._transport.request(self._registry.resolve("ping"))
        if result is not True and result != "pong":
            raise TrueNASAdapterError("TrueNAS ping returned an unexpected result")

    async def query_datasets(self) -> tuple[TrueNASDataset, ...]:
        records = await self._query("query_datasets")
        return tuple(self._map_dataset(record) for record in records)

    async def query_snapshots(self) -> tuple[TrueNASSnapshot, ...]:
        records = await self._query("query_snapshots")
        return tuple(self._map_snapshot(record) for record in records)

    async def query_targets(self) -> tuple[TrueNASTarget, ...]:
        records = await self._query("query_targets")
        return tuple(self._map_target(record) for record in records)

    async def query_extents(self) -> tuple[TrueNASExtent, ...]:
        records = await self._query("query_extents")
        return tuple(self._map_extent(record) for record in records)

    async def query_target_extents(self) -> tuple[TrueNASTargetExtent, ...]:
        records = await self._query("query_target_extents")
        return tuple(self._map_target_extent(record) for record in records)

    async def close(self) -> None:
        """Close the injected transport without exposing infrastructure details."""

        await self._transport.close()

    async def _query(self, operation: str) -> tuple[Mapping[str, object], ...]:
        result = await self._transport.request(self._registry.resolve(operation), [])
        if not isinstance(result, Sequence) or isinstance(result, (str, bytes)):
            raise TrueNASAdapterError(f"TrueNAS {operation} result is not a list")
        records: list[Mapping[str, object]] = []
        for record in result:
            if not isinstance(record, Mapping):
                raise TrueNASAdapterError(f"TrueNAS {operation} contains a malformed record")
            records.append(record)
        return tuple(records)

    @staticmethod
    def _map_dataset(record: Mapping[str, object]) -> TrueNASDataset:
        return TrueNASDataset(
            id=_required_text(record, "id"),
            name=_required_text(record, "name"),
            path=_optional_text(record, "path"),
            dataset_type=_optional_text(record, "type"),
        )

    @staticmethod
    def _map_snapshot(record: Mapping[str, object]) -> TrueNASSnapshot:
        return TrueNASSnapshot(
            id=_required_text(record, "id"),
            name=_required_text(record, "name"),
            dataset=_required_text(record, "dataset"),
        )

    @staticmethod
    def _map_target(record: Mapping[str, object]) -> TrueNASTarget:
        return TrueNASTarget(
            id=_required_int(record, "id"),
            name=_required_text(record, "name"),
            alias=_optional_text(record, "alias"),
        )

    @staticmethod
    def _map_extent(record: Mapping[str, object]) -> TrueNASExtent:
        extent_type = _optional_text(record, "type")
        if extent_type == "FILE":
            backing_path = _optional_text(record, "path") or _optional_text(record, "disk")
        else:
            # DISK/ZVOL extents use ``disk``. ``path`` is the file-backed
            # field and must not win when both keys are present.
            backing_path = _optional_text(record, "disk") or _optional_text(record, "path")
        return TrueNASExtent(
            id=_required_int(record, "id"),
            name=_required_text(record, "name"),
            path=_canonical_disk_path(backing_path, extent_type),
            extent_type=extent_type,
        )

    @staticmethod
    def _map_target_extent(record: Mapping[str, object]) -> TrueNASTargetExtent:
        return TrueNASTargetExtent(
            target_id=_required_int(record, "target", "target_id"),
            extent_id=_required_int(record, "extent", "extent_id"),
            lun_id=_required_int(record, "lunid", "lun_id"),
        )


def _required_text(record: Mapping[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise TrueNASAdapterError(f"TrueNAS field {key!r} must be a non-empty string")
    return value


def _optional_text(record: Mapping[str, object], key: str) -> str | None:
    value = record.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TrueNASAdapterError(f"TrueNAS field {key!r} must be a string or null")
    return value


def _canonical_disk_path(value: str | None, extent_type: str | None) -> str | None:
    """Use the API's ``disk`` value, not the host's ``/dev`` path."""

    if value is None or extent_type == "FILE":
        return value
    if value.startswith("/dev/"):
        return value.removeprefix("/dev/")
    return value


def _required_int(record: Mapping[str, object], *keys: str) -> int:
    for key in keys:
        value = record.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    joined_keys = ", ".join(keys)
    raise TrueNASAdapterError(f"TrueNAS field {joined_keys} must be an integer")
