"""
ADV Intelligence Layer — Signal Feedback Loop
Albeni 1905 — Invisible Luxury Ecosystem

Cattura i segnali ADV (UTM, gclid, fbclid) e orchestra:
1. UTM Sensor: decodifica la provenienza dell'utente (Google/Meta/Organic)
2. Signal Feedback Loop: quando l'IDS è alto, invia conversioni di qualità
   a Google Offline Conversions API e Meta CAPI
3. Budget Guardian: monitora spend vs quality per ottimizzare il budget €250/mese
4. Cross-Domain Attribution: traccia il percorso TOFU→MOFU→BOFU cross-dominio
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis
from sqlalchemy.orm import Session as DBSession

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Redis TTLs
REDIS_SESSION_TTL = 1800       # 30 min — sessione utente attiva
REDIS_IDS_TTL = 86400          # 24 ore — IDS score cache
REDIS_CLICK_TTL = 604800       # 7 giorni — click ID → user mapping


# ================================================================
# UTM SENSOR — Decodifica Provenienza
# ================================================================

class UTMSensor:
    """Parses and enriches UTM/campaign data from frontend tracking."""

    # Mapping utm_source → canonical source
    SOURCE_MAP = {
        "google": "google_ads",
        "google_ads": "google_ads",
        "googleads": "google_ads",
        "meta": "meta_ads",
        "facebook": "meta_ads",
        "instagram": "meta_ads",
        "fb": "meta_ads",
        "ig": "meta_ads",
        "newsletter": "email",
        "klaviyo": "email",
        "organic": "organic",
        "direct": "direct",
    }

    # Intent mapping per medium
    INTENT_MAP = {
        "cpc": "search_intent",       # Google Search Ads
        "ppc": "search_intent",
        "search": "search_intent",
        "dpa": "social_intent",        # Meta Dynamic Product Ads
        "social": "social_intent",
        "display": "display_intent",   # Google Display Network
        "video": "video_intent",       # YouTube Ads
        "email": "email_intent",       # Newsletter traffic
        "retargeting": "retargeting",
    }

    # Albeni domain → funnel stage
    DOMAIN_STAGE = {
        "worldofmerino.com": "TOFU",
        "merinouniversity.com": "MOFU",
        "perfectmerinoshirt.com": "BOFU",
        "albeni1905.com": "BOFU_HERITAGE",
    }

    @staticmethod
    def parse(campaign_data: Dict) -> Dict[str, Any]:
        """
        Parse raw UTM/campaign data into enriched signal.

        Input (from frontend JS):
            {source, medium, term, content, campaign, gclid, fbclid, landing_domain, page_url}

        Output:
            {canonical_source, intent_type, funnel_stage, is_paid, keyword, ad_id, ...}
        """
        source_raw = (campaign_data.get("source") or "").lower().strip()
        medium_raw = (campaign_data.get("medium") or "").lower().strip()
        gclid = campaign_data.get("gclid")
        fbclid = campaign_data.get("fbclid")

        # Canonical source detection
        canonical_source = UTMSensor.SOURCE_MAP.get(source_raw, "unknown")

        # Auto-detect from click IDs if UTMs are missing
        if canonical_source == "unknown":
            if gclid:
                canonical_source = "google_ads"
            elif fbclid:
                canonical_source = "meta_ads"

        # Intent type
        intent_type = UTMSensor.INTENT_MAP.get(medium_raw, "unknown")
        if intent_type == "unknown" and canonical_source == "google_ads":
            intent_type = "search_intent"
        elif intent_type == "unknown" and canonical_source == "meta_ads":
            intent_type = "social_intent"

        # Funnel stage from landing domain
        landing_domain = (campaign_data.get("landing_domain") or "").lower()
        funnel_stage = "unknown"
        for domain, stage in UTMSensor.DOMAIN_STAGE.items():
            if domain in landing_domain:
                funnel_stage = stage
                break

        # Is this paid traffic?
        is_paid = canonical_source in ("google_ads", "meta_ads") or bool(gclid) or bool(fbclid)

        return {
            "canonical_source": canonical_source,
            "intent_type": intent_type,
            "funnel_stage": funnel_stage,
            "is_paid": is_paid,
            "keyword": campaign_data.get("term"),
            "ad_content": campaign_data.get("content"),
            "campaign_name": campaign_data.get("campaign"),
            "gclid": gclid,
            "fbclid": fbclid,
            "landing_domain": landing_domain,
            "raw_source": source_raw,
            "raw_medium": medium_raw,
            "parsed_at": datetime.utcnow().isoformat(),
        }


# ================================================================
# SIGNAL FEEDBACK LOOP — IDS-Based Quality Signals
# ================================================================

class SignalFeedbackLoop:
    """
    Sends quality signals back to ad platforms based on IDS score.

    - IDS > 70 → "High Quality Lead" → Google Offline Conversion / Meta CAPI
    - IDS < 10 after 3+ pages → "Low Quality" → negative signal for optimization
    - Cluster detected → enriches conversion value for platform optimization
    """

    # Conversion value mapping per cluster (weighted by LTV potential)
    CLUSTER_CONVERSION_VALUES = {
        "business_professional": 85.0,   # Highest LTV
        "heritage_mature": 75.0,
        "conscious_premium": 65.0,
        "modern_minimalist": 55.0,
        "italian_authentic": 70.0,
    }

    def __init__(self):
        self._feedback_log: List[Dict] = []

    async def process(
        self,
        user_id: str,
        ids_score: float,
        campaign_data: Dict,
        cluster: Optional[str] = None,
        page_views: int = 0,
    ) -> Dict[str, Any]:
        """
        Process IDS score and send appropriate feedback to ad platforms.

        Returns:
            {action, platform, conversion_value, details}
        """
        result = {
            "user_id": user_id,
            "ids_score": ids_score,
            "action": "none",
            "platform": campaign_data.get("canonical_source", "unknown"),
            "conversion_value": 0.0,
            "details": {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        # HIGH QUALITY: IDS > threshold → send positive conversion
        if ids_score > settings.ADV_IDS_HIGH_QUALITY_THRESHOLD:
            conversion_value = self.CLUSTER_CONVERSION_VALUES.get(cluster, 50.0)

            # Scale by IDS (70-100 → 70%-100% of base value)
            value_multiplier = min(ids_score / 100.0, 1.0)
            final_value = round(conversion_value * value_multiplier, 2)

            result["action"] = "high_quality_conversion"
            result["conversion_value"] = final_value

            if campaign_data.get("canonical_source") == "google_ads" and campaign_data.get("gclid"):
                result["details"] = await self._send_google_conversion(
                    gclid=campaign_data["gclid"],
                    conversion_value=final_value,
                    conversion_action="High_Quality_Lead",
                    cluster=cluster,
                )

            elif campaign_data.get("canonical_source") == "meta_ads":
                result["details"] = await self._send_meta_conversion(
                    user_id=user_id,
                    event_name="QualifiedProspect",
                    conversion_value=final_value,
                    campaign_data=campaign_data,
                    cluster=cluster,
                )

        # LOW QUALITY: IDS < threshold after 3+ pages → negative signal
        elif ids_score < settings.ADV_IDS_LOW_QUALITY_THRESHOLD and page_views >= 3:
            result["action"] = "low_quality_signal"
            result["details"] = {
                "reason": "Low engagement after multiple page views",
                "ids_score": ids_score,
                "page_views": page_views,
                "recommendation": "Exclude from remarketing audiences",
            }

        # MEDIUM: Building intent, no action yet
        else:
            result["action"] = "monitoring"
            result["details"] = {
                "ids_score": ids_score,
                "next_threshold": settings.ADV_IDS_HIGH_QUALITY_THRESHOLD,
                "gap": settings.ADV_IDS_HIGH_QUALITY_THRESHOLD - ids_score,
            }

        self._feedback_log.append(result)
        return result

    async def _send_google_conversion(
        self,
        gclid: str,
        conversion_value: float,
        conversion_action: str,
        cluster: Optional[str] = None,
    ) -> Dict:
        """
        Send offline conversion to Google Ads API.
        Requires: GOOGLE_ADS_CUSTOMER_ID, GOOGLE_ADS_DEVELOPER_TOKEN, etc.
        """
        if not settings.GOOGLE_ADS_CUSTOMER_ID:
            logger.info(f"Google Ads conversion SIMULATED: gclid={gclid[:12]}... value={conversion_value}")
            return {
                "status": "simulated",
                "platform": "google_ads",
                "gclid": gclid[:12] + "...",
                "conversion_action": conversion_action,
                "conversion_value": conversion_value,
                "cluster": cluster,
                "note": "Configura GOOGLE_ADS_CUSTOMER_ID nel .env per attivare",
            }

        try:
            import httpx

            # Google Ads Offline Conversions API
            # In produzione: usare google-ads-python client library
            payload = {
                "conversions": [{
                    "gclid": gclid,
                    "conversion_action": f"customers/{settings.GOOGLE_ADS_CUSTOMER_ID}/conversionActions/{settings.GOOGLE_ADS_CONVERSION_ACTION_ID}",
                    "conversion_date_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S+00:00"),
                    "conversion_value": conversion_value,
                    "currency_code": "EUR",
                    "custom_variables": {
                        "cluster": cluster or "unknown",
                        "source": "albeni_ai_layer",
                    },
                }],
                "partial_failure": True,
            }

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://googleads.googleapis.com/v16/customers/{settings.GOOGLE_ADS_CUSTOMER_ID}:uploadOfflineUserDataJobs",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {settings.GOOGLE_ADS_REFRESH_TOKEN}",
                        "developer-token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                    },
                    timeout=10.0,
                )

                return {
                    "status": "sent" if resp.status_code < 300 else "error",
                    "platform": "google_ads",
                    "http_status": resp.status_code,
                    "conversion_action": conversion_action,
                    "conversion_value": conversion_value,
                }

        except Exception as e:
            logger.error(f"Google Ads conversion error: {e}")
            return {"status": "error", "platform": "google_ads", "error": str(e)}

    async def _send_meta_conversion(
        self,
        user_id: str,
        event_name: str,
        conversion_value: float,
        campaign_data: Dict,
        cluster: Optional[str] = None,
    ) -> Dict:
        """
        Send conversion event to Meta Conversions API (CAPI).
        Requires: META_PIXEL_ID, META_ACCESS_TOKEN
        """
        if not settings.META_PIXEL_ID:
            logger.info(f"Meta CAPI conversion SIMULATED: user={user_id} event={event_name} value={conversion_value}")
            return {
                "status": "simulated",
                "platform": "meta_capi",
                "event_name": event_name,
                "conversion_value": conversion_value,
                "cluster": cluster,
                "note": "Configura META_PIXEL_ID e META_ACCESS_TOKEN nel .env per attivare",
            }

        try:
            import httpx

            # Hash user_id for privacy (Meta requires SHA256)
            hashed_id = hashlib.sha256(user_id.encode()).hexdigest()

            event_data = {
                "data": [{
                    "event_name": event_name,
                    "event_time": int(time.time()),
                    "action_source": "website",
                    "user_data": {
                        "external_id": [hashed_id],
                        "fbp": campaign_data.get("fbclid", ""),
                    },
                    "custom_data": {
                        "value": conversion_value,
                        "currency": "EUR",
                        "content_type": "product",
                        "cluster": cluster or "unknown",
                        "ids_source": "albeni_ai_layer",
                    },
                }],
            }

            # Add test event code for sandbox testing
            if settings.META_TEST_EVENT_CODE:
                event_data["test_event_code"] = settings.META_TEST_EVENT_CODE

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://graph.facebook.com/v19.0/{settings.META_PIXEL_ID}/events",
                    json=event_data,
                    params={"access_token": settings.META_ACCESS_TOKEN},
                    timeout=10.0,
                )

                return {
                    "status": "sent" if resp.status_code < 300 else "error",
                    "platform": "meta_capi",
                    "http_status": resp.status_code,
                    "event_name": event_name,
                    "conversion_value": conversion_value,
                }

        except Exception as e:
            logger.error(f"Meta CAPI conversion error: {e}")
            return {"status": "error", "platform": "meta_capi", "error": str(e)}

    def get_stats(self) -> Dict:
        """Get feedback loop statistics."""
        total = len(self._feedback_log)
        high_quality = sum(1 for f in self._feedback_log if f["action"] == "high_quality_conversion")
        low_quality = sum(1 for f in self._feedback_log if f["action"] == "low_quality_signal")
        monitoring = sum(1 for f in self._feedback_log if f["action"] == "monitoring")
        total_value = sum(f.get("conversion_value", 0) for f in self._feedback_log)

        by_platform = {}
        for f in self._feedback_log:
            p = f.get("platform", "unknown")
            by_platform[p] = by_platform.get(p, 0) + 1

        return {
            "total_signals": total,
            "high_quality": high_quality,
            "low_quality": low_quality,
            "monitoring": monitoring,
            "total_conversion_value_eur": round(total_value, 2),
            "by_platform": by_platform,
            "quality_rate": round(high_quality / max(total, 1) * 100, 1),
        }


# ================================================================
# CROSS-DOMAIN ATTRIBUTION
# ================================================================

class CrossDomainAttribution:
    """
    Tracks user journeys across the 4 Albeni domains.
    Maps TOFU→MOFU→BOFU progression with ADV source attribution.
    """

    def __init__(self):
        self._journeys: Dict[str, List[Dict]] = {}  # user_id → touchpoints

    def track_touchpoint(
        self,
        user_id: str,
        domain: str,
        campaign_data: Dict,
        ids_score: float,
    ) -> Dict:
        """Record a touchpoint in the user's cross-domain journey."""
        if user_id not in self._journeys:
            self._journeys[user_id] = []

        stage = UTMSensor.DOMAIN_STAGE.get(domain, "unknown")

        touchpoint = {
            "domain": domain,
            "stage": stage,
            "source": campaign_data.get("canonical_source", "organic"),
            "keyword": campaign_data.get("keyword"),
            "ids_score": ids_score,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self._journeys[user_id].append(touchpoint)

        # Analyze progression
        stages_visited = [t["stage"] for t in self._journeys[user_id]]
        progression = self._analyze_progression(stages_visited)

        return {
            "user_id": user_id,
            "touchpoint": touchpoint,
            "journey_length": len(self._journeys[user_id]),
            "stages_visited": list(set(stages_visited)),
            "progression": progression,
        }

    def _analyze_progression(self, stages: List[str]) -> Dict:
        """Analyze funnel progression from touchpoint stages."""
        stage_order = {"TOFU": 1, "MOFU": 2, "BOFU": 3, "BOFU_HERITAGE": 3}
        ordered = [stage_order.get(s, 0) for s in stages if s in stage_order]

        if not ordered:
            return {"type": "unknown", "funnel_depth": 0}

        max_depth = max(ordered)
        is_progressing = len(ordered) > 1 and ordered[-1] >= ordered[-2]

        return {
            "type": "progressing" if is_progressing else "exploring",
            "funnel_depth": max_depth,
            "max_stage": {1: "TOFU", 2: "MOFU", 3: "BOFU"}.get(max_depth, "unknown"),
            "total_touchpoints": len(stages),
            "cross_domain": len(set(stages)) > 1,
        }

    def get_journey(self, user_id: str) -> List[Dict]:
        """Get full journey for a user."""
        return self._journeys.get(user_id, [])

    def get_stats(self) -> Dict:
        """Attribution stats."""
        total_users = len(self._journeys)
        cross_domain = sum(
            1 for j in self._journeys.values()
            if len(set(t["domain"] for t in j)) > 1
        )
        avg_touchpoints = (
            sum(len(j) for j in self._journeys.values()) / max(total_users, 1)
        )

        return {
            "total_tracked_users": total_users,
            "cross_domain_journeys": cross_domain,
            "avg_touchpoints": round(avg_touchpoints, 1),
            "cross_domain_rate": round(cross_domain / max(total_users, 1) * 100, 1),
        }


# ================================================================
# ADV INTELLIGENCE SERVICE (Unified Interface)
# ================================================================

class ADVIntelligence:
    """
    Unified ADV Intelligence service combining:
    - UTM Sensor
    - Signal Feedback Loop (in-memory + Postgres for persistence)
    - Cross-Domain Attribution (in-memory + Postgres)
    - Redis Fast Layer (sessions, IDS cache, click ID mapping)
    """

    def __init__(self, redis_client: Optional[aioredis.Redis] = None, db: Optional[DBSession] = None):
        self.sensor = UTMSensor()
        self.feedback = SignalFeedbackLoop()
        self.attribution = CrossDomainAttribution()
        self.redis = redis_client
        self.db = db
        logger.info("ADV Intelligence Layer initialized (Redis=%s, DB=%s)",
                     "connected" if redis_client else "none",
                     "connected" if db else "none")

    # ================================================================
    # REDIS FAST LAYER
    # ================================================================

    async def _redis_set_session(self, user_id: str, session_data: Dict):
        """Store user ADV session in Redis (TTL 30 min)."""
        if not self.redis:
            return
        try:
            key = f"user:{user_id}:adv_session"
            await self.redis.set(key, json.dumps(session_data, default=str), ex=REDIS_SESSION_TTL)
        except Exception as e:
            logger.warning(f"Redis set session failed: {e}")

    async def _redis_get_session(self, user_id: str) -> Optional[Dict]:
        """Get user ADV session from Redis."""
        if not self.redis:
            return None
        try:
            key = f"user:{user_id}:adv_session"
            data = await self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.warning(f"Redis get session failed: {e}")
            return None

    async def _redis_map_click_id(self, click_id: str, user_id: str, source: str):
        """Map click ID (gclid/fbclid) to user ID in Redis (TTL 7 days)."""
        if not self.redis or not click_id:
            return
        try:
            key = f"click:{click_id}"
            data = json.dumps({"user_id": user_id, "source": source, "mapped_at": datetime.utcnow().isoformat()})
            await self.redis.set(key, data, ex=REDIS_CLICK_TTL)
        except Exception as e:
            logger.warning(f"Redis map click_id failed: {e}")

    async def _redis_resolve_click_id(self, click_id: str) -> Optional[Dict]:
        """Resolve a click ID to user info from Redis."""
        if not self.redis or not click_id:
            return None
        try:
            key = f"click:{click_id}"
            data = await self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.warning(f"Redis resolve click_id failed: {e}")
            return None

    async def _redis_cache_ids(self, user_id: str, ids_score: float):
        """Cache current IDS score in Redis (TTL 24h)."""
        if not self.redis:
            return
        try:
            key = f"user:{user_id}:ids"
            await self.redis.set(key, str(int(ids_score)), ex=REDIS_IDS_TTL)
        except Exception as e:
            logger.warning(f"Redis cache IDS failed: {e}")

    # ================================================================
    # POSTGRES PERSISTENCE
    # ================================================================

    def _persist_attribution(self, user_id: str, parsed: Dict, ids_score: float):
        """Persist marketing attribution to Postgres."""
        if not self.db:
            return
        try:
            from models.database import MarketingAttribution
            click_id = parsed.get("gclid") or parsed.get("fbclid")
            if not click_id:
                return  # Only persist paid clicks with IDs

            attr = MarketingAttribution(
                source=parsed.get("canonical_source", "unknown"),
                medium=parsed.get("raw_medium"),
                campaign_name=parsed.get("campaign_name"),
                keyword=parsed.get("keyword"),
                ad_content=parsed.get("ad_content"),
                click_id=click_id,
                click_id_type="gclid" if parsed.get("gclid") else "fbclid",
                landing_domain=parsed.get("landing_domain"),
                device_type="unknown",
                intent_type=parsed.get("intent_type"),
                ids_at_click=int(ids_score),
            )
            self.db.add(attr)
            self.db.commit()
            logger.info(f"Attribution persisted: click_id={click_id[:12]}...")
        except Exception as e:
            logger.warning(f"Attribution persist failed: {e}")
            try:
                self.db.rollback()
            except Exception:
                pass

    def _persist_intent_log(self, user_id: str, domain: str, event_type: str,
                            event_value: Dict, ids_impact: int, click_id: Optional[str], source: str):
        """Persist user intent log to Postgres."""
        if not self.db:
            return
        try:
            from models.database import UserIntentLog
            log = UserIntentLog(
                domain=domain,
                event_type=event_type,
                event_value=event_value,
                ids_impact=ids_impact,
                campaign_click_id=click_id,
                source=source,
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.warning(f"Intent log persist failed: {e}")
            try:
                self.db.rollback()
            except Exception:
                pass

    # ================================================================
    # MAIN PIPELINE
    # ================================================================

    async def process_event(
        self,
        user_id: str,
        ids_score: float,
        raw_campaign_data: Dict,
        cluster: Optional[str] = None,
        page_views: int = 0,
    ) -> Dict[str, Any]:
        """
        Full ADV intelligence pipeline:
        1. Parse UTM/campaign data
        2. Store in Redis (fast layer) + Postgres (persistent layer)
        3. Track cross-domain touchpoint
        4. Process signal feedback loop
        """
        # 1. Parse campaign data
        parsed = UTMSensor.parse(raw_campaign_data)

        # 2. Redis: store session + map click ID + cache IDS
        click_id = parsed.get("gclid") or parsed.get("fbclid")
        await self._redis_set_session(user_id, {
            "uid": user_id,
            "source": parsed.get("canonical_source"),
            "gclid": parsed.get("gclid"),
            "fbclid": parsed.get("fbclid"),
            "initial_landing": parsed.get("landing_domain"),
            "current_score": str(int(ids_score)),
            "last_event": f"page_view_{raw_campaign_data.get('landing_domain', '')}",
        })
        if click_id:
            await self._redis_map_click_id(click_id, user_id, parsed.get("canonical_source", "unknown"))
        await self._redis_cache_ids(user_id, ids_score)

        # 3. Postgres: persist attribution + intent log
        self._persist_attribution(user_id, parsed, ids_score)
        domain = raw_campaign_data.get("landing_domain", "")
        self._persist_intent_log(
            user_id=user_id,
            domain=domain,
            event_type="adv_click",
            event_value={"campaign": parsed.get("campaign_name"), "keyword": parsed.get("keyword")},
            ids_impact=0,
            click_id=click_id,
            source=parsed.get("canonical_source", "unknown"),
        )

        # 4. Track attribution (in-memory for real-time stats)
        attribution = self.attribution.track_touchpoint(
            user_id=user_id,
            domain=domain,
            campaign_data=parsed,
            ids_score=ids_score,
        )

        # 5. Signal feedback
        feedback = await self.feedback.process(
            user_id=user_id,
            ids_score=ids_score,
            campaign_data=parsed,
            cluster=cluster,
            page_views=page_views,
        )

        # 6. If conversion sent, update Postgres attribution record
        if feedback.get("action") == "high_quality_conversion" and click_id and self.db:
            try:
                from models.database import MarketingAttribution
                attr = self.db.query(MarketingAttribution).filter_by(click_id=click_id).first()
                if attr:
                    attr.converted = True
                    attr.conversion_value = feedback.get("conversion_value", 0)
                    attr.conversion_sent_at = datetime.utcnow()
                    self.db.commit()
            except Exception as e:
                logger.warning(f"Attribution conversion update failed: {e}")

        return {
            "parsed_campaign": parsed,
            "attribution": attribution,
            "feedback": feedback,
            "redis_cached": bool(self.redis),
            "postgres_persisted": bool(self.db),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_stats(self) -> Dict:
        """Combined stats from all ADV subsystems."""
        return {
            "feedback_loop": self.feedback.get_stats(),
            "attribution": self.attribution.get_stats(),
            "config": {
                "high_quality_threshold": settings.ADV_IDS_HIGH_QUALITY_THRESHOLD,
                "low_quality_threshold": settings.ADV_IDS_LOW_QUALITY_THRESHOLD,
                "monthly_budget_eur": settings.ADV_BUDGET_MONTHLY_EUR,
                "google_ads_configured": bool(settings.GOOGLE_ADS_CUSTOMER_ID),
                "meta_capi_configured": bool(settings.META_PIXEL_ID),
                "redis_connected": bool(self.redis),
                "postgres_connected": bool(self.db),
            },
        }
