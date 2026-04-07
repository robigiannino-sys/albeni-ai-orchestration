"""
Data Hub Context Provider — AI Orchestration Layer
Albeni 1905 — Invisible Luxury Ecosystem

Middleware that connects Data Hub knowledge to all AI agents.
Every agent calls get_context() before executing, receiving
relevant data, instructions, and guidelines from uploaded files.

Architecture:
  1. Files in Data Hub can be TAGGED with categories (tone_of_voice,
     seo_guidelines, glossary, competitor_data, brand_guidelines, etc.)
  2. Each agent declares which context types it needs
  3. Context Provider retrieves, ranks, and injects the right data

This makes every uploaded document a "living instruction" for agents.
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import get_settings
from services.research_hub import ResearchHub

logger = logging.getLogger(__name__)
settings = get_settings()

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "research_hub")
TAGS_PATH = os.path.join(DATA_DIR, "_tags_index.json")


# ================================================================
# PREDEFINED CONTEXT CATEGORIES
# ================================================================

CONTEXT_CATEGORIES = {
    "tone_of_voice": {
        "label": "Tone of Voice",
        "icon": "🎨",
        "description": "Linee guida sullo stile comunicativo Albeni 1905. Definisce voce, tono, registro e personalità del brand.",
        "agents": ["content_generator", "content_validator", "email_copy", "blog_draft", "landing_copy"],
    },
    "seo_guidelines": {
        "label": "SEO Guidelines",
        "icon": "📈",
        "description": "Linee guida SEO: keyword strategy, on-page rules, 85/15 balance, cluster expansion vs semantic defense.",
        "agents": ["seo_brain", "content_generator", "semrush_agent"],
    },
    "glossary": {
        "label": "Glossario Tecnico",
        "icon": "📖",
        "description": "Terminologia tecnica Reda/Albeni: fibra merino, processi produttivi, certificazioni, naming prodotti.",
        "agents": ["content_generator", "content_validator", "translation_layer", "mt_validator"],
    },
    "competitor_data": {
        "label": "Dati Competitor",
        "icon": "🏢",
        "description": "Report e analisi sui competitor: Smartwool, Icebreaker, Allbirds, Asket, Unbound Merino, Wool&Prince.",
        "agents": ["seo_brain", "semrush_agent", "adv_strategist", "content_generator"],
    },
    "brand_guidelines": {
        "label": "Brand Guidelines",
        "icon": "💎",
        "description": "Visual identity, logo usage, colori, tipografia, posizionamento 'Invisible Luxury', valori del brand.",
        "agents": ["content_generator", "content_validator", "email_copy"],
    },
    "product_info": {
        "label": "Info Prodotti",
        "icon": "🧶",
        "description": "Schede prodotto, caratteristiche tecniche, materiali, certificazioni, collezioni, prezzi.",
        "agents": ["content_generator", "routing_layer", "email_copy", "landing_copy", "cluster_predictor"],
    },
    "cluster_profiles": {
        "label": "Profili Cluster",
        "icon": "👥",
        "description": "Definizione dei 5 cluster comportamentali: business_professional, heritage_mature, conscious_premium, modern_minimalist, italian_authentic.",
        "agents": ["cluster_predictor", "routing_layer", "content_generator", "email_copy", "intent_engine"],
    },
    "adv_strategy": {
        "label": "Strategia ADV",
        "icon": "💰",
        "description": "Budget €30K, allocazione per mercato, ROAS target, CPA limiti, media plan 18 mesi.",
        "agents": ["semrush_agent", "adv_strategist", "seo_brain"],
    },
    "translation_memory": {
        "label": "Memorie di Traduzione",
        "icon": "🌍",
        "description": "Coppie IT→DE validate, terminologia approvata, segmenti ricorrenti per il workflow MT+PE.",
        "agents": ["translation_layer", "mt_validator"],
    },
    "analytics_data": {
        "label": "Dati Analytics",
        "icon": "📊",
        "description": "Export GA4, Search Console, dati di traffico e conversione per i 4 domini × 5 mercati.",
        "agents": ["seo_brain", "semrush_agent", "routing_layer", "adv_strategist"],
    },
    "email_strategy": {
        "label": "Strategia Email",
        "icon": "📧",
        "description": "Flow Klaviyo, segmenti, template approvati, A/B test results, performance storiche.",
        "agents": ["email_copy", "cluster_predictor", "routing_layer"],
    },
    "content_calendar": {
        "label": "Piano Editoriale",
        "icon": "📅",
        "description": "Calendario contenuti, temi mensili, stagionalità, campagne pianificate.",
        "agents": ["content_generator", "seo_brain", "email_copy"],
    },
    "instructions": {
        "label": "Istruzioni Operative",
        "icon": "📋",
        "description": "Istruzioni generali e workflow operativi per tutti gli agenti. Regole di business, vincoli, priorità.",
        "agents": ["*"],  # All agents
    },
}

# Map agent IDs to human-readable names
AGENT_ID_MAP = {
    "intent_engine": "Intent Engine",
    "cluster_predictor": "Cluster Predictor",
    "routing_layer": "AI Routing Layer",
    "content_generator": "Content Generator",
    "content_validator": "Content Validator",
    "seo_brain": "SEO Semantic Brain",
    "semrush_agent": "Semrush Specialist",
    "notion_sync": "Notion Sync",
    "klaviyo_sync": "Klaviyo CRM Sync",
    "adv_strategist": "ADV Strategist",
    "translation_layer": "AI Translation Layer",
    "mt_validator": "MT+PE Validator",
    "email_copy": "Email Copy Generator",
    "blog_draft": "Blog Draft Generator",
    "landing_copy": "Landing Page Generator",
}


class DataHubContextProvider:
    """
    Connects Data Hub knowledge to all AI agents.

    Usage:
        provider = DataHubContextProvider()

        # Tag a file
        provider.tag_import("hub_20260316_123456_0", ["tone_of_voice", "brand_guidelines"])

        # Get context for an agent
        context = provider.get_context("content_generator", task_type="blog_draft", market="de")

        # Inject into prompt
        enriched_prompt = provider.enrich_prompt(base_prompt, "content_generator", task_type="blog_draft")
    """

    def __init__(self):
        self._hub = ResearchHub()
        self._tags = self._load_tags()

    def _load_tags(self) -> Dict:
        """Load tag index: maps import_id → list of tags."""
        if os.path.exists(TAGS_PATH):
            with open(TAGS_PATH, "r") as f:
                return json.load(f)
        return {}

    def _save_tags(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(TAGS_PATH, "w") as f:
            json.dump(self._tags, f, indent=2, default=str)

    # ================================================================
    # TAGGING SYSTEM
    # ================================================================

    def tag_import(self, import_id: str, tags: List[str], priority: int = 5) -> Dict:
        """
        Tag a Data Hub import with context categories.

        Args:
            import_id: The Hub import ID
            tags: List of category keys (e.g., ["tone_of_voice", "glossary"])
            priority: 1-10, higher = more important (used for ranking when multiple files match)

        Returns:
            Updated tag record
        """
        # Validate tags
        valid_tags = [t for t in tags if t in CONTEXT_CATEGORIES]
        invalid = [t for t in tags if t not in CONTEXT_CATEGORIES]

        self._tags[import_id] = {
            "tags": valid_tags,
            "priority": min(max(priority, 1), 10),
            "tagged_at": datetime.utcnow().isoformat(),
        }
        self._save_tags()

        result = {
            "import_id": import_id,
            "tags": valid_tags,
            "priority": priority,
            "status": "tagged",
        }
        if invalid:
            result["warnings"] = f"Tag non validi ignorati: {invalid}"
            result["available_tags"] = list(CONTEXT_CATEGORIES.keys())

        logger.info(f"Context Provider: tagged {import_id} with {valid_tags} (priority={priority})")
        return result

    def untag_import(self, import_id: str) -> bool:
        """Remove all tags from an import."""
        if import_id in self._tags:
            del self._tags[import_id]
            self._save_tags()
            return True
        return False

    def get_tags(self, import_id: str) -> Optional[Dict]:
        """Get tags for a specific import."""
        return self._tags.get(import_id)

    def list_tagged(self, tag_filter: str = None) -> List[Dict]:
        """List all tagged imports, optionally filtered by tag."""
        results = []
        all_imports = {r["id"]: r for r in self._hub.list_all()}

        for imp_id, tag_data in self._tags.items():
            if tag_filter and tag_filter not in tag_data["tags"]:
                continue
            imp_info = all_imports.get(imp_id, {"id": imp_id, "filename": "unknown"})
            results.append({
                **imp_info,
                "tags": tag_data["tags"],
                "tag_labels": [CONTEXT_CATEGORIES[t]["label"] for t in tag_data["tags"] if t in CONTEXT_CATEGORIES],
                "tag_icons": [CONTEXT_CATEGORIES[t]["icon"] for t in tag_data["tags"] if t in CONTEXT_CATEGORIES],
                "priority": tag_data["priority"],
                "tagged_at": tag_data.get("tagged_at"),
            })

        results.sort(key=lambda x: x.get("priority", 5), reverse=True)
        return results

    # ================================================================
    # AUTO-TAG (intelligent tagging from content analysis)
    # ================================================================

    def auto_tag(self, import_id: str) -> Dict:
        """
        Automatically suggest tags based on file content and metadata.
        Uses keyword matching on content to suggest relevant categories.
        """
        full = self._hub.get_data(import_id)
        if not full:
            return {"import_id": import_id, "suggested_tags": [], "error": "Import not found"}

        record = full.get("record", {})
        data = full.get("data", [])

        # Collect all text content for analysis
        text_blob = record.get("filename", "").lower() + " " + record.get("label", "").lower() + " "
        for row in data[:50]:  # Sample first 50 rows
            for v in row.values():
                if isinstance(v, str):
                    text_blob += v.lower() + " "

        # Score each category
        CATEGORY_KEYWORDS = {
            "tone_of_voice": ["tone", "tono", "voce", "voice", "stile", "style", "comunicazione", "registro", "personalità"],
            "seo_guidelines": [
                "seo", "keyword", "search", "ranking", "posizionamento", "on-page", "meta", "sitemap", "canonical",
                "search volume", "keyword difficulty", "serp", "organic", "position", "url", "broad match",
                "exact match", "phrase match", "intent", "intents", "keyword intents", "semrush", "backlink",
                "domain", "authority", "kd%", "volume", "trend", "results", "cpc",
            ],
            "glossary": ["glossario", "glossary", "terminologia", "definizione", "termine", "merino", "fibra", "reda", "17.70"],
            "competitor_data": [
                "competitor", "concorrente", "smartwool", "icebreaker", "allbirds", "asket", "unbound", "benchmark",
                "competitive", "gap", "domain overview", "comparison", "vs", "market share",
            ],
            "brand_guidelines": ["brand", "logo", "colori", "tipografia", "identity", "visual", "pantone", "palette"],
            "product_info": ["prodotto", "product", "sku", "prezzo", "price", "collezione", "materiale", "taglie", "size"],
            "cluster_profiles": ["cluster", "segmento", "persona", "profilo", "business_professional", "heritage", "conscious", "minimalist"],
            "adv_strategy": [
                "adv", "budget", "roas", "cpa", "campagna", "google ads", "meta ads", "spend", "investimento",
                "cpc", "cost per click", "paid", "ppc", "bid", "impression",
            ],
            "translation_memory": ["traduzione", "translation", "tedesco", "german", "deutsch", "de-de", "it-de", "übersetzung"],
            "analytics_data": [
                "analytics", "ga4", "traffic", "sessioni", "sessions", "bounce", "conversion", "pageview",
                "search volume", "trend", "volume", "clicks", "impressions", "ctr",
            ],
            "email_strategy": ["email", "newsletter", "flow", "klaviyo", "subject", "open rate", "click rate", "drip", "automation"],
            "content_calendar": ["calendario", "calendar", "piano editoriale", "editoriale", "schedule", "pubblicazione", "mese"],
            "instructions": ["istruzioni", "instructions", "procedura", "workflow", "regole", "rules", "linee guida", "guidelines", "sop"],
        }

        # Also check column headers specifically (very reliable signal)
        columns_text = ""
        if data and isinstance(data[0], dict):
            columns_text = " ".join(data[0].keys()).lower()

        suggested = []
        for cat, keywords in CATEGORY_KEYWORDS.items():
            # Score from content blob
            score = sum(1 for kw in keywords if kw in text_blob)
            # Bonus score from column headers (stronger signal)
            col_score = sum(2 for kw in keywords if kw in columns_text)
            total = score + col_score
            if total >= 2:
                suggested.append({"tag": cat, "score": total, "label": CONTEXT_CATEGORIES[cat]["label"]})

        suggested.sort(key=lambda x: x["score"], reverse=True)

        # Also detect from source type
        source = record.get("source", "")
        source_map = {
            "semrush": ["seo_guidelines", "competitor_data"],
            "google_analytics": ["analytics_data"],
            "google_ads": ["adv_strategy"],
            "search_console": ["seo_guidelines", "analytics_data"],
            "ahrefs": ["seo_guidelines", "competitor_data"],
            "klaviyo": ["email_strategy"],
            "shopify": ["product_info"],
        }
        for extra_tag in source_map.get(source, []):
            existing = next((s for s in suggested if s["tag"] == extra_tag), None)
            if existing:
                existing["score"] += 3  # Boost: source detection is very reliable
            else:
                suggested.append({"tag": extra_tag, "score": 3, "label": CONTEXT_CATEGORIES[extra_tag]["label"]})

        return {
            "import_id": import_id,
            "suggested_tags": suggested[:6],  # Max 6 suggestions
            "source_detected": source,
        }

    def auto_tag_all(self, min_score: int = 2) -> Dict:
        """
        Auto-tag ALL untagged imports in the Data Hub.
        For each untagged file, runs auto_tag() and applies all suggestions
        with score >= min_score.

        Returns summary of how many files were tagged.
        """
        all_imports = self._hub.list_all()
        tagged_ids = set(self._tags.keys())

        results = []
        tagged_count = 0
        skipped_count = 0

        for imp in all_imports:
            imp_id = imp["id"]
            if imp_id in tagged_ids:
                skipped_count += 1
                continue

            try:
                suggestion = self.auto_tag(imp_id)
                good_tags = [
                    s["tag"] for s in suggestion.get("suggested_tags", [])
                    if s["score"] >= min_score
                ]

                if good_tags:
                    # Apply the tags automatically
                    priority = min(10, 3 + max(s["score"] for s in suggestion["suggested_tags"] if s["tag"] in good_tags))
                    self.tag_import(imp_id, good_tags, priority)
                    tagged_count += 1
                    results.append({
                        "id": imp_id,
                        "filename": imp.get("label", imp.get("filename", "")),
                        "tags_applied": good_tags,
                        "priority": priority,
                        "status": "tagged",
                    })
                else:
                    results.append({
                        "id": imp_id,
                        "filename": imp.get("label", imp.get("filename", "")),
                        "tags_applied": [],
                        "status": "no_match",
                        "reason": "Nessuna categoria con score sufficiente",
                    })
            except Exception as e:
                logger.error(f"Auto-tag failed for {imp_id}: {e}")
                results.append({
                    "id": imp_id,
                    "filename": imp.get("label", imp.get("filename", "")),
                    "status": "error",
                    "error": str(e),
                })

        # Reload tags
        self._tags = self._load_tags()

        return {
            "status": "completed",
            "total_processed": len(all_imports) - skipped_count,
            "already_tagged": skipped_count,
            "newly_tagged": tagged_count,
            "no_match": sum(1 for r in results if r["status"] == "no_match"),
            "errors": sum(1 for r in results if r["status"] == "error"),
            "details": results,
        }

    # ================================================================
    # CONTEXT RETRIEVAL (the core feature)
    # ================================================================

    def get_context(self, agent_id: str, task_type: str = "", market: str = "", max_items: int = 5, max_chars: int = 8000) -> Dict:
        """
        Get relevant context for an agent from the Data Hub.

        This is the MAIN METHOD that agents call before executing.
        It returns structured context (text excerpts, data, instructions)
        that the agent can use to improve its output.

        Args:
            agent_id: The agent requesting context (e.g., "content_generator")
            task_type: Optional task specificity (e.g., "blog_draft", "email_copy")
            market: Optional market filter (e.g., "de", "it", "us")
            max_items: Max number of context sources to include
            max_chars: Max total characters to return (to fit in LLM context)

        Returns:
            {
                "agent": "Content Generator",
                "context_sources": [...],
                "instructions_text": "... compiled instructions ...",
                "total_sources": N,
                "categories_covered": [...]
            }
        """
        # 1. Find which context categories this agent needs
        relevant_cats = []
        for cat_key, cat_def in CONTEXT_CATEGORIES.items():
            if "*" in cat_def["agents"] or agent_id in cat_def["agents"] or task_type in cat_def["agents"]:
                relevant_cats.append(cat_key)

        # 2. Find tagged imports matching those categories
        matching_imports = []
        all_imports = {r["id"]: r for r in self._hub.list_all()}

        for imp_id, tag_data in self._tags.items():
            overlap = set(tag_data["tags"]) & set(relevant_cats)
            if overlap:
                imp_info = all_imports.get(imp_id)
                if imp_info:
                    matching_imports.append({
                        "import_id": imp_id,
                        "filename": imp_info.get("label", imp_info.get("filename", "")),
                        "source": imp_info.get("source", ""),
                        "matched_tags": list(overlap),
                        "priority": tag_data["priority"],
                        "tag_count": len(overlap),
                    })

        # 3. Rank by priority and tag overlap
        matching_imports.sort(key=lambda x: (x["priority"], x["tag_count"]), reverse=True)
        top_matches = matching_imports[:max_items]

        # 4. Extract content from each matched import
        context_sources = []
        instructions_parts = []
        total_chars = 0
        categories_covered = set()

        for match in top_matches:
            if total_chars >= max_chars:
                break

            full_data = self._hub.get_data(match["import_id"])
            if not full_data:
                continue

            data = full_data.get("data", [])
            record = full_data.get("record", match)

            # Extract relevant text
            excerpt = self._extract_excerpt(data, max_chars=min(2000, max_chars - total_chars), market=market)

            source_entry = {
                "id": match["import_id"],
                "filename": match["filename"],
                "source_type": match["source"],
                "tags": match["matched_tags"],
                "priority": match["priority"],
                "excerpt_chars": len(excerpt),
                "excerpt": excerpt,
            }
            context_sources.append(source_entry)
            total_chars += len(excerpt)
            categories_covered.update(match["matched_tags"])

            # Build instruction text
            tag_labels = ", ".join([CONTEXT_CATEGORIES[t]["label"] for t in match["matched_tags"]])
            instructions_parts.append(
                f"\n--- [{tag_labels}] da: {match['filename']} (priorità: {match['priority']}) ---\n{excerpt}"
            )

        # 5. Compile final context
        instructions_text = ""
        if instructions_parts:
            instructions_text = (
                f"=== CONTESTO DAL DATA HUB per {AGENT_ID_MAP.get(agent_id, agent_id)} ===\n"
                f"Task: {task_type or 'generale'} | Mercato: {market or 'tutti'}\n"
                f"Fonti: {len(context_sources)} documenti\n"
                + "".join(instructions_parts)
                + "\n=== FINE CONTESTO DATA HUB ===\n"
            )

        return {
            "agent": AGENT_ID_MAP.get(agent_id, agent_id),
            "agent_id": agent_id,
            "context_sources": context_sources,
            "instructions_text": instructions_text,
            "total_sources": len(context_sources),
            "total_chars": total_chars,
            "categories_covered": list(categories_covered),
            "categories_available": relevant_cats,
        }

    def _extract_excerpt(self, data: List[Dict], max_chars: int = 2000, market: str = "") -> str:
        """
        Extract a meaningful excerpt from import data.
        For text-based documents: concatenate paragraphs.
        For tabular data: format as key-value summaries.
        """
        if not data:
            return ""

        # Check if it's text-based (PDF, DOCX, TXT)
        if "text" in data[0]:
            parts = []
            chars = 0
            for row in data:
                text = row.get("text", "")
                # Market filter: if market specified, prefer rows mentioning that market
                if market and market.lower() not in text.lower() and len(parts) > 3:
                    continue
                if chars + len(text) > max_chars:
                    break
                parts.append(text)
                chars += len(text)
            return "\n".join(parts)

        # Tabular data: format as structured summary
        parts = []
        chars = 0
        for row in data[:50]:  # Max 50 rows
            line_parts = []
            for k, v in row.items():
                if k.startswith("_"):
                    continue
                if v and v != "":
                    line_parts.append(f"{k}: {v}")
            line = " | ".join(line_parts)
            if chars + len(line) > max_chars:
                break
            parts.append(line)
            chars += len(line)
        return "\n".join(parts)

    # ================================================================
    # PROMPT ENRICHMENT (ready-to-use for LLM calls)
    # ================================================================

    def enrich_prompt(self, base_prompt: str, agent_id: str, task_type: str = "", market: str = "") -> str:
        """
        Enrich an LLM prompt with Data Hub context.
        Simply prepends relevant context before the agent's base prompt.

        Usage in agents:
            provider = DataHubContextProvider()
            prompt = provider.enrich_prompt(
                base_prompt="Genera un blog post su lana merino per il cluster business_professional...",
                agent_id="content_generator",
                task_type="blog_draft",
                market="it"
            )
            # prompt now includes tone of voice, glossary, SEO guidelines, etc.
        """
        context = self.get_context(agent_id, task_type, market)

        if not context["instructions_text"]:
            return base_prompt  # No context available, return original

        return context["instructions_text"] + "\n\n" + base_prompt

    # ================================================================
    # DASHBOARD / API HELPERS
    # ================================================================

    def get_categories(self) -> List[Dict]:
        """Return all available context categories for the UI."""
        return [
            {
                "key": key,
                "label": cat["label"],
                "icon": cat["icon"],
                "description": cat["description"],
                "agent_count": len([a for a in cat["agents"] if a != "*"]),
                "agents": [AGENT_ID_MAP.get(a, a) for a in cat["agents"] if a != "*"] if "*" not in cat["agents"] else ["Tutti gli agenti"],
                "tagged_files": sum(1 for t in self._tags.values() if key in t["tags"]),
            }
            for key, cat in CONTEXT_CATEGORIES.items()
        ]

    def get_agent_context_map(self) -> List[Dict]:
        """Show which agents use which context categories."""
        result = []
        for agent_id, agent_name in AGENT_ID_MAP.items():
            cats = []
            for cat_key, cat_def in CONTEXT_CATEGORIES.items():
                if "*" in cat_def["agents"] or agent_id in cat_def["agents"]:
                    tagged_count = sum(1 for t in self._tags.values() if cat_key in t["tags"])
                    cats.append({
                        "category": cat_key,
                        "label": cat_def["label"],
                        "icon": cat_def["icon"],
                        "files_available": tagged_count,
                    })
            result.append({
                "agent_id": agent_id,
                "agent_name": agent_name,
                "context_categories": cats,
                "total_context_files": sum(c["files_available"] for c in cats),
            })
        return result

    # ================================================================
    # SKILL SYNC (Import skills into Data Hub as agent context)
    # ================================================================

    # Map skill files to context tags and priorities
    SKILL_MAP = {
        "albeni-seo-agent/SKILL.md": {
            "tags": ["seo_guidelines", "adv_strategy", "instructions"],
            "priority": 10,
            "label": "🎯 SEO Agent — Strategia & Istruzioni",
        },
        "albeni-seo-agent/references/budget-model.md": {
            "tags": ["adv_strategy"],
            "priority": 9,
            "label": "💰 SEO Agent — Budget Model €30K",
        },
        "albeni-seo-agent/references/competitive-intelligence.md": {
            "tags": ["competitor_data", "seo_guidelines"],
            "priority": 9,
            "label": "🏢 SEO Agent — Competitive Intelligence",
        },
        "albeni-seo-agent/references/keyword-intelligence.md": {
            "tags": ["seo_guidelines"],
            "priority": 9,
            "label": "🔑 SEO Agent — Keyword Intelligence",
        },
        "albeni-seo-agent/shared-resources/glossario-reda-albeni.json": {
            "tags": ["glossary", "product_info"],
            "priority": 10,
            "label": "📖 Glossario Tecnico Reda/Albeni",
        },
        "albeni-seo-agent/shared-resources/keyword-matrix.csv": {
            "tags": ["seo_guidelines"],
            "priority": 8,
            "label": "🔑 Keyword Matrix (4 domini × 5 mercati)",
        },
        "albeni-seo-agent/shared-resources/glossario-multilingua.csv": {
            "tags": ["glossary", "translation_memory"],
            "priority": 9,
            "label": "🌍 Glossario Multilingua",
        },
        "albeni-seo-agent/shared-resources/calendario-editoriale.csv": {
            "tags": ["content_calendar", "instructions"],
            "priority": 8,
            "label": "📅 Calendario Editoriale",
        },
        "albeni-seo-agent/shared-resources/content-pipeline.csv": {
            "tags": ["content_calendar", "instructions"],
            "priority": 8,
            "label": "📝 Content Pipeline",
        },
        "albeni-mt-translator/SKILL.md": {
            "tags": ["translation_memory", "instructions", "glossary"],
            "priority": 10,
            "label": "🌍 MT+PE Translator — Istruzioni Step 1",
        },
        "albeni-mt-validator/SKILL.md": {
            "tags": ["translation_memory", "instructions", "glossary"],
            "priority": 10,
            "label": "✅ MT+PE Validator — Istruzioni Step 3",
        },
        "albeni-mt-orchestrator/SKILL.md": {
            "tags": ["translation_memory", "instructions", "content_calendar"],
            "priority": 9,
            "label": "🔄 MT+PE Orchestrator — Workflow Pipeline",
        },
    }

    def sync_skills(self, skills_base_path: str = "/app/skills-data") -> Dict:
        """
        Import all Albeni skill files into the Data Hub and auto-tag them.
        This makes skill knowledge available to all agents via the Context Provider.

        Args:
            skills_base_path: Base path to the skills directory in the container

        Returns:
            Summary of synced files
        """
        # Try multiple possible paths (container vs local dev)
        possible_paths = [
            skills_base_path,
            "/app/skills-data",
            "/sessions/modest-awesome-euler/mnt/.skills/skills",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".skills", "skills"),
        ]

        base_path = None
        for p in possible_paths:
            if os.path.exists(p):
                base_path = p
                break

        if not base_path:
            return {"status": "error", "message": "Skills directory non trovata", "paths_tried": possible_paths}

        synced = []
        skipped = []
        errors = []

        for rel_path, config in self.SKILL_MAP.items():
            full_path = os.path.join(base_path, rel_path)
            if not os.path.exists(full_path):
                skipped.append({"file": rel_path, "reason": "File non trovato"})
                continue

            try:
                # Check if already imported (by label match)
                existing = [r for r in self._hub.list_all() if r.get("label") == config["label"]]
                if existing:
                    # Already imported — just ensure tags are correct
                    imp_id = existing[0]["id"]
                    self.tag_import(imp_id, config["tags"], config["priority"])
                    synced.append({
                        "file": rel_path,
                        "import_id": imp_id,
                        "action": "re-tagged",
                        "tags": config["tags"],
                    })
                    continue

                # Read file
                with open(full_path, "rb") as f:
                    file_bytes = f.read()

                # Import into Data Hub
                record = self._hub.import_file(
                    file_bytes=file_bytes,
                    filename=os.path.basename(full_path),
                    source_override="skill",
                    label=config["label"],
                    notes=f"Auto-synced from skill: {rel_path}",
                )

                # Tag it
                self.tag_import(record["id"], config["tags"], config["priority"])

                synced.append({
                    "file": rel_path,
                    "import_id": record["id"],
                    "action": "imported_and_tagged",
                    "tags": config["tags"],
                    "rows": record["rows_count"],
                })

            except Exception as e:
                logger.error(f"Failed to sync skill '{rel_path}': {e}")
                errors.append({"file": rel_path, "error": str(e)})

        # Reload tags
        self._tags = self._load_tags()

        result = {
            "status": "completed",
            "synced": len(synced),
            "skipped": len(skipped),
            "errors": len(errors),
            "details": synced,
        }
        if skipped:
            result["skipped_details"] = skipped
        if errors:
            result["error_details"] = errors

        logger.info(f"Skill sync completed: {len(synced)} synced, {len(skipped)} skipped, {len(errors)} errors")
        return result

    def get_summary(self) -> Dict:
        """Overall summary of the context system."""
        total_tagged = len(self._tags)
        total_imports = len(self._hub.list_all())
        categories_in_use = set()
        for tag_data in self._tags.values():
            categories_in_use.update(tag_data["tags"])

        return {
            "total_imports_in_hub": total_imports,
            "tagged_imports": total_tagged,
            "untagged_imports": total_imports - total_tagged,
            "categories_in_use": len(categories_in_use),
            "categories_available": len(CONTEXT_CATEGORIES),
            "category_details": {
                cat: {
                    "label": CONTEXT_CATEGORIES[cat]["label"],
                    "icon": CONTEXT_CATEGORIES[cat]["icon"],
                    "files": sum(1 for t in self._tags.values() if cat in t["tags"]),
                }
                for cat in CONTEXT_CATEGORIES
            },
        }
