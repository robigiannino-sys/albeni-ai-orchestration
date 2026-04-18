/**
 * ADV Budget Allocator — Dashboard Component
 * Renders in the AI Orchestration Control Tower sidebar
 *
 * Tabs:
 *   1. Overview — cluster allocation donut + summary stats
 *   2. Detail — per-cluster page-level allocation table
 *   3. Transitions — 30-day decay tracker
 *   4. Config — phase/month/budget settings
 *
 * Paste this component BEFORE the closing </script> tag in dashboard/index.html.
 * Add sidebar nav item under "Monitoraggio" section.
 */

function ADVBudgetPage() {
  const [report, setReport] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [activeTab, setActiveTab] = React.useState('overview');
  const [selectedCluster, setSelectedCluster] = React.useState(null);

  // Config form state
  const [configMonth, setConfigMonth] = React.useState(1);
  const [configSaving, setConfigSaving] = React.useState(false);

  React.useEffect(() => { loadReport(); }, []);

  async function loadReport() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/v1/adv/allocate');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setReport(data);
      setConfigMonth(data.config.currentMonth);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function updateConfig() {
    setConfigSaving(true);
    try {
      const res = await fetch('/v1/adv/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-Api-Key': 'albeni-gsc-2026' },
        body: JSON.stringify({ month: configMonth }),
      });
      if (res.ok) await loadReport();
    } catch (e) {
      console.error('Config update failed:', e);
    } finally {
      setConfigSaving(false);
    }
  }

  if (loading) return React.createElement('div', { style: { padding: 40, textAlign: 'center' } },
    React.createElement('div', { className: 'spinner' }), ' Loading ADV allocation...'
  );

  if (error) return React.createElement('div', { style: { padding: 40, color: '#e74c3c' } },
    '❌ Error: ' + error
  );

  if (!report) return null;

  const { config, global: g, clusters, transitions, recommendations } = report;

  // Color palette for clusters
  const clusterColors = { A: '#3498db', B: '#2ecc71', C: '#e67e22', D: '#e74c3c', E: '#9b59b6', F: '#1abc9c' };

  // --- TAB: Overview ---
  function renderOverview() {
    const clusterList = Object.values(clusters).sort((a, b) => b.gapScore - a.gapScore);

    return React.createElement('div', null,
      // Summary cards
      React.createElement('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 } },
        renderCard('Phase', `${config.currentPhase} — ${config.phaseLabel}`, `Month ${config.currentMonth}/18`),
        renderCard('Budget', `€${config.effectiveBudget.toLocaleString()}`, `Base €${config.baseBudget} + €${config.freedBudget} freed`),
        renderCard('Coverage', `${g.totalNonIndexed} non-indexed`, `${g.globalIndexRate}% index rate`),
        renderCard('Utilization', `${g.budgetUtilization}%`, `€${g.totalAllocated.toFixed(0)} allocated`)
      ),

      // Cluster allocation bars
      React.createElement('h3', { style: { marginBottom: 12 } }, 'Cluster Allocation'),
      React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 8 } },
        clusterList.map(c =>
          React.createElement('div', {
            key: c.id,
            style: { display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer', padding: '8px 12px', borderRadius: 8, background: selectedCluster === c.id ? '#f0f4ff' : 'transparent' },
            onClick: () => { setSelectedCluster(c.id); setActiveTab('detail'); }
          },
            React.createElement('span', { style: { width: 32, fontWeight: 700, color: clusterColors[c.id] || '#666' } }, c.id),
            React.createElement('span', { style: { width: 160, fontSize: 13 } }, c.name),
            React.createElement('div', { style: { flex: 1, background: '#e8e8e8', borderRadius: 4, height: 24, position: 'relative', overflow: 'hidden' } },
              React.createElement('div', {
                style: {
                  width: `${c.normalizedGap * 100}%`,
                  background: clusterColors[c.id] || '#666',
                  height: '100%', borderRadius: 4,
                  minWidth: c.monthlyBudget > 0 ? 4 : 0,
                }
              }),
              React.createElement('span', { style: { position: 'absolute', right: 8, top: 3, fontSize: 12, fontWeight: 600 } },
                `€${c.monthlyBudget.toFixed(0)}/mo`
              )
            ),
            React.createElement('span', { style: { width: 80, textAlign: 'right', fontSize: 12, color: '#888' } },
              `${c.nonIndexedPages} gaps`
            )
          )
        )
      ),

      // Recommendations
      recommendations.length > 0 && React.createElement('div', { style: { marginTop: 24 } },
        React.createElement('h3', { style: { marginBottom: 12 } }, 'Recommendations'),
        recommendations.map((r, i) =>
          React.createElement('div', {
            key: i,
            style: { padding: '12px 16px', marginBottom: 8, borderRadius: 8, background: r.priority === 'P0' ? '#fff3f3' : r.priority === 'P1' ? '#fff8e1' : '#f0f4ff', borderLeft: `4px solid ${r.priority === 'P0' ? '#e74c3c' : r.priority === 'P1' ? '#f39c12' : '#3498db'}` }
          },
            React.createElement('div', { style: { fontWeight: 600, fontSize: 13, marginBottom: 4 } },
              React.createElement('span', { style: { marginRight: 8, fontSize: 11, padding: '2px 6px', borderRadius: 4, background: '#eee' } }, r.priority),
              r.title
            ),
            React.createElement('div', { style: { fontSize: 12, color: '#555', marginBottom: 4 } }, r.detail),
            React.createElement('div', { style: { fontSize: 12, color: '#333', fontStyle: 'italic' } }, '→ ' + r.action)
          )
        )
      )
    );
  }

  // --- TAB: Detail ---
  function renderDetail() {
    const cluster = selectedCluster ? clusters[selectedCluster] : Object.values(clusters).sort((a, b) => b.gapScore - a.gapScore)[0];
    if (!cluster) return React.createElement('div', null, 'No cluster data');

    return React.createElement('div', null,
      // Cluster selector
      React.createElement('div', { style: { display: 'flex', gap: 8, marginBottom: 16 } },
        Object.keys(clusters).map(id =>
          React.createElement('button', {
            key: id,
            onClick: () => setSelectedCluster(id),
            style: {
              padding: '6px 16px', borderRadius: 6, border: 'none', cursor: 'pointer',
              background: (selectedCluster || Object.keys(clusters)[0]) === id ? (clusterColors[id] || '#666') : '#e8e8e8',
              color: (selectedCluster || Object.keys(clusters)[0]) === id ? '#fff' : '#333',
              fontWeight: 600, fontSize: 13,
            }
          }, id)
        )
      ),

      // Cluster header
      React.createElement('div', { style: { background: '#f8f9fa', padding: 16, borderRadius: 8, marginBottom: 16 } },
        React.createElement('h3', { style: { margin: 0 } }, `Cluster ${cluster.id} — ${cluster.name}`),
        React.createElement('div', { style: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginTop: 12 } },
          renderMini('Budget', `€${cluster.monthlyBudget.toFixed(0)}/mo`),
          renderMini('Index Rate', `${cluster.indexRate}%`),
          renderMini('Gap Score', cluster.gapScore.toFixed(4)),
          renderMini('Avg/Page', `€${cluster.perPageAvg.toFixed(2)}`)
        )
      ),

      // Page table
      React.createElement('table', { style: { width: '100%', borderCollapse: 'collapse', fontSize: 13 } },
        React.createElement('thead', null,
          React.createElement('tr', { style: { borderBottom: '2px solid #ddd', textAlign: 'left' } },
            ['Path', 'Site', 'Lang', 'Funnel', 'Multiplier', '€/month'].map(h =>
              React.createElement('th', { key: h, style: { padding: '8px 12px', fontWeight: 600 } }, h)
            )
          )
        ),
        React.createElement('tbody', null,
          (cluster.nonIndexedUrls || []).map((page, i) =>
            React.createElement('tr', { key: i, style: { borderBottom: '1px solid #eee' } },
              React.createElement('td', { style: { padding: '6px 12px', fontFamily: 'monospace', fontSize: 12 } }, page.path),
              React.createElement('td', { style: { padding: '6px 12px' } },
                React.createElement('span', { style: { padding: '2px 6px', borderRadius: 4, background: page.site === 'mu' ? '#e8f4fd' : '#e8fdf4', fontSize: 11 } }, page.site.toUpperCase())
              ),
              React.createElement('td', { style: { padding: '6px 12px' } }, page.lang.toUpperCase()),
              React.createElement('td', { style: { padding: '6px 12px' } }, page.funnelType.toUpperCase()),
              React.createElement('td', { style: { padding: '6px 12px' } }, page.funnelMultiplier + '×'),
              React.createElement('td', { style: { padding: '6px 12px', fontWeight: 600 } }, '€' + page.monthlyBudget.toFixed(2))
            )
          )
        )
      ),

      (cluster.nonIndexedUrls || []).length === 0 &&
        React.createElement('div', { style: { padding: 24, textAlign: 'center', color: '#888' } },
          '✅ All pages in this cluster are indexed — no paid allocation needed'
        )
    );
  }

  // --- TAB: Transitions ---
  function renderTransitions() {
    const { active, completed } = transitions;

    return React.createElement('div', null,
      React.createElement('h3', { style: { marginBottom: 12 } }, `Active Transitions (${active.length})`),

      active.length === 0
        ? React.createElement('div', { style: { padding: 24, textAlign: 'center', color: '#888' } }, 'No active transitions')
        : React.createElement('table', { style: { width: '100%', borderCollapse: 'collapse', fontSize: 13 } },
            React.createElement('thead', null,
              React.createElement('tr', { style: { borderBottom: '2px solid #ddd', textAlign: 'left' } },
                ['Page', 'Site', 'Cluster', 'Indexed', 'Day', 'Remaining', 'Progress'].map(h =>
                  React.createElement('th', { key: h, style: { padding: '8px 12px' } }, h)
                )
              )
            ),
            React.createElement('tbody', null,
              active.map((t, i) =>
                React.createElement('tr', { key: i, style: { borderBottom: '1px solid #eee' } },
                  React.createElement('td', { style: { padding: '6px 12px', fontFamily: 'monospace', fontSize: 12 } }, t.urlPath),
                  React.createElement('td', { style: { padding: '6px 12px' } }, t.site.toUpperCase()),
                  React.createElement('td', { style: { padding: '6px 12px' } }, t.cluster),
                  React.createElement('td', { style: { padding: '6px 12px', fontSize: 12 } }, t.indexedDate.split('T')[0]),
                  React.createElement('td', { style: { padding: '6px 12px' } }, `${t.daysSinceIndexed}/30`),
                  React.createElement('td', { style: { padding: '6px 12px', fontWeight: 600 } }, `€${t.remainingBudget.toFixed(2)}`),
                  React.createElement('td', { style: { padding: '6px 12px', width: 120 } },
                    React.createElement('div', { style: { background: '#e8e8e8', borderRadius: 4, height: 8, overflow: 'hidden' } },
                      React.createElement('div', { style: { width: `${(t.daysSinceIndexed / 30) * 100}%`, background: '#2ecc71', height: '100%', borderRadius: 4 } })
                    )
                  )
                )
              )
            )
          ),

      React.createElement('div', { style: { marginTop: 24, padding: 16, background: '#f8f9fa', borderRadius: 8, fontSize: 13 } },
        React.createElement('strong', null, `Completed transitions: ${completed}`),
        React.createElement('span', { style: { marginLeft: 16, color: '#888' } },
          `Budget freed this cycle: €${transitions.totalFreed.toFixed(2)}`
        )
      )
    );
  }

  // --- TAB: Config ---
  function renderConfig() {
    return React.createElement('div', { style: { maxWidth: 480 } },
      React.createElement('h3', { style: { marginBottom: 16 } }, 'Budget Configuration'),

      React.createElement('div', { style: { marginBottom: 16 } },
        React.createElement('label', { style: { display: 'block', fontWeight: 600, marginBottom: 4, fontSize: 13 } }, 'Current Month (1-18)'),
        React.createElement('input', {
          type: 'number', min: 1, max: 18, value: configMonth,
          onChange: (e) => setConfigMonth(parseInt(e.target.value) || 1),
          style: { padding: '8px 12px', borderRadius: 6, border: '1px solid #ddd', width: 100 }
        }),
        React.createElement('span', { style: { marginLeft: 12, fontSize: 12, color: '#888' } },
          `→ Phase ${configMonth <= 6 ? 1 : configMonth <= 12 ? 2 : 3} (${configMonth <= 6 ? 'Paid-First' : configMonth <= 12 ? 'Hybrid' : 'Organic-Led'})`
        )
      ),

      React.createElement('button', {
        onClick: updateConfig,
        disabled: configSaving,
        style: { padding: '10px 24px', borderRadius: 6, border: 'none', background: '#3498db', color: '#fff', fontWeight: 600, cursor: 'pointer' }
      }, configSaving ? 'Saving...' : 'Update Config'),

      // Phase reference
      React.createElement('div', { style: { marginTop: 32 } },
        React.createElement('h4', { style: { marginBottom: 8 } }, 'Phase Reference'),
        React.createElement('table', { style: { width: '100%', borderCollapse: 'collapse', fontSize: 13 } },
          React.createElement('thead', null,
            React.createElement('tr', { style: { borderBottom: '2px solid #ddd' } },
              ['Phase', 'Months', 'Monthly €', 'Total €', 'Strategy'].map(h =>
                React.createElement('th', { key: h, style: { padding: '8px 12px', textAlign: 'left' } }, h)
              )
            )
          ),
          React.createElement('tbody', null,
            [
              { p: 1, m: 'M1-M6', mo: '€2,500', tot: '€15,000', s: 'Paid-First' },
              { p: 2, m: 'M7-M12', mo: '€1,667', tot: '€10,000', s: 'Hybrid' },
              { p: 3, m: 'M13-M18', mo: '€833', tot: '€5,000', s: 'Organic-Led' },
            ].map(row =>
              React.createElement('tr', { key: row.p, style: { borderBottom: '1px solid #eee', background: config.currentPhase === row.p ? '#f0f4ff' : 'transparent' } },
                React.createElement('td', { style: { padding: '6px 12px', fontWeight: 600 } }, row.p),
                React.createElement('td', { style: { padding: '6px 12px' } }, row.m),
                React.createElement('td', { style: { padding: '6px 12px' } }, row.mo),
                React.createElement('td', { style: { padding: '6px 12px' } }, row.tot),
                React.createElement('td', { style: { padding: '6px 12px' } }, row.s)
              )
            )
          )
        )
      ),

      // Market allocation
      React.createElement('div', { style: { marginTop: 24 } },
        React.createElement('h4', { style: { marginBottom: 8 } }, 'Market Allocation'),
        Object.entries(report.markets).map(([mkt, data]) =>
          React.createElement('div', { key: mkt, style: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 } },
            React.createElement('span', { style: { width: 40, fontWeight: 600 } }, mkt),
            React.createElement('div', { style: { flex: 1, background: '#e8e8e8', borderRadius: 4, height: 16, overflow: 'hidden' } },
              React.createElement('div', { style: { width: `${data.pct * 100}%`, background: '#3498db', height: '100%', borderRadius: 4 } })
            ),
            React.createElement('span', { style: { width: 80, textAlign: 'right', fontSize: 12 } }, `€${data.budget.toLocaleString()} (${(data.pct * 100).toFixed(0)}%)`)
          )
        )
      )
    );
  }

  // Helper: summary card
  function renderCard(title, value, subtitle) {
    return React.createElement('div', { style: { background: '#f8f9fa', padding: 16, borderRadius: 8 } },
      React.createElement('div', { style: { fontSize: 12, color: '#888', marginBottom: 4 } }, title),
      React.createElement('div', { style: { fontSize: 20, fontWeight: 700 } }, value),
      React.createElement('div', { style: { fontSize: 11, color: '#aaa', marginTop: 2 } }, subtitle)
    );
  }

  // Helper: mini stat
  function renderMini(label, value) {
    return React.createElement('div', null,
      React.createElement('div', { style: { fontSize: 11, color: '#888' } }, label),
      React.createElement('div', { style: { fontSize: 16, fontWeight: 600 } }, value)
    );
  }

  // --- TAB BAR ---
  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'detail', label: 'Cluster Detail' },
    { id: 'transitions', label: 'Transitions' },
    { id: 'config', label: 'Config' },
  ];

  return React.createElement('div', { style: { padding: 24 } },
    React.createElement('h2', { style: { marginBottom: 4 } }, '💰 ADV Budget Allocator'),
    React.createElement('p', { style: { color: '#888', fontSize: 13, marginBottom: 20 } },
      'Paid/Organic Compensator — allocates ADV budget to non-indexed pages, shifts to organic as pages get crawled.'
    ),

    // Tab bar
    React.createElement('div', { style: { display: 'flex', gap: 4, marginBottom: 20, borderBottom: '2px solid #eee', paddingBottom: 0 } },
      tabs.map(tab =>
        React.createElement('button', {
          key: tab.id,
          onClick: () => setActiveTab(tab.id),
          style: {
            padding: '8px 20px', border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
            borderBottom: activeTab === tab.id ? '2px solid #3498db' : '2px solid transparent',
            color: activeTab === tab.id ? '#3498db' : '#888',
            background: 'transparent', marginBottom: -2,
          }
        }, tab.label)
      ),
      // Refresh button
      React.createElement('button', {
        onClick: loadReport,
        style: { marginLeft: 'auto', padding: '6px 12px', border: '1px solid #ddd', borderRadius: 6, cursor: 'pointer', fontSize: 12, background: '#fff' }
      }, '🔄 Refresh')
    ),

    // Tab content
    activeTab === 'overview' && renderOverview(),
    activeTab === 'detail' && renderDetail(),
    activeTab === 'transitions' && renderTransitions(),
    activeTab === 'config' && renderConfig()
  );
}
