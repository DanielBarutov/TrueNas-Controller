import os

import pytest

from truenas_adapter.runtime import TrueNASRuntimeConfig, build_read_only_client

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_TRUENAS_SMOKE") != "1",
    reason="set RUN_TRUENAS_SMOKE=1 to opt into the external read-only smoke check",
)
async def test_truenas_read_only_smoke() -> None:
    """Run only with an operator-supplied wss URL and API key in the environment."""

    config = TrueNASRuntimeConfig.from_env()
    client = build_read_only_client(config)
    try:
        await client.ping()
        await client.query_datasets()
        await client.query_snapshots()
        await client.query_targets()
        await client.query_extents()
        await client.query_target_extents()
    finally:
        await client.close()
