"""
Pydantic Schemas - Request/Response Models
AI Orchestration Layer - Albeni 1905
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum


# --- Enums ---

class IntentStage(str, Enum):
    TOFU = "TOFU"
    MOFU = "MOFU"
    BOFU = "BOFU"


class ClusterTag(str, Enum):
    BUSINESS_PROFESSIONAL = "business_professional"
    HERITAGE_MATURE = "heritage_mature"
    CONSCIOUS_PREMIUM = "conscious_premium"
    MODERN_MINIMALIST = "modern_minimalist"
    ITALIAN_AUTHENTIC = "italian_authentic"


class CPAAlertLevel(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class ContentReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISED = "revised"


# --- Tracking & Ingestion ---

class TrackEventRequest(BaseModel):
    user_id: str
    domain: str
    lang: str = "it"
    event_type: str
    metadata: Dict[str, Any] = {}
    timestamp: Optional[int] = None
    session_id: Optional[str] = None
    page_url: Optional[str] = None


class TrackEventResponse(BaseModel):
    status: str
    event_id: Optional[str] = None
    ids_points_awarded: float = 0


# --- IDS Calculation ---

class IDSCalculationRequest(BaseModel):
    user_id: str
    force_recalculate: bool = False


class IDSBreakdown(BaseModel):
    dwell_time_norm: float = 0
    dwell_time_weighted: float = 0
    scroll_depth_norm: float = 0
    scroll_depth_weighted: float = 0
    interactions_norm: float = 0
    interactions_weighted: float = 0
    frequency_norm: float = 0
    frequency_weighted: float = 0
    raw_total: float = 0
    final_score: int = 0


class IDSCalculationResponse(BaseModel):
    user_id: str
    ids_score: int
    intent_stage: IntentStage
    breakdown: IDSBreakdown
    predicted_cluster: Optional[str] = None
    cluster_confidence: float = 0
    routing_suggestion: str = ""
    calculation_latency_ms: int = 0


# --- Cluster Prediction ---

class ClusterPredictionRequest(BaseModel):
    user_id: str


class ClusterPredictionResponse(BaseModel):
    user_id: str
    predicted_cluster: str
    confidence: float
    probabilities: Dict[str, float]
    signals_analyzed: int = 0


# --- Routing ---

class RoutingRequest(BaseModel):
    user_id: str
    lang: str = "it"
    current_domain: Optional[str] = None


class RoutingResponse(BaseModel):
    user_id: str
    ids_score: int
    assigned_cluster: str
    intent_stage: IntentStage
    redirect_to: str
    language: str = "it"
    latency_ms: int = 0


# --- Content Generation ---

class ContentGenerationRequest(BaseModel):
    cluster: ClusterTag
    language: str = "it"
    content_type: str = "email_copy"  # email_copy, blog_draft, landing_copy
    intent_stage: IntentStage = IntentStage.BOFU
    custom_context: Optional[str] = None


class ContentGenerationResponse(BaseModel):
    cluster: str
    language: str
    content_type: str
    generated_content: Dict[str, Any]  # flexible: supports strings, lists, nested objects
    content_quality_score: float = 0
    model_used: str = "gpt-4o"
    review_status: str = "pending"
    tokens_used: int = 0


# --- Content Validation ---

class ContentValidationRequest(BaseModel):
    """
    Body schema for POST /v1/content/validate.
    Fix P0.2b (2026-05-12): precedentemente l'endpoint definiva cluster/language
    come parametri non-body (FastAPI li trattava come query string), quindi
    i field nel body JSON venivano IGNORATI e cluster restava sempre il default
    "business_professional". Spostati in Pydantic model per essere parsati dal body.
    """
    content: Any  # Dict, list, or string — flexible. Validator serializes via json.dumps.
    cluster: str = "business_professional"
    language: str = "it"
    content_type: str = "blog_draft"
    domain: str = ""
    keyword_target: str = ""
    funnel_stage: str = ""
    # P0.2 follow-up (2026-05-12): opt-out per smoke test rapidi. validate_with_ai
    # impiega 30-90s (Gemini sync + time.sleep(2) + Data Hub query). Quando True,
    # ritorna {'ai_validation': 'skipped', 'reason': 'opted out'} e l'endpoint
    # risponde in <3s (solo rule-based checks). Usato dal verify-p02-fixes.sh.
    skip_ai_validation: bool = False


# --- Klaviyo CRM Sync ---

class KlaviyoSyncRequest(BaseModel):
    email: str
    ids_score: int
    cluster_tag: str
    intent_stage: IntentStage = IntentStage.BOFU
    language: str = "it"
    last_visited_domain: Optional[str] = None
    ai_metadata: Dict[str, Any] = {}


class KlaviyoSyncResponse(BaseModel):
    status: str
    profile_id: Optional[str] = None
    flow_triggered: Optional[str] = None
    sync_latency_ms: int = 0


class KlaviyoPersonalizedPayload(BaseModel):
    api_version: str = "v1"
    trigger_event: str
    customer_properties: Dict[str, Any]
    personalized_content: Dict[str, str]


# --- ML Worker Intent Processing ---

class ProcessIntentRequest(BaseModel):
    email: str
    ids_score: int
    cluster_tag: str


class ProcessIntentResponse(BaseModel):
    status: str
    ids_score: Optional[int] = None
    cluster: Optional[str] = None
    payload_preview: Optional[Dict] = None
    reason: Optional[str] = None


# --- Dashboard ---

class DashboardMetrics(BaseModel):
    total_users: int = 0
    active_sessions: int = 0
    avg_ids_score: float = 0
    cluster_distribution: Dict[str, int] = {}
    intent_stage_distribution: Dict[str, int] = {}
    language_distribution: Dict[str, int] = {}
    cpa_current: float = 0
    cpa_alert_level: CPAAlertLevel = CPAAlertLevel.GREEN
    conversion_rate: float = 0
    roi_operational: float = 0
    seo_health: Dict[str, Any] = {}
    cannibalization_score: float = 0
    content_queue: int = 0
    klaviyo_sync_health: Dict[str, Any] = {}
    recent_anomalies: List[Dict[str, Any]] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# --- SEO Monitoring ---

class SEOHealthCheck(BaseModel):
    domain: str
    role: Optional[str] = None
    funnel_stage: Optional[str] = None  # TOFU / MOFU / BOFU
    behavioral_expansion_pct: float = 85.0
    semantic_defense_pct: float = 15.0
    cannibalization_score: float = 0
    conflicting_keywords: List[str] = []
    alert_level: str = "green"
    topical_authority_score: float = 0
    # New fields (live SEMrush-derived data — see ml-worker/services/seo_monitor.py)
    keywords_in_rank: int = 0       # n. di keyword in rank (top-100) per il dominio nel DB scelto
    organic_traffic: int = 0         # traffico organico stimato dal SEMrush domain overview
    authority_score: int = 0         # SEMrush authority score (0-100)
    semrush_database: str = ""       # mercato SEMrush usato (it, us, de, fr, ...)
    data_source: str = "live"        # 'live' = SEMrush ok; 'cached' = da Redis; 'fallback' = SEMrush vuoto
    fetched_at: Optional[str] = None # timestamp ISO della misurazione


# --- Health Check ---

class HealthResponse(BaseModel):
    status: str
    version: str
    services: Dict[str, str]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
