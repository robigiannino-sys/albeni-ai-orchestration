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
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Optional, Dict, List

import redis.asyncio as aioredis
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Header, Query, Body, File, UploadFile, Form
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

    scheduler = AsyncIOScheduler()
    scheduler.add_job(_scheduled_recompute, "interval", minutes=15, id="pipeline_consumer",
                      coalesce=True, max_instances=1, misfire_grace_time=300)
    scheduler.start()
    logger.info("Pipeline consumer scheduled every 15 minutes")

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
    user_id: str = Query(...),
    lang: str = Query("it"),
    db: DBSession = Depends(get_db)
):
    """
    Determine the optimal destination domain based on IDS and cluster.
    TOFU (0-30) -> worldofmerino.com
    MOFU (31-65) -> merinouniversity.com
    BOFU (>65) -> perfectmerinoshirt.com or albeni1905.com (by cluster)
    """
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
    Run SEO health check across domains.
    Monitors 85/15 balance and cannibalization (alert >6%, critical >12%).
    """
    monitor = SEOMonitor(db)
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


@app.get("/v1/notion/pipeline/stats")
async def get_notion_stats():
    """
    Get Content Pipeline statistics for dashboard.
    Breakdown by status, cluster, domain, funnel stage, month.
    """
    notion = NotionSync()
    stats = await notion.get_pipeline_stats()
    return stats


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
async def validate_content(
    content: Dict,
    cluster: str = "business_professional",
    language: str = "it",
    content_type: str = "blog_draft",
    domain: str = "",
    keyword_target: str = "",
    funnel_stage: str = ""
):
    """
    Standalone validation endpoint.
    Validates content against brand rules, technical accuracy,
    cluster alignment, SEO, and domain coherence.
    Returns detailed CQS score with pass/fail.
    """
    validator = ContentValidator()

    # Rule-based validation
    result = await validator.validate(
        content=content,
        cluster=cluster,
        language=language,
        content_type=content_type,
        domain=domain,
        keyword_target=keyword_target,
        funnel_stage=funnel_stage
    )

    # AI second-pass
    ai_result = await validator.validate_with_ai(
        content=content,
        cluster=cluster,
        language=language,
        keyword_target=keyword_target
    )

    return {
        "cqs_score": result.overall_score,
        "passed": result.passed,
        "threshold": settings.CONTENT_QUALITY_MIN,
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
    database: str = Query(default="it")
):
    """
    Find keyword gaps: keywords where a competitor ranks but Albeni doesn't.
    Identifies content opportunities.
    """
    agent = SemrushAgent()
    return await agent.keyword_gap(database, competitor)


@app.get("/v1/semrush/audit")
async def semrush_full_audit(
    database: str = Query(default="it")
):
    """
    Run a comprehensive SEO audit across the entire Albeni ecosystem.
    Combines domain data, keywords, competitors, backlinks, and 85/15 balance.
    WARNING: Uses many API units. Run sparingly.
    """
    agent = SemrushAgent()
    return await agent.full_seo_audit(database)


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
    """Debug endpoint: raw Gemini response metadata for troubleshooting truncation."""
    settings = get_settings()
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)

        prompt = f"Sei l'assistente di World of Merino. Rispondi in italiano.\n\nCliente: {message}\n\nAssistente:"

        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.5, "max_output_tokens": 8192},
        )

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
async def chat_sizing(
    chest_cm: float,
    language: str = "it",
):
    """
    Interactive Size & Fit Finder.
    Given the user's chest circumference (cm), returns personalized
    size recommendations for both Slim Fit and Regular Fit.
    Mirrors the Shopify widget logic on albeni1905.com.
    """
    if chest_cm < 70 or chest_cm > 150:
        raise HTTPException(
            status_code=400,
            detail="Chest measurement must be between 70 and 150 cm"
        )

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
async def generate_visuals(
    brief_text: str = Body(..., embed=True, description="Markdown text of the editorial brief"),
    max_facts: int = Body(2, embed=True, description="Max facts to generate visuals for"),
    dry_run: bool = Body(False, embed=True, description="If true, only compose prompts without generating"),
):
    """Generate editorial visuals for a Merino News Scanner brief."""
    import base64

    import os
    gemini_key = os.environ.get("GEMINI_API_KEY") or settings.GEMINI_API_KEY
    if not gemini_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    generator = VisualGenerator(api_key=gemini_key)

    if dry_run:
        results = generator.dry_run(brief_text, max_facts=max_facts)
        return {"status": "dry_run", "visuals": results, "count": len(results)}

    raw_results = generator.generate_for_brief(brief_text, max_facts=max_facts)
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
async def visual_dry_run(
    brief_text: str = Body(..., embed=True, description="Markdown text of the editorial brief"),
    max_facts: int = Body(2, embed=True, description="Max facts to generate visuals for"),
):
    """Compose visual prompts without generating images (preview mode)."""
    import os
    gemini_key = os.environ.get("GEMINI_API_KEY") or settings.GEMINI_API_KEY or "dry-run"
    generator = VisualGenerator(api_key=gemini_key)
    results = generator.dry_run(brief_text, max_facts=max_facts)
    return {"status": "dry_run", "visuals": results, "count": len(results)}
