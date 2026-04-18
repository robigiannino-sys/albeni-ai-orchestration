# Approval Dashboard Generator

Local Python tool (not a deployed service) that queries Notion for pending briefs and produces a single self-contained HTML with deployed-page previews + one-click Approve/Archive buttons wired to the `approval-webhook` Railway service.

## Setup

```bash
cd tools/dashboard-generator
cp .env.example .env
# fill NOTION_TOKEN, WEBHOOK_URL, WEBHOOK_SECRET
pip install -r requirements.txt
```

## Usage

```bash
python generate.py --open
```

- Queries Notion for all `[NEWS]` entries with `Stato = "Da Fare"`
- Renders each brief as a card showing: hero image, editorial title, incipit, narrative angle, cluster map, keyword bridge
- Embeds the webhook URL and shared secret into the HTML
- Writes `dashboard/approval-dashboard.html`
- `--open` launches it in your default browser

## Output

Each brief card has:
- **✅ Approva & Deploy** → POST `/approve` → Stato "In Produzione" → polling task deploys within 30 min
- **🗄️ Archivia** → POST `/archive` → Stato "Archiviato" (with optional reason)

## Security

The generated HTML contains `WEBHOOK_SECRET`. Do not share the file — treat it as a credential. The secret stays out of Git via `.gitignore`.

## Troubleshooting

- **Empty dashboard**: check that the integration is connected to the Content Pipeline database in Notion (page ⋯ → Connections → Add connection → Albeni AI Stack)
- **Buttons fail with "Failed to fetch"**: verify `curl $WEBHOOK_URL/health` returns `{"ok":true,...}`
- **401 unauthorized**: secrets don't match between `.env` (generator) and Railway variables (webhook)
