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
