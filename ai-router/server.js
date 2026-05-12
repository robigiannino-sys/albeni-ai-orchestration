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

// --- GSC Indexing Monitor API ---
// Stores and serves Google Search Console indexing scan results
app.get('/v1/gsc/history', (req, res) => {
    const fs = require('fs');
    const dbPath = path.join(dashboardPath, 'gsc_data.json');
    try {
        const raw = fs.readFileSync(dbPath, 'utf8');
        const data = JSON.parse(raw);
        const { site } = req.query;
        let scans = data.scans || [];
        if (site) scans = scans.filter(s => s.site === site);
        scans.sort((a, b) => new Date(b.date) - new Date(a.date));
        res.json({ scans, total: scans.length });
    } catch (e) {
        res.status(404).json({ error: 'gsc_data.json not found', detail: e.message });
    }
});

app.post('/v1/gsc/report', (req, res) => {
    const fs = require('fs');
    const dbPath = path.join(dashboardPath, 'gsc_data.json');
    // Simple API key check
    const apiKey = req.headers['x-api-key'] || req.query.api_key;
    if (apiKey !== (process.env.API_KEY || 'albeni-gsc-2026')) {
        return res.status(401).json({ error: 'Unauthorized' });
    }
    try {
        let data = { scans: [] };
        if (fs.existsSync(dbPath)) {
            data = JSON.parse(fs.readFileSync(dbPath, 'utf8'));
        }
        const report = req.body;
        // Validate required fields
        if (!report.site || !report.date || report.total_urls === undefined) {
            return res.status(400).json({ error: 'Missing required fields: site, date, total_urls' });
        }
        // Generate ID
        const siteShort = report.site.includes('merinouniversity') ? 'mu' : 'wom';
        report.id = `${siteShort}-${report.date}`;
        // Replace if same id exists (re-scan same day)
        data.scans = data.scans.filter(s => s.id !== report.id);
        data.scans.push(report);
        data.scans.sort((a, b) => new Date(b.date) - new Date(a.date));
        fs.writeFileSync(dbPath, JSON.stringify(data, null, 2), 'utf8');
        res.json({ status: 'ok', id: report.id, total_scans: data.scans.length });
    } catch (e) {
        res.status(500).json({ error: 'Failed to save report', detail: e.message });
    }
});

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
            // fino a 35s. Override via env AI_ROUTER_PROXY_TIMEOUT_MS se serve
            // più tempo per altri endpoint (es. content/generate batch).
            timeout: parseInt(process.env.AI_ROUTER_PROXY_TIMEOUT_MS || '60000', 10),
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
