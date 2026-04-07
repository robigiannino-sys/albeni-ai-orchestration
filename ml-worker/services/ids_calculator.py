"""
Intent Depth Score (IDS) Calculator
Scale: 0-100 | Weighted sum of normalized behavioral signals

Formula: IDS = (T_norm * 0.20) + (S_norm * 0.20) + (I_norm * 0.40) + (R_norm * 0.20)

Where:
  T = Dwell Time (20%) - Target >60s
  S = Scroll Depth (20%) - Steps 25/50/75/90%
  I = Technical Interactions (40%) - Clicks, downloads, video views
  R = Return Frequency (20%) - Sessions within 72h window
"""
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict

import redis.asyncio as aioredis
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import func, and_

from config import get_settings
from models.database import User, BehavioralSignal, Session as UserSession, IntentIntelligence
from models.schemas import IDSCalculationResponse, IDSBreakdown, IntentStage

logger = logging.getLogger(__name__)
settings = get_settings()


class IDSCalculator:
    """
    Calculates the Intent Depth Score for a user based on their
    behavioral signals across the 4-domain ecosystem.
    """

    # Normalization constants
    DWELL_TIME_MAX = 300       # 5 min = max dwell score
    SCROLL_DEPTH_MAX = 90      # 90% = max scroll score
    INTERACTIONS_MAX = 10       # 10 technical interactions = max score
    FREQUENCY_MAX = 5           # 5 sessions in 72h = max score

    # IDS point awards per event type
    EVENT_POINTS = {
        "dwell_time_reached": 5.0,
        "scroll_depth_25": 2.0,
        "scroll_depth_50": 4.0,
        "scroll_depth_75": 6.0,
        "scroll_depth_90": 10.0,
        "click_comparison": 8.0,
        "download_pdf": 10.0,
        "video_play": 7.0,
        "technical_interaction": 6.0,
        "lead_magnet_download": 12.0,
        "product_view": 5.0,
        "add_to_cart": 15.0,
    }

    def __init__(self, redis_client: aioredis.Redis, db: DBSession):
        self.redis = redis_client
        self.db = db

    async def calculate(self, user_id: str, force: bool = False) -> IDSCalculationResponse:
        """
        Main IDS calculation entry point.
        Returns the calculated score with full breakdown.
        """
        start_time = time.time()

        # Check Redis cache first (unless forced recalculation)
        if not force:
            cached = await self._get_cached_ids(user_id)
            if cached:
                latency = int((time.time() - start_time) * 1000)
                cached["calculation_latency_ms"] = latency
                return IDSCalculationResponse(**cached)

        # Get user from DB
        user = self.db.query(User).filter(User.external_id == user_id).first()
        if not user:
            return IDSCalculationResponse(
                user_id=user_id,
                ids_score=0,
                intent_stage=IntentStage.TOFU,
                breakdown=IDSBreakdown(),
                routing_suggestion=settings.DOMAIN_TOFU
            )

        # Calculate each component
        dwell_norm = self._calculate_dwell_time(user)
        scroll_norm = self._calculate_scroll_depth(user)
        interactions_norm = self._calculate_interactions(user)
        frequency_norm = self._calculate_frequency(user)

        # Apply weights
        dwell_weighted = dwell_norm * settings.IDS_WEIGHT_DWELL_TIME
        scroll_weighted = scroll_norm * settings.IDS_WEIGHT_SCROLL_DEPTH
        interactions_weighted = interactions_norm * settings.IDS_WEIGHT_INTERACTIONS
        frequency_weighted = frequency_norm * settings.IDS_WEIGHT_FREQUENCY

        # Final score (0-100)
        raw_total = (dwell_weighted + scroll_weighted + interactions_weighted + frequency_weighted) * 100
        final_score = min(100, max(0, int(raw_total)))

        # Determine intent stage
        intent_stage = self._get_intent_stage(final_score)

        # Get routing suggestion
        routing = self._get_routing_suggestion(final_score, user.assigned_cluster)

        # Build breakdown
        breakdown = IDSBreakdown(
            dwell_time_norm=round(dwell_norm, 4),
            dwell_time_weighted=round(dwell_weighted, 4),
            scroll_depth_norm=round(scroll_norm, 4),
            scroll_depth_weighted=round(scroll_weighted, 4),
            interactions_norm=round(interactions_norm, 4),
            interactions_weighted=round(interactions_weighted, 4),
            frequency_norm=round(frequency_norm, 4),
            frequency_weighted=round(frequency_weighted, 4),
            raw_total=round(raw_total, 2),
            final_score=final_score
        )

        latency = int((time.time() - start_time) * 1000)

        # Update user record
        user.ids_score = final_score
        user.intent_stage = intent_stage.value
        user.last_seen_at = datetime.utcnow()
        self.db.commit()

        # Save to intent_intelligence table
        intelligence = IntentIntelligence(
            user_id=user.id,
            ids_score=final_score,
            ids_breakdown=breakdown.model_dump(),
            predicted_cluster=user.assigned_cluster,
            intent_stage=intent_stage.value,
            routing_decision=routing,
            language=user.preferred_language,
            calculation_latency_ms=latency
        )
        self.db.add(intelligence)
        self.db.commit()

        # Cache in Redis (TTL: 5 minutes)
        result = IDSCalculationResponse(
            user_id=user_id,
            ids_score=final_score,
            intent_stage=intent_stage,
            breakdown=breakdown,
            predicted_cluster=user.assigned_cluster,
            cluster_confidence=float(user.cluster_confidence or 0),
            routing_suggestion=routing,
            calculation_latency_ms=latency
        )
        await self._cache_ids(user_id, result)

        return result

    def _calculate_dwell_time(self, user: User) -> float:
        """
        Normalize dwell time signal (0-1).
        Aggregates total dwell time from recent sessions (last 72h).
        """
        cutoff = datetime.utcnow() - timedelta(hours=72)
        total_dwell = self.db.query(
            func.coalesce(func.sum(BehavioralSignal.dwell_time_seconds), 0)
        ).filter(
            and_(
                BehavioralSignal.user_id == user.id,
                BehavioralSignal.event_type == "dwell_time_reached",
                BehavioralSignal.created_at >= cutoff
            )
        ).scalar() or 0

        # Also count signals that imply dwell time
        dwell_signals = self.db.query(func.count(BehavioralSignal.id)).filter(
            and_(
                BehavioralSignal.user_id == user.id,
                BehavioralSignal.event_type == "dwell_time_reached",
                BehavioralSignal.created_at >= cutoff
            )
        ).scalar() or 0

        # Each dwell_time_reached event = 60s minimum
        effective_dwell = max(total_dwell, dwell_signals * 60)
        return min(1.0, effective_dwell / self.DWELL_TIME_MAX)

    def _calculate_scroll_depth(self, user: User) -> float:
        """
        Normalize scroll depth signal (0-1).
        Uses the maximum scroll depth reached across recent sessions.
        """
        cutoff = datetime.utcnow() - timedelta(hours=72)
        max_scroll = self.db.query(
            func.coalesce(func.max(BehavioralSignal.scroll_depth), 0)
        ).filter(
            and_(
                BehavioralSignal.user_id == user.id,
                BehavioralSignal.event_type == "scroll_depth",
                BehavioralSignal.created_at >= cutoff
            )
        ).scalar() or 0

        return min(1.0, max_scroll / self.SCROLL_DEPTH_MAX)

    def _calculate_interactions(self, user: User) -> float:
        """
        Normalize technical interactions signal (0-1).
        Counts high-value interactions: comparisons, downloads, video views.
        """
        cutoff = datetime.utcnow() - timedelta(hours=72)
        high_value_types = [
            "technical_interaction", "click_comparison",
            "download_pdf", "video_play", "lead_magnet_download",
            "product_view", "add_to_cart"
        ]

        interaction_count = self.db.query(func.count(BehavioralSignal.id)).filter(
            and_(
                BehavioralSignal.user_id == user.id,
                BehavioralSignal.event_type.in_(high_value_types),
                BehavioralSignal.created_at >= cutoff
            )
        ).scalar() or 0

        return min(1.0, interaction_count / self.INTERACTIONS_MAX)

    def _calculate_frequency(self, user: User) -> float:
        """
        Normalize return frequency signal (0-1).
        Counts distinct sessions within a 72-hour window.
        """
        cutoff = datetime.utcnow() - timedelta(hours=72)
        session_count = self.db.query(func.count(UserSession.id)).filter(
            and_(
                UserSession.user_id == user.id,
                UserSession.started_at >= cutoff
            )
        ).scalar() or 0

        return min(1.0, session_count / self.FREQUENCY_MAX)

    def _get_intent_stage(self, score: int) -> IntentStage:
        """Determine the intent stage based on IDS score."""
        if score <= settings.IDS_TOFU_MAX:
            return IntentStage.TOFU
        elif score <= settings.IDS_MOFU_MAX:
            return IntentStage.MOFU
        else:
            return IntentStage.BOFU

    def _get_routing_suggestion(self, score: int, cluster: Optional[str] = None) -> str:
        """
        Determine the optimal destination domain based on IDS and cluster.
        """
        if score <= settings.IDS_TOFU_MAX:
            return settings.DOMAIN_TOFU
        elif score <= settings.IDS_MOFU_MAX:
            return settings.DOMAIN_MOFU
        else:
            # BOFU: Route based on cluster
            tech_clusters = ["business_professional", "modern_minimalist"]
            if cluster in tech_clusters:
                return settings.DOMAIN_BOFU_TECH
            else:
                return settings.DOMAIN_BOFU_HERITAGE

    async def _get_cached_ids(self, user_id: str) -> Optional[dict]:
        """Retrieve cached IDS from Redis."""
        try:
            cached = await self.redis.get(f"user:{user_id}:ids_full")
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache miss for {user_id}: {e}")
        return None

    async def _cache_ids(self, user_id: str, result: IDSCalculationResponse):
        """Cache IDS result in Redis with 5-minute TTL."""
        try:
            data = result.model_dump()
            data["intent_stage"] = data["intent_stage"].value if hasattr(data["intent_stage"], "value") else data["intent_stage"]
            await self.redis.set(
                f"user:{user_id}:ids_full",
                json.dumps(data, default=str),
                ex=300  # 5 minutes TTL
            )
            # Also cache just the score and cluster for fast router access
            await self.redis.set(f"user:{user_id}:ids", str(result.ids_score), ex=300)
            await self.redis.set(f"user:{user_id}:cluster", result.predicted_cluster or "unknown", ex=300)
            await self.redis.set(f"user:{user_id}:stage", result.intent_stage.value, ex=300)
        except Exception as e:
            logger.warning(f"Redis cache write failed for {user_id}: {e}")

    @staticmethod
    def get_event_points(event_type: str, metadata: dict = {}) -> float:
        """Calculate IDS points for a specific event."""
        # Handle scroll depth events with variable points
        if event_type == "scroll_depth":
            depth = metadata.get("depth", 0)
            return IDSCalculator.EVENT_POINTS.get(f"scroll_depth_{depth}", 2.0)

        return IDSCalculator.EVENT_POINTS.get(event_type, 1.0)
