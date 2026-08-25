import pytest

from worker.runtime import WorkerRuntimeConfig, WorkerRuntimeConfigError, _configure_broker


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
    assert config.dataset_cleanup_enabled is False
    assert config.dataset_cleanup_interval_seconds == 604800
    assert config.dataset_cleanup_retention_days == 30
    assert config.dataset_cleanup_batch_size == 10
    assert config.truenas_cleanup_apply_enabled is False


def test_embedded_broker_does_not_enable_uninitialized_prometheus_middleware() -> None:
    broker = _configure_broker("redis://redis:6379/0")

    assert "Prometheus" not in {type(middleware).__name__ for middleware in broker.middleware}


@pytest.mark.parametrize(
    "environment, message",
    [
        ({"REDIS_URL": "redis://redis:6379/0"}, "DATABASE_URL"),
        ({"DATABASE_URL": "postgresql://db"}, "REDIS_URL"),
        (
            {
                "DATABASE_URL": "postgresql://db",
                "REDIS_URL": "redis://redis:6379/0",
                "PUBLISH_EXECUTOR_MODE": "unsupported",
            },
            "PUBLISH_EXECUTOR_MODE",
        ),
    ],
)
def test_runtime_config_fails_closed(environment: dict[str, str], message: str) -> None:
    with pytest.raises(WorkerRuntimeConfigError, match=message):
        WorkerRuntimeConfig.from_env(environment)


def test_truenas_runtime_requires_connection_and_explicit_apply_gate() -> None:
    with pytest.raises(WorkerRuntimeConfigError, match="TrueNAS"):
        WorkerRuntimeConfig.from_env(
            {
                "DATABASE_URL": "postgresql://db",
                "REDIS_URL": "redis://redis:6379/0",
                "PUBLISH_EXECUTOR_MODE": "truenas",
            }
        )


def test_truenas_runtime_accepts_explicit_apply_configuration() -> None:
    config = WorkerRuntimeConfig.from_env(
        {
            "DATABASE_URL": "postgresql://db",
            "REDIS_URL": "redis://redis:6379/0",
            "PUBLISH_EXECUTOR_MODE": "truenas",
            "TRUENAS_VERSION": "25.10.5",
            "TRUENAS_WS_URL": "wss://nas.example/api/current",
            "TRUENAS_API_KEY": "test-only-key",
            "TRUENAS_APPLY_ENABLED": "true",
        }
    )

    assert config.executor_mode == "truenas"


def test_runtime_config_accepts_weekly_cleanup_schedule_without_apply() -> None:
    config = WorkerRuntimeConfig.from_env(
        {
            "DATABASE_URL": "postgresql://db",
            "REDIS_URL": "redis://redis:6379/0",
            "DATASET_CLEANUP_ENABLED": "true",
            "DATASET_CLEANUP_INTERVAL_SECONDS": "3600",
            "DATASET_CLEANUP_RETENTION_DAYS": "14",
            "DATASET_CLEANUP_BATCH_SIZE": "4",
        }
    )

    assert config.dataset_cleanup_enabled is True
    assert config.dataset_cleanup_interval_seconds == 3600
    assert config.dataset_cleanup_retention_days == 14
    assert config.dataset_cleanup_batch_size == 4


def test_runtime_config_does_not_allow_cleanup_apply_in_fake_mode() -> None:
    with pytest.raises(WorkerRuntimeConfigError, match="PUBLISH_EXECUTOR_MODE"):
        WorkerRuntimeConfig.from_env(
            {
                "DATABASE_URL": "postgresql://db",
                "REDIS_URL": "redis://redis:6379/0",
                "TRUENAS_CLEANUP_APPLY_ENABLED": "true",
            }
        )
