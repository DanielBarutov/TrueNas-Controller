"""Production process for the outbox relay and Dramatiq publish worker.

The API only commits a publish job and an outbox event. This module is the
runtime that turns that durable event into a Dramatiq message and then runs
the currently supported deterministic fake executor for dry-run/local mode.
The TrueNAS write adapter is intentionally not selected here until its apply
gate is implemented.
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
from dramatiq.worker import Worker

from application.publish_executor import FakePublishTaskExecutor
from repository.database import create_engine, create_session_factory
from repository.uow import SqlAlchemyUnitOfWorkFactory
from truenas_adapter.mock_client import FakePublishStorageAdapter
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
        if executor_mode != "fake":
            raise WorkerRuntimeConfigError(
                "PUBLISH_EXECUTOR_MODE must be 'fake' until the TrueNAS apply adapter is enabled"
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
        engine = create_engine(config.database_url)
        uow_factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))

        def handler_factory() -> PublishTaskApplicationHandler:
            return PublishTaskApplicationHandler(
                uow_factory,
                lambda: FakePublishTaskExecutor(
                    uow_factory,
                    FakePublishStorageAdapter,
                ),
            )

        broker = _configure_broker(config.redis_url)
        self._actor = build_publish_actor(handler_factory)
        self._worker = Worker(broker, worker_threads=config.worker_threads)
        self._relay = PublishOutboxRelay(
            uow_factory,
            DramatiqPublishTaskQueue(self._actor),
            worker_id=config.worker_id,
        )

    async def run(self) -> None:
        """Start Dramatiq and keep polling the durable outbox until shutdown."""

        stop_event = asyncio.Event()
        _install_signal_handlers(stop_event)
        self._worker.start()
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
    broker = RedisBroker(url=redis_url)
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
