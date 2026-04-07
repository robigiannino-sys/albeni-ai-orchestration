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
    const { user_id, domain, lang, event_type, metadata, timestamp, page_url } = req.body;

    if (!user_id || !event_type) {
        return res.status(400).json({ error: 'user_id and event_type are required' });
    }

    try {
        const redisClient = redis.getClient();
        const eventId = uuidv4();

        // 1. Store signal in Redis for fast ML Worker access
        const signalData = JSON.stringify({
            id: eventId,
            domain: domain || 'unknown',
            event_type,
            lang: lang || 'it',
            metadata: metadata || {},
            page_url: page_url || '',
            timestamp: timestamp || Date.now()
        });

        const sessionKey = `user:${user_id}:signals`;
        await redisClient.lpush(sessionKey, signalData);
        await redisClient.ltrim(sessionKey, 0, 99); // Keep last 100 signals
        await redisClient.expire(sessionKey, 86400); // 24h TTL

        // 2. Track user activity timestamp
        await redisClient.set(`user:${user_id}:last_active`, Date.now(), 'EX', 3600);

        // 3. Increment domain-specific counters
        await redisClient.hincrby(`user:${user_id}:domains`, domain || 'unknown', 1);
        await redisClient.expire(`user:${user_id}:domains`, 259200); // 72h

        // 4. Track language preference
        if (lang) {
            await redisClient.set(`user:${user_id}:lang`, lang, 'EX', 259200);
        }

        // 5. Forward to ML Worker (non-blocking for regular events)
        const forwardPayload = {
            user_id,
            domain: domain || 'unknown',
            lang: lang || 'it',
            event_type,
            metadata: metadata || {},
            page_url: page_url || '',
            timestamp: timestamp || Date.now()
        };

        // For critical events, trigger immediate IDS recalculation
        if (CRITICAL_EVENTS.includes(event_type)) {
            // Fire and forget - don't block the response
            axios.post(`${ML_WORKER_URL}/v1/track/event`, forwardPayload)
                .then(() => {
                    // Also trigger IDS recalculation
                    return axios.post(`${ML_WORKER_URL}/v1/intent/calculate`, {
                        user_id,
                        force_recalculate: true
                    });
                })
                .catch(err => console.error('ML Worker forward failed:', err.message));
        } else {
            // Non-critical: just forward the event
            axios.post(`${ML_WORKER_URL}/v1/track/event`, forwardPayload)
                .catch(err => console.error('ML Worker forward failed:', err.message));
        }

        const latency = Date.now() - startTime;

        res.status(202).json({
            status: 'event_logged',
            event_id: eventId,
            latency_ms: latency
        });

    } catch (error) {
        console.error('Event tracking error:', error);
        res.status(500).json({ error: 'Ingestion failed' });
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
