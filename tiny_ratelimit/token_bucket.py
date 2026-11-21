import math
import threading
import time
from numbers import Real
from typing import Callable, Dict, Hashable, Optional, Tuple

from .exceptions import ConfigurationError
from .result import RateLimitResult


class TokenBucketRateLimiter:
    """Thread-safe, in-memory token-bucket rate limiter."""

    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
            raise ConfigurationError("capacity must be a positive integer")

        if (
            isinstance(refill_rate, bool)
            or not isinstance(refill_rate, Real)
            or not math.isfinite(refill_rate)
            or refill_rate <= 0
        ):
            raise ConfigurationError("refill_rate must be a positive finite number")

        self.capacity = capacity
        self.refill_rate = float(refill_rate)
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._buckets: Dict[Hashable, Tuple[float, float]] = {}

    def cleanup(self) -> int:
        """Remove fully replenished buckets and return the number removed."""
        now = self._clock()
        with self._lock:
            expired = []
            for key, (tokens, last_refill) in self._buckets.items():
                elapsed = max(0.0, now - last_refill)
                replenished = min(
                    float(self.capacity),
                    tokens + elapsed * self.refill_rate,
                )
                if replenished >= self.capacity:
                    expired.append(key)
            for key in expired:
                del self._buckets[key]
        return len(expired)

    def check(self, key: Hashable, cost: float = 1.0) -> RateLimitResult:
        """Consume tokens for a request, returning whether it was allowed."""
        if (
            isinstance(cost, bool)
            or not isinstance(cost, Real)
            or not math.isfinite(cost)
            or cost <= 0
            or cost > self.capacity
        ):
            raise ConfigurationError("cost must be positive and no greater than capacity")

        now = self._clock()

        with self._lock:
            bucket = self._buckets.get(key)

            if bucket is None:
                tokens = float(self.capacity)
                last_refill = now
            else:
                tokens, last_refill = bucket
                if now > last_refill:
                    elapsed = now - last_refill
                    tokens = min(
                        float(self.capacity),
                        tokens + elapsed * self.refill_rate,
                    )
                    last_refill = now

            if tokens >= cost:
                tokens -= cost
                self._buckets[key] = (tokens, last_refill)
                return RateLimitResult(
                    allowed=True,
                    limit=self.capacity,
                    remaining=math.floor(tokens),
                    reset_after=(self.capacity - tokens) / self.refill_rate,
                )

            retry_after = (cost - tokens) / self.refill_rate
            self._buckets[key] = (tokens, last_refill)
            return RateLimitResult(
                allowed=False,
                limit=self.capacity,
                remaining=math.floor(tokens),
                retry_after=retry_after,
                reset_after=(self.capacity - tokens) / self.refill_rate,
            )
