from tiny_ratelimit import (
    FixedWindowRateLimiter,
    SlidingWindowRateLimiter,
    TokenBucketRateLimiter,
)


def fixed_window_example():
    print("Fixed-window example")
    limiter = FixedWindowRateLimiter(limit=3, window_seconds=60)

    for request_number in range(1, 5):
        result = limiter.check("user-123")
        print(
            "Request {}: allowed={}, remaining={}".format(
                request_number,
                result.allowed,
                result.remaining,
            )
        )


def sliding_window_example():
    print()
    print("Sliding-window example")
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10)

    for request_number in range(1, 4):
        result = limiter.check("user-123")
        print(
            "Request {}: allowed={}, remaining={}, retry_after={}".format(
                request_number,
                result.allowed,
                result.remaining,
                result.retry_after,
            )
        )


def token_bucket_example():
    print()
    print("Token-bucket example")
    limiter = TokenBucketRateLimiter(capacity=5, refill_rate=1)

    result = limiter.check("user-123", cost=2)
    print(
        "Allowed={}, remaining={}, retry_after={}".format(
            result.allowed,
            result.remaining,
            result.retry_after,
        )
    )


if __name__ == "__main__":
    fixed_window_example()
    sliding_window_example()
    token_bucket_example()
