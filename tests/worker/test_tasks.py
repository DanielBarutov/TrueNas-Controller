from uuid import uuid4

import pytest

from worker.tasks import PublishTaskPayload, build_publish_actor


def test_task_payload_contains_only_ids_and_idempotency() -> None:
    job_id = uuid4()
    correlation_id = uuid4()
    calls: list[PublishTaskPayload] = []
    factory_calls = 0

    def factory():
        nonlocal factory_calls
        factory_calls += 1

        def handler(payload: PublishTaskPayload) -> None:
            calls.append(payload)

        return handler

    actor = build_publish_actor(factory)
    actor.fn(str(job_id), str(correlation_id), "idempotency-key")

    assert factory_calls == 1
    assert calls == [PublishTaskPayload(job_id, correlation_id, "idempotency-key")]


def test_invalid_task_payload_fails_before_handler() -> None:
    called = False

    def handler_factory():
        def handler(payload: PublishTaskPayload) -> None:
            nonlocal called
            called = True

        return handler

    actor = build_publish_actor(handler_factory, actor_name=f"publish_job_{uuid4().hex}")
    with pytest.raises(ValueError):
        actor.fn("not-a-uuid", str(uuid4()), "idempotency-key")

    assert called is False
