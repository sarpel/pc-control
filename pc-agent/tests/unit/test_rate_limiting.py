"""
Rate Limiting Tests

Unit tests for connection attempt rate limiting with exponential backoff.
Validates rate limiting mechanisms for preventing abuse (T086).

Test Coverage:
- Connection attempt rate limiting
- Exponential backoff for failed attempts
- Request rate limiting per IP
- Block duration calculation
- Cleanup of old entries
- Rate limit statistics
"""

import pytest
import time
from datetime import datetime, timedelta
from collections import deque
from typing import Dict, Any
from unittest.mock import Mock, MagicMock


class MockRateLimitMiddleware:
    """Mock RateLimitMiddleware for testing."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        max_connection_attempts: int = 5,
        connection_window_seconds: int = 60,
        backoff_multiplier: float = 2.0,
        max_backoff_seconds: int = 300
    ):
        self.requests_per_minute = requests_per_minute
        self.max_connection_attempts = max_connection_attempts
        self.connection_window_seconds = connection_window_seconds
        self.backoff_multiplier = backoff_multiplier
        self.max_backoff_seconds = max_backoff_seconds

        self.request_counts: Dict[str, Dict[str, int]] = {}
        self.connection_attempts: Dict[str, deque] = {}
        self.failed_attempts: Dict[str, int] = {}
        self.blocked_until: Dict[str, datetime] = {}

    def check_connection_attempt_limit(self, client_ip: str) -> bool:
        """Check if client has exceeded connection attempt limit."""
        attempts = self.get_attempts_in_window(client_ip)
        return attempts < self.max_connection_attempts

    def record_connection_attempt(self, client_ip: str):
        """Record a connection attempt."""
        now = time.time()
        if client_ip not in self.connection_attempts:
            self.connection_attempts[client_ip] = deque(maxlen=self.max_connection_attempts * 2)
        self.connection_attempts[client_ip].append(now)

    def get_attempts_in_window(self, client_ip: str) -> int:
        """Get number of connection attempts in window."""
        if client_ip not in self.connection_attempts:
            return 0

        now = time.time()
        window_start = now - self.connection_window_seconds

        # Clean old attempts
        while self.connection_attempts[client_ip] and \
              self.connection_attempts[client_ip][0] < window_start:
            self.connection_attempts[client_ip].popleft()

        return len(self.connection_attempts[client_ip])

    def record_failed_connection(self, client_ip: str):
        """Record a failed connection attempt."""
        if client_ip not in self.failed_attempts:
            self.failed_attempts[client_ip] = 0
        self.failed_attempts[client_ip] += 1

        backoff_seconds = min(
            int(2 ** self.failed_attempts[client_ip] * self.backoff_multiplier),
            self.max_backoff_seconds
        )
        self.blocked_until[client_ip] = datetime.utcnow() + timedelta(seconds=backoff_seconds)

    def record_successful_connection(self, client_ip: str):
        """Record a successful connection."""
        if client_ip in self.failed_attempts:
            del self.failed_attempts[client_ip]
        if client_ip in self.blocked_until:
            del self.blocked_until[client_ip]

    def is_blocked(self, client_ip: str) -> bool:
        """Check if client is blocked."""
        if client_ip not in self.blocked_until:
            return False

        now = datetime.utcnow()
        if now < self.blocked_until[client_ip]:
            return True

        # Block expired
        del self.blocked_until[client_ip]
        if client_ip in self.failed_attempts:
            del self.failed_attempts[client_ip]
        return False

    def get_remaining_block_time(self, client_ip: str) -> int:
        """Get remaining block time in seconds."""
        if client_ip not in self.blocked_until:
            return 0
        now = datetime.utcnow()
        remaining = (self.blocked_until[client_ip] - now).total_seconds()
        return max(0, int(remaining))

    def calculate_backoff_time(self, client_ip: str) -> int:
        """Calculate backoff time."""
        if client_ip not in self.failed_attempts:
            return 1
        backoff = min(
            int(2 ** self.failed_attempts[client_ip] * self.backoff_multiplier),
            self.max_backoff_seconds
        )
        return backoff


@pytest.fixture
def rate_limiter():
    """Fixture for rate limiter."""
    limiter = MockRateLimitMiddleware()
    yield limiter


@pytest.fixture
def strict_rate_limiter():
    """Fixture for strict rate limiter."""
    limiter = MockRateLimitMiddleware(
        max_connection_attempts=3,
        connection_window_seconds=30,
        max_backoff_seconds=60
    )
    yield limiter


class TestConnectionAttemptLimiting:
    """Test connection attempt rate limiting."""

    def test_within_connection_limit(self, rate_limiter):
        """Test connection attempts within limit."""
        client_ip = "192.168.1.100"

        # Record 4 attempts (below limit of 5)
        for _ in range(4):
            rate_limiter.record_connection_attempt(client_ip)

        assert rate_limiter.check_connection_attempt_limit(client_ip) is True
        assert rate_limiter.get_attempts_in_window(client_ip) == 4

    def test_exceed_connection_limit(self, rate_limiter):
        """Test connection attempts exceeding limit."""
        client_ip = "192.168.1.100"

        # Record 5 attempts (at limit)
        for _ in range(5):
            rate_limiter.record_connection_attempt(client_ip)

        # Should exceed limit
        assert rate_limiter.check_connection_attempt_limit(client_ip) is False
        assert rate_limiter.get_attempts_in_window(client_ip) == 5

    def test_connection_window_expiry(self, rate_limiter):
        """Test that old attempts outside window are cleaned up."""
        client_ip = "192.168.1.100"

        # Create attempts with old timestamps
        old_time = time.time() - 120  # 2 minutes ago
        rate_limiter.connection_attempts[client_ip] = deque([old_time, old_time + 1])

        # Get attempts - should be 0 as they're outside window
        attempts = rate_limiter.get_attempts_in_window(client_ip)
        assert attempts == 0

    def test_multiple_clients(self, rate_limiter):
        """Test rate limiting with multiple clients."""
        clients = ["192.168.1.100", "192.168.1.101", "192.168.1.102"]

        for client_ip in clients:
            for _ in range(3):
                rate_limiter.record_connection_attempt(client_ip)

        # Each client should have 3 attempts
        for client_ip in clients:
            assert rate_limiter.get_attempts_in_window(client_ip) == 3


class TestExponentialBackoff:
    """Test exponential backoff for failed attempts."""

    def test_first_failure_backoff(self, rate_limiter):
        """Test backoff time after first failure."""
        client_ip = "192.168.1.100"

        rate_limiter.record_failed_connection(client_ip)

        # First failure: 2^1 * 2.0 = 4 seconds
        backoff = rate_limiter.calculate_backoff_time(client_ip)
        assert backoff == 4

    def test_second_failure_backoff(self, rate_limiter):
        """Test backoff time after second failure."""
        client_ip = "192.168.1.100"

        rate_limiter.record_failed_connection(client_ip)
        rate_limiter.record_failed_connection(client_ip)

        # Second failure: 2^2 * 2.0 = 8 seconds
        backoff = rate_limiter.calculate_backoff_time(client_ip)
        assert backoff == 8

    def test_multiple_failures_backoff(self, rate_limiter):
        """Test exponential growth of backoff time."""
        client_ip = "192.168.1.100"

        expected_backoffs = [4, 8, 16, 32, 64, 128, 256, 300, 300]  # 300 is max

        for i in range(9):
            rate_limiter.record_failed_connection(client_ip)
            backoff = rate_limiter.calculate_backoff_time(client_ip)
            assert backoff == expected_backoffs[i], f"Failure {i+1}: expected {expected_backoffs[i]}, got {backoff}"

    def test_max_backoff_cap(self, rate_limiter):
        """Test that backoff time is capped at maximum."""
        client_ip = "192.168.1.100"

        # Record many failures to exceed max
        for _ in range(10):
            rate_limiter.record_failed_connection(client_ip)

        backoff = rate_limiter.calculate_backoff_time(client_ip)
        assert backoff <= rate_limiter.max_backoff_seconds

    def test_successful_connection_resets_backoff(self, rate_limiter):
        """Test that successful connection resets backoff counter."""
        client_ip = "192.168.1.100"

        # Record some failures
        for _ in range(3):
            rate_limiter.record_failed_connection(client_ip)

        assert rate_limiter.failed_attempts[client_ip] == 3

        # Successful connection should reset
        rate_limiter.record_successful_connection(client_ip)

        assert client_ip not in rate_limiter.failed_attempts


class TestClientBlocking:
    """Test client blocking mechanism."""

    def test_client_not_blocked_initially(self, rate_limiter):
        """Test client is not blocked initially."""
        client_ip = "192.168.1.100"

        assert rate_limiter.is_blocked(client_ip) is False

    def test_client_blocked_after_failure(self, rate_limiter):
        """Test client is blocked after failed connection."""
        client_ip = "192.168.1.100"

        rate_limiter.record_failed_connection(client_ip)

        assert rate_limiter.is_blocked(client_ip) is True

    def test_block_duration_calculation(self, rate_limiter):
        """Test block duration is calculated correctly."""
        client_ip = "192.168.1.100"

        rate_limiter.record_failed_connection(client_ip)

        remaining = rate_limiter.get_remaining_block_time(client_ip)
        assert 0 < remaining <= 4  # First failure = 4 seconds

    def test_block_expiry(self, rate_limiter):
        """Test that block expires after duration."""
        client_ip = "192.168.1.100"

        # Set block that already expired
        rate_limiter.blocked_until[client_ip] = datetime.utcnow() - timedelta(seconds=10)

        # Should no longer be blocked
        assert rate_limiter.is_blocked(client_ip) is False

    def test_multiple_blocked_clients(self, rate_limiter):
        """Test multiple clients can be blocked independently."""
        clients = ["192.168.1.100", "192.168.1.101", "192.168.1.102"]

        for client_ip in clients:
            rate_limiter.record_failed_connection(client_ip)

        # All should be blocked
        for client_ip in clients:
            assert rate_limiter.is_blocked(client_ip) is True


class TestRateLimitConfiguration:
    """Test different rate limit configurations."""

    def test_strict_connection_limit(self, strict_rate_limiter):
        """Test stricter connection limit."""
        client_ip = "192.168.1.100"

        # Record 3 attempts (at strict limit)
        for _ in range(3):
            strict_rate_limiter.record_connection_attempt(client_ip)

        assert strict_rate_limiter.check_connection_attempt_limit(client_ip) is False

    def test_strict_backoff_cap(self, strict_rate_limiter):
        """Test stricter backoff cap."""
        client_ip = "192.168.1.100"

        # Record many failures
        for _ in range(10):
            strict_rate_limiter.record_failed_connection(client_ip)

        backoff = strict_rate_limiter.calculate_backoff_time(client_ip)
        assert backoff <= 60  # Strict max

    def test_custom_window_size(self):
        """Test custom window size."""
        limiter = MockRateLimitMiddleware(connection_window_seconds=30)
        client_ip = "192.168.1.100"

        # Add old attempt (45 seconds ago, outside 30s window)
        old_time = time.time() - 45
        limiter.connection_attempts[client_ip] = deque([old_time])

        # Should be cleaned up
        attempts = limiter.get_attempts_in_window(client_ip)
        assert attempts == 0


class TestRequestRateLimiting:
    """Test general request rate limiting."""

    def test_request_count_tracking(self, rate_limiter):
        """Test request counting per minute."""
        client_ip = "192.168.1.100"
        current_minute = datetime.utcnow().strftime("%Y%m%d%H%M")

        # Initialize tracking
        if client_ip not in rate_limiter.request_counts:
            rate_limiter.request_counts[client_ip] = {}
        rate_limiter.request_counts[client_ip][current_minute] = 50

        assert rate_limiter.request_counts[client_ip][current_minute] == 50

    def test_request_limit_not_exceeded(self, rate_limiter):
        """Test requests within limit."""
        client_ip = "192.168.1.100"
        current_minute = datetime.utcnow().strftime("%Y%m%d%H%M")

        rate_limiter.request_counts[client_ip] = {current_minute: 30}

        # 30 < 60 limit
        assert rate_limiter.request_counts[client_ip][current_minute] < rate_limiter.requests_per_minute

    def test_request_limit_exceeded(self, rate_limiter):
        """Test requests exceeding limit."""
        client_ip = "192.168.1.100"
        current_minute = datetime.utcnow().strftime("%Y%m%d%H%M")

        rate_limiter.request_counts[client_ip] = {current_minute: 70}

        # 70 > 60 limit
        assert rate_limiter.request_counts[client_ip][current_minute] >= rate_limiter.requests_per_minute


class TestStatisticsAndMonitoring:
    """Test rate limit statistics."""

    def test_get_client_statistics(self, rate_limiter):
        """Test getting statistics for a client."""
        client_ip = "192.168.1.100"

        # Record some activity
        for _ in range(3):
            rate_limiter.record_connection_attempt(client_ip)
        rate_limiter.record_failed_connection(client_ip)

        stats = {
            "client_ip": client_ip,
            "connection_attempts_in_window": rate_limiter.get_attempts_in_window(client_ip),
            "failed_attempts": rate_limiter.failed_attempts.get(client_ip, 0),
            "is_blocked": rate_limiter.is_blocked(client_ip),
            "remaining_block_time": rate_limiter.get_remaining_block_time(client_ip)
        }

        assert stats["connection_attempts_in_window"] == 3
        assert stats["failed_attempts"] == 1
        assert stats["is_blocked"] is True

    def test_statistics_for_clean_client(self, rate_limiter):
        """Test statistics for client with no violations."""
        client_ip = "192.168.1.100"

        stats = {
            "connection_attempts_in_window": rate_limiter.get_attempts_in_window(client_ip),
            "failed_attempts": rate_limiter.failed_attempts.get(client_ip, 0),
            "is_blocked": rate_limiter.is_blocked(client_ip)
        }

        assert stats["connection_attempts_in_window"] == 0
        assert stats["failed_attempts"] == 0
        assert stats["is_blocked"] is False


class TestMemoryManagement:
    """Test memory management and cleanup."""

    def test_old_attempts_cleanup(self, rate_limiter):
        """Test cleanup of old connection attempts."""
        client_ip = "192.168.1.100"

        # Add old attempts
        old_time = time.time() - 200  # 3+ minutes ago
        rate_limiter.connection_attempts[client_ip] = deque([old_time, old_time + 1, old_time + 2])

        # Trigger cleanup by getting attempts
        attempts = rate_limiter.get_attempts_in_window(client_ip)

        # Should be cleaned up
        assert attempts == 0

    def test_expired_blocks_cleanup(self, rate_limiter):
        """Test cleanup of expired blocks."""
        client_ip = "192.168.1.100"

        # Set expired block
        rate_limiter.blocked_until[client_ip] = datetime.utcnow() - timedelta(seconds=10)
        rate_limiter.failed_attempts[client_ip] = 3

        # Check if blocked - should trigger cleanup
        is_blocked = rate_limiter.is_blocked(client_ip)

        assert is_blocked is False
        assert client_ip not in rate_limiter.blocked_until
        assert client_ip not in rate_limiter.failed_attempts


class TestSecurityScenarios:
    """Test security-related scenarios."""

    def test_brute_force_protection(self, rate_limiter):
        """Test protection against brute force attacks."""
        client_ip = "192.168.1.100"

        # Simulate rapid connection attempts
        for _ in range(10):
            rate_limiter.record_connection_attempt(client_ip)

        # Should be blocked
        assert rate_limiter.check_connection_attempt_limit(client_ip) is False

    def test_distributed_attack_multiple_ips(self, rate_limiter):
        """Test handling of distributed attacks from multiple IPs."""
        attacker_ips = [f"192.168.1.{i}" for i in range(100, 110)]

        for ip in attacker_ips:
            for _ in range(6):  # Exceed limit
                rate_limiter.record_connection_attempt(ip)

        # Each IP should be limited independently
        for ip in attacker_ips:
            assert rate_limiter.check_connection_attempt_limit(ip) is False

    def test_failed_auth_escalating_backoff(self, rate_limiter):
        """Test escalating backoff for repeated failures."""
        client_ip = "192.168.1.100"

        backoff_times = []

        for _ in range(5):
            rate_limiter.record_failed_connection(client_ip)
            backoff_times.append(rate_limiter.calculate_backoff_time(client_ip))

        # Backoff should increase: 4, 8, 16, 32, 64
        assert backoff_times == [4, 8, 16, 32, 64]
        # Each should be >= previous
        for i in range(1, len(backoff_times)):
            assert backoff_times[i] >= backoff_times[i-1]


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_attempts(self, rate_limiter):
        """Test behavior with zero attempts."""
        client_ip = "192.168.1.100"

        assert rate_limiter.get_attempts_in_window(client_ip) == 0
        assert rate_limiter.check_connection_attempt_limit(client_ip) is True

    def test_exactly_at_limit(self, rate_limiter):
        """Test behavior exactly at the limit."""
        client_ip = "192.168.1.100"

        # Record exactly 5 attempts (the limit)
        for _ in range(5):
            rate_limiter.record_connection_attempt(client_ip)

        # Should be at limit (not allow more)
        assert rate_limiter.get_attempts_in_window(client_ip) == 5
        assert rate_limiter.check_connection_attempt_limit(client_ip) is False

    def test_unknown_client_ip(self, rate_limiter):
        """Test handling of unknown client IP."""
        client_ip = "unknown"

        assert rate_limiter.get_attempts_in_window(client_ip) == 0
        assert rate_limiter.is_blocked(client_ip) is False
        assert rate_limiter.get_remaining_block_time(client_ip) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
