class RateLimitError(Exception):
    """Base exception for rate-limiting errors."""


class ConfigurationError(RateLimitError, ValueError):
    """Raised when rate-limiter configuration is invalid."""
