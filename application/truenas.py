"""Application DTOs for safe, read-only TrueNAS metadata."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrueNASDataset:
    """Dataset or zvol metadata without credentials or writable handles."""

    id: str
    name: str
    path: str | None
    dataset_type: str | None


@dataclass(frozen=True, slots=True)
class TrueNASSnapshot:
    """Snapshot identity used for later staging decisions."""

    id: str
    name: str
    dataset: str


@dataclass(frozen=True, slots=True)
class TrueNASTarget:
    """iSCSI target metadata exposed to application code."""

    id: int
    name: str
    alias: str | None


@dataclass(frozen=True, slots=True)
class TrueNASExtent:
    """iSCSI extent metadata, including its non-secret backing path."""

    id: int
    name: str
    path: str | None
    extent_type: str | None


@dataclass(frozen=True, slots=True)
class TrueNASTargetExtent:
    """Read-only relationship between an iSCSI target and extent."""

    target_id: int
    extent_id: int
    lun_id: int
