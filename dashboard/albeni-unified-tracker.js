/**
 * Albeni 1905 — Unified AI Orchestration Layer Tracker (Layer 1)
 *
 * CONSOLIDATED SCRIPT - Merges albeni-ai-tracker.js + tracking.js
 *
 * Layer 1 Focus: Signal collection only
 * - UTM/campaign detection
 * - Behavioral signals (dwell, scroll, mouse, video, exit intent)
 * - Cross-domain identity preservation
 * - Multi-language support
 * - Event dispatch to /v1/track/event endpoint
 * - Bot Shield behavioral fingerprint
 * - ADV routing for paid traffic
 *
 * Layer 2 (separate file): Behavioral engine, IDS calculation, cluster prediction,
 * content personalization, Klaviyo sync
 *
 * Installation:
 * Insert in <head> of all 4 domains:
 * - worldofmerino.com (TOFU)
 * - merinouniversity.com (MOFU)
 * - perfectmerinoshirt.com (BOFU Tech)
 * - albeni1905.com (BOFU Heritage)
 *
 * Configuration (in <head> before this script):
 *   window.ALBENI_AI = {
 *     endpoint: 'https://your-ml-worker-url:8000',
 *     debug: false,
 *     domain_type: 'tofu'  // or 'mofu', 'bofu_tech', 'bofu_heritage'
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
  const DOMAIN_TYPE = CONFIG.domain_type || null;

  const ECOSYSTEM_DOMAINS = [
    'worldofmerino.com',
    'merinouniversity.com',
    'perfectmerinoshirt.com',
    'albeni1905.com'
  ];

  const SUPPORTED_LANGS = ['it', 'en', 'fr', 'de', 'es'];

  function log(...args) {
    if (DEBUG) console.log('[Albeni AI]', ...args);
  }

  // ================================================================
  // 1. LANGUAGE DETECTION (from tracking.js - more robust)
  // ================================================================
  function getLanguageContext() {
    const pathSegments = window.location.pathname.split('/');

    // Check URL path first (e.g., /de/..., /fr/...)
    const urlLang = SUPPORTED_LANGS.find(lang => pathSegments.includes(lang));
    if (urlLang) return urlLang;

    // Check HTML lang attribute
    const htmlLang = document.documentElement.lang;
    if (htmlLang) {
      const shortLang = htmlLang.split('-')[0].toLowerCase();
      if (SUPPORTED_LANGS.includes(shortLang)) return shortLang;
    }

    // Fallback to browser language
    const browserLang = (navigator.language || navigator.userLanguage || 'it')
      .split('-')[0]
      .toLowerCase();
    return SUPPORTED_LANGS.includes(browserLang) ? browserLang : 'it';
  }

  const currentLang = getLanguageContext();

  // ================================================================
  // 2. VISITOR ID SYSTEM (albeni_visitor_id from tracker.js)
  // ================================================================
  function getOrCreateVisitorId() {
    let id = localStorage.getItem('albeni_visitor_id');
    if (!id) {
      id = 'v_' + Date.now().toString(36) + '_' + Math.random().toString(36).substr(2, 9);
      localStorage.setItem('albeni_visitor_id', id);
    }
    return id;
  }

  const visitorId = getOrCreateVisitorId();

  // ================================================================
  // 3. CROSS-DOMAIN UID PRESERVATION (from tracking.js)
  // ================================================================
  const urlParams = new URLSearchParams(window.location.search);
  let uid = urlParams.get('uid') || localStorage.getItem('albeni_uid');

  if (!uid) {
    uid = 'uid_' + Date.now().toString(36) + '_' + Math.random().toString(36).substr(2, 9);
  }
  localStorage.setItem('albeni_uid', uid);

  function preserveUID() {
    document.querySelectorAll('a[href]').forEach(link => {
      try {
        const url = new URL(link.href);
        if (ECOSYSTEM_DOMAINS.some(d => url.hostname.includes(d))) {
          if (!url.searchParams.has('uid')) {
            url.searchParams.set('uid', uid);
            url.searchParams.set('lang', currentLang);
            link.href = url.toString();
          }
        }
      } catch (e) {
        // Skip invalid URLs
      }
    });
  }

  // Run on load and on dynamic content changes
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', preserveUID);
  } else {
    preserveUID();
  }

  // Watch for dynamically added links (MutationObserver from tracking.js)
  const observer = new MutationObserver(preserveUID);
  observer.observe(document.body || document.documentElement, {
    childList: true,
    subtree: true
  });

  // ================================================================
  // 4. UTM SENSOR — Campaign Data Detection
  // ================================================================
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
  // 5. SESSION & BEHAVIORAL TRACKING INITIALIZATION
  // ================================================================
  const sessionStart = Date.now();
  const pageStartTime = Date.now();

  let mouseEventCount = 0;
  let maxScrollDepth = 0;
  let dwellTriggered = false;
  let exitTriggered = false;

  // Page view counter
  let pageViewCount = parseInt(sessionStorage.getItem('albeni_pageviews') || '0') + 1;
  sessionStorage.setItem('albeni_pageviews', pageViewCount.toString());

  // Initialize session start timestamp
  if (!sessionStorage.getItem('albeni_session_start')) {
    sessionStorage.setItem('albeni_session_start', Date.now().toString());
  }

  // Scroll milestone tracking (from tracking.js)
  const scrollMilestones = [25, 50, 75, 90];
  const triggeredMilestones = new Set();

  // ================================================================
  // 6. MOUSE & CLICK EVENTS (throttled)
  // ================================================================
  let lastMouseTime = 0;
  document.addEventListener('mousemove', function() {
    const now = Date.now();
    if (now - lastMouseTime > 500) { // Max 2 events/second
      mouseEventCount++;
      lastMouseTime = now;
    }
  }, { passive: true });

  document.addEventListener('click', function() {
    mouseEventCount++;
  }, { passive: true });

  // ================================================================
  // 7. SCROLL DEPTH TRACKING (merged: continuous + milestones)
  // ================================================================
  let scrollTimeout;
  function updateScrollDepth() {
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    const docHeight = Math.max(
      document.body.scrollHeight,
      document.documentElement.scrollHeight
    ) - window.innerHeight;

    if (docHeight > 0) {
      // Continuous tracking (from tracker.js)
      const depth = Math.round((scrollTop / docHeight) * 100);
      if (depth > maxScrollDepth) {
        maxScrollDepth = depth;
      }

      // Milestone tracking (from tracking.js)
      scrollMilestones.forEach(milestone => {
        if (depth >= milestone && !triggeredMilestones.has(milestone)) {
          triggeredMilestones.add(milestone);
          sendSignal('scroll_depth', { depth: milestone });
        }
      });
    }
  }

  window.addEventListener('scroll', function() {
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(updateScrollDepth, 200);
  }, { passive: true });

  // ================================================================
  // 8. DWELL TIME SENSOR (60s threshold from tracking.js)
  // ================================================================
  setTimeout(() => {
    if (!dwellTriggered && !document.hidden) {
      sendSignal('dwell_time_reached', { seconds: 60 });
      dwellTriggered = true;
    }
  }, 60000);

  // Track when user returns to tab after 60s
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !dwellTriggered) {
      const elapsed = (Date.now() - pageStartTime) / 1000;
      if (elapsed >= 60) {
        sendSignal('dwell_time_reached', { seconds: Math.round(elapsed) });
        dwellTriggered = true;
      }
    }
  });

  // ================================================================
  // 9. TECHNICAL INTERACTION SENSOR (from tracking.js)
  // ================================================================
  const interactionSelectors = [
    '.btn-compare',           // Weight comparison buttons
    '.video-material',        // Material Science videos
    '.download-lead-magnet',  // Lead magnet downloads
    '.product-detail',        // Product detail clicks
    '.add-to-cart',          // Add to cart actions
    '.size-selector',        // Size selection
    '.weight-selector',      // Weight selection
    '[data-ai-track]'        // Custom tracking attribute
  ];

  document.addEventListener('click', (e) => {
    const target = e.target.closest(interactionSelectors.join(', '));
    if (!target) return;

    let interactionType = 'technical_interaction';

    if (target.matches('.btn-compare')) interactionType = 'click_comparison';
    else if (target.matches('.video-material')) interactionType = 'video_play';
    else if (target.matches('.download-lead-magnet')) interactionType = 'lead_magnet_download';
    else if (target.matches('.add-to-cart')) interactionType = 'add_to_cart';
    else if (target.matches('.product-detail')) interactionType = 'product_view';

    sendSignal(interactionType, {
      element: target.className,
      text: (target.innerText || '').substring(0, 100),
      context_lang: currentLang,
      data_track: target.dataset?.aiTrack || ''
    });
  });

  // ================================================================
  // 10. VIDEO ENGAGEMENT TRACKING (from tracking.js)
  // ================================================================
  document.querySelectorAll('video, iframe[src*="youtube"], iframe[src*="vimeo"]').forEach(video => {
    if (video.tagName === 'VIDEO') {
      video.addEventListener('play', () => {
        sendSignal('video_play', {
          src: video.src || video.currentSrc,
          duration: video.duration
        });
      });
    } else {
      // For embedded videos, track click on the iframe area
      video.addEventListener('click', () => {
        sendSignal('video_play', { src: video.src });
      });
    }
  });

  // ================================================================
  // 11. EXIT INTENT DETECTION (from tracking.js)
  // ================================================================
  if (window.innerWidth > 768) {
    document.addEventListener('mouseout', (e) => {
      if (!exitTriggered && e.clientY < 10 && e.relatedTarget === null) {
        sendSignal('exit_intent', {
          time_on_page: Math.round((Date.now() - pageStartTime) / 1000),
          max_scroll: Math.max(...triggeredMilestones, 0)
        });
        exitTriggered = true;
      }
    });
  }

  // ================================================================
  // 12. SIGNAL DISPATCHER (unified sendSignal)
  // ================================================================
  function sendSignal(eventType, metadata = {}) {
    const dwellTime = Date.now() - sessionStart;
    const sessionDuration = parseInt(
      sessionStorage.getItem('albeni_session_start') || Date.now().toString()
    );

    const payload = {
      event_type: eventType,
      visitor_id: visitorId,
      uid: uid,
      timestamp: new Date().toISOString(),
      page_url: window.location.href,
      domain: window.location.hostname,
      domain_type: DOMAIN_TYPE,
      language: currentLang,
      dwell_time_ms: dwellTime,
      mouse_events: mouseEventCount,
      scroll_depth_pct: maxScrollDepth,
      page_views: pageViewCount,
      session_duration_ms: Date.now() - sessionDuration,
      device: /Mobi|Android/i.test(navigator.userAgent) ? 'mobile' : 'desktop',
      user_agent: navigator.userAgent,
      campaign: activeCampaign,
      referrer: document.referrer,
      ...(metadata || {}),
    };

    log('Sending signal:', eventType, payload);

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
  // 13. BOT SHIELD — Behavioral Fingerprint (from tracker.js)
  // ================================================================
  function sendBotShieldCheck() {
    const dwellTime = Date.now() - sessionStart;
    const isPaid = !!(activeCampaign && (activeCampaign.gclid || activeCampaign.fbclid));

    const shieldData = {
      visitor_id: visitorId,
      ip_address: '', // Server-side detection (IP not available client-side)
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
  // 14. ADV ROUTING — Dynamic Landing Check (from tracker.js)
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
      language: currentLang,
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
  // 15. CROSS-DOMAIN SHIFT BANNER (from tracker.js)
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
  // AUTO-FIRE EVENTS
  // ================================================================

  // Page view on load
  sendSignal('page_view', {
    title: document.title,
    path: window.location.pathname,
    campaign: activeCampaign ? 'detected' : 'organic'
  });

  // ADV routing check (only for paid traffic)
  checkADVRouting();

  // Bot Shield check after 5 seconds (enough time to gather behavioral data)
  setTimeout(sendBotShieldCheck, 5000);

  // Send engagement data on page unload
  window.addEventListener('beforeunload', function() {
    sendSignal('page_exit', {
      final_dwell_ms: Date.now() - sessionStart,
      final_scroll_depth: maxScrollDepth,
      final_mouse_events: mouseEventCount,
    });
  });

  // ================================================================
  // PUBLIC API EXPOSURE
  // ================================================================
  window.albeniAI = {
    // Custom event tracking
    track: sendSignal,

    // Retrieve campaign attribution data
    getCampaign: function() {
      return activeCampaign;
    },

    // Get persistent visitor ID
    getVisitorId: function() {
      return visitorId;
    },

    // Get detected language
    getLang: function() {
      return currentLang;
    },

    // Get cross-domain UID
    getUID: function() {
      return uid;
    },

    // Get session metrics
    getSessionMetrics: function() {
      return {
        dwell_ms: Date.now() - sessionStart,
        scroll_depth: maxScrollDepth,
        mouse_events: mouseEventCount,
        page_views: pageViewCount,
        milestones: Array.from(triggeredMilestones).sort((a, b) => a - b)
      };
    }
  };

  // ================================================================
  // CHATBOT BRIDGE — Expose sendSignal for the chat widget snippet
  // The chatbot snippet calls ALBENI_AI._sendSignal() to track
  // chat interactions (open, message, escalation) as IDS signals.
  // ================================================================
  CONFIG._sendSignal = sendSignal;

  // ================================================================
  // INITIALIZATION LOG
  // ================================================================
  log('Albeni AI Unified Tracker initialized', {
    version: '2.0-merged',
    domain: window.location.hostname,
    domain_type: DOMAIN_TYPE,
    language: currentLang,
    visitor_id: visitorId,
    uid: uid,
    campaign: activeCampaign ? 'detected' : 'organic',
    page_views: pageViewCount,
  });

  console.debug(
    `[Albeni AI] Tracker active | Visitor: ${visitorId} | Lang: ${currentLang} | Domain: ${window.location.hostname}`
  );

})();

/*
 * ========================================
 * CSS CLASS REFERENCE FOR DEVELOPERS
 * ========================================
 *
 * Add these CSS classes to your HTML elements for automatic tracking:
 *
 * .btn-compare          - Weight comparison buttons (150g vs 190g)
 * .video-material       - Material Science video play buttons
 * .download-lead-magnet - Lead magnet download buttons/links
 * .product-detail       - Product detail page links
 * .add-to-cart          - Add to cart buttons
 * .size-selector        - Size selection elements
 * .weight-selector      - Weight selection elements (150g/190g)
 * [data-ai-track="X"]   - Custom tracking (X = your label)
 *
 * Example:
 *   <button class="btn-compare">Confronta 150g vs 190g</button>
 *   <a class="download-lead-magnet" href="/guide.pdf">Scarica la Guida</a>
 *   <button data-ai-track="custom-action">Action</button>
 *
 * ========================================
 * PUBLIC API USAGE
 * ========================================
 *
 * Track custom events:
 *   window.albeniAI.track('custom_event', { custom_field: 'value' });
 *
 * Get campaign attribution:
 *   const campaign = window.albeniAI.getCampaign();
 *   console.log(campaign.source); // 'google', 'facebook', etc.
 *
 * Get visitor tracking IDs:
 *   const visitorId = window.albeniAI.getVisitorId();
 *   const uid = window.albeniAI.getUID();
 *   const lang = window.albeniAI.getLang();
 *
 * Get session engagement metrics:
 *   const metrics = window.albeniAI.getSessionMetrics();
 *   console.log(metrics.dwell_ms, metrics.scroll_depth, metrics.milestones);
 */
