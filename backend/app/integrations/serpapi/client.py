"""Centralised SerpApi HTTP client: auth, caching, retries, timeouts, structured errors, call tracking."""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.core.cache import CacheBackend, make_cache_key
from app.core.logging import get_logger
from app.schemas.result import ApiCall

log = get_logger(__name__)


# --------------------------------------------------------------------------- errors
class SerpApiError(Exception):
    code = "upstream_error"
    user_message = "The live travel data service returned an error. Please try again."
    retryable = False

    def __init__(self, detail: str = "", *, engine: str | None = None) -> None:
        super().__init__(detail or self.user_message)
        self.detail = detail
        self.engine = engine


class SerpApiAuthError(SerpApiError):
    code = "upstream_auth"
    user_message = "The SerpApi key was rejected. Check SERPAPI_API_KEY in your .env file."


class SerpApiQuotaError(SerpApiError):
    code = "upstream_quota_exhausted"
    user_message = "The SerpApi account has run out of searches for this period."


class SerpApiRateLimitError(SerpApiError):
    code = "upstream_rate_limited"
    user_message = "Live travel data is rate-limited right now. Please wait a minute and try again."
    retryable = True


class SerpApiTimeoutError(SerpApiError):
    code = "upstream_timeout"
    user_message = "Live travel data took too long to respond. Please try again."
    retryable = True


class SerpApiUpstreamError(SerpApiError):
    code = "upstream_error"
    retryable = True


class SerpApiMalformedResponse(SerpApiError):
    code = "upstream_malformed"
    user_message = "Live travel data came back in an unexpected format."


_EMPTY_MARKERS = ("hasn't returned any results", "has not returned any results", "no results")


# --------------------------------------------------------------------------- tracking
class CallTracker:
    """Collects every provider call made for one mission (shown in the transparency panel)."""

    def __init__(self) -> None:
        self.calls: list[ApiCall] = []

    def record(self, api: str, purpose: str, *, cached: bool, ok: bool, ms: int, error: str | None = None) -> None:
        self.calls.append(ApiCall(api=api, purpose=purpose, cached=cached, ok=ok, ms=ms, error=error))

    @property
    def live_calls(self) -> int:
        return sum(1 for c in self.calls if not c.cached)

    @property
    def cache_hits(self) -> int:
        return sum(1 for c in self.calls if c.cached)


# --------------------------------------------------------------------------- client
class SerpApiClient:
    def __init__(
        self,
        api_key: str,
        *,
        cache: CacheBackend,
        base_url: str = "https://serpapi.com/search.json",
        timeout_seconds: float = 25.0,
        max_retries: int = 2,
        max_concurrency: int = 4,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("SerpApiClient requires an API key")
        self._api_key = api_key
        self._cache = cache
        self._base_url = base_url
        self._timeout = httpx.Timeout(timeout_seconds, connect=5.0)
        self._max_retries = max_retries
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._transport = transport
        self._sleep = sleep
        self._http: httpx.AsyncClient | None = None

    def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=self._timeout, transport=self._transport,
                                           headers={"User-Agent": "TripMission/1.0"})
        return self._http

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()

    async def search(
        self,
        engine: str,
        params: dict[str, Any],
        *,
        ttl_seconds: int,
        tracker: CallTracker | None = None,
        purpose: str = "",
    ) -> dict[str, Any]:
        query = {k: v for k, v in params.items() if v is not None}
        query["engine"] = engine
        key = make_cache_key(engine, query)

        started = time.perf_counter()
        cached = await self._cache.get(key)
        if cached is not None:
            if tracker:
                tracker.record(engine, purpose, cached=True, ok=True, ms=int((time.perf_counter() - started) * 1000))
            log.info("serpapi cache hit", extra={"context": {"engine": engine, "purpose": purpose}})
            return cached

        try:
            data = await self._fetch_with_retries(engine, query)
        except SerpApiError as exc:
            elapsed = int((time.perf_counter() - started) * 1000)
            if tracker:
                tracker.record(engine, purpose, cached=False, ok=False, ms=elapsed, error=exc.code)
            log.warning("serpapi call failed", extra={"context": {
                "engine": engine, "purpose": purpose, "code": exc.code, "detail": exc.detail[:200], "ms": elapsed}})
            raise

        elapsed = int((time.perf_counter() - started) * 1000)
        if tracker:
            tracker.record(engine, purpose, cached=False, ok=True, ms=elapsed)
        log.info("serpapi call ok", extra={"context": {"engine": engine, "purpose": purpose, "ms": elapsed}})
        if not data.get("_empty"):
            await self._cache.set(key, engine, data, ttl_seconds)
        return data

    async def _fetch_with_retries(self, engine: str, query: dict[str, Any]) -> dict[str, Any]:
        attempt = 0
        while True:
            try:
                async with self._semaphore:
                    return await self._fetch_once(engine, query)
            except SerpApiError as exc:
                if not exc.retryable or attempt >= self._max_retries:
                    raise
                delay = getattr(exc, "retry_after", None) or (0.6 * (2 ** attempt) + random.uniform(0, 0.25))
                attempt += 1
                log.info("serpapi retry", extra={"context": {"engine": engine, "attempt": attempt, "code": exc.code}})
                await self._sleep(min(delay, 8.0))

    async def _fetch_once(self, engine: str, query: dict[str, Any]) -> dict[str, Any]:
        params = {**query, "api_key": self._api_key, "output": "json"}
        try:
            response = await self._client().get(self._base_url, params=params)
        except httpx.TimeoutException as exc:
            raise SerpApiTimeoutError(type(exc).__name__, engine=engine) from None
        except httpx.TransportError as exc:
            raise SerpApiUpstreamError(f"transport: {type(exc).__name__}", engine=engine) from None

        status = response.status_code
        body: Any
        try:
            body = response.json()
        except ValueError:
            body = None

        error_text = body.get("error", "") if isinstance(body, dict) else ""

        if status == 429:
            err = SerpApiRateLimitError(error_text or "HTTP 429", engine=engine)
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                err.retry_after = float(retry_after)  # type: ignore[attr-defined]
            raise err
        if status in (401, 403) or "invalid api key" in error_text.lower():
            raise SerpApiAuthError(error_text or f"HTTP {status}", engine=engine)
        if "run out of searches" in error_text.lower():
            raise SerpApiQuotaError(error_text, engine=engine)
        if status >= 500:
            raise SerpApiUpstreamError(f"HTTP {status}", engine=engine)
        if not isinstance(body, dict):
            raise SerpApiMalformedResponse(f"HTTP {status}: non-JSON body", engine=engine)
        if error_text:
            if any(marker in error_text.lower() for marker in _EMPTY_MARKERS):
                return {"_empty": True, "error": error_text}
            raise SerpApiUpstreamError(error_text, engine=engine)
        if status >= 400:
            raise SerpApiUpstreamError(f"HTTP {status}", engine=engine)
        return body


# --------------------------------------------------------------------------- user-facing messages
_PUBLIC_MESSAGES = {
    "upstream_timeout": "Live travel data took too long to respond. Please try again.",
    "upstream_rate_limited": "Lots of journeys are being planned right now. Please wait a minute and try again.",
}
_GENERIC_PUBLIC = "We couldn't load live travel data right now. Please try again in a few minutes."


def public_message(exc: SerpApiError, debug: bool = False) -> str:
    """A message safe for travellers: no provider names, keys, HTTP codes or request details.
    With DEBUG_MODE the developer-facing message and raw detail are returned instead."""
    if debug:
        return f"{exc.user_message} [{exc.code}{': ' + exc.detail[:200] if exc.detail else ''}]"
    return _PUBLIC_MESSAGES.get(exc.code, _GENERIC_PUBLIC)
