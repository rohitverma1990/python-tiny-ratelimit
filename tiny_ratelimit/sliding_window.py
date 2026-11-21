import math
import threading
import time
from collections import deque
from numbers import Real
from typing import Callable, Deque, Dict, Hashable, Optional

from .exceptions import ConfigurationError
from .result import RateLimitResult


class SlidingWindowRateLimiter:
    """Thread-safe, in-memory sliding-window rate limiter."""

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ConfigurationError("limit must be a positive integer")

        if (
            isinstance(window_seconds, bool)
            or not isinstance(window_seconds, Real)
            or not math.isfinite(window_seconds)
            or window_seconds <= 0
        ):
            raise ConfigurationError("window_seconds must be a positive finite number")

        self.limit = limit
        self.window_seconds = float(window_seconds)
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._requests: Dict[Hashable, Deque[float]] = {}

    def _remove_expired(self, timestamps: Deque[float], now: float) -> None:
        """Remove timestamps outside the active sliding window."""
        while timestamps and now - timestamps[0] >= self.window_seconds:
            timestamps.popleft()

    def cleanup(self) -> int:
        """Remove clients with no requests in the active window."""
        now = self._clock()
        with self._lock:
            expired_clients = []
            for key, timestamps in self._requests.items():
                self._remove_expired(timestamps, now)
                if not timestamps:
                    expired_clients.append(key)

            for key in expired_clients:
                del self._requests[key]

        return len(expired_clients)

    def check(self, key: Hashable) -> RateLimitResult:
        """Check and record one request for the given client key."""
        now = self._clock()

        with self._lock:
            timestamps = self._requests.setdefault(key, deque())
            self._remove_expired(timestamps, now)

            reset_after = (
                max(0.0, timestamps[0] + self.window_seconds - now)
                if timestamps
                else self.window_seconds
            )

            if len(timestamps) >= self.limit:
                return RateLimitResult(
                    allowed=False,
                    limit=self.limit,
                    remaining=0,
                    retry_after=reset_after,
                    reset_after=reset_after,
                )

            timestamps.append(now)
            return RateLimitResult(
                allowed=True,
                limit=self.limit,
                remaining=self.limit - len(timestamps),
                reset_after=reset_after,
            )
