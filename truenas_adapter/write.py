"""Fail-closed TrueNAS write adapter for the approved snapshot workflow."""

from collections.abc import Mapping
import re

from application.ports import TrueNASJsonRpcTransport, TrueNASWriteClient
from application.truenas import TrueNASExtent, TrueNASSnapshot
from truenas_adapter.read_only import TrueNASAdapterError, TrueNASReadOnlyAdapter
from truenas_adapter.registry import TrueNASMethodRegistry

_DATASET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
_SNAPSHOT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class TrueNASWriteAdapter(TrueNASWriteClient):
    """Translate only snapshot, clone and existing-extent device updates."""

    def __init__(self, transport: TrueNASJsonRpcTransport, registry: TrueNASMethodRegistry) -> None:
        if not registry.allow_writes:
            raise ValueError("write adapter requires a write-enabled method registry")
        self._transport = transport
        self._registry = registry

    async def create_snapshot(self, dataset: str, snapshot_name: str) -> TrueNASSnapshot:
        _validate_dataset(dataset)
        _validate_snapshot_name(snapshot_name)
        result = await self._transport.request(
            self._registry.resolve("create_snapshot"),
            [{"dataset": dataset, "name": snapshot_name}],
        )
        record = _mapping_result(result, "snapshot create")
        dataset_value = record.get("dataset")
        if not isinstance(dataset_value, str) or not dataset_value:
            dataset_value = dataset
        return TrueNASSnapshot(
            id=_required_text(record, "id", "name"),
            name=_required_text(record, "name", "id"),
            dataset=dataset_value,
        )

    async def clone_snapshot(self, snapshot: str, dataset_dst: str) -> None:
        _validate_snapshot(snapshot)
        _validate_dataset(dataset_dst)
        result = await self._transport.request(
            self._registry.resolve("clone_snapshot"),
            [{"snapshot": snapshot, "dataset_dst": dataset_dst}],
        )
        if result is not True:
            raise TrueNASAdapterError("TrueNAS snapshot clone returned an unexpected result")

    async def update_extent_device(self, extent_id: int, device: str) -> TrueNASExtent:
        if extent_id <= 0:
            raise ValueError("extent_id must be positive")
        if not device.startswith("/dev/zvol/") or ".." in device.split("/"):
            raise ValueError("device must be a /dev/zvol path without traversal")
        result = await self._transport.request(
            self._registry.resolve("update_extent_device"),
            [extent_id, {"disk": device}],
        )
        record = _mapping_result(result, "extent update")
        return TrueNASReadOnlyAdapter._map_extent(record)

    async def close(self) -> None:
        await self._transport.close()


def _validate_dataset(value: str) -> None:
    if not value or not _DATASET_RE.fullmatch(value) or ".." in value.split("/"):
        raise ValueError("dataset must be a safe TrueNAS dataset name")


def _validate_snapshot_name(value: str) -> None:
    if not value or not _SNAPSHOT_RE.fullmatch(value):
        raise ValueError("snapshot name contains unsupported characters")


def _validate_snapshot(value: str) -> None:
    dataset, separator, name = value.partition("@")
    if not separator:
        raise ValueError("snapshot must use dataset@snapshot format")
    _validate_dataset(dataset)
    _validate_snapshot_name(name)


def _mapping_result(result: object, operation: str) -> Mapping[str, object]:
    if not isinstance(result, Mapping):
        raise TrueNASAdapterError(f"TrueNAS {operation} returned a malformed object")
    return result


def _required_text(record: Mapping[str, object], key: str, fallback: str | None = None) -> str:
    value = record.get(key)
    if isinstance(value, str) and value:
        return value
    if fallback is not None:
        fallback_value = record.get(fallback)
        if isinstance(fallback_value, str) and fallback_value:
            return fallback_value
    raise TrueNASAdapterError(f"TrueNAS field {key!r} must be a non-empty string")
