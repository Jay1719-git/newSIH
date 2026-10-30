from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict, deque


class LoginThrottle:
    """Small process-local limiter for the single-process synthetic/demo API."""

    def __init__(self, attempts: int = 8, window_seconds: int = 900, block_seconds: int = 900):
        self.attempts = attempts
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._blocked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _keys(remote: str, email: str) -> tuple[str, str]:
        remote_hash = hashlib.sha256(remote.strip().encode()).hexdigest()
        pair_hash = hashlib.sha256(
            f"{remote_hash}\0{email.strip().casefold()}".encode()
        ).hexdigest()
        return f"ip:{remote_hash}", f"identity:{pair_hash}"

    def is_blocked(self, remote: str, email: str, now: float | None = None) -> bool:
        moment = now if now is not None else time.monotonic()
        keys = self._keys(remote, email)
        with self._lock:
            blocked = False
            for key in keys:
                until = self._blocked_until.get(key, 0)
                if until > moment:
                    blocked = True
                elif until:
                    self._blocked_until.pop(key, None)
                attempts = self._failures.get(key)
                if attempts is not None:
                    while attempts and attempts[0] <= moment - self.window_seconds:
                        attempts.popleft()
                    if not attempts:
                        self._failures.pop(key, None)
            return blocked

    def record_failure(self, remote: str, email: str, now: float | None = None) -> None:
        moment = now if now is not None else time.monotonic()
        keys = self._keys(remote, email)
        with self._lock:
            if len(self._failures) >= 10_000:
                self._failures = defaultdict(
                    deque,
                    {
                        key: attempts
                        for key, attempts in self._failures.items()
                        if attempts and attempts[-1] > moment - self.window_seconds
                    },
                )
                self._blocked_until = {
                    key: until for key, until in self._blocked_until.items() if until > moment
                }
                if len(self._failures) >= 10_000:
                    oldest = min(self._failures, key=lambda key: self._failures[key][-1])
                    self._failures.pop(oldest, None)
                    self._blocked_until.pop(oldest, None)
            for key in keys:
                attempts = self._failures[key]
                while attempts and attempts[0] <= moment - self.window_seconds:
                    attempts.popleft()
                attempts.append(moment)
                if len(attempts) >= self.attempts:
                    self._blocked_until[key] = moment + self.block_seconds

    def clear(self, remote: str, email: str) -> None:
        _, key = self._keys(remote, email)
        with self._lock:
            self._failures.pop(key, None)
            self._blocked_until.pop(key, None)


login_throttle = LoginThrottle()
