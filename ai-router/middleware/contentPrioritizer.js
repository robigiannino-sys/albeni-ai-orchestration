/**
 * ============================================================
 * Content AI Layer — Generazione Prioritizzata
 * Albeni 1905 — AI Orchestration Layer
 * ============================================================
 *
 * PURPOSE:
 * Integrates GSC indexing data with content generation decisions.
 * When the Content Generator produces new content, this module
 * determines priority based on cluster indexation health:
 *
 *   - HIGH indexation clusters → "amplify" (ROI immediato)
 *     Google already trusts this area; new content gets indexed fast.
 *     Strategy: produce more content to capture adjacent keywords.
 *
 *   - LOW indexation clusters → "support" (boost discovery)
 *     Google hasn't crawled much here; needs internal link support.
 *     Strategy: create hub/pillar content, improve interlinking.
 *
 *   - MEDIUM indexation → "sustain" (maintain momentum)
 *     Cluster is growing; keep feeding it at steady pace.
 *
 * THRESHOLDS:
 *   - HIGH:   ≥60% indexed → amplify (immediate ROI)
 *   - MEDIUM: 20-59% indexed → sustain (growing)
 *   - LOW:    <20% indexed → support (needs crawl boost)
 *
 * DATA SOURCES:
 *   - mu_crawl_map.json / wom_crawl_map.json → per-URL verdicts
 *   - CLUSTER_URL_MAP → URL→cluster assignments
 *   - Content Library → existing content inventory
 *
 * OUTPUTS:
 *   - Per-cluster priority scores with strategy recommendations
 *   - Content generation queue (ordered by expected ROI)
 *   - Gap analysis: clusters with content gaps vs indexation potential
 *
 * @version 1.0.0
 * @date 2026-04-10
 */

const fs = require('fs');
const path = require('path');

// ============================================================
// CLUSTER DEFINITIONS
// ============================================================
// Maps behavioral clusters to their thematic URL patterns.
// Each cluster has MU paths (educational) and WoM paths (editorial).
// The engine matches URLs to clusters via prefix/contains matching.

const CLUSTERS = {
  A: {
    id: 'A',
    name: 'Material Science',
    nameIT: 'Scienza dei Materiali',
    behavioral: 'Heritage',
    mu_department: '/department-material-science',
    wom_collection: '/heritage-archive',
    description: 'Fiber properties, keratin structure, thermoregulation, 17-micron standard',
    mu_patterns: [
      '/department-material-science',
      '/struttura-cheratina',
      '/termoregolazione-attiva',
      '/17-micron-gold-standard',
      '/cotone-vs-merino',
      '/esperienza-sensoriale',
      '/gsm-decoded',
      '/lca-impronta-ambientale',
      '/alpha-keratin',
      '/active-thermoregulation',
      '/cotton-vs-merino',
      '/sensory-experience',
      '/gold-standard',
      '/etalon-or-17',
      '/structure-keratine',
      '/thermoregulation-active',
      '/sinneserlebnis',
      '/aktive-thermoregulation',
      '/comfort-assoluto',
    ],
    wom_patterns: [
      '/heritage-archive/lana-merino-guida-completa',
      '/heritage-archive/il-primo-strato',
      '/heritage-archive/il-comfort-come-asset',
      '/heritage-archive/merinowolle-leitfaden',
      '/heritage-archive/merino-wool-complete-guide',
      '/heritage-archive/laine-merinos-guide',
      '/heritage-archive/die-erste-schicht',
      '/heritage-archive/the-first-layer',
      '/heritage-archive/la-premiere-couche',
      '/heritage-archive/komfort-als-asset',
      '/heritage-archive/comfort-as-asset',
      '/heritage-archive/confort-comme-atout',
      '/tessuti-italiani-pregiati',
      '/premium-italian-fabrics',
      '/edle-italienische-stoffe',
      '/tissus-italiens-qualite',
    ],
  },
  B: {
    id: 'B',
    name: 'Construction & Design',
    nameIT: 'Costruzione & Design',
    behavioral: 'Business',
    mu_department: '/department-construction',
    wom_collection: '/professionisti-in-movimento',
    description: 'Architecture of fit, Italian craftsmanship, cut&sewn vs knit, layering',
    mu_patterns: [
      '/department-construction',
      '/construction',
      '/architecture-of-fit',
      '/artigianalita-italiana',
      '/physics-of-performance',
      '/art-of-construction',
      '/italian-craftsmanship',
      '/artisanat-italien',
      '/coupe-cousu',
      '/architektur-der-passform',
    ],
    wom_patterns: [
      '/professionisti-in-movimento/layering-intelligente',
      '/professionisti-in-movimento/travel-stability',
      '/professionisti-in-movimento/smart-layering',
      '/professionisti-in-movimento/intelligentes-layering',
      '/professionisti-in-movimento/layering-intelligent',
      '/manifattura-italiana-t-shirt',
      '/italian-t-shirt-manufacturing',
      '/italienische-t-shirt',
      '/fabrication-italienne',
    ],
  },
  C: {
    id: 'C',
    name: 'Ethical Origins',
    nameIT: 'Origini Etiche',
    behavioral: 'Conscious',
    mu_department: '/department-ethical-origins',
    wom_collection: '/sostenibilita-oltre-le-promesse',
    description: 'ZQ protocol, governance, LCA, sustainability, supply chain traceability',
    mu_patterns: [
      '/department-ethical-origins',
      '/ethical-origins',
      '/governance',
      '/global-governance',
      '/dal-vello-al-capo',
      '/sostenibilita-merino',
      '/lca-',
      '/zq-protocol',
      '/zq-protokoll',
      '/origines-ethiques',
      '/origine-ethique',
      '/durabilite-merinos',
      '/nachhaltigkeit',
      '/sustainability',
      '/from-fleece-to-garment',
      '/vom-vlies-zum',
      '/de-la-toison',
    ],
    wom_patterns: [
      '/sostenibilita-oltre-le-promesse',
      '/sustainability-beyond-promises',
      '/nachhaltigkeit-jenseits',
      '/durabilite-au-dela',
      '/meno-capi-zero-sensi',
      '/fewer-pieces-zero-guilt',
      '/weniger-teile-null',
      '/moins-de-pieces-zero',
      '/armadio-che-funziona',
      '/wardrobe-that-works',
      '/kleiderschrank-der-funktioniert',
      '/garde-robe-qui-fonctionne',
      '/cost-per-wear',
      '/kosten-pro-nutzung',
      '/cout-par-port',
      '/pelle-sensibile',
      '/sensitive-skin',
      '/empfindliche-haut',
      '/peau-sensible',
    ],
  },
  D: {
    id: 'D',
    name: 'Innovation',
    nameIT: 'Innovazione',
    behavioral: 'Performance Athletes',
    mu_department: '/department-innovation',
    wom_collection: null, // mapped to tessuti-italiani / heritage-archive
    description: 'Plasma technology, compact treatment, anti-shrinkage evolution',
    mu_patterns: [
      '/department-innovation',
      '/plasma-tech',
      '/plasma-treatment',
      '/compact-technologie',
      '/compact-technology',
      '/technologie-compact',
      '/plasmabehandlung',
      '/traitement-plasma',
      '/innovation',
    ],
    wom_patterns: [
      // Innovation content on WoM maps to material culture / heritage
      '/tessuti-italiani-pregiati-cultura-materiale',
      '/premium-italian-fabrics-material-culture',
      '/edle-italienische-stoffe-materialkultur',
      '/tissus-italiens-qualite-culture-materielle',
    ],
  },
  E: {
    id: 'E',
    name: 'Practical Lab',
    nameIT: 'Laboratorio Pratico',
    behavioral: 'Outdoor Enthusiasts',
    mu_department: '/department-practical-lab',
    wom_collection: '/professionisti-in-movimento',
    description: 'Cost-per-wear, capsule wardrobe, business travel, GSM guide, maintenance',
    mu_patterns: [
      '/department-practical-lab',
      '/cost-per-wear',
      '/guida-costo-per-utilizzo',
      '/science-of-maintenance',
      '/guardaroba-capsula',
      '/capsule-wardrobe',
      '/kapselgarderobe',
      '/garde-robe-capsule',
      '/business-travel-capsule',
      '/150g-190g',
      '/grammatura-merino',
      '/merino-weight',
      '/grammage',
      '/gewicht-ratgeber',
      '/filiera-merino',
      '/supply-chain',
      '/lieferkette',
      '/filiere-italienne',
      '/checklist-',
      '/checkliste-',
    ],
    wom_patterns: [
      '/professionisti-in-movimento/travel-light-checklist',
      '/professionisti-in-movimento/il-guardaroba-capsula',
      '/professionisti-in-movimento/capsule-wardrobe',
      '/professionisti-in-movimento/kapselgarderobe',
      '/professionisti-in-movimento/garde-robe-capsule',
      '/professionisti-in-movimento/one-bag',
      '/professionisti-in-movimento/dal-desk-al-trail',
      '/professionisti-in-movimento/desk-to-trail',
      '/professionisti-in-movimento/du-bureau-au-sentier',
      '/professionisti-in-movimento/dal-volo-alla-riunione',
      '/professionisti-in-movimento/from-flight',
      '/professionisti-in-movimento/du-vol-a-la-reunion',
      '/professionisti-in-movimento/vom-flug-zum-meeting',
      '/professionisti-in-movimento/vom-schreibtisch',
      '/scegliere-tshirt-premium',
      '/choose-premium-tshirt',
      '/premium-tshirt-auswaehlen',
      '/choisir-tshirt-premium',
      '/manutenzione-no-stiro',
      '/no-iron-guide',
      '/ratgeber-buegellos',
      '/sans-repassage',
      '/investire-nel-vestire',
      '/investment-dressing',
    ],
  },
  F: {
    id: 'F',
    name: 'Heritage & Brand',
    nameIT: 'Heritage & Brand',
    behavioral: 'Heritage',
    mu_department: null,
    wom_collection: '/heritage-archive',
    description: 'Brand philosophy, manifesto, editorial team, heritage archive hub',
    mu_patterns: [
      '/heritage-archive',
      '/heritage-philosophy',
      '/manifesto',
      '/redazione',
      '/research-library',
      '/eleganza-matura',
      '/essenzialismo-tessile',
      '/lp-b-performance',
      '/lp-c-business',
      '/lp-a-heritage',
      '/merino-business-performance',
      '/merino-viaggio-performance',
      '/layering-professionale',
    ],
    wom_patterns: [
      '/heritage-archive',
      '/chi-siamo',
      '/about-us',
      '/ueber-uns',
      '/a-propos-de-nous',
      '/redazione',
      '/editorial-team',
      '/redaktion',
      '/redaction',
      '/storie',
      '/stories',
      '/geschichten',
      '/histoires',
      '/field-note/',
      '/note-di-campo',
      '/field-notes',
      '/feldnotizen',
      '/notes-de-terrain',
      '/guide',
      '/guides',
      '/ratgeber',
      '/lead-magnet',
    ],
  },
};

// ============================================================
// LANGUAGE DETECTION (shared with indexAwareRouter)
// ============================================================

function detectLanguage(urlPath) {
  if (urlPath.startsWith('/en-us/') || urlPath.startsWith('/en/')) return 'en';
  if (urlPath.startsWith('/de/')) return 'de';
  if (urlPath.startsWith('/fr/')) return 'fr';
  return 'it';
}

function stripLangPrefix(urlPath) {
  return urlPath
    .replace(/^\/en-us\//, '/')
    .replace(/^\/en\//, '/')
    .replace(/^\/de\//, '/')
    .replace(/^\/fr\//, '/')
    .replace(/^\/(en|de|fr)-/, '/');
}

// ============================================================
// URL → CLUSTER CLASSIFIER
// ============================================================
/**
 * Assigns a URL to a cluster based on pattern matching.
 * Returns cluster ID (A-F) or 'uncategorized'.
 */
function classifyUrl(urlPath, site) {
  const clean = stripLangPrefix(urlPath.replace(/\/$/, '') || '/');

  for (const [id, cluster] of Object.entries(CLUSTERS)) {
    const patterns = site === 'mu' ? cluster.mu_patterns : cluster.wom_patterns;
    for (const pattern of patterns) {
      if (clean === pattern || clean.startsWith(pattern + '/') || clean.includes(pattern)) {
        return id;
      }
    }
  }

  // Fallback: try to match by WoM collection hub patterns for WoM URLs
  if (site === 'wom') {
    // WoM-specific patterns based on collection structure
    if (clean.startsWith('/heritage-archive')) return 'A'; // default to Material Science for heritage
    if (clean.startsWith('/professionisti-in-movimento') || clean.startsWith('/professionals')) return 'B';
    if (clean.startsWith('/sostenibilita') || clean.startsWith('/sustainability') || clean.startsWith('/nachhaltigkeit') || clean.startsWith('/durabilite')) return 'C';
  }

  return 'uncategorized';
}

// ============================================================
// PRIORITY THRESHOLDS
// ============================================================
const THRESHOLDS = {
  HIGH: 60,   // ≥60% indexed → amplify
  MEDIUM: 20, // 20-59% → sustain
  // <20% → support
};

function getStrategy(indexRate) {
  if (indexRate >= THRESHOLDS.HIGH) return 'amplify';
  if (indexRate >= THRESHOLDS.MEDIUM) return 'sustain';
  return 'support';
}

function getStrategyDetails(strategy) {
  const details = {
    amplify: {
      label: '🚀 Amplify',
      labelIT: '🚀 Amplifica',
      action: 'Produce more content in this cluster — Google already trusts it',
      actionIT: 'Produci più contenuti in questo cluster — Google lo indicizza rapidamente',
      contentType: 'Adjacent keyword content, long-tail variants, topical depth',
      contentTypeIT: 'Contenuti keyword adiacenti, varianti long-tail, profondità tematica',
      expectedROI: 'high',
      timeToIndex: '< 7 days',
      priority: 1,
    },
    sustain: {
      label: '📈 Sustain',
      labelIT: '📈 Sostieni',
      action: 'Maintain steady content pace — cluster is growing',
      actionIT: 'Mantieni ritmo costante — il cluster sta crescendo',
      contentType: 'Interlinking support, internal link boosters, content updates',
      contentTypeIT: 'Supporto interlinking, booster link interni, aggiornamenti contenuti',
      expectedROI: 'medium',
      timeToIndex: '7-30 days',
      priority: 2,
    },
    support: {
      label: '🔧 Support',
      labelIT: '🔧 Supporta',
      action: 'Create hub/pillar content to help Google discover this area',
      actionIT: 'Crea contenuti pillar/hub per aiutare Google a scoprire quest\'area',
      contentType: 'Pillar pages, interlinking hubs, sitemap improvements, crawl-bait',
      contentTypeIT: 'Pagine pillar, hub interlinking, miglioramenti sitemap, crawl-bait',
      expectedROI: 'low (long-term)',
      timeToIndex: '30-90 days',
      priority: 3,
    },
  };
  return details[strategy] || details.support;
}

// ============================================================
// CRAWL MAP STORE — Step 5 fase 2 (Task #14, 2026-05-14):
//   Sorgente primaria: GET /v1/crawl-map?site=... su ml-worker (Postgres)
//   Fallback: file JSON committato (mantenuto come safety net)
// Pattern identico a indexAwareRouter.CrawlMapStore.
// ============================================================
const axios = require('axios');
const ML_WORKER_URL = process.env.ML_WORKER_URL || 'http://albeni-ai-orchestration.railway.internal:8080';

class CrawlMapStore {
  constructor(dashboardPath, options = {}) {
    this.dashboardPath = dashboardPath;
    this.apiBase = options.apiBase || ML_WORKER_URL;
    this.maps = { mu: {}, wom: {} };
    this.lastLoad = 0;
    this.TTL = 5 * 60 * 1000;
    this.loadingPromise = null;

    // Sync bootstrap dal file — primo getVerdict/cluster analysis non sarà vuoto
    this.loadFromFile();
  }

  async loadFromApi() {
    try {
      const fetchSite = async (site) => {
        const url = `${this.apiBase}/v1/crawl-map?site=${site}&limit=5000`;
        const r = await axios.get(url, { timeout: 8000 });
        if (r.status !== 200) throw new Error(`HTTP ${r.status}`);
        const map = {};
        for (const e of (r.data.entries || [])) {
          map[e.url_path] = e.verdict;
        }
        return map;
      };
      const [mu, wom] = await Promise.all([fetchSite('mu'), fetchSite('wom')]);
      this.maps.mu = mu;
      this.maps.wom = wom;
      console.log(`[ContentPrioritizer] Crawl maps loaded from API: MU ${Object.keys(mu).length}, WoM ${Object.keys(wom).length}`);
      return true;
    } catch (e) {
      console.warn(`[ContentPrioritizer] API load failed (${e.message}), falling back to JSON cache`);
      return false;
    }
  }

  loadFromFile() {
    try {
      for (const site of ['mu', 'wom']) {
        const mapPath = path.join(this.dashboardPath, `${site}_crawl_map.json`);
        if (fs.existsSync(mapPath)) {
          this.maps[site] = JSON.parse(fs.readFileSync(mapPath, 'utf8'));
        }
      }
      console.log(`[ContentPrioritizer] Crawl maps loaded from JSON: MU ${Object.keys(this.maps.mu).length}, WoM ${Object.keys(this.maps.wom).length}`);
    } catch (e) {
      console.error('[ContentPrioritizer] Failed to load crawl maps from JSON:', e.message);
    }
  }

  /**
   * Non-blocking refresh (fire-and-forget). Le funzioni che chiamano load()
   * leggono dalla cache in memoria, eventualmente leggermente stale.
   */
  load() {
    const now = Date.now();
    if (now - this.lastLoad < this.TTL) return;
    if (this.loadingPromise) return;

    this.loadingPromise = (async () => {
      const apiOk = await this.loadFromApi();
      if (!apiOk) this.loadFromFile();
      this.lastLoad = Date.now();
      this.loadingPromise = null;
    })();
  }
}

// ============================================================
// CORE ANALYSIS ENGINE
// ============================================================

/**
 * Analyzes all crawl map URLs, classifies them into clusters,
 * and computes per-cluster indexation health metrics.
 */
function analyzeClusterHealth(store) {
  store.load();

  const clusterStats = {};

  // Initialize all clusters
  for (const [id, cluster] of Object.entries(CLUSTERS)) {
    clusterStats[id] = {
      id,
      name: cluster.name,
      nameIT: cluster.nameIT,
      behavioral: cluster.behavioral,
      description: cluster.description,
      mu: { total: 0, indexed: 0, neutral: 0, error: 0, urls: [] },
      wom: { total: 0, indexed: 0, neutral: 0, error: 0, urls: [] },
      combined: { total: 0, indexed: 0, indexRate: 0 },
      strategy: null,
      strategyDetails: null,
      languages: { it: { total: 0, indexed: 0 }, en: { total: 0, indexed: 0 }, de: { total: 0, indexed: 0 }, fr: { total: 0, indexed: 0 } },
    };
  }

  // Also track uncategorized
  clusterStats['uncategorized'] = {
    id: 'uncategorized',
    name: 'Uncategorized',
    nameIT: 'Non categorizzato',
    behavioral: '-',
    description: 'URLs not matching any cluster pattern',
    mu: { total: 0, indexed: 0, neutral: 0, error: 0, urls: [] },
    wom: { total: 0, indexed: 0, neutral: 0, error: 0, urls: [] },
    combined: { total: 0, indexed: 0, indexRate: 0 },
    strategy: null,
    strategyDetails: null,
    languages: { it: { total: 0, indexed: 0 }, en: { total: 0, indexed: 0 }, de: { total: 0, indexed: 0 }, fr: { total: 0, indexed: 0 } },
  };

  // Process each site's crawl map
  for (const site of ['mu', 'wom']) {
    const map = store.maps[site] || {};
    for (const [urlPath, verdict] of Object.entries(map)) {
      const clusterId = classifyUrl(urlPath, site);
      const stats = clusterStats[clusterId];
      if (!stats) continue;

      const siteStats = stats[site];
      siteStats.total++;

      const isIndexed = verdict === 'PASS';
      if (isIndexed) siteStats.indexed++;
      else if (verdict === 'ERROR' || verdict === 'N/A') siteStats.error++;
      else siteStats.neutral++;

      // Track by language
      const lang = detectLanguage(urlPath);
      if (stats.languages[lang]) {
        stats.languages[lang].total++;
        if (isIndexed) stats.languages[lang].indexed++;
      }

      // Store URL details (limit to avoid memory bloat)
      if (siteStats.urls.length < 50) {
        siteStats.urls.push({ path: urlPath, verdict, lang });
      }
    }
  }

  // Compute combined metrics and strategy
  for (const stats of Object.values(clusterStats)) {
    stats.combined.total = stats.mu.total + stats.wom.total;
    stats.combined.indexed = stats.mu.indexed + stats.wom.indexed;
    stats.combined.indexRate = stats.combined.total > 0
      ? parseFloat(((stats.combined.indexed / stats.combined.total) * 100).toFixed(1))
      : 0;

    stats.strategy = getStrategy(stats.combined.indexRate);
    stats.strategyDetails = getStrategyDetails(stats.strategy);

    // Per-site index rates
    stats.mu.indexRate = stats.mu.total > 0
      ? parseFloat(((stats.mu.indexed / stats.mu.total) * 100).toFixed(1)) : 0;
    stats.wom.indexRate = stats.wom.total > 0
      ? parseFloat(((stats.wom.indexed / stats.wom.total) * 100).toFixed(1)) : 0;

    // Per-language index rates
    for (const lang of Object.keys(stats.languages)) {
      const l = stats.languages[lang];
      l.indexRate = l.total > 0 ? parseFloat(((l.indexed / l.total) * 100).toFixed(1)) : 0;
    }
  }

  return clusterStats;
}

// ============================================================
// CONTENT GENERATION QUEUE
// ============================================================
/**
 * Produces a prioritized queue of content recommendations
 * based on cluster health analysis.
 *
 * The queue balances two forces:
 *   1. Amplify high-indexation clusters (quick wins)
 *   2. Support low-indexation clusters (long-term growth)
 *
 * Allocation model (of next N content pieces):
 *   - 50% → amplify clusters (ROI immediato)
 *   - 30% → sustain clusters (momentum)
 *   - 20% → support clusters (crawl boost)
 */
function generateContentQueue(clusterStats, maxItems = 20) {
  const queue = [];

  // Separate clusters by strategy
  const amplify = [];
  const sustain = [];
  const support = [];

  for (const [id, stats] of Object.entries(clusterStats)) {
    if (id === 'uncategorized') continue;
    if (stats.strategy === 'amplify') amplify.push(stats);
    else if (stats.strategy === 'sustain') sustain.push(stats);
    else support.push(stats);
  }

  // Sort within each group
  amplify.sort((a, b) => b.combined.indexRate - a.combined.indexRate);
  sustain.sort((a, b) => b.combined.indexRate - a.combined.indexRate);
  support.sort((a, b) => a.combined.indexRate - b.combined.indexRate); // lowest first

  // Allocation
  const slots = {
    amplify: Math.round(maxItems * 0.5),
    sustain: Math.round(maxItems * 0.3),
    support: Math.round(maxItems * 0.2),
  };

  // Generate recommendations per cluster
  function addRecommendations(clusters, slotCount, strategy) {
    if (clusters.length === 0) return;
    const perCluster = Math.max(1, Math.ceil(slotCount / clusters.length));

    for (const cluster of clusters) {
      const recs = generateClusterRecommendations(cluster, perCluster);
      queue.push(...recs);
    }
  }

  addRecommendations(amplify, slots.amplify, 'amplify');
  addRecommendations(sustain, slots.sustain, 'sustain');
  addRecommendations(support, slots.support, 'support');

  // Sort final queue by priority score (lower = higher priority)
  queue.sort((a, b) => a.priorityScore - b.priorityScore);

  return queue.slice(0, maxItems);
}

/**
 * Generates specific content recommendations for a cluster.
 */
function generateClusterRecommendations(cluster, maxRecs) {
  const recs = [];
  const strategy = cluster.strategy;
  const details = cluster.strategyDetails;

  // Find weakest languages (lowest index rate)
  const langPriority = Object.entries(cluster.languages)
    .filter(([, l]) => l.total > 0)
    .sort((a, b) => a[1].indexRate - b[1].indexRate);

  // Find weakest site
  const weakerSite = cluster.mu.indexRate <= cluster.wom.indexRate ? 'mu' : 'wom';

  if (strategy === 'amplify') {
    // For amplify: suggest content in already-strong areas to capture more KW
    recs.push({
      cluster: cluster.id,
      clusterName: cluster.name,
      strategy: 'amplify',
      type: 'long-tail-expansion',
      title: `Long-tail expansion for ${cluster.name}`,
      titleIT: `Espansione long-tail per ${cluster.nameIT}`,
      description: `Create 2-3 long-tail keyword variants targeting adjacent queries in the ${cluster.name} cluster. Google already indexes ${cluster.combined.indexRate}% of this content.`,
      descriptionIT: `Crea 2-3 varianti keyword long-tail per query adiacenti nel cluster ${cluster.nameIT}. Google indicizza già il ${cluster.combined.indexRate}% di questo contenuto.`,
      targetSite: cluster.wom.indexRate > cluster.mu.indexRate ? 'wom' : 'mu',
      targetLanguages: langPriority.slice(0, 2).map(([l]) => l),
      priorityScore: details.priority * 10 - cluster.combined.indexRate,
      expectedImpact: 'high',
      indexRate: cluster.combined.indexRate,
    });

    if (maxRecs > 1) {
      recs.push({
        cluster: cluster.id,
        clusterName: cluster.name,
        strategy: 'amplify',
        type: 'topical-depth',
        title: `Topical depth content for ${cluster.name}`,
        titleIT: `Contenuto di profondità tematica per ${cluster.nameIT}`,
        description: `Add in-depth articles covering sub-topics within ${cluster.name} to build topical authority.`,
        descriptionIT: `Aggiungi articoli approfonditi su sotto-temi di ${cluster.nameIT} per costruire autorità tematica.`,
        targetSite: 'wom',
        targetLanguages: ['it', 'en'],
        priorityScore: details.priority * 10 - cluster.combined.indexRate + 5,
        expectedImpact: 'high',
        indexRate: cluster.combined.indexRate,
      });
    }
  }

  if (strategy === 'sustain') {
    // For sustain: focus on interlinking and weaker languages
    recs.push({
      cluster: cluster.id,
      clusterName: cluster.name,
      strategy: 'sustain',
      type: 'interlink-booster',
      title: `Interlinking boost for ${cluster.name}`,
      titleIT: `Boost interlinking per ${cluster.nameIT}`,
      description: `Strengthen internal links to non-indexed pages in ${cluster.name} (${cluster.combined.total - cluster.combined.indexed} pages still not crawled).`,
      descriptionIT: `Rafforza i link interni verso pagine non indicizzate in ${cluster.nameIT} (${cluster.combined.total - cluster.combined.indexed} pagine ancora non scansionate).`,
      targetSite: weakerSite,
      targetLanguages: langPriority.slice(0, 2).map(([l]) => l),
      priorityScore: details.priority * 10 + (100 - cluster.combined.indexRate),
      expectedImpact: 'medium',
      indexRate: cluster.combined.indexRate,
    });

    if (maxRecs > 1 && langPriority.length > 0 && langPriority[0][1].indexRate < 50) {
      const weakLang = langPriority[0][0];
      recs.push({
        cluster: cluster.id,
        clusterName: cluster.name,
        strategy: 'sustain',
        type: 'language-gap',
        title: `${weakLang.toUpperCase()} language gap in ${cluster.name}`,
        titleIT: `Gap linguistico ${weakLang.toUpperCase()} in ${cluster.nameIT}`,
        description: `${weakLang.toUpperCase()} has only ${langPriority[0][1].indexRate}% indexation in ${cluster.name}. Consider creating dedicated content or improving translations.`,
        descriptionIT: `${weakLang.toUpperCase()} ha solo ${langPriority[0][1].indexRate}% indicizzazione in ${cluster.nameIT}. Valuta contenuti dedicati o migliorare le traduzioni.`,
        targetSite: weakerSite,
        targetLanguages: [weakLang],
        priorityScore: details.priority * 10 + (100 - langPriority[0][1].indexRate),
        expectedImpact: 'medium',
        indexRate: cluster.combined.indexRate,
      });
    }
  }

  if (strategy === 'support') {
    // For support: focus on discoverability
    recs.push({
      cluster: cluster.id,
      clusterName: cluster.name,
      strategy: 'support',
      type: 'pillar-content',
      title: `Pillar page for ${cluster.name}`,
      titleIT: `Pagina pillar per ${cluster.nameIT}`,
      description: `Create a comprehensive pillar page to serve as a crawl hub for the ${cluster.name} cluster. Only ${cluster.combined.indexRate}% indexed — Google needs entry points.`,
      descriptionIT: `Crea una pagina pillar completa come hub di scansione per il cluster ${cluster.nameIT}. Solo ${cluster.combined.indexRate}% indicizzato — Google ha bisogno di punti di ingresso.`,
      targetSite: weakerSite,
      targetLanguages: ['it', 'en'],
      priorityScore: details.priority * 10 + (200 - cluster.combined.indexRate),
      expectedImpact: 'low-medium',
      indexRate: cluster.combined.indexRate,
    });

    if (maxRecs > 1) {
      recs.push({
        cluster: cluster.id,
        clusterName: cluster.name,
        strategy: 'support',
        type: 'crawl-bait',
        title: `Crawl-bait content for ${cluster.name}`,
        titleIT: `Contenuto crawl-bait per ${cluster.nameIT}`,
        description: `Short, link-rich pages within ${cluster.name} designed to attract Googlebot and distribute PageRank to unindexed pages.`,
        descriptionIT: `Pagine brevi e ricche di link in ${cluster.nameIT} progettate per attirare Googlebot e distribuire PageRank alle pagine non indicizzate.`,
        targetSite: 'wom',
        targetLanguages: ['it'],
        priorityScore: details.priority * 10 + (200 - cluster.combined.indexRate) + 5,
        expectedImpact: 'low',
        indexRate: cluster.combined.indexRate,
      });
    }
  }

  return recs.slice(0, maxRecs);
}

// ============================================================
// CROSS-DOMAIN OPPORTUNITY DETECTOR
// ============================================================
/**
 * Identifies cross-domain content opportunities:
 * pages that exist on one site but not the other,
 * especially when the existing version is indexed.
 */
function detectCrossDomainGaps(clusterStats) {
  const gaps = [];

  for (const [id, stats] of Object.entries(clusterStats)) {
    if (id === 'uncategorized') continue;

    // MU has content but WoM doesn't (or vice versa)
    if (stats.mu.total > 0 && stats.wom.total === 0) {
      gaps.push({
        cluster: id,
        clusterName: stats.name,
        gap: 'wom_missing',
        description: `${stats.name} has ${stats.mu.total} MU pages but no WoM editorial content`,
        recommendation: 'Create WoM editorial articles to provide TOFU entry points',
        severity: stats.mu.indexed > 0 ? 'high' : 'medium',
      });
    }

    if (stats.wom.total > 0 && stats.mu.total === 0) {
      gaps.push({
        cluster: id,
        clusterName: stats.name,
        gap: 'mu_missing',
        description: `${stats.name} has ${stats.wom.total} WoM pages but no MU educational content`,
        recommendation: 'Create MU educational guides to provide MOFU depth',
        severity: stats.wom.indexed > 0 ? 'high' : 'medium',
      });
    }

    // Large indexation imbalance between sites
    if (stats.mu.total > 3 && stats.wom.total > 3) {
      const diff = Math.abs(stats.mu.indexRate - stats.wom.indexRate);
      if (diff > 40) {
        const strongSite = stats.mu.indexRate > stats.wom.indexRate ? 'mu' : 'wom';
        const weakSite = strongSite === 'mu' ? 'wom' : 'mu';
        gaps.push({
          cluster: id,
          clusterName: stats.name,
          gap: 'site_imbalance',
          description: `${stats.name}: ${strongSite.toUpperCase()} at ${stats[strongSite].indexRate}% but ${weakSite.toUpperCase()} at ${stats[weakSite].indexRate}%`,
          recommendation: `Boost interlinking from ${strongSite.toUpperCase()} to ${weakSite.toUpperCase()} to transfer crawl equity`,
          severity: 'medium',
        });
      }
    }
  }

  return gaps;
}

// ============================================================
// SUMMARY REPORT GENERATOR
// ============================================================

function generateReport(store) {
  const clusterStats = analyzeClusterHealth(store);
  const queue = generateContentQueue(clusterStats);
  const gaps = detectCrossDomainGaps(clusterStats);

  // Global stats
  let totalUrls = 0, totalIndexed = 0;
  const strategyCounts = { amplify: 0, sustain: 0, support: 0 };

  for (const [id, stats] of Object.entries(clusterStats)) {
    if (id === 'uncategorized') continue;
    totalUrls += stats.combined.total;
    totalIndexed += stats.combined.indexed;
    strategyCounts[stats.strategy]++;
  }

  return {
    timestamp: new Date().toISOString(),
    global: {
      totalUrls,
      totalIndexed,
      globalIndexRate: totalUrls > 0 ? parseFloat(((totalIndexed / totalUrls) * 100).toFixed(1)) : 0,
      clusterCount: Object.keys(clusterStats).length - 1, // exclude uncategorized
      strategyCounts,
    },
    clusters: clusterStats,
    contentQueue: queue,
    crossDomainGaps: gaps,
    thresholds: THRESHOLDS,
    allocationModel: {
      amplify: '50%',
      sustain: '30%',
      support: '20%',
      description: 'Allocation of next N content pieces across strategies',
    },
  };
}

// ============================================================
// EXPRESS ROUTE FACTORY
// ============================================================

function createRoutes(dashboardPath) {
  const express = require('express');
  const router = express.Router();
  const store = new CrawlMapStore(dashboardPath);

  // --- Full report ---
  // GET /v1/content/priorities
  router.get('/', (req, res) => {
    try {
      const report = generateReport(store);
      res.json(report);
    } catch (e) {
      console.error('[ContentPrioritizer] Report error:', e);
      res.status(500).json({ error: e.message });
    }
  });

  // --- Cluster health only ---
  // GET /v1/content/priorities/clusters
  router.get('/clusters', (req, res) => {
    try {
      const stats = analyzeClusterHealth(store);
      res.json({ clusters: stats, timestamp: new Date().toISOString() });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  });

  // --- Content queue only ---
  // GET /v1/content/priorities/queue?max=20
  router.get('/queue', (req, res) => {
    try {
      const max = parseInt(req.query.max) || 20;
      const stats = analyzeClusterHealth(store);
      const queue = generateContentQueue(stats, max);
      res.json({ queue, total: queue.length, timestamp: new Date().toISOString() });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  });

  // --- Cross-domain gap analysis ---
  // GET /v1/content/priorities/gaps
  router.get('/gaps', (req, res) => {
    try {
      const stats = analyzeClusterHealth(store);
      const gaps = detectCrossDomainGaps(stats);
      res.json({ gaps, total: gaps.length, timestamp: new Date().toISOString() });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  });

  // --- Single cluster detail ---
  // GET /v1/content/priorities/cluster/:id
  router.get('/cluster/:id', (req, res) => {
    try {
      const stats = analyzeClusterHealth(store);
      const cluster = stats[req.params.id.toUpperCase()] || stats[req.params.id];
      if (!cluster) {
        return res.status(404).json({ error: `Cluster "${req.params.id}" not found` });
      }
      res.json({ cluster, timestamp: new Date().toISOString() });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  });

  // --- Consult endpoint for Content Generator ---
  // POST /v1/content/priorities/consult
  // Body: { cluster: "A", site: "wom", lang: "de" }
  // Returns: should this content be generated? priority? alternative?
  router.post('/consult', (req, res) => {
    try {
      const { cluster: clusterId, site, lang } = req.body;
      if (!clusterId) {
        return res.status(400).json({ error: 'Missing required field: cluster' });
      }

      const stats = analyzeClusterHealth(store);
      const cluster = stats[clusterId.toUpperCase()] || stats[clusterId];
      if (!cluster) {
        return res.status(404).json({ error: `Cluster "${clusterId}" not found` });
      }

      const siteStats = site ? cluster[site] : null;
      const langStats = lang ? cluster.languages[lang] : null;

      // Decision logic
      const decision = {
        cluster: cluster.id,
        strategy: cluster.strategy,
        proceed: true,
        priority: cluster.strategyDetails.priority,
        reasoning: '',
        alternatives: [],
      };

      if (cluster.strategy === 'amplify') {
        decision.reasoning = `Cluster ${cluster.name} is at ${cluster.combined.indexRate}% indexation. New content will likely be indexed quickly — proceed with high priority.`;
        decision.priority = 1;
      } else if (cluster.strategy === 'sustain') {
        decision.reasoning = `Cluster ${cluster.name} is growing (${cluster.combined.indexRate}%). Content is useful but ensure strong internal linking.`;
        decision.priority = 2;

        // Suggest amplify clusters as alternatives
        const amplifyClusters = Object.values(stats)
          .filter(s => s.strategy === 'amplify' && s.id !== 'uncategorized')
          .map(s => ({ cluster: s.id, name: s.name, indexRate: s.combined.indexRate }));
        if (amplifyClusters.length > 0) {
          decision.alternatives = amplifyClusters;
        }
      } else {
        decision.reasoning = `Cluster ${cluster.name} is at ${cluster.combined.indexRate}% — low indexation. Content may take 30-90 days to appear. Consider creating support/pillar content first.`;
        decision.priority = 3;

        // Check if interlinking support would help more
        const notIndexed = cluster.combined.total - cluster.combined.indexed;
        if (notIndexed > 10) {
          decision.alternatives.push({
            action: 'interlinking_boost',
            description: `${notIndexed} pages in this cluster are not indexed. Improve internal links before creating more content.`,
          });
        }
      }

      // Language-specific advice
      if (langStats && langStats.total > 0 && langStats.indexRate < 10) {
        decision.languageWarning = `${lang.toUpperCase()} has only ${langStats.indexRate}% indexation in this cluster. Consider prioritizing IT or EN first.`;
      }

      res.json({ decision, clusterHealth: cluster, timestamp: new Date().toISOString() });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  });

  // --- Update thresholds ---
  // PUT /v1/content/priorities/thresholds
  router.put('/thresholds', (req, res) => {
    const apiKey = req.headers['x-api-key'] || req.query.api_key;
    if (apiKey !== (process.env.API_KEY || 'albeni-gsc-2026')) {
      return res.status(401).json({ error: 'Unauthorized' });
    }
    const { high, medium } = req.body;
    if (high !== undefined) THRESHOLDS.HIGH = parseInt(high);
    if (medium !== undefined) THRESHOLDS.MEDIUM = parseInt(medium);
    res.json({ status: 'ok', thresholds: THRESHOLDS });
  });

  return router;
}

// ============================================================
// EXPORTS
// ============================================================

module.exports = {
  createRoutes,
  analyzeClusterHealth,
  generateContentQueue,
  detectCrossDomainGaps,
  generateReport,
  classifyUrl,
  CrawlMapStore,
  CLUSTERS,
  THRESHOLDS,
};
