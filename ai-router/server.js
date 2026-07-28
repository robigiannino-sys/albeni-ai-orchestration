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

// --- Controllo accessi della tower ---------------------------------------
// Dallo stesso host escono due cose molto diverse: una API di ingestion che i
// browser dei visitatori chiamano sui 4 domini WordPress (deve restare aperta,
// non ha credenziali) e un cruscotto interno con i dati operativi. Fino al
// 28/07/2026 era aperto tutto, e la dashboard portava in chiaro la API_KEY di
// scrittura: chiunque aprisse la pagina poteva riscrivere il budget ADV.
//
// Regola: default-deny. Passano senza credenziali solo le famiglie che il
// frontend pubblico chiama davvero — enumerate dai tracker in dashboard/*.js e
// dagli snippet in wp-snippets/. Tutto il resto vuole la API_KEY (script e
// server-to-server) oppure Basic auth (browser).
const { safeEqual, requestHasValidApiKey } = require('./utils/apiKey');

const PUBLIC_API_PREFIXES = [
    '/v1/track/',           // ingestion eventi comportamentali
    '/v1/intent/',          // calcolo IDS lato client
    '/v1/cluster/',         // cluster prediction
    '/v1/crm/',             // sync-lead dai form
    '/v1/cro/',             // widget CRO sui siti WP
    '/v1/cro-conversion',   // proxy conversioni (snippet WP)
    '/v1/chat/',            // chatbot customer service
    '/v1/adv/route',        // routing ADV
    '/v1/adv/shield/',      // bot shield
    '/v1/router/assign',    // assegnazione dominio cross-site
    '/v1/router/status',
];

function hasValidBasicAuth(req) {
    const user = process.env.DASHBOARD_USER;
    const pass = process.env.DASHBOARD_PASSWORD;
    if (!user || !pass) return false;
    const header = req.headers.authorization || '';
    if (!header.startsWith('Basic ')) return false;
    let decoded;
    try {
        decoded = Buffer.from(header.slice(6), 'base64').toString('utf8');
    } catch (e) {
        return false;
    }
    const sep = decoded.indexOf(':');
    if (sep < 0) return false;
    return safeEqual(decoded.slice(0, sep), user) && safeEqual(decoded.slice(sep + 1), pass);
}

// I file davvero pubblici della cartella dashboard: gli script Layer 1
// iniettati sui siti WordPress. index.html non e' piu' qui — il cruscotto
// adesso sta dietro autenticazione.
const PUBLIC_DASHBOARD_FILES = new Set([
    'albeni-ai-tracker.js',
    'albeni-behavioral-engine.js',
    'albeni-unified-tracker.js',
    'content-lake-multilingual.js',
]);

app.use((req, res, next) => {
    let name;
    try {
        name = path.basename(decodeURIComponent(req.path));
    } catch (e) {
        return res.status(400).json({ error: 'Bad request' });
    }
    if (PUBLIC_DASHBOARD_FILES.has(name)) return next();
    if (PUBLIC_API_PREFIXES.some(p => req.path === p || req.path.startsWith(p))) return next();
    if (requestHasValidApiKey(req) || hasValidBasicAuth(req)) return next();

    res.set('WWW-Authenticate', 'Basic realm="micron-e Control Tower", charset="UTF-8"');
    return res.status(401).json({ error: 'Unauthorized' });
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
// Quali file di questa cartella express.static puo' materializzare: i tracker
// pubblici piu' lo shell della dashboard, che a questo punto ha gia' superato
// il controllo accessi qui sopra. Tutto il resto e' dato interno — crawl map
// lette da indexAwareRouter/contentPrioritizer, adv_transitions.json scritto a
// runtime da advBudgetAllocator, dump legacy — e non passa da qui nemmeno per
// un utente autenticato. Allowlist e non denylist: un file nuovo lasciato
// cadere in questa cartella nasce privato.
const STATIC_SERVABLE_FILES = new Set([
    'index.html',
    ...PUBLIC_DASHBOARD_FILES,
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
    let name;
    try {
        name = path.basename(decodeURIComponent(req.path));
    } catch (e) {
        return next(); // percent-encoding malformato — non tocca mai il disco
    }
    if (!STATIC_SERVABLE_FILES.has(name)) return next();
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

// Header che descrivono *questa* connessione o l'incarto del body del client, e
// che quindi non possono viaggiare su una connessione diversa con un body
// diverso. Nota su content-length, che e' il motivo per cui esiste questa
// lista: express.json() ha gia' consumato il body e ce lo consegna come
// oggetto; axios lo ri-serializza con JSON.stringify, che e' compatto. Il
// client, se e' Python requests (json=), aveva serializzato con json.dumps,
// che mette uno spazio dopo ogni virgola e ogni due punti. La content-length
// del client descrive quindi piu' byte di quanti ne mandiamo noi, e axios
// (setContentLength(len, false) — il false vuol dire "non sovrascrivere se
// c'e' gia'") si guarda bene dal correggerla. Uvicorn resta in attesa dei byte
// mancanti finche' non scade il timeout: la richiesta non fallisce, si pianta.
// E' il guasto che dal 2026-05-14 mandava in timeout ogni POST /v1/gsc/report
// dello scan mensile mentre le GET sulle stesse rotte rispondevano in 100ms.
const HOP_BY_HOP_REQUEST_HEADERS = new Set([
    'host',              // lo ricalcola axios sul target
    'content-length',    // vedi sopra: si riferisce al body del client, non al nostro
    'connection',
    'keep-alive',
    'transfer-encoding',
    'upgrade',
    'te',
    'trailer',
    'expect',            // un 100-continue verso di noi non riguarda ml-worker
    'proxy-authorization',
    'proxy-connection'
]);

// Le rotte che chiamano Gemini in sincrono sono lente per costruzione:
// /v1/content/validate fa il second-pass (validate_with_ai) e puo' impiegare
// 30-90s, /v1/content/generate altrettanto. Tutto il resto e' lettura da
// Postgres o ingestione e deve rispondere in fretta: se non lo fa e' rotto, e
// tenerlo appeso due minuti serve solo a nascondere il guasto a chi chiama.
// Smoke test fast su validate: skip_ai_validation=true nel body.
const SLOW_AI_ROUTE_PREFIXES = ['/v1/content/validate', '/v1/content/generate'];
const PROXY_TIMEOUT_MS = parseInt(process.env.AI_ROUTER_PROXY_TIMEOUT_MS || '20000', 10);
const PROXY_SLOW_TIMEOUT_MS = parseInt(process.env.AI_ROUTER_PROXY_SLOW_TIMEOUT_MS || '120000', 10);

app.all('/v1/*', async (req, res) => {
    const targetUrl = `${ML_WORKER_URL}${req.originalUrl}`;
    const isSlowRoute = SLOW_AI_ROUTE_PREFIXES.some(p => req.path.startsWith(p));
    const timeoutMs = isSlowRoute ? PROXY_SLOW_TIMEOUT_MS : PROXY_TIMEOUT_MS;
    try {
        const forwardedHeaders = {};
        Object.entries(req.headers).forEach(([key, value]) => {
            if (!HOP_BY_HOP_REQUEST_HEADERS.has(key.toLowerCase())) {
                forwardedHeaders[key] = value;
            }
        });
        forwardedHeaders['x-forwarded-for'] = req.ip;
        forwardedHeaders['x-forwarded-proto'] = req.protocol;

        const axiosConfig = {
            method: req.method.toLowerCase(),
            url: targetUrl,
            headers: forwardedHeaders,
            timeout: timeoutMs,
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
        console.error(`[ML Proxy] ${req.method} ${req.originalUrl} -> ${targetUrl} FAILED:`, error.code || '-', error.message);
        if (error.code === 'ECONNREFUSED' || error.code === 'ENOTFOUND' || error.code === 'EAI_AGAIN') {
            res.status(503).json({
                error: 'ML Worker unavailable',
                detail: 'The Python FastAPI backend is not responding. Check Railway deployment.',
                code: error.code,
                target: targetUrl
            });
        // ECONNABORTED e' il codice che axios usa per il *proprio* timeout
        // (ETIMEDOUT arriva solo dal socket di sistema). Prima era gestito solo
        // ETIMEDOUT, quindi il caso di gran lunga piu' frequente — ml-worker che
        // non risponde in tempo — usciva dal ramo generico come 502 "proxy
        // error", che manda a cercare il guasto nel posto sbagliato.
        } else if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
            res.status(504).json({
                error: 'ML Worker timeout',
                detail: `No response from ML Worker within ${Math.round(timeoutMs / 1000)}s.`,
                code: error.code,
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
