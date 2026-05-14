# Google Ads API · Setup credenziali per `google_ads_spend_sync.py`

Lo script richiede 5 valori in `.env`. Sono tutti **già pre-definiti** in `ml-worker/config.py` ma vuoti:

```
GOOGLE_ADS_CUSTOMER_ID=
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_CLIENT_ID=
GOOGLE_ADS_CLIENT_SECRET=
GOOGLE_ADS_REFRESH_TOKEN=
GOOGLE_ADS_LOGIN_CUSTOMER_ID=    # opzionale, solo se l'account è sotto un MCC manager
```

I primi 5 sono **obbligatori**. Il 6° serve solo se gestisci l'account Albeni 1905 da un MCC manager (caso tipico delle agency).

---

## Step 1 · Customer ID (1 minuto)

Vai su [ads.google.com](https://ads.google.com), in alto a destra trovi l'ID account nel formato `123-456-7890`.
Nel `.env` mettilo senza trattini:

```
GOOGLE_ADS_CUSTOMER_ID=1234567890
```

Se l'account è sotto un MCC, prendi anche l'ID del manager (sempre 10 cifre senza trattini):

```
GOOGLE_ADS_LOGIN_CUSTOMER_ID=9876543210
```

---

## Step 2 · Developer Token (3-5 giorni di attesa, è il bottleneck reale)

Questo è **lo step lento**. Google deve approvarti manualmente.

1. Vai su [Google Ads → Tools → API Center](https://ads.google.com/aw/apicenter)
2. Compila il form di richiesta: descrivi l'uso (reporting/spend analytics interno per Albeni 1905, no spamming, no automated bidding aggressive)
3. Accetta i T&S
4. Google ti dà subito un token **"Test"** (funziona solo su test accounts)
5. Per il **"Basic Access"** (legge dati di produzione) submetti il form di review. Approvazione: 2-5 giorni lavorativi.
6. Quando approva, copialo:

```
GOOGLE_ADS_DEVELOPER_TOKEN=ABCdef123_xyz...
```

**Nel frattempo:** lo script gira già con un test account se vuoi testare il flusso prima dell'approvazione production.

---

## Step 3 · OAuth Client ID + Secret (10 minuti)

1. Vai su [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials)
2. Crea un nuovo project (es. "albeni-ads-sync") se non ce l'hai già
3. Abilita la **Google Ads API**: vai su Library → cerca "Google Ads API" → Enable
4. Torna su Credentials → **Create Credentials → OAuth 2.0 Client ID**
5. Tipo: **Desktop app** (più semplice di Web app per script CLI)
6. Nome: "Albeni Ads Sync"
7. Ti dà `client_id` (finisce in `.apps.googleusercontent.com`) e `client_secret`

```
GOOGLE_ADS_CLIENT_ID=123-abc.apps.googleusercontent.com
GOOGLE_ADS_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxx
```

---

## Step 4 · Refresh Token (10 minuti, una volta sola)

Il refresh token è ciò che permette allo script di rinnovare l'access token automaticamente senza login interattivo. Si genera UNA VOLTA.

**Metodo facile · OAuth 2.0 Playground:**

1. Vai su [OAuth 2.0 Playground](https://developers.google.com/oauthplayground)
2. Ingranaggio in alto a destra → spunta **"Use your own OAuth credentials"** → incolla `client_id` + `client_secret` di Step 3
3. Nella sinistra, **Step 1**: Scopes → input box → digita `https://www.googleapis.com/auth/adwords` → Authorize APIs
4. Login con l'account Google che ha accesso all'account Ads Albeni
5. **Step 2**: clicca "Exchange authorization code for tokens"
6. Copia il **Refresh token** (NON l'access token, quello scade in 1 ora)

```
GOOGLE_ADS_REFRESH_TOKEN=1//0xxxxxxxxxxxxxxxxxx
```

---

## Step 5 · Test (1 minuto)

```bash
cd "/Users/roberto/Desktop/ALBENI/albeni.com/STEFANO/AI STACK APP/ai-orchestration-layer"

# Dry-run: pulla ma non POSTa, mostra payload + totali
python3 scripts/google_ads_spend_sync.py --since 2026-05-13 --until 2026-05-13 --dry-run --verbose

# Se vedi righe e totale spend coerente → live
python3 scripts/google_ads_spend_sync.py --since 2026-05-13 --until 2026-05-13
```

Verifica che siano arrivati al DB:

```bash
curl -s "https://albeni-ai-orchestration-production.up.railway.app/v1/adv/spend/summary?days=7&channel=google_ads" \
  | python3 -m json.tool
```

---

## Step 6 · Schedule daily (1 minuto)

Una volta validato il sync manuale, schedula. Due opzioni:

**Opzione A · cron Mac (sempre)**

```
crontab -e
```

Aggiungi:

```
# Albeni · Google Ads spend sync giornaliero alle 06:00 (Europe/Rome)
0 6 * * * cd "/Users/roberto/Desktop/ALBENI/albeni.com/STEFANO/AI STACK APP/ai-orchestration-layer" && /usr/bin/python3 scripts/google_ads_spend_sync.py >> /tmp/google_ads_sync.log 2>&1
```

Il cron pulla ieri (default), quindi alle 6:00 di oggi si scrivono i dati di ieri.

**Opzione B · Cowork scheduled task** (parte solo se hai la sessione Cowork aperta)

Chiedimi: "schedula google_ads_spend_sync ogni giorno alle 6" e te lo creo come scheduled task interno.

---

## Backfill iniziale

Per popolare lo storico (es. ultimi 90 giorni) **una volta sola** dopo aver completato Step 1-5:

```bash
python3 scripts/google_ads_spend_sync.py --since 2026-02-14 --until 2026-05-13 --verbose
```

Lo script gestisce automaticamente la paginazione fino a 50 pagine × 1000 righe = 50k campagne/giorno. Per Albeni siamo ben sotto.

---

## Troubleshooting

| Errore | Causa probabile | Fix |
|---|---|---|
| `OAuth refresh failed: HTTP 400` | refresh_token scaduto o revocato | Rigenera (Step 4) |
| `HTTP 401: PERMISSION_DENIED` | developer_token non ancora approvato per Basic Access | Aspetta approvazione (Step 2) o usa test account |
| `HTTP 403: customer not found` | customer_id sbagliato o l'utente OAuth non ha accesso | Verifica Step 1 + che l'account OAuth abbia visibilità su quel customer |
| `INVALID_LOGIN_CUSTOMER_ID` | L'account è sotto un MCC ma non hai settato GOOGLE_ADS_LOGIN_CUSTOMER_ID | Aggiungilo al `.env` |
| Currency non-EUR nei log | Il customer Google Ads è settato in USD/GBP/etc | Aggiungere FX conversion in `to_batch_payload()` (TODO marker già nel codice) |
