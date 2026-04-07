"""
Cluster Prediction Model
Identifies which of the 5 behavioral clusters a user belongs to
based on navigation patterns. Target accuracy: >85%

Clusters:
1. Business Professional - Performance under blazer, 12h thermal stability
2. Heritage Mature - Investment quality, 270 years history, elegant
3. Conscious Premium - Sustainability, ZQ certification, ethical luxury
4. Modern Minimalist - Clean design, versatility, capsule wardrobe
5. Italian Authentic - Made in Italy pride, craftsmanship, thermal comfort
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from collections import Counter

import redis.asyncio as aioredis
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import func, and_

from config import get_settings
from models.database import User, BehavioralSignal
from models.schemas import ClusterPredictionResponse

logger = logging.getLogger(__name__)
settings = get_settings()


# Cluster signal mapping: which behaviors indicate which cluster
CLUSTER_SIGNALS = {
    "business_professional": {
        "keywords": [
            "blazer", "office", "business", "travel", "wrinkle",
            "performance", "meeting", "flight", "boardroom", "professional",
            "12 ore", "12 hours", "no iron", "viaggio"
        ],
        "domains_weight": {
            "perfectmerinoshirt.com": 0.4,
            "merinouniversity.com": 0.3,
            "albeni1905.com": 0.2,
            "worldofmerino.com": 0.1
        },
        "preferred_weight": "150g",
        "typical_scroll": 75,  # Reads thoroughly
        "typical_dwell": 90,   # Spends time on tech specs
    },
    "heritage_mature": {
        "keywords": [
            "heritage", "storia", "history", "tradition", "investment",
            "quality", "reda", "270", "craftsmanship", "elegance",
            "lusso", "luxury", "classico", "classic", "permanente"
        ],
        "domains_weight": {
            "albeni1905.com": 0.4,
            "worldofmerino.com": 0.3,
            "merinouniversity.com": 0.2,
            "perfectmerinoshirt.com": 0.1
        },
        "preferred_weight": "190g",
        "typical_scroll": 90,  # Very thorough reader
        "typical_dwell": 120,  # Contemplative
    },
    "conscious_premium": {
        "keywords": [
            "sustainable", "sostenibile", "ethical", "etico", "ZQ",
            "environment", "ambiente", "green", "carbon", "organic",
            "responsible", "responsabile", "traceable", "certificato"
        ],
        "domains_weight": {
            "worldofmerino.com": 0.35,
            "merinouniversity.com": 0.35,
            "albeni1905.com": 0.2,
            "perfectmerinoshirt.com": 0.1
        },
        "preferred_weight": "150g",
        "typical_scroll": 90,
        "typical_dwell": 100,
    },
    "modern_minimalist": {
        "keywords": [
            "minimal", "clean", "capsule", "wardrobe", "versatile",
            "essential", "essenziale", "design", "simple", "semplice",
            "basic", "staple", "uniforme", "uniform"
        ],
        "domains_weight": {
            "perfectmerinoshirt.com": 0.35,
            "worldofmerino.com": 0.25,
            "albeni1905.com": 0.25,
            "merinouniversity.com": 0.15
        },
        "preferred_weight": "150g",
        "typical_scroll": 50,  # Quick decision maker
        "typical_dwell": 45,   # Efficient browser
    },
    "italian_authentic": {
        "keywords": [
            "italia", "italian", "made in italy", "artigianale", "artisan",
            "merino", "lana", "wool", "estate", "summer", "thermal",
            "sudore", "sweat", "comfort", "cura", "care"
        ],
        "domains_weight": {
            "worldofmerino.com": 0.3,
            "albeni1905.com": 0.3,
            "merinouniversity.com": 0.25,
            "perfectmerinoshirt.com": 0.15
        },
        "preferred_weight": "190g",
        "typical_scroll": 75,
        "typical_dwell": 80,
    }
}


class ClusterPredictor:
    """
    Predicts user cluster based on behavioral signals.
    Uses a rule-based scoring system with keyword matching,
    domain affinity, and behavioral pattern analysis.
    """

    def __init__(self, redis_client: aioredis.Redis, db: DBSession):
        self.redis = redis_client
        self.db = db

    async def predict(self, user_id: str) -> ClusterPredictionResponse:
        """
        Main prediction entry point.
        Analyzes user signals and returns cluster assignment with confidence.
        """
        user = self.db.query(User).filter(User.external_id == user_id).first()
        if not user:
            return ClusterPredictionResponse(
                user_id=user_id,
                predicted_cluster="unknown",
                confidence=0.0,
                probabilities={c: 0.0 for c in settings.CLUSTERS},
                signals_analyzed=0
            )

        # Get recent signals (72h window)
        cutoff = datetime.utcnow() - timedelta(hours=72)
        signals = self.db.query(BehavioralSignal).filter(
            and_(
                BehavioralSignal.user_id == user.id,
                BehavioralSignal.created_at >= cutoff
            )
        ).all()

        if not signals:
            return ClusterPredictionResponse(
                user_id=user_id,
                predicted_cluster="unknown",
                confidence=0.0,
                probabilities={c: 0.0 for c in settings.CLUSTERS},
                signals_analyzed=0
            )

        # Calculate scores for each cluster
        scores = {}
        for cluster_name in settings.CLUSTERS:
            scores[cluster_name] = self._score_cluster(cluster_name, signals, user)

        # Normalize to probabilities
        total = sum(scores.values())
        if total > 0:
            probabilities = {k: round(v / total, 4) for k, v in scores.items()}
        else:
            probabilities = {c: 0.2 for c in settings.CLUSTERS}

        # Find the best cluster
        best_cluster = max(probabilities, key=probabilities.get)
        confidence = probabilities[best_cluster]

        # Update user record
        user.assigned_cluster = best_cluster
        user.cluster_confidence = confidence
        self.db.commit()

        # Cache in Redis
        await self._cache_cluster(user_id, best_cluster, confidence)

        return ClusterPredictionResponse(
            user_id=user_id,
            predicted_cluster=best_cluster,
            confidence=confidence,
            probabilities=probabilities,
            signals_analyzed=len(signals)
        )

    def _score_cluster(self, cluster_name: str, signals: list, user: User) -> float:
        """
        Calculate affinity score for a specific cluster based on signals.
        """
        config = CLUSTER_SIGNALS[cluster_name]
        score = 0.0

        # 1. Domain affinity (30% of score)
        domain_counts = Counter()
        for signal in signals:
            domain = signal.domain
            for domain_key in config["domains_weight"]:
                if domain_key in (domain or ""):
                    domain_counts[domain_key] += 1

        domain_score = 0.0
        total_signals = len(signals)
        if total_signals > 0:
            for domain, count in domain_counts.items():
                weight = config["domains_weight"].get(domain, 0)
                domain_score += (count / total_signals) * weight
        score += domain_score * 30

        # 2. Keyword matching (40% of score)
        keyword_matches = 0
        for signal in signals:
            if signal.event_value:
                signal_text = json.dumps(signal.event_value).lower()
                for keyword in config["keywords"]:
                    if keyword.lower() in signal_text:
                        keyword_matches += 1

            if signal.interaction_element:
                for keyword in config["keywords"]:
                    if keyword.lower() in signal.interaction_element.lower():
                        keyword_matches += 1

        keyword_score = min(1.0, keyword_matches / max(1, len(config["keywords"]) * 0.3))
        score += keyword_score * 40

        # 3. Behavioral pattern matching (30% of score)
        max_scroll = 0
        total_dwell = 0
        interaction_types = Counter()

        for signal in signals:
            if signal.scroll_depth:
                max_scroll = max(max_scroll, signal.scroll_depth)
            if signal.dwell_time_seconds:
                total_dwell += signal.dwell_time_seconds
            if signal.event_type:
                interaction_types[signal.event_type] += 1

        # Compare with typical cluster behavior
        scroll_similarity = 1.0 - abs(max_scroll - config["typical_scroll"]) / 100
        dwell_similarity = 1.0 - min(1.0, abs(total_dwell - config["typical_dwell"]) / 200)
        behavior_score = (scroll_similarity + dwell_similarity) / 2
        score += behavior_score * 30

        return max(0, score)

    async def _cache_cluster(self, user_id: str, cluster: str, confidence: float):
        """Cache cluster prediction in Redis."""
        try:
            await self.redis.set(f"user:{user_id}:cluster", cluster, ex=600)
            await self.redis.set(f"user:{user_id}:cluster_confidence", str(confidence), ex=600)
        except Exception as e:
            logger.warning(f"Redis cluster cache failed for {user_id}: {e}")
