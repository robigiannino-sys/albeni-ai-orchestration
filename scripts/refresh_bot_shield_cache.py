#!/usr/bin/env python3
"""
Refresh the Redis SET 'bot_shield:exclusions' from the Postgres
`bot_shield_exclusions` table (only rows where active=TRUE and not expired).

Run via:
    cd ~/Desktop/ALBENI/albeni.com/STEFANO/AI\ STACK\ APP/ai-orchestration-layer
    railway run --service Postgres bash -c 'python3 /tmp/refresh_bot_shield_cache.py'

The ai-router/routes/tracking.js handler does SISMEMBER on this set as a
fast O(1) gate before persisting any tracking event.

Should be run:
- Whenever a row is added/removed/deactivated in bot_shield_exclusions
- Periodically (e.g. via scheduled task) as a safety net

Failure modes:
- If REDIS_URL not in env: ml-worker creds not loaded, run from a service
  that has both DATABASE_URL + REDIS_URL (Postgres or albeni-ai-orchestration).
- If Redis unreachable: ai-router fails open (continues tracking everyone).
  This script's failure is recoverable on next run.
"""
import os
import sys
import psycopg2
import redis as redis_lib

PG_URL = os.environ.get('DATABASE_PUBLIC_URL') or os.environ.get('DATABASE_URL')
REDIS_URL = os.environ.get('REDIS_PUBLIC_URL') or os.environ.get('REDIS_URL')

if not PG_URL:
    print('ERROR: DATABASE_URL not in env. Run via `railway run --service Postgres ...`')
    sys.exit(1)
if not REDIS_URL:
    print('ERROR: REDIS_URL not in env. Run via `railway run --service Redis ...` or pass REDIS_PUBLIC_URL')
    sys.exit(1)

print(f'PG: {PG_URL.split("@")[-1]}')
print(f'REDIS: {REDIS_URL.split("@")[-1] if "@" in REDIS_URL else REDIS_URL}')

# Pull active exclusions from Postgres
pg_conn = psycopg2.connect(PG_URL)
cur = pg_conn.cursor()
cur.execute('''
    SELECT visitor_id FROM bot_shield_exclusions
    WHERE active = TRUE
      AND visitor_id IS NOT NULL
      AND (expires_at IS NULL OR expires_at > NOW())
''')
visitor_ids = [r[0] for r in cur.fetchall() if r[0]]
cur.close(); pg_conn.close()

print(f'Found {len(visitor_ids)} active exclusions in Postgres')

# Push to Redis SET (delete + recreate atomically via pipeline)
r = redis_lib.from_url(REDIS_URL)
SET_KEY = 'bot_shield:exclusions'

pipe = r.pipeline()
pipe.delete(SET_KEY)
if visitor_ids:
    pipe.sadd(SET_KEY, *visitor_ids)
pipe.execute()

# Verify
final_count = r.scard(SET_KEY)
print(f'Redis SET {SET_KEY}: {final_count} members')

if final_count == len(visitor_ids):
    print('OK — cache refreshed')
    sys.exit(0)
else:
    print(f'WARN — count mismatch (expected {len(visitor_ids)}, got {final_count})')
    sys.exit(2)
