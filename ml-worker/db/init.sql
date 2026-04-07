-- =============================================================
-- AI Orchestration Layer - Albeni 1905
-- PostgreSQL Database Schema
-- =============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================
-- A. USERS TABLE
-- Centralizes user identity across the 4-domain ecosystem
-- =============================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id VARCHAR(50) UNIQUE NOT NULL,        -- Cross-domain ID (from JS snippet)
    email VARCHAR(255) UNIQUE,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    preferred_language VARCHAR(5) DEFAULT 'it',      -- it, en, fr, de, es
    assigned_cluster VARCHAR(50),                     -- business_professional, heritage_mature, etc.
    cluster_confidence DECIMAL(5,4) DEFAULT 0.0,     -- Prediction confidence (target >0.85)
    ids_score INTEGER DEFAULT 0,                      -- Current Intent Depth Score (0-100)
    intent_stage VARCHAR(10) DEFAULT 'TOFU',          -- TOFU, MOFU, BOFU
    klaviyo_profile_id VARCHAR(100),                  -- Klaviyo CRM link
    shopify_customer_id VARCHAR(100),                 -- Shopify link
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_sessions INTEGER DEFAULT 0,
    total_purchases INTEGER DEFAULT 0,
    ltv_estimate DECIMAL(10,2) DEFAULT 0.00,
    churn_risk DECIMAL(5,4) DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_external_id ON users(external_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_cluster ON users(assigned_cluster);
CREATE INDEX idx_users_ids_score ON users(ids_score);
CREATE INDEX idx_users_intent_stage ON users(intent_stage);

-- =============================================================
-- B. SESSIONS TABLE
-- Tracks individual browsing sessions across domains
-- =============================================================
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(100) UNIQUE NOT NULL,
    source_domain VARCHAR(100) NOT NULL,              -- worldofmerino.com, merinouniversity.com, etc.
    language VARCHAR(5) DEFAULT 'it',
    entry_page TEXT,
    exit_page TEXT,
    page_views INTEGER DEFAULT 0,
    total_dwell_time INTEGER DEFAULT 0,               -- Total seconds
    max_scroll_depth INTEGER DEFAULT 0,               -- Max % reached
    ids_score_start INTEGER DEFAULT 0,
    ids_score_end INTEGER DEFAULT 0,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    utm_source VARCHAR(100),
    utm_medium VARCHAR(100),
    utm_campaign VARCHAR(200),
    device_type VARCHAR(20),                          -- mobile, desktop, tablet
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_domain ON sessions(source_domain);
CREATE INDEX idx_sessions_active ON sessions(is_active);
CREATE INDEX idx_sessions_created ON sessions(created_at);

-- =============================================================
-- C. BEHAVIORAL SIGNALS TABLE
-- Logs every micro-interaction for IDS calculation
-- =============================================================
CREATE TABLE behavioral_signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    domain VARCHAR(100) NOT NULL,
    language VARCHAR(5) DEFAULT 'it',
    event_type VARCHAR(50) NOT NULL,                  -- scroll_depth, dwell_time_reached, technical_interaction, etc.
    event_value JSONB,                                -- Flexible metadata storage
    -- Specific signal fields for fast querying
    scroll_depth INTEGER,                             -- 25, 50, 75, 90
    dwell_time_seconds INTEGER,
    interaction_type VARCHAR(50),                      -- click_comparison, download_pdf, video_play, etc.
    interaction_element VARCHAR(200),
    page_url TEXT,
    referrer_url TEXT,
    ids_points_awarded DECIMAL(5,2) DEFAULT 0,        -- Points contributed to IDS
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_signals_user_id ON behavioral_signals(user_id);
CREATE INDEX idx_signals_session_id ON behavioral_signals(session_id);
CREATE INDEX idx_signals_event_type ON behavioral_signals(event_type);
CREATE INDEX idx_signals_created ON behavioral_signals(created_at);
CREATE INDEX idx_signals_domain ON behavioral_signals(domain);

-- =============================================================
-- D. INTENT INTELLIGENCE TABLE
-- Stores AI-processed results: IDS calculations, cluster predictions
-- =============================================================
CREATE TABLE intent_intelligence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ids_score INTEGER NOT NULL,                        -- Calculated IDS (0-100)
    ids_breakdown JSONB NOT NULL,                      -- {dwell_time: X, scroll: Y, interactions: Z, frequency: W}
    predicted_cluster VARCHAR(50),
    cluster_probabilities JSONB,                       -- {business: 0.82, heritage: 0.12, ...}
    intent_stage VARCHAR(10) NOT NULL,                 -- TOFU, MOFU, BOFU
    routing_decision VARCHAR(200),                     -- Assigned destination domain
    language VARCHAR(5) DEFAULT 'it',
    model_version VARCHAR(20) DEFAULT 'v1.0',
    calculation_latency_ms INTEGER,                    -- Performance tracking
    triggered_actions JSONB,                           -- Actions taken (klaviyo_sync, route_change, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_intelligence_user_id ON intent_intelligence(user_id);
CREATE INDEX idx_intelligence_ids ON intent_intelligence(ids_score);
CREATE INDEX idx_intelligence_cluster ON intent_intelligence(predicted_cluster);
CREATE INDEX idx_intelligence_stage ON intent_intelligence(intent_stage);
CREATE INDEX idx_intelligence_created ON intent_intelligence(created_at);

-- =============================================================
-- E. CONTENT GENERATION LOG
-- Tracks AI-generated content (70/30 model)
-- =============================================================
CREATE TABLE content_generation_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    target_cluster VARCHAR(50) NOT NULL,
    target_language VARCHAR(5) DEFAULT 'it',
    content_type VARCHAR(50) NOT NULL,                 -- email_copy, blog_draft, landing_copy, lead_magnet
    target_domain VARCHAR(100),
    intent_stage VARCHAR(10),
    generated_content TEXT NOT NULL,
    content_quality_score DECIMAL(5,2),                -- CQS target >= 76
    human_review_status VARCHAR(20) DEFAULT 'pending', -- pending, approved, rejected, revised
    human_reviewer VARCHAR(100),
    revision_notes TEXT,
    model_used VARCHAR(50) DEFAULT 'gpt-4o',
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP
);

CREATE INDEX idx_content_cluster ON content_generation_log(target_cluster);
CREATE INDEX idx_content_status ON content_generation_log(human_review_status);
CREATE INDEX idx_content_type ON content_generation_log(content_type);

-- =============================================================
-- F. SEO MONITORING TABLE
-- Tracks 85/15 balance, cannibalization, keyword health
-- =============================================================
CREATE TABLE seo_monitoring (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    check_date DATE NOT NULL DEFAULT CURRENT_DATE,
    domain VARCHAR(100) NOT NULL,
    language VARCHAR(5) DEFAULT 'it',
    -- 85/15 Balance Tracking
    behavioral_expansion_pct DECIMAL(5,2),             -- Target: 85%
    semantic_defense_pct DECIMAL(5,2),                  -- Target: 15%
    -- Cannibalization Monitoring
    cannibalization_score DECIMAL(5,2) DEFAULT 0,       -- Alert >6%, Critical >12%
    conflicting_keywords JSONB,                         -- Keywords causing cannibalization
    canonical_suggestions JSONB,                        -- Suggested fixes
    -- Keyword Health
    total_tracked_keywords INTEGER DEFAULT 0,
    keywords_top3 INTEGER DEFAULT 0,
    keywords_top10 INTEGER DEFAULT 0,
    topical_authority_score DECIMAL(5,2),
    -- Featured Snippets
    featured_snippets_won INTEGER DEFAULT 0,
    featured_snippets_lost INTEGER DEFAULT 0,
    alert_level VARCHAR(10) DEFAULT 'green',            -- green, yellow, red
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_seo_domain ON seo_monitoring(domain);
CREATE INDEX idx_seo_date ON seo_monitoring(check_date);
CREATE INDEX idx_seo_alert ON seo_monitoring(alert_level);

-- =============================================================
-- G. CPA & FINANCIAL GOVERNANCE TABLE
-- =============================================================
CREATE TABLE financial_governance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_date DATE NOT NULL DEFAULT CURRENT_DATE,
    cluster VARCHAR(50),
    language VARCHAR(5) DEFAULT 'it',
    market VARCHAR(5),                                  -- IT, DE, FR, EN, ES
    -- CPA Metrics
    cpa_current DECIMAL(10,2),                          -- Current CPA in EUR
    cpa_alert_level VARCHAR(10) DEFAULT 'green',        -- green (<=9), yellow (10-15), red (>15)
    -- Revenue & ROI
    revenue_total DECIMAL(12,2) DEFAULT 0,
    revenue_from_crm DECIMAL(12,2) DEFAULT 0,           -- Target 22-28% of total
    crm_revenue_pct DECIMAL(5,2) DEFAULT 0,
    roi_operational DECIMAL(7,2) DEFAULT 0,             -- Target >= 100%
    -- Campaign Performance
    total_orders INTEGER DEFAULT 0,
    conversion_rate DECIMAL(5,4) DEFAULT 0,
    cpc_avg DECIMAL(10,2) DEFAULT 0,
    ad_spend DECIMAL(12,2) DEFAULT 0,
    -- Klaviyo Metrics
    email_open_rate DECIMAL(5,4) DEFAULT 0,             -- Target > 40%
    email_ctr DECIMAL(5,4) DEFAULT 0,                   -- Target > 8%
    -- Alerts
    anomalies_detected JSONB,
    actions_taken JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_financial_date ON financial_governance(report_date);
CREATE INDEX idx_financial_cluster ON financial_governance(cluster);
CREATE INDEX idx_financial_alert ON financial_governance(cpa_alert_level);

-- =============================================================
-- H. KLAVIYO SYNC LOG
-- Tracks all CRM synchronization events
-- =============================================================
CREATE TABLE klaviyo_sync_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    sync_type VARCHAR(50) NOT NULL,                     -- profile_update, flow_trigger, event_track
    trigger_reason VARCHAR(100),                        -- ids_threshold, cluster_change, purchase, etc.
    payload_sent JSONB NOT NULL,
    response_status INTEGER,
    response_body JSONB,
    sync_latency_ms INTEGER,
    success BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_klaviyo_user ON klaviyo_sync_log(user_id);
CREATE INDEX idx_klaviyo_type ON klaviyo_sync_log(sync_type);
CREATE INDEX idx_klaviyo_success ON klaviyo_sync_log(success);
CREATE INDEX idx_klaviyo_created ON klaviyo_sync_log(created_at);

-- =============================================================
-- I. ROUTING DECISIONS LOG
-- Audit trail of all routing decisions
-- =============================================================
CREATE TABLE routing_decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    ids_score INTEGER NOT NULL,
    predicted_cluster VARCHAR(50),
    source_domain VARCHAR(100),
    destination_domain VARCHAR(100),
    language VARCHAR(5),
    intent_stage VARCHAR(10),
    decision_latency_ms INTEGER,                        -- Target <120ms
    was_redirected BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_routing_user ON routing_decisions(user_id);
CREATE INDEX idx_routing_created ON routing_decisions(created_at);

-- =============================================================
-- J. MARKETING ATTRIBUTIONS TABLE
-- Maps every single click from advertising platforms
-- Links GCLID/FBCLID to user profiles for offline conversion feedback
-- =============================================================
CREATE TABLE marketing_attributions (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    source VARCHAR(50) NOT NULL,                          -- google, meta, linkedin, organic
    medium VARCHAR(50),                                   -- cpc, dpa, story, email
    campaign_name VARCHAR(200),
    keyword VARCHAR(200),                                 -- utm_term (es. "17.5 micron")
    ad_content VARCHAR(200),                              -- utm_content
    click_id VARCHAR(255) UNIQUE,                         -- GCLID o FBCLID
    click_id_type VARCHAR(10),                            -- gclid, fbclid
    landing_domain VARCHAR(100),
    landing_page TEXT,
    device_type VARCHAR(20),                              -- mobile, desktop, tablet
    intent_type VARCHAR(50),                              -- search_intent, social_intent, display_intent
    ids_at_click INTEGER DEFAULT 0,                       -- IDS score at the time of click
    converted BOOLEAN DEFAULT FALSE,                      -- True if user reached high-quality threshold
    conversion_value DECIMAL(10,2) DEFAULT 0,             -- EUR value sent to platform
    conversion_sent_at TIMESTAMP,                         -- When feedback was sent to Google/Meta
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_attr_user ON marketing_attributions(user_id);
CREATE INDEX idx_attr_click_id ON marketing_attributions(click_id);
CREATE INDEX idx_attr_source ON marketing_attributions(source);
CREATE INDEX idx_attr_keyword ON marketing_attributions(keyword);
CREATE INDEX idx_attr_created ON marketing_attributions(created_at);
CREATE INDEX idx_attr_converted ON marketing_attributions(converted);

-- =============================================================
-- K. USER INTENT LOGS TABLE
-- Logs all relevant actions captured by the AI Layer sensors
-- Used for IDS calculation and cross-domain attribution analysis
-- =============================================================
CREATE TABLE user_intent_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    domain VARCHAR(100) NOT NULL,
    event_type VARCHAR(50) NOT NULL,                      -- page_view, scroll, click, dwell_time, bot_detected
    event_value JSONB,                                    -- Flexible extra data
    ids_impact INTEGER DEFAULT 0,                         -- How much this event changed the IDS
    campaign_click_id VARCHAR(255),                       -- Link back to marketing_attributions.click_id
    source VARCHAR(50),                                   -- Where this event originated (google, meta, organic)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_intent_log_user ON user_intent_logs(user_id);
CREATE INDEX idx_intent_log_event ON user_intent_logs(event_type);
CREATE INDEX idx_intent_log_domain ON user_intent_logs(domain);
CREATE INDEX idx_intent_log_created ON user_intent_logs(created_at);
CREATE INDEX idx_intent_log_click_id ON user_intent_logs(campaign_click_id);

-- =============================================================
-- L. BOT SHIELD EXCLUSIONS TABLE
-- Persists blocked IPs/fingerprints for cross-restart protection
-- =============================================================
CREATE TABLE bot_shield_exclusions (
    id SERIAL PRIMARY KEY,
    ip_address VARCHAR(45) NOT NULL,                      -- IPv4/IPv6
    visitor_id VARCHAR(100),
    threat_score DECIMAL(5,3) NOT NULL,
    signals JSONB NOT NULL,                               -- Array of threat signals
    is_paid_click BOOLEAN DEFAULT FALSE,
    estimated_savings_eur DECIMAL(10,2) DEFAULT 0,
    excluded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '30 days'),
    active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_bot_ip ON bot_shield_exclusions(ip_address);
CREATE INDEX idx_bot_active ON bot_shield_exclusions(active);
CREATE INDEX idx_bot_expires ON bot_shield_exclusions(expires_at);


-- =============================================================
-- FUNCTIONS & TRIGGERS
-- =============================================================

-- Auto-update updated_at on users table
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to calculate CPA alert level
CREATE OR REPLACE FUNCTION get_cpa_alert_level(cpa DECIMAL)
RETURNS VARCHAR(10) AS $$
BEGIN
    IF cpa <= 9 THEN RETURN 'green';
    ELSIF cpa <= 15 THEN RETURN 'yellow';
    ELSE RETURN 'red';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to determine intent stage from IDS
CREATE OR REPLACE FUNCTION get_intent_stage(ids INTEGER)
RETURNS VARCHAR(10) AS $$
BEGIN
    IF ids <= 30 THEN RETURN 'TOFU';
    ELSIF ids <= 65 THEN RETURN 'MOFU';
    ELSE RETURN 'BOFU';
    END IF;
END;
$$ LANGUAGE plpgsql;
