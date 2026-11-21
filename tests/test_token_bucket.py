import threading
import unittest

from tiny_ratelimit import ConfigurationError, TokenBucketRateLimiter


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TokenBucketRateLimiterTests(unittest.TestCase):
    def test_allows_requests_up_to_capacity(self):
        limiter = TokenBucketRateLimiter(capacity=2, refill_rate=1)

        self.assertTrue(limiter.check("client-a").allowed)
        result = limiter.check("client-a")

        self.assertTrue(result.allowed)
        self.assertEqual(result.remaining, 0)

    def test_rejects_when_bucket_is_empty(self):
        limiter = TokenBucketRateLimiter(capacity=1, refill_rate=0.5)

        limiter.check("client-a")
        result = limiter.check("client-a")

        self.assertFalse(result.allowed)
        self.assertEqual(result.remaining, 0)
        self.assertAlmostEqual(result.retry_after, 2.0, places=3)

    def test_clock_rollback_does_not_create_tokens(self):
        clock = FakeClock()
        limiter = TokenBucketRateLimiter(2, 1, clock=clock)
        self.assertTrue(limiter.check("client-a", cost=2).allowed)
        clock.now = 90.0
        result = limiter.check("client-a")
        self.assertFalse(result.allowed)
        self.assertAlmostEqual(result.retry_after, 1.0)

    def test_refills_tokens_over_time(self):
        clock = FakeClock()
        limiter = TokenBucketRateLimiter(2, 1, clock=clock)

        limiter.check("client-a")
        limiter.check("client-a")
        self.assertFalse(limiter.check("client-a").allowed)

        clock.advance(1)

        result = limiter.check("client-a")
        self.assertTrue(result.allowed)
        self.assertEqual(result.remaining, 0)

    def test_supports_fractional_request_cost(self):
        limiter = TokenBucketRateLimiter(3, 1)

        result = limiter.check("client-a", cost=1.5)

        self.assertTrue(result.allowed)
        self.assertEqual(result.remaining, 1)

    def test_clients_have_independent_buckets(self):
        limiter = TokenBucketRateLimiter(1, 1)

        self.assertTrue(limiter.check("client-a").allowed)
        self.assertTrue(limiter.check("client-b").allowed)
        self.assertFalse(limiter.check("client-a").allowed)

    def test_cleanup_removes_only_fully_replenished_buckets(self):
        clock = FakeClock()
        limiter = TokenBucketRateLimiter(5, 1, clock=clock)
        limiter.check("client-a", cost=3)
        limiter.check("client-b", cost=1)
        clock.advance(1.5)
        self.assertEqual(limiter.cleanup(), 1)
        result = limiter.check("client-a", cost=4)
        self.assertFalse(result.allowed)
        self.assertAlmostEqual(result.retry_after, 0.5)
        clock.advance(2)
        self.assertEqual(limiter.cleanup(), 1)
        self.assertEqual(limiter.cleanup(), 0)

    def test_rejects_invalid_configuration_and_cost(self):
        for capacity in [0, -1, True, 1.5]:
            with self.subTest(capacity=capacity):
                with self.assertRaises(ConfigurationError):
                    TokenBucketRateLimiter(capacity, 1)

        for refill_rate in [0, -1, float("inf"), float("nan"), True]:
            with self.subTest(refill_rate=refill_rate):
                with self.assertRaises(ConfigurationError):
                    TokenBucketRateLimiter(5, refill_rate)

        limiter = TokenBucketRateLimiter(5, 1)
        for cost in [0, -1, True, float("inf"), float("nan"), 6]:
            with self.subTest(cost=cost):
                with self.assertRaises(ConfigurationError):
                    limiter.check("client-a", cost=cost)

    def test_concurrent_requests_do_not_exceed_capacity(self):
        capacity = 10
        workers = 50
        limiter = TokenBucketRateLimiter(capacity, 1)
        barrier = threading.Barrier(workers)
        results = []
        results_lock = threading.Lock()

        def make_request():
            barrier.wait()
            result = limiter.check("shared-client")
            with results_lock:
                results.append(result.allowed)

        threads = [
            threading.Thread(target=make_request)
            for _ in range(workers)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        self.assertEqual(sum(results), capacity)
        self.assertEqual(len(results), workers)


if __name__ == "__main__":
    unittest.main()
