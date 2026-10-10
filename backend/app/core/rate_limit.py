"""Small in-memory sliding-window rate limiter (per client IP, per bucket)."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.errors import RateLimitedError


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def check(self, bucket: str, client: str, limit: int, window_seconds: float = 60.0) -> None:
        if limit <= 0:
            return
        now = time.monotonic()
        hits = self._hits[(bucket, client)]
        while hits and hits[0] <= now - window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = int(window_seconds - (now - hits[0])) + 1
            raise RateLimitedError(
                "Too many requests. Please wait a moment and try again.",
                details={"retry_after_seconds": retry_after},
            )
        hits.append(now)

    def reset(self) -> None:
        self._hits.clear()


limiter = SlidingWindowLimiter()


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"
