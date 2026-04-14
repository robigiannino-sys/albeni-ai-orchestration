# Approval Webhook

Part of the Albeni 1905 AI Orchestration Layer. Accepts approve/archive actions from the local Merino News approval dashboard HTML and updates the Notion Content Pipeline accordingly.

## Endpoints

| Method | Path       | Auth        | Purpose                                     |
|--------|------------|-------------|---------------------------------------------|
| GET    | `/health`  | none        | Liveness probe (used by Railway + monorepo) |
| POST   | `/approve` | `X-Webhook-Secret` | Sets Stato → "In Produzione"          |
| POST   | `/archive` | `X-Webhook-Secret` | Sets Stato → "Archiviato"             |
| GET    | `/pending` | `X-Webhook-Secret` | Lists Da Fare briefs                   |

## Flow

```
Merino News Scanner (7am)
         ↓ brief with Stato="Da Fare" in Notion

[user]  python tools/dashboard-generator/generate.py --open
         ↓ dashboard.html in browser

[user]  click ✅ Approva / 🗄️ Archivia
         ↓ POST /approve or /archive

approval-webhook (this service)
         ↓ Notion API update Stato

notion-approval-deployer (scheduled task, 30min polling)
         ↓ reads "In Produzione" entries
         ↓ invokes wom-page-deployer / mu-content-deployer
         ↓ page deployed to WoM/MU
```

## Deploy (Railway)

Reuses the monorepo's `railway-setup.sh`. See root README for the unified flow.

Required env vars (via `railway variables set`):

```
NOTION_TOKEN
NOTION_DB_ID
WEBHOOK_SECRET
ALLOWED_ORIGINS
```

## Local dev

```bash
cp .env.example .env  # fill in real values
npm install
npm run dev
curl http://localhost:3001/health
```
