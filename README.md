# AI Orchestration Layer - Albeni 1905

Il "cervello" centrale dell'ecosistema digitale Invisible Luxury, che coordina i quattro domini attraverso una logica basata sull'intento dell'utente.

## Architettura

```
                    ┌──────────────────────────────────────┐
                    │        JavaScript Snippet             │
                    │  (WordPress + Shopify - 4 domini)     │
                    └──────────────┬───────────────────────┘
                                   │
                    ┌──────────────▼───────────────────────┐
                    │     AI Router (Node.js/Express)       │
                    │     Port: 3000                        │
                    │  - Tracking ingestion                 │
                    │  - Cross-domain routing (<120ms)      │
                    │  - Bot protection (Pay-as-you-crawl)  │
                    │  - C2PA digital fingerprinting        │
                    └──────────────┬───────────────────────┘
                                   │
                    ┌──────────────▼───────────────────────┐
                    │     ML Worker (Python/FastAPI)        │
                    │     Port: 8000                        │
                    │  - IDS Calculator (0-100)             │
                    │  - Cluster Predictor (5 clusters)     │
                    │  - Content Generator (70/30)          │
                    │  - Klaviyo CRM Sync                   │
                    │  - SEO Monitor (85/15)                │
                    └───────┬──────────────┬───────────────┘
                            │              │
              ┌─────────────▼──┐   ┌───────▼──────────────┐
              │  PostgreSQL    │   │  Redis               │
              │  Port: 5432   │   │  Port: 6379          │
              │  (Persistenza)│   │  (Cache <120ms)      │
              └───────────────┘   └──────────────────────┘
```

## Quick Start

### 1. Configurazione
```bash
cp .env.example .env
# Modifica .env con le tue API key (OpenAI, Klaviyo, GA4)
```

### 2. Avvio con Docker Compose
```bash
docker-compose up -d
```

### 3. Verifica
```bash
# Health check ML Worker
curl http://localhost:8000/health

# Health check AI Router
curl http://localhost:3000/health

# Dashboard
open http://localhost:8000/dashboard
```

## Endpoint API

### Behavioral & Intent API
| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| POST | `/v1/track/event` | Ingestione segnali comportamentali |
| POST | `/v1/intent/calculate` | Calcolo Intent Depth Score |
| POST | `/v1/cluster/predict` | Predizione cluster comportamentale |
| GET  | `/v1/router/assign` | Routing cross-dominio |
| GET  | `/v1/router/status` | Stato routing utente |

### Content & CRM API
| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| POST | `/v1/content/generate` | Generazione contenuti AI (70/30) |
| POST | `/v1/crm/sync-lead` | Sincronizzazione Klaviyo |
| POST | `/v1/crm/trigger-flow` | Trigger flusso email manuale |
| POST | `/v1/crm/unboxing` | Trigger post-acquisto (QR code) |
| POST | `/v1/ml/process-intent` | Pipeline completa: IDS + Content + Klaviyo |

### Monitoring API
| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET | `/v1/seo/health` | Health check SEO (85/15, cannibalization) |
| GET | `/v1/dashboard/metrics` | Metriche aggregate per dashboard |
| GET | `/health` | System health check |

## Domini Ecosistema

| Dominio | Ruolo | IDS Range |
|---------|-------|-----------|
| worldofmerino.com | TOFU - Lifestyle & Discovery | 0-30 |
| merinouniversity.com | MOFU - Technical Authority | 31-65 |
| perfectmerinoshirt.com | BOFU - Product (Tech clusters) | >65 |
| albeni1905.com | BOFU - Brand Store (Heritage clusters) | >65 |

## 5 Cluster Comportamentali

1. **Business Professional** - Performance sotto blazer, viaggi, efficienza
2. **Heritage Mature** - Investimento, qualita permanente, tradizione
3. **Conscious Premium** - Sostenibilita, etica, certificazione ZQ
4. **Modern Minimalist** - Design pulito, capsule wardrobe, essenziale
5. **Italian Authentic** - Made in Italy, comfort termico, artigianalita

## Formula IDS

```
IDS = (T_norm * 0.20) + (S_norm * 0.20) + (I_norm * 0.40) + (R_norm * 0.20)

T = Dwell Time (target >60s)
S = Scroll Depth (25/50/75/90%)
I = Technical Interactions (comparazioni, download, video)
R = Return Frequency (sessioni in 72h)
```

## Soglie CPA

| Livello | Range | Azione |
|---------|-------|--------|
| Verde | CPA <= 9 EUR | Scalabilita massima |
| Giallo | CPA 10-15 EUR | Ottimizzazione continua |
| Rosso | CPA > 15 EUR | Sospensione campagne |

## Installazione Snippet JS

Inserire `snippets/tracking.js` nel `<head>` di tutti i siti dell'ecosistema.
Aggiungere le classi CSS agli elementi interattivi:
- `.btn-compare` - Pulsanti comparazione pesi
- `.video-material` - Video Material Science
- `.download-lead-magnet` - Download lead magnet
- `.add-to-cart` - Pulsante aggiungi al carrello
- `[data-ai-track="X"]` - Tracking personalizzato

## Stack Tecnologico

- **Python 3.10** + FastAPI (ML Worker)
- **Node.js 18** + Express (AI Router)
- **PostgreSQL 15** (Persistenza)
- **Redis 7** (Caching)
- **OpenAI GPT-4o** (Content generation)
- **Klaviyo API** (CRM)
- **Docker Compose** (Orchestrazione)
