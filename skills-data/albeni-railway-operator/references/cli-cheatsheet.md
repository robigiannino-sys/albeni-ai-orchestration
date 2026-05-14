# Railway CLI Cheatsheet — Albeni 1905

## Daily commands

| Comando | Cosa fa | Quando usarlo |
|---|---|---|
| `railway whoami` | Verifica login | Inizio sessione, dopo riavvio |
| `railway list` | Lista progetti | Per scegliere a cosa linkarsi |
| `railway status` | Mostra progetto+env+service linked nella cartella corrente | Sanity check |
| `railway link -p <name-or-id>` | Linka cartella corrente al progetto | Una volta per cartella |
| `railway logs --service <svc>` | Tail dei log | Dopo deploy, durante debug |
| `railway run --service <svc> <cmd>` | Esegue comando con env iniettata | Query DB, smoke test |
| `railway variables --service <svc> --kv` | Lista env vars in formato KEY=VALUE | Recupero URL/credenziali |

## Lifecycle

| Comando | Cosa fa |
|---|---|
| `railway init` | Crea nuovo progetto |
| `railway add` | Aggiunge service o plugin (Postgres, Redis, ecc.) |
| `railway up` | Deploy diretto (bypassa Git) |
| `railway down` | Rimuove ultimo deployment |
| `railway delete -p <id>` | Cancella progetto (irreversibile, chiede conferma nome) |
| `railway domain --service <svc> --add <domain>` | Aggiunge custom domain |

## Service management

| Comando | Cosa fa |
|---|---|
| `railway service` | Lista service del progetto linked |
| `railway service create <name>` | Crea nuovo service |
| `railway service delete <name>` | Cancella service |
| `railway environment` | Lista environment (production, staging, ecc.) |
| `railway environment new <name>` | Crea environment |

## Diagnostic / Operational

| Comando | Cosa fa |
|---|---|
| `railway logs --service <svc> --filter runtime` | Solo runtime logs (non build) |
| `railway logs --service <svc> --filter build` | Solo build logs |
| `railway shell` | Apre subshell con tutte le env vars del progetto |
| `railway connect <service>` | Apre psql/mongosh/redis-cli (richiede client locale) |
| `railway run --service <svc> printenv` | Stampa tutte le env vars (DEBUG: redact prima di condividere) |
| `railway list --json | python3 -m json.tool` | Lista in JSON con tutti i metadati |

## Pattern utili (one-liner)

### Identifica il project ID dal nome
```bash
railway list --json | python3 -c '
import json, sys
for p in json.load(sys.stdin):
    print(f"{p[\"name\"]:25s}  {p[\"id\"]}  deletedAt={p.get(\"deletedAt\")}")
'
```

### Estrai DATABASE_PUBLIC_URL
```bash
railway variables --service Postgres --kv | grep '^DATABASE_PUBLIC_URL=' | cut -d= -f2-
```

### Smoke test completo (ai-router + ml-worker + DB)
```bash
echo "=== ai-router /health ==="
curl -s https://creative-perfection-production-57b5.up.railway.app/health | python3 -m json.tool
echo "=== Dashboard metrics ==="
curl -s https://creative-perfection-production-57b5.up.railway.app/v1/dashboard/metrics | python3 -m json.tool
echo "=== Postgres count ==="
cd ai-orchestration-layer
railway run --service Postgres bash -c 'python3 -c "
import os, psycopg2
c = psycopg2.connect(os.environ[\"DATABASE_PUBLIC_URL\"]).cursor()
for t in [\"users\",\"sessions\",\"behavioral_signals\"]:
    c.execute(f\"SELECT COUNT(*) FROM {t}\")
    print(f\"  {t}: {c.fetchone()[0]}\")
"'
```

### Backup DB (export JSON via psycopg2)
```bash
railway run --service Postgres bash -c 'python3 -c "
import os, psycopg2, json, sys
c = psycopg2.connect(os.environ[\"DATABASE_PUBLIC_URL\"]).cursor()
c.execute(\"SELECT row_to_json(t) FROM users t\")
for row in c:
    print(json.dumps(row[0]))
" > /tmp/backup_users.jsonl'
```

### Watch deploy in real-time
```bash
git push origin main && railway logs --service creative-perfection
# Aspetta "Application startup complete" / "Listening on port"
```

## Errori comuni e fix

| Errore | Causa | Fix |
|---|---|---|
| `No linked project found` | Cartella non linked | `cd ai-orchestration-layer && railway link -p kind-prosperity` |
| `bash: psql: command not found` | psql non installato sul Mac | Usa Python+psycopg2 oppure `brew install libpq && brew link --force libpq` |
| `psycopg2 ModuleNotFoundError` | python3 di sistema non ha psycopg2 | `pip3 install --user --break-system-packages psycopg2-binary` poi usa `bash -c 'python3 ...'` |
| `could not translate host name "postgres.railway.internal"` | Stai usando DATABASE_URL (interna) da Mac | Usa DATABASE_PUBLIC_URL |
| `application_passwords_disabled` (su WP) | Plugin security blocca App Passwords | Usa `albeni-wp-operator` skill via CodeMirror |
| `Method Not Allowed` (405) | Endpoint richiede POST, hai fatto GET | Verifica con `curl -X POST -H 'Content-Type: application/json' -d '{...}'` |

## Quotes & Escaping (osascript context)

Quando chiami railway via AppleScript `do shell script`:
- Path con spazi: usa quote singole `'...'` o escape con `\\ `
- Doppia escaping per Python heredoc: `bash -c 'python3 -c "..."'` con triple-escape sui quotes interni
- Meglio: copia lo script in `/tmp/script.py` e chiama `python3 /tmp/script.py` (no escaping)
