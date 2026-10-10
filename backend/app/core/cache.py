"""Pluggable response cache: Redis when available, otherwise the database, memory for tests."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from app.core.logging import get_logger

log = get_logger(__name__)

_EXCLUDED_KEY_PARAMS = {"api_key", "output", "async", "no_cache"}


def make_cache_key(engine: str, params: dict[str, Any]) -> str:
    """Deterministic key over engine + every request parameter except credentials."""
    clean = {k: v for k, v in params.items() if k not in _EXCLUDED_KEY_PARAMS and v is not None}
    raw = json.dumps({"engine": engine, "params": clean}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class CacheBackend(Protocol):
    name: str

    async def get(self, key: str) -> dict[str, Any] | None: ...

    async def set(self, key: str, engine: str, value: dict[str, Any], ttl_seconds: int) -> None: ...


class MemoryCache:
    name = "memory"

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, dict[str, Any]]] = {}

    async def get(self, key: str) -> dict[str, Any] | None:
        item = self._store.get(key)
        if not item:
            return None
        expires, value = item
        if expires < time.monotonic():
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, engine: str, value: dict[str, Any], ttl_seconds: int) -> None:
        self._store[key] = (time.monotonic() + ttl_seconds, value)


class DatabaseCache:
    name = "database"

    async def get(self, key: str) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_sync, key)

    async def set(self, key: str, engine: str, value: dict[str, Any], ttl_seconds: int) -> None:
        await asyncio.to_thread(self._set_sync, key, engine, value, ttl_seconds)

    @staticmethod
    def _get_sync(key: str) -> dict[str, Any] | None:
        from app.core.database import session_scope
        from app.models import SearchCache

        with session_scope() as session:
            row = session.get(SearchCache, key)
            if row is None:
                return None
            expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
            if expires < datetime.now(timezone.utc):
                return None
            return row.payload

    @staticmethod
    def _set_sync(key: str, engine: str, value: dict[str, Any], ttl_seconds: int) -> None:
        from app.core.database import session_scope
        from app.models import SearchCache

        now = datetime.now(timezone.utc)
        try:
            with session_scope() as session:
                row = session.get(SearchCache, key)
                if row is None:
                    row = SearchCache(key=key, engine=engine)
                    session.add(row)
                row.payload = value
                row.created_at = now
                row.expires_at = now + timedelta(seconds=ttl_seconds)
        except Exception as exc:  # cache failures must never fail a mission
            log.warning("cache write failed", extra={"context": {"error": type(exc).__name__}})


class RedisCache:
    name = "redis"

    def __init__(self, url: str) -> None:
        import redis.asyncio as redis_async

        self._client = redis_async.from_url(url, decode_responses=True)

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception:
            return False

    async def get(self, key: str) -> dict[str, Any] | None:
        try:
            raw = await self._client.get(f"tm:serp:{key}")
        except Exception as exc:
            log.warning("redis get failed", extra={"context": {"error": type(exc).__name__}})
            return None
        return json.loads(raw) if raw else None

    async def set(self, key: str, engine: str, value: dict[str, Any], ttl_seconds: int) -> None:
        try:
            await self._client.set(f"tm:serp:{key}", json.dumps(value), ex=ttl_seconds)
        except Exception as exc:
            log.warning("redis set failed", extra={"context": {"error": type(exc).__name__}})


_cache: CacheBackend | None = None


async def init_cache(redis_url: str) -> CacheBackend:
    global _cache
    if redis_url:
        try:
            candidate = RedisCache(redis_url)
            if await candidate.ping():
                _cache = candidate
                log.info("cache backend: redis")
                return _cache
            log.warning("redis unreachable, falling back to database cache")
        except Exception as exc:
            log.warning("redis unavailable", extra={"context": {"error": type(exc).__name__}})
    _cache = DatabaseCache()
    log.info("cache backend: database")
    return _cache


def get_cache() -> CacheBackend:
    global _cache
    if _cache is None:
        _cache = DatabaseCache()
    return _cache


def set_cache(cache: CacheBackend) -> None:
    global _cache
    _cache = cache
