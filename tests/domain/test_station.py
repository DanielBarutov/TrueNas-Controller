from datetime import UTC, datetime
from uuid import uuid4

import pytest

from domain.station import Station, StationRole, StationStatus


def make_station(**overrides: object) -> Station:
    values: dict[str, object] = {
        "id": uuid4(),
        "station_id": uuid4(),
        "display_name": "Client 01",
        "hostname": "client-01",
        "role": StationRole.CLIENT,
    }
    values.update(overrides)
    return Station(**values)  # type: ignore[arg-type]


def test_available_station_requires_enabled_non_offline_state() -> None:
    assert make_station(status=StationStatus.ONLINE).is_available is True
    assert make_station(status=StationStatus.STALE).is_available is True
    assert make_station(status=StationStatus.OFFLINE).is_available is False


@pytest.mark.parametrize(
    ("field", "value"),
    [("display_name", "  "), ("hostname", "")],
)
def test_station_rejects_blank_identity_fields(field: str, value: str) -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        make_station(**{field: value})


def test_deleted_station_must_be_disabled() -> None:
    with pytest.raises(ValueError, match="deleted station"):
        make_station(deleted_at=datetime.now(UTC))


def test_disabled_status_requires_disabled_flag() -> None:
    with pytest.raises(ValueError, match="disabled status"):
        make_station(status=StationStatus.DISABLED)
