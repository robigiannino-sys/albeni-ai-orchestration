"""
SEO Balance Monitor & Anti-Cannibalization Engine
Manages the 85/15 balance model and detects keyword conflicts between domains.

85% = Behavioral Cluster SEO (expansion)
15% = Semantic Defense (protection of technical keywords like "cut & sewn")
"""
import logging
from datetime import datetime, date
from typing import Dict, List, Optional

from sqlalchemy.orm import Session as DBSession
from sqlalchemy import func, and_

from config import get_settings
from models.database import User, BehavioralSignal
from models.schemas import SEOHealthCheck

logger = logging.getLogger(__name__)
settings = get_settings()

# Domain-keyword mapping (which keywords belong to which domain)
DOMAIN_KEYWORD_MAP = {
    "worldofmerino.com": {
        "role": "TOFU - Lifestyle & Discovery",
        "primary_keywords": [
            "world of merino", "merino wool benefits", "natural fibers",
            "sustainable fashion", "wool vs cotton", "merino lifestyle",
            "invisible luxury", "ethical clothing"
        ],
        "protected_topics": ["merino education", "brand storytelling", "lifestyle content"]
    },
    "merinouniversity.com": {
        "role": "MOFU - Technical Authority",
        "primary_keywords": [
            "merino wool properties", "17 micron fiber", "cut and sewn construction",
            "wool care guide", "merino vs synthetic", "thermal regulation wool",
            "fabric weight guide", "150g vs 190g merino"
        ],
        "protected_topics": ["technical guides", "material science", "fabric comparisons"]
    },
    "perfectmerinoshirt.com": {
        "role": "BOFU Technical - Product Conversion",
        "primary_keywords": [
            "best merino t-shirt", "merino undershirt blazer",
            "no sweat t-shirt", "wrinkle free merino", "travel t-shirt",
            "perfect merino shirt buy", "merino base layer business"
        ],
        "protected_topics": ["product specs", "purchase conversion", "technical landing pages"]
    },
    "albeni1905.com": {
        "role": "BOFU Heritage - Brand Store",
        "primary_keywords": [
            "albeni 1905", "reda wool", "italian luxury t-shirt",
            "made in italy merino", "luxury undershirt", "heritage wool brand",
            "cut & sewn vs knit", "albeni merino"
        ],
        "protected_topics": ["brand identity", "heritage narrative", "e-commerce"]
    }
}

# Semantic Defense keywords (15% focus)
SEMANTIC_DEFENSE_KEYWORDS = [
    "cut & sewn", "cut and sewn vs knit", "17 micron merino",
    "reda 1865", "CompACT technology", "albeni 1905 merino",
    "invisible luxury t-shirt", "superfine merino 17 micron"
]


class SEOMonitor:
    """
    Monitors SEO health across the 4-domain ecosystem.
    Detects cannibalization and ensures 85/15 balance.
    """

    def __init__(self, db: DBSession):
        self.db = db

    async def run_health_check(self, domain: Optional[str] = None) -> List[SEOHealthCheck]:
        """
        Run SEO health check for one or all domains.
        Returns health status with cannibalization alerts.
        """
        domains = [domain] if domain else list(DOMAIN_KEYWORD_MAP.keys())
        results = []

        for d in domains:
            check = await self._check_domain(d)
            results.append(check)

        return results

    async def _check_domain(self, domain: str) -> SEOHealthCheck:
        """Check SEO health for a specific domain."""
        config = DOMAIN_KEYWORD_MAP.get(domain, {})

        # Calculate cannibalization score
        cannibalization = self._detect_cannibalization(domain)

        # Determine alert level
        if cannibalization["score"] > settings.CANNIBALIZATION_CRITICAL:
            alert = "red"
        elif cannibalization["score"] > settings.CANNIBALIZATION_WARNING:
            alert = "yellow"
        else:
            alert = "green"

        # Estimate 85/15 balance based on content distribution
        behavioral_pct, defense_pct = self._estimate_balance(domain)

        return SEOHealthCheck(
            domain=domain,
            behavioral_expansion_pct=behavioral_pct,
            semantic_defense_pct=defense_pct,
            cannibalization_score=cannibalization["score"],
            conflicting_keywords=cannibalization["conflicts"],
            alert_level=alert,
            topical_authority_score=self._estimate_topical_authority(domain)
        )

    def _detect_cannibalization(self, domain: str) -> Dict:
        """
        Detect keyword cannibalization between this domain and others.
        Returns score (0-100) and list of conflicting keywords.
        """
        config = DOMAIN_KEYWORD_MAP.get(domain, {})
        my_keywords = set(k.lower() for k in config.get("primary_keywords", []))
        conflicts = []

        for other_domain, other_config in DOMAIN_KEYWORD_MAP.items():
            if other_domain == domain:
                continue

            other_keywords = set(k.lower() for k in other_config.get("primary_keywords", []))
            overlap = my_keywords & other_keywords

            for kw in overlap:
                conflicts.append(f"{kw} (conflict with {other_domain})")

        # Score: percentage of keywords that overlap
        total_keywords = len(my_keywords) if my_keywords else 1
        score = (len(conflicts) / total_keywords) * 100

        return {
            "score": round(score, 1),
            "conflicts": conflicts
        }

    def _estimate_balance(self, domain: str) -> tuple:
        """
        Estimate the 85/15 balance for a domain.
        Returns (behavioral_pct, defense_pct).
        """
        config = DOMAIN_KEYWORD_MAP.get(domain, {})
        primary_count = len(config.get("primary_keywords", []))

        # Check how many keywords are in semantic defense list
        defense_count = sum(
            1 for kw in config.get("primary_keywords", [])
            if any(sd.lower() in kw.lower() for sd in SEMANTIC_DEFENSE_KEYWORDS)
        )

        if primary_count > 0:
            defense_pct = round((defense_count / primary_count) * 100, 1)
            behavioral_pct = round(100 - defense_pct, 1)
        else:
            behavioral_pct = 85.0
            defense_pct = 15.0

        return behavioral_pct, defense_pct

    def _estimate_topical_authority(self, domain: str) -> float:
        """
        Estimate topical authority score based on content coverage.
        Simplified heuristic (0-100).
        """
        config = DOMAIN_KEYWORD_MAP.get(domain, {})
        keyword_count = len(config.get("primary_keywords", []))
        topic_count = len(config.get("protected_topics", []))

        # Base score from keyword coverage
        base = min(60, keyword_count * 8)
        # Bonus for topic diversity
        bonus = min(40, topic_count * 13)

        return min(100, round(base + bonus, 1))

    def get_canonical_suggestions(self, conflicts: List[str]) -> List[Dict]:
        """
        Generate canonical tag correction suggestions for conflicting keywords.
        """
        suggestions = []
        for conflict in conflicts:
            # Parse the conflict string
            parts = conflict.split(" (conflict with ")
            if len(parts) == 2:
                keyword = parts[0]
                conflicting_domain = parts[1].rstrip(")")

                # Determine which domain should own this keyword
                owner = self._determine_keyword_owner(keyword)

                suggestions.append({
                    "keyword": keyword,
                    "conflicting_domain": conflicting_domain,
                    "suggested_owner": owner,
                    "action": f"Add canonical tag pointing to {owner} for pages targeting '{keyword}'"
                })

        return suggestions

    def _determine_keyword_owner(self, keyword: str) -> str:
        """Determine which domain should own a specific keyword."""
        keyword_lower = keyword.lower()

        # Check semantic defense keywords first
        if any(sd.lower() in keyword_lower for sd in SEMANTIC_DEFENSE_KEYWORDS):
            return "merinouniversity.com"  # Technical authority owns defense keywords

        # Score each domain based on keyword relevance
        scores = {}
        for domain, config in DOMAIN_KEYWORD_MAP.items():
            score = sum(
                1 for pk in config["primary_keywords"]
                if keyword_lower in pk.lower() or pk.lower() in keyword_lower
            )
            scores[domain] = score

        if scores:
            return max(scores, key=scores.get)
        return "worldofmerino.com"  # Default to TOFU domain
