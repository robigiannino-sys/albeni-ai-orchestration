/**
 * ============================================================
 * ADV Budget Allocator — Paid/Organic Compensator
 * Albeni 1905 — AI Orchestration Layer
 * ============================================================
 *
 * PURPOSE:
 * Bridges the gap between content that exists and content that
 * Google can see — by directing paid spend exactly where organic
 * visibility is missing, and pulling it back as organic catches up.
 *
 * LOGIC:
 *   1. Read cluster health from contentPrioritizer
 *   2. Compute gap_score per cluster = non_indexed_ratio × kw_volume_weight
 *   3. Normalize and allocate monthly budget across clusters
 *   4. Distribute within clusters by page priority
 *   5. Apply 30-day linear decay for newly-indexed pages
 *   6. Enforce guardrails (min €5, max 15%, exclusions)
 *
 * DATA SOURCES:
 *   - contentPrioritizer.js → cluster health, crawl maps
 *   - adv_transitions.json → pages in 30-day decay phase
 *   - Budget config → €30K / 18 months, phase-based
 *
 * API:
 *   GET  /v1/adv/allocate          → Full allocation report
 *   GET  /v1/adv/cluster/:id       → Single cluster allocation
 *   GET  /v1/adv/transitions       → Pages in 30-day decay
 *   POST /v1/adv/index-event       → Record a page indexation event
 *   PUT  /v1/adv/config            → Update budget/phase config
 *
 * @version 1.0.0
 * @date 2026-04-10
 */

const fs = require('fs');
const path = require('path');

// Reuse core infrastructure from contentPrioritizer
const {
  analyzeClusterHealth,
  CrawlMapStore,
  CLUSTERS,
} = require('./contentPrioritizer');

// ============================================================
// BUDGET CONFIGURATION
// ============================================================

const BUDGET_CONFIG = {
  total: 30000,
  phases: {
    1: { months: [1, 2, 3, 4, 5, 6], monthlyBudget: 2500, label: 'Paid-First' },
    2: { months: [7, 8, 9, 10, 11, 12], monthlyBudget: 1667, label: 'Hybrid' },
    3: { months: [13, 14, 15, 16, 17, 18], monthlyBudget: 833, label: 'Organic-Led' },
  },
  // Current phase — updated via PUT /v1/adv/config
  currentPhase: 1,
  currentMonth: 1,
};

// Market allocation (post-SEMrush audit)
const MARKET_ALLOCATION = {
  DE: { pct: 0.35, budget: 10500, label: 'Germany (Priority)' },
  US: { pct: 0.25, budget: 7500, label: 'United States' },
  IT: { pct: 0.18, budget: 5400, label: 'Italy' },
  UK: { pct: 0.12, budget: 3600, label: 'United Kingdom' },
  FR: { pct: 0.10, budget: 3000, label: 'France' },
};

// Cluster keyword volume weights (from 62 L1 head-terms)
const CLUSTER_KW_WEIGHTS = {
  A: { weight: 0.28, label: 'Scienza Materiali', topKW: 'merino wool, 17 micron, keratin' },
  B: { weight: 0.12, label: 'Costruzione & Design', topKW: 'cut & sew, t-shirt construction' },
  C: { weight: 0.18, label: 'Origini Etiche', topKW: 'sustainable wool, ethical fashion' },
  D: { weight: 0.08, label: 'Innovazione', topKW: 'merino technology, fabric innovation' },
  E: { weight: 0.22, label: 'Lab Pratico', topKW: 'merino care, GSM guide, capsule wardrobe' },
  F: { weight: 0.12, label: 'Heritage & Brand', topKW: 'Italian clothing brand, heritage' },
};

// Funnel multipliers for page-level priority
const FUNNEL_MULTIPLIER = {
  bofu: 1.5,   // Pages with PMS/Albeni CTA
  mofu: 1.2,   // MU educational, checklists
  tofu: 1.0,   // WoM editorial, stories
};

// Guardrails
const GUARDRAILS = {
  minPageAllocation: 5,    // €5/month minimum per page
  maxPagePct: 0.15,        // 15% of monthly budget max per page
  transitionDays: 30,      // Linear decay period
};

// Pages excluded from paid allocation
const EXCLUDED_PATHS = [
  '/', '/faq', '/contacts', '/contatti', '/cookie-policy', '/privacy',
  '/manifesto', '/research-library', '/redazione', '/editorial-team',
  '/chi-siamo', '/about-us', '/ueber-uns', '/a-propos-de-nous',
];

// ============================================================
// TRANSITION TRACKER
// ============================================================
// Tracks pages transitioning from paid→organic (30-day decay)

class TransitionStore {
  constructor(dashboardPath) {
    this.filePath = path.join(dashboardPath, 'adv_transitions.json');
    this.transitions = [];
    this.lastLoad = 0;
    this.TTL = 60 * 1000; // 1 minute
  }

  load() {
    const now = Date.now();
    if (now - this.lastLoad < this.TTL) return;
    try {
      if (fs.existsSync(this.filePath)) {
        this.transitions = JSON.parse(fs.readFileSync(this.filePath, 'utf8'));
      }
      this.lastLoad = now;
    } catch (e) {
      console.error('[ADVAllocator] Failed to load transitions:', e.message);
      this.transitions = [];
    }
  }

  save() {
    try {
      fs.writeFileSync(this.filePath, JSON.stringify(this.transitions, null, 2), 'utf8');
      this.lastLoad = Date.now();
    } catch (e) {
      console.error('[ADVAllocator] Failed to save transitions:', e.message);
    }
  }

  addTransition(urlPath, site, cluster, originalBudget) {
    // Don't duplicate
    const existing = this.transitions.find(t => t.urlPath === urlPath && t.site === site);
    if (existing) return existing;

    const transition = {
      urlPath,
      site,
      cluster,
      originalBudget,
      indexedDate: new Date().toISOString(),
      daysSinceIndexed: 0,
      remainingBudget: originalBudget,
      status: 'decaying', // decaying | completed
    };
    this.transitions.push(transition);
    this.save();
    return transition;
  }

  // Update all transitions: compute days elapsed, remaining budget
  refresh() {
    const now = new Date();
    let freed = 0;

    for (const t of this.transitions) {
      if (t.status === 'completed') continue;

      const indexedDate = new Date(t.indexedDate);
      t.daysSinceIndexed = Math.floor((now - indexedDate) / (1000 * 60 * 60 * 24));

      if (t.daysSinceIndexed >= GUARDRAILS.transitionDays) {
        freed += t.remainingBudget;
        t.remainingBudget = 0;
        t.status = 'completed';
      } else {
        const decayFactor = Math.max(0, (GUARDRAILS.transitionDays - t.daysSinceIndexed) / GUARDRAILS.transitionDays);
        const newBudget = parseFloat((t.originalBudget * decayFactor).toFixed(2));
        freed += (t.remainingBudget - newBudget);
        t.remainingBudget = newBudget;
      }
    }

    this.save();
    return { freedBudget: parseFloat(freed.toFixed(2)) };
  }

  getActive() {
    return this.transitions.filter(t => t.status === 'decaying');
  }

  getCompleted() {
    return this.transitions.filter(t => t.status === 'completed');
  }
}

// ============================================================
// CORE ALLOCATION ENGINE
// ============================================================

/**
 * Computes full budget allocation based on cluster health + KW weights.
 * Returns per-cluster and per-page allocation with recommendations.
 */
function computeAllocation(store, transitionStore) {
  const clusterHealth = analyzeClusterHealth(store);
  transitionStore.load();
  const { freedBudget } = transitionStore.refresh();

  const phase = BUDGET_CONFIG.phases[BUDGET_CONFIG.currentPhase];
  const monthlyBudget = phase.monthlyBudget + freedBudget;
  const maxPerPage = monthlyBudget * GUARDRAILS.maxPagePct;

  // Step 1: Compute gap scores
  const clusterAllocations = {};
  let totalGapScore = 0;

  for (const [id, cluster] of Object.entries(CLUSTERS)) {
    const health = clusterHealth[id];
    if (!health || id === 'uncategorized') continue;

    const kwData = CLUSTER_KW_WEIGHTS[id];
    if (!kwData) continue;

    const nonIndexedRatio = health.combined.total > 0
      ? (health.combined.total - health.combined.indexed) / health.combined.total
      : 0;

    const gapScore = nonIndexedRatio * kwData.weight;
    totalGapScore += gapScore;

    clusterAllocations[id] = {
      id,
      name: kwData.label,
      behavioral: health.behavioral,
      kwWeight: kwData.weight,
      topKW: kwData.topKW,
      // Health metrics
      totalPages: health.combined.total,
      indexedPages: health.combined.indexed,
      nonIndexedPages: health.combined.total - health.combined.indexed,
      indexRate: health.combined.indexRate,
      muIndexRate: health.mu.indexRate,
      womIndexRate: health.wom.indexRate,
      // Gap analysis
      nonIndexedRatio: parseFloat(nonIndexedRatio.toFixed(3)),
      gapScore: parseFloat(gapScore.toFixed(4)),
      normalizedGap: 0, // computed below
      // Budget (computed below)
      monthlyBudget: 0,
      perPageAvg: 0,
      // Strategy from content AI layer
      contentStrategy: health.strategy,
      // Pages detail
      nonIndexedUrls: [],
      // Transition pages in this cluster
      activeTransitions: transitionStore.getActive().filter(t => t.cluster === id),
      transitionBudget: 0,
    };

    // Collect non-indexed URLs for page-level allocation
    for (const site of ['mu', 'wom']) {
      const siteHealth = health[site];
      if (siteHealth.urls) {
        for (const url of siteHealth.urls) {
          if (url.verdict !== 'PASS' && !isExcluded(url.path)) {
            clusterAllocations[id].nonIndexedUrls.push({
              path: url.path,
              site,
              lang: url.lang,
              verdict: url.verdict,
              funnelType: site === 'mu' ? 'mofu' : 'tofu',
              funnelMultiplier: site === 'mu' ? FUNNEL_MULTIPLIER.mofu : FUNNEL_MULTIPLIER.tofu,
            });
          }
        }
      }
    }
  }

  // Step 2: Normalize and allocate budget
  for (const alloc of Object.values(clusterAllocations)) {
    alloc.normalizedGap = totalGapScore > 0
      ? parseFloat((alloc.gapScore / totalGapScore).toFixed(4))
      : 0;

    // Base cluster budget from gap score
    let clusterBudget = monthlyBudget * alloc.normalizedGap;

    // Subtract transition budget (pages still decaying in this cluster)
    const transitionCost = alloc.activeTransitions.reduce((sum, t) => sum + t.remainingBudget, 0);
    alloc.transitionBudget = parseFloat(transitionCost.toFixed(2));
    clusterBudget = Math.max(0, clusterBudget - transitionCost);

    alloc.monthlyBudget = parseFloat(clusterBudget.toFixed(2));
    alloc.perPageAvg = alloc.nonIndexedPages > 0
      ? parseFloat((clusterBudget / alloc.nonIndexedPages).toFixed(2))
      : 0;

    // Step 3: Page-level distribution
    if (alloc.nonIndexedUrls.length > 0 && clusterBudget > 0) {
      // Assign priority scores
      let totalPriority = 0;
      for (const page of alloc.nonIndexedUrls) {
        page.priorityScore = page.funnelMultiplier; // base = funnel position
        totalPriority += page.priorityScore;
      }

      // Distribute budget by priority score
      for (const page of alloc.nonIndexedUrls) {
        const share = totalPriority > 0 ? page.priorityScore / totalPriority : 0;
        let pageBudget = clusterBudget * share;

        // Apply guardrails
        pageBudget = Math.max(GUARDRAILS.minPageAllocation, pageBudget);
        pageBudget = Math.min(maxPerPage, pageBudget);
        page.monthlyBudget = parseFloat(pageBudget.toFixed(2));
      }

      // Sort by budget descending
      alloc.nonIndexedUrls.sort((a, b) => b.monthlyBudget - a.monthlyBudget);
    }
  }

  // Step 4: Generate recommendations
  const recommendations = generateRecommendations(clusterAllocations, transitionStore);

  // Step 5: Compile summary
  let totalAllocated = 0;
  let totalNonIndexed = 0;
  let totalPages = 0;
  let totalIndexed = 0;

  for (const alloc of Object.values(clusterAllocations)) {
    totalAllocated += alloc.monthlyBudget + alloc.transitionBudget;
    totalNonIndexed += alloc.nonIndexedPages;
    totalPages += alloc.totalPages;
    totalIndexed += alloc.indexedPages;
  }

  return {
    timestamp: new Date().toISOString(),
    config: {
      currentPhase: BUDGET_CONFIG.currentPhase,
      phaseLabel: phase.label,
      currentMonth: BUDGET_CONFIG.currentMonth,
      baseBudget: phase.monthlyBudget,
      freedBudget: parseFloat(freedBudget.toFixed(2)),
      effectiveBudget: parseFloat(monthlyBudget.toFixed(2)),
      maxPerPage,
    },
    global: {
      totalPages,
      totalIndexed,
      totalNonIndexed,
      globalIndexRate: totalPages > 0 ? parseFloat(((totalIndexed / totalPages) * 100).toFixed(1)) : 0,
      totalAllocated: parseFloat(totalAllocated.toFixed(2)),
      budgetUtilization: parseFloat(((totalAllocated / monthlyBudget) * 100).toFixed(1)),
      paidCoverageRate: totalNonIndexed > 0
        ? parseFloat(((Object.values(clusterAllocations).reduce((s, a) => s + a.nonIndexedUrls.length, 0) / totalNonIndexed) * 100).toFixed(1))
        : 0,
    },
    clusters: clusterAllocations,
    transitions: {
      active: transitionStore.getActive(),
      completed: transitionStore.getCompleted().length,
      totalFreed: parseFloat(freedBudget.toFixed(2)),
    },
    recommendations,
    markets: MARKET_ALLOCATION,
    guardrails: GUARDRAILS,
  };
}

// ============================================================
// EXCLUSION CHECK
// ============================================================

function isExcluded(urlPath) {
  const clean = urlPath.replace(/\/$/, '') || '/';
  const stripped = clean
    .replace(/^\/en-us\//, '/')
    .replace(/^\/en\//, '/')
    .replace(/^\/de\//, '/')
    .replace(/^\/fr\//, '/');

  return EXCLUDED_PATHS.some(ex => stripped === ex || stripped.startsWith(ex + '/'));
}

// ============================================================
// RECOMMENDATION ENGINE
// ============================================================

function generateRecommendations(clusterAllocations, transitionStore) {
  const recs = [];

  // Sort clusters by gap score descending
  const sorted = Object.values(clusterAllocations).sort((a, b) => b.gapScore - a.gapScore);

  // 1. Most critical cluster
  if (sorted.length > 0 && sorted[0].nonIndexedRatio > 0.5) {
    const top = sorted[0];
    recs.push({
      type: 'critical_cluster',
      priority: 'P0',
      cluster: top.id,
      title: `Cluster ${top.id} (${top.name}) ha il gap più critico`,
      detail: `${top.nonIndexedPages} pagine non indicizzate su ${top.totalPages} totali (${top.indexRate}% index rate). ` +
              `Riceve €${top.monthlyBudget}/mese di budget paid. KW weight: ${(top.kwWeight * 100).toFixed(0)}%.`,
      action: `Concentrare paid su pagine MOFU di questo cluster + boost interlinking via snippet #2867.`,
    });
  }

  // 2. Clusters with 100% indexation (can free budget)
  const fullyIndexed = sorted.filter(c => c.indexRate >= 100);
  if (fullyIndexed.length > 0) {
    recs.push({
      type: 'budget_freed',
      priority: 'P1',
      title: `${fullyIndexed.length} cluster completamente indicizzati`,
      detail: `Cluster ${fullyIndexed.map(c => c.id).join(', ')} hanno index rate 100%. ` +
              `Budget riallocabile verso cluster con gap.`,
      action: `Verificare che tutte le transizioni 30gg siano completate, poi riallocare.`,
    });
  }

  // 3. MU vs WoM imbalance
  for (const alloc of sorted) {
    if (alloc.muIndexRate < 10 && alloc.womIndexRate > 50) {
      recs.push({
        type: 'site_imbalance',
        priority: 'P1',
        cluster: alloc.id,
        title: `Cluster ${alloc.id}: MU a ${alloc.muIndexRate}% vs WoM a ${alloc.womIndexRate}%`,
        detail: `MU è il collo di bottiglia. L'Index-Aware Router (#3018) compensa per UX, ` +
                `ma il paid deve comunque targettare MU per accelerare l'indicizzazione.`,
        action: `Allocare paid specificamente su URL MU di questo cluster.`,
      });
    }
  }

  // 4. Pages close to 30-day urgency threshold
  const active = transitionStore.getActive();
  const nearExpiry = active.filter(t => t.daysSinceIndexed >= 25);
  if (nearExpiry.length > 0) {
    recs.push({
      type: 'transition_expiry',
      priority: 'P2',
      title: `${nearExpiry.length} transizioni in scadenza nei prossimi 5 giorni`,
      detail: nearExpiry.map(t => `${t.urlPath} (day ${t.daysSinceIndexed}/30, €${t.remainingBudget} residuo)`).join('; '),
      action: `Budget liberato sarà auto-riallocato al prossimo calcolo.`,
    });
  }

  // 5. Budget utilization warning
  const totalAllocated = Object.values(clusterAllocations).reduce((s, a) => s + a.monthlyBudget, 0);
  const phase = BUDGET_CONFIG.phases[BUDGET_CONFIG.currentPhase];
  if (totalAllocated < phase.monthlyBudget * 0.8) {
    recs.push({
      type: 'underutilized',
      priority: 'P2',
      title: `Budget utilizzato al ${((totalAllocated / phase.monthlyBudget) * 100).toFixed(0)}%`,
      detail: `€${totalAllocated.toFixed(0)} allocati su €${phase.monthlyBudget} disponibili. ` +
              `Il surplus può andare su retargeting o BOFU defense.`,
      action: `Considerare di aumentare le allocazioni per i cluster D ed E (gap più alti).`,
    });
  }

  return recs;
}

// ============================================================
// EXPRESS ROUTE FACTORY
// ============================================================

function createRoutes(dashboardPath) {
  const express = require('express');
  const router = express.Router();
  const store = new CrawlMapStore(dashboardPath);
  const transitionStore = new TransitionStore(dashboardPath);

  // --- Full allocation report ---
  // GET /v1/adv/allocate
  router.get('/allocate', (req, res) => {
    try {
      const report = computeAllocation(store, transitionStore);
      res.json(report);
    } catch (e) {
      console.error('[ADVAllocator] Report error:', e);
      res.status(500).json({ error: e.message });
    }
  });

  // --- Full report (also on root) ---
  router.get('/', (req, res) => {
    try {
      const report = computeAllocation(store, transitionStore);
      res.json(report);
    } catch (e) {
      console.error('[ADVAllocator] Report error:', e);
      res.status(500).json({ error: e.message });
    }
  });

  // --- Single cluster allocation ---
  // GET /v1/adv/cluster/:id
  router.get('/cluster/:id', (req, res) => {
    try {
      const report = computeAllocation(store, transitionStore);
      const cluster = report.clusters[req.params.id.toUpperCase()];
      if (!cluster) {
        return res.status(404).json({ error: `Cluster "${req.params.id}" not found` });
      }
      res.json({
        cluster,
        config: report.config,
        timestamp: report.timestamp,
      });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  });

  // --- Transitions list ---
  // GET /v1/adv/transitions
  router.get('/transitions', (req, res) => {
    try {
      transitionStore.load();
      transitionStore.refresh();
      res.json({
        active: transitionStore.getActive(),
        completed: transitionStore.getCompleted(),
        totalActive: transitionStore.getActive().length,
        totalCompleted: transitionStore.getCompleted().length,
        timestamp: new Date().toISOString(),
      });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  });

  // --- Record indexation event ---
  // POST /v1/adv/index-event
  // Body: { urlPath: "/page-slug", site: "mu", cluster: "A" }
  // Called when GSC scan detects a new PASS verdict
  router.post('/index-event', (req, res) => {
    const apiKey = req.headers['x-api-key'] || req.query.api_key;
    if (apiKey !== (process.env.API_KEY || 'albeni-gsc-2026')) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    try {
      const { urlPath, site, cluster } = req.body;
      if (!urlPath || !site) {
        return res.status(400).json({ error: 'Missing required fields: urlPath, site' });
      }

      transitionStore.load();

      // Estimate original budget for this page (use cluster average)
      const report = computeAllocation(store, transitionStore);
      const clusterData = report.clusters[cluster || 'A'];
      const estimatedBudget = clusterData ? clusterData.perPageAvg : GUARDRAILS.minPageAllocation;

      const transition = transitionStore.addTransition(
        urlPath, site, cluster || 'uncategorized', estimatedBudget
      );

      res.json({
        status: 'ok',
        transition,
        message: `Page "${urlPath}" entered 30-day transition. Budget will decay from €${estimatedBudget} to €0.`,
      });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  });

  // --- Batch index events (from GSC scan) ---
  // POST /v1/adv/index-events
  // Body: { events: [{ urlPath, site, cluster }, ...] }
  router.post('/index-events', (req, res) => {
    const apiKey = req.headers['x-api-key'] || req.query.api_key;
    if (apiKey !== (process.env.API_KEY || 'albeni-gsc-2026')) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    try {
      const { events } = req.body;
      if (!Array.isArray(events)) {
        return res.status(400).json({ error: 'Body must contain events array' });
      }

      transitionStore.load();
      const report = computeAllocation(store, transitionStore);
      const results = [];

      for (const evt of events.slice(0, 100)) { // max 100 per batch
        const clusterData = report.clusters[evt.cluster || 'A'];
        const budget = clusterData ? clusterData.perPageAvg : GUARDRAILS.minPageAllocation;
        const transition = transitionStore.addTransition(
          evt.urlPath, evt.site, evt.cluster || 'uncategorized', budget
        );
        results.push(transition);
      }

      res.json({
        status: 'ok',
        processed: results.length,
        transitions: results,
      });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  });

  // --- Update config ---
  // PUT /v1/adv/config
  router.put('/config', (req, res) => {
    const apiKey = req.headers['x-api-key'] || req.query.api_key;
    if (apiKey !== (process.env.API_KEY || 'albeni-gsc-2026')) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    const { phase, month, budgetOverride } = req.body;
    if (phase !== undefined) {
      if (![1, 2, 3].includes(phase)) {
        return res.status(400).json({ error: 'Phase must be 1, 2, or 3' });
      }
      BUDGET_CONFIG.currentPhase = phase;
    }
    if (month !== undefined) {
      if (month < 1 || month > 18) {
        return res.status(400).json({ error: 'Month must be 1-18' });
      }
      BUDGET_CONFIG.currentMonth = month;
      // Auto-detect phase from month
      if (month <= 6) BUDGET_CONFIG.currentPhase = 1;
      else if (month <= 12) BUDGET_CONFIG.currentPhase = 2;
      else BUDGET_CONFIG.currentPhase = 3;
    }
    if (budgetOverride !== undefined) {
      BUDGET_CONFIG.phases[BUDGET_CONFIG.currentPhase].monthlyBudget = budgetOverride;
    }

    res.json({
      status: 'ok',
      config: {
        currentPhase: BUDGET_CONFIG.currentPhase,
        currentMonth: BUDGET_CONFIG.currentMonth,
        monthlyBudget: BUDGET_CONFIG.phases[BUDGET_CONFIG.currentPhase].monthlyBudget,
        phaseLabel: BUDGET_CONFIG.phases[BUDGET_CONFIG.currentPhase].label,
      },
    });
  });

  return router;
}

// ============================================================
// EXPORTS
// ============================================================

module.exports = {
  createRoutes,
  computeAllocation,
  TransitionStore,
  BUDGET_CONFIG,
  MARKET_ALLOCATION,
  CLUSTER_KW_WEIGHTS,
  GUARDRAILS,
};
