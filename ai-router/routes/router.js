/**
 * AI Router Routes - Cross-Domain Routing Engine
 * Endpoint: /v1/router/assign
 *
 * Determines the optimal destination domain based on IDS score and cluster.
 * Target latency: <120ms using Redis cached scores.
 *
 * Routing Logic:
 *   IDS 0-30  (TOFU) -> worldofmerino.com
 *   IDS 31-65 (MOFU) -> merinouniversity.com
 *   IDS >65   (BOFU) -> perfectmerinoshirt.com (Business/Minimalist)
 *                     -> albeni1905.com (Heritage/Conscious/Authentic)
 */

const express = require('express');
const router = express.Router();
const axios = require('axios');
const redis = require('../utils/redis');

const ML_WORKER_URL = process.env.ML_WORKER_URL || 'http://ml-worker:8000';

// Domain configuration
const DOMAINS = {
    TOFU: process.env.DOMAIN_TOFU || 'https://worldofmerino.com',
    MOFU: process.env.DOMAIN_MOFU || 'https://merinouniversity.com',
    BOFU_TECH: process.env.DOMAIN_BOFU_TECH || 'https://perfectmerinoshirt.com',
    BOFU_HERITAGE: process.env.DOMAIN_BOFU_HERITAGE || 'https://albeni1905.com'
};

// IDS Thresholds
const THRESHOLDS = {
    TOFU_MAX: parseInt(process.env.IDS_TOFU_MAX) || 30,
    MOFU_MAX: parseInt(process.env.IDS_MOFU_MAX) || 65,
    BOFU_MIN: parseInt(process.env.IDS_BOFU_MIN) || 65
};

// Clusters that route to perfectmerinoshirt.com
const TECH_CLUSTERS = ['business_professional', 'modern_minimalist'];

/**
 * GET /v1/router/assign
 * Determine the optimal domain for a user based on IDS and cluster.
 */
router.get('/assign', async (req, res) => {
    const startTime = Date.now();
    // Schema-tolerant param mapping (post Bug 1bis pattern):
    // accept both user_id (legacy) and visitor_id (current snippet convention),
    // both lang and language.
    const user_id = req.query.user_id || req.query.visitor_id;
    const lang = req.query.lang || req.query.language;

    if (!user_id) {
        return res.status(400).json({ error: 'user_id or visitor_id is required' });
    }

    try {
        const redisClient = redis.getClient();

        // 1. Try Redis cache first for ultra-fast response
        let idsScore = await redisClient.get(`user:${user_id}:ids`);
        let predictedCluster = await redisClient.get(`user:${user_id}:cluster`);

        // 2. If not cached, request calculation from ML Worker
        if (idsScore === null) {
            try {
                const mlResponse = await axios.get(
                    `${ML_WORKER_URL}/v1/router/assign`,
                    {
                        params: { user_id, lang: lang || 'it' },
                        timeout: 3000
                    }
                );
                idsScore = mlResponse.data.ids_score;
                predictedCluster = mlResponse.data.assigned_cluster;
            } catch (mlError) {
                console.warn('ML Worker unavailable, using default routing:', mlError.message);
                idsScore = 0;
                predictedCluster = 'unknown';
            }
        } else {
            idsScore = parseInt(idsScore);
        }

        predictedCluster = predictedCluster || 'unknown';

        // 3. Apply routing logic
        let destination;
        let intentStage;

        if (idsScore <= THRESHOLDS.TOFU_MAX) {
            intentStage = 'TOFU';
            destination = DOMAINS.TOFU;
        } else if (idsScore <= THRESHOLDS.MOFU_MAX) {
            intentStage = 'MOFU';
            destination = DOMAINS.MOFU;
        } else {
            intentStage = 'BOFU';
            if (TECH_CLUSTERS.includes(predictedCluster)) {
                destination = DOMAINS.BOFU_TECH;
            } else {
                destination = DOMAINS.BOFU_HERITAGE;
            }
        }

        // 4. Apply language-aware routing
        const userLang = lang || await redisClient.get(`user:${user_id}:lang`) || 'it';
        if (userLang !== 'it') {
            // Append language prefix for international routing
            destination = `${destination}/${userLang}`;
        }

        const latencyMs = Date.now() - startTime;

        // 5. Log routing decision in Redis (for analytics)
        await redisClient.lpush(`routing:log`, JSON.stringify({
            user_id,
            ids_score: idsScore,
            cluster: predictedCluster,
            destination,
            lang: userLang,
            latency_ms: latencyMs,
            timestamp: Date.now()
        }));
        await redisClient.ltrim('routing:log', 0, 9999);

        // 6. Track in GA4 (server-side) - fire and forget
        if (process.env.GA4_MEASUREMENT_ID && process.env.GA4_API_SECRET) {
            trackGA4Routing(user_id, destination, idsScore, predictedCluster);
        }

        res.json({
            user_id,
            ids_score: idsScore,
            assigned_cluster: predictedCluster,
            intent_stage: intentStage,
            redirect_to: destination,
            language: userLang,
            latency_ms: latencyMs
        });

    } catch (error) {
        console.error('Routing error:', error);
        // Fallback: send to TOFU domain
        res.json({
            user_id,
            ids_score: 0,
            assigned_cluster: 'unknown',
            intent_stage: 'TOFU',
            redirect_to: DOMAINS.TOFU,
            language: lang || 'it',
            latency_ms: Date.now() - startTime,
            fallback: true
        });
    }
});

/**
 * GET /v1/router/status
 * Get current routing status for a user (without triggering redirect).
 */
router.get('/status', async (req, res) => {
    // Schema-tolerant (vedi /assign)
    const user_id = req.query.user_id || req.query.visitor_id;

    if (!user_id) {
        return res.status(400).json({ error: 'user_id or visitor_id is required' });
    }

    try {
        const redisClient = redis.getClient();

        const idsScore = await redisClient.get(`user:${user_id}:ids`) || 0;
        const cluster = await redisClient.get(`user:${user_id}:cluster`) || 'unknown';
        const stage = await redisClient.get(`user:${user_id}:stage`) || 'TOFU';
        const lang = await redisClient.get(`user:${user_id}:lang`) || 'it';
        const lastActive = await redisClient.get(`user:${user_id}:last_active`);
        const domains = await redisClient.hgetall(`user:${user_id}:domains`);

        res.json({
            user_id,
            ids_score: parseInt(idsScore),
            cluster,
            intent_stage: stage,
            language: lang,
            last_active: lastActive ? new Date(parseInt(lastActive)).toISOString() : null,
            domain_visits: domains || {},
            cached: true
        });

    } catch (error) {
        res.status(500).json({ error: 'Status retrieval failed' });
    }
});

/**
 * Server-side GA4 tracking for routing decisions.
 */
function trackGA4Routing(userId, destination, idsScore, cluster) {
    const measurementId = process.env.GA4_MEASUREMENT_ID;
    const apiSecret = process.env.GA4_API_SECRET;

    if (!measurementId || !apiSecret) return;

    axios.post(
        `https://www.google-analytics.com/mp/collect?measurement_id=${measurementId}&api_secret=${apiSecret}`,
        {
            client_id: userId,
            events: [{
                name: 'ai_routing_decision',
                params: {
                    destination_domain: destination,
                    ids_score: idsScore,
                    predicted_cluster: cluster,
                    engagement_time_msec: 100
                }
            }]
        }
    ).catch(err => console.error('GA4 tracking failed:', err.message));
}

module.exports = router;
