from __future__ import annotations

import io
import logging

import httpx
import pytest

from app.core.cache import MemoryCache, make_cache_key
from app.core.logging import RedactingFilter
from app.integrations.serpapi.client import (CallTracker, SerpApiAuthError, SerpApiClient, SerpApiMalformedResponse, SerpApiQuotaError,
                                             SerpApiRateLimitError, SerpApiTimeoutError, SerpApiUpstreamError)


async def _no_sleep(_):
    return None


def _client(handler, cache=None, retries=2):
    return SerpApiClient("secret-key-abcdef", cache=cache or MemoryCache(), transport=httpx.MockTransport(handler),
                         max_retries=retries, sleep=_no_sleep)


async def test_cache_hit_avoids_second_call():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"best_flights": []})

    client, tracker = _client(handler), CallTracker()
    await client.search("google_flights", {"departure_id": "IDR"}, ttl_seconds=60, tracker=tracker)
    await client.search("google_flights", {"departure_id": "IDR"}, ttl_seconds=60, tracker=tracker)
    assert len(calls) == 1
    assert tracker.live_calls == 1 and tracker.cache_hits == 1
    assert calls[0].url.params["api_key"] == "secret-key-abcdef"


def test_cache_key_excludes_api_key_and_is_order_independent():
    a = make_cache_key("google_hotels", {"q": "x", "check_in_date": "2026-10-08", "api_key": "one"})
    b = make_cache_key("google_hotels", {"check_in_date": "2026-10-08", "q": "x", "api_key": "two"})
    c = make_cache_key("google_hotels", {"check_in_date": "2026-10-09", "q": "x"})
    assert a == b != c


async def test_retries_on_5xx_then_succeeds():
    responses = [httpx.Response(503), httpx.Response(502), httpx.Response(200, json={"ok": 1})]
    client = _client(lambda r: responses.pop(0))
    assert (await client.search("google_local", {"q": "cafe"}, ttl_seconds=1)) == {"ok": 1}


async def test_rate_limit_exhausts_retries():
    client = _client(lambda r: httpx.Response(429, json={"error": "Too many requests"}), retries=1)
    with pytest.raises(SerpApiRateLimitError):
        await client.search("google_local", {"q": "cafe"}, ttl_seconds=1)


async def test_auth_and_quota_errors_are_not_retried():
    calls = []

    def auth(request):
        calls.append(1)
        return httpx.Response(401, json={"error": "Invalid API key. Your API key should be here: ..."})

    with pytest.raises(SerpApiAuthError):
        await _client(auth).search("google_flights", {}, ttl_seconds=1)
    assert len(calls) == 1
    with pytest.raises(SerpApiQuotaError):
        await _client(lambda r: httpx.Response(200, json={"error": "Your account has run out of searches."})).search(
            "google_flights", {}, ttl_seconds=1)


async def test_timeout_is_mapped():
    def boom(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(SerpApiTimeoutError):
        await _client(boom).search("google_flights", {}, ttl_seconds=1)


async def test_empty_result_is_not_an_error_and_not_cached():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"error": "Google hasn't returned any results for this query."})

    client = _client(handler)
    data = await client.search("google_local", {"q": "x"}, ttl_seconds=60)
    assert data["_empty"] is True
    await client.search("google_local", {"q": "x"}, ttl_seconds=60)
    assert len(calls) == 2


async def test_malformed_body():
    client = _client(lambda r: httpx.Response(200, content=b"<html>oops</html>"))
    with pytest.raises(SerpApiMalformedResponse):
        await client.search("google_local", {"q": "x"}, ttl_seconds=1)


def test_log_redaction():
    stream = io.StringIO()
    logger = logging.getLogger("redaction-test")
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactingFilter(["super-secret-value"]))
    logger.addHandler(handler)
    logger.warning("GET https://serpapi.com/search.json?engine=x&api_key=abc123&q=y and super-secret-value")
    out = stream.getvalue()
    assert "abc123" not in out and "super-secret-value" not in out and "api_key=***" in out
