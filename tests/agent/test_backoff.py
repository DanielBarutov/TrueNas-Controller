import pytest

from agent.backoff import BackoffPolicy


def test_backoff_is_exponential_bounded_and_deterministic_at_midpoint() -> None:
    policy = BackoffPolicy(base_delay_seconds=1, max_delay_seconds=3, jitter_ratio=0.2)

    assert policy.delay(0, 0.5) == 1
    assert policy.delay(1, 0.5) == 2
    assert policy.delay(2, 0.5) == 3
    assert policy.delay(8, 1) == 3


def test_backoff_rejects_invalid_policy_or_random_value() -> None:
    with pytest.raises(ValueError):
        BackoffPolicy(base_delay_seconds=0)
    with pytest.raises(ValueError):
        BackoffPolicy(jitter_ratio=2)
    with pytest.raises(ValueError):
        BackoffPolicy().delay(0, 2)
