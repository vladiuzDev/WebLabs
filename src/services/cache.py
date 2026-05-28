import json
import logging
from typing import Any

import redis as redis_lib

from src.core.config import CACHE_TTL_DEFAULT, REDIS_HOST, REDIS_PASSWORD, REDIS_PORT

logger = logging.getLogger(__name__)

_APP_PREFIX = "wp"


def make_key(*parts: str) -> str:
    """Build a namespaced Redis key: wp:<part1>:<part2>:..."""
    return ":".join([_APP_PREFIX, *parts])


class CacheService:
    def __init__(self) -> None:
        self._client: redis_lib.Redis | None = None
        try:
            client = redis_lib.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD or None,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
            self._client = client
            logger.info("Redis connected at %s:%s", REDIS_HOST, REDIS_PORT)
        except Exception as exc:
            logger.warning("Redis unavailable, caching disabled: %s", exc)

    @property
    def available(self) -> bool:
        return self._client is not None

    def get(self, key: str) -> Any | None:
        """Return deserialized value or None on miss / error."""
        if not self._client:
            return None
        try:
            raw = self._client.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception as exc:
            logger.warning("Cache GET error key=%s: %s", key, exc)
            return None

    def set(self, key: str, value: Any, ttl: int = CACHE_TTL_DEFAULT) -> None:
        """Serialize value and store with TTL (seconds)."""
        if not self._client:
            return
        try:
            self._client.setex(key, ttl, json.dumps(value, default=str))
        except Exception as exc:
            logger.warning("Cache SET error key=%s: %s", key, exc)

    def delete(self, key: str) -> None:
        """Delete a single key asynchronously (UNLINK)."""
        if not self._client:
            return
        try:
            self._client.unlink(key)
        except Exception as exc:
            logger.warning("Cache DELETE error key=%s: %s", key, exc)

    def delete_by_pattern(self, pattern: str) -> None:
        """Delete all keys matching a glob pattern."""
        if not self._client:
            return
        try:
            keys = self._client.keys(pattern)
            if keys:
                self._client.unlink(*keys)
        except Exception as exc:
            logger.warning("Cache DELETE_BY_PATTERN error pattern=%s: %s", pattern, exc)

    def check_exists(self, key: str) -> bool | None:
        """
        Check whether a key exists.

        Returns:
            True  — key found (Redis available, token valid)
            False — key missing (Redis available, token revoked / not stored)
            None  — Redis unavailable (caller should fall back to DB)
        """
        if not self._client:
            return None
        try:
            return self._client.exists(key) > 0
        except Exception as exc:
            logger.warning("Cache EXISTS error key=%s: %s", key, exc)
            return None


cache = CacheService()
