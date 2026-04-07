"""
Semrush Specialist Agent - AI Orchestration Layer
Albeni 1905 - Invisible Luxury Ecosystem

Connects to Semrush API to acquire and analyze:
- Domain Analytics (organic + paid traffic, rankings)
- Organic Keyword positions across 4 domains × 5 markets
- Paid/ADV keyword data and competitor ad copy
- Competitor analysis (Smartwool, Icebreaker, Allbirds, Asket, Unbound Merino)
- Backlink profile overview
- Keyword gap analysis between Albeni domains and competitors

Supports the 85/15 SEO balance:
  85% behavioral cluster expansion | 15% semantic defense
"""

import logging
import csv
import io
from typing import Optional, Dict, List, Any
from datetime import datetime

import httpx
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SemrushAgent:
    """
    Semrush Specialist Agent for the Albeni 1905 AI Orchestration Layer.
    Acquires and analyzes SEO + Paid data from Semrush API.
    """

    API_BASE = "https://api.semrush.com"
    ANALYTICS_BASE = "https://api.semrush.com/analytics/v1"

    # Albeni 1905 ecosystem domains
    DOMAINS = {
        "tofu": "worldofmerino.com",
        "mofu": "merinouniversity.com",
        "bofu_tech": "perfectmerinoshirt.com",
        "bofu_heritage": "albeni1905.com",
    }

    # Target markets (Semrush database codes)
    MARKETS = {
        "it": "it",   # Italy
        "de": "de",   # Germany
        "en": "us",   # US/English (global)
        "fr": "fr",   # France
        "es": "es",   # Spain
    }

    # Key competitors for benchmarking
    COMPETITORS = [
        "smartwool.com",
        "icebreaker.com",
        "allbirds.com",
        "asket.com",
        "unboundmerino.com",
        "woolandprince.com",
    ]

    # 85/15 SEO balance categories
    CLUSTER_EXPANSION_KEYWORDS = [
        "merino wool benefits", "merino vs cotton", "sustainable fashion",
        "ethical clothing", "travel wardrobe", "capsule wardrobe merino",
        "wool care guide", "temperature regulation fabric",
        "lana merino benefici", "maglia merino uomo",
        "Merinowolle Vorteile", "nachhaltige Mode",
    ]

    SEMANTIC_DEFENSE_KEYWORDS = [
        "albeni 1905", "albeni merino", "reda 1865",
        "cut & sewn merino", "invisible luxury",
        "perfect merino shirt", "world of merino",
    ]

    def __init__(self):
        self.api_key = settings.SEMRUSH_API_KEY
        if not self.api_key:
            logger.warning("SEMRUSH_API_KEY not configured")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def _request(self, params: Dict[str, str]) -> List[Dict[str, str]]:
        """
        Make a request to Semrush API.
        Returns parsed CSV data as list of dicts.
        Semrush API returns semicolon-separated CSV.
        """
        params["key"] = self.api_key
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.API_BASE, params=params)

            if response.status_code != 200:
                error_text = response.text.strip()
                logger.error(f"Semrush API error: {response.status_code} - {error_text}")
                raise Exception(f"Semrush API error: {error_text}")

            # Parse semicolon-separated CSV
            return self._parse_csv(response.text)

    async def _request_analytics(self, params: Dict[str, str]) -> List[Dict[str, str]]:
        """Request to Semrush Analytics API (backlinks, etc.)."""
        params["key"] = self.api_key
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.ANALYTICS_BASE, params=params)

            if response.status_code != 200:
                error_text = response.text.strip()
                logger.error(f"Semrush Analytics API error: {response.status_code} - {error_text}")
                raise Exception(f"Semrush Analytics API error: {error_text}")

            return self._parse_csv(response.text)

    def _parse_csv(self, text: str) -> List[Dict[str, str]]:
        """Parse Semrush semicolon-separated CSV response."""
        reader = csv.DictReader(io.StringIO(text.strip()), delimiter=";")
        return [dict(row) for row in reader]

    # =================================================================
    # DOMAIN ANALYTICS
    # =================================================================

    async def get_domain_overview(self, domain: str, database: str = "it") -> Dict[str, Any]:
        """
        Get domain-level overview: organic traffic, paid traffic, rankings.
        """
        if not self._is_configured():
            return {"error": "Semrush API key not configured", "domain": domain}

        try:
            data = await self._request({
                "type": "domain_ranks",
                "domain": domain,
                "database": database,
                "export_columns": "Db,Dn,Rk,Or,Ot,Oc,Ad,At,Ac",
            })
            if data:
                row = data[0]
                return {
                    "domain": domain,
                    "database": database,
                    "semrush_rank": int(row.get("Rk", 0)),
                    "organic_keywords": int(row.get("Or", 0)),
                    "organic_traffic": int(row.get("Ot", 0)),
                    "organic_cost": float(row.get("Oc", 0)),
                    "paid_keywords": int(row.get("Ad", 0)),
                    "paid_traffic": int(row.get("At", 0)),
                    "paid_cost": float(row.get("Ac", 0)),
                    "fetched_at": datetime.utcnow().isoformat(),
                }
            return {"domain": domain, "database": database, "data": None}
        except Exception as e:
            logger.error(f"Domain overview failed for {domain}: {e}")
            return {"domain": domain, "database": database, "error": str(e)}

    async def get_all_domains_overview(self, database: str = "it") -> Dict[str, Any]:
        """Get overview for all 4 Albeni domains in a specific market."""
        results = {}
        for funnel, domain in self.DOMAINS.items():
            results[funnel] = await self.get_domain_overview(domain, database)
        return {
            "database": database,
            "domains": results,
            "fetched_at": datetime.utcnow().isoformat(),
        }

    # =================================================================
    # ORGANIC KEYWORDS
    # =================================================================

    async def get_organic_keywords(
        self, domain: str, database: str = "it", limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get organic keyword positions for a domain.
        Returns ranked keywords with position, volume, CPC, traffic %.
        """
        if not self._is_configured():
            return {"error": "Semrush API key not configured"}

        try:
            data = await self._request({
                "type": "domain_organic",
                "domain": domain,
                "database": database,
                "display_limit": str(limit),
                "export_columns": "Ph,Po,Nq,Cp,Ur,Tr,Tc,Co,Kd",
                "display_sort": "tr_desc",  # Sort by traffic descending
            })

            keywords = []
            for row in data:
                keywords.append({
                    "keyword": row.get("Ph", ""),
                    "position": int(row.get("Po", 0)),
                    "search_volume": int(row.get("Nq", 0)),
                    "cpc": float(row.get("Cp", 0)),
                    "url": row.get("Ur", ""),
                    "traffic_percent": float(row.get("Tr", 0)),
                    "traffic_cost": float(row.get("Tc", 0)),
                    "competition": float(row.get("Co", 0)),
                    "keyword_difficulty": int(row.get("Kd", 0)),
                })

            return {
                "domain": domain,
                "database": database,
                "total_keywords": len(keywords),
                "keywords": keywords,
            }
        except Exception as e:
            logger.error(f"Organic keywords failed for {domain}: {e}")
            return {"domain": domain, "error": str(e)}

    # =================================================================
    # PAID (ADV) KEYWORDS
    # =================================================================

    async def get_paid_keywords(
        self, domain: str, database: str = "it", limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get paid/ADV keyword data for a domain.
        Shows which keywords the domain is bidding on in Google Ads.
        """
        if not self._is_configured():
            return {"error": "Semrush API key not configured"}

        try:
            data = await self._request({
                "type": "domain_adwords",
                "domain": domain,
                "database": database,
                "display_limit": str(limit),
                "export_columns": "Ph,Po,Nq,Cp,Ur,Tr,Tc,Co,Tt,Ds",
                "display_sort": "tr_desc",
            })

            paid_kws = []
            for row in data:
                paid_kws.append({
                    "keyword": row.get("Ph", ""),
                    "position": int(row.get("Po", 0)),
                    "search_volume": int(row.get("Nq", 0)),
                    "cpc": float(row.get("Cp", 0)),
                    "url": row.get("Ur", ""),
                    "traffic_percent": float(row.get("Tr", 0)),
                    "traffic_cost": float(row.get("Tc", 0)),
                    "title": row.get("Tt", ""),
                    "description": row.get("Ds", ""),
                })

            return {
                "domain": domain,
                "database": database,
                "total_paid_keywords": len(paid_kws),
                "paid_keywords": paid_kws,
            }
        except Exception as e:
            logger.error(f"Paid keywords failed for {domain}: {e}")
            return {"domain": domain, "error": str(e)}

    # =================================================================
    # COMPETITOR ANALYSIS
    # =================================================================

    async def get_organic_competitors(
        self, domain: str, database: str = "it", limit: int = 20
    ) -> Dict[str, Any]:
        """
        Find organic competitors for a domain.
        Shows domains competing for the same organic keywords.
        """
        if not self._is_configured():
            return {"error": "Semrush API key not configured"}

        try:
            data = await self._request({
                "type": "domain_organic_organic",
                "domain": domain,
                "database": database,
                "display_limit": str(limit),
                "export_columns": "Dn,Cr,Np,Or,Ot,Oc,Ad",
            })

            competitors = []
            for row in data:
                competitors.append({
                    "domain": row.get("Dn", ""),
                    "competition_level": float(row.get("Cr", 0)),
                    "common_keywords": int(row.get("Np", 0)),
                    "organic_keywords": int(row.get("Or", 0)),
                    "organic_traffic": int(row.get("Ot", 0)),
                    "organic_cost": float(row.get("Oc", 0)),
                    "paid_keywords": int(row.get("Ad", 0)),
                })

            return {
                "domain": domain,
                "database": database,
                "competitors": competitors,
            }
        except Exception as e:
            logger.error(f"Competitor analysis failed for {domain}: {e}")
            return {"domain": domain, "error": str(e)}

    async def benchmark_vs_competitors(self, database: str = "it") -> Dict[str, Any]:
        """
        Benchmark all 4 Albeni domains against known competitors.
        Compares organic traffic, keywords, and estimated traffic cost.
        """
        if not self._is_configured():
            return {"error": "Semrush API key not configured"}

        all_domains = list(self.DOMAINS.values()) + self.COMPETITORS
        results = {}

        for domain in all_domains:
            overview = await self.get_domain_overview(domain, database)
            results[domain] = overview

        # Classify into our domains vs competitors
        albeni_data = {k: results[v] for k, v in self.DOMAINS.items()}
        competitor_data = {d: results[d] for d in self.COMPETITORS}

        # Calculate totals
        albeni_total_traffic = sum(
            d.get("organic_traffic", 0) for d in albeni_data.values()
        )
        albeni_total_keywords = sum(
            d.get("organic_keywords", 0) for d in albeni_data.values()
        )
        competitor_avg_traffic = (
            sum(d.get("organic_traffic", 0) for d in competitor_data.values())
            / max(1, len(competitor_data))
        )

        return {
            "database": database,
            "albeni_ecosystem": albeni_data,
            "competitors": competitor_data,
            "summary": {
                "albeni_total_organic_traffic": albeni_total_traffic,
                "albeni_total_organic_keywords": albeni_total_keywords,
                "competitor_avg_organic_traffic": round(competitor_avg_traffic),
                "traffic_gap": round(competitor_avg_traffic - albeni_total_traffic),
            },
            "fetched_at": datetime.utcnow().isoformat(),
        }

    # =================================================================
    # KEYWORD RESEARCH
    # =================================================================

    async def keyword_overview(
        self, keyword: str, database: str = "it"
    ) -> Dict[str, Any]:
        """
        Get detailed data for a specific keyword.
        Volume, CPC, competition, trend, SERP features.
        """
        if not self._is_configured():
            return {"error": "Semrush API key not configured"}

        try:
            data = await self._request({
                "type": "phrase_all",
                "phrase": keyword,
                "database": database,
                "export_columns": "Ph,Nq,Cp,Co,Nr,Td",
            })

            if data:
                row = data[0]
                return {
                    "keyword": keyword,
                    "database": database,
                    "search_volume": int(row.get("Nq", 0)),
                    "cpc": float(row.get("Cp", 0)),
                    "competition": float(row.get("Co", 0)),
                    "results_count": int(row.get("Nr", 0)),
                    "trend": row.get("Td", ""),
                }
            return {"keyword": keyword, "database": database, "data": None}
        except Exception as e:
            logger.error(f"Keyword overview failed for '{keyword}': {e}")
            return {"keyword": keyword, "error": str(e)}

    async def keyword_batch_overview(
        self, keywords: List[str], database: str = "it"
    ) -> Dict[str, Any]:
        """Analyze multiple keywords at once."""
        results = {}
        for kw in keywords:
            results[kw] = await self.keyword_overview(kw, database)
        return {"database": database, "keywords": results}

    async def get_related_keywords(
        self, keyword: str, database: str = "it", limit: int = 30
    ) -> Dict[str, Any]:
        """
        Get related keywords (broad match) for content expansion.
        """
        if not self._is_configured():
            return {"error": "Semrush API key not configured"}

        try:
            data = await self._request({
                "type": "phrase_related",
                "phrase": keyword,
                "database": database,
                "display_limit": str(limit),
                "export_columns": "Ph,Nq,Cp,Co,Kd,Nr",
                "display_sort": "nq_desc",
            })

            related = []
            for row in data:
                related.append({
                    "keyword": row.get("Ph", ""),
                    "search_volume": int(row.get("Nq", 0)),
                    "cpc": float(row.get("Cp", 0)),
                    "competition": float(row.get("Co", 0)),
                    "keyword_difficulty": int(row.get("Kd", 0)),
                    "results_count": int(row.get("Nr", 0)),
                })

            return {
                "seed_keyword": keyword,
                "database": database,
                "related_keywords": related,
            }
        except Exception as e:
            logger.error(f"Related keywords failed for '{keyword}': {e}")
            return {"keyword": keyword, "error": str(e)}

    # =================================================================
    # BACKLINK ANALYSIS
    # =================================================================

    async def get_backlinks_overview(self, domain: str) -> Dict[str, Any]:
        """
        Get backlink profile overview for a domain.
        Total backlinks, referring domains, authority score.
        """
        if not self._is_configured():
            return {"error": "Semrush API key not configured"}

        try:
            data = await self._request_analytics({
                "type": "backlinks_overview",
                "target": domain,
                "target_type": "root_domain",
                "export_columns": "ascore,total,domains_num,urls_num,ips_num,follows_num,nofollows_num,texts_num,images_num",
            })

            if data:
                row = data[0]
                return {
                    "domain": domain,
                    "authority_score": int(row.get("ascore", 0)),
                    "total_backlinks": int(row.get("total", 0)),
                    "referring_domains": int(row.get("domains_num", 0)),
                    "referring_urls": int(row.get("urls_num", 0)),
                    "referring_ips": int(row.get("ips_num", 0)),
                    "follow_links": int(row.get("follows_num", 0)),
                    "nofollow_links": int(row.get("nofollows_num", 0)),
                    "text_links": int(row.get("texts_num", 0)),
                    "image_links": int(row.get("images_num", 0)),
                }
            return {"domain": domain, "data": None}
        except Exception as e:
            logger.error(f"Backlinks overview failed for {domain}: {e}")
            return {"domain": domain, "error": str(e)}

    # =================================================================
    # 85/15 SEO BALANCE ANALYSIS
    # =================================================================

    async def analyze_seo_balance(self, database: str = "it") -> Dict[str, Any]:
        """
        Analyze the 85/15 SEO balance across all Albeni domains.
        85% = cluster expansion keywords (TOFU/MOFU content)
        15% = semantic defense keywords (brand terms)

        Returns current balance, gaps, and recommendations.
        """
        if not self._is_configured():
            return {"error": "Semrush API key not configured"}

        expansion_data = []
        defense_data = []

        # Check cluster expansion keywords
        for kw in self.CLUSTER_EXPANSION_KEYWORDS:
            try:
                result = await self.keyword_overview(kw, database)
                if "error" not in result:
                    expansion_data.append(result)
            except Exception:
                pass

        # Check semantic defense keywords
        for kw in self.SEMANTIC_DEFENSE_KEYWORDS:
            try:
                result = await self.keyword_overview(kw, database)
                if "error" not in result:
                    defense_data.append(result)
            except Exception:
                pass

        # Aggregate volumes
        expansion_volume = sum(d.get("search_volume", 0) for d in expansion_data)
        defense_volume = sum(d.get("search_volume", 0) for d in defense_data)
        total_volume = expansion_volume + defense_volume

        if total_volume > 0:
            expansion_pct = round(expansion_volume / total_volume * 100, 1)
            defense_pct = round(defense_volume / total_volume * 100, 1)
        else:
            expansion_pct = 0
            defense_pct = 0

        # Determine balance health
        if 80 <= expansion_pct <= 90:
            balance_status = "optimal"
        elif 70 <= expansion_pct <= 95:
            balance_status = "acceptable"
        else:
            balance_status = "needs_adjustment"

        return {
            "database": database,
            "target_balance": {"expansion": 85, "defense": 15},
            "current_balance": {
                "expansion_pct": expansion_pct,
                "defense_pct": defense_pct,
            },
            "balance_status": balance_status,
            "expansion_keywords": expansion_data,
            "defense_keywords": defense_data,
            "total_search_volume": total_volume,
            "recommendations": self._generate_balance_recommendations(
                expansion_pct, defense_pct, expansion_data, defense_data
            ),
        }

    def _generate_balance_recommendations(
        self,
        expansion_pct: float,
        defense_pct: float,
        expansion_data: List,
        defense_data: List,
    ) -> List[str]:
        """Generate actionable recommendations based on 85/15 balance."""
        recs = []

        if expansion_pct < 80:
            recs.append(
                f"Cluster expansion is at {expansion_pct}% (target: 85%). "
                "Create more TOFU/MOFU content on general merino topics."
            )
        elif expansion_pct > 90:
            recs.append(
                f"Cluster expansion is at {expansion_pct}% (target: 85%). "
                "Increase semantic defense with branded content and landing pages."
            )

        if defense_pct < 10:
            recs.append(
                "Brand defense is weak. Ensure 'Albeni 1905', 'Reda 1865', "
                "and 'Cut & Sewn' keywords are ranking on page 1."
            )

        # Find high-volume, low-competition expansion opportunities
        opportunities = [
            d for d in expansion_data
            if d.get("search_volume", 0) > 500 and d.get("competition", 1) < 0.5
        ]
        if opportunities:
            recs.append(
                f"Found {len(opportunities)} high-volume, low-competition "
                "cluster expansion opportunities to target."
            )

        if not recs:
            recs.append("SEO balance is healthy. Continue current strategy.")

        return recs

    # =================================================================
    # FULL AUDIT (Comprehensive Report)
    # =================================================================

    async def full_seo_audit(self, database: str = "it") -> Dict[str, Any]:
        """
        Run a comprehensive SEO audit across the Albeni ecosystem.
        Combines domain overview, keywords, competitors, backlinks, and balance.
        """
        if not self._is_configured():
            return {"error": "Semrush API key not configured", "message": "Please set SEMRUSH_API_KEY in .env"}

        logger.info(f"Starting full SEO audit for database: {database}")
        audit = {
            "audit_date": datetime.utcnow().isoformat(),
            "database": database,
            "domains": {},
            "competitor_benchmark": None,
            "seo_balance": None,
        }

        # 1. Domain overviews + top keywords for each Albeni domain
        for funnel, domain in self.DOMAINS.items():
            overview = await self.get_domain_overview(domain, database)
            organic_kws = await self.get_organic_keywords(domain, database, limit=20)
            paid_kws = await self.get_paid_keywords(domain, database, limit=10)
            backlinks = await self.get_backlinks_overview(domain)

            audit["domains"][funnel] = {
                "domain": domain,
                "overview": overview,
                "top_organic_keywords": organic_kws.get("keywords", [])[:20],
                "top_paid_keywords": paid_kws.get("paid_keywords", [])[:10],
                "backlinks": backlinks,
            }

        # 2. Competitor benchmark
        audit["competitor_benchmark"] = await self.benchmark_vs_competitors(database)

        # 3. 85/15 SEO balance
        audit["seo_balance"] = await self.analyze_seo_balance(database)

        logger.info("Full SEO audit completed")
        return audit

    # =================================================================
    # PAID/ADV INTELLIGENCE
    # =================================================================

    async def get_paid_intelligence(self, database: str = "it") -> Dict[str, Any]:
        """
        Paid advertising intelligence across Albeni domains and competitors.
        Shows ad spend, ad copy, keyword overlap.
        """
        if not self._is_configured():
            return {"error": "Semrush API key not configured"}

        albeni_paid = {}
        competitor_paid = {}

        # Albeni paid data
        for funnel, domain in self.DOMAINS.items():
            overview = await self.get_domain_overview(domain, database)
            paid_kws = await self.get_paid_keywords(domain, database, limit=20)
            albeni_paid[funnel] = {
                "domain": domain,
                "paid_keywords": overview.get("paid_keywords", 0),
                "paid_traffic": overview.get("paid_traffic", 0),
                "paid_cost": overview.get("paid_cost", 0),
                "top_ads": paid_kws.get("paid_keywords", [])[:10],
            }

        # Competitor paid data
        for comp in self.COMPETITORS[:4]:  # Top 4 competitors
            overview = await self.get_domain_overview(comp, database)
            paid_kws = await self.get_paid_keywords(comp, database, limit=10)
            competitor_paid[comp] = {
                "paid_keywords": overview.get("paid_keywords", 0),
                "paid_traffic": overview.get("paid_traffic", 0),
                "paid_cost": overview.get("paid_cost", 0),
                "top_ads": paid_kws.get("paid_keywords", [])[:5],
            }

        # Calculate ADV gap
        albeni_total_cost = sum(d["paid_cost"] for d in albeni_paid.values())
        competitor_avg_cost = (
            sum(d["paid_cost"] for d in competitor_paid.values())
            / max(1, len(competitor_paid))
        )

        return {
            "database": database,
            "albeni_paid": albeni_paid,
            "competitor_paid": competitor_paid,
            "summary": {
                "albeni_total_adv_cost": round(albeni_total_cost, 2),
                "competitor_avg_adv_cost": round(competitor_avg_cost, 2),
                "adv_gap": round(competitor_avg_cost - albeni_total_cost, 2),
            },
            "fetched_at": datetime.utcnow().isoformat(),
        }

    # =================================================================
    # KEYWORD GAP ANALYSIS
    # =================================================================

    async def keyword_gap(
        self, database: str = "it", competitor: str = "smartwool.com"
    ) -> Dict[str, Any]:
        """
        Find keywords where a competitor ranks but Albeni doesn't.
        Uses domain_domains comparison for the main Albeni domain.
        """
        if not self._is_configured():
            return {"error": "Semrush API key not configured"}

        try:
            # Use albeni1905.com as primary comparison domain
            data = await self._request({
                "type": "domain_domains",
                "domains": f"albeni1905.com|or|{competitor}|or",
                "database": database,
                "display_limit": "50",
                "export_columns": "Ph,Nq,Cp,Co,Kd,P0,P1",
                "display_sort": "nq_desc",
                "display_filter": "+|Po0|Eq|0",  # Where Albeni has no ranking
            })

            gaps = []
            for row in data:
                gaps.append({
                    "keyword": row.get("Ph", ""),
                    "search_volume": int(row.get("Nq", 0)),
                    "cpc": float(row.get("Cp", 0)),
                    "competition": float(row.get("Co", 0)),
                    "keyword_difficulty": int(row.get("Kd", 0)),
                    "albeni_position": row.get("P0", "-"),
                    "competitor_position": row.get("P1", "-"),
                })

            return {
                "albeni_domain": "albeni1905.com",
                "competitor": competitor,
                "database": database,
                "total_gaps": len(gaps),
                "keyword_gaps": gaps,
            }
        except Exception as e:
            logger.error(f"Keyword gap failed vs {competitor}: {e}")
            return {"competitor": competitor, "error": str(e)}

    # =================================================================
    # POSITION TRACKING HELPERS
    # =================================================================

    async def check_keyword_positions(
        self, keywords: List[str], database: str = "it"
    ) -> Dict[str, Any]:
        """
        Check where all 4 Albeni domains rank for specific keywords.
        Useful for tracking target keywords from the Content Pipeline.
        """
        if not self._is_configured():
            return {"error": "Semrush API key not configured"}

        results = {}
        for kw in keywords:
            kw_data = {"keyword": kw, "positions": {}}
            for funnel, domain in self.DOMAINS.items():
                try:
                    organic = await self.get_organic_keywords(domain, database, limit=100)
                    # Find this keyword in the domain's rankings
                    found = False
                    for ranked_kw in organic.get("keywords", []):
                        if ranked_kw["keyword"].lower() == kw.lower():
                            kw_data["positions"][domain] = {
                                "position": ranked_kw["position"],
                                "url": ranked_kw["url"],
                                "traffic_percent": ranked_kw["traffic_percent"],
                            }
                            found = True
                            break
                    if not found:
                        kw_data["positions"][domain] = {"position": "-", "url": None}
                except Exception:
                    kw_data["positions"][domain] = {"position": "error", "url": None}

            results[kw] = kw_data

        return {"database": database, "keyword_positions": results}
