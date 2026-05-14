"""
SEO Balance Monitor & Anti-Cannibalization Engine — LIVE EDITION (14 mag 2026).

Manages the 85/15 balance model and detects keyword conflicts between domains
using LIVE data from SEMrush + Redis cache (TTL 1h to spare API units).

Pre-14-mag-2026: balance/cannibalization were calculated against static keyword
maps hardcoded below. The dashboard "SEO Health" widget literally showed those
hardcoded values (85/15/<6%). Now both backend and widget consume SEMrush data.

Per-domain SEMrush market mapping:
- worldofmerino.com  → "us" (lifestyle internazionale, niente rank IT)
- merinouniversity.com → "it" (educational, italiano)
- perfectmerinoshirt.com → "us" (commerciale US/EN)
- albeni1905.com → "it" (e-commerce italiano)
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session as DBSession

from config import get_settings
from models.schemas import SEOHealthCheck
from services.semrush_agent import SemrushAgent

logger = logging.getLogger(__name__)
settings = get_settings()

# Domain-role mapping (statico — definisce ruolo strategico e mercato SEMrush)
DOMAIN_KEYWORD_MAP = {
    "worldofmerino.com": {
        "role": "TOFU - Lifestyle & Discovery",
        "funnel_stage": "TOFU",
        "semrush_database": "us",
        # legacy hint list (used as fallback se SEMrush ritorna 0 keyword)
        "primary_keywords": [
            "world of merino", "merino wool benefits", "natural fibers",
            "sustainable fashion", "wool vs cotton", "merino lifestyle",
            "invisible luxury", "ethical clothing"
        ],
        "protected_topics": ["merino education", "brand storytelling", "lifestyle content"]
    },
    "merinouniversity.com": {
        "role": "MOFU - Technical Authority",
        "funnel_stage": "MOFU",
        "semrush_database": "it",
        "primary_keywords": [
            "merino wool properties", "17 micron fiber", "cut and sewn construction",
            "wool care guide", "merino vs synthetic", "thermal regulation wool",
            "fabric weight guide", "150g vs 190g merino"
        ],
        "protected_topics": ["technical guides", "material science", "fabric comparisons"]
    },
    "perfectmerinoshirt.com": {
        "role": "BOFU Technical - Product Conversion",
        "funnel_stage": "BOFU",
        "semrush_database": "us",
        "primary_keywords": [
            "best merino t-shirt", "merino undershirt blazer",
            "no sweat t-shirt", "wrinkle free merino", "travel t-shirt",
            "perfect merino shirt buy", "merino base layer business"
        ],
        "protected_topics": ["product specs", "purchase conversion", "technical landing pages"]
    },
    "albeni1905.com": {
        "role": "BOFU Heritage - Brand Store",
        "funnel_stage": "BOFU",
        "semrush_database": "it",
        "primary_keywords": [
            "albeni 1905", "reda wool", "italian luxury t-shirt",
            "made in italy merino", "luxury undershirt", "heritage wool brand",
            "cut & sewn vs knit", "albeni merino"
        ],
        "protected_topics": ["brand identity", "heritage narrative", "e-commerce"]
    }
}

# Semantic Defense keywords (15% focus — usate per matching contro le keyword in rank reali)
SEMANTIC_DEFENSE_KEYWORDS = [
    "cut & sewn", "cut and sewn", "17 micron", "reda 1865", "reda merino",
    "compact technology", "invisible luxury", "superfine merino",
    "albeni 1905", "albeni merino", "made in italy merino",
    "italian merino", "italian luxury",
]

# Redis cache TTL: SEMrush API units are limited; data SEO non cambia per minuti
SEO_HEALTH_CACHE_TTL = 3600  # 1 hour
SEO_HEALTH_CACHE_KEY_PREFIX = "seo_health:v2:"


class SEOMonitor:
    """
    Monitors SEO health across the 4-domain ecosystem using LIVE SEMrush data.

    Architecture:
    - Per domain: fetch top-N organic keywords from SEMrush (cached 1h in Redis)
    - behavioral_expansion_pct / semantic_defense_pct: real ratio of in-rank keywords
      matching the SEMANTIC_DEFENSE_KEYWORDS list
    - cannibalization_score: % of in-rank keywords that also appear in another
      Albeni domain's in-rank set
    - topical_authority_score: SEMrush authority_score from backlinks_overview

    Fallback policy: if SEMrush returns 0 keywords or errors out for a domain,
    SEOHealthCheck.data_source becomes "fallback" and percentages fall back to
    the static keyword-map heuristic (so the widget never breaks).
    """

    def __init__(self, db: DBSession, redis_client=None, semrush_agent: Optional[SemrushAgent] = None):
        self.db = db
        self.redis = redis_client  # may be None (callers can omit for sync/test paths)
        self.semrush = semrush_agent or SemrushAgent()

    async def run_health_check(self, domain: Optional[str] = None) -> List[SEOHealthCheck]:
        """Run SEO health check for one or all domains (live SEMrush + Redis cache)."""
        domains = [domain] if domain else list(DOMAIN_KEYWORD_MAP.keys())

        # First pass: fetch (or load from cache) the in-rank keyword set per domain.
        # We need ALL of them to compute cross-domain cannibalization.
        per_domain_data: Dict[str, Dict] = {}
        for d in domains:
            per_domain_data[d] = await self._fetch_domain_data(d)

        # Second pass: compute health checks (cannibalization needs cross-domain view)
        results: List[SEOHealthCheck] = []
        for d in domains:
            results.append(self._compile_health(d, per_domain_data))
        return results

    # -------------------------------------------------------------------------
    # DATA FETCH (live + cached)
    # -------------------------------------------------------------------------
    async def _fetch_domain_data(self, domain: str) -> Dict:
        """Fetch all SEMrush data needed for one domain. Cached in Redis (1h TTL)."""
        cache_key = f"{SEO_HEALTH_CACHE_KEY_PREFIX}{domain}"
        if self.redis:
            try:
                cached_raw = await self.redis.get(cache_key)
                if cached_raw:
                    data = json.loads(cached_raw)
                    data["_source"] = "cached"
                    return data
            except Exception as e:
                logger.warning(f"Redis cache read failed for {domain}: {e}")

        config = DOMAIN_KEYWORD_MAP.get(domain, {})
        database = config.get("semrush_database", "us")
        keywords: List[Dict] = []
        organic_traffic = 0
        authority = 0
        source = "live"

        # 1) organic keywords in rank (top 100)
        try:
            kw_response = await self.semrush.get_organic_keywords(domain, database, limit=100)
            keywords = kw_response.get("keywords", []) if isinstance(kw_response, dict) else []
        except Exception as e:
            logger.warning(f"SEMrush organic_keywords failed for {domain}: {e}")
            keywords = []

        # 2) domain overview (traffic, organic count) — best-effort
        try:
            overview = await self.semrush.get_domain_overview(domain, database)
            organic_traffic = int(overview.get("organic_traffic", 0)) if isinstance(overview, dict) else 0
        except Exception as e:
            logger.warning(f"SEMrush domain_overview failed for {domain}: {e}")

        # 3) authority score from backlinks
        try:
            backlinks = await self.semrush.get_backlinks_overview(domain)
            authority = int(backlinks.get("authority_score", 0)) if isinstance(backlinks, dict) else 0
        except Exception as e:
            logger.warning(f"SEMrush backlinks failed for {domain}: {e}")

        # If SEMrush returned no rank data at all, mark as fallback so the
        # caller can switch to the static-map heuristic.
        if not keywords and organic_traffic == 0 and authority == 0:
            source = "fallback"

        data = {
            "domain": domain,
            "database": database,
            "keywords": keywords,           # list of dicts with "keyword", "position", "search_volume", ...
            "organic_traffic": organic_traffic,
            "authority_score": authority,
            "_source": source,
        }

        # Cache (skip if fallback so we re-try next time API quota recovers)
        if self.redis and source == "live":
            try:
                await self.redis.setex(cache_key, SEO_HEALTH_CACHE_TTL, json.dumps(data))
            except Exception as e:
                logger.warning(f"Redis cache write failed for {domain}: {e}")
        return data

    # -------------------------------------------------------------------------
    # COMPILE — combina i dati per produrre il SEOHealthCheck finale
    # -------------------------------------------------------------------------
    def _compile_health(self, domain: str, per_domain_data: Dict[str, Dict]) -> SEOHealthCheck:
        config = DOMAIN_KEYWORD_MAP.get(domain, {})
        my_data = per_domain_data.get(domain, {})
        my_keywords = my_data.get("keywords", [])
        source = my_data.get("_source", "live")

        # 1) Balance behavioral / defense
        if my_keywords:
            behavioral_pct, defense_pct = self._compute_balance_from_keywords(my_keywords)
        else:
            # Fallback: deduzione dalla mappa statica
            behavioral_pct, defense_pct = self._compute_balance_from_static_map(domain)

        # 2) Cannibalization: % di keyword in rank che compaiono ANCHE nel rank
        #    di un altro dominio Albeni (con posizione utile, <= 30).
        cann_score, conflicts = self._compute_cannibalization(domain, per_domain_data)

        # 3) Alert level
        if cann_score > settings.CANNIBALIZATION_CRITICAL:
            alert = "red"
        elif cann_score > settings.CANNIBALIZATION_WARNING:
            alert = "yellow"
        else:
            alert = "green"

        # 4) Topical authority: prima preferenza = SEMrush authority_score;
        #    se 0/mancante, ripiega sul calcolo euristico — ma NON marcare l'intera
        #    misurazione come fallback solo per questo (l'authority è un dato
        #    accessorio, le keyword in rank sono la fonte primaria).
        authority = my_data.get("authority_score", 0)
        if not authority:
            authority = self._estimate_topical_authority_heuristic(domain)
        # source rimane quello determinato da _fetch_domain_data: 'live' se SEMrush
        # ha risposto keyword o traffic, 'fallback' solo se TUTTE le call sono vuote.

        return SEOHealthCheck(
            domain=domain,
            role=config.get("role"),
            funnel_stage=config.get("funnel_stage"),
            behavioral_expansion_pct=behavioral_pct,
            semantic_defense_pct=defense_pct,
            cannibalization_score=cann_score,
            conflicting_keywords=conflicts[:20],  # top 20 per evitare payload enormi
            alert_level=alert,
            topical_authority_score=float(authority),
            keywords_in_rank=len(my_keywords),
            organic_traffic=int(my_data.get("organic_traffic", 0)),
            authority_score=int(my_data.get("authority_score", 0)),
            semrush_database=my_data.get("database", config.get("semrush_database", "")),
            data_source=source,
            fetched_at=datetime.utcnow().isoformat() + "Z",
        )

    # -------------------------------------------------------------------------
    # COMPUTATION helpers (pure functions, no I/O)
    # -------------------------------------------------------------------------
    def _compute_balance_from_keywords(self, keywords: List[Dict]) -> Tuple[float, float]:
        """Calcola behavioral_pct / defense_pct dai keyword in rank reali."""
        if not keywords:
            return 85.0, 15.0
        defense_count = 0
        for kw_entry in keywords:
            kw = (kw_entry.get("keyword") or "").lower()
            if any(sd.lower() in kw for sd in SEMANTIC_DEFENSE_KEYWORDS):
                defense_count += 1
        total = len(keywords)
        defense_pct = round((defense_count / total) * 100, 1)
        behavioral_pct = round(100 - defense_pct, 1)
        return behavioral_pct, defense_pct

    def _compute_balance_from_static_map(self, domain: str) -> Tuple[float, float]:
        """Fallback se SEMrush non dà rank: misurazione contro la mappa statica."""
        config = DOMAIN_KEYWORD_MAP.get(domain, {})
        primary = config.get("primary_keywords", [])
        if not primary:
            return 85.0, 15.0
        defense_count = sum(
            1 for kw in primary
            if any(sd.lower() in kw.lower() for sd in SEMANTIC_DEFENSE_KEYWORDS)
        )
        defense_pct = round((defense_count / len(primary)) * 100, 1)
        behavioral_pct = round(100 - defense_pct, 1)
        return behavioral_pct, defense_pct

    def _compute_cannibalization(self, domain: str, per_domain_data: Dict[str, Dict]) -> Tuple[float, List[str]]:
        """Cross-domain overlap: keyword in rank presenti su >1 dominio Albeni (top 30)."""
        my_kws = {
            (k.get("keyword") or "").lower().strip()
            for k in per_domain_data.get(domain, {}).get("keywords", [])
            if self._kw_in_useful_position(k)
        }
        my_kws.discard("")
        if not my_kws:
            return 0.0, []
        conflicts: List[str] = []
        for other_domain, other_data in per_domain_data.items():
            if other_domain == domain:
                continue
            other_kws = {
                (k.get("keyword") or "").lower().strip()
                for k in other_data.get("keywords", [])
                if self._kw_in_useful_position(k)
            }
            overlap = my_kws & other_kws
            for kw in sorted(overlap):
                conflicts.append(f"{kw} (conflict with {other_domain})")
        score = round((len(conflicts) / len(my_kws)) * 100, 1)
        return score, conflicts

    @staticmethod
    def _kw_in_useful_position(kw_entry: Dict) -> bool:
        """Una keyword conta come 'in rank utile' se è in top 30 (Po <= 30)."""
        try:
            pos = int(kw_entry.get("position", 0) or 0)
            return 1 <= pos <= 30
        except (TypeError, ValueError):
            return False

    def _estimate_topical_authority_heuristic(self, domain: str) -> float:
        """Fallback heuristic se SEMrush authority_score non è disponibile."""
        config = DOMAIN_KEYWORD_MAP.get(domain, {})
        keyword_count = len(config.get("primary_keywords", []))
        topic_count = len(config.get("protected_topics", []))
        base = min(60, keyword_count * 8)
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
