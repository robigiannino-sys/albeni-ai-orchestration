"""
Notion Integration Service - Bidirectional Sync
Albeni 1905 - AI Orchestration Layer

Connects the Content Pipeline and Calendario Editoriale on Notion
with the AI content generation engine (Gemini).

Flow:
1. READ: Fetch "Da Fare" tasks from Content Pipeline
2. GENERATE: Use Gemini to generate content for each task
3. WRITE: Push generated content back to Notion page body
4. UPDATE: Change status from "Da Fare" → "In Produzione"
5. SYNC: Push IDS/cluster data to Calendario Editoriale
"""
import logging
import json
import httpx
from typing import Dict, List, Optional
from datetime import datetime

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Map Notion cluster names to internal cluster IDs
CLUSTER_MAP = {
    "C1 Heritage Mature": "heritage_mature",
    "C2 Business Professional": "business_professional",
    "C3 Conscious Premium": "conscious_premium",
    "C4 Italian Authentic": "italian_authentic",
    "C5 Modern Minimalist": "modern_minimalist",
    "C6 Semantic Defense": "business_professional",  # fallback
    "EDU/TOFU": "conscious_premium",  # fallback for educational
}

# Map Notion content types to internal content types
CONTENT_TYPE_MAP = {
    "Cornerstone": "blog_draft",
    "Pillar Page": "blog_draft",
    "Blog Post": "blog_draft",
    "Landing Page": "landing_copy",
    "Product Page": "landing_copy",
    "FAQ": "blog_draft",
}

# Map Notion language codes to internal codes
LANGUAGE_MAP = {
    "IT": "it",
    "EN": "en",
    "DE": "de",
    "FR": "fr",
}


class NotionSync:
    """
    Bidirectional sync between Notion databases and AI Orchestration Layer.
    """

    def __init__(self):
        self.token = settings.NOTION_API_TOKEN
        self.pipeline_db = settings.NOTION_CONTENT_PIPELINE_DB
        self.calendario_db = settings.NOTION_CALENDARIO_DB
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _is_configured(self) -> bool:
        """Check if Notion integration is properly configured."""
        return bool(self.token and self.pipeline_db)

    async def get_pending_tasks(self) -> List[Dict]:
        """
        Fetch tasks with status "Da Fare" from Content Pipeline.
        These are the tasks that need AI content generation.
        """
        if not self._is_configured():
            logger.warning("Notion not configured, skipping sync")
            return []

        url = f"{NOTION_API_BASE}/databases/{self.pipeline_db}/query"
        payload = {
            "filter": {
                "property": "Stato",
                "select": {
                    "equals": "Da Fare"
                }
            },
            "sorts": [
                {
                    "property": "Mese Pubblicazione",
                    "direction": "ascending"
                }
            ]
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload, timeout=30)
                response.raise_for_status()
                data = response.json()

            tasks = []
            for page in data.get("results", []):
                props = page["properties"]
                task = {
                    "page_id": page["id"],
                    "title": self._get_title(props.get("Contenuto", {})),
                    "cluster": props.get("Cluster", {}).get("select", {}).get("name", "") if props.get("Cluster", {}).get("select") else "",
                    "domain": props.get("Dominio", {}).get("select", {}).get("name", "") if props.get("Dominio", {}).get("select") else "",
                    "content_type": props.get("Tipo Contenuto", {}).get("select", {}).get("name", "") if props.get("Tipo Contenuto", {}).get("select") else "",
                    "funnel_stage": props.get("Fase Funnel", {}).get("select", {}).get("name", "") if props.get("Fase Funnel", {}).get("select") else "",
                    "languages": [opt["name"] for opt in props.get("Lingua", {}).get("multi_select", [])],
                    "keyword_target": self._get_rich_text(props.get("Keyword Target", {})),
                    "month": props.get("Mese Pubblicazione", {}).get("select", {}).get("name", "") if props.get("Mese Pubblicazione", {}).get("select") else "",
                    "note": self._get_rich_text(props.get("Note", {})),
                }
                tasks.append(task)

            logger.info(f"Found {len(tasks)} pending tasks in Notion Content Pipeline")
            return tasks

        except Exception as e:
            logger.error(f"Failed to fetch Notion tasks: {e}")
            return []

    async def get_all_pipeline_tasks(self) -> List[Dict]:
        """
        Fetch ALL tasks from Content Pipeline (any status).
        Used for dashboard overview.
        """
        if not self._is_configured():
            return []

        url = f"{NOTION_API_BASE}/databases/{self.pipeline_db}/query"
        payload = {
            "sorts": [
                {
                    "property": "Mese Pubblicazione",
                    "direction": "ascending"
                }
            ]
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload, timeout=30)
                response.raise_for_status()
                data = response.json()

            tasks = []
            for page in data.get("results", []):
                props = page["properties"]
                task = {
                    "page_id": page["id"],
                    "title": self._get_title(props.get("Contenuto", {})),
                    "cluster": props.get("Cluster", {}).get("select", {}).get("name", "") if props.get("Cluster", {}).get("select") else "",
                    "domain": props.get("Dominio", {}).get("select", {}).get("name", "") if props.get("Dominio", {}).get("select") else "",
                    "content_type": props.get("Tipo Contenuto", {}).get("select", {}).get("name", "") if props.get("Tipo Contenuto", {}).get("select") else "",
                    "funnel_stage": props.get("Fase Funnel", {}).get("select", {}).get("name", "") if props.get("Fase Funnel", {}).get("select") else "",
                    "languages": [opt["name"] for opt in props.get("Lingua", {}).get("multi_select", [])],
                    "keyword_target": self._get_rich_text(props.get("Keyword Target", {})),
                    "month": props.get("Mese Pubblicazione", {}).get("select", {}).get("name", "") if props.get("Mese Pubblicazione", {}).get("select") else "",
                    "status": props.get("Stato", {}).get("select", {}).get("name", "") if props.get("Stato", {}).get("select") else "",
                    "note": self._get_rich_text(props.get("Note", {})),
                }
                tasks.append(task)

            return tasks

        except Exception as e:
            logger.error(f"Failed to fetch all Notion tasks: {e}")
            return []

    async def update_task_status(self, page_id: str, new_status: str, note: str = "") -> bool:
        """
        Update the status of a Content Pipeline task.
        Valid statuses: "Da Fare", "In Produzione", "In Traduzione", "In Revisione", "Pubblicato"
        """
        if not self._is_configured():
            return False

        url = f"{NOTION_API_BASE}/pages/{page_id}"
        properties = {
            "Stato": {
                "select": {"name": new_status}
            }
        }

        if note:
            properties["Note"] = {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": note}
                }]
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    url,
                    headers=self.headers,
                    json={"properties": properties},
                    timeout=30
                )
                response.raise_for_status()

            logger.info(f"Updated Notion page {page_id} status to: {new_status}")
            return True

        except Exception as e:
            logger.error(f"Failed to update Notion page {page_id}: {e}")
            return False

    async def write_content_to_page(self, page_id: str, generated_content: Dict, model_used: str, quality_score: float) -> bool:
        """
        Write AI-generated content to a Notion page body.
        Appends content blocks below the page title.
        """
        if not self._is_configured():
            return False

        url = f"{NOTION_API_BASE}/blocks/{page_id}/children"

        # Build content blocks
        blocks = []

        # Header: AI Generation metadata
        blocks.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": f"AI Generated | Model: {model_used} | Quality Score: {quality_score}/100 | {datetime.now().strftime('%d/%m/%Y %H:%M')}"}
                }],
                "icon": {"emoji": "🤖"}
            }
        })

        # Divider
        blocks.append({"object": "block", "type": "divider", "divider": {}})

        # Write content based on structure
        if isinstance(generated_content, dict):
            for key, value in generated_content.items():
                # Section heading
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": key.replace("_", " ").title()}
                        }]
                    }
                })

                # Content
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            # Handle sections with heading/content
                            text = json.dumps(item, ensure_ascii=False, indent=2)
                        else:
                            text = str(item)
                        blocks.append({
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": [{
                                    "type": "text",
                                    "text": {"content": text[:2000]}  # Notion limit
                                }]
                            }
                        })
                elif isinstance(value, str):
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{
                                "type": "text",
                                "text": {"content": value[:2000]}
                            }]
                        }
                    })

        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    url,
                    headers=self.headers,
                    json={"children": blocks},
                    timeout=30
                )
                response.raise_for_status()

            logger.info(f"Wrote AI content to Notion page {page_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to write content to Notion page {page_id}: {e}")
            return False

    async def create_pipeline_entry(self, title: str, cluster: str, domain: str,
                                     content_type: str, funnel_stage: str,
                                     languages: List[str], keyword: str = "",
                                     month: str = "", note: str = "") -> Optional[str]:
        """
        Create a new entry in the Content Pipeline database.
        Returns the page_id if successful.
        """
        if not self._is_configured():
            return None

        url = f"{NOTION_API_BASE}/pages"
        properties = {
            "Contenuto": {
                "title": [{
                    "type": "text",
                    "text": {"content": title}
                }]
            },
            "Stato": {
                "select": {"name": "Da Fare"}
            }
        }

        if cluster:
            properties["Cluster"] = {"select": {"name": cluster}}
        if domain:
            properties["Dominio"] = {"select": {"name": domain}}
        if content_type:
            properties["Tipo Contenuto"] = {"select": {"name": content_type}}
        if funnel_stage:
            properties["Fase Funnel"] = {"select": {"name": funnel_stage}}
        if languages:
            properties["Lingua"] = {"multi_select": [{"name": lang} for lang in languages]}
        if keyword:
            properties["Keyword Target"] = {"rich_text": [{"type": "text", "text": {"content": keyword}}]}
        if month:
            properties["Mese Pubblicazione"] = {"select": {"name": month}}
        if note:
            properties["Note"] = {"rich_text": [{"type": "text", "text": {"content": note}}]}

        payload = {
            "parent": {"database_id": self.pipeline_db},
            "properties": properties
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload, timeout=30)
                response.raise_for_status()
                data = response.json()

            page_id = data["id"]
            logger.info(f"Created Notion pipeline entry: {title} (ID: {page_id})")
            return page_id

        except Exception as e:
            logger.error(f"Failed to create Notion pipeline entry: {e}")
            return None

    async def get_pipeline_stats(self) -> Dict:
        """
        Get statistics from Content Pipeline for dashboard.
        """
        tasks = await self.get_all_pipeline_tasks()

        stats = {
            "total": len(tasks),
            "by_status": {},
            "by_cluster": {},
            "by_domain": {},
            "by_funnel": {},
            "by_month": {},
        }

        for task in tasks:
            status = task.get("status", "Unknown")
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

            cluster = task.get("cluster", "Unknown")
            stats["by_cluster"][cluster] = stats["by_cluster"].get(cluster, 0) + 1

            domain = task.get("domain", "Unknown")
            stats["by_domain"][domain] = stats["by_domain"].get(domain, 0) + 1

            funnel = task.get("funnel_stage", "Unknown")
            stats["by_funnel"][funnel] = stats["by_funnel"].get(funnel, 0) + 1

            month = task.get("month", "Unknown")
            stats["by_month"][month] = stats["by_month"].get(month, 0) + 1

        return stats

    def map_cluster(self, notion_cluster: str) -> str:
        """Map Notion cluster name to internal cluster ID."""
        return CLUSTER_MAP.get(notion_cluster, "business_professional")

    def map_content_type(self, notion_type: str) -> str:
        """Map Notion content type to internal content type."""
        return CONTENT_TYPE_MAP.get(notion_type, "blog_draft")

    def map_language(self, notion_lang: str) -> str:
        """Map Notion language code to internal code."""
        return LANGUAGE_MAP.get(notion_lang, "it")

    @staticmethod
    def _get_title(prop: dict) -> str:
        """Extract title text from Notion title property."""
        title_list = prop.get("title", [])
        if title_list:
            return title_list[0].get("text", {}).get("content", "")
        return ""

    @staticmethod
    def _get_rich_text(prop: dict) -> str:
        """Extract text from Notion rich_text property."""
        text_list = prop.get("rich_text", [])
        if text_list:
            return text_list[0].get("text", {}).get("content", "")
        return ""
