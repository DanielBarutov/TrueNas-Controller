"""Production process for the outbox relay and Dramatiq publish worker.

The API only commits a publish job and an outbox event. This module is the
runtime that turns that durable event into a Dramatiq message and then runs
the currently supported deterministic fake executor for dry-run/local mode.
The TrueNAS write adapter is selected only by the explicit ``truenas`` mode and
its separate ``TRUENAS_APPLY_ENABLED`` gate.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
import os
import signal
import socket

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import default_middleware
from dramatiq.middleware.prometheus import Prometheus
from dramatiq.worker import Worker
from sqlalchemy.pool import NullPool

from application.publish_executor import FakePublishTaskExecutor, TrueNASPublishTaskExecutor
from repository.database import create_engine, create_session_factory
from repository.uow import SqlAlchemyUnitOfWorkFactory
from truenas_adapter.mock_client import FakePublishStorageAdapter
from truenas_adapter.runtime import (
    TrueNASRuntimeConfig,
    TrueNASRuntimeConfigError,
    build_read_only_client,
    build_write_client,
)
from worker.composition import PublishTaskApplicationHandler
from worker.outbox_relay import PublishOutboxRelay
from worker.tasks import DramatiqPublishTaskQueue, build_publish_actor

logger = logging.getLogger(__name__)


class WorkerRuntimeConfigError(ValueError):
    """Worker configuration is incomplete or unsupported."""


class WorkerRuntimeConfig:
    """Environment-backed settings for one worker process."""

    def __init__(
        self,
        *,
        database_url: str,
        redis_url: str,
        worker_id: str,
        poll_interval_seconds: float,
        worker_threads: int,
        executor_mode: str,
    ) -> None:
        self.database_url = database_url
        self.redis_url = redis_url
        self.worker_id = worker_id
        self.poll_interval_seconds = poll_interval_seconds
        self.worker_threads = worker_threads
        self.executor_mode = executor_mode

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> WorkerRuntimeConfig:
        source = os.environ if env is None else env
        database_url = source.get("DATABASE_URL", "").strip()
        redis_url = source.get("REDIS_URL", "").strip()
        if not database_url:
            raise WorkerRuntimeConfigError("DATABASE_URL is required for the worker")
        if not redis_url:
            raise WorkerRuntimeConfigError("REDIS_URL is required for the worker")

        worker_id = source.get("WORKER_ID", socket.gethostname()).strip()
        if not worker_id:
            raise WorkerRuntimeConfigError("WORKER_ID must not be blank")
        poll_interval_seconds = _positive_float(
            source.get("WORKER_POLL_INTERVAL_SECONDS", "1"),
            "WORKER_POLL_INTERVAL_SECONDS",
        )
        worker_threads = _positive_int(
            source.get("DRAMATIQ_WORKER_THREADS", "2"),
            "DRAMATIQ_WORKER_THREADS",
        )
        executor_mode = source.get("PUBLISH_EXECUTOR_MODE", "fake").strip().lower()
        if executor_mode not in {"fake", "truenas"}:
            raise WorkerRuntimeConfigError("PUBLISH_EXECUTOR_MODE must be 'fake' or 'truenas'")
        if executor_mode == "truenas":
            try:
                truenas_config = TrueNASRuntimeConfig.from_env(source)
            except TrueNASRuntimeConfigError as exc:
                raise WorkerRuntimeConfigError(f"invalid TrueNAS worker config: {exc}") from exc
            if not truenas_config.apply_enabled:
                raise WorkerRuntimeConfigError(
                    "TRUENAS_APPLY_ENABLED=true is required for PUBLISH_EXECUTOR_MODE=truenas"
                )
        return cls(
            database_url=database_url,
            redis_url=redis_url,
            worker_id=worker_id,
            poll_interval_seconds=poll_interval_seconds,
            worker_threads=worker_threads,
            executor_mode=executor_mode,
        )


class PublishWorkerRuntime:
    """Run the queue consumer and the database-backed outbox relay together."""

    def __init__(self, config: WorkerRuntimeConfig) -> None:
        self._config = config
        engine = create_engine(config.database_url, poolclass=NullPool)
        self._uow_factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
        self._truenas_config = (
            TrueNASRuntimeConfig.from_env() if config.executor_mode == "truenas" else None
        )

        broker = _configure_broker(config.redis_url)
        self._worker = Worker(broker, worker_threads=config.worker_threads)
        self._actor: dramatiq.Actor | None = None
        self._relay: PublishOutboxRelay | None = None

    def _handler_factory(self) -> PublishTaskApplicationHandler:
        if self._config.executor_mode == "fake":

            def executor_factory() -> FakePublishTaskExecutor:
                return FakePublishTaskExecutor(self._uow_factory, FakePublishStorageAdapter)
        else:
            if self._truenas_config is None:
                raise WorkerRuntimeConfigError("TrueNAS runtime config is not initialized")
            config = self._truenas_config

            def executor_factory() -> TrueNASPublishTaskExecutor:
                return TrueNASPublishTaskExecutor(
                    self._uow_factory,
                    lambda: build_read_only_client(config),
                    lambda: build_write_client(config),
                )

        return PublishTaskApplicationHandler(self._uow_factory, executor_factory)

    async def run(self) -> None:
        """Start Dramatiq and keep polling the durable outbox until shutdown."""

        stop_event = asyncio.Event()
        _install_signal_handlers(stop_event)
        self._worker.start()
        # The embedded worker installs its consumer middleware in start().
        # Declare the actor afterwards so after_declare_queue can attach the
        # consumer to the already-running worker.
        self._actor = build_publish_actor(self._handler_factory)
        self._relay = PublishOutboxRelay(
            self._uow_factory,
            DramatiqPublishTaskQueue(self._actor),
            worker_id=self._config.worker_id,
        )
        logger.info(
            "publish worker consumers attached: %s",
            sorted(self._worker.consumers),
        )
        logger.info(
            "publish worker started: worker_id=%s executor=%s poll_interval=%ss",
            self._config.worker_id,
            self._config.executor_mode,
            self._config.poll_interval_seconds,
        )
        try:
            while not stop_event.is_set():
                try:
                    result = await self._relay.run_once()
                    if result.claimed:
                        logger.info(
                            "outbox poll: claimed=%s dispatched=%s failed=%s",
                            result.claimed,
                            result.dispatched,
                            result.failed,
                        )
                except Exception:
                    logger.exception("outbox poll failed; retrying")
                await _wait_or_stop(stop_event, self._config.poll_interval_seconds)
        finally:
            logger.info("stopping publish worker")
            self._worker.stop()


def _configure_broker(redis_url: str) -> RedisBroker:
    # ``Worker.start`` is embedded in this process rather than launched by
    # Dramatiq's CLI. The built-in Prometheus middleware initializes its
    # counters in the CLI-only ``after_process_boot`` hook, so leaving it in
    # the embedded broker causes a second middleware failure after a task
    # completes. Keep the retry/age/shutdown middleware and omit only metrics.
    middleware = [
        middleware_type()
        for middleware_type in default_middleware
        if middleware_type is not Prometheus
    ]
    broker = RedisBroker(url=redis_url, middleware=middleware)
    dramatiq.set_broker(broker)
    return broker


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop_event.set)
        except NotImplementedError:
            logger.warning("signal handlers are unavailable for signal=%s", signum)


async def _wait_or_stop(stop_event: asyncio.Event, timeout: float) -> None:
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=timeout)
    except TimeoutError:
        return


def _positive_float(raw_value: str, name: str) -> float:
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise WorkerRuntimeConfigError(f"{name} must be a positive number") from exc
    if value <= 0:
        raise WorkerRuntimeConfigError(f"{name} must be a positive number")
    return value


def _positive_int(raw_value: str, name: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise WorkerRuntimeConfigError(f"{name} must be a positive integer") from exc
    if value < 1:
        raise WorkerRuntimeConfigError(f"{name} must be a positive integer")
    return value


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = WorkerRuntimeConfig.from_env()
    asyncio.run(PublishWorkerRuntime(config).run())


if __name__ == "__main__":
    main()
