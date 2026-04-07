/**
 * Bot Protection Middleware - Pay-as-you-Crawl
 * Implements the Digital Moat strategy:
 *
 * 1. Blocks unauthorized AI training bots (Google-Extended, GPTBot, etc.)
 * 2. Returns HTTP 402 (Payment Required) for unauthorized scrapers
 * 3. Allows legitimate search engine crawlers (Googlebot, Bingbot)
 * 4. Monitors and logs bot activity
 */

// Blocked AI training/scraping bots
const BLOCKED_BOTS = [
    'GPTBot',
    'Google-Extended',
    'CCBot',
    'ClaudeBot',
    'anthropic-ai',
    'ChatGPT-User',
    'Bytespider',
    'Diffbot',
    'FacebookBot',
    'Applebot-Extended',
    'PerplexityBot',
    'YouBot'
];

// Allowed legitimate crawlers (for SEO indexing)
const ALLOWED_BOTS = [
    'Googlebot',
    'Bingbot',
    'Slurp',         // Yahoo
    'DuckDuckBot',
    'Baiduspider',
    'YandexBot'
];

// Rate tracking for suspicious activity
const requestCounts = new Map();

function botProtection(req, res, next) {
    const userAgent = req.headers['user-agent'] || '';
    const ip = req.ip || req.connection.remoteAddress;

    // 1. Check for blocked AI bots
    const isBlockedBot = BLOCKED_BOTS.some(bot =>
        userAgent.toLowerCase().includes(bot.toLowerCase())
    );

    if (isBlockedBot) {
        console.warn(`[BOT_BLOCK] Blocked AI bot: ${userAgent} from ${ip}`);
        return res.status(402).json({
            error: 'Payment Required',
            message: 'Unauthorized AI training/scraping detected. Please contact licensing@albeni1905.com for data access agreements.',
            policy: 'https://albeni1905.com/ai-data-policy',
            bot_detected: userAgent.substring(0, 100)
        });
    }

    // 2. Check for allowed bots (skip rate limiting)
    const isAllowedBot = ALLOWED_BOTS.some(bot =>
        userAgent.toLowerCase().includes(bot.toLowerCase())
    );

    if (isAllowedBot) {
        return next();
    }

    // 3. Rate-based scraper detection (non-bot User-Agents)
    const now = Date.now();
    const windowMs = 60000; // 1 minute window

    if (!requestCounts.has(ip)) {
        requestCounts.set(ip, []);
    }

    const timestamps = requestCounts.get(ip);
    // Clean old entries
    const recent = timestamps.filter(t => now - t < windowMs);
    recent.push(now);
    requestCounts.set(ip, recent);

    // If more than 100 requests per minute from same IP, suspect scraper
    if (recent.length > 100) {
        console.warn(`[RATE_BLOCK] Suspected scraper: ${ip} (${recent.length} req/min)`);
        return res.status(429).json({
            error: 'Too Many Requests',
            message: 'Request rate exceeds acceptable limits. If you are a legitimate service, please contact api@albeni1905.com.'
        });
    }

    // Cleanup old IPs periodically
    if (requestCounts.size > 10000) {
        const cutoff = now - windowMs * 5;
        for (const [key, val] of requestCounts) {
            if (val.length === 0 || val[val.length - 1] < cutoff) {
                requestCounts.delete(key);
            }
        }
    }

    next();
}

module.exports = { botProtection };
