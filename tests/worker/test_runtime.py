import pytest

from worker.runtime import WorkerRuntimeConfig, WorkerRuntimeConfigError


def test_runtime_config_has_safe_local_fake_defaults() -> None:
    config = WorkerRuntimeConfig.from_env(
        {
            "DATABASE_URL": "postgresql+asyncpg://user:password@postgres/db",
            "REDIS_URL": "redis://redis:6379/0",
        }
    )

    assert config.executor_mode == "fake"
    assert config.poll_interval_seconds == 1
    assert config.worker_threads == 2


@pytest.mark.parametrize(
    "environment, message",
    [
        ({"REDIS_URL": "redis://redis:6379/0"}, "DATABASE_URL"),
        ({"DATABASE_URL": "postgresql://db"}, "REDIS_URL"),
        (
            {
                "DATABASE_URL": "postgresql://db",
                "REDIS_URL": "redis://redis:6379/0",
                "PUBLISH_EXECUTOR_MODE": "truenas",
            },
            "PUBLISH_EXECUTOR_MODE",
        ),
    ],
)
def test_runtime_config_fails_closed(environment: dict[str, str], message: str) -> None:
    with pytest.raises(WorkerRuntimeConfigError, match=message):
        WorkerRuntimeConfig.from_env(environment)
