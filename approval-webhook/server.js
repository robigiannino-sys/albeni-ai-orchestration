// ============================================================================
// Albeni 1905 — Approval Webhook Service
// ----------------------------------------------------------------------------
// Accepts POST requests from the local approval dashboard HTML and updates
// the Notion Content Pipeline "Stato" property accordingly. The
// `notion-approval-deployer` polling task (every 30min) picks up entries
// set to "In Produzione" and triggers the wp/mu deploy skills.
//
// Endpoints:
//   POST /approve  — sets Stato = "In Produzione"
//   POST /archive  — sets Stato = "Archiviato"
//   GET  /health   — liveness probe (matches monorepo convention)
//   GET  /pending  — lists current "Da Fare" briefs (dashboard sync)
//
// Security:
//   Write endpoints require header `X-Webhook-Secret: $WEBHOOK_SECRET`.
// ============================================================================

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const { Client } = require('@notionhq/client');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3001;
const NOTION_TOKEN = process.env.NOTION_TOKEN;
const NOTION_DB_ID = process.env.NOTION_DB_ID;
const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET;
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || '*')
  .split(',')
  .map(s => s.trim());

if (!NOTION_TOKEN || !NOTION_DB_ID || !WEBHOOK_SECRET) {
  console.error('[FATAL] Missing required env vars: NOTION_TOKEN, NOTION_DB_ID, WEBHOOK_SECRET');
  process.exit(1);
}

const notion = new Client({ auth: NOTION_TOKEN });

// ---------- middleware ----------
app.use(helmet());
app.use(morgan('combined'));
app.use(express.json({ limit: '100kb' }));
app.use(cors({
  origin: ALLOWED_ORIGINS.includes('*') ? true : ALLOWED_ORIGINS,
  methods: ['GET', 'POST', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'X-Webhook-Secret'],
}));

function requireSecret(req, res, next) {
  const incoming = req.header('X-Webhook-Secret');
  if (incoming !== WEBHOOK_SECRET) {
    return res.status(401).json({ ok: false, error: 'unauthorized' });
  }
  next();
}

// ---------- helpers ----------
async function setStato(pageId, statoValue) {
  return notion.pages.update({
    page_id: pageId,
    properties: {
      Stato: { select: { name: statoValue } },
    },
  });
}

async function appendComment(pageId, text) {
  try {
    await notion.comments.create({
      parent: { page_id: pageId },
      rich_text: [{ type: 'text', text: { content: text } }],
    });
  } catch (e) {
    console.warn('[warn] comment append failed:', e.message);
  }
}

// ---------- endpoints ----------
app.get('/health', (_req, res) => {
  res.json({
    ok: true,
    service: 'approval-webhook',
    ts: new Date().toISOString(),
    uptime_s: Math.round(process.uptime()),
  });
});

app.post('/approve', requireSecret, async (req, res) => {
  const { pageId, actor } = req.body || {};
  if (!pageId) return res.status(400).json({ ok: false, error: 'pageId required' });

  try {
    await setStato(pageId, 'In Produzione');
    await appendComment(
      pageId,
      `✅ Approved via dashboard${actor ? ` (${actor})` : ''} at ${new Date().toISOString()}. ` +
      `Stato → "In Produzione". Approval deployer will pick it up at next polling cycle (≤30min).`,
    );
    console.log(`[approve] ${pageId}`);
    res.json({ ok: true, action: 'approve', pageId, newStato: 'In Produzione' });
  } catch (e) {
    console.error('[approve error]', e);
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.post('/archive', requireSecret, async (req, res) => {
  const { pageId, actor, reason } = req.body || {};
  if (!pageId) return res.status(400).json({ ok: false, error: 'pageId required' });

  try {
    await setStato(pageId, 'Archiviato');
    await appendComment(
      pageId,
      `🗄️ Archived via dashboard${actor ? ` (${actor})` : ''} at ${new Date().toISOString()}.` +
      (reason ? ` Reason: ${reason}` : ''),
    );
    console.log(`[archive] ${pageId}${reason ? ' — ' + reason : ''}`);
    res.json({ ok: true, action: 'archive', pageId, newStato: 'Archiviato' });
  } catch (e) {
    console.error('[archive error]', e);
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.get('/pending', requireSecret, async (_req, res) => {
  try {
    const q = await notion.databases.query({
      database_id: NOTION_DB_ID,
      filter: {
        and: [
          { property: 'Stato', select: { equals: 'Da Fare' } },
          { property: 'Contenuto', title: { starts_with: '[NEWS]' } },
        ],
      },
      sorts: [{ timestamp: 'created_time', direction: 'descending' }],
      page_size: 100,
    });
    res.json({
      ok: true,
      count: q.results.length,
      items: q.results.map(p => ({
        id: p.id,
        url: p.url,
        title: (p.properties.Contenuto?.title?.[0]?.plain_text) || '(untitled)',
        dominio: p.properties.Dominio?.select?.name,
        tipo: p.properties['Tipo Contenuto']?.select?.name,
        cluster: p.properties.Cluster?.select?.name,
        keyword: p.properties['Keyword Target']?.rich_text?.[0]?.plain_text,
        note: p.properties.Note?.rich_text?.[0]?.plain_text,
        created: p.created_time,
      })),
    });
  } catch (e) {
    console.error('[pending error]', e);
    res.status(500).json({ ok: false, error: e.message });
  }
});

// ---------- boot ----------
app.listen(PORT, () => {
  console.log(`[ready] approval-webhook listening on :${PORT}`);
  console.log(`        allowed origins: ${ALLOWED_ORIGINS.join(', ')}`);
});
