/**
 * Albeni 1905 — Behavioral Engine v2
 * ============================================================
 * Layer 2 del sistema adattivo: IDS calculation + Cluster detection
 * + Content Personalization + Klaviyo CRM sync trigger.
 *
 * DIPENDENZA: deve essere caricato DOPO albeni-ai-tracker.js
 *
 * Installazione WordPress (tutti e 3 i domini attivi):
 *   worldofmerino.com     (TOFU)
 *   merinouniversity.com  (MOFU)
 *   perfectmerinoshirt.com (BOFU tecnico)
 *
 * Configurazione minima nell'<head> PRIMA di questo script:
 *   <script>
 *     window.ALBENI_AI = {
 *       endpoint: 'https://<ml-worker-public-url>:8000',
 *       klaviyoEndpoint: 'https://<ai-router-public-url>:3000',
 *       domain_type: 'tofu' | 'mofu' | 'bofu_tech',
 *       debug: false
 *     };
 *   </script>
 *
 * Architettura:
 *   IDS formula: T×0.2 + S×0.2 + I×0.4 + R×0.2  (scala 0-100)
 *   T = dwell time score
 *   S = scroll depth score
 *   I = interaction/intent signals
 *   R = return visit score
 *
 *   IDS thresholds:
 *   < 30  → TOFU (educazione)
 *   30-54 → MOFU (considerazione)
 *   55-64 → BOFU soft (valutazione)
 *   ≥ 65  → BOFU hot → Klaviyo sync trigger
 * ============================================================
 */

(function () {
  'use strict';

  const CONFIG      = window.ALBENI_AI || {};
  const ENDPOINT    = CONFIG.endpoint || 'http://localhost:8000';
  const ROUTER_URL  = CONFIG.klaviyoEndpoint || 'http://localhost:3000';
  const DOMAIN_TYPE = CONFIG.domain_type || _inferDomainType();
  const DEBUG       = CONFIG.debug || false;

  function log(...args) {
    if (DEBUG) console.log('[Albeni BE]', ...args);
  }

  // ============================================================
  // 0. DOMAIN TYPE INFERENCE (fallback if not configured)
  // ============================================================
  function _inferDomainType() {
    const h = window.location.hostname;
    if (h.includes('worldofmerino'))      return 'tofu';
    if (h.includes('merinouniversity'))   return 'mofu';
    if (h.includes('perfectmerino'))      return 'bofu_tech';
    return 'tofu'; // safe fallback
  }

  // ============================================================
  // 1. SESSION STATE  — accumulates IDS ingredients
  // ============================================================
  const STATE = {
    visitorId:    _getVisitorId(),
    cluster:      localStorage.getItem('albeni_cluster') || null,
    ids:          parseFloat(localStorage.getItem('albeni_ids') || '0'),
    idsStage:     localStorage.getItem('albeni_ids_stage') || 'discovery',
    returnVisits: parseInt(localStorage.getItem('albeni_return_visits') || '0'),
    pageViews:    parseInt(sessionStorage.getItem('albeni_pageviews') || '1'),
    domainPath:   JSON.parse(localStorage.getItem('albeni_domain_path') || '[]'),

    // BOFU-specific signals
    weightSelected:     false,
    comparisonViewed:   false,
    techSpecEngaged:    false,
    ctaClicked:         false,
    quizCompleted:      false,
    chatEngaged:        false,        // Customer Care chatbot interaction
    chatMessages:       0,            // Number of chat messages sent
    chatSizingUsed:     false,        // Used the sizing calculator via chat
    chatEscalated:      false,        // Escalation to human operator triggered
    klaviyoSynced:      localStorage.getItem('albeni_klaviyo_synced') === 'true',
  };

  // Track domain visits across sessions
  if (!STATE.domainPath.includes(DOMAIN_TYPE)) {
    STATE.domainPath.push(DOMAIN_TYPE);
    localStorage.setItem('albeni_domain_path', JSON.stringify(STATE.domainPath));
  }

  // Increment return visits counter (only once per session per domain)
  const returnKey = 'albeni_visited_' + DOMAIN_TYPE;
  if (!sessionStorage.getItem(returnKey)) {
    STATE.returnVisits++;
    localStorage.setItem('albeni_return_visits', STATE.returnVisits.toString());
    sessionStorage.setItem(returnKey, '1');
  }

  // ============================================================
  // 2. REAL-TIME IDS CALCULATOR (client-side estimate)
  //    Full server-side recalculation via /v1/intent/calculate
  // ============================================================
  function calculateLocalIDS(dwellMs, scrollPct) {
    // T score: 0-100 based on dwell time (120s = 100)
    const T = Math.min(100, (dwellMs / 120000) * 100);

    // S score: scroll depth 0-100
    const S = Math.min(100, scrollPct);

    // I score: interaction signals (weighted)
    let I = 0;
    if (STATE.pageViews >= 3)          I += 20;
    if (STATE.domainPath.length >= 2)  I += 20; // visited multiple domains
    if (STATE.techSpecEngaged)         I += 15;
    if (STATE.comparisonViewed)        I += 15;
    if (STATE.weightSelected)          I += 15;
    if (STATE.ctaClicked)              I += 10;
    if (STATE.quizCompleted)           I += 20;
    if (STATE.chatEngaged)             I += 10; // Chatbot interaction
    if (STATE.chatMessages >= 3)       I += 10; // Deep chat engagement (3+ msgs)
    if (STATE.chatSizingUsed)          I += 15; // Used sizing via chat = high intent
    I = Math.min(100, I);

    // R score: return visits 0-100
    const R = Math.min(100, STATE.returnVisits * 25);

    const ids = (T * 0.2) + (S * 0.2) + (I * 0.4) + (R * 0.2);
    return Math.round(ids);
  }

  function getIDSStage(ids) {
    if (ids >= 65) return 'hot';
    if (ids >= 55) return 'bofu_soft';
    if (ids >= 30) return 'mofu';
    return 'discovery';
  }

  // ============================================================
  // 3. SERVER-SIDE IDS + CLUSTER CALL
  //    Fires after 15s engagement or on BOFU domain
  // ============================================================
  function syncIDSWithServer(dwellMs, scrollPct) {
    const payload = {
      visitor_id:         STATE.visitorId,
      dwell_time_ms:      dwellMs,
      scroll_depth_pct:   scrollPct,
      page_views:         STATE.pageViews,
      return_visits:      STATE.returnVisits,
      domain:             window.location.hostname,
      domain_type:        DOMAIN_TYPE,
      domain_path:        STATE.domainPath,
      page_url:           window.location.pathname,
      tech_spec_engaged:  STATE.techSpecEngaged,
      comparison_viewed:  STATE.comparisonViewed,
      weight_selected:    STATE.weightSelected,
      cta_clicked:        STATE.ctaClicked,
      quiz_completed:     STATE.quizCompleted,
      timestamp:          new Date().toISOString(),
    };

    fetch(ENDPOINT + '/v1/intent/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    .then(r => r.json())
    .then(result => {
      log('IDS result:', result);
      const newIDS = result.ids_score || calculateLocalIDS(dwellMs, scrollPct);
      STATE.ids = newIDS;
      STATE.idsStage = result.intent_stage || getIDSStage(newIDS);

      localStorage.setItem('albeni_ids', newIDS.toString());
      localStorage.setItem('albeni_ids_stage', STATE.idsStage);

      // Update cluster if server returned one
      if (result.cluster) {
        STATE.cluster = result.cluster;
        localStorage.setItem('albeni_cluster', result.cluster);
        applyClusterPersonalization(result.cluster, newIDS);
      }

      // IDS > 65 → trigger Klaviyo sync (once per visitor)
      if (newIDS >= 65 && !STATE.klaviyoSynced) {
        triggerKlaviyoSync(newIDS, result.cluster);
      }

      // Show cross-domain CTA if stage suggests progression
      handleFunnelProgression(STATE.idsStage, result.cluster);

      // Dispatch custom event for other scripts
      window.dispatchEvent(new CustomEvent('albeni:ids_updated', {
        detail: { ids: newIDS, stage: STATE.idsStage, cluster: result.cluster }
      }));
    })
    .catch(err => {
      log('IDS sync error (fallback to local):', err);
      // Use local calculation as fallback
      const localIDS = calculateLocalIDS(dwellMs, scrollPct);
      STATE.ids = localIDS;
      STATE.idsStage = getIDSStage(localIDS);
      applyClusterPersonalization(STATE.cluster, localIDS);
      handleFunnelProgression(STATE.idsStage, STATE.cluster);
    });
  }

  // Also call cluster predict if no cluster yet
  function predictCluster() {
    if (STATE.cluster) {
      applyClusterPersonalization(STATE.cluster, STATE.ids);
      return;
    }

    const payload = {
      visitor_id:       STATE.visitorId,
      domain_type:      DOMAIN_TYPE,
      page_url:         window.location.pathname,
      return_visits:    STATE.returnVisits,
      domain_path:      STATE.domainPath,
      device:           /Mobi|Android/i.test(navigator.userAgent) ? 'mobile' : 'desktop',
      language:         document.documentElement.lang || 'it',
    };

    fetch(ENDPOINT + '/v1/cluster/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    .then(r => r.json())
    .then(result => {
      if (result.cluster) {
        STATE.cluster = result.cluster;
        localStorage.setItem('albeni_cluster', result.cluster);
        applyClusterPersonalization(result.cluster, STATE.ids);
        log('Cluster assigned:', result.cluster, 'confidence:', result.confidence);
      }
    })
    .catch(err => log('Cluster predict error:', err));
  }

  // ============================================================
  // 4. CONTENT PERSONALIZATION ENGINE
  //    Swaps headlines, subheadlines, CTAs based on cluster
  // ============================================================
  const CONTENT_VARIANTS = window.ALBENI_CONTENT_VARIANTS || _getDefaultVariants();

  function applyClusterPersonalization(cluster, ids) {
    if (!cluster) return;
    const domainVariants = CONTENT_VARIANTS[DOMAIN_TYPE] || {};
    const clusterVariants = domainVariants[cluster] || domainVariants['default'];
    if (!clusterVariants) return;

    log('Applying personalization for cluster:', cluster, 'domain:', DOMAIN_TYPE);

    // Hero headline
    _swapText('[data-albeni-hero-title], [data-albeni-headline], .albeni-hero-title', clusterVariants.headline);

    // Hero subheadline
    _swapText('[data-albeni-hero-sub], [data-albeni-subheadline], .albeni-hero-sub', clusterVariants.subheadline);

    // Primary CTA
    _swapText('[data-albeni-cta-primary], .albeni-cta-primary', clusterVariants.cta_primary);

    // Secondary CTA
    _swapText('[data-albeni-cta-secondary], .albeni-cta-secondary', clusterVariants.cta_secondary);

    // Value proposition block
    _swapText('[data-albeni-value-prop], .albeni-value-prop', clusterVariants.value_prop);

    // Trust signal
    _swapText('[data-albeni-trust], .albeni-trust', clusterVariants.trust_signal);

    // Apply body class for CSS-driven personalization
    document.body.classList.remove(
      'albeni-cluster-business_professional',
      'albeni-cluster-heritage_mature',
      'albeni-cluster-conscious_premium',
      'albeni-cluster-modern_minimalist',
      'albeni-cluster-italian_authentic'
    );
    document.body.classList.add('albeni-cluster-' + cluster);

    // IDS-stage class for urgency/progression messaging
    document.body.classList.remove(
      'albeni-stage-discovery', 'albeni-stage-mofu',
      'albeni-stage-bofu_soft', 'albeni-stage-hot'
    );
    document.body.classList.add('albeni-stage-' + (STATE.idsStage || 'discovery'));
  }

  function _swapText(selectors, text) {
    if (!text) return;
    const el = document.querySelector(selectors);
    if (el && !el.getAttribute('data-albeni-locked')) {
      el.textContent = text;
      el.setAttribute('data-albeni-personalized', 'true');
    }
  }

  // ============================================================
  // 5. DEFAULT CONTENT VARIANTS PER DOMAIN × CLUSTER
  //    (Sovrascrivibili via window.ALBENI_CONTENT_VARIANTS)
  // ============================================================
  function _getDefaultVariants() {
    return {

      // ── TOFU: worldofmerino.com ──────────────────────────────
      tofu: {
        business_professional: {
          headline:    'La fibra che lavora mentre lavori.',
          subheadline: 'Merino Superfine 17 micron — regolazione termica attiva per chi non si ferma mai.',
          cta_primary: 'Scopri le performance tecniche →',
          cta_secondary: 'Perché Super 120\'s?',
          value_prop:  'Termoregolazione certificata. Zero compromessi.',
          trust_signal: 'Indossata da professionisti in 12 paesi.',
        },
        heritage_mature: {
          headline:    'Dal 1905. La lana che racconta una storia vera.',
          subheadline: 'Filiera italiana verificata. Artigianalità che si vede e si sente.',
          cta_primary: 'Scopri l\'eredità Albeni →',
          cta_secondary: 'Filiera e certificazioni',
          value_prop:  '270 anni di storia tessile combinata.',
          trust_signal: 'Produzione italiana verificata.',
        },
        conscious_premium: {
          headline:    'Fibra naturale. Impatto reale.',
          subheadline: 'Merino rigenerabile, filiera tracciata, durata garantita — meno consumi, più valore.',
          cta_primary: 'Esplora la sostenibilità →',
          cta_secondary: 'Certificazioni ambientali',
          value_prop:  'Una T-shirt che dura anni riduce i rifiuti tessili.',
          trust_signal: 'Filiera OEKO-TEX certificata.',
        },
        modern_minimalist: {
          headline:    'Zero logo. Massima sostanza.',
          subheadline: 'Il tessuto perfetto per chi vuole qualità senza distrazioni visive.',
          cta_primary: 'Vedi i colori neutri →',
          cta_secondary: 'Confronta con il cotone premium',
          value_prop:  'Essenzialità certificata. Qualità verificabile.',
          trust_signal: 'Design minimal. Standard tecnico massimo.',
        },
        italian_authentic: {
          headline:    'La T-shirt italiana che dura.',
          subheadline: 'Qualità Made in Italy nel tessuto di tutti i giorni — non nella narrativa.',
          cta_primary: 'Scopri il Merino italiano →',
          cta_secondary: 'Confronta con cotone',
          value_prop:  'Artigianalità italiana. Prezzo onesto.',
          trust_signal: 'Prodotto e confezionato in Italia.',
        },
        default: {
          headline:    'Il miglior merino che abbia mai indossato.',
          subheadline: 'T-shirt Superfine 17 micron — termoregolazione, comfort, durata.',
          cta_primary: 'Scopri il mondo Merino →',
          cta_secondary: 'Cos\'è la Merino Superfine?',
          value_prop:  'La fibra più tecnica nel capo più semplice.',
          trust_signal: 'Trusted by professionals worldwide.',
        },
      },

      // ── MOFU: merinouniversity.com ───────────────────────────
      mofu: {
        business_professional: {
          headline:    '17 micron. Il confine tra lana e seta.',
          subheadline: 'Comparazione tecnica: Merino Superfine vs. cotone Pima vs. lana convenzionale.',
          cta_primary: 'Leggi il confronto tecnico →',
          cta_secondary: 'Certificazioni Super 120\'s',
          value_prop:  'Dati misurabili, non promesse di marketing.',
          trust_signal: 'Analisi tecnica indipendente.',
        },
        heritage_mature: {
          headline:    'Perché la filiera conta più del brand.',
          subheadline: 'Come riconoscere una vera lana italiana. Guida alla qualità certificata.',
          cta_primary: 'Guida alla filiera →',
          cta_secondary: 'Storia del Merino italiano',
          value_prop:  'Trasparenza totale dalla fibra al capo finito.',
          trust_signal: 'Tracciabilità verificata dal gregge.',
        },
        conscious_premium: {
          headline:    'Sostenibilità reale: i numeri del Merino vs. cotone.',
          subheadline: 'CO₂, consumo idrico, durata del prodotto — confronto dati certificati.',
          cta_primary: 'Analisi impatto ambientale →',
          cta_secondary: 'Riciclabilità del Merino',
          value_prop:  'Durata ×3 rispetto al cotone = ÷3 rifiuti tessili.',
          trust_signal: 'Dati da studi LCA certificati.',
        },
        modern_minimalist: {
          headline:    'Perché il Merino batte il cotone premium ogni volta.',
          subheadline: 'Test comparativo: 6 settimane, 3 tessuti, un solo vincitore.',
          cta_primary: 'Leggi il test →',
          cta_secondary: 'Guida alla scelta del peso',
          value_prop:  'Qualità misurabile. Non interpretabile.',
          trust_signal: 'Test condotto con utenti reali.',
        },
        italian_authentic: {
          headline:    'La differenza tra Merino e lana normale.',
          subheadline: 'Tutto quello che devi sapere prima di comprare una T-shirt di qualità.',
          cta_primary: 'Guida per principianti →',
          cta_secondary: 'Domande frequenti',
          value_prop:  'Capire prima, scegliere meglio.',
          trust_signal: 'Guida semplice, tecnica verificata.',
        },
        default: {
          headline:    'L\'università del Merino.',
          subheadline: 'Tutto quello che non ti dicono sulle T-shirt di qualità.',
          cta_primary: 'Inizia il percorso →',
          cta_secondary: 'Glossario tecnico',
          value_prop:  'Educazione tecnica prima dell\'acquisto.',
          trust_signal: 'Contenuti verificati da esperti tessili.',
        },
      },

      // ── BOFU TECNICO: perfectmerinoshirt.com ────────────────
      bofu_tech: {
        business_professional: {
          headline:    'La T-shirt progettata per chi si muove tutto il giorno.',
          subheadline: 'Super 120\'s, 17 micron, 150g — termoregolazione attiva dal mattino alla sera.',
          cta_primary: 'Scegli il tuo peso →',
          cta_secondary: 'Confronta 150g vs 190g',
          value_prop:  'Comfort verificabile. Qualità misurabile.',
          trust_signal: '★★★★★ "Indistinguibile da una camicia di lusso sotto giacca."',
        },
        heritage_mature: {
          headline:    'Sartorialità italiana. In una T-shirt.',
          subheadline: 'Merino Superfine selezionato, filiera verificata, costruzione senza compromessi.',
          cta_primary: 'Scopri la costruzione →',
          cta_secondary: 'Certificati di filiera',
          value_prop:  'Il valore che si vede quando le altre T-shirt sono già consumate.',
          trust_signal: '★★★★★ "La qualità si sente al primo tatto. Non si torna indietro."',
        },
        conscious_premium: {
          headline:    'Acquisto unico. Impatto ridotto.',
          subheadline: 'Merino 150g: la scelta sostenibile per chi compra una volta e tiene per anni.',
          cta_primary: 'Perché dura di più →',
          cta_secondary: 'Guida alla cura del Merino',
          value_prop:  'Meno acquisti, più qualità — meno rifiuti tessili.',
          trust_signal: '★★★★★ "Ho smesso di comprare 5 T-shirt di cotone all\'anno."',
        },
        modern_minimalist: {
          headline:    'Una T-shirt. Tre anni di utilizzo.',
          subheadline: 'Colori neutri, taglio pulito, qualità che non si vede ma si sente.',
          cta_primary: 'Scegli il colore →',
          cta_secondary: 'Guida alla taglia',
          value_prop:  'Il capo essenziale fatto nella maniera giusta.',
          trust_signal: '★★★★★ "Finalmente una basic che non sembra basic."',
        },
        italian_authentic: {
          headline:    'Tutta l\'eccellenza italiana nel comfort di ogni giorno.',
          subheadline: 'Merino italiano 190g — calore, morbidezza e durata nel capo che indossi di più.',
          cta_primary: 'Ordina la tua →',
          cta_secondary: 'Confronta 150g vs 190g',
          value_prop:  'Made in Italy. Non come slogan — come garanzia.',
          trust_signal: '★★★★★ "La migliore T-shirt italiana che abbia mai comprato."',
        },
        default: {
          headline:    'La T-shirt Merino definitiva.',
          subheadline: '150g o 190g — scegli la tua versione della perfezione.',
          cta_primary: 'Trova la tua misura →',
          cta_secondary: 'Quale peso fa per me?',
          value_prop:  'Invisible Luxury: si vede meno, si sente di più.',
          trust_signal: '★★★★★ Media 4.9/5 su 340 recensioni verificate.',
        },
      },
    };
  }

  // ============================================================
  // 6. FUNNEL PROGRESSION — Cross-domain CTA banners
  //    (albeni1905.com escluso: redirige su perfectmerinoshirt.com)
  // ============================================================
  function handleFunnelProgression(stage, cluster) {
    // Don't show shift banners on bofu_tech (already at bottom of accessible funnel)
    if (DOMAIN_TYPE === 'bofu_tech') return;

    // Only show if IDS has reached meaningful threshold
    if (STATE.ids < 35) return;

    const progressionTargets = {
      tofu: {
        url:     'https://merinouniversity.com',
        label:   'merinouniversity.com',
        message: 'Vuoi capire davvero la differenza? Approfondisci →',
      },
      mofu: {
        url:     'https://perfectmerinoshirt.com',
        label:   'perfectmerinoshirt.com',
        message: 'Pronto a scegliere la tua? Confronto tecnico completo →',
      },
    };

    const target = progressionTargets[DOMAIN_TYPE];
    if (!target) return;

    // Override message by cluster for relevance
    if (cluster === 'business_professional' && DOMAIN_TYPE === 'mofu') {
      target.message = 'Specifiche tecniche complete su Perfect Merino Shirt →';
    }
    if (cluster === 'conscious_premium' && DOMAIN_TYPE === 'tofu') {
      target.message = 'Scopri i dati di sostenibilità su Merino University →';
    }

    // Show with delay to avoid interrupting first engagement
    setTimeout(function () {
      if (window.albeniAI && window.albeniAI.showShiftBanner) {
        window.albeniAI.showShiftBanner(target.message, target.url);
      } else {
        _showProgressionBanner(target.message, target.url);
      }
    }, 25000); // 25s delay
  }

  function _showProgressionBanner(message, url) {
    if (document.getElementById('albeni-progression-banner')) return;
    const b = document.createElement('div');
    b.id = 'albeni-progression-banner';
    b.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);' +
      'background:linear-gradient(135deg,#1a1a2e,#16213e);color:#e8d5b7;' +
      'padding:14px 22px;border-radius:10px;font-family:system-ui,sans-serif;' +
      'font-size:14px;max-width:460px;width:90%;z-index:9999;' +
      'box-shadow:0 8px 32px rgba(0,0,0,0.35);display:flex;align-items:center;' +
      'gap:12px;cursor:pointer;animation:albeni-slide-in 0.4s ease-out;';
    b.innerHTML = '<span style="flex:1;line-height:1.4">' + message + '</span>' +
      '<span style="background:#e8d5b7;color:#1a1a2e;padding:7px 14px;border-radius:7px;' +
      'font-weight:700;font-size:12px;white-space:nowrap;">Vai →</span>' +
      '<span id="albeni-banner-close" style="opacity:.5;font-size:18px;line-height:1;' +
      'margin-left:4px;cursor:pointer;">✕</span>';
    document.getElementById('albeni-banner-close') && b.querySelector('#albeni-banner-close')
      .addEventListener('click', function(e) { e.stopPropagation(); b.remove(); });
    b.addEventListener('click', function() { window.location.href = url; });
    const s = document.createElement('style');
    s.textContent = '@keyframes albeni-slide-in{from{opacity:0;transform:translateX(-50%) translateY(16px)}' +
      'to{opacity:1;transform:translateX(-50%) translateY(0)}}';
    document.head.appendChild(s);
    document.body.appendChild(b);
    setTimeout(function() { if (b.parentNode) { b.style.opacity='0'; b.style.transition='opacity .4s'; setTimeout(function(){b.remove();},400); }}, 20000);
  }

  // ============================================================
  // 7. KLAVIYO SYNC — fires when IDS ≥ 65
  //    Routes through AI Router /v1/crm/sync-lead
  // ============================================================
  function triggerKlaviyoSync(ids, cluster) {
    if (STATE.klaviyoSynced) return;

    const email = _getStoredEmail();
    // Build payload — email is optional (server handles anonymous profiles)
    const payload = {
      visitor_id:   STATE.visitorId,
      email:        email || undefined,
      ids_score:    ids,
      cluster:      cluster || STATE.cluster || 'unknown',
      domain:       window.location.hostname,
      domain_type:  DOMAIN_TYPE,
      domain_path:  STATE.domainPath,
      page_url:     window.location.href,
      source:       'behavioral_engine_ids_threshold',
      timestamp:    new Date().toISOString(),
      signals: {
        tech_spec_engaged:  STATE.techSpecEngaged,
        comparison_viewed:  STATE.comparisonViewed,
        weight_selected:    STATE.weightSelected,
        cta_clicked:        STATE.ctaClicked,
        quiz_completed:     STATE.quizCompleted,
        return_visits:      STATE.returnVisits,
        page_views:         STATE.pageViews,
      }
    };

    fetch(ROUTER_URL + '/v1/crm/sync-lead', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    .then(r => r.json())
    .then(result => {
      log('Klaviyo sync complete:', result);
      STATE.klaviyoSynced = true;
      localStorage.setItem('albeni_klaviyo_synced', 'true');
      window.dispatchEvent(new CustomEvent('albeni:klaviyo_synced', { detail: result }));
    })
    .catch(err => log('Klaviyo sync error:', err));
  }

  function _getStoredEmail() {
    // Check if email was captured by a form (Klaviyo embed, CF7, etc.)
    return localStorage.getItem('albeni_visitor_email') ||
           sessionStorage.getItem('albeni_visitor_email') ||
           null;
  }

  // ============================================================
  // 8. BOFU-SPECIFIC SIGNAL LISTENERS
  //    Only active on perfectmerinoshirt.com
  // ============================================================
  function initBOFUListeners() {
    if (DOMAIN_TYPE !== 'bofu_tech') return;

    // Weight selector (radio buttons or custom selector)
    document.addEventListener('change', function(e) {
      const el = e.target;
      if (el.name === 'weight' || el.closest('[data-albeni-weight-selector]') ||
          el.name === 'variation' || el.closest('.product-weight-select')) {
        STATE.weightSelected = true;
        log('Weight selected');
        _bumpInteractionScore(15);
      }
    });

    // Comparison table engagement
    document.addEventListener('click', function(e) {
      if (e.target.closest('[data-albeni-comparison], .albeni-comparison-table, .comparison-table')) {
        STATE.comparisonViewed = true;
        log('Comparison table engaged');
        _bumpInteractionScore(15);
      }
      // Primary CTA click
      if (e.target.closest('[data-albeni-cta-primary], .albeni-cta-primary, .add-to-cart, .woocommerce-cart-form')) {
        STATE.ctaClicked = true;
        log('Primary CTA clicked');
        _bumpInteractionScore(20);
      }
    });

    // Technical spec section visibility (Intersection Observer)
    const techSections = document.querySelectorAll('[data-albeni-tech-spec], .albeni-tech-spec, .product-tech-specs, .merino-specs');
    if (techSections.length > 0 && 'IntersectionObserver' in window) {
      const obs = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
          if (entry.isIntersecting && !STATE.techSpecEngaged) {
            STATE.techSpecEngaged = true;
            log('Tech spec section viewed');
            _bumpInteractionScore(15);
          }
        });
      }, { threshold: 0.4 });
      techSections.forEach(function(el) { obs.observe(el); });
    }

    // Quiz completion event (works with Typeform, WP Quiz plugins)
    window.addEventListener('message', function(e) {
      if (e.data && (e.data.type === 'form-submit' || e.data.type === 'quiz-complete')) {
        STATE.quizCompleted = true;
        log('Quiz/form completed');
        _bumpInteractionScore(20);
      }
    });
    document.addEventListener('albeni:quiz_complete', function() {
      STATE.quizCompleted = true;
      _bumpInteractionScore(20);
    });
  }

  function _bumpInteractionScore(delta) {
    // Re-trigger IDS sync after significant interaction
    const now = Date.now();
    const sessionStart = parseInt(sessionStorage.getItem('albeni_session_start') || now.toString());
    const scrollPct = parseFloat(localStorage.getItem('_albeni_last_scroll') || '0');
    const dwellMs = now - sessionStart;

    const newLocalIDS = calculateLocalIDS(dwellMs, scrollPct);
    STATE.ids = newLocalIDS;

    if (newLocalIDS >= 65 && !STATE.klaviyoSynced) {
      // Trigger immediate server sync to confirm and fire Klaviyo
      syncIDSWithServer(dwellMs, scrollPct);
    }
  }

  // ============================================================
  // 9. MOFU-SPECIFIC LISTENERS: merinouniversity.com
  //    Track deep content engagement (guides, comparisons)
  // ============================================================
  function initMOFUListeners() {
    if (DOMAIN_TYPE !== 'mofu') return;

    // Track reading depth (articles / guides)
    if ('IntersectionObserver' in window) {
      const articleEnds = document.querySelectorAll('[data-albeni-article-end], .article-end, .post-footer');
      if (articleEnds.length > 0) {
        const obs = new IntersectionObserver(function(entries) {
          entries.forEach(function(entry) {
            if (entry.isIntersecting) {
              STATE.techSpecEngaged = true; // reuse flag for full-read signal
              log('Article fully read on MOFU');
              _bumpInteractionScore(15);
            }
          });
        }, { threshold: 0.5 });
        articleEnds.forEach(function(el) { obs.observe(el); });
      }
    }
  }

  // ============================================================
  // 10. EMAIL CAPTURE LISTENER
  //     Stores email for Klaviyo sync if visitor fills any form
  // ============================================================
  function initEmailCapture() {
    document.addEventListener('submit', function(e) {
      const form = e.target;
      const emailInput = form.querySelector('input[type="email"], input[name="email"], input[name="EMAIL"]');
      if (emailInput && emailInput.value) {
        const email = emailInput.value.trim();
        if (/^[^@]+@[^@]+\.[^@]+$/.test(email)) {
          localStorage.setItem('albeni_visitor_email', email);
          sessionStorage.setItem('albeni_visitor_email', email);
          log('Email captured:', email);
          // If IDS already above threshold, sync immediately
          if (STATE.ids >= 65) triggerKlaviyoSync(STATE.ids, STATE.cluster);
        }
      }
    });
  }

  // ============================================================
  // 11. SCROLL TRACKING (persistent for IDS calc)
  // ============================================================
  let _lastScrollDepth = 0;
  window.addEventListener('scroll', function() {
    const docH = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight) - window.innerHeight;
    if (docH > 0) {
      const depth = Math.round((window.pageYOffset / docH) * 100);
      if (depth > _lastScrollDepth) {
        _lastScrollDepth = depth;
        localStorage.setItem('_albeni_last_scroll', depth.toString());
      }
    }
  }, { passive: true });

  // ============================================================
  // 12. TIMED IDS SYNC SCHEDULE
  // ============================================================
  // First sync at 15s (enough to gather real signals)
  setTimeout(function() {
    const sessionStart = parseInt(sessionStorage.getItem('albeni_session_start') || Date.now().toString());
    syncIDSWithServer(Date.now() - sessionStart, _lastScrollDepth);
  }, 15000);

  // Deeper sync at 45s (for engaged readers)
  setTimeout(function() {
    const sessionStart = parseInt(sessionStorage.getItem('albeni_session_start') || Date.now().toString());
    syncIDSWithServer(Date.now() - sessionStart, _lastScrollDepth);
  }, 45000);

  // ============================================================
  // INIT
  // ============================================================
  function init() {
    // Initial cluster personalization from stored data
    if (STATE.cluster) {
      applyClusterPersonalization(STATE.cluster, STATE.ids);
    } else {
      // Predict cluster after 3s (DOM is ready, first signals gathered)
      setTimeout(predictCluster, 3000);
    }

    initBOFUListeners();
    initMOFUListeners();
    initEmailCapture();

    // Expose public API
    window.albeniEngine = {
      getState:    function() { return { ...STATE }; },
      getIDS:      function() { return STATE.ids; },
      getCluster:  function() { return STATE.cluster; },
      getStage:    function() { return STATE.idsStage; },
      forceSync:   function() {
        const ss = parseInt(sessionStorage.getItem('albeni_session_start') || Date.now().toString());
        syncIDSWithServer(Date.now() - ss, _lastScrollDepth);
      },
      trackEvent:  function(name, data) {
        if (window.albeniAI) window.albeniAI.track(name, data);
      },
      // Called when visitor completes quiz widget
      quizComplete: function(answers) {
        STATE.quizCompleted = true;
        document.dispatchEvent(new CustomEvent('albeni:quiz_complete', { detail: answers }));
      },
      // Called by email forms
      setEmail: function(email) {
        localStorage.setItem('albeni_visitor_email', email);
        if (STATE.ids >= 65) triggerKlaviyoSync(STATE.ids, STATE.cluster);
      },
    };

    // ============================================================
    // CHATBOT EVENT LISTENER
    // Listens for 'albeni:chat' custom events dispatched by the
    // chatbot snippet (albeni-chatbot-snippet.js).
    // Updates IDS interaction signals based on chat behavior.
    // ============================================================
    document.addEventListener('albeni:chat', function(e) {
      var d = e.detail || {};
      var evt = d.event;
      var meta = d.meta || {};

      log('Chat event received:', evt, meta);

      if (evt === 'chat_opened') {
        STATE.chatEngaged = true;
      }

      if (evt === 'chat_message_sent') {
        STATE.chatMessages++;

        // Topic-specific IDS signals
        if (meta.topic === 'sizing') STATE.chatSizingUsed = true;
        if (meta.escalated) STATE.chatEscalated = true;

        // Re-sync IDS after meaningful chat engagement (3+ messages)
        if (STATE.chatMessages === 3 || STATE.chatMessages === 6) {
          var ss = parseInt(sessionStorage.getItem('albeni_session_start') || Date.now().toString());
          syncIDSWithServer(Date.now() - ss, _lastScrollDepth);
        }
      }
    });

    log('Behavioral Engine initialized', {
      domain: DOMAIN_TYPE,
      cluster: STATE.cluster || 'pending',
      ids: STATE.ids,
      stage: STATE.idsStage,
      returnVisits: STATE.returnVisits,
    });
  }

  // ============================================================
  // UTILS
  // ============================================================
  function _getVisitorId() {
    return localStorage.getItem('albeni_visitor_id') ||
           (window.albeniAI && window.albeniAI.getVisitorId ? window.albeniAI.getVisitorId() : 'v_unknown');
  }

  // Run after DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
