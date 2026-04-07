"""
Klaviyo CRM Integration Service
Syncs user profiles, triggers flows, and sends personalized content.

Key features:
- Profile sync with cluster tags and IDS scores
- Flow triggering based on IDS thresholds
- Predictive send-time optimization
- Dynamic copy injection per cluster
"""
import logging
import time
import json
from typing import Dict, Optional, Any
from datetime import datetime

import httpx
from sqlalchemy.orm import Session as DBSession

from config import get_settings
from models.database import User, KlaviyoSyncLog
from models.schemas import KlaviyoSyncRequest, KlaviyoSyncResponse, IntentStage

logger = logging.getLogger(__name__)
settings = get_settings()

# Klaviyo API base URL
KLAVIYO_API_BASE = "https://a.klaviyo.com/api"

# Flow mapping based on IDS stage
FLOW_MAPPING = {
    "TOFU": {
        "flow_name": "Welcome Series - Educational",
        "description": "Storia di Reda e Albeni, introduzione al merino",
        "trigger_metric": "TOFU_Entry"
    },
    "MOFU": {
        "flow_name": "Consideration Flow - Technical",
        "description": "Comparazioni cotone vs merino, guide tecniche",
        "trigger_metric": "MOFU_Consideration"
    },
    "BOFU": {
        "flow_name": "Conversion Flow - Purchase",
        "description": "Rassicurazione prezzo, checkout facilitato",
        "trigger_metric": "BOFU_Intent_Threshold_Reached"
    },
    "POST_PURCHASE": {
        "flow_name": "Post-Purchase CX Enhancement",
        "description": "Cura del capo, cross-sell 150g/190g",
        "trigger_metric": "Purchase_Completed"
    },
    "WIN_BACK": {
        "flow_name": "Win-Back Narrative",
        "description": "Riattivazione clienti a rischio churn",
        "trigger_metric": "Churn_Risk_Detected"
    }
}


class KlaviyoService:
    """
    Manages all Klaviyo CRM interactions for the AI Orchestration Layer.
    """

    def __init__(self, db: DBSession):
        self.db = db
        self.api_key = settings.KLAVIYO_API_KEY
        self.revision = settings.KLAVIYO_REVISION
        self.headers = {
            "Authorization": f"Klaviyo-API-Key {self.api_key}",
            "revision": self.revision,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def sync_lead(self, request: KlaviyoSyncRequest) -> KlaviyoSyncResponse:
        """
        Main sync entry point. Updates Klaviyo profile and triggers appropriate flow.
        Activated when IDS > 65 (BOFU threshold).
        """
        start_time = time.time()

        try:
            # 1. Create or update Klaviyo profile
            profile_id = await self._upsert_profile(request)

            # 2. Track the intent event
            await self._track_event(request, profile_id)

            # 3. Determine and trigger the right flow
            flow_config = FLOW_MAPPING.get(request.intent_stage.value, FLOW_MAPPING["BOFU"])
            flow_triggered = flow_config["flow_name"]

            latency = int((time.time() - start_time) * 1000)

            # Log the sync
            self._log_sync(
                user_email=request.email,
                sync_type="lead_sync",
                trigger_reason=f"IDS={request.ids_score}, Stage={request.intent_stage.value}",
                payload=request.model_dump(),
                response_status=200,
                success=True,
                latency=latency
            )

            return KlaviyoSyncResponse(
                status="success",
                profile_id=profile_id,
                flow_triggered=flow_triggered,
                sync_latency_ms=latency
            )

        except Exception as e:
            latency = int((time.time() - start_time) * 1000)
            logger.error(f"Klaviyo sync failed: {e}")

            self._log_sync(
                user_email=request.email,
                sync_type="lead_sync",
                trigger_reason=f"IDS={request.ids_score}",
                payload=request.model_dump(),
                response_status=500,
                success=False,
                latency=latency,
                error=str(e)
            )

            return KlaviyoSyncResponse(
                status="error",
                sync_latency_ms=latency
            )

    async def _upsert_profile(self, request: KlaviyoSyncRequest) -> Optional[str]:
        """Create or update a Klaviyo profile with AI-enriched data."""
        payload = {
            "data": {
                "type": "profile",
                "attributes": {
                    "email": request.email,
                    "properties": {
                        "ids_score": request.ids_score,
                        "cluster_tag": request.cluster_tag,
                        "intent_stage": request.intent_stage.value,
                        "preferred_language": request.language,
                        "last_visited_domain": request.last_visited_domain,
                        "ai_routing_accuracy": request.ai_metadata.get("routing_accuracy", 0),
                        "preferred_weight": request.ai_metadata.get("preferred_weight", ""),
                        "thermal_need_detected": request.ai_metadata.get("thermal_need_detected", False),
                        "security_flag": "C2PA_Verified",
                        "last_ai_sync": datetime.utcnow().isoformat(),
                        "source": "ai_orchestration_layer"
                    }
                }
            }
        }

        if not self.api_key:
            logger.info(f"[MOCK] Klaviyo profile upsert for {request.email}")
            return f"mock_profile_{request.email}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{KLAVIYO_API_BASE}/profiles/",
                headers=self.headers,
                json=payload,
                timeout=10.0
            )

            if response.status_code in (200, 201):
                data = response.json()
                return data.get("data", {}).get("id")
            elif response.status_code == 409:
                # Profile exists, update it
                return await self._update_existing_profile(request)
            else:
                logger.error(f"Klaviyo profile creation failed: {response.status_code} - {response.text}")
                return None

    async def _update_existing_profile(self, request: KlaviyoSyncRequest) -> Optional[str]:
        """Update an existing Klaviyo profile by email."""
        if not self.api_key:
            return f"mock_profile_{request.email}"

        # First, find the profile by email
        async with httpx.AsyncClient() as client:
            search_response = await client.get(
                f"{KLAVIYO_API_BASE}/profiles/",
                headers=self.headers,
                params={"filter": f'equals(email,"{request.email}")'},
                timeout=10.0
            )

            if search_response.status_code == 200:
                profiles = search_response.json().get("data", [])
                if profiles:
                    profile_id = profiles[0]["id"]
                    # Update the profile
                    update_payload = {
                        "data": {
                            "type": "profile",
                            "id": profile_id,
                            "attributes": {
                                "properties": {
                                    "ids_score": request.ids_score,
                                    "cluster_tag": request.cluster_tag,
                                    "intent_stage": request.intent_stage.value,
                                    "preferred_language": request.language,
                                    "last_ai_sync": datetime.utcnow().isoformat()
                                }
                            }
                        }
                    }
                    await client.patch(
                        f"{KLAVIYO_API_BASE}/profiles/{profile_id}/",
                        headers=self.headers,
                        json=update_payload,
                        timeout=10.0
                    )
                    return profile_id

        return None

    async def _track_event(self, request: KlaviyoSyncRequest, profile_id: Optional[str]):
        """Track an event in Klaviyo to trigger the appropriate flow."""
        flow_config = FLOW_MAPPING.get(request.intent_stage.value, FLOW_MAPPING["BOFU"])

        payload = {
            "data": {
                "type": "event",
                "attributes": {
                    "metric": {
                        "data": {
                            "type": "metric",
                            "attributes": {
                                "name": flow_config["trigger_metric"]
                            }
                        }
                    },
                    "profile": {
                        "data": {
                            "type": "profile",
                            "attributes": {
                                "email": request.email
                            }
                        }
                    },
                    "properties": {
                        "ids_score": request.ids_score,
                        "cluster_tag": request.cluster_tag,
                        "intent_stage": request.intent_stage.value,
                        "language": request.language,
                        "domain": request.last_visited_domain,
                        "ai_metadata": request.ai_metadata,
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    "time": datetime.utcnow().isoformat()
                }
            }
        }

        if not self.api_key:
            logger.info(f"[MOCK] Klaviyo event tracked: {flow_config['trigger_metric']} for {request.email}")
            return

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{KLAVIYO_API_BASE}/events/",
                headers=self.headers,
                json=payload,
                timeout=10.0
            )

            if response.status_code not in (200, 201, 202):
                logger.error(f"Klaviyo event tracking failed: {response.status_code}")

    async def trigger_post_purchase(self, email: str, order_data: dict):
        """Trigger post-purchase flow (Unboxing, Cross-sell, Care instructions)."""
        payload = {
            "data": {
                "type": "event",
                "attributes": {
                    "metric": {
                        "data": {
                            "type": "metric",
                            "attributes": {"name": "Purchase_Completed"}
                        }
                    },
                    "profile": {
                        "data": {
                            "type": "profile",
                            "attributes": {"email": email}
                        }
                    },
                    "properties": {
                        "order_id": order_data.get("order_id"),
                        "product_weight": order_data.get("weight", "150g"),
                        "cross_sell_suggestion": "190g" if order_data.get("weight") == "150g" else "150g",
                        "care_content_url": f"https://merinouniversity.com/care-guide",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            }
        }

        if not self.api_key:
            logger.info(f"[MOCK] Post-purchase flow triggered for {email}")
            return

        async with httpx.AsyncClient() as client:
            await client.post(
                f"{KLAVIYO_API_BASE}/events/",
                headers=self.headers,
                json=payload,
                timeout=10.0
            )

    async def trigger_win_back(self, email: str, churn_risk: float, last_cluster: str):
        """Trigger win-back flow for users at risk of churn."""
        payload = {
            "data": {
                "type": "event",
                "attributes": {
                    "metric": {
                        "data": {
                            "type": "metric",
                            "attributes": {"name": "Churn_Risk_Detected"}
                        }
                    },
                    "profile": {
                        "data": {
                            "type": "profile",
                            "attributes": {"email": email}
                        }
                    },
                    "properties": {
                        "churn_risk_score": churn_risk,
                        "last_cluster": last_cluster,
                        "win_back_type": "narrative",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            }
        }

        if not self.api_key:
            logger.info(f"[MOCK] Win-back flow triggered for {email} (churn risk: {churn_risk})")
            return

        async with httpx.AsyncClient() as client:
            await client.post(
                f"{KLAVIYO_API_BASE}/events/",
                headers=self.headers,
                json=payload,
                timeout=10.0
            )

    def build_personalized_payload(
        self,
        email: str,
        ids_score: int,
        cluster_tag: str,
        ai_content: dict,
        ai_metadata: dict = {}
    ) -> dict:
        """
        Build the universal payload for Klaviyo sync.
        Matches the specification from data_implementation_klaviyo.docx
        """
        return {
            "api_version": "v1",
            "trigger_event": "BOFU_Intent_Threshold_Reached",
            "customer_properties": {
                "$email": email,
                "ids_score": ids_score,
                "cluster_tag": cluster_tag,
                "intent_stage": "BOFU",
                "last_visited_domain": ai_metadata.get("last_domain", "perfectmerinoshirt.com"),
                "ai_metadata": {
                    "routing_accuracy": ai_metadata.get("routing_accuracy", 0.92),
                    "preferred_weight": ai_metadata.get("preferred_weight", "150g"),
                    "thermal_need_detected": ai_metadata.get("thermal_need", True)
                }
            },
            "personalized_content": {
                "email_subject": ai_content.get("subject", ""),
                "hero_headline": ai_content.get("headline", ""),
                "body_copy": ai_content.get("body", ""),
                "cta_label": ai_content.get("cta_label", "Acquista l'Invisibile"),
                "cta_link": ai_content.get("cta_link", "https://perfectmerinoshirt.com/checkout")
            }
        }

    def _log_sync(
        self,
        user_email: str,
        sync_type: str,
        trigger_reason: str,
        payload: dict,
        response_status: int,
        success: bool,
        latency: int,
        error: str = None
    ):
        """Log sync attempt to database."""
        try:
            # Find user by email
            user = self.db.query(User).filter(User.email == user_email).first()

            log = KlaviyoSyncLog(
                user_id=user.id if user else None,
                sync_type=sync_type,
                trigger_reason=trigger_reason,
                payload_sent=payload,
                response_status=response_status,
                success=success,
                sync_latency_ms=latency,
                error_message=error
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log Klaviyo sync: {e}")
