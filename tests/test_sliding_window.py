import threading
import unittest

from tiny_ratelimit import ConfigurationError, SlidingWindowRateLimiter


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class SlidingWindowRateLimiterTests(unittest.TestCase):
    def test_allows_requests_up_to_limit(self):
        limiter = SlidingWindowRateLimiter(2, 10)
        self.assertTrue(limiter.check("client-a").allowed)
        self.assertTrue(limiter.check("client-a").allowed)
        self.assertFalse(limiter.check("client-a").allowed)

    def test_expires_requests_individually(self):
        clock = FakeClock()
        limiter = SlidingWindowRateLimiter(2, 10, clock=clock)
        self.assertTrue(limiter.check("client-a").allowed)
        clock.advance(5)
        self.assertTrue(limiter.check("client-a").allowed)
        clock.advance(5)
        self.assertTrue(limiter.check("client-a").allowed)

    def test_returns_retry_after_for_rejected_request(self):
        clock = FakeClock()
        limiter = SlidingWindowRateLimiter(1, 10, clock=clock)
        self.assertTrue(limiter.check("client-a").allowed)
        clock.advance(3)
        result = limiter.check("client-a")
        self.assertFalse(result.allowed)
        self.assertAlmostEqual(result.retry_after, 7)

    def test_clients_have_independent_limits(self):
        limiter = SlidingWindowRateLimiter(1, 10)
        self.assertTrue(limiter.check("client-a").allowed)
        self.assertTrue(limiter.check("client-b").allowed)
        self.assertFalse(limiter.check("client-a").allowed)

    def test_cleanup_removes_expired_client_history(self):
        clock = FakeClock()
        limiter = SlidingWindowRateLimiter(1, 10, clock=clock)
        limiter.check("client-a")
        clock.advance(10)
        self.assertEqual(limiter.cleanup(), 1)
        self.assertEqual(limiter.cleanup(), 0)

    def test_rejects_invalid_configuration(self):
        for limit in [0, -1, True, 1.5]:
            with self.subTest(limit=limit):
                with self.assertRaises(ConfigurationError):
                    SlidingWindowRateLimiter(limit, 10)
        for window in [0, -1, True, float("inf"), float("nan")]:
            with self.subTest(window=window):
                with self.assertRaises(ConfigurationError):
                    SlidingWindowRateLimiter(5, window)

    def test_concurrent_requests_do_not_exceed_limit(self):
        limit = 5
        workers = 20
        limiter = SlidingWindowRateLimiter(limit, 60)
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

        self.assertEqual(sum(results), limit)
        self.assertEqual(len(results), workers)

    def test_clock_rollback_does_not_expire_requests(self):
        clock = FakeClock()
        limiter = SlidingWindowRateLimiter(1, 10, clock=clock)
        self.assertTrue(limiter.check("client-a").allowed)
        clock.now = 90.0
        result = limiter.check("client-a")
        self.assertFalse(result.allowed)
        self.assertAlmostEqual(result.retry_after, 20.0)


if __name__ == "__main__":
    unittest.main()
