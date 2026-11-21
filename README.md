# Tiny RateLimit

A lightweight, thread-safe Python library for in-memory API rate limiting. It provides fixed-window, sliding-window log, and token-bucket algorithms without third-party runtime dependencies.

## Features

- Fixed-window rate limiting with configurable request limits and time windows.
- Sliding-window log rate limiting with per-request expiration.

- Token-bucket rate limiting with configurable capacity and refill rate.
- Independent request tracking for each client key.
- Thread-safe request evaluation.
- Injectable clocks for deterministic testing.
- Structured results with remaining capacity, reset time, and retry information.
- Python 3.9+ support.
- No third-party runtime dependencies.

## Algorithms

### Fixed window

Allows a configured number of requests per client during a fixed time window. The window starts when that client's first request is received. Once the window expires, the request count resets.

### Sliding-window log

Tracks the timestamp of each accepted request for every client. Before evaluating a new request, timestamps outside the configured rolling time window are removed. A request is accepted only when fewer than the configured limit remain in that window. Rejected requests include a retry_after value indicating when the oldest active request expires and capacity becomes available.

This approach provides a precise rolling-window limit, at the cost of storing individual request timestamps while they remain active.

### Token bucket

Each client has a bucket that starts full. Tokens are replenished continuously at the configured refill rate, up to the bucket capacity. Requests consume tokens and can specify a cost.

## Requirements

- Python 3.9 or newer.

## Installation

Clone the repository:

    git clone https://github.com/rohitverma1990/python-tiny-ratelimit.git
    cd python-tiny-ratelimit

The project has no third-party runtime dependencies. To run the example from the repository root:

    PYTHONPATH=. python3 examples/basic_usage.py

For local package installation, use a modern pip and build tooling compatible with the pyproject.toml configuration.

## Usage

### Fixed-window limiter

    from tiny_ratelimit import FixedWindowRateLimiter

    limiter = FixedWindowRateLimiter(limit=100, window_seconds=60)
    result = limiter.check("user-123")

    if result.allowed:
        print("Request allowed")
    else:
        print("Rate limit exceeded. Retry after:", result.retry_after)

This example allows up to 100 requests per client in each 60-second window.

### Sliding-window limiter

    from tiny_ratelimit import SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter(limit=100, window_seconds=60)

    result = limiter.check("user-123")

    if result.allowed:
        print("Request allowed")
    else:
        print("Rate limit exceeded. Retry after:", result.retry_after)

This example allows up to 100 requests for each client in any rolling 60-second period. Unlike a fixed window, the window moves forward with time and each accepted request expires individually.

### Token-bucket limiter

    from tiny_ratelimit import TokenBucketRateLimiter

    limiter = TokenBucketRateLimiter(capacity=10, refill_rate=2)
    result = limiter.check("user-123", cost=1)

    if result.allowed:
        print("Request allowed")
    else:
        print("Rate limit exceeded. Retry after:", result.retry_after)

This bucket holds up to 10 tokens and refills at 2 tokens per second. A request consumes one token by default. The optional cost argument allows a request to consume more than one token.

## Result fields

All three algorithms return an immutable RateLimitResult object:

| Field | Description |
|---|---|
| allowed | Whether the request was accepted. |
| limit | Configured request limit or bucket capacity. |
| remaining | Remaining whole requests or tokens. |
| retry_after | Seconds to wait before a rejected request can be retried; None for accepted requests. |
| reset_after | For fixed windows, seconds until the current window expires. For sliding windows, seconds until the oldest active request expires. For token buckets, seconds until the bucket is completely full. |

For token buckets, remaining is the number of whole tokens, rounded down. Fractional token balances are supported internally.

## Thread safety and limitations

- Operations within each limiter instance are protected by a thread lock.
- Client state is stored in memory and is local to the process.
- State is not shared between multiple application processes or machines.
- Client state is retained in memory until it expires or is removed by cleanup. Applications with many active client keys should schedule cleanup as appropriate.
- These limiters provide request evaluation, not a web-framework integration or distributed rate-limiting service.

## Client-state cleanup

All three limiter classes provide a `cleanup()` method that removes eligible client entries and returns the number of entries removed.

For fixed-window limiters, cleanup removes windows that have expired.

For sliding-window limiters, cleanup removes clients with no requests remaining in the active window.

For token-bucket limiters, cleanup removes buckets that have naturally refilled to their full capacity. Partially depleted buckets are preserved so cleanup cannot grant clients additional tokens.

Cleanup is explicit: applications can call it periodically according to their workload and memory requirements. Cleanup operations are thread-safe.

Example:

    removed = limiter.cleanup()
    print("Removed client entries:", removed)

## Running tests

Run the standard-library test suite from the repository root:

    python3 -m unittest discover -s tests -v

The tests cover request limits, independent clients, time-based expiration, cleanup, clock rollback, invalid configuration, fractional token costs, and concurrent access.

## License

This project is licensed under the MIT License. See LICENSE.
