"""
Circuit Breaker Pattern Implementation for CrowdVision

Provides resilient service calls by preventing cascading failures.
When a service repeatedly fails, the circuit "opens" and fast-fails
subsequent requests until the service recovers.

States:
    CLOSED: Normal operation, requests flow through
    OPEN: Service failing, requests are rejected immediately
    HALF_OPEN: Testing recovery, limited requests allowed

Usage:
    from utils.circuit_breaker import CircuitBreaker

    breaker = CircuitBreaker("rtsp_stream", failure_threshold=3, recovery_timeout=30.0)

    if breaker.is_available():
        try:
            result = risky_operation()
            breaker.record_success()
        except Exception:
            breaker.record_failure()
"""

import time
import threading
import random
from enum import Enum
from typing import Optional
from dataclasses import dataclass
import logging
logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject requests
    HALF_OPEN = "half_open" # Testing recovery


@dataclass
class CircuitStats:
    """Statistics for circuit breaker monitoring"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state_changes: int = 0
    current_state: CircuitState = CircuitState.CLOSED


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for resilient service calls.

    Prevents cascading failures by fast-failing when a service is down.
    Automatically tests recovery after a timeout period.

    Args:
        name: Identifier for this circuit breaker (for logging)
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before testing recovery
        half_open_max_calls: Number of test calls allowed in half-open state
        success_threshold: Successes needed in half-open to close circuit

    Example:
        breaker = CircuitBreaker("gpu_inference", failure_threshold=3)

        if breaker.is_available():
            try:
                result = gpu_inference(frame)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                return cpu_fallback(frame)
        else:
            return cpu_fallback(frame)
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        success_threshold: int = 2
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._last_success_time: Optional[float] = None
        self._half_open_calls = 0
        self._half_open_successes = 0
        self._lock = threading.RLock()

        # Statistics
        self._stats = CircuitStats()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for automatic transitions"""
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if self._last_failure_time is not None:
                    elapsed = time.time() - self._last_failure_time
                    if elapsed >= self.recovery_timeout:
                        self._transition_to(CircuitState.HALF_OPEN)
            return self._state

    @property
    def stats(self) -> CircuitStats:
        """Get circuit breaker statistics"""
        with self._lock:
            self._stats.current_state = self._state
            return self._stats

    def _transition_to(self, new_state: CircuitState):
        """Transition to a new state with logging"""
        old_state = self._state
        self._state = new_state
        self._stats.state_changes += 1

        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._half_open_successes = 0

        logger.info(f"[CircuitBreaker:{self.name}] {old_state.value} -> {new_state.value}")

    def is_available(self) -> bool:
        """Check if requests should be allowed through"""
        current_state = self.state  # This checks for timeout-based transitions

        with self._lock:
            if current_state == CircuitState.OPEN:
                self._stats.rejected_calls += 1
                return False

            if current_state == CircuitState.HALF_OPEN:
                # Limit calls in half-open state
                if self._half_open_calls >= self.half_open_max_calls:
                    self._stats.rejected_calls += 1
                    return False
                self._half_open_calls += 1

            self._stats.total_calls += 1
            return True

    def record_success(self):
        """Record a successful operation"""
        with self._lock:
            self._success_count += 1
            self._last_success_time = time.time()
            self._stats.successful_calls += 1
            self._stats.last_success_time = self._last_success_time

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
                    self._failure_count = 0

            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    def record_failure(self, error: Optional[Exception] = None):
        """Record a failed operation"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            self._stats.failed_calls += 1
            self._stats.last_failure_time = self._last_failure_time

            if error:
                logger.error(f"[CircuitBreaker:{self.name}] Failure recorded: {type(error).__name__}: {error}")

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open state reopens the circuit
                self._transition_to(CircuitState.OPEN)

            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

    def reset(self):
        """Manually reset the circuit breaker to closed state"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._half_open_successes = 0
            logger.info(f"[CircuitBreaker:{self.name}] Manually reset to CLOSED")

    def force_open(self):
        """Manually force the circuit open (for maintenance)"""
        with self._lock:
            self._transition_to(CircuitState.OPEN)
            self._last_failure_time = time.time()
            logger.info(f"[CircuitBreaker:{self.name}] Manually forced OPEN")

    def __repr__(self) -> str:
        return f"CircuitBreaker(name={self.name}, state={self.state.value}, failures={self._failure_count})"


class ExponentialBackoff:
    """
    Exponential backoff calculator with jitter for retry delays.

    Usage:
        backoff = ExponentialBackoff(base_delay=2.0, max_delay=60.0)

        for attempt in range(max_attempts):
            try:
                result = operation()
                break
            except Exception:
                delay = backoff.get_delay(attempt)
                time.sleep(delay)
    """

    def __init__(
        self,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        multiplier: float = 2.0,
        jitter: float = 0.5
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number (0-indexed)"""
        # Exponential delay
        delay = self.base_delay * (self.multiplier ** attempt)

        # Add jitter (random factor)
        jitter_range = delay * self.jitter
        delay += random.uniform(-jitter_range, jitter_range)

        # Cap at max delay
        return min(delay, self.max_delay)


class CircuitBreakerRegistry:
    """
    Central registry for all circuit breakers.
    Allows monitoring and management of all breakers in the system.

    Usage:
        registry = CircuitBreakerRegistry()

        # Get or create breaker
        breaker = registry.get_or_create("rtsp_cam1", failure_threshold=5)

        # Get all breaker stats
        all_stats = registry.get_all_stats()
    """

    _instance: Optional["CircuitBreakerRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._breakers = {}
                    cls._instance._breaker_lock = threading.Lock()
        return cls._instance

    @classmethod
    def get_instance(cls) -> "CircuitBreakerRegistry":
        """Get singleton instance"""
        return cls()

    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        **kwargs
    ) -> CircuitBreaker:
        """Get existing breaker or create new one"""
        with self._breaker_lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                    **kwargs
                )
            return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get breaker by name, returns None if not found"""
        with self._breaker_lock:
            return self._breakers.get(name)

    def remove(self, name: str) -> bool:
        """Remove a breaker from registry"""
        with self._breaker_lock:
            if name in self._breakers:
                del self._breakers[name]
                return True
            return False

    def get_all_stats(self) -> dict:
        """Get stats for all breakers"""
        with self._breaker_lock:
            return {
                name: {
                    "state": breaker.state.value,
                    "total_calls": breaker.stats.total_calls,
                    "successful_calls": breaker.stats.successful_calls,
                    "failed_calls": breaker.stats.failed_calls,
                    "rejected_calls": breaker.stats.rejected_calls,
                    "state_changes": breaker.stats.state_changes,
                }
                for name, breaker in self._breakers.items()
            }

    def reset_all(self):
        """Reset all breakers to closed state"""
        with self._breaker_lock:
            for breaker in self._breakers.values():
                breaker.reset()

    def list_open_circuits(self) -> list:
        """List names of all open circuits"""
        with self._breaker_lock:
            return [
                name for name, breaker in self._breakers.items()
                if breaker.state == CircuitState.OPEN
            ]


# Convenience function for creating breakers
def create_circuit_breaker(
    name: str,
    failure_threshold: int = 3,
    recovery_timeout: float = 30.0,
    register: bool = True,
    **kwargs
) -> CircuitBreaker:
    """
    Create a circuit breaker, optionally registering it globally.

    Args:
        name: Breaker identifier
        failure_threshold: Failures before opening
        recovery_timeout: Seconds before testing recovery
        register: If True, register with global registry

    Returns:
        CircuitBreaker instance
    """
    if register:
        return CircuitBreakerRegistry.get_instance().get_or_create(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            **kwargs
        )

    return CircuitBreaker(
        name=name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        **kwargs
    )


__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "CircuitStats",
    "ExponentialBackoff",
    "CircuitBreakerRegistry",
    "create_circuit_breaker",
]
