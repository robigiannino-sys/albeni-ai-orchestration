/**
 * AI Orchestration Layer - Tracking Snippet (Multilingua)
 * Albeni 1905 - Invisible Luxury Ecosystem
 *
 * Deploy this snippet in the <head> of ALL websites:
 * - worldofmerino.com (WordPress - TOFU)
 * - merinouniversity.com (WordPress - MOFU)
 * - perfectmerinoshirt.com (Shopify - BOFU Tech)
 * - albeni1905.com (Shopify - BOFU Heritage)
 *
 * Supports: IT, EN, FR, DE, ES
 *
 * INSTALLATION:
 * 1. Copy this script into the <head> tag of every page
 * 2. Replace API_BASE_URL with your actual AI Router endpoint
 * 3. Add CSS classes to interactive elements (see bottom of file)
 */
(function() {
    'use strict';

    // ========================================
    // CONFIGURATION - EDIT THIS
    // ========================================
    const API_BASE_URL = 'https://api.albeni1905.com'; // Your AI Router URL

    // ========================================
    // 1. LANGUAGE DETECTION
    // ========================================
    const getLanguageContext = () => {
        const pathSegments = window.location.pathname.split('/');
        const supportedLangs = ['it', 'en', 'fr', 'de', 'es'];

        // Check URL path first (e.g., /de/..., /fr/...)
        const urlLang = supportedLangs.find(lang => pathSegments.includes(lang));
        if (urlLang) return urlLang;

        // Check HTML lang attribute
        const htmlLang = document.documentElement.lang;
        if (htmlLang) {
            const shortLang = htmlLang.split('-')[0].toLowerCase();
            if (supportedLangs.includes(shortLang)) return shortLang;
        }

        // Fallback to browser language
        const browserLang = (navigator.language || navigator.userLanguage || 'it').split('-')[0].toLowerCase();
        return supportedLangs.includes(browserLang) ? browserLang : 'it';
    };

    const currentLang = getLanguageContext();

    // ========================================
    // 2. CROSS-DOMAIN IDENTITY
    // ========================================
    const urlParams = new URLSearchParams(window.location.search);
    let userId = urlParams.get('uid') || localStorage.getItem('albeni_uid');

    if (!userId) {
        userId = 'uid_' + Date.now().toString(36) + '_' + Math.random().toString(36).substr(2, 9);
    }
    localStorage.setItem('albeni_uid', userId);

    // Preserve UID in all internal links
    const preserveUID = () => {
        const ecosystemDomains = [
            'worldofmerino.com',
            'merinouniversity.com',
            'perfectmerinoshirt.com',
            'albeni1905.com'
        ];

        document.querySelectorAll('a[href]').forEach(link => {
            try {
                const url = new URL(link.href);
                if (ecosystemDomains.some(d => url.hostname.includes(d))) {
                    if (!url.searchParams.has('uid')) {
                        url.searchParams.set('uid', userId);
                        url.searchParams.set('lang', currentLang);
                        link.href = url.toString();
                    }
                }
            } catch (e) { /* Skip invalid URLs */ }
        });
    };

    // Run on load and on dynamic content changes
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', preserveUID);
    } else {
        preserveUID();
    }

    // Watch for dynamically added links
    const observer = new MutationObserver(preserveUID);
    observer.observe(document.body || document.documentElement, {
        childList: true,
        subtree: true
    });

    // ========================================
    // 3. SIGNAL DISPATCHER
    // ========================================
    const signalQueue = [];
    let isProcessing = false;

    const sendSignal = (eventType, metadata = {}) => {
        const payload = {
            user_id: userId,
            domain: window.location.hostname,
            lang: currentLang,
            event_type: eventType,
            metadata: {
                ...metadata,
                context_lang: currentLang,
                page_url: window.location.href,
                referrer: document.referrer
            },
            page_url: window.location.href,
            timestamp: Date.now()
        };

        // Use sendBeacon for reliability (survives page unload)
        if (navigator.sendBeacon) {
            navigator.sendBeacon(
                `${API_BASE_URL}/v1/track/event`,
                new Blob([JSON.stringify(payload)], { type: 'application/json' })
            );
        } else {
            // Fallback to fetch
            fetch(`${API_BASE_URL}/v1/track/event`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                keepalive: true
            }).catch(err => console.debug('AI Signal:', err.message));
        }
    };

    // ========================================
    // 4. DWELL TIME SENSOR (>60s)
    // ========================================
    let dwellTriggered = false;
    let pageStartTime = Date.now();

    setTimeout(() => {
        if (!dwellTriggered && !document.hidden) {
            sendSignal('dwell_time_reached', { seconds: 60 });
            dwellTriggered = true;
        }
    }, 60000);

    // Also track when user returns to tab after 60s
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && !dwellTriggered) {
            const elapsed = (Date.now() - pageStartTime) / 1000;
            if (elapsed >= 60) {
                sendSignal('dwell_time_reached', { seconds: Math.round(elapsed) });
                dwellTriggered = true;
            }
        }
    });

    // ========================================
    // 5. SCROLL DEPTH SENSOR (25/50/75/90%)
    // ========================================
    const scrollMilestones = [25, 50, 75, 90];
    const triggeredMilestones = new Set();

    const checkScroll = () => {
        const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
        if (scrollHeight <= 0) return;

        const scrollPercent = Math.round((window.scrollY / scrollHeight) * 100);

        scrollMilestones.forEach(milestone => {
            if (scrollPercent >= milestone && !triggeredMilestones.has(milestone)) {
                triggeredMilestones.add(milestone);
                sendSignal('scroll_depth', { depth: milestone });
            }
        });
    };

    // Throttled scroll listener
    let scrollTimeout;
    window.addEventListener('scroll', () => {
        if (scrollTimeout) return;
        scrollTimeout = setTimeout(() => {
            checkScroll();
            scrollTimeout = null;
        }, 200);
    }, { passive: true });

    // ========================================
    // 6. TECHNICAL INTERACTION SENSOR
    // ========================================
    const interactionSelectors = [
        '.btn-compare',           // Weight comparison buttons (150g vs 190g)
        '.video-material',        // Material Science videos
        '.download-lead-magnet',  // Lead magnet downloads
        '.product-detail',        // Product detail clicks
        '.add-to-cart',          // Add to cart actions
        '.size-selector',        // Size selection
        '.weight-selector',      // Weight selection (150g/190g)
        '[data-ai-track]'        // Custom tracking attribute
    ];

    document.addEventListener('click', (e) => {
        const target = e.target.closest(interactionSelectors.join(', '));
        if (!target) return;

        let interactionType = 'technical_interaction';

        // Determine specific interaction type
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

    // ========================================
    // 7. VIDEO ENGAGEMENT TRACKING
    // ========================================
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

    // ========================================
    // 8. AI ROUTING HOOK
    // ========================================
    window.checkAIRouting = async function() {
        try {
            const response = await fetch(
                `${API_BASE_URL}/v1/router/assign?user_id=${userId}&lang=${currentLang}`
            );
            const data = await response.json();

            if (data.redirect_to && !window.location.origin.includes(new URL(data.redirect_to).hostname)) {
                // Preserve UID and language in redirect
                const redirectUrl = new URL(data.redirect_to);
                redirectUrl.searchParams.set('uid', userId);
                redirectUrl.searchParams.set('lang', currentLang);
                window.location.href = redirectUrl.toString();
            }

            return data;
        } catch (err) {
            console.debug('AI Routing check failed:', err.message);
            return null;
        }
    };

    // ========================================
    // 9. ROUTING STATUS (for CTA personalization)
    // ========================================
    window.getAIStatus = async function() {
        try {
            const response = await fetch(
                `${API_BASE_URL}/v1/router/status?user_id=${userId}`
            );
            return await response.json();
        } catch (err) {
            return { ids_score: 0, cluster: 'unknown', intent_stage: 'TOFU' };
        }
    };

    // ========================================
    // 10. PAGE VIEW TRACKING
    // ========================================
    sendSignal('page_view', {
        title: document.title,
        path: window.location.pathname
    });

    // ========================================
    // 11. EXIT INTENT (desktop)
    // ========================================
    if (window.innerWidth > 768) {
        let exitTriggered = false;
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

    // Console log for development verification
    console.debug(`[Albeni AI] Tracking active | User: ${userId} | Lang: ${currentLang} | Domain: ${window.location.hostname}`);

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
 */
