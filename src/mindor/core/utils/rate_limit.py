from typing import Optional
from mindor.dsl.schema.component.impl.rate_limit import RateLimitConfig
from .time import parse_duration
import asyncio, time

class RateLimiter:
    def __init__(self, config: RateLimitConfig):
        self.config: RateLimitConfig = config
        self._lock: asyncio.Lock = asyncio.Lock()

        self._token_bucket_enabled: bool = config.requests is not None
        self._interval_enabled: bool = config.interval is not None

        if self._token_bucket_enabled:
            self._period_seconds: float = parse_duration(config.period).total_seconds()
            self._refill_rate: float = config.requests / self._period_seconds
            self._capacity: float = float(config.burst if config.burst is not None else config.requests)
            self._tokens: float = self._capacity
            self._last_refill: float = time.monotonic()
        else:
            self._period_seconds = 0.0
            self._refill_rate = 0.0
            self._capacity = 0.0
            self._tokens = 0.0
            self._last_refill = 0.0

        if self._interval_enabled:
            self._interval_seconds: float = parse_duration(config.interval).total_seconds()
            self._next_allowed_at: float = 0.0
        else:
            self._interval_seconds = 0.0
            self._next_allowed_at = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()

            if self._token_bucket_enabled:
                self._tokens = min(self._capacity, self._tokens + (now - self._last_refill) * self._refill_rate)
                self._last_refill = now
                self._tokens -= 1
                token_allowed_at = now + max(0.0, -self._tokens / self._refill_rate)
            else:
                token_allowed_at = now

            if self._interval_enabled:
                interval_wait = max(0.0, self._next_allowed_at - token_allowed_at)
                send_at = token_allowed_at + interval_wait
                self._next_allowed_at = send_at + self._interval_seconds
            else:
                send_at = token_allowed_at

            wait_seconds = send_at - now

        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
