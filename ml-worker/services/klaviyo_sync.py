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
        "description": "Introduzione alla fibra merino e alla filiera",
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


# Cache dell'overview CRM (liste + flow) per la pagina Klaviyo della tower.
# Le liste con profile_count sono l'endpoint piu' rate-limitato di Klaviyo
# (burst 1/s, 15/min): senza cache ogni apertura della pagina consumerebbe
# la finestra intera. TTL breve: sono dati di struttura, non di traffico.
_OVERVIEW_TTL_S = 300
_overview_cache: Dict[str, Any] = {"ts": 0.0, "data": None}


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
                visitor_id=request.visitor_id,
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
                visitor_id=request.visitor_id,
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

    @staticmethod
    def _identity(request: KlaviyoSyncRequest) -> Dict[str, str]:
        """
        Identificatori del profilo Klaviyo. Un profilo anonimo esiste solo se ha
        un external_id: usiamo il visitor_id del tracker. Quando arrivano
        entrambi li mandiamo insieme — e' cosi' che Klaviyo riconcilia il
        profilo anonimo con la lead nel momento in cui lascia l'email.
        """
        ident = {}
        if request.email:
            ident["email"] = request.email
        if request.visitor_id:
            ident["external_id"] = request.visitor_id
        return ident

    async def _fetch_all_pages(
        self, client: httpx.AsyncClient, url: str, max_pages: int = 10
    ) -> tuple:
        """
        Segue la paginazione cursor di Klaviyo (links.next) e accumula `data`.
        Ritorna (items, error): con un errore HTTP si torna quel che si ha
        gia' raccolto piu' il messaggio, mai un'eccezione — la pagina della
        tower deve poter dire "liste ok, flow negati" invece di morire intera.
        """
        items = []
        next_url = url
        for _ in range(max_pages):
            if not next_url:
                break
            try:
                resp = await client.get(next_url, headers=self.headers)
                if resp.status_code != 200:
                    detail = resp.text[:200]
                    return items, f"HTTP {resp.status_code}: {detail}"
                body = resp.json()
                items.extend(body.get("data", []))
                next_url = (body.get("links") or {}).get("next")
            except Exception as e:
                return items, str(e)
        return items, None

    async def get_crm_overview(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Liste (con profile_count) e flow reali dell'account Klaviyo, per la
        pagina CRM della tower — sostituisce lo snapshot hardcodato che
        faceva sembrare il CRM "solo WoM".
        """
        now = time.time()
        if (
            not force_refresh
            and _overview_cache["data"] is not None
            and now - _overview_cache["ts"] < _OVERVIEW_TTL_S
        ):
            return {**_overview_cache["data"], "cached": True}

        async with httpx.AsyncClient(timeout=20.0) as client:
            lists_raw, lists_error = await self._fetch_all_pages(
                client,
                f"{KLAVIYO_API_BASE}/lists/?additional-fields[list]=profile_count",
            )
            if lists_error and not lists_raw:
                # profile_count puo' mancare per scope o revision: meglio le
                # liste senza conteggio che nessuna lista.
                lists_raw, lists_error = await self._fetch_all_pages(
                    client, f"{KLAVIYO_API_BASE}/lists/"
                )
            flows_raw, flows_error = await self._fetch_all_pages(
                client, f"{KLAVIYO_API_BASE}/flows/"
            )

        data = {
            "lists": [
                {
                    "id": item.get("id"),
                    "name": (item.get("attributes") or {}).get("name"),
                    "profile_count": (item.get("attributes") or {}).get("profile_count"),
                    "created": (item.get("attributes") or {}).get("created"),
                }
                for item in lists_raw
            ],
            "flows": [
                {
                    "id": item.get("id"),
                    "name": (item.get("attributes") or {}).get("name"),
                    "status": (item.get("attributes") or {}).get("status"),
                    "archived": (item.get("attributes") or {}).get("archived"),
                    "trigger_type": (item.get("attributes") or {}).get("trigger_type"),
                }
                for item in flows_raw
            ],
            "lists_error": lists_error,
            "flows_error": flows_error,
            "fetched_at": datetime.utcnow().isoformat(),
        }
        # Un fetch completamente fallito non deve avvelenare la cache: la
        # pagina ritenterebbe fra 5 minuti mostrando errori ormai vecchi.
        if lists_raw or flows_raw:
            _overview_cache["ts"] = now
            _overview_cache["data"] = data
        return {**data, "cached": False}

    @staticmethod
    def _merge_behavioral(
        request: KlaviyoSyncRequest,
        existing: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Campi comportamentali da scrivere su un profilo che gia' esiste.

        Il tracker senza consenso *statistics* non ha localStorage, quindi la
        catena manda IDS=0 / cluster "unknown" in buona fede: senza guardia
        quegli zeri sovrascrivono un profilo gia' arricchito da un altro punto
        di raccolta (verificato 29/07 sul profilo di test del 28/07, che da
        IDS=72/italian_authentic/BOFU e' finito a 0/unknown/TOFU).

        Non e' un floor monotono: un IDS ricalcolato piu' basso e' un dato
        legittimo e passa. A non passare e' il sync *senza segnale*.
        """
        props: Dict[str, Any] = {
            "preferred_language": request.language,
            "last_ai_sync": datetime.utcnow().isoformat()
        }

        # cluster_tag: un cluster noto non torna mai a "unknown". Il passaggio
        # da un cluster noto a un altro e' invece una riclassificazione valida.
        incoming_cluster = (request.cluster_tag or "").strip()
        existing_cluster = (existing.get("cluster_tag") or "").strip()
        if incoming_cluster and incoming_cluster != "unknown":
            props["cluster_tag"] = request.cluster_tag
        elif not existing_cluster:
            props["cluster_tag"] = request.cluster_tag

        # ids_score e intent_stage viaggiano insieme: lo stage e' derivato dallo
        # score, riscriverne uno solo li lascerebbe incoerenti.
        incoming_score = request.ids_score or 0
        try:
            existing_score = int(existing.get("ids_score") or 0)
        except (TypeError, ValueError):
            existing_score = 0

        if incoming_score > 0 or existing_score <= 0:
            props["ids_score"] = request.ids_score
            props["intent_stage"] = request.intent_stage.value
        else:
            logger.info(
                "Klaviyo sync senza segnale (IDS=0) su profilo con IDS=%s: "
                "campi comportamentali preservati",
                existing_score
            )

        return props

    async def _fetch_profile_properties(self, client: httpx.AsyncClient, profile_id: str) -> Dict[str, Any]:
        """Proprieta' correnti del profilo, per poterle confrontare prima del PATCH."""
        try:
            response = await client.get(
                f"{KLAVIYO_API_BASE}/profiles/{profile_id}/",
                headers=self.headers,
                timeout=10.0
            )
            if response.status_code == 200:
                return response.json().get("data", {}).get("attributes", {}).get("properties", {}) or {}
            logger.warning(
                "Lettura profilo %s fallita (%s): il merge parte da vuoto",
                profile_id, response.status_code
            )
        except httpx.HTTPError as exc:
            logger.warning("Lettura profilo %s fallita (%s): il merge parte da vuoto", profile_id, exc)
        return {}

    async def _upsert_profile(self, request: KlaviyoSyncRequest) -> Optional[str]:
        """Create or update a Klaviyo profile with AI-enriched data."""
        payload = {
            "data": {
                "type": "profile",
                "attributes": {
                    **self._identity(request),
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

        ref = request.email or request.visitor_id

        if not self.api_key:
            logger.info(f"[MOCK] Klaviyo profile upsert for {ref}")
            return f"mock_profile_{ref}"

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
                # Profile exists. Klaviyo mette l'id del duplicato nel corpo del
                # 409: usarlo evita una ricerca in piu' e funziona anche quando
                # il match e' avvenuto sull'external_id invece che sull'email.
                duplicate_id = None
                try:
                    errors = response.json().get("errors", [])
                    duplicate_id = errors[0].get("meta", {}).get("duplicate_profile_id")
                except Exception:
                    pass
                return await self._update_existing_profile(request, profile_id=duplicate_id)
            else:
                logger.error(f"Klaviyo profile creation failed: {response.status_code} - {response.text}")
                return None

    async def _update_existing_profile(
        self,
        request: KlaviyoSyncRequest,
        profile_id: Optional[str] = None
    ) -> Optional[str]:
        """Update an existing Klaviyo profile, found by email or by external_id."""
        if not self.api_key:
            return f"mock_profile_{request.email or request.visitor_id}"

        async with httpx.AsyncClient() as client:
            existing_props: Dict[str, Any] = {}

            if not profile_id:
                # Senza email il profilo si ritrova solo per external_id.
                if request.email:
                    prof_filter = f'equals(email,"{request.email}")'
                else:
                    prof_filter = f'equals(external_id,"{request.visitor_id}")'

                search_response = await client.get(
                    f"{KLAVIYO_API_BASE}/profiles/",
                    headers=self.headers,
                    params={"filter": prof_filter},
                    timeout=10.0
                )

                if search_response.status_code == 200:
                    profiles = search_response.json().get("data", [])
                    if profiles:
                        profile_id = profiles[0]["id"]
                        existing_props = profiles[0].get("attributes", {}).get("properties", {}) or {}
            elif profile_id:
                # Veniamo dal 409: abbiamo l'id del duplicato ma non i suoi dati.
                existing_props = await self._fetch_profile_properties(client, profile_id)

            if profile_id:
                # Update the profile. Rimandiamo anche gli identificatori: se il
                # profilo era anonimo e ora conosciamo l'email, e' qui che le due
                # identita' si saldano sullo stesso profilo.
                update_payload = {
                    "data": {
                        "type": "profile",
                        "id": profile_id,
                        "attributes": {
                            **self._identity(request),
                            "properties": self._merge_behavioral(request, existing_props)
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
                            "attributes": self._identity(request)
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
            logger.info(
                f"[MOCK] Klaviyo event tracked: {flow_config['trigger_metric']} "
                f"for {request.email or request.visitor_id}"
            )
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
        user_email: Optional[str],
        sync_type: str,
        trigger_reason: str,
        payload: dict,
        response_status: int,
        success: bool,
        latency: int,
        error: str = None,
        visitor_id: Optional[str] = None
    ):
        """Log sync attempt to database."""
        try:
            # Find user by email, altrimenti per external_id (= visitor_id del
            # tracker). user_id resta NULL se il visitatore non e' ancora in DB:
            # la riga di log si scrive comunque, ed e' il punto — il contatore
            # deve misurare i tentativi, non i soli visitatori gia' noti.
            user = None
            if user_email:
                user = self.db.query(User).filter(User.email == user_email).first()
            if user is None and visitor_id:
                user = self.db.query(User).filter(User.external_id == visitor_id).first()

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
            # Il rollback evita che una scrittura di log fallita lasci la
            # sessione sporca per il resto della richiesta.
            self.db.rollback()
            logger.error(f"Failed to log Klaviyo sync: {e}")
