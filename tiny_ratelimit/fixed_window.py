import math
import threading
import time
from numbers import Real
from typing import Callable, Dict, Hashable, Optional, Tuple

from .exceptions import ConfigurationError
from .result import RateLimitResult


class FixedWindowRateLimiter:
    """Thread-safe, in-memory fixed-window rate limiter."""

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
        self._windows: Dict[Hashable, Tuple[float, int]] = {}

    def cleanup(self) -> int:
        """Remove expired client windows and return the number removed."""
        now = self._clock()
        with self._lock:
            expired = [key for key, (window_start, _) in self._windows.items() if now >= window_start + self.window_seconds]
            for key in expired:
                del self._windows[key]
        return len(expired)

    def check(self, key: Hashable) -> RateLimitResult:
        """Check and record one request for the given client key."""
        now = self._clock()

        with self._lock:
            window = self._windows.get(key)

            if window is None or now - window[0] >= self.window_seconds:
                window_start = now
                request_count = 0
            else:
                window_start, request_count = window

            reset_after = max(0.0, window_start + self.window_seconds - now)

            if request_count < self.limit:
                request_count += 1
                self._windows[key] = (window_start, request_count)
                return RateLimitResult(
                    allowed=True,
                    limit=self.limit,
                    remaining=self.limit - request_count,
                    reset_after=reset_after,
                )

            return RateLimitResult(
                allowed=False,
                limit=self.limit,
                remaining=0,
                retry_after=reset_after,
                reset_after=reset_after,
            )
