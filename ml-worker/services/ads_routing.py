"""
Dynamic ADV Routing — Intelligent Landing & Cross-Domain Shift
Albeni 1905 — Invisible Luxury Ecosystem

Decide dove mandare l'utente in base a:
1. Source (Google Ads vs Meta Ads vs Organic)
2. Intent (search_intent vs social_intent)
3. Keyword (informative vs transactional)
4. IDS Score (se alto → shift verso BOFU)
5. Cluster (personalizzazione del messaggio)

Regole:
- Search Intent "informative" → worldofmerino.com (TOFU)
- Search Intent "transactional" → albeni1905.com o perfectmerinoshirt.com (BOFU)
- Social Intent "visual" → perfectmerinoshirt.com (BOFU mobile-fast)
- IDS alto su TOFU → shift a BOFU con messaggio personalizzato
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ================================================================
# KEYWORD INTENT CLASSIFICATION
# ================================================================

# Informational keywords → TOFU (worldofmerino.com)
INFORMATIONAL_KEYWORDS = [
    "proprietà merino", "merino properties", "merino vorteile",
    "lana merino benefici", "merino wool benefits",
    "merino vs cotton", "merino vs cotone",
    "17 micron", "17.5 micron", "super 120",
    "come lavare merino", "how to wash merino",
    "merino antiodore", "merino odor", "merino geruch",
    "termoregolazione", "thermoregulation",
    "fibra naturale", "natural fiber",
    "merino estate", "merino summer", "merino sommer",
]

# Transactional keywords → BOFU (albeni1905.com / perfectmerinoshirt.com)
TRANSACTIONAL_KEYWORDS = [
    "t-shirt merino", "merino t-shirt", "merino tshirt",
    "polo merino", "merino polo",
    "comprare merino", "buy merino", "merino kaufen",
    "t-shirt lusso", "luxury t-shirt", "luxus t-shirt",
    "merino prezzo", "merino price", "merino preis",
    "albeni", "albeni 1905",
    "reda merino", "perfect merino shirt",
    "cut and sewn", "cut & sewn",
    "invisible luxury",
    "merino uomo elegante", "merino men elegant",
]

# Comparison/consideration keywords → MOFU (merinouniversity.com)
CONSIDERATION_KEYWORDS = [
    "merino vs sintetico", "merino vs synthetic",
    "migliore t-shirt", "best t-shirt", "beste t-shirt",
    "confronto merino", "merino comparison", "merino vergleich",
    "recensione merino", "merino review", "merino bewertung",
    "qualità merino", "merino quality", "merino qualität",
    "smartwool vs", "icebreaker vs", "allbirds vs",
    "unbound merino vs", "wool and prince vs",
]


# ================================================================
# ROUTING MESSAGES — Cross-Domain Shift Prompts
# ================================================================

SHIFT_MESSAGES = {
    "tofu_to_bofu": {
        "it": "Ora che conosci la fibra, scopri come Albeni la trasforma in un capo che indosserai ogni giorno.",
        "en": "Now that you know the fiber, discover how Albeni transforms it into a garment you'll wear every day.",
        "de": "Jetzt, wo Sie die Faser kennen, entdecken Sie, wie Albeni sie in ein Kleidungsstück verwandelt, das Sie jeden Tag tragen werden.",
        "fr": "Maintenant que vous connaissez la fibre, découvrez comment Albeni la transforme en un vêtement que vous porterez chaque jour.",
    },
    "mofu_to_bofu": {
        "it": "Hai confrontato le alternative. Albeni 1905 + Reda 1865 = 270+ anni di eccellenza. Pronto a toccare con mano?",
        "en": "You've compared the alternatives. Albeni 1905 + Reda 1865 = 270+ years of excellence. Ready to experience it?",
        "de": "Sie haben die Alternativen verglichen. Albeni 1905 + Reda 1865 = 270+ Jahre Exzellenz. Bereit, es zu erleben?",
        "fr": "Vous avez comparé les alternatives. Albeni 1905 + Reda 1865 = 270+ ans d'excellence. Prêt à découvrir ?",
    },
    "social_mobile": {
        "it": "La T-shirt che non si stira, non prende odori, e dura anni. Scoprila ora.",
        "en": "The T-shirt that doesn't wrinkle, doesn't smell, and lasts for years. Discover it now.",
        "de": "Das T-Shirt, das nicht knittert, nicht riecht und jahrelang hält. Jetzt entdecken.",
        "fr": "Le T-shirt qui ne se froisse pas, ne sent pas, et dure des années. Découvrez-le maintenant.",
    },
    "travel_persona": {
        "it": "La T-shirt che non si stira, pensata per il tuo prossimo viaggio.",
        "en": "The wrinkle-free T-shirt, designed for your next trip.",
        "de": "Das knitterfreie T-Shirt, perfekt für Ihre nächste Reise.",
        "fr": "Le T-shirt infroissable, conçu pour votre prochain voyage.",
    },
}

# Cluster-specific headline overrides for landing pages
CLUSTER_HEADLINES = {
    "business_professional": {
        "it": "Same Silhouette, Superior Substance. La T-shirt per chi non scende a compromessi.",
        "en": "Same Silhouette, Superior Substance. The T-shirt for those who never compromise.",
        "de": "Same Silhouette, Superior Substance. Das T-Shirt für alle, die keine Kompromisse eingehen.",
    },
    "heritage_mature": {
        "it": "120 anni di tradizione italiana. 17 micron di eccellenza Reda.",
        "en": "120 years of Italian tradition. 17 microns of Reda excellence.",
        "de": "120 Jahre italienische Tradition. 17 Mikron Reda-Exzellenz.",
    },
    "conscious_premium": {
        "it": "ZQ certificata. Tracciabile dal pascolo al tuo guardaroba. Naturale, rinnovabile, biodegradabile.",
        "en": "ZQ certified. Traceable from farm to your wardrobe. Natural, renewable, biodegradable.",
        "de": "ZQ-zertifiziert. Vom Feld bis zu Ihrem Kleiderschrank rückverfolgbar.",
    },
    "modern_minimalist": {
        "it": "Un capo. Ogni giorno. Senza pensarci. Il guardaroba essenziale inizia qui.",
        "en": "One garment. Every day. No thought required. The essential wardrobe starts here.",
        "de": "Ein Kleidungsstück. Jeden Tag. Ohne nachzudenken. Die Essentials beginnen hier.",
    },
    "italian_authentic": {
        "it": "Reda 1865 × Albeni 1905. Due secoli di artigianato italiano nel tuo quotidiano.",
        "en": "Reda 1865 × Albeni 1905. Two centuries of Italian craftsmanship in your everyday.",
        "de": "Reda 1865 × Albeni 1905. Zwei Jahrhunderte italienisches Handwerk im Alltag.",
    },
}


# ================================================================
# ADV ROUTER SERVICE
# ================================================================

class ADVRouter:
    """
    Dynamic routing engine for ADV traffic.
    Decides landing page, layout, and messaging based on ad context.
    """

    def __init__(self):
        self._routing_log: List[Dict] = []

    def classify_keyword_intent(self, keyword: Optional[str]) -> str:
        """Classify a search keyword into intent category."""
        if not keyword:
            return "unknown"

        kw_lower = keyword.lower()

        # Score each category
        informational_score = sum(1 for k in INFORMATIONAL_KEYWORDS if k in kw_lower)
        transactional_score = sum(1 for k in TRANSACTIONAL_KEYWORDS if k in kw_lower)
        consideration_score = sum(1 for k in CONSIDERATION_KEYWORDS if k in kw_lower)

        scores = {
            "informational": informational_score,
            "transactional": transactional_score,
            "consideration": consideration_score,
        }

        best = max(scores, key=scores.get)
        if scores[best] == 0:
            # Fallback: check for brand terms
            if any(b in kw_lower for b in ["albeni", "reda", "perfect merino"]):
                return "transactional"
            return "informational"  # Default: educate first

        return best

    def route(
        self,
        campaign_data: Dict,
        ids_score: float = 0,
        cluster: Optional[str] = None,
        language: str = "it",
        device: str = "desktop",
    ) -> Dict[str, Any]:
        """
        Determine optimal routing for an ADV visitor.

        Returns:
            {
                target_domain, target_url, layout, headline,
                shift_message (if cross-domain shift), routing_reason
            }
        """
        source = campaign_data.get("canonical_source", "unknown")
        intent = campaign_data.get("intent_type", "unknown")
        keyword = campaign_data.get("keyword")
        current_stage = campaign_data.get("funnel_stage", "unknown")

        result = {
            "source": source,
            "intent_type": intent,
            "language": language,
            "device": device,
            "ids_score": ids_score,
            "cluster": cluster,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # ---- GOOGLE ADS (Search Intent) ----
        if source == "google_ads" or intent == "search_intent":
            kw_intent = self.classify_keyword_intent(keyword)

            if kw_intent == "informational":
                result.update({
                    "target_domain": "worldofmerino.com",
                    "target_url": settings.DOMAIN_TOFU,
                    "layout": "educational_long",
                    "routing_reason": f"Search intent informational: '{keyword}'",
                })
            elif kw_intent == "consideration":
                result.update({
                    "target_domain": "merinouniversity.com",
                    "target_url": settings.DOMAIN_MOFU,
                    "layout": "comparison_deep",
                    "routing_reason": f"Search intent consideration: '{keyword}'",
                })
            else:  # transactional
                result.update({
                    "target_domain": "albeni1905.com",
                    "target_url": settings.DOMAIN_BOFU_HERITAGE,
                    "layout": "product_hero",
                    "routing_reason": f"Search intent transactional: '{keyword}'",
                })

        # ---- META ADS (Social Intent) ----
        elif source == "meta_ads" or intent == "social_intent":
            # Social → always BOFU, mobile-optimized
            layout = "mobile_fast" if device == "mobile" else "visual_hero"

            # Check ad content for persona targeting
            ad_content = (campaign_data.get("ad_content") or "").lower()
            if any(w in ad_content for w in ["viaggio", "travel", "reise", "voyage"]):
                result["shift_message"] = SHIFT_MESSAGES["travel_persona"].get(language, SHIFT_MESSAGES["travel_persona"]["en"])

            result.update({
                "target_domain": "perfectmerinoshirt.com",
                "target_url": settings.DOMAIN_BOFU_TECH,
                "layout": layout,
                "routing_reason": "Social intent → BOFU mobile-fast conversion",
            })

            # Add social-specific CTA
            result["shift_message"] = result.get("shift_message") or SHIFT_MESSAGES["social_mobile"].get(language, SHIFT_MESSAGES["social_mobile"]["en"])

        # ---- ORGANIC / EMAIL / DIRECT ----
        else:
            result.update({
                "target_domain": "albeni1905.com",
                "target_url": settings.DOMAIN_BOFU_HERITAGE,
                "layout": "default",
                "routing_reason": f"Non-paid traffic from {source}",
            })

        # ---- CROSS-DOMAIN SHIFT based on IDS ----
        if ids_score > settings.ADV_IDS_HIGH_QUALITY_THRESHOLD:
            # High intent user on TOFU/MOFU → shift to BOFU
            if current_stage == "TOFU":
                result["shift_target"] = {
                    "domain": "albeni1905.com",
                    "url": settings.DOMAIN_BOFU_HERITAGE,
                    "message": SHIFT_MESSAGES["tofu_to_bofu"].get(language, SHIFT_MESSAGES["tofu_to_bofu"]["en"]),
                    "reason": f"IDS {ids_score} > {settings.ADV_IDS_HIGH_QUALITY_THRESHOLD} on TOFU → shift to BOFU",
                }
            elif current_stage == "MOFU":
                result["shift_target"] = {
                    "domain": "albeni1905.com",
                    "url": settings.DOMAIN_BOFU_HERITAGE,
                    "message": SHIFT_MESSAGES["mofu_to_bofu"].get(language, SHIFT_MESSAGES["mofu_to_bofu"]["en"]),
                    "reason": f"IDS {ids_score} > {settings.ADV_IDS_HIGH_QUALITY_THRESHOLD} on MOFU → shift to BOFU",
                }

        # ---- CLUSTER-SPECIFIC HEADLINE ----
        if cluster and cluster in CLUSTER_HEADLINES:
            headlines = CLUSTER_HEADLINES[cluster]
            result["headline"] = headlines.get(language, headlines.get("en", ""))

        self._routing_log.append(result)
        return result

    def get_stats(self) -> Dict:
        """Routing statistics."""
        total = len(self._routing_log)
        by_domain = {}
        by_source = {}
        shifts = sum(1 for r in self._routing_log if "shift_target" in r)

        for r in self._routing_log:
            d = r.get("target_domain", "unknown")
            s = r.get("source", "unknown")
            by_domain[d] = by_domain.get(d, 0) + 1
            by_source[s] = by_source.get(s, 0) + 1

        return {
            "total_routed": total,
            "by_target_domain": by_domain,
            "by_source": by_source,
            "cross_domain_shifts": shifts,
            "shift_rate": round(shifts / max(total, 1) * 100, 1),
        }
