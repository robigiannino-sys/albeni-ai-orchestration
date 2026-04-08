/**
 * AI Router - Node.js Express Server
 * Albeni 1905 - AI Orchestration Layer
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

// Security middleware (relaxed CSP for dashboard CDN scripts)
app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'self'"],
            scriptSrc: ["'self'", "'unsafe-inline'", "'unsafe-eval'", "https://cdnjs.cloudflare.com"],
            styleSrc: ["'self'", "'unsafe-inline'"],
            imgSrc: ["'self'", "data:"],
            connectSrc: ["'self'", "http://localhost:8000", "http://localhost:3000",
                         process.env.ML_WORKER_URL || "http://albeni-ai-orchestration.railway.internal:8000",
                         "*.railway.internal"]
        }
    }
}));
app.use(cors({
    origin: [
        process.env.DOMAIN_TOFU || 'https://worldofmerino.com',
        process.env.DOMAIN_MOFU || 'https://merinouniversity.com',
        process.env.DOMAIN_BOFU_TECH || 'https://perfectmerinoshirt.com',
        process.env.DOMAIN_BOFU_HERITAGE || 'https://albeni1905.com',
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

// Serve static files from dashboard folder (JS snippets, JSON, etc.)
// Railway: dashboard is at /app/dashboard (copied during build)
// Docker-compose: dashboard is mounted at /app/dashboard
const dashboardPath = process.env.DASHBOARD_PATH || path.join(__dirname, 'dashboard');
app.use(express.static(dashboardPath, {
    setHeaders: (res, filePath) => {
        if (filePath.endsWith('.js')) {
            res.setHeader('Access-Control-Allow-Origin', '*');
            res.setHeader('Content-Type', 'application/javascript');
        }
    }
}));

// Dashboard - serve the HTML file
app.get('/', (req, res) => {
    res.sendFile(path.join(dashboardPath, 'index.html'));
});
app.get('/dashboard', (req, res) => {
    res.sendFile(path.join(dashboardPath, 'index.html'));
});

// Content Library API - serve the JSON database
app.get('/v1/content-library', (req, res) => {
    const fs = require('fs');
    const dbPath = path.join(dashboardPath, 'content_library.json');
    try {
        const raw = fs.readFileSync(dbPath, 'utf8');
        const db = JSON.parse(raw);
        // Optional filters via query params
        const { cat, search, limit } = req.query;
        let items = db.contents || [];
        if (cat && cat !== 'all') items = items.filter(i => i.category === cat);
        if (search) {
            const q = search.toLowerCase();
            items = items.filter(i =>
                (i.title||'').toLowerCase().includes(q) ||
                (i.summary||'').toLowerCase().includes(q) ||
                (i.body||'').toLowerCase().includes(q) ||
                (i.tags||[]).some(t => t.toLowerCase().includes(q))
            );
        }
        if (limit) items = items.slice(0, parseInt(limit));
        res.json({ ...db, contents: items, filtered_count: items.length });
    } catch (e) {
        res.status(404).json({ error: 'content_library.json not found', detail: e.message });
    }
});

// --- ML Worker Proxy ---
// Forward all /v1/* requests not handled above to the ML Worker (Python FastAPI)
// The ML Worker is internal-only on Railway (not publicly accessible)
const axios = require('axios');
const ML_WORKER_URL = process.env.ML_WORKER_URL || 'http://albeni-ai-orchestration.railway.internal:8000';

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
            timeout: 30000, // 30s timeout for AI operations
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
            res.status(504).json({
                error: 'ML Worker timeout',
                detail: 'The request took longer than 30 seconds.',
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
    console.log(`   ML Worker: ${process.env.ML_WORKER_URL || 'http://albeni-ai-orchestration.railway.internal:8000'}`);
});

module.exports = app;
