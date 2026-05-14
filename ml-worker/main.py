"""
AI Orchestration Layer - ML Worker (FastAPI)
Albeni 1905 - Invisible Luxury Ecosystem

The cognitive engine that powers:
- Intent Depth Score (IDS) calculation
- Cluster prediction (5 behavioral clusters)
- Personalized content generation (70/30 model)
- Klaviyo CRM synchronization
- SEO monitoring (85/15 balance)
"""
import asyncio
import logging
import time
import json
import os
from datetime import datetime, timedelta, date
from contextlib import asynccontextmanager
from typing import Optional, Dict, List

import redis.asyncio as aioredis
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Header, Query, Body, File, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import func, and_

from config import get_settings, Settings
from models.database import (
    get_db, User, Session as UserSession,
    BehavioralSignal, IntentIntelligence, ContentGenerationLog,
    KlaviyoSyncLog, RoutingDecision
)
from models.schemas import (
    TrackEventRequest, TrackEventResponse,
    IDSCalculationRequest, IDSCalculationResponse,
    ClusterPredictionRequest, ClusterPredictionResponse,
    RoutingRequest, RoutingResponse,
    ContentGenerationRequest, ContentGenerationResponse,
    ContentValidationRequest, VisualDryRunRequest, VisualGenerateRequest,
    KlaviyoSyncRequest, KlaviyoSyncResponse,
    ProcessIntentRequest, ProcessIntentResponse,
    DashboardMetrics, SEOHealthCheck, HealthResponse,
    IntentStage, ClusterTag
)
from services.ids_calculator import IDSCalculator
from services.cluster_predictor import ClusterPredictor
from services.content_generator import ContentGenerator
from services.klaviyo_sync import KlaviyoService
from services.seo_monitor import SEOMonitor
from services.notion_sync import NotionSync
from services.content_validator import ContentValidator
from services.semrush_agent import SemrushAgent
from services.semrush_data_library import SemrushDataLibrary
from services.research_hub import ResearchHub
from services.context_provider import DataHubContextProvider
from services.customer_care import CustomerCareAI
from services.ads_intelligence import ADVIntelligence, UTMSensor
from services.ads_routing import ADVRouter
from services.bot_shield import BotShield
from services.bot_shield_cache import refresh_bot_shield_cache, periodic_refresh_loop
from services.visual_generator import VisualGenerator
from services.pipeline_consumer import recompute_pipeline

# Pipeline consumer scheduler (added 2026-05-06 to fix the downstream pipeline that
# never aggregated behavioral_signals into sessions/intent_intelligence/routing_decisions).
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# Redis client (initialized on startup)
redis_client: Optional[aioredis.Redis] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: Redis + bot_shield cache + pipeline consumer scheduler."""
    global redis_client
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    logger.info("Redis connected")

    # Initial refresh of the bot_shield Redis SET that ai-router consults as a
    # gate before persisting tracking events. Without this the SET would be
    # whatever was left from previous deploys; we want a fresh truth on boot.
    await refresh_bot_shield_cache(redis_client)

    # Spawn the periodic refresh task so newly added exclusions in Postgres
    # propagate to the gate within 5 minutes without manual intervention.
    bot_shield_task = asyncio.create_task(periodic_refresh_loop(redis_client))

    # Pipeline consumer scheduler (added 2026-05-06).
    # Periodically processes new behavioral_signals so the downstream tables
    # (sessions, intent_intelligence, routing_decisions) keep up with edge ingest.
    async def _scheduled_recompute():
        from sqlalchemy import text as _sql_text  # local import keeps module load light
        try:
            db = next(get_db())
            try:
                stats = await recompute_pipeline(db, redis_client)
                logger.info(f"Scheduled pipeline recompute OK: {stats}")
            finally:
                db.close()
        except Exception as e:
            logger.exception(f"Scheduled pipeline recompute FAILED: {e}")

    # Anomaly Detection v0 (Step 3b, 2026-05-14). Daily KPI snapshot + detection.
    # Gira alle 04:15 UTC (≈06:15 Europe/Rome estate) — finestra notturna,
    # marketing_attributions del giorno prima sono già consolidate.
    async def _scheduled_anomaly():
        try:
            db = next(get_db())
            try:
                snap = _take_kpi_snapshot(db)
                det = _detect_anomalies(db)
                logger.info(f"Scheduled anomaly snapshot OK: written={snap.get('written')} "
                            f"alerts_created={det.get('alerts_created')}")
            finally:
                db.close()
        except Exception as e:
            logger.exception(f"Scheduled anomaly snapshot FAILED: {e}")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(_scheduled_recompute, "interval", minutes=15, id="pipeline_consumer",
                      coalesce=True, max_instances=1, misfire_grace_time=300)
    scheduler.add_job(_scheduled_anomaly, "cron", hour=4, minute=15, id="anomaly_daily",
                      coalesce=True, max_instances=1, misfire_grace_time=3600)
    scheduler.start()
    logger.info("Schedulers active: pipeline_consumer (15m) + anomaly_daily (04:15 UTC)")

    yield

    # Shutdown: stop scheduler, cancel periodic task, close Redis.
    scheduler.shutdown(wait=False)
    bot_shield_task.cancel()
    try:
        await bot_shield_task
    except asyncio.CancelledError:
        pass

    if redis_client:
        await redis_client.close()
        logger.info("Redis disconnected")


# FastAPI App
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI Orchestration Layer for the Albeni 1905 Invisible Luxury Ecosystem",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (chatbot widget JS)
_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


# ===================================================================
# HEALTH CHECK
# ===================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """System health check."""
    services_status = {}

    # Check Redis
    try:
        await redis_client.ping()
        services_status["redis"] = "healthy"
    except Exception:
        services_status["redis"] = "unhealthy"

    # Check DB
    try:
        from sqlalchemy import text
        db = next(get_db())
        db.execute(text("SELECT 1"))
        services_status["database"] = "healthy"
        db.close()
    except Exception as e:
        services_status["database"] = "unhealthy"
        logger.warning(f"DB health check failed: {e}")

    # Check AI Provider (Gemini or OpenAI)
    if settings.AI_PROVIDER == "gemini":
        services_status["ai_provider"] = "gemini_configured" if settings.GEMINI_API_KEY else "not_configured"
    else:
        services_status["ai_provider"] = "openai_configured" if settings.OPENAI_API_KEY else "not_configured"
    services_status["klaviyo"] = "configured" if settings.KLAVIYO_API_KEY else "not_configured"
    services_status["notion"] = "configured" if settings.NOTION_API_TOKEN else "not_configured"
    services_status["semrush"] = "configured" if settings.SEMRUSH_API_KEY else "not_configured"
    services_status["context_provider"] = "active"
    services_status["data_hub"] = "active"
    services_status["customer_care"] = "active"
    services_status["adv_intelligence"] = "active"
    services_status["bot_shield"] = "active"

    # Degraded only if critical services (db, redis) are down
    critical_healthy = services_status.get("redis") == "healthy" and services_status.get("database") == "healthy"
    return HealthResponse(
        status="healthy" if critical_healthy else "degraded",
        version=settings.APP_VERSION,
        services=services_status
    )


# ===================================================================
# TRACKING & INGESTION (L1-L2)
# ===================================================================

@app.post("/v1/track/event", response_model=TrackEventResponse)
async def track_event(event: TrackEventRequest, db: DBSession = Depends(get_db)):
    """
    Ingest behavioral signals from the 4 domains.
    Records scroll depth, dwell time, technical interactions.
    """
    try:
        # Find or create user
        user = db.query(User).filter(User.external_id == event.user_id).first()
        if not user:
            user = User(
                external_id=event.user_id,
                preferred_language=event.lang
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # Calculate IDS points for this event
        points = IDSCalculator.get_event_points(event.event_type, event.metadata)

        # Parse event-specific fields
        scroll_depth = event.metadata.get("depth") if event.event_type == "scroll_depth" else None
        dwell_seconds = event.metadata.get("seconds") if event.event_type == "dwell_time_reached" else None

        # Store the signal
        signal = BehavioralSignal(
            user_id=user.id,
            domain=event.domain,
            language=event.lang,
            event_type=event.event_type,
            event_value=event.metadata,
            scroll_depth=scroll_depth,
            dwell_time_seconds=dwell_seconds,
            interaction_type=event.metadata.get("element", event.event_type),
            interaction_element=event.metadata.get("text", ""),
            page_url=event.page_url or event.metadata.get("page_url", ""),
            ids_points_awarded=points
        )
        db.add(signal)

        # Update user's last seen
        user.last_seen_at = datetime.utcnow()
        user.preferred_language = event.lang

        db.commit()

        # Cache latest signal in Redis for fast access
        await redis_client.lpush(
            f"user:{event.user_id}:signals",
            json.dumps({
                "domain": event.domain,
                "event_type": event.event_type,
                "lang": event.lang,
                "timestamp": event.timestamp or int(datetime.utcnow().timestamp() * 1000)
            })
        )
        await redis_client.ltrim(f"user:{event.user_id}:signals", 0, 99)  # Keep last 100

        return TrackEventResponse(
            status="event_logged",
            event_id=str(signal.id),
            ids_points_awarded=points
        )

    except Exception as e:
        logger.error(f"Track event failed: {e}")
        raise HTTPException(status_code=500, detail="Event ingestion failed")


# ===================================================================
# IDS CALCULATION (L3)
# ===================================================================

@app.post("/v1/intent/calculate", response_model=IDSCalculationResponse)
async def calculate_ids(payload: Dict = Body(...), db: DBSession = Depends(get_db)):
    """
    Calculate the Intent Depth Score for a user.
    IDS = (T*0.2) + (S*0.2) + (I*0.4) + (R*0.2) scaled to 0-100.

    Schema-tolerant: accepts both modern {user_id, force_recalculate}
    and legacy widget payloads {visitor_id, dwell_time_ms, scroll_depth_pct, ...}.
    Bug 1bis fix (2026-05-05).
    """
    user_id = payload.get("user_id") or payload.get("visitor_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id or visitor_id required")
    force_recalculate = bool(payload.get("force_recalculate", False))
    calculator = IDSCalculator(redis_client, db)
    result = await calculator.calculate(user_id, force_recalculate)
    return result


# ===================================================================
# CLUSTER PREDICTION (L3)
# ===================================================================

@app.post("/v1/cluster/predict", response_model=ClusterPredictionResponse)
async def predict_cluster(payload: Dict = Body(...), db: DBSession = Depends(get_db)):
    """
    Predict which of the 5 behavioral clusters a user belongs to.
    Target accuracy: >85%.

    Schema-tolerant: accepts both modern {user_id} and legacy widget payloads
    {visitor_id, domain_type, page_url, return_visits, ...}.
    Bug 1bis fix (2026-05-05).
    """
    user_id = payload.get("user_id") or payload.get("visitor_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id or visitor_id required")
    predictor = ClusterPredictor(redis_client, db)
    result = await predictor.predict(user_id)
    return result


# ===================================================================
# AI ROUTER (L3)
# ===================================================================

@app.get("/v1/router/assign", response_model=RoutingResponse)
async def assign_route(
    user_id: Optional[str] = Query(None),
    visitor_id: Optional[str] = Query(None),
    lang: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    db: DBSession = Depends(get_db)
):
    """
    Determine the optimal destination domain based on IDS and cluster.
    TOFU (0-30) -> worldofmerino.com
    MOFU (31-65) -> merinouniversity.com
    BOFU (>65) -> perfectmerinoshirt.com or albeni1905.com (by cluster)

    Accepts either user_id (legacy) or visitor_id (current snippet convention),
    and either `lang` or `language` (sibling-endpoint convention).
    """
    # Schema-tolerant param mapping (post Bug 1bis pattern)
    user_id = user_id or visitor_id
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id or visitor_id required")
    lang = lang or language or "it"

    start_time = time.time()

    # Try Redis cache first for ultra-fast response (<120ms)
    cached_ids = await redis_client.get(f"user:{user_id}:ids")
    cached_cluster = await redis_client.get(f"user:{user_id}:cluster")

    if cached_ids is not None:
        ids_score = int(cached_ids)
        cluster = cached_cluster or "unknown"
    else:
        # Calculate fresh
        calculator = IDSCalculator(redis_client, db)
        result = await calculator.calculate(user_id)
        ids_score = result.ids_score
        cluster = result.predicted_cluster or "unknown"

    # Determine intent stage
    if ids_score <= settings.IDS_TOFU_MAX:
        stage = IntentStage.TOFU
        destination = settings.DOMAIN_TOFU
    elif ids_score <= settings.IDS_MOFU_MAX:
        stage = IntentStage.MOFU
        destination = settings.DOMAIN_MOFU
    else:
        stage = IntentStage.BOFU
        tech_clusters = ["business_professional", "modern_minimalist"]
        if cluster in tech_clusters:
            destination = settings.DOMAIN_BOFU_TECH
        else:
            destination = settings.DOMAIN_BOFU_HERITAGE

    latency = int((time.time() - start_time) * 1000)

    # Log the routing decision
    user = db.query(User).filter(User.external_id == user_id).first()
    if user:
        decision = RoutingDecision(
            user_id=user.id,
            ids_score=ids_score,
            predicted_cluster=cluster,
            destination_domain=destination,
            language=lang,
            intent_stage=stage.value,
            decision_latency_ms=latency
        )
        db.add(decision)
        db.commit()

    return RoutingResponse(
        user_id=user_id,
        ids_score=ids_score,
        assigned_cluster=cluster,
        intent_stage=stage,
        redirect_to=destination,
        language=lang,
        latency_ms=latency
    )


# ===================================================================
# CONTENT GENERATION (70/30 Model)
# ===================================================================

@app.post("/v1/content/generate", response_model=ContentGenerationResponse)
async def generate_content(request: ContentGenerationRequest, db: DBSession = Depends(get_db)):
    """
    Generate personalized content for a specific cluster and language.
    AI produces 70%, human editor reviews and finalizes 30%.
    """
    generator = ContentGenerator(db)
    result = await generator.generate(request)

    # Alert if quality score is below threshold
    if result.content_quality_score < settings.CONTENT_QUALITY_MIN:
        logger.warning(
            f"Content quality below threshold: {result.content_quality_score} < {settings.CONTENT_QUALITY_MIN} "
            f"for cluster={request.cluster.value}, lang={request.language}"
        )

    return result


# ===================================================================
# AI PROVIDER DIAGNOSTICS
# ===================================================================

@app.get("/v1/diagnostics/ai-provider")
async def diagnostics_ai_provider():
    """
    Diagnostica lo stato del provider AI senza esporre chiavi.
    Fix P0.2a (2026-05-12): /v1/content/generate ritornava sempre
    model_used="fallback" / tokens_used=0. Questo endpoint espone
    perché — config issue vs init runtime vs runtime exception.

    Restituisce:
      provider: stringa configurata (gemini/openai)
      gemini_key_set: bool — se GEMINI_API_KEY è non vuoto
      gemini_key_len: int — lunghezza della key (0 se mancante)
      gemini_model_name: stringa configurata
      gemini_init_ok: bool — True se il GenerativeModel si è inizializzato
      gemini_smoke_test_ok: bool/None — esegue una call minima a Gemini se key+init ok
      gemini_smoke_test_error: stringa — errore se smoke fallisce
      openai_key_set: bool
    """
    result = {
        "provider": settings.AI_PROVIDER,
        "gemini_key_set": bool(settings.GEMINI_API_KEY),
        "gemini_key_len": len(settings.GEMINI_API_KEY or ""),
        "gemini_model_name": settings.GEMINI_MODEL,
        "gemini_init_ok": False,
        "gemini_smoke_test_ok": None,
        "gemini_smoke_test_error": None,
        "openai_key_set": bool(settings.OPENAI_API_KEY),
    }

    if settings.AI_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel(settings.GEMINI_MODEL)
            result["gemini_init_ok"] = True

            # Smoke test minimo (1 token output, no cost rilevante)
            try:
                resp = model.generate_content(
                    "Reply with the single word: ok",
                    generation_config={"temperature": 0, "max_output_tokens": 5},
                )
                result["gemini_smoke_test_ok"] = bool(resp.text)
            except Exception as smoke_err:
                result["gemini_smoke_test_ok"] = False
                result["gemini_smoke_test_error"] = type(smoke_err).__name__ + ": " + str(smoke_err)[:200]
        except Exception as init_err:
            result["gemini_smoke_test_ok"] = False
            result["gemini_smoke_test_error"] = "INIT: " + type(init_err).__name__ + ": " + str(init_err)[:200]

    return result


# ===================================================================
# CONTENT LAKE - Persistent Content Repository
# ===================================================================

@app.get("/v1/content/lake")
async def content_lake_list(
    db: DBSession = Depends(get_db),
    cluster: Optional[str] = None,
    language: Optional[str] = None,
    content_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0)
):
    """List all generated content with filters."""
    query = db.query(ContentGenerationLog).order_by(ContentGenerationLog.created_at.desc())

    if cluster:
        query = query.filter(ContentGenerationLog.target_cluster == cluster)
    if language:
        query = query.filter(ContentGenerationLog.target_language == language)
    if content_type:
        query = query.filter(ContentGenerationLog.content_type == content_type)
    if status:
        query = query.filter(ContentGenerationLog.human_review_status == status)
    if search:
        query = query.filter(ContentGenerationLog.generated_content.ilike(f"%{search}%"))

    total = query.count()
    items = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "id": str(item.id),
                "cluster": item.target_cluster,
                "language": item.target_language,
                "content_type": item.content_type,
                "domain": item.target_domain,
                "intent_stage": item.intent_stage,
                "content": item.generated_content,
                "quality_score": float(item.content_quality_score) if item.content_quality_score else 0,
                "review_status": item.human_review_status,
                "reviewer": item.human_reviewer,
                "revision_notes": item.revision_notes,
                "model_used": item.model_used,
                "prompt_tokens": item.prompt_tokens or 0,
                "completion_tokens": item.completion_tokens or 0,
                "total_tokens": (item.prompt_tokens or 0) + (item.completion_tokens or 0),
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
            }
            for item in items
        ]
    }


@app.get("/v1/content/lake/stats/summary")
async def content_lake_stats(db: DBSession = Depends(get_db)):
    """Content Lake statistics — declared BEFORE {content_id} routes to avoid path conflicts."""
    total = db.query(func.count(ContentGenerationLog.id)).scalar() or 0
    pending = db.query(func.count(ContentGenerationLog.id)).filter(
        ContentGenerationLog.human_review_status == "pending"
    ).scalar() or 0
    approved = db.query(func.count(ContentGenerationLog.id)).filter(
        ContentGenerationLog.human_review_status == "approved"
    ).scalar() or 0
    rejected = db.query(func.count(ContentGenerationLog.id)).filter(
        ContentGenerationLog.human_review_status == "rejected"
    ).scalar() or 0

    total_tokens = db.query(
        func.coalesce(func.sum(ContentGenerationLog.prompt_tokens), 0) +
        func.coalesce(func.sum(ContentGenerationLog.completion_tokens), 0)
    ).scalar() or 0

    avg_quality = db.query(func.avg(ContentGenerationLog.content_quality_score)).scalar() or 0

    by_cluster = dict(
        db.query(ContentGenerationLog.target_cluster, func.count(ContentGenerationLog.id))
        .group_by(ContentGenerationLog.target_cluster).all()
    )
    by_type = dict(
        db.query(ContentGenerationLog.content_type, func.count(ContentGenerationLog.id))
        .group_by(ContentGenerationLog.content_type).all()
    )
    by_language = dict(
        db.query(ContentGenerationLog.target_language, func.count(ContentGenerationLog.id))
        .group_by(ContentGenerationLog.target_language).all()
    )

    return {
        "total": total,
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "total_tokens_used": total_tokens,
        "avg_quality_score": round(float(avg_quality), 1),
        "by_cluster": by_cluster,
        "by_type": by_type,
        "by_language": by_language,
    }


@app.get("/v1/content/lake/{content_id}")
async def content_lake_detail(content_id: str, db: DBSession = Depends(get_db)):
    """Get a single content entry by ID."""
    item = db.query(ContentGenerationLog).filter(ContentGenerationLog.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    return {
        "id": str(item.id),
        "cluster": item.target_cluster,
        "language": item.target_language,
        "content_type": item.content_type,
        "domain": item.target_domain,
        "intent_stage": item.intent_stage,
        "content": item.generated_content,
        "quality_score": float(item.content_quality_score) if item.content_quality_score else 0,
        "review_status": item.human_review_status,
        "reviewer": item.human_reviewer,
        "revision_notes": item.revision_notes,
        "model_used": item.model_used,
        "prompt_tokens": item.prompt_tokens or 0,
        "completion_tokens": item.completion_tokens or 0,
        "total_tokens": (item.prompt_tokens or 0) + (item.completion_tokens or 0),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
    }


@app.patch("/v1/content/lake/{content_id}")
async def content_lake_update(content_id: str, db: DBSession = Depends(get_db), body: dict = Body(...)):
    """Update review status, notes, or reviewer for a content entry."""
    item = db.query(ContentGenerationLog).filter(ContentGenerationLog.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")

    if "review_status" in body:
        item.human_review_status = body["review_status"]
    if "reviewer" in body:
        item.human_reviewer = body["reviewer"]
    if "revision_notes" in body:
        item.revision_notes = body["revision_notes"]
    if body.get("review_status") in ("approved", "rejected", "revised"):
        item.reviewed_at = datetime.utcnow()

    db.commit()
    return {"status": "updated", "id": str(item.id), "review_status": item.human_review_status}


# ===================================================================
# ML WORKER: INTENT PROCESSING + CONTENT + KLAVIYO SYNC
# ===================================================================

@app.post("/v1/ml/process-intent", response_model=ProcessIntentResponse)
async def process_intent(data: ProcessIntentRequest, db: DBSession = Depends(get_db)):
    """
    Full pipeline: Check IDS -> Generate content -> Sync to Klaviyo.
    Only activates for BOFU (IDS > 65).
    """
    if data.ids_score <= settings.IDS_BOFU_MIN:
        return ProcessIntentResponse(
            status="ignored",
            reason=f"IDS score {data.ids_score} below BOFU threshold ({settings.IDS_BOFU_MIN})"
        )

    try:
        # 1. Generate personalized copy
        generator = ContentGenerator(db)
        content_request = ContentGenerationRequest(
            cluster=ClusterTag(data.cluster_tag),
            language="it",
            content_type="email_copy",
            intent_stage=IntentStage.BOFU
        )
        content_result = await generator.generate(content_request)

        # 2. Sync to Klaviyo
        klaviyo = KlaviyoService(db)
        payload = klaviyo.build_personalized_payload(
            email=data.email,
            ids_score=data.ids_score,
            cluster_tag=data.cluster_tag,
            ai_content=content_result.generated_content
        )

        # 3. Send to Klaviyo
        sync_request = KlaviyoSyncRequest(
            email=data.email,
            ids_score=data.ids_score,
            cluster_tag=data.cluster_tag,
            intent_stage=IntentStage.BOFU
        )
        sync_result = await klaviyo.sync_lead(sync_request)

        return ProcessIntentResponse(
            status="success",
            ids_score=data.ids_score,
            cluster=data.cluster_tag,
            payload_preview=payload
        )

    except Exception as e:
        logger.error(f"Process intent failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================================================================
# ADMIN: PIPELINE CONSUMER (added 2026-05-06)
# ===================================================================

@app.post("/v1/admin/recompute-pipeline")
async def admin_recompute_pipeline(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    db: DBSession = Depends(get_db),
):
    """
    Force a full pipeline backfill: cluster prediction + IDS calculation +
    sessions aggregation for every user. Normally this runs every 15 minutes
    via the APScheduler job in lifespan(); this endpoint exists so an
    operator can trigger it on demand from the dashboard or a CLI script.

    Auth: X-Admin-Key must match settings.API_KEY.
    """
    if not settings.API_KEY or x_admin_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin key")
    stats = await recompute_pipeline(db, redis_client)
    return {"status": "ok", "stats": stats}


# ===================================================================
# KLAVIYO CRM SYNC
# ===================================================================

@app.post("/v1/crm/sync-lead", response_model=KlaviyoSyncResponse)
async def sync_lead_to_klaviyo(request: KlaviyoSyncRequest, db: DBSession = Depends(get_db)):
    """
    Sync user profile and trigger flows in Klaviyo.
    Includes cluster tags, IDS scores, and AI-generated content.
    """
    klaviyo = KlaviyoService(db)
    result = await klaviyo.sync_lead(request)
    return result


@app.post("/v1/crm/post-purchase")
async def trigger_post_purchase(
    email: str,
    order_id: str,
    weight: str = "150g",
    db: DBSession = Depends(get_db)
):
    """Trigger post-purchase flow (Unboxing, Care, Cross-sell)."""
    klaviyo = KlaviyoService(db)
    await klaviyo.trigger_post_purchase(email, {
        "order_id": order_id,
        "weight": weight
    })
    return {"status": "post_purchase_flow_triggered"}


# ===================================================================
# SEO MONITORING (85/15 Balance)
# ===================================================================

@app.get("/v1/seo/health")
async def seo_health_check(
    domain: Optional[str] = None,
    db: DBSession = Depends(get_db)
):
    """
    Run SEO health check across domains using LIVE SEMrush data.
    Behavioral / Defense / Cannibalization are computed from the actual in-rank
    keywords per domain (cached 1h in Redis to spare SEMrush API units).
    """
    monitor = SEOMonitor(db, redis_client=redis_client)
    results = await monitor.run_health_check(domain)
    return {"domains": [r.model_dump() for r in results]}


# ===================================================================
# DASHBOARD METRICS
# ===================================================================

@app.get("/v1/dashboard/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(db: DBSession = Depends(get_db)):
    """
    Aggregate metrics for the executive dashboard.
    Includes IDS averages, cluster distribution, CPA alerts, and more.
    """
    try:
        # Total users
        total_users = db.query(func.count(User.id)).scalar() or 0

        # Active sessions (last 30 min)
        active_cutoff = datetime.utcnow() - timedelta(minutes=30)
        active_sessions = db.query(func.count(UserSession.id)).filter(
            UserSession.started_at >= active_cutoff
        ).scalar() or 0

        # Average IDS
        avg_ids = db.query(func.avg(User.ids_score)).scalar() or 0

        # Cluster distribution
        cluster_dist = {}
        cluster_counts = db.query(
            User.assigned_cluster, func.count(User.id)
        ).group_by(User.assigned_cluster).all()
        for cluster, count in cluster_counts:
            if cluster:
                cluster_dist[cluster] = count

        # Intent stage distribution
        stage_dist = {}
        stage_counts = db.query(
            User.intent_stage, func.count(User.id)
        ).group_by(User.intent_stage).all()
        for stage, count in stage_counts:
            if stage:
                stage_dist[stage] = count

        # Language distribution
        lang_dist = {}
        lang_counts = db.query(
            User.preferred_language, func.count(User.id)
        ).group_by(User.preferred_language).all()
        for lang, count in lang_counts:
            if lang:
                lang_dist[lang] = count

        # Content queue (pending reviews)
        content_queue = db.query(func.count(ContentGenerationLog.id)).filter(
            ContentGenerationLog.human_review_status == "pending"
        ).scalar() or 0

        # Klaviyo sync health
        recent_syncs = db.query(func.count(KlaviyoSyncLog.id)).filter(
            KlaviyoSyncLog.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).scalar() or 0
        successful_syncs = db.query(func.count(KlaviyoSyncLog.id)).filter(
            and_(
                KlaviyoSyncLog.created_at >= datetime.utcnow() - timedelta(hours=24),
                KlaviyoSyncLog.success == True
            )
        ).scalar() or 0

        return DashboardMetrics(
            total_users=total_users,
            active_sessions=active_sessions,
            avg_ids_score=round(float(avg_ids), 1),
            cluster_distribution=cluster_dist,
            intent_stage_distribution=stage_dist,
            language_distribution=lang_dist,
            content_queue=content_queue,
            klaviyo_sync_health={
                "last_24h_total": recent_syncs,
                "last_24h_successful": successful_syncs,
                "success_rate": round(successful_syncs / max(1, recent_syncs) * 100, 1)
            }
        )

    except Exception as e:
        logger.error(f"Dashboard metrics failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to aggregate metrics")


# ===================================================================
# NOTION INTEGRATION (Editorial Calendar & Content Pipeline)
# ===================================================================

@app.get("/v1/notion/pipeline")
async def get_notion_pipeline():
    """
    Fetch all tasks from the Notion Content Pipeline.
    Returns tasks with their status, cluster, domain, and content type.
    """
    notion = NotionSync()
    tasks = await notion.get_all_pipeline_tasks()
    return {"tasks": tasks, "total": len(tasks)}


@app.get("/v1/notion/pipeline/pending")
async def get_notion_pending():
    """
    Fetch only "Da Fare" tasks from Notion Content Pipeline.
    These are ready for AI content generation.
    """
    notion = NotionSync()
    tasks = await notion.get_pending_tasks()
    return {"pending_tasks": tasks, "total": len(tasks)}


# ===================================================================
# GSC INDEXING MONITOR — migrated from filesystem JSON to Postgres
# Old version: ai-router/server.js wrote to gsc_data.json (ephemeral).
# Bug fix 2026-05-14: data persisted in DB to survive container redeploys.
# ===================================================================

# ── EMBEDDED GSC BASELINE — historical scans pre-migration ──
# Source: ai-router/dashboard/gsc_data.json committed on 2026-05-14
# The JSON file is not accessible from the ml-worker container (separate Railway service),
# so we embed the baseline here. Subsequent scans land in DB via POST /v1/gsc/report.
_GSC_BASELINE_SCANS = [
    {
        "scan_id": "wom-2026-05-13", "site": "worldofmerino.com",
        "property": "https://worldofmerino.com/", "date": "2026-05-13",
        "total_urls": 410, "indexed": 319, "crawled_not_indexed": 3,
        "not_crawled": 88, "errors": 0, "neutral": 91,
        "duration_minutes": None, "source": "manual-backfill-fix",
    },
    {
        "scan_id": "mu-2026-05-13", "site": "merinouniversity.com",
        "property": "https://merinouniversity.com/", "date": "2026-05-13",
        "total_urls": 281, "indexed": 37, "crawled_not_indexed": 7,
        "not_crawled": 237, "errors": 0, "neutral": 244,
        "duration_minutes": None, "source": "manual-backfill-fix",
    },
    {
        "scan_id": "mu-2026-04-09", "site": "merinouniversity.com",
        "property": "https://merinouniversity.com/", "date": "2026-04-09",
        "total_urls": 280, "indexed": 8, "crawled_not_indexed": 3,
        "not_crawled": 269, "errors": 0, "neutral": 272,
        "duration_minutes": 100, "source": "manual",
    },
]


def _ensure_gsc_table_and_seed(db: DBSession):
    """
    Auto-create table if missing and seed from embedded baseline (one-time bootstrap).
    Idempotent: subsequent calls do nothing once table is populated.
    """
    from models.database import GSCIndexingScan, engine
    from datetime import datetime as dt
    try:
        GSCIndexingScan.__table__.create(bind=engine, checkfirst=True)
    except Exception as e:
        logger.warning(f"GSC table create check failed (probably already exists): {e}")
    count = db.query(GSCIndexingScan).count()
    if count > 0:
        return False
    inserted = 0
    for s in _GSC_BASELINE_SCANS:
        try:
            row = GSCIndexingScan(
                scan_id=s["scan_id"],
                site=s["site"],
                property=s["property"],
                date=dt.fromisoformat(s["date"]).date(),
                total_urls=s["total_urls"],
                indexed=s["indexed"],
                crawled_not_indexed=s["crawled_not_indexed"],
                not_crawled=s["not_crawled"],
                errors=s["errors"],
                neutral=s["neutral"],
                duration_minutes=s["duration_minutes"],
                source=s["source"],
            )
            db.add(row)
            inserted += 1
        except Exception as e:
            logger.warning(f"GSC seed: skip row {s.get('scan_id')}: {e}")
    db.commit()
    logger.info(f"GSC seed: inserted {inserted} scans from embedded baseline")
    return True


@app.get("/v1/gsc/history")
async def gsc_history(
    site: Optional[str] = Query(None, description="Filter by site (worldofmerino.com, merinouniversity.com)"),
    db: DBSession = Depends(get_db)
):
    """
    Return GSC indexing scan history. Persisted in Postgres (table gsc_indexing_scans).
    Bootstraps from legacy gsc_data.json on first call if table is empty.
    Maintains backward-compatible response shape: {scans: [...], total: N}.
    """
    from models.database import GSCIndexingScan
    _ensure_gsc_table_and_seed(db)
    q = db.query(GSCIndexingScan)
    if site:
        q = q.filter(GSCIndexingScan.site == site)
    rows = q.order_by(GSCIndexingScan.date.desc()).all()
    scans = []
    for r in rows:
        scans.append({
            "id": r.scan_id,
            "site": r.site,
            "property": r.property,
            "date": r.date.isoformat() if r.date else None,
            "total_urls": r.total_urls,
            "indexed": r.indexed,
            "crawled_not_indexed": r.crawled_not_indexed,
            "not_crawled": r.not_crawled,
            "errors": r.errors,
            "neutral": r.neutral,
            "duration_minutes": r.duration_minutes,
            "source": r.source,
        })
    return {"scans": scans, "total": len(scans)}


@app.post("/v1/gsc/report")
async def gsc_report(
    request: Request,
    payload: Dict = Body(...),
    db: DBSession = Depends(get_db)
):
    """
    Record a new GSC scan. Idempotent on scan_id (UPSERT semantics: re-scan same day overwrites).
    API key check kept for compatibility with existing gsc_index_monitor.py script.
    Body: {site, date, total_urls, indexed, crawled_not_indexed, not_crawled, errors, neutral, source?, duration_minutes?}
    """
    from models.database import GSCIndexingScan
    from datetime import datetime as dt

    api_key = (request.headers.get("x-api-key") or request.query_params.get("api_key") or "").strip()
    expected = (os.environ.get("API_KEY") or "albeni-gsc-2026").strip()
    if api_key != expected:
        logger.warning(f"GSC POST 401: api_key_len={len(api_key)} expected_len={len(expected)}")
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not payload.get("site") or not payload.get("date") or payload.get("total_urls") is None:
        raise HTTPException(status_code=400, detail="Missing required fields: site, date, total_urls")

    _ensure_gsc_table_and_seed(db)

    # Generate scan_id (compat with Node implementation pattern)
    site_short = "mu" if "merinouniversity" in payload["site"] else "wom"
    scan_id = f"{site_short}-{payload['date']}"

    # UPSERT - delete existing same-day scan, insert new one
    db.query(GSCIndexingScan).filter(GSCIndexingScan.scan_id == scan_id).delete()
    row = GSCIndexingScan(
        scan_id=scan_id,
        site=payload["site"],
        property=payload.get("property"),
        date=dt.fromisoformat(payload["date"]).date(),
        total_urls=payload.get("total_urls", 0),
        indexed=payload.get("indexed", 0),
        crawled_not_indexed=payload.get("crawled_not_indexed", 0),
        not_crawled=payload.get("not_crawled", 0),
        errors=payload.get("errors", 0),
        neutral=payload.get("neutral", 0),
        duration_minutes=payload.get("duration_minutes"),
        source=payload.get("source", "manual"),
    )
    db.add(row)
    db.commit()

    total = db.query(GSCIndexingScan).count()
    return {"status": "ok", "id": scan_id, "total_scans": total}


@app.get("/v1/notion/pipeline/stats")
async def get_notion_stats():
    """
    Get Content Pipeline statistics for dashboard.
    Breakdown by status, cluster, domain, funnel stage, month.
    """
    notion = NotionSync()
    stats = await notion.get_pipeline_stats()
    return stats


# ===================================================================
# ADV SPEND TRACKING — sblocca Tile T1 CPA (Dashboard Executive)
# Pattern speculare al fix GSC del 2026-05-14: persistenza Postgres,
# UPSERT idempotente, auto-create al primo POST.
# Spec: Audit_Closure_2026-05-14.docx → Step 3a (P1).
# Soglie CPA (doc 19): VERDE ≤€9 · GIALLO €10-15 · ROSSO €16-34 · NERO ≥€35
# ===================================================================

# Canali ADV supportati. Estendere qui se si aggiungono piattaforme.
_ADV_CHANNELS = {"google_ads", "meta_ads", "tiktok_ads", "linkedin_ads", "manual"}


def _ensure_adv_spend_table(db: DBSession):
    """
    Auto-create adv_spend table if missing. Idempotente.
    Non c'è seed perché lo spend storico arriva dalla sync (Step 3a Sessione 2).
    """
    from models.database import AdvSpend, engine
    try:
        AdvSpend.__table__.create(bind=engine, checkfirst=True)
    except Exception as e:
        logger.warning(f"adv_spend table create check failed (probably already exists): {e}")


def _build_spend_id(channel: str, date_str: str, campaign_id: Optional[str]) -> str:
    """
    Idempotency key per UPSERT. Re-sync stesso giorno/campagna sovrascrive.
    Formato: {channel}-{YYYY-MM-DD}-{campaign_id|'_none_'}
    """
    cid = (campaign_id or "_none_").strip().replace(" ", "_")[:120]
    return f"{channel}-{date_str}-{cid}"


@app.post("/v1/adv/spend/report")
async def adv_spend_report(
    request: Request,
    payload: Dict = Body(...),
    db: DBSession = Depends(get_db)
):
    """
    Ingest spend ADV — single row per channel/date/campaign.

    Body atteso:
        {
            "channel": "google_ads" | "meta_ads" | ...,
            "date": "YYYY-MM-DD",
            "amount_eur": 12.34,
            "campaign_id": "optional platform ID",
            "campaign_name": "optional human label",
            "currency": "EUR",
            "amount_original": 12.34,
            "impressions": 1000,
            "clicks": 50,
            "country": "IT" | "DE" | "FR" | "US" | "UK",
            "source": "google_ads_sync" | "meta_ads_sync" | "manual"
        }

    Auth: header `x-api-key` o query `api_key` deve matchare env `API_KEY`
          (effettivo su albeni-ai-orchestration: albeni1905-internal-api-v1).
    Idempotenza: UPSERT su (channel, date, campaign_id).
    """
    from models.database import AdvSpend
    from datetime import datetime as dt
    from decimal import Decimal, InvalidOperation

    # ── Auth ──
    api_key = (request.headers.get("x-api-key") or request.query_params.get("api_key") or "").strip()
    expected = (os.environ.get("API_KEY") or "albeni-gsc-2026").strip()
    if api_key != expected:
        logger.warning(f"ADV POST 401: api_key_len={len(api_key)} expected_len={len(expected)}")
        raise HTTPException(status_code=401, detail="Unauthorized")

    # ── Validation ──
    channel = (payload.get("channel") or "").strip().lower()
    date_str = (payload.get("date") or "").strip()
    amount_raw = payload.get("amount_eur")

    if not channel:
        raise HTTPException(status_code=400, detail="Missing required field: channel")
    if channel not in _ADV_CHANNELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported channel '{channel}'. Allowed: {sorted(_ADV_CHANNELS)}"
        )
    if not date_str:
        raise HTTPException(status_code=400, detail="Missing required field: date")
    try:
        date_obj = dt.fromisoformat(date_str).date()
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid date '{date_str}', expected YYYY-MM-DD")
    if amount_raw is None:
        raise HTTPException(status_code=400, detail="Missing required field: amount_eur")
    try:
        amount_eur = Decimal(str(amount_raw))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"Invalid amount_eur '{amount_raw}'")
    if amount_eur < 0:
        raise HTTPException(status_code=400, detail="amount_eur must be >= 0")

    _ensure_adv_spend_table(db)

    spend_id = _build_spend_id(channel, date_str, payload.get("campaign_id"))

    # UPSERT — delete-then-insert (stesso pattern di /v1/gsc/report)
    db.query(AdvSpend).filter(AdvSpend.spend_id == spend_id).delete()
    row = AdvSpend(
        spend_id=spend_id,
        date=date_obj,
        channel=channel,
        campaign_id=(payload.get("campaign_id") or None),
        campaign_name=(payload.get("campaign_name") or None),
        amount_eur=amount_eur,
        currency=(payload.get("currency") or "EUR").upper()[:3],
        amount_original=(
            Decimal(str(payload["amount_original"]))
            if payload.get("amount_original") is not None else None
        ),
        impressions=payload.get("impressions"),
        clicks=payload.get("clicks"),
        country=((payload.get("country") or "").upper()[:2] or None),
        source=(payload.get("source") or "manual")[:50],
    )
    db.add(row)
    db.commit()

    total = db.query(AdvSpend).count()
    return {
        "status": "ok",
        "spend_id": spend_id,
        "channel": channel,
        "date": date_str,
        "amount_eur": float(amount_eur),
        "total_rows": total,
    }


@app.post("/v1/adv/spend/batch")
async def adv_spend_batch(
    request: Request,
    payload: Dict = Body(...),
    db: DBSession = Depends(get_db)
):
    """
    Batch ingest — accetta `{"rows": [...]}` con le stesse chiavi di /v1/adv/spend/report.
    Pensato per sync giornaliero da Google Ads / Meta Ads (Step 3a Sessione 2).
    Auth identica a /v1/adv/spend/report. UPSERT per riga.

    Risposta: {ok, inserted, errors: [...]} così la sync sa cosa è andato a fuoco.
    """
    from models.database import AdvSpend
    from datetime import datetime as dt
    from decimal import Decimal, InvalidOperation

    api_key = (request.headers.get("x-api-key") or request.query_params.get("api_key") or "").strip()
    expected = (os.environ.get("API_KEY") or "albeni-gsc-2026").strip()
    if api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    rows_in = payload.get("rows")
    if not isinstance(rows_in, list) or not rows_in:
        raise HTTPException(status_code=400, detail="Body must contain non-empty 'rows' array")

    _ensure_adv_spend_table(db)

    inserted = 0
    errors = []
    for i, item in enumerate(rows_in):
        try:
            channel = (item.get("channel") or "").strip().lower()
            date_str = (item.get("date") or "").strip()
            if channel not in _ADV_CHANNELS:
                raise ValueError(f"unsupported channel '{channel}'")
            date_obj = dt.fromisoformat(date_str).date()
            amount_eur = Decimal(str(item.get("amount_eur", 0)))
            if amount_eur < 0:
                raise ValueError("amount_eur must be >= 0")

            spend_id = _build_spend_id(channel, date_str, item.get("campaign_id"))
            db.query(AdvSpend).filter(AdvSpend.spend_id == spend_id).delete()
            db.add(AdvSpend(
                spend_id=spend_id,
                date=date_obj,
                channel=channel,
                campaign_id=(item.get("campaign_id") or None),
                campaign_name=(item.get("campaign_name") or None),
                amount_eur=amount_eur,
                currency=(item.get("currency") or "EUR").upper()[:3],
                amount_original=(
                    Decimal(str(item["amount_original"]))
                    if item.get("amount_original") is not None else None
                ),
                impressions=item.get("impressions"),
                clicks=item.get("clicks"),
                country=((item.get("country") or "").upper()[:2] or None),
                source=(item.get("source") or "manual")[:50],
            ))
            inserted += 1
        except (InvalidOperation, ValueError, TypeError, KeyError) as e:
            errors.append({"index": i, "error": str(e), "item": item})

    db.commit()
    total = db.query(AdvSpend).count()
    return {
        "status": "ok" if not errors else "partial",
        "inserted": inserted,
        "errors": errors,
        "total_rows": total,
    }


@app.get("/v1/adv/spend/summary")
async def adv_spend_summary(
    days: int = Query(default=7, ge=1, le=365, description="Lookback window in days"),
    channel: Optional[str] = Query(default=None, description="Filter by channel"),
    db: DBSession = Depends(get_db)
):
    """
    Riepilogo spend per finestra mobile.
    Usato da /v1/executive/aggregates per il calcolo CPA (Step 3a Sessione 3)
    e disponibile come endpoint pubblico (con auth header non richiesto) per il debug rapido.

    Risposta:
        {
            window_days, since, total_spend_eur, total_rows,
            by_channel: [{channel, spend_eur, rows}],
            by_day:     [{date, spend_eur}],
            latest_date
        }
    """
    from models.database import AdvSpend
    from sqlalchemy import func, text
    from datetime import datetime, timezone, timedelta

    _ensure_adv_spend_table(db)

    now = datetime.now(timezone.utc)
    since_dt = (now - timedelta(days=days)).date()

    base_q = db.query(AdvSpend).filter(AdvSpend.date >= since_dt)
    if channel:
        base_q = base_q.filter(AdvSpend.channel == channel.strip().lower())

    total_spend = base_q.with_entities(func.coalesce(func.sum(AdvSpend.amount_eur), 0)).scalar() or 0
    total_rows = base_q.count()

    by_channel_q = (
        base_q.with_entities(
            AdvSpend.channel,
            func.coalesce(func.sum(AdvSpend.amount_eur), 0),
            func.count(AdvSpend.id),
        )
        .group_by(AdvSpend.channel)
        .order_by(func.sum(AdvSpend.amount_eur).desc())
    )

    by_day_q = (
        base_q.with_entities(
            AdvSpend.date,
            func.coalesce(func.sum(AdvSpend.amount_eur), 0),
        )
        .group_by(AdvSpend.date)
        .order_by(AdvSpend.date.desc())
    )

    latest = db.query(func.max(AdvSpend.date)).scalar()

    return {
        "window_days": days,
        "since": since_dt.isoformat(),
        "computed_at": now.isoformat(),
        "filter_channel": channel,
        "total_spend_eur": float(total_spend),
        "total_rows": total_rows,
        "latest_date": latest.isoformat() if latest else None,
        "by_channel": [
            {"channel": c, "spend_eur": float(s), "rows": int(r)}
            for c, s, r in by_channel_q.all()
        ],
        "by_day": [
            {"date": d.isoformat(), "spend_eur": float(s)}
            for d, s in by_day_q.all()
        ],
    }


# ===================================================================
# CRO ENGINE — Step 7 (2026-05-14)
# Multi-Armed Bandit per microcopy adattivo. Modulo 6 dei 7 AI Stack originali.
# Algoritmo: epsilon-greedy 10% exploration / 90% exploitation.
# Step 7.1 (questa sessione): schema + helper + select_variant() + record_*
# Step 7.2: endpoint REST. Step 7.3: frontend integration.
# ===================================================================

import random as _cro_random

# Soglie MAB (override via env se serve calibrare exploration)
_CRO_EPSILON         = float(os.environ.get("CRO_EPSILON", "0.10"))        # 10% exploration
_CRO_MIN_EXPOSURES   = int(os.environ.get("CRO_MIN_EXPOSURES", "30"))      # sotto questa soglia gira pure exploration
_CRO_TIE_BREAK_BY_RECENCY = True  # se più variant hanno stesso winrate, preferisci la meno esposta (esplora di più)


def _ensure_cro_tables(db: DBSession):
    """Auto-create cro_slots + cro_variants + cro_exposures + cro_conversions. Idempotente."""
    from models.database import CROSlot, CROVariant, CROExposure, CROConversion, engine
    try:
        CROSlot.__table__.create(bind=engine, checkfirst=True)
        CROVariant.__table__.create(bind=engine, checkfirst=True)
        CROExposure.__table__.create(bind=engine, checkfirst=True)
        CROConversion.__table__.create(bind=engine, checkfirst=True)
    except Exception as e:
        logger.warning(f"CRO tables create check failed (probably already exist): {e}")


def _eligible_variants(db: DBSession, slot_key: str, cluster: Optional[str] = None,
                        language: str = "it"):
    """
    Ritorna le variant attive per uno slot, filtrate per cluster + language.
    Fallback hierarchy:
      1. Match esatto: cluster + language
      2. Fallback: cluster=NULL (generic) + language match
      3. Fallback finale: cluster=NULL + language=NULL (catch-all)
    """
    from models.database import CROSlot, CROVariant
    slot = db.query(CROSlot).filter(CROSlot.slot_key == slot_key, CROSlot.active == True).first()
    if not slot:
        return [], None

    base_q = db.query(CROVariant).filter(
        CROVariant.slot_id == slot.id,
        CROVariant.active == True
    )

    # Tier 1: cluster + language match esatti (più specifico)
    if cluster:
        rows = base_q.filter(CROVariant.cluster == cluster, CROVariant.language == language).all()
        if rows:
            return rows, slot

    # Tier 2: cluster generic (NULL) ma language match
    rows = base_q.filter(CROVariant.cluster.is_(None), CROVariant.language == language).all()
    if rows:
        return rows, slot

    # Tier 3: catch-all (qualsiasi cluster, qualsiasi language)
    rows = base_q.all()
    return rows, slot


def _select_variant(db: DBSession, slot_key: str, cluster: Optional[str] = None,
                     language: str = "it"):
    """
    MAB epsilon-greedy:
      - Se total exposures per slot < _CRO_MIN_EXPOSURES → pure random (cold start)
      - Altrimenti: con probabilità EPSILON → random (exploration);
                    altrimenti → variant con winrate massimo (exploitation).
      - Tie-break per winrate uguali: variant con meno esposizioni (più esplorazione).

    Ritorna (variant, slot) oppure (None, None) se nessuna variant eligibile.
    """
    variants, slot = _eligible_variants(db, slot_key, cluster=cluster, language=language)
    if not variants:
        return None, None

    total_exposures = sum(v.exposure_count or 0 for v in variants)

    # Cold start: troppo poco signal, gira pure random
    if total_exposures < _CRO_MIN_EXPOSURES:
        return _cro_random.choice(variants), slot

    # Exploration: con epsilon% probabilità → random
    if _cro_random.random() < _CRO_EPSILON:
        return _cro_random.choice(variants), slot

    # Exploitation: prendi quella con winrate massimo
    def winrate(v):
        return (v.win_count or 0) / max(v.exposure_count or 0, 1)

    sorted_variants = sorted(variants, key=lambda v: (-winrate(v), v.exposure_count or 0))
    return sorted_variants[0], slot


def _coerce_user_uuid(raw_user_id) -> Optional[object]:
    """
    Parse user_id (string) come UUID. Se invalid o se l'user non esiste nella
    tabella users, ritorna None (downgrade a "anonymous exposure"). Pattern
    "loose attribution": un visitor pure cookie-only è OK senza FK strict.

    Bug fix 2026-05-14: lo smoke test (e widget JS lato WP con cookie esterni)
    passa user_id che non sempre corrisponde a un utente del DB. La FK
    cro_exposures.user_id → users.id provocava Internal Server Error.
    """
    from uuid import UUID
    if raw_user_id is None:
        return None
    try:
        return UUID(str(raw_user_id))
    except (ValueError, AttributeError, TypeError):
        return None


def _record_exposure(db: DBSession, variant_id: int, user_id: Optional[str] = None,
                      session_id: Optional[str] = None):
    """
    Log un'esposizione. Increment exposure_count atomicamente.
    Ritorna CROExposure persisted (con id valido per future conversion linking).

    user_id parsing: accetta string (es. da query param), prova UUID parse;
    se invalid o user non esistente in `users`, downgrade a None.
    """
    from models.database import CROVariant, CROExposure, User
    from datetime import datetime as dt

    # Coerce + verifica FK
    user_uuid = _coerce_user_uuid(user_id)
    if user_uuid is not None:
        # FK check: se l'user_id non esiste in users, downgrade a None
        # (evita IntegrityError; pattern "loose attribution" per visitor esterni)
        exists = db.query(User.id).filter(User.id == user_uuid).first()
        if not exists:
            user_uuid = None

    exposure = CROExposure(
        variant_id=variant_id,
        user_id=user_uuid,
        session_id=(session_id[:100] if session_id else None),
        served_at=dt.utcnow(),
    )
    db.add(exposure)
    # Bump counter
    variant = db.query(CROVariant).filter(CROVariant.id == variant_id).first()
    if variant:
        variant.exposure_count = (variant.exposure_count or 0) + 1
    db.commit()
    db.refresh(exposure)
    return exposure


def _record_conversion(db: DBSession, exposure_id: int, conversion_type: str,
                        value_eur: Optional[float] = None):
    """
    Registra una conversion linkata a un'exposure. Increment win_count della variant.
    Idempotente: se l'exposure è già 'converted', non duplica.
    """
    from models.database import CROVariant, CROExposure, CROConversion
    from datetime import datetime as dt
    from decimal import Decimal

    exposure = db.query(CROExposure).filter(CROExposure.id == exposure_id).first()
    if not exposure:
        return None, "exposure_not_found"
    if exposure.converted:
        return exposure, "already_converted"

    conversion = CROConversion(
        exposure_id=exposure_id,
        conversion_type=conversion_type,
        value_eur=Decimal(str(value_eur)) if value_eur is not None else None,
    )
    db.add(conversion)
    exposure.converted = True
    exposure.conversion_recorded_at = dt.utcnow()
    variant = db.query(CROVariant).filter(CROVariant.id == exposure.variant_id).first()
    if variant:
        variant.win_count = (variant.win_count or 0) + 1
    db.commit()
    return conversion, "ok"


@app.post("/v1/cro/slot")
async def cro_slot_upsert(
    request: Request,
    payload: Dict = Body(...),
    db: DBSession = Depends(get_db)
):
    """
    Admin: crea/aggiorna uno slot CRO. Auth API_KEY.
    Body: {slot_key, description?, active?}
    Idempotente: UPSERT su slot_key.
    """
    from models.database import CROSlot

    api_key = (request.headers.get("x-api-key") or request.query_params.get("api_key") or "").strip()
    expected = (os.environ.get("API_KEY") or "albeni-gsc-2026").strip()
    if api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    slot_key = (payload.get("slot_key") or "").strip()
    if not slot_key:
        raise HTTPException(status_code=400, detail="Missing slot_key")

    _ensure_cro_tables(db)
    existing = db.query(CROSlot).filter(CROSlot.slot_key == slot_key).first()
    if existing:
        if "description" in payload:
            existing.description = payload.get("description")
        if "active" in payload:
            existing.active = bool(payload.get("active"))
        db.commit()
        return {"status": "updated", "slot_id": existing.id, "slot_key": slot_key}
    slot = CROSlot(
        slot_key=slot_key,
        description=payload.get("description"),
        active=bool(payload.get("active", True)),
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return {"status": "created", "slot_id": slot.id, "slot_key": slot_key}


@app.post("/v1/cro/variant")
async def cro_variant_upsert(
    request: Request,
    payload: Dict = Body(...),
    db: DBSession = Depends(get_db)
):
    """
    Admin: crea/aggiorna una variant. Auth API_KEY.
    Body: {slot_key, variant_key, text, cluster?, language?, active?}
    UPSERT su (slot_key, variant_key).
    NB: non resetta exposure_count/win_count su update — questi accumulano.
    """
    from models.database import CROSlot, CROVariant

    api_key = (request.headers.get("x-api-key") or request.query_params.get("api_key") or "").strip()
    expected = (os.environ.get("API_KEY") or "albeni-gsc-2026").strip()
    if api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    slot_key = (payload.get("slot_key") or "").strip()
    variant_key = (payload.get("variant_key") or "").strip()
    text = payload.get("text") or ""
    if not slot_key or not variant_key or not text:
        raise HTTPException(status_code=400, detail="Required: slot_key, variant_key, text")

    _ensure_cro_tables(db)
    slot = db.query(CROSlot).filter(CROSlot.slot_key == slot_key).first()
    if not slot:
        raise HTTPException(status_code=404, detail=f"Slot '{slot_key}' not found (create via POST /v1/cro/slot first)")

    existing = db.query(CROVariant).filter(
        CROVariant.slot_id == slot.id, CROVariant.variant_key == variant_key
    ).first()

    if existing:
        existing.text = text
        if "cluster" in payload:
            existing.cluster = payload.get("cluster") or None
        if "language" in payload:
            existing.language = (payload.get("language") or "it").lower()[:5]
        if "active" in payload:
            existing.active = bool(payload.get("active"))
        db.commit()
        return {"status": "updated", "variant_id": existing.id,
                "exposure_count": existing.exposure_count, "win_count": existing.win_count}

    variant = CROVariant(
        slot_id=slot.id,
        variant_key=variant_key,
        text=text,
        cluster=payload.get("cluster") or None,
        language=(payload.get("language") or "it").lower()[:5],
        active=bool(payload.get("active", True)),
    )
    db.add(variant)
    db.commit()
    db.refresh(variant)
    return {"status": "created", "variant_id": variant.id}


@app.get("/v1/cro/microcopy")
async def cro_microcopy(
    slot: str = Query(..., description="slot_key (es. 'homepage_hero_cta')"),
    cluster: Optional[str] = Query(None, description="Filtro cluster comportamentale"),
    language: str = Query(default="it", description="Codice lingua (it, en, de, fr)"),
    user_id: Optional[str] = Query(None, description="UUID utente (per dedup esposizioni)"),
    session_id: Optional[str] = Query(None, description="Session ID per dedup intra-sessione"),
    db: DBSession = Depends(get_db)
):
    """
    Endpoint principale del CRO Engine — serve il testo della variant scelta dal MAB.
    Chiamato dal widget JS al pageload, ritorna {variant_id, variant_key, text, exposure_id}.

    Logica:
    1. Selection MAB epsilon-greedy (10% exploration / 90% exploitation, vedi _select_variant)
    2. Log exposure su cro_exposures (bump exposure_count della variant)
    3. Ritorna l'exposure_id per il widget — necessario per /v1/cro/conversion futuro

    No auth: read-only public endpoint (chiamato da WP frontend senza credenziali).
    """
    _ensure_cro_tables(db)

    variant, slot_obj = _select_variant(db, slot, cluster=cluster, language=language)
    if not variant:
        # No variant configurata → ritorna 200 con fallback null, il widget mostrerà il default hardcoded
        return {
            "found": False,
            "slot_key": slot,
            "reason": "no_active_variant_for_slot_cluster_language",
            "filters": {"cluster": cluster, "language": language},
        }

    exposure = _record_exposure(db, variant.id, user_id=user_id, session_id=session_id)

    return {
        "found": True,
        "slot_key": slot,
        "variant_id": variant.id,
        "variant_key": variant.variant_key,
        "text": variant.text,
        "exposure_id": exposure.id,
        "cluster": variant.cluster,
        "language": variant.language,
    }


@app.post("/v1/cro/conversion")
async def cro_conversion(
    request: Request,
    payload: Dict = Body(...),
    db: DBSession = Depends(get_db)
):
    """
    Registra conversion event attribuita a una specifica exposure.
    Body: {exposure_id, conversion_type, value_eur?}
    Auth API_KEY (per evitare conversion injection da client malevoli).

    Effetti: incrementa win_count della variant, marca l'exposure converted=True.
    Idempotente: se l'exposure è già 'converted', non incrementa nuovamente.
    """
    api_key = (request.headers.get("x-api-key") or request.query_params.get("api_key") or "").strip()
    expected = (os.environ.get("API_KEY") or "albeni-gsc-2026").strip()
    if api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    exposure_id = payload.get("exposure_id")
    conversion_type = (payload.get("conversion_type") or "").strip() or "default"
    value_eur = payload.get("value_eur")

    if not exposure_id:
        raise HTTPException(status_code=400, detail="Missing exposure_id")

    _ensure_cro_tables(db)
    conversion, status = _record_conversion(db, int(exposure_id), conversion_type,
                                             value_eur=float(value_eur) if value_eur is not None else None)
    if status == "exposure_not_found":
        raise HTTPException(status_code=404, detail="Exposure not found")
    return {
        "status": status,
        "exposure_id": exposure_id,
        "conversion_type": conversion_type,
        "value_eur": value_eur,
    }


@app.get("/v1/cro/stats")
async def cro_stats(
    slot: Optional[str] = Query(None, description="Filtra per slot_key (omesso = tutti)"),
    db: DBSession = Depends(get_db)
):
    """
    Performance per variant. Comodo per dashboard CRO Live tile (Task #7.3)
    + decisioni operative (pause/promote variant manualmente).

    Ritorna per ogni variant: exposures, wins, cr_pct, lift_vs_avg, status_band.
    Status band:
      - 'cold'    → meno di 30 esposizioni (cold start MAB)
      - 'live'    → tra 30 e 200 esposizioni
      - 'mature'  → oltre 200 esposizioni, stats statisticamente solide
    """
    from models.database import CROSlot, CROVariant

    _ensure_cro_tables(db)

    q = db.query(CROVariant).filter(CROVariant.active == True)
    slot_obj = None
    if slot:
        slot_obj = db.query(CROSlot).filter(CROSlot.slot_key == slot).first()
        if not slot_obj:
            raise HTTPException(status_code=404, detail=f"Slot '{slot}' not found")
        q = q.filter(CROVariant.slot_id == slot_obj.id)
    variants = q.all()

    results = []
    by_slot: Dict[int, List] = {}
    for v in variants:
        by_slot.setdefault(v.slot_id, []).append(v)

    for slot_id, slot_variants in by_slot.items():
        s = db.query(CROSlot).filter(CROSlot.id == slot_id).first()
        if not s:
            continue
        total_exp = sum(v.exposure_count or 0 for v in slot_variants)
        total_wins = sum(v.win_count or 0 for v in slot_variants)
        avg_cr = (total_wins / total_exp * 100) if total_exp > 0 else 0

        variant_data = []
        for v in slot_variants:
            exp = v.exposure_count or 0
            wins = v.win_count or 0
            cr = (wins / exp * 100) if exp > 0 else 0
            lift = (cr - avg_cr) if total_exp > 0 else 0
            if exp < 30:
                band = "cold"
            elif exp < 200:
                band = "live"
            else:
                band = "mature"
            variant_data.append({
                "variant_id": v.id,
                "variant_key": v.variant_key,
                "text": v.text,
                "cluster": v.cluster,
                "language": v.language,
                "exposures": exp,
                "wins": wins,
                "cr_pct": round(cr, 2),
                "lift_vs_avg_pp": round(lift, 2),
                "band": band,
            })

        # Sort by CR desc per default
        variant_data.sort(key=lambda x: -x["cr_pct"])
        results.append({
            "slot_key": s.slot_key,
            "description": s.description,
            "total_exposures": total_exp,
            "total_conversions": total_wins,
            "avg_cr_pct": round(avg_cr, 2),
            "variants": variant_data,
        })

    return {"slots": results, "total_slots": len(results)}


# ===================================================================
# CRAWL MAP — Step 5 (2026-05-14, NEW-02 audit closure)
# Migrazione di wom_crawl_map.json + mu_crawl_map.json dal filesystem
# committato a git verso Postgres con UPSERT incrementale.
# Fase 1 (questa): tabella + endpoint + migration script.
# Fase 2 (Task #14): switch dei middleware Node a leggere via API.
# ===================================================================

_CRAWL_VERDICTS = {"PASS", "NEUTRAL", "N/A", "FAIL", "UNKNOWN"}
_CRAWL_SITES = {"mu", "wom"}


def _ensure_crawl_map_table(db: DBSession):
    """Auto-create crawl_map_entries. Idempotente."""
    from models.database import CrawlMapEntry, engine
    try:
        CrawlMapEntry.__table__.create(bind=engine, checkfirst=True)
    except Exception as e:
        logger.warning(f"crawl_map_entries create check failed (probably already exists): {e}")


def _normalize_url_path(path_str: str) -> str:
    """
    Normalizza il path per matchare la logica di getVerdict() in indexAwareRouter.js:
    rimuove trailing slash (eccetto root '/'). Idempotente.
    """
    if not path_str:
        return "/"
    p = path_str.strip()
    if p == "/":
        return p
    return p.rstrip("/")


@app.post("/v1/crawl-map/batch")
async def crawl_map_batch(
    request: Request,
    payload: Dict = Body(...),
    db: DBSession = Depends(get_db)
):
    """
    Batch UPSERT di verdetti crawl. Auth API_KEY.
    Body: {"site": "mu" | "wom", "entries": [{"url_path": "/...", "verdict": "PASS", "source"?: "..."}], "source"?: "..."}
    Idempotente: re-POST stessa URL+site sovrascrive.
    """
    from models.database import CrawlMapEntry
    from datetime import datetime as dt

    api_key = (request.headers.get("x-api-key") or request.query_params.get("api_key") or "").strip()
    expected = (os.environ.get("API_KEY") or "albeni-gsc-2026").strip()
    if api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    site = (payload.get("site") or "").strip().lower()
    if site not in _CRAWL_SITES:
        raise HTTPException(status_code=400, detail=f"Invalid site '{site}'. Allowed: {sorted(_CRAWL_SITES)}")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise HTTPException(status_code=400, detail="Body must contain non-empty 'entries' array")
    default_source = (payload.get("source") or "manual")[:50]

    _ensure_crawl_map_table(db)

    inserted = 0
    errors = []
    now_dt = dt.utcnow()
    for i, e in enumerate(entries):
        try:
            url_path = _normalize_url_path(e.get("url_path") or "")
            verdict = (e.get("verdict") or "").strip().upper()
            if not url_path:
                raise ValueError("missing url_path")
            if verdict not in _CRAWL_VERDICTS:
                raise ValueError(f"invalid verdict '{verdict}' (allowed: {sorted(_CRAWL_VERDICTS)})")
            # UPSERT delete-then-insert (pattern coerente con gsc/adv)
            db.query(CrawlMapEntry).filter(
                CrawlMapEntry.site == site,
                CrawlMapEntry.url_path == url_path
            ).delete()
            db.add(CrawlMapEntry(
                site=site,
                url_path=url_path,
                verdict=verdict,
                last_scanned_at=now_dt,
                source=(e.get("source") or default_source)[:50],
            ))
            inserted += 1
        except (ValueError, TypeError) as ex:
            errors.append({"index": i, "error": str(ex), "entry": e})

    db.commit()
    total = db.query(CrawlMapEntry).filter(CrawlMapEntry.site == site).count()
    return {
        "status": "ok" if not errors else "partial",
        "site": site,
        "inserted": inserted,
        "errors": errors,
        "total_rows_for_site": total,
    }


@app.get("/v1/crawl-map")
async def crawl_map_get(
    site: str = Query(..., description="'mu' | 'wom'"),
    url: Optional[str] = Query(None, description="Optional url_path filter (single URL lookup)"),
    verdict: Optional[str] = Query(None, description="Filter by verdict (PASS/NEUTRAL/...)"),
    limit: int = Query(default=500, ge=1, le=5000),
    db: DBSession = Depends(get_db)
):
    """
    Lookup crawl map. 3 modalità d'uso:
      1) Single URL: ?site=mu&url=/path → ritorna {verdict, last_scanned_at} o 404
      2) Filter by verdict: ?site=mu&verdict=PASS → ritorna lista URL con quel verdict
      3) Full dump per site: ?site=mu → ritorna fino a `limit` entries

    Pensato per:
      - Middleware Node (Task #14): single URL lookup con cache 5min
      - Dashboard / debug: full dump
      - Sync script: filter by verdict per identificare URL da ri-scan
    """
    from models.database import CrawlMapEntry

    site_norm = site.strip().lower()
    if site_norm not in _CRAWL_SITES:
        raise HTTPException(status_code=400, detail=f"Invalid site '{site}'. Allowed: {sorted(_CRAWL_SITES)}")

    _ensure_crawl_map_table(db)

    # Single URL mode
    if url:
        url_norm = _normalize_url_path(url)
        row = db.query(CrawlMapEntry).filter(
            CrawlMapEntry.site == site_norm,
            CrawlMapEntry.url_path == url_norm
        ).first()
        if not row:
            return {"site": site_norm, "url_path": url_norm, "verdict": "UNKNOWN", "found": False}
        return {
            "site": site_norm,
            "url_path": row.url_path,
            "verdict": row.verdict,
            "last_scanned_at": row.last_scanned_at.isoformat() if row.last_scanned_at else None,
            "source": row.source,
            "found": True,
        }

    # List mode
    q = db.query(CrawlMapEntry).filter(CrawlMapEntry.site == site_norm)
    if verdict:
        q = q.filter(CrawlMapEntry.verdict == verdict.strip().upper())
    rows = q.order_by(CrawlMapEntry.url_path.asc()).limit(limit).all()
    return {
        "site": site_norm,
        "filter_verdict": verdict,
        "total": len(rows),
        "entries": [
            {"url_path": r.url_path, "verdict": r.verdict,
             "last_scanned_at": r.last_scanned_at.isoformat() if r.last_scanned_at else None,
             "source": r.source}
            for r in rows
        ],
    }


@app.get("/v1/crawl-map/stats")
async def crawl_map_stats(
    site: Optional[str] = Query(None, description="Optional filter, otherwise both sites"),
    db: DBSession = Depends(get_db)
):
    """
    Distribuzione verdetti per site. Comodo per dashboard / decisioni ADV budget allocator
    (es. quante URL stanno in NEUTRAL → paid coverage da attivare).
    """
    from models.database import CrawlMapEntry
    from sqlalchemy import func

    _ensure_crawl_map_table(db)

    sites_to_check = [site.strip().lower()] if site else sorted(_CRAWL_SITES)
    out: Dict = {}
    for s in sites_to_check:
        if s not in _CRAWL_SITES:
            continue
        rows = (
            db.query(CrawlMapEntry.verdict, func.count(CrawlMapEntry.id))
            .filter(CrawlMapEntry.site == s)
            .group_by(CrawlMapEntry.verdict)
            .all()
        )
        breakdown = {v: int(n) for v, n in rows}
        total = sum(breakdown.values())
        latest = db.query(func.max(CrawlMapEntry.last_scanned_at)).filter(CrawlMapEntry.site == s).scalar()
        out[s] = {
            "total": total,
            "by_verdict": breakdown,
            "pct_indexed": round(breakdown.get("PASS", 0) / total * 100, 1) if total else None,
            "latest_scan_at": latest.isoformat() if latest else None,
        }
    return {"sites": out}


# ===================================================================
# ANOMALY DETECTION v0 — Step 3b (2026-05-14)
# Cron daily registra KPI snapshot; detection confronta vs rolling 7d avg;
# alert generati in anomaly_alerts.
# Sblocca Tile T8 della Dashboard Executive (oggi buglist statica).
#
# KPI monitorati v0 (lista estendibile):
#   - cpa_7d                       — CPA paid (€) calcolato in /v1/executive/aggregates
#   - organic_pct                  — % attribuzioni organic vs paid
#   - cluster_heritage_mature_cr   — CR % del cluster narrativo principale
#
# Soglie deviazione default:
#   INFO 10-25% · WARNING 25-50% · CRITICAL >50%  (o cross-threshold)
# ===================================================================

# Soglie deviazione (override via env se serve)
_ANOMALY_INFO_PCT     = float(os.environ.get("ANOMALY_INFO_PCT", "10"))
_ANOMALY_WARN_PCT     = float(os.environ.get("ANOMALY_WARN_PCT", "25"))
_ANOMALY_CRIT_PCT     = float(os.environ.get("ANOMALY_CRIT_PCT", "50"))
_ANOMALY_BASELINE_DAYS = int(os.environ.get("ANOMALY_BASELINE_DAYS", "7"))


def _ensure_anomaly_tables(db: DBSession):
    """Auto-create kpi_snapshots + anomaly_alerts. Idempotente."""
    from models.database import KPISnapshot, AnomalyAlert, engine
    try:
        KPISnapshot.__table__.create(bind=engine, checkfirst=True)
        AnomalyAlert.__table__.create(bind=engine, checkfirst=True)
    except Exception as e:
        logger.warning(f"anomaly tables create check failed (probably already exist): {e}")


def _classify_severity(deviation_pct: float, cross_threshold: bool = False) -> Optional[str]:
    """
    Severity ladder con override "cross-threshold" che forza CRITICAL.
    Ritorna None se la deviazione è sotto la soglia INFO (nessun alert da creare).
    """
    if cross_threshold:
        return "CRITICAL"
    abs_dev = abs(deviation_pct)
    if abs_dev >= _ANOMALY_CRIT_PCT:
        return "CRITICAL"
    if abs_dev >= _ANOMALY_WARN_PCT:
        return "WARNING"
    if abs_dev >= _ANOMALY_INFO_PCT:
        return "INFO"
    return None


def _take_kpi_snapshot(db: DBSession, target_date: Optional[date] = None) -> Dict:
    """
    Calcola i 3 KPI v0 di oggi e li scrive in kpi_snapshots (UPSERT su date,metric_name).
    Ritorna {date, metrics: {metric_name: {value, sample_size, extra}}, written: N}.

    NB: target_date opzionale per backfill (es. _take_kpi_snapshot(db, target_date=date(2026,5,10))).
    """
    from models.database import KPISnapshot
    from sqlalchemy import text as sql_text
    from datetime import datetime, timezone, timedelta, date as dt_date

    _ensure_anomaly_tables(db)
    snap_date = target_date or datetime.now(timezone.utc).date()

    # Finestra di riferimento per i KPI "rolling 7d" (=cpa_7d, org_paid_mix)
    window_end = snap_date + timedelta(days=1)  # esclusivo
    window_start = window_end - timedelta(days=7)

    metrics: Dict[str, Dict] = {}

    # ── 1) CPA 7d ──
    spend_row = db.execute(sql_text(
        "SELECT COALESCE(SUM(amount_eur), 0) AS s "
        "FROM adv_spend WHERE date >= :s AND date < :e"
    ), {"s": window_start, "e": window_end}).fetchone()
    spend = float(spend_row[0] or 0)
    conv_row = db.execute(sql_text(
        "SELECT COUNT(*) FROM marketing_attributions "
        "WHERE converted=true "
        "  AND created_at >= :s AND created_at < :e "
        "  AND LOWER(COALESCE(medium,'')) IN ('cpc','ppc','paid_social','sponsored','dpa','display','story')"
    ), {"s": datetime.combine(window_start, datetime.min.time()),
        "e": datetime.combine(window_end, datetime.min.time())}).fetchone()
    paid_conv = int(conv_row[0] or 0)
    cpa = (spend / paid_conv) if (spend > 0 and paid_conv > 0) else None
    cpa_band = None
    if cpa is not None:
        cpa_band = "VERDE" if cpa <= 9 else "GIALLO" if cpa <= 15 else "ROSSO" if cpa <= 34 else "NERO"
    metrics["cpa_7d"] = {
        "value": cpa,
        "sample_size": paid_conv,
        "extra": {"total_spend_eur": round(spend, 2), "band": cpa_band},
    }

    # ── 2) Organic share ──
    mix_rows = db.execute(sql_text("""
        SELECT
            CASE WHEN LOWER(COALESCE(medium,'')) IN ('organic','referral','none','(none)','email','direct') THEN 'org'
                 WHEN LOWER(COALESCE(medium,'')) IN ('cpc','ppc','paid_social','sponsored','dpa','display','story') THEN 'paid'
                 ELSE 'unk' END AS bkt,
            COUNT(*)
        FROM marketing_attributions
        WHERE created_at >= :s AND created_at < :e
        GROUP BY bkt
    """), {"s": datetime.combine(window_start, datetime.min.time()),
           "e": datetime.combine(window_end, datetime.min.time())}).fetchall()
    mix = {b: int(n) for b, n in mix_rows}
    total_mix = sum(mix.values())
    org_pct = round(mix.get("org", 0) / total_mix * 100, 2) if total_mix else None
    metrics["organic_pct"] = {
        "value": org_pct,
        "sample_size": total_mix,
        "extra": {"org": mix.get("org", 0), "paid": mix.get("paid", 0), "unk": mix.get("unk", 0)},
    }

    # ── 3) Heritage Mature CR ──
    hm_row = db.execute(sql_text("""
        SELECT COUNT(*) AS attr,
               COUNT(*) FILTER (WHERE ma.converted=true) AS conv
        FROM marketing_attributions ma
        JOIN users u ON u.id = ma.user_id
        WHERE LOWER(COALESCE(u.assigned_cluster, '')) = 'heritage_mature'
          AND ma.created_at >= :s AND ma.created_at < :e
    """), {"s": datetime.combine(window_start, datetime.min.time()),
           "e": datetime.combine(window_end, datetime.min.time())}).fetchone()
    hm_attr = int(hm_row[0] or 0); hm_conv = int(hm_row[1] or 0)
    hm_cr = round(hm_conv / hm_attr * 100, 2) if hm_attr > 0 else None
    metrics["cluster_heritage_mature_cr"] = {
        "value": hm_cr,
        "sample_size": hm_attr,
        "extra": {"conversions": hm_conv, "target_cr_pct": 4.8},
    }

    # ── Persist (UPSERT per metric_name + date) ──
    written = 0
    for name, m in metrics.items():
        db.query(KPISnapshot).filter(
            KPISnapshot.date == snap_date,
            KPISnapshot.metric_name == name
        ).delete()
        db.add(KPISnapshot(
            date=snap_date,
            metric_name=name,
            value=m["value"],
            sample_size=m["sample_size"],
            extra=m["extra"],
        ))
        written += 1
    db.commit()
    return {"date": snap_date.isoformat(), "metrics": metrics, "written": written}


def _detect_anomalies(db: DBSession, ref_date: Optional[date] = None) -> Dict:
    """
    Confronta i valori di ref_date (default = oggi) con la media rolling sui giorni precedenti.
    Per ogni metrica fuori soglia (e con baseline non-null) crea un AnomalyAlert.
    Idempotente per metric+date: se esiste già un alert UNRESOLVED stesso giorno+metric, non duplica.
    Ritorna {ref_date, baseline_days, alerts_created}.
    """
    from models.database import KPISnapshot, AnomalyAlert
    from sqlalchemy import text as sql_text
    from datetime import datetime, timezone, timedelta

    _ensure_anomaly_tables(db)
    today = ref_date or datetime.now(timezone.utc).date()
    baseline_from = today - timedelta(days=_ANOMALY_BASELINE_DAYS)
    baseline_to = today  # esclusivo: rolling AVG dei N giorni PRECEDENTI

    today_snaps = db.query(KPISnapshot).filter(KPISnapshot.date == today).all()
    if not today_snaps:
        return {"ref_date": today.isoformat(), "alerts_created": 0,
                "skipped_reason": "no_snapshots_for_ref_date"}

    alerts_created = 0
    details = []
    for snap in today_snaps:
        if snap.value is None:
            continue
        current = float(snap.value)

        # Rolling baseline (escludiamo il giorno stesso)
        rows = db.query(KPISnapshot.value).filter(
            KPISnapshot.metric_name == snap.metric_name,
            KPISnapshot.date >= baseline_from,
            KPISnapshot.date < baseline_to,
            KPISnapshot.value.isnot(None),
        ).all()
        baseline_vals = [float(r[0]) for r in rows if r[0] is not None]
        if len(baseline_vals) < 3:
            # Troppo pochi datapoint storici per giudicare → no alert (warming-up)
            details.append({"metric": snap.metric_name, "skipped": "insufficient_baseline",
                            "baseline_count": len(baseline_vals)})
            continue
        baseline = sum(baseline_vals) / len(baseline_vals)

        if baseline == 0:
            # division by zero edge case: tratta qualsiasi current != 0 come CRITICAL
            deviation_pct = float("inf") if current != 0 else 0.0
        else:
            deviation_pct = (current - baseline) / baseline * 100.0

        # Cross-threshold: per cpa_7d, se la banda è cambiata in peggio rispetto a baseline → CRITICAL
        cross_threshold = False
        if snap.metric_name == "cpa_7d" and snap.extra:
            current_band = snap.extra.get("band")
            # Compare con band del giorno prima
            prev_snap = db.query(KPISnapshot).filter(
                KPISnapshot.metric_name == "cpa_7d",
                KPISnapshot.date < today,
                KPISnapshot.value.isnot(None),
            ).order_by(KPISnapshot.date.desc()).first()
            if prev_snap and prev_snap.extra:
                prev_band = prev_snap.extra.get("band")
                band_order = {"VERDE": 0, "GIALLO": 1, "ROSSO": 2, "NERO": 3}
                if prev_band in band_order and current_band in band_order \
                   and band_order[current_band] > band_order[prev_band]:
                    cross_threshold = True

        severity = _classify_severity(deviation_pct, cross_threshold=cross_threshold)
        if severity is None:
            details.append({"metric": snap.metric_name, "skipped": "below_info_threshold",
                            "deviation_pct": round(deviation_pct, 2)})
            continue

        # Dedup: esiste già alert UNRESOLVED per stessa metric creato oggi?
        already = db.query(AnomalyAlert).filter(
            AnomalyAlert.metric_name == snap.metric_name,
            AnomalyAlert.resolved == False,  # noqa: E712
            AnomalyAlert.created_at >= datetime.combine(today, datetime.min.time()),
        ).first()
        if already:
            details.append({"metric": snap.metric_name, "skipped": "alert_already_open_today",
                            "existing_alert_id": already.id})
            continue

        direction = "↑" if deviation_pct > 0 else "↓"
        msg = (
            f"{snap.metric_name}: current={current:.2f}, baseline_{len(baseline_vals)}d_avg={baseline:.2f}, "
            f"deviation {direction}{abs(deviation_pct):.1f}%"
        )
        if cross_threshold:
            msg += " · CROSS-THRESHOLD CPA band"

        alert = AnomalyAlert(
            metric_name=snap.metric_name,
            severity=severity,
            current_value=current,
            baseline_value=baseline,
            deviation_pct=round(deviation_pct, 2) if deviation_pct != float("inf") else None,
            message=msg,
            resolved=False,
        )
        db.add(alert)
        alerts_created += 1
        details.append({"metric": snap.metric_name, "severity": severity,
                        "current": current, "baseline": round(baseline, 4),
                        "deviation_pct": round(deviation_pct, 2) if deviation_pct != float("inf") else "inf"})

    db.commit()
    return {
        "ref_date": today.isoformat(),
        "baseline_days": _ANOMALY_BASELINE_DAYS,
        "alerts_created": alerts_created,
        "details": details,
    }


@app.post("/v1/anomaly/snapshot")
async def anomaly_snapshot(
    request: Request,
    backfill_date: Optional[str] = Query(default=None, description="YYYY-MM-DD, default oggi"),
    db: DBSession = Depends(get_db)
):
    """
    Trigger manuale dello snapshot KPI + anomaly detection.
    Auth: stesso API_KEY usato dagli altri endpoint di ingest.
    Chiamato automaticamente dallo scheduler APScheduler (lifespan job).
    """
    api_key = (request.headers.get("x-api-key") or request.query_params.get("api_key") or "").strip()
    expected = (os.environ.get("API_KEY") or "albeni-gsc-2026").strip()
    if api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from datetime import datetime as dt
    target_date = None
    if backfill_date:
        try:
            target_date = dt.fromisoformat(backfill_date).date()
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date '{backfill_date}'")

    snap = _take_kpi_snapshot(db, target_date=target_date)
    det = _detect_anomalies(db, ref_date=target_date)
    return {"status": "ok", "snapshot": snap, "detection": det}


@app.get("/v1/anomaly/alerts")
async def anomaly_alerts(
    days: int = Query(default=7, ge=1, le=90),
    include_resolved: bool = Query(default=False),
    min_severity: str = Query(default="INFO", description="INFO | WARNING | CRITICAL"),
    db: DBSession = Depends(get_db)
):
    """
    Lista alert per Tile T8 della Dashboard Executive. Default: 7gg, solo aperti, severity ≥ INFO.
    """
    from models.database import AnomalyAlert
    from datetime import datetime, timezone, timedelta

    _ensure_anomaly_tables(db)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    sev_order = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}
    min_idx = sev_order.get(min_severity.upper(), 0)

    q = db.query(AnomalyAlert).filter(AnomalyAlert.created_at >= since)
    if not include_resolved:
        q = q.filter(AnomalyAlert.resolved == False)  # noqa: E712
    rows = q.order_by(AnomalyAlert.created_at.desc()).all()

    items = []
    counts = {"INFO": 0, "WARNING": 0, "CRITICAL": 0}
    for r in rows:
        if sev_order.get(r.severity, 0) < min_idx:
            continue
        counts[r.severity] = counts.get(r.severity, 0) + 1
        items.append({
            "id": r.id,
            "metric_name": r.metric_name,
            "severity": r.severity,
            "current_value": float(r.current_value) if r.current_value is not None else None,
            "baseline_value": float(r.baseline_value) if r.baseline_value is not None else None,
            "deviation_pct": float(r.deviation_pct) if r.deviation_pct is not None else None,
            "message": r.message,
            "resolved": r.resolved,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "window_days": days,
        "total": len(items),
        "counts": counts,
        "min_severity": min_severity.upper(),
        "alerts": items,
    }


@app.get("/v1/anomaly/baseline")
async def anomaly_baseline(
    metric: str = Query(..., description="metric_name (es. cpa_7d)"),
    days: int = Query(default=14, ge=1, le=90),
    db: DBSession = Depends(get_db)
):
    """Debug endpoint: ritorna gli snapshot storici di una metrica + media."""
    from models.database import KPISnapshot
    from datetime import datetime, timezone, timedelta

    _ensure_anomaly_tables(db)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    rows = (
        db.query(KPISnapshot)
        .filter(KPISnapshot.metric_name == metric, KPISnapshot.date >= since)
        .order_by(KPISnapshot.date.asc())
        .all()
    )
    values = [float(r.value) for r in rows if r.value is not None]
    avg = sum(values) / len(values) if values else None
    return {
        "metric": metric,
        "window_days": days,
        "snapshots": [
            {"date": r.date.isoformat(), "value": float(r.value) if r.value is not None else None,
             "sample_size": r.sample_size, "extra": r.extra}
            for r in rows
        ],
        "avg": avg,
        "n_with_value": len(values),
    }


@app.post("/v1/anomaly/alerts/{alert_id}/resolve")
async def anomaly_alert_resolve(
    alert_id: int,
    request: Request,
    db: DBSession = Depends(get_db)
):
    """Marca un alert come risolto. Auth API_KEY come endpoint di ingest."""
    from models.database import AnomalyAlert
    from datetime import datetime

    api_key = (request.headers.get("x-api-key") or request.query_params.get("api_key") or "").strip()
    expected = (os.environ.get("API_KEY") or "albeni-gsc-2026").strip()
    if api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    alert = db.query(AnomalyAlert).filter(AnomalyAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.resolved = True
    alert.resolved_at = datetime.utcnow()
    db.commit()
    return {"status": "ok", "alert_id": alert_id, "resolved_at": alert.resolved_at.isoformat()}


# ===================================================================
# DASHBOARD EXECUTIVE — Aggregates (T1 CPA · T2 Org/Paid · T6 CR Cluster)
# Spec: Spec_Dashboard_Executive_2026-05-14.docx
# ===================================================================

# Medium classification: tweak qui se cambiano le convenzioni UTM
_ORGANIC_MEDIUMS = {"organic", "referral", "none", "(none)", "email", "direct"}
_PAID_MEDIUMS    = {"cpc", "ppc", "paid_social", "sponsored", "dpa", "display", "story"}


@app.get("/v1/executive/aggregates")
async def executive_aggregates(
    window_days: int = Query(default=7, ge=1, le=90, description="Window in days"),
    min_sample: int = Query(default=10, description="If 7d sample < this, fall back to all-time"),
    db: DBSession = Depends(get_db)
):
    """
    Aggregations for Dashboard Executive tiles T1, T2, T6.

    Returns structured JSON with explicit `value` or `null + reason`
    to allow the UI to render "no data yet" honestly.

    Tile T1 (CPA vs Target): currently null - no adv_spend tracking table.
        We expose paid_attributions count + converted_count as proxy.
    Tile T2 (Org/Paid Mix): organic_pct, paid_pct from marketing_attributions.
    Tile T6 (CR per Cluster): JOIN marketing_attributions + users.assigned_cluster.
    """
    from sqlalchemy import text
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=window_days)

    # Helper: classify medium into 'organic' / 'paid' / 'unknown'
    organic_list = "(" + ",".join(f"'{m}'" for m in _ORGANIC_MEDIUMS) + ")"
    paid_list    = "(" + ",".join(f"'{m}'" for m in _PAID_MEDIUMS) + ")"

    # ── T2 Org/Paid Mix ──
    # Try 7d window first; if total < min_sample, fall back to all_time.
    sql_mix = f"""
        WITH cls AS (
            SELECT
                CASE
                    WHEN LOWER(medium) IN {organic_list} THEN 'organic'
                    WHEN LOWER(medium) IN {paid_list}    THEN 'paid'
                    ELSE 'unknown'
                END AS bucket,
                converted
            FROM marketing_attributions
            WHERE created_at >= :since
        )
        SELECT bucket,
               COUNT(*) AS attributions,
               COUNT(*) FILTER (WHERE converted=true) AS conversions
        FROM cls
        GROUP BY bucket
        ORDER BY bucket;
    """
    sql_mix_all = sql_mix.replace("WHERE created_at >= :since", "")

    rows = db.execute(text(sql_mix), {"since": window_start}).fetchall()
    total_7d = sum(r[1] for r in rows)
    used_window = f"{window_days}d"
    if total_7d < min_sample:
        rows = db.execute(text(sql_mix_all)).fetchall()
        used_window = "all_time"

    mix = {"organic": 0, "paid": 0, "unknown": 0}
    conv_by_bucket = {"organic": 0, "paid": 0, "unknown": 0}
    for bucket, attr, conv in rows:
        mix[bucket] = attr
        conv_by_bucket[bucket] = conv
    total = sum(mix.values())

    org_paid_payload = {
        "window": used_window,
        "computed_at": now.isoformat(),
        "value": None if total == 0 else {
            "organic_pct": round(mix["organic"]   / total * 100, 1) if total else 0,
            "paid_pct":    round(mix["paid"]      / total * 100, 1) if total else 0,
            "unknown_pct": round(mix["unknown"]   / total * 100, 1) if total else 0,
            "organic_count": mix["organic"],
            "paid_count":    mix["paid"],
            "unknown_count": mix["unknown"],
            "total":         total,
            "conversions_organic": conv_by_bucket["organic"],
            "conversions_paid":    conv_by_bucket["paid"],
        },
        "reason": "no_attributions_in_window" if total == 0 else None,
    }

    # ── T1 CPA vs Target ──
    # CPA = SUM(adv_spend.amount_eur) / COUNT(paid_conversions) sulla stessa finestra di T2.
    # Soglie tile (Audit_Closure_2026-05-14): VERDE ≤€9 · GIALLO €10-15 · ROSSO €16-34 · NERO ≥€35.
    # Target sostenibilità modello 36M (doc 19): €17.92 sostenibile · €19.39 max.
    _ensure_adv_spend_table(db)  # idempotente, costo zero — copre prima esecuzione

    if used_window == "all_time":
        spend_row = db.execute(text(
            "SELECT COALESCE(SUM(amount_eur), 0) AS s, COUNT(*) AS n FROM adv_spend"
        )).fetchone()
    else:
        spend_row = db.execute(text(
            "SELECT COALESCE(SUM(amount_eur), 0) AS s, COUNT(*) AS n "
            "FROM adv_spend WHERE date >= :since_date"
        ), {"since_date": window_start.date()}).fetchone()
    total_spend_eur = float(spend_row[0] or 0)
    spend_rows = int(spend_row[1] or 0)
    paid_conv = conv_by_bucket["paid"]

    if total_spend_eur <= 0:
        cpa_value = None
        cpa_band = None
        cpa_reason = "no_spend_in_window" if used_window != "all_time" else "no_adv_spend_data"
    elif paid_conv <= 0:
        cpa_value = None
        cpa_band = None
        cpa_reason = "no_paid_conversions_in_window"
    else:
        cpa = total_spend_eur / paid_conv
        cpa_value = round(cpa, 2)
        if cpa <= 9:
            cpa_band = "VERDE"
        elif cpa <= 15:
            cpa_band = "GIALLO"
        elif cpa <= 34:
            cpa_band = "ROSSO"
        else:
            cpa_band = "NERO"
        cpa_reason = None

    cpa_payload = {
        "window": used_window,
        "computed_at": now.isoformat(),
        "value": cpa_value,
        "band": cpa_band,
        "reason": cpa_reason,
        "total_spend_eur": round(total_spend_eur, 2),
        "spend_rows": spend_rows,
        "paid_conversions": paid_conv,
        "thresholds": {"green_max": 9, "yellow_max": 15, "red_max": 34},
        "target_sustainable_eur": 17.92,
        "target_max_eur": 19.39,
        "proxy": {
            "paid_attributions": mix["paid"],
            "paid_conversions": conv_by_bucket["paid"],
            "implied_paid_conversion_rate_pct": (
                round(conv_by_bucket["paid"] / mix["paid"] * 100, 2)
                if mix["paid"] > 0 else None
            ),
        },
    }

    # ── T6 CR per Cluster ──
    # JOIN marketing_attributions ↔ users.assigned_cluster.
    # Order by CR (conversions / attributions). Min 3 attributions to avoid noise.
    sql_cr = """
        SELECT
            u.assigned_cluster AS cluster,
            COUNT(*) AS attributions,
            COUNT(*) FILTER (WHERE ma.converted=true) AS conversions
        FROM marketing_attributions ma
        JOIN users u ON u.id = ma.user_id
        WHERE u.assigned_cluster IS NOT NULL
          AND ma.created_at >= :since
        GROUP BY u.assigned_cluster
        ORDER BY 2 DESC
        LIMIT 5;
    """
    sql_cr_all = sql_cr.replace("AND ma.created_at >= :since\n", "")

    cr_rows = db.execute(text(sql_cr), {"since": window_start}).fetchall()
    if sum(r[1] for r in cr_rows) < min_sample:
        cr_rows = db.execute(text(sql_cr_all)).fetchall()

    cr_by_cluster = []
    for cluster, attr, conv in cr_rows:
        cr_by_cluster.append({
            "cluster": cluster,
            "attributions": attr,
            "conversions": conv,
            "cr_pct": round(conv / attr * 100, 2) if attr > 0 else 0.0,
        })

    # ── Totals & meta ──
    total_attr_all = db.execute(text(
        "SELECT COUNT(*) AS t, COUNT(*) FILTER (WHERE converted=true) AS c "
        "FROM marketing_attributions;"
    )).fetchone()

    return {
        "cpa_7d": cpa_payload,
        "org_paid_mix_7d": org_paid_payload,
        "cr_by_cluster_7d": {
            "window": used_window,
            "computed_at": now.isoformat(),
            "value": cr_by_cluster if cr_by_cluster else None,
            "reason": "no_attributions_with_cluster" if not cr_by_cluster else None,
            "targets": {"heritage_mature": 4.8, "business_professional": 3.8},
        },
        "totals": {
            "marketing_attributions_total": total_attr_all[0] if total_attr_all else 0,
            "marketing_attributions_converted": total_attr_all[1] if total_attr_all else 0,
        },
        "meta": {
            "window_days_requested": window_days,
            "window_actually_used": used_window,
            "min_sample_threshold": min_sample,
            "endpoint_version": "v1.0",
        },
    }


@app.post("/v1/notion/generate-from-pipeline")
async def generate_from_notion(
    limit: int = Query(default=1, ge=1, le=10, description="Max tasks to process"),
    db: DBSession = Depends(get_db)
):
    """
    Main integration endpoint: reads "Da Fare" tasks from Notion,
    generates AI content with Gemini, writes it back to Notion,
    and updates status to "In Produzione".
    """
    notion = NotionSync()
    generator = ContentGenerator(db)
    validator = ContentValidator()

    # 1. Get pending tasks
    pending = await notion.get_pending_tasks()
    if not pending:
        return {"status": "no_pending_tasks", "message": "No tasks with status 'Da Fare' found in Notion"}

    results = []
    for task in pending[:limit]:
        try:
            # 2. Map Notion fields to internal format
            cluster = notion.map_cluster(task["cluster"])
            content_type = notion.map_content_type(task["content_type"])
            primary_lang = notion.map_language(task["languages"][0]) if task["languages"] else "it"

            # 3. Build custom context from Notion task
            custom_context = f"Titolo: {task['title']}."
            if task["keyword_target"]:
                custom_context += f" Keyword target: {task['keyword_target']}."
            if task["note"]:
                custom_context += f" Note: {task['note']}."
            if task["domain"]:
                custom_context += f" Dominio: {task['domain']}."

            # 4. Generate content with Gemini
            content_request = ContentGenerationRequest(
                cluster=ClusterTag(cluster),
                language=primary_lang,
                content_type=content_type,
                intent_stage=IntentStage.TOFU if task["funnel_stage"] == "TOFU"
                    else IntentStage.MOFU if task["funnel_stage"] == "MOFU"
                    else IntentStage.BOFU,
                domain=task["domain"],
                custom_context=custom_context
            )
            content_result = await generator.generate(content_request)

            # 5. VALIDATION AGENT: verify content before writing to Notion
            validation = await validator.validate(
                content=content_result.generated_content,
                cluster=cluster,
                language=primary_lang,
                content_type=content_type,
                domain=task["domain"],
                keyword_target=task.get("keyword_target", ""),
                funnel_stage=task.get("funnel_stage", "")
            )

            # 5b. AI second-pass validation (anti-hallucination)
            ai_validation = await validator.validate_with_ai(
                content=content_result.generated_content,
                cluster=cluster,
                language=primary_lang,
                keyword_target=task.get("keyword_target", "")
            )

            validated_cqs = validation.overall_score

            # 6. Decision: write to Notion only if CQS >= 76
            if validation.passed:
                # PASSED: Write content + validation report to Notion
                await notion.write_content_to_page(
                    page_id=task["page_id"],
                    generated_content=content_result.generated_content,
                    model_used=content_result.model_used,
                    quality_score=validated_cqs
                )

                # Update status to "In Produzione"
                note_text = (f"AI generated ({content_result.model_used}) - "
                            f"CQS: {validated_cqs}/100 VALIDATED ✅ - "
                            f"{datetime.utcnow().strftime('%d/%m/%Y %H:%M')}")
                if validation.warnings:
                    note_text += f" | Warnings: {len(validation.warnings)}"
                await notion.update_task_status(task["page_id"], "In Produzione", note_text)

                results.append({
                    "page_id": task["page_id"],
                    "title": task["title"],
                    "status": "validated_and_written",
                    "model_used": content_result.model_used,
                    "cqs_score": validated_cqs,
                    "validation_passed": True,
                    "tokens_used": content_result.tokens_used,
                    "warnings": validation.warnings,
                    "ai_verdict": ai_validation.get("overall_verdict", "N/A"),
                })
            else:
                # FAILED: Do NOT write to Notion, keep "Da Fare" with error note
                error_summary = "; ".join(validation.errors[:5])
                note_text = (f"AI VALIDATION FAILED ❌ - CQS: {validated_cqs}/100 (min 76) - "
                            f"Errors: {error_summary} - "
                            f"{datetime.utcnow().strftime('%d/%m/%Y %H:%M')}")
                await notion.update_task_status(task["page_id"], "Da Fare", note_text)

                results.append({
                    "page_id": task["page_id"],
                    "title": task["title"],
                    "status": "validation_failed",
                    "model_used": content_result.model_used,
                    "cqs_score": validated_cqs,
                    "validation_passed": False,
                    "errors": validation.errors,
                    "warnings": validation.warnings,
                    "suggestions": validation.suggestions,
                    "ai_verdict": ai_validation.get("overall_verdict", "N/A"),
                })

            logger.info(f"Notion pipeline: '{task['title']}' - CQS: {validated_cqs}/100 - "
                        f"{'PASSED' if validation.passed else 'FAILED'}")

        except Exception as e:
            logger.error(f"Failed to process Notion task '{task.get('title', 'unknown')}': {e}")
            results.append({
                "page_id": task["page_id"],
                "title": task["title"],
                "status": "error",
                "error": str(e)
            })

    return {
        "status": "completed",
        "processed": len(results),
        "results": results
    }


@app.post("/v1/notion/create-task")
async def create_notion_task(
    title: str,
    cluster: str = "",
    domain: str = "",
    content_type: str = "Blog Post",
    funnel_stage: str = "TOFU",
    languages: str = "IT",
    keyword: str = "",
    month: str = "",
    note: str = ""
):
    """
    Create a new task in the Notion Content Pipeline.
    Languages should be comma-separated (e.g., "IT,EN,DE").
    """
    notion = NotionSync()
    lang_list = [l.strip() for l in languages.split(",") if l.strip()]

    page_id = await notion.create_pipeline_entry(
        title=title,
        cluster=cluster,
        domain=domain,
        content_type=content_type,
        funnel_stage=funnel_stage,
        languages=lang_list,
        keyword=keyword,
        month=month,
        note=note
    )

    if page_id:
        return {"status": "created", "page_id": page_id, "title": title}
    else:
        raise HTTPException(status_code=500, detail="Failed to create Notion task")


# ===================================================================
# CONTENT VALIDATION AGENT
# ===================================================================

@app.post("/v1/content/validate")
async def validate_content(req: ContentValidationRequest):
    """
    Standalone validation endpoint.
    Validates content against brand rules, technical accuracy,
    cluster alignment, SEO, and domain coherence.
    Returns detailed CQS score with pass/fail.

    Fix P0.2b (2026-05-12): refactor signature → ContentValidationRequest
    Pydantic model. Prima i campi cluster/language/content_type erano scalari
    top-level dell'handler, quindi FastAPI li parsava come query params e
    ignorava i field omonimi nel body JSON (cluster restava sempre il default
    "business_professional", causando cluster_alignment errato per ogni cluster
    non-business). Ora tutto viene dal body.
    """
    # Wrap stringhe come dict per compatibilità con validator.validate (json.dumps)
    content_payload = req.content if isinstance(req.content, dict) else {"content": req.content}

    validator = ContentValidator()

    # Rule-based validation
    result = await validator.validate(
        content=content_payload,
        cluster=req.cluster,
        language=req.language,
        content_type=req.content_type,
        domain=req.domain,
        keyword_target=req.keyword_target,
        funnel_stage=req.funnel_stage
    )

    # AI second-pass — opt-out for fast smoke tests (P0.2 follow-up 2026-05-12)
    if req.skip_ai_validation:
        ai_result = {"ai_validation": "skipped", "reason": "opted out via skip_ai_validation=true"}
    else:
        ai_result = await validator.validate_with_ai(
            content=content_payload,
            cluster=req.cluster,
            language=req.language,
            keyword_target=req.keyword_target
        )

    return {
        "cqs_score": result.overall_score,
        "passed": result.passed,
        "threshold": settings.CONTENT_QUALITY_MIN,
        "cluster": req.cluster,
        "checks": result.checks,
        "errors": result.errors,
        "warnings": result.warnings,
        "suggestions": result.suggestions,
        "ai_validation": ai_result,
    }


# ===================================================================
# SEMRUSH SEO & PAID INTELLIGENCE
# ===================================================================

@app.get("/v1/semrush/overview")
async def semrush_domain_overview(
    domain: Optional[str] = None,
    database: str = Query(default="it", description="Market: it, de, us, fr, es")
):
    """
    Get domain overview from Semrush.
    If no domain specified, returns overview for all 4 Albeni domains.
    """
    agent = SemrushAgent()
    if domain:
        return await agent.get_domain_overview(domain, database)
    return await agent.get_all_domains_overview(database)


@app.get("/v1/semrush/organic-keywords")
async def semrush_organic_keywords(
    domain: str = Query(..., description="Domain to analyze"),
    database: str = Query(default="it"),
    limit: int = Query(default=50, ge=1, le=100)
):
    """Get top organic keywords for a domain with positions and traffic."""
    agent = SemrushAgent()
    return await agent.get_organic_keywords(domain, database, limit)


@app.get("/v1/semrush/paid-keywords")
async def semrush_paid_keywords(
    domain: str = Query(..., description="Domain to analyze"),
    database: str = Query(default="it"),
    limit: int = Query(default=50, ge=1, le=100)
):
    """Get paid/ADV keywords for a domain (Google Ads data)."""
    agent = SemrushAgent()
    return await agent.get_paid_keywords(domain, database, limit)


@app.get("/v1/semrush/competitors")
async def semrush_competitors(
    domain: str = Query(default="albeni1905.com"),
    database: str = Query(default="it"),
    limit: int = Query(default=20, ge=1, le=50)
):
    """Find organic competitors for a domain."""
    agent = SemrushAgent()
    return await agent.get_organic_competitors(domain, database, limit)


@app.get("/v1/semrush/benchmark")
async def semrush_benchmark(
    database: str = Query(default="it")
):
    """
    Benchmark all 4 Albeni domains vs competitors
    (Smartwool, Icebreaker, Allbirds, Asket, Unbound Merino).
    """
    agent = SemrushAgent()
    return await agent.benchmark_vs_competitors(database)


@app.get("/v1/semrush/keyword")
async def semrush_keyword_overview(
    keyword: str = Query(..., description="Keyword to analyze"),
    database: str = Query(default="it")
):
    """Get detailed data for a specific keyword (volume, CPC, competition)."""
    agent = SemrushAgent()
    return await agent.keyword_overview(keyword, database)


@app.get("/v1/semrush/keyword/related")
async def semrush_related_keywords(
    keyword: str = Query(..., description="Seed keyword"),
    database: str = Query(default="it"),
    limit: int = Query(default=30, ge=1, le=100)
):
    """Get related keywords for content expansion."""
    agent = SemrushAgent()
    return await agent.get_related_keywords(keyword, database, limit)


@app.get("/v1/semrush/backlinks")
async def semrush_backlinks(
    domain: str = Query(default="albeni1905.com")
):
    """Get backlink profile overview (authority score, referring domains)."""
    agent = SemrushAgent()
    return await agent.get_backlinks_overview(domain)


@app.get("/v1/semrush/seo-balance")
async def semrush_seo_balance(
    database: str = Query(default="it")
):
    """
    Analyze the 85/15 SEO balance across the Albeni ecosystem.
    85% cluster expansion / 15% semantic defense.
    """
    agent = SemrushAgent()
    return await agent.analyze_seo_balance(database)


@app.get("/v1/semrush/paid-intelligence")
async def semrush_paid_intelligence(
    database: str = Query(default="it")
):
    """
    Paid advertising intelligence: ADV spend, ad copy, competitor ads.
    Supports the €30K ADV budget allocation strategy.
    """
    agent = SemrushAgent()
    return await agent.get_paid_intelligence(database)


@app.get("/v1/semrush/keyword-gap")
async def semrush_keyword_gap(
    competitor: str = Query(default="smartwool.com"),
    database: str = Query(default="it"),
    domain: Optional[str] = Query(None, description="Albeni domain to compare (default: albeni1905.com)"),
    albeni_domain: Optional[str] = Query(None),
):
    """
    Find keyword gaps: keywords where a competitor ranks but Albeni doesn't.
    Identifies content opportunities.

    Accepts `domain` or `albeni_domain` to pick which Albeni satellite to compare
    (worldofmerino, merinouniversity, perfectmerinoshirt, albeni1905).
    """
    side = domain or albeni_domain or "albeni1905.com"
    agent = SemrushAgent()
    return await agent.keyword_gap(database, competitor, side)


@app.get("/v1/semrush/audit")
async def semrush_full_audit(
    database: str = Query(default="it")
):
    """
    Run a comprehensive SEO audit across the entire Albeni ecosystem.
    Combines domain data, keywords, competitors, backlinks, and 85/15 balance.
    WARNING: Uses many API units. Run sparingly.

    Timeout protection (Bug 4 — 2026-05-14): audit is sync-multi-call and can
    exceed Railway's gateway timeout. Cap at 25s with graceful partial response.
    """
    agent = SemrushAgent()
    try:
        return await asyncio.wait_for(agent.full_seo_audit(database), timeout=25.0)
    except asyncio.TimeoutError:
        return {
            "error": "timeout",
            "type": "TimeoutError",
            "message": "Full SEO audit exceeded 25s — try narrowing scope or running individual endpoints",
            "database": database,
            "partial": False,
        }


@app.post("/v1/semrush/check-positions")
async def semrush_check_positions(
    keywords: List[str],
    database: str = Query(default="it")
):
    """
    Check where all 4 Albeni domains rank for specific keywords.
    Useful for tracking Content Pipeline target keywords.
    """
    agent = SemrushAgent()
    return await agent.check_keyword_positions(keywords, database)


# ===================================================================
# SEMRUSH DATA LIBRARY (Import & Query Research Data)
# ===================================================================

@app.post("/v1/semrush/library/upload")
async def semrush_upload(
    file: UploadFile = File(...),
    label: str = Form(default=""),
    database: str = Form(default="it"),
    notes: str = Form(default=""),
):
    """
    Upload a Semrush CSV or XLSX export to the data library.
    Auto-detects export type (keyword research, domain analytics, etc.).
    """
    library = SemrushDataLibrary()

    filename = file.filename or "unknown"
    content_bytes = await file.read()

    try:
        if filename.lower().endswith((".xlsx", ".xls")):
            export_type, rows = library.parse_xlsx(content_bytes, filename)
        else:
            # Treat as CSV (including .csv and .txt)
            content_str = content_bytes.decode("utf-8", errors="replace")
            export_type, rows = library.parse_csv(content_str, filename)
    except Exception as e:
        logger.error(f"Failed to parse Semrush file '{filename}': {e}")
        raise HTTPException(status_code=400, detail=f"Errore nel parsing del file: {str(e)}")

    if not rows:
        raise HTTPException(status_code=400, detail="Il file non contiene dati riconoscibili")

    # Store with metadata
    metadata = {
        "label": label or filename,
        "database": database,
        "notes": notes,
        "original_filename": filename,
        "file_size_bytes": len(content_bytes),
    }
    record = library.store_import(export_type, rows, filename, metadata)

    return {
        "status": "imported",
        "import_id": record["id"],
        "filename": filename,
        "export_type": export_type,
        "rows_imported": len(rows),
        "columns": record["columns"],
        "summary": record.get("summary", {}),
    }


@app.get("/v1/semrush/library")
async def semrush_library_list():
    """List all imported Semrush datasets in the data library."""
    library = SemrushDataLibrary()
    imports = library.list_imports()
    stats = library.get_aggregate_stats()
    return {"imports": imports, "stats": stats}


@app.get("/v1/semrush/library/{import_id}")
async def semrush_library_get(import_id: str):
    """Get a specific imported dataset with full data."""
    library = SemrushDataLibrary()
    data = library.get_import(import_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Import '{import_id}' non trovato")
    return data


@app.delete("/v1/semrush/library/{import_id}")
async def semrush_library_delete(import_id: str):
    """Delete an imported dataset."""
    library = SemrushDataLibrary()
    if library.delete_import(import_id):
        return {"status": "deleted", "import_id": import_id}
    raise HTTPException(status_code=404, detail=f"Import '{import_id}' non trovato")


@app.get("/v1/semrush/library/search/keywords")
async def semrush_library_search(
    q: str = Query(..., description="Keyword search query"),
    import_id: Optional[str] = Query(default=None, description="Filter by specific import"),
):
    """Search keywords across all imported Semrush data."""
    library = SemrushDataLibrary()
    results = library.search_keywords(q, import_id)
    return {"query": q, "results": results, "total": len(results)}


@app.get("/v1/semrush/library/keywords/all")
async def semrush_library_all_keywords(
    min_volume: int = Query(default=0),
    max_kd: int = Query(default=100),
    limit: int = Query(default=200, ge=1, le=1000),
):
    """
    Get unified keyword universe from all imported Semrush data.
    Merges and deduplicates across all imports.
    """
    library = SemrushDataLibrary()
    keywords = library.get_all_keywords(min_volume, max_kd)
    return {
        "total": len(keywords),
        "keywords": keywords[:limit],
        "filters": {"min_volume": min_volume, "max_kd": max_kd},
    }


# ===================================================================
# RESEARCH DATA HUB (Universal File Import)
# ===================================================================

@app.post("/v1/hub/upload")
async def hub_upload(
    file: UploadFile = File(...),
    label: str = Form(default=""),
    source: str = Form(default=""),
    notes: str = Form(default=""),
):
    """
    Upload ANY file to the Research Data Hub.
    Auto-detects source type (Semrush, GA4, Google Ads, Search Console,
    Ahrefs, Screaming Frog, Shopify, Klaviyo, PDF, DOCX, JSON, TXT).
    """
    hub = ResearchHub()
    filename = file.filename or "unknown"
    content_bytes = await file.read()

    try:
        record = hub.import_file(
            file_bytes=content_bytes,
            filename=filename,
            source_override=source,
            label=label or filename,
            notes=notes,
        )
    except ValueError as e:
        logger.warning(f"Hub import validation error for '{filename}': {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Hub import failed for '{filename}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Errore server durante l'import: {str(e)}")

    return {
        "status": "imported",
        "import_id": record["id"],
        "filename": filename,
        "source": record["source"],
        "category": record["category"],
        "icon": record["icon"],
        "file_type": record["file_type"],
        "rows_imported": record["rows_count"],
        "columns": record["columns"][:15],
    }


@app.get("/v1/hub")
async def hub_list(source: Optional[str] = None):
    """List all imported datasets. Optionally filter by source type."""
    hub = ResearchHub()
    imports = hub.list_all(source)
    stats = hub.get_stats()
    return {"imports": imports, "stats": stats}


@app.get("/v1/hub/{import_id}")
async def hub_get(import_id: str):
    """Get a specific imported dataset with full data."""
    hub = ResearchHub()
    data = hub.get_data(import_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Import '{import_id}' non trovato")
    return data


@app.delete("/v1/hub/{import_id}")
async def hub_delete(import_id: str):
    """Delete an imported dataset."""
    hub = ResearchHub()
    if hub.delete(import_id):
        return {"status": "deleted", "import_id": import_id}
    raise HTTPException(status_code=404, detail=f"Import '{import_id}' non trovato")


@app.get("/v1/hub/search/all")
async def hub_search(
    q: str = Query(..., description="Search query"),
    source: Optional[str] = Query(default=None, description="Filter by source type"),
):
    """Full-text search across ALL imported data from all sources."""
    hub = ResearchHub()
    results = hub.search(q, source)
    return {"query": q, "source_filter": source, "results": results, "total": len(results)}


# ===================================================================
# CONTEXT PROVIDER (Data Hub → Agent Knowledge Bridge)
# ===================================================================

@app.get("/v1/context/categories")
async def context_categories():
    """List all available context categories with tag counts."""
    provider = DataHubContextProvider()
    return {"categories": provider.get_categories()}


@app.get("/v1/context/summary")
async def context_summary():
    """Overall summary of the Data Hub context system."""
    provider = DataHubContextProvider()
    return provider.get_summary()


@app.get("/v1/context/agent-map")
async def context_agent_map():
    """Show which agents use which context categories and how many files are available."""
    provider = DataHubContextProvider()
    return {"agents": provider.get_agent_context_map()}


@app.post("/v1/context/tag")
async def context_tag(
    import_id: str = Query(...),
    tags: List[str] = Body(...),
    priority: int = Query(default=5),
):
    """Tag a Data Hub import with context categories so agents can use it."""
    provider = DataHubContextProvider()
    return provider.tag_import(import_id, tags, priority)


@app.post("/v1/context/auto-tag")
async def context_auto_tag(import_id: str):
    """Automatically suggest context tags for an import based on its content."""
    provider = DataHubContextProvider()
    return provider.auto_tag(import_id)


@app.delete("/v1/context/tag/{import_id}")
async def context_untag(import_id: str):
    """Remove all context tags from an import."""
    provider = DataHubContextProvider()
    removed = provider.untag_import(import_id)
    return {"import_id": import_id, "removed": removed}


@app.get("/v1/context/tagged")
async def context_list_tagged(
    tag: Optional[str] = Query(default=None, description="Filter by tag category"),
):
    """List all tagged imports, optionally filtered by tag."""
    provider = DataHubContextProvider()
    return {"tagged": provider.list_tagged(tag)}


@app.get("/v1/context/for-agent/{agent_id}")
async def context_for_agent(
    agent_id: str,
    task_type: str = Query(default="", description="Task type for finer context"),
    market: str = Query(default="", description="Market/language code"),
):
    """
    Get the context that would be injected for a specific agent.
    Useful for debugging and previewing what data agents receive.
    """
    provider = DataHubContextProvider()
    return provider.get_context(agent_id, task_type, market)


@app.post("/v1/context/sync-skills")
async def context_sync_skills():
    """
    Import all Albeni skill files (SEO agent, MT translator, validator, orchestrator)
    into the Data Hub and auto-tag them so all agents can use them as context.
    """
    provider = DataHubContextProvider()
    return provider.sync_skills()


@app.post("/v1/context/auto-tag-all")
async def context_auto_tag_all():
    """
    Automatically tag ALL untagged imports in the Data Hub.
    Analyzes content and metadata to assign the best context categories.
    """
    provider = DataHubContextProvider()
    return provider.auto_tag_all(min_score=2)


# ===================================================================
# CUSTOMER CARE AI (Multilingua Chatbot)
# ===================================================================

# Global instance (keeps conversation state in memory)
_customer_care: Optional[CustomerCareAI] = None

def get_customer_care() -> CustomerCareAI:
    global _customer_care
    if _customer_care is None:
        _customer_care = CustomerCareAI()
    return _customer_care


@app.post("/v1/chat/start")
async def chat_start(language: str = "it", domain_type: str = "bofu_heritage"):
    """Start a new customer care chat session with domain-aware welcome message."""
    care = get_customer_care()
    return care.start_session(language, domain_type=domain_type)


@app.post("/v1/chat/message")
async def chat_message(
    message: str,
    language: str = "it",
    session_id: Optional[str] = None,
    user_email: Optional[str] = None,
    user_id: Optional[str] = None,
    domain_type: str = "bofu_heritage",
):
    """
    Send a message to the Customer Care AI chatbot.

    The bot:
    1. Detects topic (sizing, care, materials, shipping, returns, sustainability)
    2. Responds from knowledge base (fast) or Gemini AI (complex questions)
    3. Tracks intent (IDS delta) for funnel progression
    4. Escalates to human operator via Klaviyo + Notion if dissatisfaction detected
    5. Adjusts tone and cross-domain CTAs based on domain_type (tofu|mofu|bofu_tech|bofu_heritage)
    """
    care = get_customer_care()
    return await care.chat(
        message=message,
        language=language,
        session_id=session_id,
        user_email=user_email,
        user_id=user_id,
        domain_type=domain_type,
    )


@app.get("/widget.js")
async def serve_widget_js():
    """Serve the chatbot widget JS for embedding on sites."""
    js_path = Path(__file__).parent / "static" / "chatbot-widget.js"
    if not js_path.exists():
        raise HTTPException(status_code=404, detail="Widget JS not found")
    return Response(
        content=js_path.read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=3600", "Access-Control-Allow-Origin": "*"}
    )


@app.get("/v1/chat/debug-gemini")
async def debug_gemini(message: str = "hai suggerimenti per il viaggio?", language: str = "it"):
    """Debug endpoint: raw Gemini response metadata for troubleshooting truncation.
    Wrapped in asyncio.wait_for to prevent the request from hanging the worker
    if the Gemini API is slow or unreachable (see Bug 4/5 — 2026-05-14)."""
    settings = get_settings()
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)

        prompt = f"Sei l'assistente di World of Merino. Rispondi in italiano.\n\nCliente: {message}\n\nAssistente:"

        # Run the sync call in a thread + cap total time to 8s to avoid 12s+ hangs
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    prompt,
                    generation_config={"temperature": 0.5, "max_output_tokens": 8192},
                ),
                timeout=8.0,
            )
        except asyncio.TimeoutError:
            return {
                "error": "timeout",
                "type": "TimeoutError",
                "message": "Gemini API did not respond within 8s — likely upstream slowness or wrong API key",
                "model": settings.GEMINI_MODEL,
            }

        # Extract all metadata
        result = {
            "prompt_len": len(prompt),
            "model": settings.GEMINI_MODEL,
            "response_text": None,
            "response_text_len": None,
            "candidates_count": 0,
            "finish_reason": None,
            "safety_ratings": None,
            "parts": [],
            "prompt_feedback": None,
        }

        try:
            result["response_text"] = response.text
            result["response_text_len"] = len(response.text)
        except Exception as e:
            result["response_text_error"] = str(e)

        try:
            result["prompt_feedback"] = str(getattr(response, 'prompt_feedback', None))
        except Exception:
            pass

        if response.candidates:
            result["candidates_count"] = len(response.candidates)
            c = response.candidates[0]
            result["finish_reason"] = str(getattr(c, 'finish_reason', 'unknown'))
            result["safety_ratings"] = [str(r) for r in getattr(c, 'safety_ratings', [])]

            parts = getattr(c.content, 'parts', [])
            for i, p in enumerate(parts):
                part_text = getattr(p, 'text', '')
                result["parts"].append({
                    "index": i,
                    "text_len": len(part_text),
                    "text_preview": part_text[:200],
                    "text_end": part_text[-50:] if len(part_text) > 50 else part_text,
                })

        return result

    except Exception as e:
        return {"error": str(e), "type": str(type(e).__name__)}


@app.get("/v1/chat/history/{session_id}")
async def chat_history(session_id: str):
    """Retrieve conversation history for a session."""
    care = get_customer_care()
    messages = care.get_conversation(session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "messages": messages}


@app.get("/v1/chat/stats")
async def chat_stats():
    """Get chatbot usage statistics."""
    care = get_customer_care()
    return care.get_stats()


@app.post("/v1/chat/sizing")
async def chat_sizing(payload: Dict = Body(...)):
    """
    Interactive Size & Fit Finder.
    Given the user's chest circumference (cm), returns personalized
    size recommendations for both Slim Fit and Regular Fit.
    Mirrors the Shopify widget logic on albeni1905.com.

    Body-tolerant: accepts {chest_cm} (required) and optional {language|lang}.
    Aligns with sibling endpoint convention (post Bug 1bis pattern).
    """
    chest_raw = payload.get("chest_cm")
    if chest_raw is None:
        raise HTTPException(status_code=400, detail="chest_cm required in body")
    try:
        chest_cm = float(chest_raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="chest_cm must be a number")

    if chest_cm < 70 or chest_cm > 150:
        raise HTTPException(
            status_code=400,
            detail="Chest measurement must be between 70 and 150 cm"
        )

    language = payload.get("language") or payload.get("lang") or "it"
    care = get_customer_care()
    return care.calculate_size(chest_cm, language)


@app.get("/v1/chat/sizing/table")
async def chat_sizing_table():
    """
    Returns the full size chart data for both fits.
    Can be used by frontend widgets to render the size table.
    """
    from services.customer_care import SIZE_FIT_DATA, STRETCH_TOLERANCE_CM
    return {
        "fits": SIZE_FIT_DATA,
        "stretch_tolerance_cm": STRETCH_TOLERANCE_CM,
        "available_sizes": list(SIZE_FIT_DATA["slim"]["sizes"].keys()),
    }


# ===================================================================
# ADV INTELLIGENCE LAYER
# ===================================================================

# Global instances (singletons)
_adv_intelligence: Optional[ADVIntelligence] = None
_adv_router: Optional[ADVRouter] = None
_bot_shield: Optional[BotShield] = None


def get_adv_intelligence(db: DBSession = None) -> ADVIntelligence:
    global _adv_intelligence
    if _adv_intelligence is None:
        _adv_intelligence = ADVIntelligence(redis_client=redis_client, db=db)
    elif db and not _adv_intelligence.db:
        _adv_intelligence.db = db
        _adv_intelligence.redis = redis_client
    return _adv_intelligence


def get_adv_router() -> ADVRouter:
    global _adv_router
    if _adv_router is None:
        _adv_router = ADVRouter()
    return _adv_router


def get_bot_shield() -> BotShield:
    global _bot_shield
    if _bot_shield is None:
        _bot_shield = BotShield()
    return _bot_shield


@app.post("/v1/adv/track")
async def adv_track_event(
    user_id: str,
    ids_score: float = 0,
    cluster: Optional[str] = None,
    page_views: int = 0,
    source: Optional[str] = None,
    medium: Optional[str] = None,
    term: Optional[str] = None,
    content: Optional[str] = None,
    campaign: Optional[str] = None,
    gclid: Optional[str] = None,
    fbclid: Optional[str] = None,
    landing_domain: Optional[str] = None,
    db: DBSession = Depends(get_db),
):
    """
    Full ADV intelligence pipeline:
    1. Parse UTM/campaign data (UTM Sensor)
    2. Store in Redis (fast) + Postgres (persistent)
    3. Track cross-domain attribution
    4. Process Signal Feedback Loop (IDS → Google/Meta conversions)
    """
    adv = get_adv_intelligence(db=db)
    raw_data = {
        "source": source, "medium": medium, "term": term,
        "content": content, "campaign": campaign,
        "gclid": gclid, "fbclid": fbclid,
        "landing_domain": landing_domain,
    }
    return await adv.process_event(
        user_id=user_id,
        ids_score=ids_score,
        raw_campaign_data=raw_data,
        cluster=cluster,
        page_views=page_views,
    )


@app.post("/v1/adv/route")
async def adv_route_visitor(
    source: Optional[str] = None,
    medium: Optional[str] = None,
    term: Optional[str] = None,
    content: Optional[str] = None,
    gclid: Optional[str] = None,
    fbclid: Optional[str] = None,
    landing_domain: Optional[str] = None,
    ids_score: float = 0,
    cluster: Optional[str] = None,
    language: str = "it",
    device: str = "desktop",
):
    """
    Dynamic ADV routing: determine optimal landing page,
    layout and messaging based on campaign source + user context.
    """
    parsed = UTMSensor.parse({
        "source": source, "medium": medium, "term": term,
        "content": content, "gclid": gclid, "fbclid": fbclid,
        "landing_domain": landing_domain,
    })
    router = get_adv_router()
    return router.route(
        campaign_data=parsed,
        ids_score=ids_score,
        cluster=cluster,
        language=language,
        device=device,
    )


@app.post("/v1/adv/shield/analyze")
async def adv_shield_analyze(
    payload: Dict = Body(...),
    db: DBSession = Depends(get_db),
):
    """
    Bot Shield: analyze visitor behavior for click fraud.
    Returns threat score and recommended action (allow/monitor/flag/block).
    Persists exclusions to Postgres for cross-restart protection.

    Schema-tolerant: accepts JSON body (was previously query-params, which
    caused 422 errors when the widget JS sent a JSON body via fetch()).
    Bug 1bis fix (2026-05-05).
    """
    visitor_id = payload.get("visitor_id") or payload.get("user_id") or ""
    ip_address = payload.get("ip_address") or payload.get("ip") or ""
    if not visitor_id:
        raise HTTPException(status_code=400, detail="visitor_id required")
    if not ip_address:
        # IP often not available client-side; use a placeholder so the
        # shield can still score behavior signals.
        ip_address = "0.0.0.0"

    user_agent = payload.get("user_agent", "")
    dwell_time_ms = int(payload.get("dwell_time_ms", 0) or 0)
    mouse_events = int(payload.get("mouse_events", 0) or 0)
    scroll_depth_pct = float(payload.get("scroll_depth_pct", 0) or 0)
    pages_viewed = int(payload.get("pages_viewed", 1) or 1)
    session_duration_ms = int(payload.get("session_duration_ms", 0) or 0)
    is_paid = bool(payload.get("is_paid", False))
    referrer = payload.get("referrer")

    shield = get_bot_shield()
    result = shield.analyze_visitor(
        visitor_id=visitor_id,
        ip_address=ip_address,
        user_agent=user_agent,
        dwell_time_ms=dwell_time_ms,
        mouse_events=mouse_events,
        scroll_depth_pct=scroll_depth_pct,
        pages_viewed=pages_viewed,
        session_duration_ms=session_duration_ms,
        is_paid=is_paid,
        referrer=referrer,
    )

    # Persist exclusion to Postgres if blocked
    if result.get("should_exclude"):
        try:
            from models.database import BotShieldExclusion
            exclusion = BotShieldExclusion(
                ip_address=ip_address,
                visitor_id=visitor_id,
                threat_score=result["threat_score"],
                signals=result["signals"],
                is_paid_click=is_paid,
                estimated_savings_eur=shield._avg_cpc_eur if is_paid else 0,
            )
            db.add(exclusion)
            db.commit()
        except Exception as e:
            logger.warning(f"Bot exclusion persist failed: {e}")

    return result


@app.get("/v1/adv/shield/exclusions")
async def adv_shield_exclusions():
    """Get the current IP exclusion list for ad platform sync."""
    shield = get_bot_shield()
    return {"exclusions": shield.get_exclusion_list(), "count": len(shield.get_exclusion_list())}


@app.get("/v1/adv/stats")
async def adv_stats():
    """Combined ADV Intelligence statistics."""
    adv = get_adv_intelligence()
    router = get_adv_router()
    shield = get_bot_shield()
    return {
        "intelligence": adv.get_stats(),
        "routing": router.get_stats(),
        "bot_shield": shield.get_stats(),
    }


# ===================================================================
# AI COMMAND TERMINAL (Natural Language Interface)
# ===================================================================

# Terminal conversation history for context-aware routing
_terminal_history: List[Dict] = []  # [{role, content, agent, timestamp}]
MAX_TERMINAL_HISTORY = 20


def _add_terminal_history(role: str, content: str, agent: str = None):
    """Add a message to terminal history."""
    _terminal_history.append({
        "role": role,
        "content": content[:500],
        "agent": agent,
        "timestamp": datetime.utcnow().isoformat(),
    })
    # Keep only last N messages
    while len(_terminal_history) > MAX_TERMINAL_HISTORY:
        _terminal_history.pop(0)


def _get_terminal_context(last_n: int = 6) -> str:
    """Build conversation context string from recent terminal history."""
    if not _terminal_history:
        return ""
    recent = _terminal_history[-last_n:]
    lines = []
    for msg in recent:
        prefix = "UTENTE" if msg["role"] == "user" else f"SISTEMA ({msg.get('agent', '?')})"
        lines.append(f"[{prefix}]: {msg['content'][:300]}")
    return "\n".join(lines)


def _is_follow_up(cmd_lower: str) -> bool:
    """Detect if the command is a conversational follow-up to a previous response."""
    if not _terminal_history:
        return False
    follow_up_patterns = [
        "quale", "quali", "cosa", "come", "perché", "dimmi di più",
        "approfondisci", "spiega meglio", "e per", "e il", "e la", "e i",
        "in dettaglio", "nello specifico", "più info", "elabora",
        "what", "which", "how", "why", "tell me more", "elaborate",
        "and the", "and what", "specifically",
    ]
    # Short commands that reference something from context
    if len(cmd_lower) < 60 and any(p in cmd_lower for p in follow_up_patterns):
        return True
    # Very short + previous response exists
    if len(cmd_lower) < 40 and len(_terminal_history) >= 2:
        last_assistant = [m for m in _terminal_history if m["role"] == "assistant"]
        if last_assistant and last_assistant[-1].get("agent") == "AI Strategy Director":
            return True
    return False


@app.post("/v1/terminal/execute")
async def terminal_execute(
    command: str,
    db: DBSession = Depends(get_db)
):
    """
    Process a natural language command and route it to the appropriate agent.
    Uses Gemini to interpret the command and execute the right action.
    Maintains conversation history for context-aware follow-ups.
    """
    import re
    import google.generativeai as genai

    # Store user command in history
    _add_terminal_history("user", command)

    # Available commands mapped to actions
    COMMAND_MAP = {
        # Notion commands
        "pipeline": {"agent": "Notion Sync", "endpoint": "notion_pipeline"},
        "pendenti": {"agent": "Notion Sync", "endpoint": "notion_pending"},
        "da fare": {"agent": "Notion Sync", "endpoint": "notion_pending"},
        "stats": {"agent": "Notion Sync", "endpoint": "notion_stats"},
        "statistiche": {"agent": "Notion Sync", "endpoint": "notion_stats"},
        "genera": {"agent": "Content Validator", "endpoint": "generate"},
        "generate": {"agent": "Content Validator", "endpoint": "generate"},
        # SEO / Semrush commands
        "seo": {"agent": "SEO Semantic Brain", "endpoint": "seo_health"},
        "health": {"agent": "System", "endpoint": "health"},
        "overview": {"agent": "Semrush Specialist", "endpoint": "semrush_overview"},
        "semrush": {"agent": "Semrush Specialist", "endpoint": "semrush_overview"},
        "benchmark": {"agent": "Semrush Specialist", "endpoint": "semrush_benchmark"},
        "competitor": {"agent": "Semrush Specialist", "endpoint": "semrush_benchmark"},
        "keyword": {"agent": "Semrush Specialist", "endpoint": "semrush_keyword"},
        "backlink": {"agent": "Semrush Specialist", "endpoint": "semrush_backlinks"},
        "balance": {"agent": "Semrush Specialist", "endpoint": "semrush_balance"},
        "85/15": {"agent": "Semrush Specialist", "endpoint": "semrush_balance"},
        "paid": {"agent": "Semrush Specialist", "endpoint": "semrush_paid"},
        "adv": {"agent": "Semrush Specialist", "endpoint": "semrush_paid"},
        "gap": {"agent": "Semrush Specialist", "endpoint": "semrush_gap"},
        "audit": {"agent": "Semrush Specialist", "endpoint": "semrush_audit"},
        # Data Hub (Research Hub + Semrush Data Library)
        "libreria": {"agent": "Data Hub", "endpoint": "hub_list"},
        "library": {"agent": "Data Hub", "endpoint": "hub_list"},
        "dati": {"agent": "Data Hub", "endpoint": "hub_list"},
        "hub": {"agent": "Data Hub", "endpoint": "hub_list"},
        "cerca keyword": {"agent": "Data Hub", "endpoint": "hub_search"},
        "cerca": {"agent": "Data Hub", "endpoint": "hub_search"},
        "search": {"agent": "Data Hub", "endpoint": "hub_search"},
        "importa": {"agent": "Data Hub", "endpoint": "hub_list"},
        # Context Provider commands
        "contesto": {"agent": "Context Provider", "endpoint": "context_summary"},
        "context": {"agent": "Context Provider", "endpoint": "context_summary"},
        "tag": {"agent": "Context Provider", "endpoint": "context_tag_list"},
        "categorie": {"agent": "Context Provider", "endpoint": "context_categories"},
        # Klaviyo commands
        "klaviyo": {"agent": "Klaviyo CRM Sync", "endpoint": "klaviyo_sync"},
        "sync": {"agent": "Klaviyo CRM Sync", "endpoint": "klaviyo_sync"},
        "crm": {"agent": "Klaviyo CRM Sync", "endpoint": "klaviyo_sync"},
        # Intent/Cluster commands
        "ids": {"agent": "Intent Engine", "endpoint": "calculate_ids"},
        "intent": {"agent": "Intent Engine", "endpoint": "calculate_ids"},
        "cluster": {"agent": "Cluster Predictor", "endpoint": "predict_cluster"},
        "predici": {"agent": "Cluster Predictor", "endpoint": "predict_cluster"},
        # Router
        "routing": {"agent": "AI Routing Layer", "endpoint": "route"},
        "route": {"agent": "AI Routing Layer", "endpoint": "route"},
        # Content
        "email": {"agent": "Content AI Layer", "endpoint": "gen_email"},
        "blog": {"agent": "Content AI Layer", "endpoint": "gen_blog"},
        "landing": {"agent": "Content AI Layer", "endpoint": "gen_landing"},
        # ADV Intelligence
        "adv stats": {"agent": "ADV Intelligence", "endpoint": "adv_stats"},
        "adv shield": {"agent": "Bot Shield", "endpoint": "adv_shield"},
        "adv routing": {"agent": "ADV Router", "endpoint": "adv_routing"},
        "bot": {"agent": "Bot Shield", "endpoint": "adv_shield"},
        "esclusioni": {"agent": "Bot Shield", "endpoint": "adv_exclusions"},
        "exclusions": {"agent": "Bot Shield", "endpoint": "adv_exclusions"},
        # System
        "help": {"agent": "System", "endpoint": "help"},
        "aiuto": {"agent": "System", "endpoint": "help"},
        "agenti": {"agent": "System", "endpoint": "agents_list"},
        "agents": {"agent": "System", "endpoint": "agents_list"},
        "status": {"agent": "System", "endpoint": "health"},
        "metriche": {"agent": "System", "endpoint": "metrics"},
        "metrics": {"agent": "System", "endpoint": "metrics"},
    }

    cmd_lower = command.lower().strip()
    start_time = time.time()

    # Detect if this is a complex instruction (not a simple keyword command)
    complex_indicators = [
        "implementa", "crea una strategia", "pianifica", "progetta",
        "istruzioni per", "istruzioni:", "strategia", "budget",
        "analizza in dettaglio", "prepara un piano", "elabora",
        "come posso", "cosa dovrei", "suggerisci", "consiglia",
        "ottimizza", "migliora", "confronta in dettaglio",
        "spiega", "descrivi", "definisci", "valuta",
        "proponi", "raccomanda", "organizza", "struttura",
    ]
    is_complex = (
        len(cmd_lower) > 40
        and any(ind in cmd_lower for ind in complex_indicators)
    )

    # Detect follow-up questions that should go to AI Strategy Director
    is_follow_up = _is_follow_up(cmd_lower)

    # 1. For complex instructions OR follow-ups: use AI reasoning (Gemini)
    if is_complex or is_follow_up:
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel(settings.GEMINI_MODEL)

            # Gather live system context
            context_parts = []

            # Add conversation history for context-aware responses
            conv_context = _get_terminal_context(last_n=6)
            if conv_context:
                context_parts.append(f"CRONOLOGIA CONVERSAZIONE TERMINALE (ultimi messaggi):\n{conv_context}")

            # Get Data Hub context if relevant
            try:
                cp = DataHubContextProvider()
                # Detect which agent categories might be relevant
                for agent_key in ["seo_brain", "semrush_agent", "content_generator", "adv_strategist"]:
                    ctx = cp.get_context(agent_key, max_chars=1500, max_items=2)
                    if ctx["instructions_text"]:
                        context_parts.append(ctx["instructions_text"])
            except Exception:
                pass

            # Get Semrush live data if SEO/paid related
            seo_keywords = ["seo", "keyword", "paid", "adv", "budget", "competitor", "benchmark", "organic", "search", "ranking"]
            if any(kw in cmd_lower for kw in seo_keywords):
                try:
                    sr = SemrushAgent()
                    overview = await sr.get_all_domains_overview("it")
                    if overview:
                        context_parts.append(f"DATI SEMRUSH LIVE (panoramica domini IT):\n{json.dumps(overview, indent=2, default=str)[:2000]}")
                except Exception:
                    pass

            # Get Notion pipeline status
            try:
                notion = NotionSync()
                pipeline_stats = await notion.get_pipeline_stats()
                if pipeline_stats:
                    context_parts.append(f"STATO CONTENT PIPELINE:\n{json.dumps(pipeline_stats, indent=2, default=str)[:500]}")
            except Exception:
                pass

            hub_context = "\n\n".join(context_parts) if context_parts else "Nessun dato contestuale disponibile."

            ai_prompt = f"""Sei l'AI Strategy Director di Albeni 1905, il sistema di orchestrazione AI per un brand italiano di lusso nel merino.

ECOSISTEMA ALBENI:
- 4 domini: worldofmerino.com (TOFU), merinouniversity.com (MOFU), perfectmerinoshirt.com (BOFU), albeni1905.com (BOFU heritage)
- 5 mercati: IT, DE, US, FR, ES
- 5 cluster comportamentali: business_professional, heritage_mature, conscious_premium, modern_minimalist, italian_authentic
- Budget ADV: €30K / 18 mesi (disponibile)
- SEO balance target: 85% cluster expansion / 15% semantic defense
- 6 competitor: Smartwool, Icebreaker, Allbirds, Asket, Unbound Merino, Wool&Prince
- Brand positioning: "Invisible Luxury" — Same Silhouette, Superior Substance
- Prodotti: T-shirt, polo, camicie in merino 17μ (Reda 1865), 150g e 190g, Cut & Sewn
- CQS (Content Quality Score) target: ≥76/100

DATI LIVE DAL SISTEMA:
{hub_context}

ISTRUZIONE DELL'UTENTE:
{command}

Rispondi come un senior strategist esperto. Sii specifico, azionabile, e strutturato.
- Se l'utente chiede una strategia, fornisci un piano dettagliato con fasi, timeline, budget allocation, KPI target
- Se chiede analisi, usa i dati live per dare insight concreti
- Se chiede istruzioni per un agente, scrivi le istruzioni precise che l'agente dovrebbe seguire
- Se la domanda è un FOLLOW-UP a una risposta precedente (vedi CRONOLOGIA), rispondi nel contesto di quella conversazione — NON trattarla come una domanda nuova isolata
- Usa numeri concreti, non generici
- Rispondi in italiano
- Formatta la risposta in modo leggibile (usa bullet, sezioni, tabelle testuali se servono)"""

            response = model.generate_content(
                ai_prompt,
                generation_config={"temperature": 0.7, "max_output_tokens": 4000}
            )

            ai_response = response.text.strip()
            latency = int((time.time() - start_time) * 1000)

            # Store response in terminal history
            _add_terminal_history("assistant", ai_response[:500], agent="AI Strategy Director")

            return {
                "agent": "AI Strategy Director",
                "action": "ai_reasoning",
                "command": command,
                "result": ai_response,
                "response_type": "ai_strategy",
                "latency_ms": latency,
                "context_sources": len(context_parts),
            }

        except Exception as e:
            logger.error(f"AI reasoning failed: {e}")
            # Fall through to keyword matching as fallback

    # 2. Try direct command matching (fast path for simple commands)
    matched_action = None
    for trigger, action in COMMAND_MAP.items():
        if trigger in cmd_lower:
            matched_action = action
            break

    # 3. If no match and not complex, try AI for medium-complexity commands
    if not matched_action and len(cmd_lower) > 15 and settings.GEMINI_API_KEY:
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel(settings.GEMINI_MODEL)

            # Include conversation context for follow-up awareness
            conv_ctx = _get_terminal_context(last_n=4)
            history_block = f"\n\nCRONOLOGIA CONVERSAZIONE RECENTE:\n{conv_ctx}" if conv_ctx else ""

            routing_prompt = f"""Sei il router dell'AI Orchestration Layer di Albeni 1905.
L'utente ha scritto: "{command}"{history_block}

Devi rispondere SOLO con un JSON valido che indica quale azione eseguire:
{{
    "intent": "la richiesta dell'utente in una frase",
    "agent": "nome agente migliore",
    "action": "azione da eseguire",
    "params": {{}},
    "answer": "risposta breve e utile per l'utente"
}}

Agenti disponibili: Notion Sync, Semrush Specialist, SEO Semantic Brain, Content Generator,
Content Validator, Klaviyo CRM, Intent Engine, Cluster Predictor, AI Routing Layer, Data Hub, Context Provider, AI Strategy Director.

IMPORTANTE: Se la domanda sembra un FOLLOW-UP alla conversazione precedente (es. "quale è la keyword gap" dopo un'analisi strategica), l'agente corretto è "AI Strategy Director" — NON il Semrush Specialist.
Se la domanda non riguarda nessun agente specifico, rispondi comunque con una risposta utile nel campo "answer"."""

            response = model.generate_content(
                routing_prompt,
                generation_config={"temperature": 0.3, "response_mime_type": "application/json"}
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            ai_route = json.loads(raw.strip())

            latency = int((time.time() - start_time) * 1000)
            agent_name_routed = ai_route.get("agent", "AI Router")
            answer_text = ai_route.get("answer", str(ai_route))
            _add_terminal_history("assistant", answer_text[:500], agent=agent_name_routed)

            return {
                "agent": agent_name_routed,
                "action": ai_route.get("action", "ai_response"),
                "command": command,
                "result": answer_text,
                "response_type": "ai_routed",
                "latency_ms": latency,
            }
        except Exception as e:
            logger.warning(f"AI routing fallback failed: {e}")

    # 4. Execute the matched action (or show help)
    try:
        if not matched_action or matched_action["endpoint"] == "help":
            return {
                "agent": "Sistema",
                "action": "help",
                "response": (
                    "Comandi disponibili:\n\n"
                    "📝 NOTION: 'pipeline', 'pendenti', 'stats', 'genera [N]'\n"
                    "📈 SEMRUSH: 'overview', 'benchmark', 'keyword [parola]', 'backlink', 'balance', 'paid', 'gap', 'audit'\n"
                    "📂 DATA HUB: 'libreria', 'cerca [keyword]', 'dati', 'hub'\n"
                    "🧠 CONTESTO: 'contesto', 'categorie', 'tag'\n"
                    "📧 KLAVIYO: 'sync', 'crm'\n"
                    "🎯 INTENT: 'ids [user]', 'cluster [user]', 'routing [user]'\n"
                    "✍️ CONTENT: 'email', 'blog', 'landing'\n"
                    "📣 ADV: 'adv stats', 'adv routing', 'adv shield', 'esclusioni'\n"
                    "🔧 SISTEMA: 'status', 'metriche', 'agenti'\n\n"
                    "💡 Puoi anche dare istruzioni complesse in linguaggio naturale, es:\n"
                    "• 'implementa una strategia SEO per il mercato DE con budget 500€/mese'\n"
                    "• 'analizza i competitor e suggerisci keyword gap da colmare'\n"
                    "• 'prepara un piano editoriale per i prossimi 3 mesi'\n"
                    "• 'quali contenuti dovrei creare per il cluster business_professional?'"
                ),
                "latency_ms": int((time.time() - start_time) * 1000),
            }

        endpoint = matched_action["endpoint"]
        agent_name = matched_action["agent"]
        result = None

        # --- NOTION ---
        if endpoint == "notion_pipeline":
            notion = NotionSync()
            tasks = await notion.get_all_pipeline_tasks()
            result = {"tasks": len(tasks), "sample": tasks[:5]}

        elif endpoint == "notion_pending":
            notion = NotionSync()
            tasks = await notion.get_pending_tasks()
            result = {"pending_tasks": len(tasks), "titles": [t["title"] for t in tasks[:10]]}

        elif endpoint == "notion_stats":
            notion = NotionSync()
            result = await notion.get_pipeline_stats()

        elif endpoint == "generate":
            # Extract limit from command (e.g., "genera 3")
            nums = re.findall(r'\d+', cmd_lower)
            limit = int(nums[0]) if nums else 1
            limit = min(limit, 10)
            # Delegate to the full pipeline endpoint
            notion = NotionSync()
            generator = ContentGenerator(db)
            validator = ContentValidator()
            pending = await notion.get_pending_tasks()
            if not pending:
                result = {"message": "Nessun task 'Da Fare' nel Content Pipeline"}
            else:
                result = {"message": f"Avvio generazione per {min(limit, len(pending))} task...", "note": "Usa il bottone 'Genera + Valida' nella pagina Notion per il flusso completo con validazione."}

        # --- SEMRUSH ---
        elif endpoint == "semrush_overview":
            # Extract domain if mentioned
            domain = None
            for d in ["worldofmerino.com", "merinouniversity.com", "perfectmerinoshirt.com", "albeni1905.com"]:
                if d.split(".")[0] in cmd_lower:
                    domain = d
                    break
            sr = SemrushAgent()
            if domain:
                result = await sr.get_domain_overview(domain, "it")
            else:
                result = await sr.get_all_domains_overview("it")

        elif endpoint == "semrush_benchmark":
            sr = SemrushAgent()
            result = await sr.benchmark_vs_competitors("it")

        elif endpoint == "semrush_keyword":
            # Extract keyword from command
            kw_match = re.search(r'keyword\s+(.+?)(?:\s+(?:in|su|per|database)\s|$)', cmd_lower)
            if not kw_match:
                # Try to extract after "analizza"
                kw_match = re.search(r'(?:analizza|cerca|ricerca)\s+(?:la\s+keyword\s+)?(.+?)$', cmd_lower)
            keyword = kw_match.group(1).strip() if kw_match else cmd_lower.replace("keyword", "").strip()
            if keyword:
                sr = SemrushAgent()
                result = await sr.keyword_overview(keyword, "it")
            else:
                result = {"error": "Specifica una keyword, es: 'keyword lana merino benefici'"}

        elif endpoint == "semrush_backlinks":
            domain = "albeni1905.com"
            for d in ["worldofmerino.com", "merinouniversity.com", "perfectmerinoshirt.com", "albeni1905.com"]:
                if d.split(".")[0] in cmd_lower:
                    domain = d
                    break
            sr = SemrushAgent()
            result = await sr.get_backlinks_overview(domain)

        elif endpoint == "semrush_balance":
            sr = SemrushAgent()
            result = await sr.analyze_seo_balance("it")

        elif endpoint == "semrush_paid":
            sr = SemrushAgent()
            result = await sr.get_paid_intelligence("it")

        elif endpoint == "semrush_gap":
            competitor = "smartwool.com"
            for c in ["icebreaker.com", "allbirds.com", "asket.com", "unboundmerino.com"]:
                if c.split(".")[0] in cmd_lower:
                    competitor = c
                    break
            sr = SemrushAgent()
            result = await sr.keyword_gap("it", competitor)

        elif endpoint == "semrush_audit":
            sr = SemrushAgent()
            result = {"message": "L'audit completo consuma molte API units. Avviare dalla pagina SEO & Semrush per il report completo.", "note": "Usa 'overview' per una panoramica veloce."}

        # --- DATA HUB (Research Hub) ---
        elif endpoint == "hub_list":
            hub = ResearchHub()
            all_data = hub.list_all()
            hub_stats = hub.get_stats()
            result = {
                "total_imports": hub_stats.get("total_imports", 0),
                "total_rows": hub_stats.get("total_rows", 0),
                "sources": hub_stats.get("by_source", {}),
                "imports": [{"file": i.get("label", i.get("filename")), "source": i.get("source"), "type": i.get("file_type"), "rows": i.get("row_count")} for i in all_data[:10]],
            }

        elif endpoint == "hub_search":
            search_term = cmd_lower.replace("cerca keyword", "").replace("cerca", "").replace("search", "").strip()
            if search_term:
                hub = ResearchHub()
                results = hub.search(search_term)
                # Also search Semrush library for backward compatibility
                lib = SemrushDataLibrary()
                sr_results = lib.search_keywords(search_term)
                combined = results + [{"keyword": r.get("keyword"), "volume": r.get("volume"), "kd": r.get("kd"), "cpc": r.get("cpc"), "_source": "semrush_library"} for r in sr_results]
                result = {
                    "query": search_term,
                    "found": len(combined),
                    "top_results": combined[:20],
                }
            else:
                result = {"message": "Specifica cosa cercare, es: 'cerca merino wool'"}

        # --- CONTEXT PROVIDER ---
        elif endpoint == "context_summary":
            cp = DataHubContextProvider()
            result = cp.get_summary()

        elif endpoint == "context_categories":
            cp = DataHubContextProvider()
            result = {"categories": cp.get_categories()}

        elif endpoint == "context_tag_list":
            cp = DataHubContextProvider()
            result = {"tagged_files": cp.list_tagged()}

        # --- KLAVIYO ---
        elif endpoint == "klaviyo_sync":
            result = {"status": "Klaviyo connesso", "account": "Best Before Srl", "public_key": "VbcXCv", "note": "Usa la pagina Klaviyo CRM per test sync completi."}

        # --- INTENT / CLUSTER / ROUTING ---
        elif endpoint == "calculate_ids":
            user_match = re.search(r'(?:ids|intent)\s+(\S+)', cmd_lower)
            user_id = user_match.group(1) if user_match else "test-user-001"
            calculator = IDSCalculator(redis_client, db)
            result = (await calculator.calculate(user_id)).model_dump()

        elif endpoint == "predict_cluster":
            user_match = re.search(r'(?:cluster|predici)\s+(\S+)', cmd_lower)
            user_id = user_match.group(1) if user_match else "test-user-001"
            predictor = ClusterPredictor(redis_client, db)
            result = (await predictor.predict(user_id)).model_dump()

        elif endpoint == "route":
            user_match = re.search(r'(?:routing|route)\s+(\S+)', cmd_lower)
            user_id = user_match.group(1) if user_match else "test-user-001"
            result = {"note": f"Routing per utente {user_id}", "endpoint": f"/v1/router/assign?user_id={user_id}&lang=it"}

        # --- CONTENT ---
        elif endpoint in ("gen_email", "gen_blog", "gen_landing"):
            content_type = {"gen_email": "email_copy", "gen_blog": "blog_draft", "gen_landing": "landing_copy"}[endpoint]
            cluster = "business_professional"
            for c in ["heritage_mature", "conscious_premium", "modern_minimalist", "italian_authentic"]:
                if c.replace("_", " ") in cmd_lower or c.replace("_", "") in cmd_lower:
                    cluster = c
                    break
            generator = ContentGenerator(db)
            req = ContentGenerationRequest(
                cluster=ClusterTag(cluster),
                language="it",
                content_type=content_type,
                intent_stage=IntentStage.BOFU if content_type == "email_copy" else IntentStage.TOFU,
            )
            gen_result = await generator.generate(req)
            result = {
                "content_type": content_type,
                "cluster": cluster,
                "model_used": gen_result.model_used,
                "quality_score": gen_result.content_quality_score,
                "tokens_used": gen_result.tokens_used,
                "content_preview": {k: (v[:200] + "..." if isinstance(v, str) and len(v) > 200 else v) for k, v in gen_result.generated_content.items()},
            }

        # --- SYSTEM ---
        elif endpoint == "agents_list":
            result = {
                "agents": [
                    {"name": "Intent Engine", "layer": "L2-L3", "status": "active"},
                    {"name": "Cluster Predictor", "layer": "L3", "status": "active"},
                    {"name": "AI Routing Layer", "layer": "L3", "status": "active"},
                    {"name": "Content AI Layer", "layer": "L4", "status": "active"},
                    {"name": "Content Validator", "layer": "L4", "status": "active"},
                    {"name": "Notion Sync", "layer": "L4", "status": "active"},
                    {"name": "Klaviyo CRM Sync", "layer": "L4", "status": "active"},
                    {"name": "Semrush Specialist", "layer": "L3", "status": "active"},
                    {"name": "SEO Semantic Brain", "layer": "L3", "status": "active"},
                    {"name": "Bot Protection", "layer": "L5", "status": "active"},
                    {"name": "C2PA Fingerprint", "layer": "L5", "status": "active"},
                    {"name": "ADV Intelligence", "layer": "L3", "status": "active"},
                    {"name": "ADV Router", "layer": "L3", "status": "active"},
                    {"name": "Bot Shield", "layer": "L5", "status": "active"},
                    {"name": "Customer Care AI", "layer": "L4", "status": "active"},
                ],
                "total": 15,
            }

        elif endpoint == "health":
            try:
                await redis_client.ping()
                redis_ok = True
            except Exception:
                redis_ok = False
            result = {
                "system": "healthy" if redis_ok else "degraded",
                "redis": "healthy" if redis_ok else "unhealthy",
                "ai_provider": "gemini_configured" if settings.GEMINI_API_KEY else "not_configured",
                "klaviyo": "configured" if settings.KLAVIYO_API_KEY else "not_configured",
                "notion": "configured" if settings.NOTION_API_TOKEN else "not_configured",
                "semrush": "configured" if settings.SEMRUSH_API_KEY else "not_configured",
            }

        elif endpoint == "metrics":
            total_users = db.query(func.count(User.id)).scalar() or 0
            avg_ids = db.query(func.avg(User.ids_score)).scalar() or 0
            result = {"total_users": total_users, "avg_ids": round(float(avg_ids), 1)}

        # --- SEO HEALTH ---
        elif endpoint == "seo_health":
            monitor = SEOMonitor(db)
            results = await monitor.run_health_check(None)
            result = {"domains": [r.model_dump() for r in results]}

        # --- ADV INTELLIGENCE ---
        elif endpoint == "adv_stats":
            adv = get_adv_intelligence()
            router = get_adv_router()
            shield = get_bot_shield()
            result = {
                "intelligence": adv.get_stats(),
                "routing": router.get_stats(),
                "bot_shield": shield.get_stats(),
            }

        elif endpoint == "adv_shield":
            shield = get_bot_shield()
            result = shield.get_stats()

        elif endpoint == "adv_exclusions":
            shield = get_bot_shield()
            exclusions = shield.get_exclusion_list()
            result = {"exclusion_list": exclusions, "total": len(exclusions)}

        elif endpoint == "adv_routing":
            router = get_adv_router()
            result = router.get_stats()

        latency = int((time.time() - start_time) * 1000)

        # Store response in terminal history
        result_preview = json.dumps(result, default=str, ensure_ascii=False)[:500] if result else ""
        _add_terminal_history("assistant", result_preview, agent=agent_name)

        return {
            "agent": agent_name,
            "action": endpoint,
            "command": command,
            "result": result,
            "latency_ms": latency,
        }

    except Exception as e:
        logger.error(f"Terminal command failed: {e}")
        return {
            "agent": matched_action["agent"] if matched_action else "Sistema",
            "action": "error",
            "command": command,
            "error": str(e),
            "latency_ms": int((time.time() - start_time) * 1000),
        }


@app.delete("/v1/terminal/history")
async def terminal_clear_history():
    """Clear terminal conversation history (used by 'Pulisci' button)."""
    global _terminal_history
    count = len(_terminal_history)
    _terminal_history = []
    return {"cleared": count, "status": "ok"}


@app.get("/v1/terminal/history")
async def terminal_get_history():
    """Get terminal conversation history."""
    return {"messages": _terminal_history, "count": len(_terminal_history)}


# ===================================================================
# ENTRY POINT
# ===================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# ===================================================================
# VISUAL BRIEF GENERATOR — Phase 6 News Scanner
# ===================================================================

@app.post("/v1/visual/generate")
async def generate_visuals(req: VisualGenerateRequest):
    """
    Generate editorial visuals for a Merino News Scanner brief.
    Fix BUG-07 sibling (2026-05-14): accetta sia `brief_text` sia `prompt` (Pydantic v2 AliasChoices).
    """
    import base64

    import os
    gemini_key = os.environ.get("GEMINI_API_KEY") or settings.GEMINI_API_KEY
    if not gemini_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    generator = VisualGenerator(api_key=gemini_key)

    if req.dry_run:
        results = generator.dry_run(req.brief_text, max_facts=req.max_facts)
        return {"status": "dry_run", "visuals": results, "count": len(results)}

    raw_results = generator.generate_for_brief(req.brief_text, max_facts=req.max_facts)
    visuals = []
    for r in raw_results:
        visuals.append({
            "fact_number": r["fact_number"],
            "fact_title": r["fact_title"],
            "destination": r["destination"],
            "topic": r["topic"],
            "description": r["description"],
            "prompt": r["prompt"],
            "success": r["success"],
            "error": r.get("error"),
            "image_base64": base64.b64encode(r["image_bytes"]).decode() if r["image_bytes"] else None,
        })

    generated = sum(1 for v in visuals if v["success"])
    failed = sum(1 for v in visuals if not v["success"])
    return {"status": "completed", "visuals": visuals, "summary": {"generated": generated, "failed": failed, "total": len(visuals)}}


@app.post("/v1/visual/dry-run")
async def visual_dry_run(req: VisualDryRunRequest):
    """
    Compose visual prompts without generating images (preview mode).
    Fix BUG-07 (2026-05-14): accetta sia `brief_text` sia `prompt` come body key
    (Pydantic v2 AliasChoices, vedi models/schemas.py).
    """
    import os
    gemini_key = os.environ.get("GEMINI_API_KEY") or settings.GEMINI_API_KEY or "dry-run"
    generator = VisualGenerator(api_key=gemini_key)
    results = generator.dry_run(req.brief_text, max_facts=req.max_facts)
    return {"status": "dry_run", "visuals": results, "count": len(results)}
