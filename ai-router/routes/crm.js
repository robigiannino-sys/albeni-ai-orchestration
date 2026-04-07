/**
 * CRM Integration Routes - Klaviyo Sync
 * Endpoint: /v1/crm/sync-lead
 *
 * Bridges the AI Router with Klaviyo CRM.
 * Forwards enriched user data to ML Worker for processing and sync.
 */

const express = require('express');
const router = express.Router();
const axios = require('axios');
const redis = require('../utils/redis');

const ML_WORKER_URL = process.env.ML_WORKER_URL || 'http://ml-worker:8000';

/**
 * POST /v1/crm/sync-lead
 * Sync user profile to Klaviyo with AI-enriched data.
 * Typically triggered when IDS > 65 (BOFU threshold).
 */
router.post('/sync-lead', async (req, res) => {
    const startTime = Date.now();
    const {
        email, visitor_id,
        ids_score, cluster, cluster_tag,
        intent_stage, language,
        last_visited_domain, domain, domain_type, domain_path,
        source, signals,
        ai_metadata
    } = req.body;

    // email is now optional — anonymous visitor syncs are allowed (visitor_id required)
    if (!email && !visitor_id) {
        return res.status(400).json({ error: 'email or visitor_id is required' });
    }

    // Derive intent_stage from IDS score if not provided
    const idsScore = ids_score || 0;
    let derivedStage = intent_stage;
    if (!derivedStage) {
        if (idsScore >= 65) derivedStage = 'BOFU';
        else if (idsScore >= 30) derivedStage = 'MOFU';
        else derivedStage = 'TOFU';
    }

    // Cache anonymous sync to avoid duplicate Klaviyo calls (TTL: 1 hour)
    if (!email && visitor_id) {
        const cacheKey = `klaviyo_anon_sync:${visitor_id}`;
        try {
            const cached = await redis.getClient().get(cacheKey);
            if (cached) {
                return res.json({ status: 'already_synced', visitor_id, cached: true });
            }
            await redis.getClient().setEx(cacheKey, 3600, JSON.stringify({ ids_score: idsScore, cluster: cluster || cluster_tag }));
        } catch (redisErr) {
            console.warn('Redis cache error (non-blocking):', redisErr.message);
        }
    }

    try {
        // Forward to ML Worker which handles Klaviyo API integration
        const response = await axios.post(
            `${ML_WORKER_URL}/v1/crm/sync-lead`,
            {
                email:                email || null,
                visitor_id:           visitor_id || null,
                ids_score:            idsScore,
                cluster_tag:          cluster || cluster_tag || 'unknown',
                intent_stage:         derivedStage,
                language:             language || 'it',
                last_visited_domain:  domain || last_visited_domain || '',
                domain_type:          domain_type || 'bofu_tech',
                domain_path:          domain_path || [],
                source:               source || 'behavioral_engine',
                behavioral_signals:   signals || {},
                ai_metadata:          ai_metadata || {}
            },
            { timeout: 10000 }
        );

        const latency = Date.now() - startTime;

        res.json({
            ...response.data,
            router_latency_ms: latency
        });

    } catch (error) {
        console.error('CRM sync error:', error.message);
        res.status(502).json({
            error: 'CRM sync failed',
            detail: error.response?.data || error.message
        });
    }
});

/**
 * POST /v1/crm/trigger-flow
 * Manually trigger a specific Klaviyo flow for a user.
 */
router.post('/trigger-flow', async (req, res) => {
    const { email, flow_type, properties } = req.body;

    if (!email || !flow_type) {
        return res.status(400).json({ error: 'email and flow_type are required' });
    }

    const validFlows = ['welcome', 'consideration', 'conversion', 'post_purchase', 'win_back'];
    if (!validFlows.includes(flow_type)) {
        return res.status(400).json({
            error: `Invalid flow_type. Must be one of: ${validFlows.join(', ')}`
        });
    }

    try {
        // Map flow types to intent stages
        const flowToStage = {
            welcome: 'TOFU',
            consideration: 'MOFU',
            conversion: 'BOFU',
            post_purchase: 'BOFU',
            win_back: 'BOFU'
        };

        const response = await axios.post(
            `${ML_WORKER_URL}/v1/crm/sync-lead`,
            {
                email,
                ids_score: properties?.ids_score || 50,
                cluster_tag: properties?.cluster_tag || 'unknown',
                intent_stage: flowToStage[flow_type],
                language: properties?.language || 'it',
                ai_metadata: properties || {}
            },
            { timeout: 10000 }
        );

        res.json({
            status: 'flow_triggered',
            flow_type,
            ...response.data
        });

    } catch (error) {
        console.error('Flow trigger error:', error.message);
        res.status(502).json({ error: 'Flow trigger failed' });
    }
});

/**
 * POST /v1/crm/unboxing
 * Triggered when customer scans QR code on delivery box.
 * Activates post-purchase CX enhancement flow.
 */
router.post('/unboxing', async (req, res) => {
    const { email, order_id, product_weight } = req.body;

    if (!email || !order_id) {
        return res.status(400).json({ error: 'email and order_id are required' });
    }

    try {
        const response = await axios.post(
            `${ML_WORKER_URL}/v1/crm/post-purchase`,
            null,
            {
                params: {
                    email,
                    order_id,
                    weight: product_weight || '150g'
                },
                timeout: 10000
            }
        );

        res.json({
            status: 'unboxing_flow_triggered',
            order_id,
            cross_sell_suggestion: product_weight === '150g' ? '190g' : '150g'
        });

    } catch (error) {
        console.error('Unboxing trigger error:', error.message);
        res.status(502).json({ error: 'Unboxing flow trigger failed' });
    }
});

module.exports = router;
