/**
 * ============================================================
 * Index-Aware Cross-Domain Router
 * Albeni 1905 â AI Orchestration Layer
 * ============================================================
 *
 * PURPOSE:
 * When the routing engine selects a destination page, this module
 * checks its GSC indexing status via the crawl maps. If the page
 * is NOT indexed (NEUTRAL/ERROR), it looks for an indexed cross-domain
 * equivalent and swaps the destination.
 *
 * LOGIC HIERARCHY:
 *   1. Router picks candidate URL (e.g., MU /dal-vello-al-capo)
 *   2. Crawl map says NEUTRAL â page not crawled by Google
 *   3. Equivalence map finds WoM /heritage-archive/... as fallback
 *   4. WoM crawl map says PASS â swap destination
 *   5. If no indexed fallback exists â keep original (helps discovery)
 *
 * This is COMPLEMENTARY to the Semantic Brain interlinking snippets
 * (#2867 MU, #2063 WoM) which prioritize NOT-crawled pages in
 * internal links to boost crawling. The routing layer serves a
 * different purpose: UX + link-sharing coherence for real visitors.
 *
 * IMPORTANT DISTINCTION:
 *   - Interlinking (on-page): NOT-crawled FIRST â SEO crawl boost
 *   - User routing (this):    INDEXED preferred â UX quality
 *
 * DATA SOURCES:
 *   - gsc_data.json (dashboard/) â scan history
 *   - mu_crawl_map / wom_crawl_map â URLâverdict maps
 *     (loaded from dashboard/ or fetched from WP options via API)
 *
 * @version 1.0.0
 * @date 2026-04-10
 */

const fs = require('fs');
const path = require('path');

// ============================================================
// CROSS-DOMAIN EQUIVALENCE MAP
// ============================================================
// Maps MU IT page slugs â WoM IT equivalent slugs.
// The router resolves language variants via Polylang-style prefixes.
//
// Structure: { mu_path: wom_path }
// Both paths are IT (default language), language prefixes are
// resolved dynamically by the resolve() function.
//
// NOTE: This is topic-level equivalence, not 1:1 page mapping.
// A MU educational page maps to the WoM editorial page covering
// the same behavioral cluster topic.
// ============================================================

const CROSS_DOMAIN_MAP = {
  // === Cluster A: Material Science â Heritage Archive (material culture) ===
  '/department-material-science':        '/heritage-archive',
  '/struttura-cheratina-2':              '/heritage-archive/lana-merino-guida-completa',
  '/termoregolazione-attiva-merino':     '/heritage-archive/il-primo-strato-tocca-la-pelle',
  '/17-micron-gold-standard-comfort-assoluto': '/heritage-archive/il-comfort-come-asset',
  '/cotone-vs-merino-superfine':         '/sostenibilita-oltre-le-promesse/armadio-che-funziona',
  '/esperienza-sensoriale-merino-17-micron': '/heritage-archive/il-comfort-come-asset',
  '/gsm-decoded':                        '/sostenibilita-oltre-le-promesse/scegliere-tshirt-premium-6-segnali-qualita',
  '/lca-impronta-ambientale-merino':     '/sostenibilita-oltre-le-promesse/meno-capi-zero-sensi-di-colpa',

  // === Cluster B: Construction & Design â Professionals/Heritage ===
  '/department-construction':            '/professionisti-in-movimento',
  '/construction':                       '/professionisti-in-movimento/layering-intelligente-2-strati-invece-di-4',
  '/construction/artigianalita-italiana-ingegneria-sartoriale': '/manifattura-italiana-t-shirt-eccellenza-invisibile',
  '/physics-of-performance':             '/professionisti-in-movimento/travel-stability',

  // === Cluster C: Ethical Origins â Sustainability Beyond Promises ===
  '/department-ethical-origins':          '/sostenibilita-oltre-le-promesse',
  '/ethical-origins':                    '/sostenibilita-oltre-le-promesse',
  '/ethical-origins/zq-protocol':        '/sostenibilita-oltre-le-promesse/meno-capi-zero-sensi-di-colpa',
  '/governance':                         '/sostenibilita-oltre-le-promesse',
  '/global-governance-standards':        '/sostenibilita-oltre-le-promesse',
  '/dal-vello-al-capo':                  '/heritage-archive/lana-merino-guida-completa',

  // === Cluster D: Innovation â Heritage/Sustainability ===
  '/department-innovation':              '/tessuti-italiani-pregiati-cultura-materiale',
  '/plasma-technology':                  '/tessuti-italiani-pregiati-cultura-materiale',
  '/plasma-treatment-evoluzione-anti-restringimento': '/tessuti-italiani-pregiati-cultura-materiale',

  // === Cluster E: Practical Lab â Professionals + Sustainability ===
  '/department-practical-lab':           '/professionisti-in-movimento',
  '/cost-per-wear':                      '/sostenibilita-oltre-le-promesse/cost-per-wear-calculator',
  '/guida-costo-per-utilizzo':           '/investire-nel-vestire-formula-costo-per-utilizzo',
  '/science-of-maintenance':             '/sostenibilita-oltre-le-promesse/manutenzione-no-stiro',
  '/department-practical-lab/guida-scientifica-guardaroba-capsula': '/professionisti-in-movimento/il-guardaroba-capsula-funziona-davvero',
  '/department-practical-lab/business-travel-capsule-merino': '/professionisti-in-movimento/travel-light-checklist',
  '/department-practical-lab/guida-150g-190g-grammatura-merino': '/sostenibilita-oltre-le-promesse/scegliere-tshirt-premium-6-segnali-qualita',
  '/department-practical-lab/filiera-merino-italiano-dal-grezzo-al-capo': '/heritage-archive/lana-merino-guida-completa',

  // === Cluster F: Governance/Heritage â Heritage Archive ===
  '/heritage-archive':                   '/heritage-archive',
  '/heritage-philosophy':                '/heritage-archive',
  '/manifesto':                          '/chi-siamo',
  '/redazione':                          '/redazione',

  // === Landing Pages â Collection hubs ===
  '/lp-b-performance-merino':            '/professionisti-in-movimento',
  '/lp-c-business-merino':               '/professionisti-in-movimento',
  '/department-ethical-origins/lp-a-heritage-merino': '/heritage-archive',

  // === Checklists â Related content ===
  '/department-practical-lab/checklist-qualita-heritage-merino':     '/heritage-archive/il-comfort-come-asset',
  '/department-practical-lab/checklist-viaggio-intelligente-merino': '/professionisti-in-movimento/travel-light-checklist',
  '/department-practical-lab/checklist-layering-professionale-merino': '/professionisti-in-movimento/layering-intelligente-2-strati-invece-di-4',
  '/department-practical-lab/checklist-sensoriale-qualita-tessile':  '/heritage-archive/il-comfort-come-asset',
  '/department-practical-lab/checklist-sostenibilita-tessile-merino': '/sostenibilita-oltre-le-promesse/meno-capi-zero-sensi-di-colpa',
};

// ============================================================
// LANGUAGE PREFIX MAPS
// ============================================================
// MU uses: /en/en-slug, /de/de-slug, /fr/fr-slug
// WoM uses: /en-us/en-slug, /de/de-slug, /fr/fr-slug

const LANG_PREFIX = {
  mu:  { it: '',    en: '/en',    de: '/de',  fr: '/fr'  },
  wom: { it: '',    en: '/en-us', de: '/de',  fr: '/fr'  },
};

const DOMAIN = {
  mu:  process.env.DOMAIN_MOFU  || 'https://merinouniversity.com',
  wom: process.env.DOMAIN_TOFU  || 'https://worldofmerino.com',
};

// ============================================================
// CRAWL MAP LOADER
// ============================================================

class CrawlMapStore {
  constructor(dashboardPath) {
    this.dashboardPath = dashboardPath;
    this.maps = { mu: {}, wom: {} };
    this.lastLoad = 0;
    this.TTL = 5 * 60 * 1000; // reload every 5 minutes
  }

  load() {
    const now = Date.now();
    if (now - this.lastLoad < this.TTL) return;

    try {
      const muPath = path.join(this.dashboardPath, 'mu_crawl_map.json');
      const womPath = path.join(this.dashboardPath, 'wom_crawl_map.json');

      if (fs.existsSync(muPath)) {
        this.maps.mu = JSON.parse(fs.readFileSync(muPath, 'utf8'));
      }
      if (fs.existsSync(womPath)) {
        this.maps.wom = JSON.parse(fs.readFileSync(womPath, 'utf8'));
      }
      this.lastLoad = now;
      console.log(`[IndexRouter] Crawl maps loaded: MU ${Object.keys(this.maps.mu).length} URLs, WoM ${Object.keys(this.maps.wom).length} URLs`);
    } catch (e) {
      console.error('[IndexRouter] Failed to load crawl maps:', e.message);
    }
  }

  getVerdict(site, urlPath) {
    this.load();
    const map = this.maps[site] || {};
    // Try exact match, then with/without trailing slash
    const clean = urlPath.replace(/\/$/, '') || '/';
    return map[clean] || map[clean + '/'] || 'UNKNOWN';
  }

  isIndexed(site, urlPath) {
    return this.getVerdict(site, urlPath) === 'PASS';
  }

  getStats() {
    this.load();
    const stats = {};
    for (const site of ['mu', 'wom']) {
      const map = this.maps[site];
      const total = Object.keys(map).length;
      const indexed = Object.values(map).filter(v => v === 'PASS').length;
      stats[site] = { total, indexed, rate: total > 0 ? (indexed / total * 100).toFixed(1) : '0.0' };
    }
    return stats;
  }
}

// ============================================================
// LANGUAGE DETECTION
// ============================================================

function detectLanguage(urlPath) {
  if (urlPath.startsWith('/en-us/') || urlPath.startsWith('/en/')) return 'en';
  if (urlPath.startsWith('/de/')) return 'de';
  if (urlPath.startsWith('/fr/')) return 'fr';
  return 'it';
}

function detectSite(url) {
  if (url.includes('merinouniversity')) return 'mu';
  if (url.includes('worldofmerino'))    return 'wom';
  if (url.includes('perfectmerino'))    return 'pms';
  if (url.includes('albeni1905'))       return 'albeni';
  return null;
}

// ============================================================
// STRIP LANGUAGE PREFIX â GET IT BASE SLUG
// ============================================================
// MU: /en/en-architecture-of-fit â /architecture-of-fit (approx)
// WoM: /en-us/en-heritage-archive â /heritage-archive (approx)
//
// For the equivalence map, we only need the IT slug since the map
// is keyed by IT paths. Language-specific routing is handled
// separately when building the fallback URL.

function stripToItSlug(urlPath, site) {
  // Remove language prefix
  let slug = urlPath;
  if (site === 'wom') {
    slug = slug.replace(/^\/en-us\//, '/').replace(/^\/de\//, '/').replace(/^\/fr\//, '/');
  } else {
    slug = slug.replace(/^\/en\//, '/').replace(/^\/de\//, '/').replace(/^\/fr\//, '/');
  }
  // Remove language prefix from slug itself (e.g., en-architecture â architecture)
  slug = slug.replace(/^\/(en|de|fr)-/, '/');
  return slug;
}

// ============================================================
// RESOLVE: THE MAIN ROUTING FUNCTION
// ============================================================
/**
 * Given a candidate URL, check indexing status and return
 * the best destination (original or cross-domain fallback).
 *
 * @param {string} candidateUrl - Full URL (e.g., https://merinouniversity.com/en/en-cost-per-wear)
 * @param {CrawlMapStore} store - Crawl map store instance
 * @returns {Object} { url, swapped, reason, original, verdict, fallbackVerdict }
 */
function resolve(candidateUrl, store) {
  const urlObj = new URL(candidateUrl);
  const urlPath = urlObj.pathname.replace(/\/$/, '') || '/';
  const site = detectSite(candidateUrl);
  const lang = detectLanguage(urlPath);

  const result = {
    url: candidateUrl,
    swapped: false,
    reason: null,
    original: candidateUrl,
    site,
    lang,
    verdict: 'UNKNOWN',
    fallbackVerdict: null,
  };

  if (!site || !['mu', 'wom'].includes(site)) {
    result.reason = 'not_applicable_domain';
    return result;
  }

  // Step 1: Check if candidate is already indexed
  const verdict = store.getVerdict(site, urlPath);
  result.verdict = verdict;

  if (verdict === 'PASS') {
    result.reason = 'already_indexed';
    return result;
  }

  // Step 2: Page is NOT indexed â look for cross-domain fallback
  const targetSite = site === 'mu' ? 'wom' : 'mu';
  const itSlug = stripToItSlug(urlPath, site);

  // Look up in equivalence map (keyed by MU IT slugs)
  let fallbackItSlug = null;
  if (site === 'mu') {
    fallbackItSlug = CROSS_DOMAIN_MAP[itSlug];
  } else {
    // Reverse lookup: WoM â MU (less common but supported)
    const reverseEntry = Object.entries(CROSS_DOMAIN_MAP).find(([mu, wom]) => wom === itSlug);
    if (reverseEntry) fallbackItSlug = reverseEntry[0];
  }

  if (!fallbackItSlug) {
    result.reason = 'no_cross_domain_equivalent';
    return result;
  }

  // Step 3: Build the fallback URL with correct language prefix
  const prefix = LANG_PREFIX[targetSite][lang] || '';
  // For non-IT languages, WoM and MU add lang prefix to slug too
  let langSlug = fallbackItSlug;
  if (lang !== 'it') {
    // WoM/MU convention: /de/de-slug, /en/en-slug, etc.
    // But many WoM IT slugs work as-is in the path structure
    // We check the crawl map for both variants
    const variants = [
      `${prefix}${fallbackItSlug}`,
      `${prefix}/${lang}-${fallbackItSlug.replace(/^\//, '')}`,
      `${prefix}/${lang}${fallbackItSlug}`,
    ];

    // Find the first variant that's indexed
    let bestVariant = null;
    let bestVerdict = null;

    for (const v of variants) {
      const verd = store.getVerdict(targetSite, v);
      if (verd === 'PASS') {
        bestVariant = v;
        bestVerdict = verd;
        break;
      }
      // Track any variant that exists in the map at all
      if (verd !== 'UNKNOWN' && !bestVariant) {
        bestVariant = v;
        bestVerdict = verd;
      }
    }

    if (bestVariant && bestVerdict === 'PASS') {
      langSlug = bestVariant;
    } else {
      // No indexed variant found in target domain either
      result.reason = 'fallback_also_not_indexed';
      result.fallbackVerdict = bestVerdict;
      return result;
    }
  } else {
    // IT: check if the fallback IT path is indexed
    const fallbackVerdict = store.getVerdict(targetSite, fallbackItSlug);
    if (fallbackVerdict !== 'PASS') {
      result.reason = 'fallback_also_not_indexed';
      result.fallbackVerdict = fallbackVerdict;
      return result;
    }
    langSlug = fallbackItSlug;
  }

  // Step 4: Swap!
  const fallbackUrl = `${DOMAIN[targetSite]}${langSlug}`;
  result.url = fallbackUrl;
  result.swapped = true;
  result.reason = 'swapped_to_indexed_equivalent';
  result.fallbackVerdict = 'PASS';

  return result;
}

// ============================================================
// BATCH RESOLVE (for dashboard/analytics)
// ============================================================

function batchResolve(urls, store) {
  return urls.map(url => resolve(url, store));
}

// ============================================================
// EXPRESS ROUTE FACTORY
// ============================================================

function createRoutes(dashboardPath) {
  const express = require('express');
  const router = express.Router();
  const store = new CrawlMapStore(dashboardPath);

  // --- Resolve single URL ---
  // GET /v1/router/resolve?url=https://merinouniversity.com/en/en-cost-per-wear
  router.get('/resolve', (req, res) => {
    const { url } = req.query;
    if (!url) {
      return res.status(400).json({ error: 'Missing required param: url' });
    }
    try {
      const result = resolve(url, store);
      res.json(result);
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  });

  // --- Batch resolve ---
  // POST /v1/router/resolve { urls: [...] }
  router.post('/resolve', (req, res) => {
    const { urls } = req.body;
    if (!Array.isArray(urls) || urls.length === 0) {
      return res.status(400).json({ error: 'Body must contain urls array' });
    }
    if (urls.length > 100) {
      return res.status(400).json({ error: 'Max 100 URLs per batch' });
    }
    try {
      const results = batchResolve(urls, store);
      const swapped = results.filter(r => r.swapped).length;
      res.json({
        results,
        summary: {
          total: results.length,
          swapped,
          kept: results.length - swapped,
        }
      });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  });

  // --- Crawl map stats ---
  // GET /v1/router/index-stats
  router.get('/index-stats', (req, res) => {
    const stats = store.getStats();
    res.json({
      ...stats,
      equivalence_map_size: Object.keys(CROSS_DOMAIN_MAP).length,
      last_load: store.lastLoad ? new Date(store.lastLoad).toISOString() : null,
    });
  });

  // --- Dry-run simulation ---
  // GET /v1/router/simulate?site=mu&lang=en
  // Returns what would happen for ALL MU pages in that language
  router.get('/simulate', (req, res) => {
    const site = req.query.site || 'mu';
    const lang = req.query.lang || 'it';

    store.load();
    const map = store.maps[site] || {};
    const prefix = LANG_PREFIX[site]?.[lang] || '';

    // Filter URLs for the requested language
    const urls = Object.keys(map)
      .filter(p => {
        if (lang === 'it') return !p.startsWith('/en') && !p.startsWith('/de') && !p.startsWith('/fr');
        return p.startsWith(prefix + '/');
      })
      .map(p => `${DOMAIN[site]}${p}`);

    const results = batchResolve(urls, store);
    const swapped = results.filter(r => r.swapped);
    const notIndexedNoFallback = results.filter(r =>
      r.verdict !== 'PASS' && !r.swapped
    );

    res.json({
      site,
      lang,
      total_urls: results.length,
      already_indexed: results.filter(r => r.verdict === 'PASS').length,
      swapped_to_fallback: swapped.length,
      not_indexed_no_fallback: notIndexedNoFallback.length,
      swapped_details: swapped.map(r => ({
        from: r.original,
        to: r.url,
        reason: r.reason,
      })),
      orphaned: notIndexedNoFallback.map(r => ({
        url: r.original,
        reason: r.reason,
      })),
    });
  });

  // --- Update crawl maps from external source ---
  // POST /v1/router/crawl-maps { mu: {...}, wom: {...} }
  router.post('/crawl-maps', (req, res) => {
    const apiKey = req.headers['x-api-key'] || req.query.api_key;
    if (apiKey !== (process.env.API_KEY || 'albeni-gsc-2026')) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    const { mu, wom } = req.body;
    let updated = [];

    try {
      if (mu && typeof mu === 'object') {
        fs.writeFileSync(
          path.join(dashboardPath, 'mu_crawl_map.json'),
          JSON.stringify(mu, null, 2), 'utf8'
        );
        updated.push('mu');
      }
      if (wom && typeof wom === 'object') {
        fs.writeFileSync(
          path.join(dashboardPath, 'wom_crawl_map.json'),
          JSON.stringify(wom, null, 2), 'utf8'
        );
        updated.push('wom');
      }

      // Force reload on next request
      store.lastLoad = 0;

      res.json({ status: 'ok', updated });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  });

  return router;
}

module.exports = {
  createRoutes,
  resolve,
  batchResolve,
  CrawlMapStore,
  CROSS_DOMAIN_MAP,
  LANG_PREFIX,
  DOMAIN,
};
