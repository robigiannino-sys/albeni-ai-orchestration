"""
Pipeline Consumer (downstream batch processor).
Albeni 1905 — added 2026-05-06.

Why this exists
---------------
The ml-worker exposes on-demand endpoints (/v1/cluster/predict,
/v1/intent/calculate, /v1/router/assign), but until 2026-05-06 nothing
was triggering them on the stream of new behavioral_signals. As a result
the downstream tables (intent_intelligence, sessions, routing_decisions)
stayed at zero delta even while behavioral_signals grew. This module
implements the missing batch consumer.

What it does
------------
1. Finds users whose downstream state is "stale": null cluster, ids_score==0,
   or any user with new behavioral_signals since their last
   intent_intelligence calculation.
2. For each, runs the on-demand pipeline (cluster_predictor → ids_calculator).
3. Aggregates raw behavioral_signals into sessions using a 30-minute gap
   heuristic (industry standard for session windowing).

It is invoked by:
- The APScheduler job set up in main.py:lifespan (every 15 minutes).
- The /v1/admin/recompute-pipeline endpoint (manual trigger).
- The scripts/recompute_pipeline.py CLI (manual one-shot from Mac).
"""
import logging
from datetime import datetime, timedelta
from typing import Dict

from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from models.database import User, BehavioralSignal, IntentIntelligence
from services.cluster_predictor import ClusterPredictor
from services.ids_calculator import IDSCalculator

logger = logging.getLogger(__name__)


SESSION_GAP_MINUTES = 30


async def recompute_pipeline(db: DBSession, redis_client) -> Dict:
    """Run a full backfill pass. Returns a stats dict for the caller to log."""
    started = datetime.utcnow()
    stats = {
        "users_total": 0,
        "users_processed": 0,
        "cluster_updated": 0,
        "ids_updated": 0,
        "sessions_created": 0,
        "errors": [],
        "duration_ms": 0,
    }

    try:
        users = db.query(User).all()
        stats["users_total"] = len(users)

        cluster_predictor = ClusterPredictor(redis_client, db)
        ids_calculator = IDSCalculator(redis_client, db)

        for user in users:
            try:
                # 1. Cluster prediction (skip if already classified)
                if not user.assigned_cluster:
                    try:
                        cluster_result = await cluster_predictor.predict(user.external_id)
                        if cluster_result and getattr(cluster_result, "predicted_cluster", None):
                            stats["cluster_updated"] += 1
                    except Exception as e:
                        stats["errors"].append(f"cluster:{user.external_id}:{e}")

                # 2. IDS calculation (always recompute if user has new signals)
                last_intent = (
                    db.query(IntentIntelligence)
                    .filter(IntentIntelligence.user_id == user.id)
                    .order_by(IntentIntelligence.created_at.desc())
                    .first()
                )
                last_signal = (
                    db.query(BehavioralSignal)
                    .filter(BehavioralSignal.user_id == user.id)
                    .order_by(BehavioralSignal.created_at.desc())
                    .first()
                )

                needs_recalc = (
                    last_signal is not None
                    and (last_intent is None or last_signal.created_at > last_intent.created_at)
                )
                if needs_recalc or user.ids_score == 0:
                    try:
                        await ids_calculator.calculate(user.external_id, force=True)
                        stats["ids_updated"] += 1
                    except Exception as e:
                        stats["errors"].append(f"ids:{user.external_id}:{e}")

                stats["users_processed"] += 1
            except Exception as e:
                stats["errors"].append(f"user:{user.external_id}:{e}")
                continue

        # 3. Session aggregation
        try:
            stats["sessions_created"] = _aggregate_sessions(db)
        except Exception as e:
            stats["errors"].append(f"sessions:{e}")
            db.rollback()

    finally:
        stats["duration_ms"] = int((datetime.utcnow() - started).total_seconds() * 1000)
        logger.info(
            "Pipeline consumer pass: %s users (cluster +%s, ids +%s, sessions +%s, errors %s) in %sms",
            stats["users_processed"], stats["cluster_updated"], stats["ids_updated"],
            stats["sessions_created"], len(stats["errors"]), stats["duration_ms"],
        )

    return stats


def _aggregate_sessions(db: DBSession) -> int:
    """
    Build the sessions table from raw behavioral_signals using a gap heuristic.
    A new session starts whenever consecutive signals from the same user are
    more than SESSION_GAP_MINUTES apart.

    Idempotent: only inserts sessions that don't already exist (matched by
    user_id + started_at). We do NOT touch the existing 370 seed sessions.
    """
    sql = text("""
        WITH gaps AS (
            SELECT
                bs.user_id,
                bs.created_at,
                bs.domain,
                bs.language,
                bs.page_url,
                LAG(bs.created_at) OVER (PARTITION BY bs.user_id ORDER BY bs.created_at) AS prev_ts
            FROM behavioral_signals bs
        ),
        marked AS (
            SELECT
                user_id, created_at, domain, language, page_url,
                CASE
                    WHEN prev_ts IS NULL OR EXTRACT(EPOCH FROM (created_at - prev_ts)) > :gap_seconds
                    THEN 1 ELSE 0
                END AS is_new_session
            FROM gaps
        ),
        sessioned AS (
            SELECT
                user_id, created_at, domain, language, page_url,
                SUM(is_new_session) OVER (PARTITION BY user_id ORDER BY created_at) AS sess_seq
            FROM marked
        ),
        agg AS (
            SELECT
                user_id,
                sess_seq,
                MIN(created_at) AS started_at,
                MAX(created_at) AS ended_at,
                MIN(domain) AS source_domain,
                MIN(language) AS language,
                (ARRAY_AGG(page_url ORDER BY created_at ASC))[1] AS entry_page,
                (ARRAY_AGG(page_url ORDER BY created_at DESC))[1] AS exit_page,
                COUNT(*) AS page_views
            FROM sessioned
            GROUP BY user_id, sess_seq
        )
        INSERT INTO sessions (
            id, user_id, session_id, source_domain, language,
            entry_page, exit_page, page_views, started_at, ended_at,
            is_active, created_at
        )
        SELECT
            gen_random_uuid(),
            agg.user_id,
            'auto_' || agg.user_id::text || '_' || EXTRACT(EPOCH FROM agg.started_at)::bigint,
            COALESCE(agg.source_domain, 'unknown'),
            COALESCE(agg.language, 'it'),
            agg.entry_page,
            agg.exit_page,
            agg.page_views,
            agg.started_at,
            agg.ended_at,
            FALSE,
            NOW()
        FROM agg
        WHERE NOT EXISTS (
            SELECT 1 FROM sessions s
            WHERE s.user_id = agg.user_id AND s.started_at = agg.started_at
        )
        RETURNING 1
    """)
    result = db.execute(sql, {"gap_seconds": SESSION_GAP_MINUTES * 60})
    inserted = result.rowcount or 0
    db.commit()
    return inserted
