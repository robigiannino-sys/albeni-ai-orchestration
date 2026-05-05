"""
Bot Shield Cache — keeps the Redis SET 'bot_shield:exclusions' in sync
with the Postgres `bot_shield_exclusions` table.

The ai-router does an O(1) SISMEMBER lookup against this set on every
/v1/track/event call. If a visitor_id is in the set the event is dropped
without persistence. This module is the source of truth for what's IN
the set.

Strategy:
- On ml-worker startup, refresh once.
- Then refresh every REFRESH_INTERVAL seconds via an asyncio background task.
- Failure to refresh logs a warning but does NOT crash ml-worker — the
  ai-router fail-opens if Redis is empty (prefer noisy data to a black hole).

The refresh uses sync psycopg2 (already in deps) wrapped in run_in_executor
so we don't block the event loop.
"""
import asyncio
import logging
import os
from typing import Optional

import psycopg2

logger = logging.getLogger(__name__)

REFRESH_INTERVAL_SECONDS = 300  # 5 minutes
SET_KEY = "bot_shield:exclusions"


def _fetch_active_exclusions_sync() -> list[str]:
    """Sync helper — pulls active visitor_ids from Postgres. Runs in executor."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not in env")
    conn = psycopg2.connect(url)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT visitor_id FROM bot_shield_exclusions
            WHERE active = TRUE
              AND visitor_id IS NOT NULL
              AND (expires_at IS NULL OR expires_at > NOW())
            """
        )
        ids = [r[0] for r in cur.fetchall() if r[0]]
        cur.close()
        return ids
    finally:
        conn.close()


async def refresh_bot_shield_cache(redis_client) -> int:
    """
    Refresh the Redis SET from Postgres. Returns the number of members
    in the set after refresh, or -1 on failure (caller decides what to do).
    """
    try:
        loop = asyncio.get_running_loop()
        visitor_ids = await loop.run_in_executor(None, _fetch_active_exclusions_sync)

        # Use pipeline so DELETE+SADD is one round-trip
        pipe = redis_client.pipeline()
        pipe.delete(SET_KEY)
        if visitor_ids:
            pipe.sadd(SET_KEY, *visitor_ids)
        await pipe.execute()

        count = await redis_client.scard(SET_KEY)
        logger.info(
            "bot_shield cache refreshed: %d active exclusions from Postgres, %d in Redis SET",
            len(visitor_ids), count
        )
        return count
    except Exception as e:
        logger.warning("bot_shield cache refresh FAILED: %s", e, exc_info=True)
        return -1


async def periodic_refresh_loop(redis_client, interval: int = REFRESH_INTERVAL_SECONDS):
    """
    Background task: refresh forever every `interval` seconds.
    Cancellable via task.cancel() during shutdown.
    """
    logger.info("bot_shield periodic refresh started (interval=%ds)", interval)
    try:
        while True:
            await asyncio.sleep(interval)
            await refresh_bot_shield_cache(redis_client)
    except asyncio.CancelledError:
        logger.info("bot_shield periodic refresh cancelled")
        raise
