from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RateLimitResult:
    """Outcome of a rate-limit check."""

    allowed: bool
    limit: int
    remaining: int
    retry_after: Optional[float] = None
    reset_after: Optional[float] = None
