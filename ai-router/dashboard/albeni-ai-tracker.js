/**
 * Albeni 1905 — AI Orchestration Layer Tracker
 * Frontend tracking snippet per cattura segnali ADV + comportamentali
 *
 * Installazione: Inserire nell'<head> di tutti i 4 domini:
 * - worldofmerino.com (TOFU)
 * - merinouniversity.com (MOFU)
 * - perfectmerinoshirt.com (BOFU)
 * - albeni1905.com (BOFU Heritage)
 *
 * Configurazione:
 *   window.ALBENI_AI = {
 *     endpoint: 'https://your-ml-worker-url:8000',
 *     debug: false
 *   };
 */

(function() {
  'use strict';

  // ================================================================
  // CONFIGURATION
  // ================================================================
  const CONFIG = window.ALBENI_AI || {};
  const ENDPOINT = CONFIG.endpoint || 'http://localhost:8000';
  const DEBUG = CONFIG.debug || false;

  function log(...args) {
    if (DEBUG) console.log('[Albeni AI]', ...args);
  }

  // ================================================================
  // 1. UTM SENSOR — Cattura Provenienza ADV
  // ================================================================
  const urlParams = new URLSearchParams(window.location.search);

  const campaignData = {
    source:         urlParams.get('utm_source'),
    medium:         urlParams.get('utm_medium'),
    term:           urlParams.get('utm_term'),
    content:        urlParams.get('utm_content'),
    campaign:       urlParams.get('utm_campaign'),
    gclid:          urlParams.get('gclid'),
    fbclid:         urlParams.get('fbclid'),
    landing_domain: window.location.hostname,
    page_url:       window.location.pathname,
    referrer:       document.referrer || null,
  };

  // Persist campaign data in sessionStorage for cross-page attribution
  if (campaignData.source || campaignData.gclid || campaignData.fbclid) {
    sessionStorage.setItem('albeni_campaign', JSON.stringify(campaignData));
    log('Campaign data captured:', campaignData);
  }

  // Retrieve persisted campaign data (for subsequent pages)
  const storedCampaign = JSON.parse(sessionStorage.getItem('albeni_campaign') || 'null');
  const activeCampaign = (campaignData.source || campaignData.gclid || campaignData.fbclid)
    ? campaignData
    : storedCampaign;

  // ================================================================
  // 2. BEHAVIORAL SIGNALS — Dwell Time, Scroll, Mouse
  // ================================================================
  const sessionStart = Date.now();
  let mouseEventCount = 0;
  let maxScrollDepth = 0;
  let pageViewCount = parseInt(sessionStorage.getItem('albeni_pageviews') || '0') + 1;
  sessionStorage.setItem('albeni_pageviews', pageViewCount.toString());

  // Mouse movement tracking (throttled)
  let lastMouseTime = 0;
  document.addEventListener('mousemove', function() {
    const now = Date.now();
    if (now - lastMouseTime > 500) { // Max 2 events/second
      mouseEventCount++;
      lastMouseTime = now;
    }
  }, { passive: true });

  // Click tracking
  document.addEventListener('click', function() {
    mouseEventCount++;
  }, { passive: true });

  // Scroll depth tracking (throttled)
  let scrollTimeout;
  window.addEventListener('scroll', function() {
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(function() {
      const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
      const docHeight = Math.max(
        document.body.scrollHeight,
        document.documentElement.scrollHeight
      ) - window.innerHeight;
      if (docHeight > 0) {
        const depth = Math.round((scrollTop / docHeight) * 100);
        if (depth > maxScrollDepth) {
          maxScrollDepth = depth;
        }
      }
    }, 200);
  }, { passive: true });

  // ================================================================
  // 3. AI EVENT SENDER
  // ================================================================
  function sendAI(eventType, extraData) {
    const dwellTime = Date.now() - sessionStart;
    const sessionDuration = parseInt(sessionStorage.getItem('albeni_session_start') || Date.now().toString());

    const payload = {
      event_type: eventType,
      visitor_id: getOrCreateVisitorId(),
      timestamp: new Date().toISOString(),
      page_url: window.location.href,
      domain: window.location.hostname,
      dwell_time_ms: dwellTime,
      mouse_events: mouseEventCount,
      scroll_depth_pct: maxScrollDepth,
      page_views: pageViewCount,
      session_duration_ms: Date.now() - sessionDuration,
      device: /Mobi|Android/i.test(navigator.userAgent) ? 'mobile' : 'desktop',
      user_agent: navigator.userAgent,
      campaign: activeCampaign,
      ...(extraData || {}),
    };

    log('Sending event:', eventType, payload);

    // Use sendBeacon for reliability (especially on page unload)
    if (navigator.sendBeacon) {
      navigator.sendBeacon(
        ENDPOINT + '/v1/track/event',
        new Blob([JSON.stringify(payload)], { type: 'application/json' })
      );
    } else {
      fetch(ENDPOINT + '/v1/track/event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        keepalive: true,
      }).catch(function(err) { log('Send error:', err); });
    }
  }

  // ================================================================
  // 4. BOT SHIELD — Behavioral Fingerprint
  // ================================================================
  function sendBotShieldCheck() {
    const dwellTime = Date.now() - sessionStart;
    const isPaid = !!(activeCampaign && (activeCampaign.gclid || activeCampaign.fbclid));

    const shieldData = {
      visitor_id: getOrCreateVisitorId(),
      ip_address: '',  // Server-side detection (IP not available client-side)
      user_agent: navigator.userAgent,
      dwell_time_ms: dwellTime,
      mouse_events: mouseEventCount,
      scroll_depth_pct: maxScrollDepth,
      pages_viewed: pageViewCount,
      session_duration_ms: dwellTime,
      is_paid: isPaid,
      referrer: document.referrer || null,
    };

    fetch(ENDPOINT + '/v1/adv/shield/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(shieldData),
    })
    .then(function(r) { return r.json(); })
    .then(function(result) {
      log('Bot Shield result:', result);
      if (result.should_exclude) {
        log('⚠️ Visitor flagged as bot/fraud');
      }
    })
    .catch(function(err) { log('Shield error:', err); });
  }

  // ================================================================
  // 5. ADV ROUTING — Dynamic Landing Check
  // ================================================================
  function checkADVRouting() {
    if (!activeCampaign || (!activeCampaign.source && !activeCampaign.gclid && !activeCampaign.fbclid)) {
      return; // Not paid traffic, skip
    }

    const routeParams = new URLSearchParams({
      source: activeCampaign.source || '',
      medium: activeCampaign.medium || '',
      term: activeCampaign.term || '',
      content: activeCampaign.content || '',
      gclid: activeCampaign.gclid || '',
      fbclid: activeCampaign.fbclid || '',
      landing_domain: window.location.hostname,
      language: document.documentElement.lang || 'it',
      device: /Mobi|Android/i.test(navigator.userAgent) ? 'mobile' : 'desktop',
    });

    fetch(ENDPOINT + '/v1/adv/route?' + routeParams.toString(), {
      method: 'POST',
    })
    .then(function(r) { return r.json(); })
    .then(function(route) {
      log('ADV Route:', route);

      // Apply dynamic headline if provided
      if (route.headline) {
        const heroEl = document.querySelector('[data-albeni-hero], .hero-title, h1');
        if (heroEl) {
          heroEl.textContent = route.headline;
          log('Dynamic headline applied:', route.headline);
        }
      }

      // Show cross-domain shift banner if recommended
      if (route.shift_target) {
        showShiftBanner(route.shift_target.message, route.shift_target.url);
      }

      // Apply layout class
      if (route.layout) {
        document.body.classList.add('albeni-layout-' + route.layout);
      }
    })
    .catch(function(err) { log('Route error:', err); });
  }

  // ================================================================
  // 6. CROSS-DOMAIN SHIFT BANNER
  // ================================================================
  function showShiftBanner(message, targetUrl) {
    if (!message || !targetUrl) return;

    const banner = document.createElement('div');
    banner.id = 'albeni-shift-banner';
    banner.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);' +
      'background:linear-gradient(135deg,#1a1a2e,#16213e);color:#e8d5b7;' +
      'padding:16px 24px;border-radius:12px;font-family:system-ui,sans-serif;' +
      'font-size:14px;max-width:480px;z-index:9999;box-shadow:0 8px 32px rgba(0,0,0,0.3);' +
      'display:flex;align-items:center;gap:12px;cursor:pointer;' +
      'animation:albeni-slide-up 0.5s ease-out;';

    banner.innerHTML = '<span style="flex:1">' + message + '</span>' +
      '<span style="background:#e8d5b7;color:#1a1a2e;padding:8px 16px;border-radius:8px;' +
      'font-weight:600;white-space:nowrap;font-size:13px;">Scopri →</span>';

    banner.addEventListener('click', function() {
      window.location.href = targetUrl;
    });

    // Add animation
    const style = document.createElement('style');
    style.textContent = '@keyframes albeni-slide-up{from{opacity:0;transform:translateX(-50%) translateY(20px)}' +
      'to{opacity:1;transform:translateX(-50%) translateY(0)}}';
    document.head.appendChild(style);

    document.body.appendChild(banner);

    // Auto-dismiss after 15 seconds
    setTimeout(function() {
      if (banner.parentNode) {
        banner.style.opacity = '0';
        banner.style.transition = 'opacity 0.5s';
        setTimeout(function() { banner.remove(); }, 500);
      }
    }, 15000);
  }

  // ================================================================
  // UTILITIES
  // ================================================================
  function getOrCreateVisitorId() {
    var id = localStorage.getItem('albeni_visitor_id');
    if (!id) {
      id = 'v_' + Date.now().toString(36) + '_' + Math.random().toString(36).substr(2, 9);
      localStorage.setItem('albeni_visitor_id', id);
    }
    return id;
  }

  // Initialize session start
  if (!sessionStorage.getItem('albeni_session_start')) {
    sessionStorage.setItem('albeni_session_start', Date.now().toString());
  }

  // ================================================================
  // AUTO-FIRE EVENTS
  // ================================================================

  // Page view on load
  sendAI('page_view', { campaign: activeCampaign });

  // ADV routing check (only for paid traffic)
  checkADVRouting();

  // Bot Shield check after 5 seconds (enough time to gather behavioral data)
  setTimeout(sendBotShieldCheck, 5000);

  // Send engagement data on page unload
  window.addEventListener('beforeunload', function() {
    sendAI('page_exit', {
      final_dwell_ms: Date.now() - sessionStart,
      final_scroll_depth: maxScrollDepth,
      final_mouse_events: mouseEventCount,
    });
  });

  // Expose API for custom events
  window.albeniAI = {
    track: sendAI,
    getCampaign: function() { return activeCampaign; },
    getVisitorId: getOrCreateVisitorId,
  };

  log('Albeni AI Tracker initialized', {
    domain: window.location.hostname,
    campaign: activeCampaign ? 'detected' : 'organic',
    pageViews: pageViewCount,
  });

})();
