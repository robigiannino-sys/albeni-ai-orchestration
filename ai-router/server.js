/**
 * AI Router - Node.js Express Server
 * micron-è — AI Orchestration Layer
 *
 * The "traffic controller" of the ecosystem.
 * Manages cross-domain routing at <120ms latency using Redis cache.
 */

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const rateLimit = require('express-rate-limit');
const path = require('path');
const dotenv = require('dotenv');

dotenv.config();

const app = express();

// Import route modules
const trackingRoutes = require('./routes/tracking');
const routerRoutes = require('./routes/router');
const crmRoutes = require('./routes/crm');

// Import middleware
const { botProtection } = require('./middleware/botProtection');
const { c2paMiddleware } = require('./middleware/c2pa');
const { createRoutes: createIndexRoutes } = require('./middleware/indexAwareRouter');
const { createRoutes: createContentPriorityRoutes } = require('./middleware/contentPrioritizer');
const { createRoutes: createAdvBudgetRoutes } = require('./middleware/advBudgetAllocator');

// Security middleware (relaxed CSP for dashboard CDN scripts)
app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'self'"],
            scriptSrc: ["'self'", "'unsafe-inline'", "'unsafe-eval'", "https://cdnjs.cloudflare.com"],
            styleSrc: ["'self'", "'unsafe-inline'"],
            imgSrc: ["'self'", "data:"],
            connectSrc: ["'self'", "http://localhost:8000", "http://localhost:3000",
                         process.env.ML_WORKER_URL || "http://albeni-ai-orchestration.railway.internal:8080",
                         "*.railway.internal"]
        }
    }
}));
app.use(cors({
    origin: [
        process.env.DOMAIN_TOFU || 'https://worldofmerino.com',
        process.env.DOMAIN_MOFU || 'https://merinouniversity.com',
        process.env.DOMAIN_BOFU_TECH || 'https://perfectmerinoshirt.com',
        process.env.DOMAIN_BOFU_HERITAGE || 'https://micron-e.com',
        'http://localhost:3000',
        'http://localhost:8000',
        'http://localhost:8080',
        'https://creative-perfection-production-57b5.up.railway.app',
        /\.hostingersite\.com$/
    ],
    credentials: true
}));

// Rate limiting
const limiter = rateLimit({
    windowMs: 1 * 60 * 1000, // 1 minute
    max: 200, // 200 requests per minute per IP
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: 'Too many requests, please try again later.' }
});
app.use('/v1/', limiter);

// Body parsing
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: true }));

// Logging
app.use(morgan('combined'));

// Bot protection (Pay-as-you-crawl)
app.use(botProtection);

// C2PA metadata injection for served assets
app.use('/assets', c2paMiddleware);

// --- Routes ---

// Health check
app.get('/health', (req, res) => {
    const redis = require('./utils/redis');
    const redisStatus = redis.getClient().status === 'ready' ? 'healthy' : 'connecting';

    res.json({
        status: 'healthy',
        service: 'ai-router',
        version: '1.0.0',
        uptime: process.uptime(),
        redis: redisStatus,
        timestamp: new Date().toISOString()
    });
});

// API Routes
app.use('/v1/track', trackingRoutes);
app.use('/v1/router', routerRoutes);
app.use('/v1/crm', crmRoutes);

// Index-Aware Cross-Domain Router (GSC crawl map fallback)
// Must be BEFORE the ML Worker catch-all proxy at app.all('/v1/*')
const dashboardPath_early = process.env.DASHBOARD_PATH || path.join(__dirname, 'dashboard');
app.use('/v1/router', createIndexRoutes(dashboardPath_early));

// Serve static files from dashboard folder (JS snippets, JSON, etc.)
// Railway: dashboard is at /app/dashboard (copied during build)
// Docker-compose: dashboard is mounted at /app/dashboard
const dashboardPath = process.env.DASHBOARD_PATH || path.join(__dirname, 'dashboard');
app.use('/v1/content/priorities', createContentPriorityRoutes(dashboardPath));
app.use('/v1/adv', createAdvBudgetRoutes(dashboardPath));
// Only these files are meant to be world-readable: the Layer 1 tracking scripts
// injected into the WordPress sites (they need CORS *) and the dashboard shell.
// Everything else in this folder is internal data — crawl maps read by
// indexAwareRouter/contentPrioritizer, adv_transitions.json written by
// advBudgetAllocator, legacy dumps — and must stay off the public surface.
// Allowlist, not denylist: a new file dropped in here is private by default.
const PUBLIC_DASHBOARD_FILES = new Set([
    'index.html',
    'albeni-ai-tracker.js',
    'albeni-behavioral-engine.js',
    'albeni-unified-tracker.js',
    'content-lake-multilingual.js',
]);

const dashboardStatic = express.static(dashboardPath, {
    setHeaders: (res, filePath) => {
        if (filePath.endsWith('.js')) {
            res.setHeader('Access-Control-Allow-Origin', '*');
            res.setHeader('Content-Type', 'application/javascript');
        }
    }
});

app.use((req, res, next) => {
    // path.basename on the decoded path: anything not explicitly public falls
    // through to the /v1 routes and, failing those, to a 404.
    let name;
    try {
        name = path.basename(decodeURIComponent(req.path));
    } catch (e) {
        return next(); // malformed percent-encoding — never reaches the disk
    }
    if (!PUBLIC_DASHBOARD_FILES.has(name)) return next();
    return dashboardStatic(req, res, next);
});

// Dashboard - serve the HTML file
app.get('/', (req, res) => {
    res.sendFile(path.join(dashboardPath, 'index.html'));
});
app.get('/dashboard', (req, res) => {
    res.sendFile(path.join(dashboardPath, 'index.html'));
});

// Content Library API — RIMOSSA il 28/07/2026.
// Serviva content_library.json (dump di marzo) senza auth. Nessun lettore: la
// pagina Content Lake della dashboard legge /v1/content/lake dal Postgres via
// ML Worker, non questo file. L'archivio è stato spostato in ai-router/data/,
// fuori dall'albero servito da express.static.

// --- GSC Indexing Monitor API ---
// MIGRATED 2026-05-14 to ml-worker Python + Postgres for persistence.
// Old filesystem-based handlers (gsc_data.json) lost scans on every Railway deploy.
// New endpoints: ml-worker/main.py — GET /v1/gsc/history + POST /v1/gsc/report.
// Requests now fall through to the generic /v1/* proxy below (line ~218).

// --- ML Worker Proxy ---
// Forward all /v1/* requests not handled above to the ML Worker (Python FastAPI)
// The ML Worker is internal-only on Railway (not publicly accessible)
const axios = require('axios');
const ML_WORKER_URL = process.env.ML_WORKER_URL || 'http://albeni-ai-orchestration.railway.internal:8080';

app.all('/v1/*', async (req, res) => {
    const targetUrl = `${ML_WORKER_URL}${req.originalUrl}`;
    try {
        const axiosConfig = {
            method: req.method.toLowerCase(),
            url: targetUrl,
            headers: {
                ...req.headers,
                host: undefined, // let axios set the correct host
                'x-forwarded-for': req.ip,
                'x-forwarded-proto': req.protocol
            },
            // Fix P0.2 follow-up (2026-05-12): /v1/content/validate ora chiama
            // anche Gemini second-pass (validate_with_ai) che può impiegare
            // 30-90s (Gemini sync + time.sleep(2) buffer + Data Hub query DB).
            // Default 120s per coprire i worst case. Override via env
            // AI_ROUTER_PROXY_TIMEOUT_MS. Smoke test fast: usare
            // skip_ai_validation=true nel body per saltare il second-pass.
            timeout: parseInt(process.env.AI_ROUTER_PROXY_TIMEOUT_MS || '120000', 10),
            validateStatus: () => true // forward all status codes as-is
        };

        // Forward body for POST/PUT/PATCH
        if (['POST', 'PUT', 'PATCH'].includes(req.method) && req.body) {
            axiosConfig.data = req.body;
        }

        // Forward query params
        if (Object.keys(req.query).length > 0) {
            axiosConfig.params = req.query;
        }

        const mlResponse = await axios(axiosConfig);

        // Forward response headers (skip hop-by-hop)
        const skipHeaders = ['transfer-encoding', 'connection', 'keep-alive'];
        Object.entries(mlResponse.headers).forEach(([key, value]) => {
            if (!skipHeaders.includes(key.toLowerCase())) {
                res.setHeader(key, value);
            }
        });

        res.status(mlResponse.status).send(mlResponse.data);
    } catch (error) {
        console.error(`[ML Proxy] ${req.method} ${req.originalUrl} -> ${targetUrl} FAILED:`, error.message);
        if (error.code === 'ECONNREFUSED') {
            res.status(503).json({
                error: 'ML Worker unavailable',
                detail: 'The Python FastAPI backend is not responding. Check Railway deployment.',
                target: targetUrl
            });
        } else if (error.code === 'ETIMEDOUT') {
            const timeoutSec = Math.round(parseInt(process.env.AI_ROUTER_PROXY_TIMEOUT_MS || '60000', 10) / 1000);
            res.status(504).json({
                error: 'ML Worker timeout',
                detail: `The request took longer than ${timeoutSec} seconds.`,
                target: targetUrl
            });
        } else {
            res.status(502).json({
                error: 'ML Worker proxy error',
                detail: error.message,
                target: targetUrl
            });
        }
    }
});

// Also proxy the widget.js endpoint from ML Worker
app.get('/widget.js', async (req, res) => {
    try {
        const mlResponse = await axios.get(`${ML_WORKER_URL}/widget.js`, { timeout: 5000 });
        res.setHeader('Content-Type', 'application/javascript');
        res.setHeader('Access-Control-Allow-Origin', '*');
        res.send(mlResponse.data);
    } catch (error) {
        res.status(502).send('// Widget unavailable - ML Worker not responding');
    }
});

// 404 handler (only for non /v1/ routes)
app.use((req, res) => {
    res.status(404).json({ error: 'Endpoint not found' });
});

// Error handler
app.use((err, req, res, next) => {
    console.error('Unhandled error:', err);
    res.status(500).json({ error: 'Internal server error' });
});

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`🚀 AI Router active on port ${PORT}`);
    console.log(`   Environment: ${process.env.NODE_ENV || 'development'}`);
    console.log(`   ML Worker: ${process.env.ML_WORKER_URL || 'http://albeni-ai-orchestration.railway.internal:8080'}`);
});

module.exports = app;
