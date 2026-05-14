/**
 * CRO Adaptive Microcopy Widget — Albeni 1905 AI Stack
 * Step 7.3 (2026-05-14).
 *
 * Cosa fa:
 *   1. Al pageload trova tutti gli elementi DOM con `data-cro-slot="..."`
 *   2. Per ciascuno chiama GET /v1/cro/microcopy?slot=...&cluster=...&language=...
 *   3. Sostituisce il textContent con la variant selezionata dal MAB epsilon-greedy
 *   4. Salva exposure_id in dataset per tracking conversioni
 *   5. Su click di elementi con `data-cro-conversion-trigger` registra conversion
 *
 * Setup WPCode:
 *   - Code Type: JavaScript Snippet
 *   - Location: Site Wide Footer
 *   - Auto Insert: enabled
 *   - Copia tutto il contenuto di questo file
 *
 * Markup HTML lato editor (Gutenberg HTML block):
 *   <h1 data-cro-slot="homepage_hero_cta">Default fallback text</h1>
 *   <a class="btn" data-cro-slot="newsletter_signup_headline">Default text</a>
 *   <button data-cro-conversion-trigger="lead">Iscriviti</button>
 *
 * NB sul fallback: se l'API è down o lo slot non ha variant configurate,
 * il widget LASCIA il testo originale del Gutenberg block. Niente flash di vuoto.
 */
(function () {
    'use strict';

    var ML_WORKER_URL = 'https://albeni-ai-orchestration-production.up.railway.app';
    var API_KEY = null; // solo per /v1/cro/conversion (read è no-auth)
    // IMPORTANTE: API_KEY non va esposta nel JS pubblico. Per conversion,
    // proxy via WPCode PHP snippet che firma server-side (vedi cro_widget_conversion_proxy.php).
    var CONVERSION_PROXY_URL = '/wp-json/albeni/v1/cro-conversion'; // se hai il proxy PHP attivo

    // ── Cluster detection (riusa la logica del bot_shield / IDS) ──
    function detectCluster() {
        // 1. URL param ?cluster=
        var params = new URLSearchParams(window.location.search);
        if (params.has('cluster')) return params.get('cluster');
        // 2. Cookie albeni_cluster (settato dall'AI Stack lato server-side post-IDS)
        var m = document.cookie.match(/albeni_cluster=([^;]+)/);
        if (m) return decodeURIComponent(m[1]);
        // 3. window.albeniCluster (se settato da altro snippet)
        if (window.albeniCluster) return window.albeniCluster;
        return null; // fallback: il backend userà variant generic (cluster=NULL)
    }

    function detectLanguage() {
        // Polylang aggiunge la lingua all'<html lang>
        var lang = (document.documentElement.lang || 'it').toLowerCase().split('-')[0];
        return ['it', 'en', 'de', 'fr'].indexOf(lang) >= 0 ? lang : 'it';
    }

    function getOrCreateSessionId() {
        var sid = sessionStorage.getItem('albeni_cro_session_id');
        if (!sid) {
            sid = 'cro_' + Date.now() + '_' + Math.random().toString(36).slice(2, 10);
            sessionStorage.setItem('albeni_cro_session_id', sid);
        }
        return sid;
    }

    function getUserId() {
        // Riusa cookie visitor_id già settato da albeni-track.js (bot_shield)
        var m = document.cookie.match(/albeni_visitor_id=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : null;
    }

    // ── Fetch single microcopy ──
    function loadMicrocopy(element) {
        var slot = element.dataset.croSlot;
        if (!slot) return;
        var cluster = detectCluster();
        var language = detectLanguage();
        var sessionId = getOrCreateSessionId();
        var userId = getUserId();

        var url = new URL(ML_WORKER_URL + '/v1/cro/microcopy');
        url.searchParams.set('slot', slot);
        url.searchParams.set('language', language);
        if (cluster) url.searchParams.set('cluster', cluster);
        if (sessionId) url.searchParams.set('session_id', sessionId);
        if (userId) url.searchParams.set('user_id', userId);

        fetch(url, { method: 'GET', mode: 'cors', credentials: 'omit' })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (!data || !data.found) return; // lascia il fallback in pagina
                // Replace textContent (non innerHTML, evita XSS dai testi DB)
                element.textContent = data.text;
                element.dataset.croExposureId = data.exposure_id;
                element.dataset.croVariantKey = data.variant_key;
                element.classList.add('cro-personalized');
            })
            .catch(function (e) {
                // Silent fail: meglio mostrare default che rompere il sito
                if (window.console && console.warn) {
                    console.warn('[CRO] microcopy failed for slot=' + slot + ':', e);
                }
            });
    }

    // ── Conversion tracking ──
    function recordConversion(exposureId, conversionType, valueEur) {
        if (!exposureId) return;
        // Via proxy WP (server firma con API key, non esposta al frontend)
        fetch(CONVERSION_PROXY_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({
                exposure_id: parseInt(exposureId, 10),
                conversion_type: conversionType || 'click',
                value_eur: valueEur || null
            })
        }).catch(function () { /* silent */ });
    }

    // ── Init al DOMContentLoaded ──
    function init() {
        // 1. Trova tutti i nodi con slot e carica la variant
        var slots = document.querySelectorAll('[data-cro-slot]');
        slots.forEach(loadMicrocopy);

        // 2. Bind click su elementi conversion-trigger
        document.addEventListener('click', function (e) {
            var trigger = e.target.closest('[data-cro-conversion-trigger]');
            if (!trigger) return;
            // Trova l'exposure più vicina nel DOM (parent o sibling)
            var slotEl = trigger.closest('[data-cro-exposure-id]')
                || document.querySelector('[data-cro-exposure-id]');
            if (!slotEl) return;
            var conversionType = trigger.dataset.croConversionTrigger || 'click';
            var valueEur = parseFloat(trigger.dataset.croValueEur) || null;
            recordConversion(slotEl.dataset.croExposureId, conversionType, valueEur);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
