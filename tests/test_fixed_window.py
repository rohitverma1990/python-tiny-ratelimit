import threading
import unittest

from tiny_ratelimit import ConfigurationError, FixedWindowRateLimiter


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FixedWindowRateLimiterTests(unittest.TestCase):
    def test_allows_requests_up_to_limit(self):
        limiter = FixedWindowRateLimiter(limit=2, window_seconds=10)

        first = limiter.check("client-a")
        second = limiter.check("client-a")

        self.assertTrue(first.allowed)
        self.assertEqual(first.remaining, 1)
        self.assertTrue(second.allowed)
        self.assertEqual(second.remaining, 0)

    def test_rejects_requests_after_limit(self):
        limiter = FixedWindowRateLimiter(limit=1, window_seconds=10)

        limiter.check("client-a")
        result = limiter.check("client-a")

        self.assertFalse(result.allowed)
        self.assertEqual(result.remaining, 0)
        self.assertAlmostEqual(result.retry_after, 10.0, places=3)

    def test_clock_rollback_does_not_reset_window(self):
        clock = FakeClock()
        limiter = FixedWindowRateLimiter(1, 10, clock=clock)
        self.assertTrue(limiter.check("client-a").allowed)
        clock.now = 90.0
        result = limiter.check("client-a")
        self.assertFalse(result.allowed)
        self.assertAlmostEqual(result.retry_after, 20.0)

    def test_resets_after_window_expires(self):
        clock = FakeClock()
        limiter = FixedWindowRateLimiter(1, 10, clock=clock)

        self.assertTrue(limiter.check("client-a").allowed)
        self.assertFalse(limiter.check("client-a").allowed)

        clock.advance(10)

        result = limiter.check("client-a")
        self.assertTrue(result.allowed)
        self.assertEqual(result.remaining, 0)

    def test_clients_have_independent_limits(self):
        limiter = FixedWindowRateLimiter(1, 10)

        self.assertTrue(limiter.check("client-a").allowed)
        self.assertTrue(limiter.check("client-b").allowed)
        self.assertFalse(limiter.check("client-a").allowed)

    def test_cleanup_removes_only_expired_windows(self):
        clock = FakeClock()
        limiter = FixedWindowRateLimiter(1, 10, clock=clock)
        self.assertEqual(limiter.cleanup(), 0)
        self.assertTrue(limiter.check("client-a").allowed)
        self.assertTrue(limiter.check("client-b").allowed)
        clock.advance(5)
        self.assertTrue(limiter.check("client-c").allowed)
        clock.advance(5)
        self.assertEqual(limiter.cleanup(), 2)
        self.assertFalse(limiter.check("client-c").allowed)
        self.assertTrue(limiter.check("client-a").allowed)
        self.assertEqual(limiter.cleanup(), 0)

    def test_rejects_invalid_configuration(self):
        invalid_values = [0, -1, True, 1.5]

        for limit in invalid_values:
            with self.subTest(limit=limit):
                with self.assertRaises(ConfigurationError):
                    FixedWindowRateLimiter(limit, 10)

        for window in [0, -1, float("inf"), float("nan"), True]:
            with self.subTest(window=window):
                with self.assertRaises(ConfigurationError):
                    FixedWindowRateLimiter(5, window)

    def test_concurrent_requests_do_not_exceed_limit(self):
        limit = 10
        workers = 50
        limiter = FixedWindowRateLimiter(limit, 60)
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


if __name__ == "__main__":
    unittest.main()
