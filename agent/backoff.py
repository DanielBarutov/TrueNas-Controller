"""Bounded exponential backoff with injectable jitter for agent retries."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BackoffPolicy:
    """Retry timing policy that never grows beyond ``max_delay_seconds``."""

    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    jitter_ratio: float = 0.2
    max_attempts: int = 3

    def __post_init__(self) -> None:
        if self.base_delay_seconds <= 0:
            raise ValueError("base_delay_seconds must be positive")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds must not be below base delay")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between zero and one")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")

    def delay(self, attempt: int, random_value: float = 0.5) -> float:
        """Return one bounded delay; ``random_value`` must be in [0, 1]."""

        if attempt < 0:
            raise ValueError("attempt cannot be negative")
        if not 0 <= random_value <= 1:
            raise ValueError("random_value must be between zero and one")
        exponential = min(self.max_delay_seconds, self.base_delay_seconds * 2**attempt)
        jitter = (random_value * 2 - 1) * self.jitter_ratio
        return min(self.max_delay_seconds, max(0.0, exponential * (1 + jitter)))
