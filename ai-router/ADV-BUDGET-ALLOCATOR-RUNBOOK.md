# ADV Budget Allocator — Deployment Runbook

## Overview

The ADV Budget Allocator is a middleware module for the AI Orchestration Layer on Railway. It automatically allocates the €30K ADV budget across non-indexed pages based on cluster health, and manages the 30-day gradual transition from paid to organic as pages get indexed.

## Files

| File | Location | Purpose |
|------|----------|---------|
| `advBudgetAllocator.js` | `ai-router/middleware/` | Core module — allocation engine, transitions, API routes |
| `adv-budget-page.jsx` | `ai-router/dashboard/` | Dashboard React component (4 tabs) |
| `adv_transitions.json` | `ai-router/dashboard/` | Persistent store for 30-day decay transitions (auto-created) |

## Integration Steps

### Step 1: Mount API routes in server

In `ai-orchestration-server.js.patch`, add these 2 lines:

**Line 29 (imports section):**
```javascript
const { createRoutes: createAdvBudgetRoutes } = require('./middleware/advBudgetAllocator');
```

**Line 107 (routes section), after the content priorities route:**
```javascript
app.use('/v1/adv', createAdvBudgetRoutes(dashboardPath));
```

### Step 2: Add dashboard page

In `dashboard/index.html`, add these integrations:

**A) Sidebar nav item** (under "Monitoraggio" section, after Content AI Layer):
```html
<div class="${`nav-item ${page==='adv-budget'?'active':''}`}" onclick="setPage('adv-budget')">
    <span class="icon">💰</span> ADV Allocator
</div>
```

**B) Page render condition** (in App component, after ContentAIPage):
```jsx
{page === 'adv-budget' && <ADVBudgetPage />}
```

**C) Component code**: Paste the entire contents of `adv-budget-page.jsx` before the closing `</script>` tag.

### Step 3: Deploy to Railway

```bash
cd ai-orchestration-layer
git add ai-router/middleware/advBudgetAllocator.js
git add ai-router/dashboard/adv-budget-page.jsx
git add ai-router/ADV-BUDGET-ALLOCATOR-RUNBOOK.md
git commit -m "feat: ADV Budget Allocator module — paid/organic compensator"
git push origin main
```

Railway auto-deploys on push to main.

## API Reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/v1/adv/` | No | Full allocation report |
| `GET` | `/v1/adv/allocate` | No | Full allocation report (alias) |
| `GET` | `/v1/adv/cluster/:id` | No | Single cluster allocation (A-F) |
| `GET` | `/v1/adv/transitions` | No | Active/completed transition list |
| `POST` | `/v1/adv/index-event` | X-Api-Key | Record single page indexation |
| `POST` | `/v1/adv/index-events` | X-Api-Key | Batch indexation events (max 100) |
| `PUT` | `/v1/adv/config` | X-Api-Key | Update phase/month/budget |

### Example: Full Report

```bash
curl https://your-railway-url.up.railway.app/v1/adv/allocate
```

### Example: Update to Month 3

```bash
curl -X PUT https://your-railway-url.up.railway.app/v1/adv/config \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: albeni-gsc-2026" \
  -d '{"month": 3}'
```

### Example: Record Indexation Event

```bash
curl -X POST https://your-railway-url.up.railway.app/v1/adv/index-event \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: albeni-gsc-2026" \
  -d '{"urlPath": "/struttura-cheratina-2", "site": "mu", "cluster": "A"}'
```

## GSC Integration

The `gsc_index_monitor.py` script should be extended to automatically call `/v1/adv/index-events` when it detects pages that have transitioned from NEUTRAL → PASS between scans. This closes the loop:

```
GSC Scan → detect new PASS verdicts → POST /v1/adv/index-events → transitions start decaying
```

### Integration point in gsc_index_monitor.py

After the scan comparison logic, add:

```python
# Find newly indexed pages (were NEUTRAL, now PASS)
new_indexed = []
for url, verdict in current_scan.items():
    if verdict == 'PASS' and previous_scan.get(url) != 'PASS':
        new_indexed.append({
            'urlPath': url,
            'site': site_key,  # 'mu' or 'wom'
            'cluster': classify_url(url)  # use same classification logic
        })

if new_indexed:
    requests.post(
        f'{RAILWAY_URL}/v1/adv/index-events',
        json={'events': new_indexed},
        headers={'X-Api-Key': API_KEY}
    )
```

## Architecture

```
┌─────────────────────────────────────┐
│         GSC Crawl Maps              │
│  (mu_crawl_map.json, wom_crawl_map) │
└──────────────┬──────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│     contentPrioritizer.js            │
│  (CrawlMapStore, CLUSTERS, health)   │
└──────────────┬───────────────────────┘
               │ imports
               ▼
┌──────────────────────────────────────┐
│     advBudgetAllocator.js            │
│                                      │
│  gap_score = non_idx_ratio × kw_wt   │
│  budget = normalized_gap × monthly_€  │
│  30-day linear decay on indexation    │
│                                      │
│  API: /v1/adv/*                      │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│     adv_transitions.json             │
│  (persistent decay tracker)          │
└──────────────────────────────────────┘
```

## Dashboard

The ADV Budget page has 4 tabs:

1. **Overview** — Summary cards (phase, budget, coverage, utilization) + cluster allocation bars + recommendations
2. **Cluster Detail** — Select a cluster to see per-page budget allocation with funnel multipliers
3. **Transitions** — Active 30-day decay tracker with progress bars + completed count
4. **Config** — Update current month (auto-detects phase), view phase/market reference tables
