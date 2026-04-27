/**
 * Tracking Routes - Behavioral Signal Ingestion
 * Endpoint: /v1/track/event
 *
 * Receives signals from the JavaScript snippet deployed on all 4 domains.
 * Stores in Redis for fast access and forwards to ML Worker for processing.
 */

const express = require('express');
const router = express.Router();
const axios = require('axios');
const { v4: uuidv4 } = require('uuid');
const redis = require('../utils/redis');

const ML_WORKER_URL = process.env.ML_WORKER_URL || 'http://ml-worker:8000';

// Critical events that trigger immediate IDS recalculation
const CRITICAL_EVENTS = [
    'click_comparison',
    'download_pdf',
    'lead_magnet_download',
    'add_to_cart',
    'product_view',
    'video_play'
];

/**
 * POST /v1/track/event
 * Ingest behavioral signals from the ecosystem domains.
 */
router.post('/event', async (req, res) => {
    const startTime = Date.now();
    const body = req.body || {};

    // Schema-tolerant extraction: support both legacy snippet (visitor_id, top-level fields)
    // and modern client (user_id, metadata wrapper). Fixes the silent drop where snippets
    // sent visitor_id and got 400, and where top-level fields were never persisted.
    const user_id = body.user_id || body.visitor_id;
    const domain = body.domain || body.source_domain || 'unknown';
    const lang = body.lang || body.language || 'it';
    const event_type = body.event_type;
    const page_url = body.page_url || body.url || '';
    const session_id = body.session_id || body.sessionId || null;

    // ml-worker Pydantic expects timestamp: Optional[int] (millis since epoch).
    // The legacy snippet sends ISO 8601 string. Coerce to int millis.
    let timestamp = body.timestamp;
    if (typeof timestamp === 'string') {
        const parsed = Date.parse(timestamp);
        timestamp = isNaN(parsed) ? Date.now() : parsed;
    } else if (typeof timestamp !== 'number') {
        timestamp = Date.now();
    }

    // Build metadata from explicit metadata/event_value (modern) PLUS any top-level
    // signal fields the legacy snippet sends (dwell_time_ms, scroll_depth_pct, etc.)
    const metadata = {
        ...(body.metadata || body.event_value || {}),
        // Surface legacy top-level signal fields if present
        ...(body.dwell_time_ms !== undefined && { dwell_time_ms: body.dwell_time_ms }),
        ...(body.scroll_depth_pct !== undefined && { scroll_depth_pct: body.scroll_depth_pct }),
        ...(body.mouse_events !== undefined && { mouse_events: body.mouse_events }),
        ...(body.page_views !== undefined && { page_views: body.page_views }),
        ...(body.session_duration_ms !== undefined && { session_duration_ms: body.session_duration_ms }),
        ...(body.device !== undefined && { device: body.device }),
        ...(body.user_agent !== undefined && { user_agent: body.user_agent }),
        ...(body.campaign !== undefined && { campaign: body.campaign }),
    };

    if (!user_id || !event_type) {
        return res.status(400).json({
            error: 'user_id (or visitor_id) and event_type are required',
            received: { hasUserId: !!user_id, hasEventType: !!event_type, keys: Object.keys(body) }
        });
    }

    try {
        const redisClient = redis.getClient();
        const eventId = uuidv4();

        // 1. Store signal in Redis for fast ML Worker access
        const signalData = JSON.stringify({
            id: eventId,
            domain,
            event_type,
            lang,
            metadata,
            page_url,
            timestamp,
            session_id
        });

        const sessionKey = `user:${user_id}:signals`;
        await redisClient.lpush(sessionKey, signalData);
        await redisClient.ltrim(sessionKey, 0, 99); // Keep last 100 signals
        await redisClient.expire(sessionKey, 86400); // 24h TTL

        // 2. Track user activity timestamp
        await redisClient.set(`user:${user_id}:last_active`, Date.now(), 'EX', 3600);

        // 3. Increment domain-specific counters
        await redisClient.hincrby(`user:${user_id}:domains`, domain, 1);
        await redisClient.expire(`user:${user_id}:domains`, 259200); // 72h

        // 4. Track language preference
        if (lang) {
            await redisClient.set(`user:${user_id}:lang`, lang, 'EX', 259200);
        }

        // 5. Forward to ML Worker — AWAIT now (was fire-and-forget which masked failures
        //    e.g. unset ML_WORKER_URL falling back to http://ml-worker:8000 which doesn't
        //    resolve on Railway). If ml-worker is down/slow we still don't want to hold
        //    the snippet too long, so we cap the timeout.
        const forwardPayload = {
            user_id,
            domain,
            lang,
            event_type,
            metadata,
            page_url,
            timestamp
        };

        let forwardOk = false;
        let forwardError = null;
        try {
            await axios.post(`${ML_WORKER_URL}/v1/track/event`, forwardPayload, { timeout: 4000 });
            forwardOk = true;

            // For critical events, also trigger immediate IDS recalculation (best-effort)
            if (CRITICAL_EVENTS.includes(event_type)) {
                axios.post(`${ML_WORKER_URL}/v1/intent/calculate`, {
                    user_id,
                    force_recalculate: true
                }, { timeout: 4000 })
                    .catch(err => console.error('IDS recalc failed:', err.message));
            }
        } catch (err) {
            forwardError = err.message || String(err);
            console.error('ML Worker forward failed:', forwardError, '— url:', `${ML_WORKER_URL}/v1/track/event`);
        }

        const latency = Date.now() - startTime;

        // 202 only when persisted; 502 (Bad Gateway) when forward to ml-worker failed.
        // The dashboard / monitoring can rely on the status code now to spot ghost backends.
        if (!forwardOk) {
            return res.status(502).json({
                status: 'cached_only',
                event_id: eventId,
                latency_ms: latency,
                error: 'ml_worker_unreachable',
                detail: forwardError
            });
        }

        res.status(202).json({
            status: 'event_logged',
            event_id: eventId,
            latency_ms: latency,
            persisted: true
        });

    } catch (error) {
        console.error('Event tracking error:', error);
        res.status(500).json({ error: 'Ingestion failed', detail: error.message });
    }
});

/**
 * POST /v1/track/batch
 * Batch ingestion of multiple events (for deferred/offline signals).
 */
router.post('/batch', async (req, res) => {
    const { events } = req.body;

    if (!Array.isArray(events) || events.length === 0) {
        return res.status(400).json({ error: 'events array is required' });
    }

    if (events.length > 50) {
        return res.status(400).json({ error: 'Maximum 50 events per batch' });
    }

    const results = [];
    const redisClient = redis.getClient();

    for (const event of events) {
        try {
            const eventId = uuidv4();
            const sessionKey = `user:${event.user_id}:signals`;
            await redisClient.lpush(sessionKey, JSON.stringify({
                id: eventId,
                domain: event.domain,
                event_type: event.event_type,
                lang: event.lang || 'it',
                metadata: event.metadata || {},
                timestamp: event.timestamp || Date.now()
            }));
            results.push({ event_id: eventId, status: 'logged' });
        } catch (err) {
            results.push({ error: err.message, status: 'failed' });
        }
    }

    // Forward batch to ML Worker
    axios.post(`${ML_WORKER_URL}/v1/track/event`, { batch: events })
        .catch(err => console.error('ML Worker batch forward failed:', err.message));

    res.status(202).json({ status: 'batch_processed', results });
});

module.exports = router;
