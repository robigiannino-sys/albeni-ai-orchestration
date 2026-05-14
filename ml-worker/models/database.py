"""
SQLAlchemy Database Models - AI Orchestration Layer
"""
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean,
    DateTime, Text, ForeignKey, JSON, Date, Numeric, BigInteger
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid

from config import get_settings

settings = get_settings()
engine = create_engine(settings.effective_database_url, pool_size=20, max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    preferred_language = Column(String(5), default="it")
    assigned_cluster = Column(String(50))
    cluster_confidence = Column(Numeric(5, 4), default=0.0)
    ids_score = Column(Integer, default=0)
    intent_stage = Column(String(10), default="TOFU")
    klaviyo_profile_id = Column(String(100))
    shopify_customer_id = Column(String(100))
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    total_sessions = Column(Integer, default=0)
    total_purchases = Column(Integer, default=0)
    ltv_estimate = Column(Numeric(10, 2), default=0.00)
    churn_risk = Column(Numeric(5, 4), default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sessions = relationship("Session", back_populates="user")
    signals = relationship("BehavioralSignal", back_populates="user")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_id = Column(String(100), unique=True, nullable=False)
    source_domain = Column(String(100), nullable=False)
    language = Column(String(5), default="it")
    entry_page = Column(Text)
    exit_page = Column(Text)
    page_views = Column(Integer, default=0)
    total_dwell_time = Column(Integer, default=0)
    max_scroll_depth = Column(Integer, default=0)
    ids_score_start = Column(Integer, default=0)
    ids_score_end = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    utm_source = Column(String(100))
    utm_medium = Column(String(100))
    utm_campaign = Column(String(200))
    device_type = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")
    signals = relationship("BehavioralSignal", back_populates="session")


class BehavioralSignal(Base):
    __tablename__ = "behavioral_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"))
    domain = Column(String(100), nullable=False)
    language = Column(String(5), default="it")
    event_type = Column(String(50), nullable=False)
    event_value = Column(JSONB)
    scroll_depth = Column(Integer)
    dwell_time_seconds = Column(Integer)
    interaction_type = Column(String(50))
    interaction_element = Column(String(200))
    page_url = Column(Text)
    referrer_url = Column(Text)
    ids_points_awarded = Column(Numeric(5, 2), default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="signals")
    session = relationship("Session", back_populates="signals")


class IntentIntelligence(Base):
    __tablename__ = "intent_intelligence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ids_score = Column(Integer, nullable=False)
    ids_breakdown = Column(JSONB, nullable=False)
    predicted_cluster = Column(String(50))
    cluster_probabilities = Column(JSONB)
    intent_stage = Column(String(10), nullable=False)
    routing_decision = Column(String(200))
    language = Column(String(5), default="it")
    model_version = Column(String(20), default="v1.0")
    calculation_latency_ms = Column(Integer)
    triggered_actions = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)


class ContentGenerationLog(Base):
    __tablename__ = "content_generation_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_cluster = Column(String(50), nullable=False)
    target_language = Column(String(5), default="it")
    content_type = Column(String(50), nullable=False)
    target_domain = Column(String(100))
    intent_stage = Column(String(10))
    generated_content = Column(Text, nullable=False)
    content_quality_score = Column(Numeric(5, 2))
    human_review_status = Column(String(20), default="pending")
    human_reviewer = Column(String(100))
    revision_notes = Column(Text)
    model_used = Column(String(50), default="gpt-4o")
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime)


class KlaviyoSyncLog(Base):
    __tablename__ = "klaviyo_sync_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    sync_type = Column(String(50), nullable=False)
    trigger_reason = Column(String(100))
    payload_sent = Column(JSONB, nullable=False)
    response_status = Column(Integer)
    response_body = Column(JSONB)
    sync_latency_ms = Column(Integer)
    success = Column(Boolean, default=False)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class RoutingDecision(Base):
    __tablename__ = "routing_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    ids_score = Column(Integer, nullable=False)
    predicted_cluster = Column(String(50))
    source_domain = Column(String(100))
    destination_domain = Column(String(100))
    language = Column(String(5))
    intent_stage = Column(String(10))
    decision_latency_ms = Column(Integer)
    was_redirected = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketingAttribution(Base):
    __tablename__ = "marketing_attributions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    source = Column(String(50), nullable=False)
    medium = Column(String(50))
    campaign_name = Column(String(200))
    keyword = Column(String(200))
    ad_content = Column(String(200))
    click_id = Column(String(255), unique=True)
    click_id_type = Column(String(10))           # gclid, fbclid
    landing_domain = Column(String(100))
    landing_page = Column(Text)
    device_type = Column(String(20))
    intent_type = Column(String(50))
    ids_at_click = Column(Integer, default=0)
    converted = Column(Boolean, default=False)
    conversion_value = Column(Numeric(10, 2), default=0)
    conversion_sent_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="attributions")


class UserIntentLog(Base):
    __tablename__ = "user_intent_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    domain = Column(String(100), nullable=False)
    event_type = Column(String(50), nullable=False)
    event_value = Column(JSONB)
    ids_impact = Column(Integer, default=0)
    campaign_click_id = Column(String(255))
    source = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="intent_logs")


class BotShieldExclusion(Base):
    __tablename__ = "bot_shield_exclusions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip_address = Column(String(45), nullable=False)
    visitor_id = Column(String(100))
    threat_score = Column(Numeric(5, 3), nullable=False)
    signals = Column(JSONB, nullable=False)
    is_paid_click = Column(Boolean, default=False)
    estimated_savings_eur = Column(Numeric(10, 2), default=0)
    excluded_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    active = Column(Boolean, default=True)


class GSCIndexingScan(Base):
    """
    GSC Indexing Monitor scan results - persistence for Tower GSC widget.
    Migrated from filesystem JSON (ai-router/dashboard/gsc_data.json) on
    2026-05-14 because container fs is ephemeral - scans were lost every deploy.
    """
    __tablename__ = "gsc_indexing_scans"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    scan_id = Column(String(100), unique=True, nullable=False, index=True)  # e.g. "mu-2026-05-13"
    site = Column(String(100), nullable=False, index=True)
    property = Column(Text)
    date = Column(Date, nullable=False, index=True)
    total_urls = Column(Integer, default=0)
    indexed = Column(Integer, default=0)
    crawled_not_indexed = Column(Integer, default=0)
    not_crawled = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    neutral = Column(Integer, default=0)
    duration_minutes = Column(Integer, nullable=True)
    source = Column(String(50), default="manual")
    created_at = Column(DateTime, default=datetime.utcnow)


class KPISnapshot(Base):
    """
    Snapshot daily di un KPI della Dashboard Executive.
    Sostiene l'Anomaly Detection v0 (Step 3b, 2026-05-14):
    - Cron daily registra valori KPI di oggi
    - Detection confronta oggi vs rolling 7d avg
    - Alert generati in anomaly_alerts quando deviazione fuori soglia

    UPSERT su (date, metric_name): rerun stesso giorno sovrascrive.

    metric_name convention (lowercase + snake_case):
      - cpa_7d                       (€)
      - organic_pct                  (%)
      - paid_pct                     (%)
      - cluster_heritage_mature_cr   (%)
      - cluster_business_pro_cr      (%)
      - ids_avg                      (n)
      - pipeline_published_total     (n)
    """
    __tablename__ = "kpi_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    metric_name = Column(String(80), nullable=False, index=True)
    value = Column(Numeric(14, 4), nullable=True)        # nullable se KPI non calcolabile (es. CPA con zero spend)
    sample_size = Column(Integer, nullable=True)         # n. di datapoint usati (paid attr, attribuzioni, ecc.) — utile per filtri qualità
    extra = Column(JSONB, nullable=True)                 # band, reason, breakdown — payload contestuale
    created_at = Column(DateTime, default=datetime.utcnow)


class AnomalyAlert(Base):
    """
    Alert generato dall'engine Anomaly Detection v0.
    Severity ladder:
      INFO     · deviazione 10-25% vs baseline 7d
      WARNING  · deviazione 25-50% vs baseline 7d
      CRITICAL · deviazione >50% OR cross-threshold (es. CPA che salta a NERO)

    Alert sono "resolved=False" finché non manualmente chiusi via /v1/anomaly/alerts/{id}/resolve
    (endpoint da aggiungere in iterazione successiva — per ora si lasciano aperti).
    """
    __tablename__ = "anomaly_alerts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    metric_name = Column(String(80), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)   # INFO | WARNING | CRITICAL
    current_value = Column(Numeric(14, 4), nullable=True)
    baseline_value = Column(Numeric(14, 4), nullable=True)
    deviation_pct = Column(Numeric(8, 2), nullable=True)        # signed: positivo=sopra baseline, negativo=sotto
    message = Column(Text, nullable=False)
    resolved = Column(Boolean, default=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class CrawlMapEntry(Base):
    """
    Per-URL crawl/indexing verdict (PASS · NEUTRAL · N/A · FAIL).
    Migrazione 2026-05-14 (NEW-02 audit closure): da wom_crawl_map.json / mu_crawl_map.json
    (committati a git nella dashboard ai-router, read-only) a Postgres con UPSERT incrementale.

    UPSERT su (site, url_path): re-scan stessa URL aggiorna senza duplicare.
    """
    __tablename__ = "crawl_map_entries"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    site = Column(String(20), nullable=False, index=True)            # 'mu' | 'wom' (matcha middleware Node)
    url_path = Column(String(500), nullable=False, index=True)        # es. '/de/de-heritage-archive'
    verdict = Column(String(20), nullable=False, index=True)          # PASS | NEUTRAL | N/A | FAIL | UNKNOWN
    last_scanned_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String(50), default="manual")                     # manual | gsc_scan | semrush_scan | migration_json
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AdvSpend(Base):
    """
    ADV daily spend by channel / campaign.
    Sblocca il Tile T1 CPA della Dashboard Executive: CPA = SUM(amount_eur)/COUNT(paid_conversions).
    Soglie (doc 19): VERDE ≤€9 · GIALLO €10-15 · ROSSO €16-34 · NERO ≥€35.

    Pattern speculare a GSCIndexingScan (filesystem→Postgres, fix 2026-05-14):
    idempotency via spend_id, UPSERT semantics, auto-create al primo POST.
    """
    __tablename__ = "adv_spend"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # spend_id pattern: "{channel}-{date}-{campaign_id}" — chiave naturale per UPSERT
    spend_id = Column(String(200), unique=True, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    channel = Column(String(50), nullable=False, index=True)        # google_ads, meta_ads, tiktok_ads, ...
    campaign_id = Column(String(100))                                # ID stabile della piattaforma
    campaign_name = Column(String(255))                              # human-readable
    amount_eur = Column(Numeric(10, 2), nullable=False, default=0)   # spend convertito in EUR
    currency = Column(String(3), default="EUR")                      # valuta originale
    amount_original = Column(Numeric(10, 2), nullable=True)          # importo nella valuta originale (audit)
    impressions = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    country = Column(String(2), nullable=True)                       # ISO-2: IT, DE, FR, US, UK
    source = Column(String(50), default="manual")                    # manual | google_ads_sync | meta_ads_sync | api
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
