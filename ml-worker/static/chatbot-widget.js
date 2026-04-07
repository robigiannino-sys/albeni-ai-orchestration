/**
 * Albeni 1905 — Customer Care Chat Widget (WPCode Snippet)
 * ============================================================
 * Embed this via WPCode on all 4 ecosystem domains.
 *
 * DEPENDS ON: albeni-unified-tracker.js (reads window.ALBENI_AI config
 *             and localStorage keys: albeni_uid, albeni_visitor_id)
 *
 * Configuration (already set by unified tracker):
 *   window.ALBENI_AI = {
 *     endpoint: 'https://your-ml-worker:8000',
 *     debug: false,
 *     domain_type: 'tofu' | 'mofu' | 'bofu_tech' | 'bofu_heritage'
 *   };
 *
 * WPCode settings:
 *   - Insert: Site Wide Footer
 *   - Type: JavaScript Snippet
 *   - Priority: 20 (after tracker at 10)
 *   - Device: All
 * ============================================================
 */
(function () {
  'use strict';

  // ── CONFIG ──────────────────────────────────────────────
  var AI = window.ALBENI_AI || {};
  var API = AI.endpoint || 'http://localhost:8000';
  var DEBUG = AI.debug || false;

  function log() {
    if (DEBUG) console.log.apply(console, ['[Albeni Chat]'].concat(Array.from(arguments)));
  }

  // ── DETECT LANGUAGE (same logic as unified tracker) ─────
  function detectLang() {
    var segs = window.location.pathname.split('/');
    var langs = ['it', 'en', 'de', 'fr'];
    for (var i = 0; i < segs.length; i++) {
      if (langs.indexOf(segs[i]) !== -1) return segs[i];
    }
    var hl = (document.documentElement.lang || '').split('-')[0].toLowerCase();
    if (langs.indexOf(hl) !== -1) return hl;
    var bl = (navigator.language || 'it').split('-')[0].toLowerCase();
    return langs.indexOf(bl) !== -1 ? bl : 'it';
  }

  var LANG = detectLang();

  // ── DETECT DOMAIN TYPE ─────────────────────────────────
  var DOMAIN_TYPE = (AI.domain_type || '').toLowerCase();
  if (!DOMAIN_TYPE) {
    var h = window.location.hostname;
    if (h.indexOf('worldofmerino') !== -1)      DOMAIN_TYPE = 'tofu';
    else if (h.indexOf('merinouniversity') !== -1) DOMAIN_TYPE = 'mofu';
    else if (h.indexOf('perfectmerino') !== -1)    DOMAIN_TYPE = 'bofu_tech';
    else                                            DOMAIN_TYPE = 'bofu_heritage';
  }

  // ── READ IDENTITY FROM TRACKER ─────────────────────────
  var USER_ID = null;
  var USER_EMAIL = null;
  try {
    USER_ID = localStorage.getItem('albeni_uid') || localStorage.getItem('albeni_visitor_id') || null;
  } catch (e) {}

  // ================================================================
  // DOMAIN PERSONALITY — Name, avatar, tone, colors per domain
  // ================================================================
  var DOMAIN_PROFILES = {
    tofu: {
      name: 'World of Merino',
      initials: 'WM',
      tagline: { it: 'Il tuo viaggio nel merino', en: 'Your merino journey', de: 'Ihre Merino-Reise', fr: 'Votre voyage m\u00e9rinos' },
      accentColor: '#5b8a72',  // nature green
      footerText: 'World of Merino \u2014 Discover the Fiber'
    },
    mofu: {
      name: 'Merino University',
      initials: 'MU',
      tagline: { it: 'Impara dalla fibra', en: 'Learn from the fiber', de: 'Lernen Sie von der Faser', fr: 'Apprenez de la fibre' },
      accentColor: '#2a6496',  // academic blue
      footerText: 'Merino University \u2014 Knowledge Hub'
    },
    bofu_tech: {
      name: 'Perfect Merino Shirt',
      initials: 'PM',
      tagline: { it: 'La t-shirt perfetta, per te', en: 'The perfect t-shirt, for you', de: 'Das perfekte T-Shirt f\u00fcr Sie', fr: 'Le t-shirt parfait pour vous' },
      accentColor: '#4a4a4a',  // tech gray
      footerText: 'Perfect Merino Shirt \u2014 Engineered Comfort'
    },
    bofu_heritage: {
      name: 'Albeni 1905',
      initials: 'A',
      tagline: { it: 'Come posso aiutarti?', en: 'How can I help?', de: 'Wie kann ich helfen?', fr: 'Comment puis-je aider ?' },
      accentColor: '#b8860b',  // heritage gold
      footerText: 'Albeni 1905 \u2014 Invisible Luxury'
    }
  };

  var PROFILE = DOMAIN_PROFILES[DOMAIN_TYPE] || DOMAIN_PROFILES.bofu_heritage;

  // ================================================================
  // DOMAIN-SPECIFIC QUICK ACTIONS
  // Each domain surfaces the actions most relevant to its funnel role
  // ================================================================
  var DOMAIN_QUICK_ACTIONS = {
    // TOFU: Discovery & inspiration → push to MU and Albeni
    tofu: {
      it: [
        { l: 'Cos\u2019\u00e8 il merino?', m: 'Cos\u2019\u00e8 la fibra merino e perch\u00e9 \u00e8 speciale?' },
        { l: 'Merino vs cotone', m: 'Quali sono le differenze tra merino e cotone?' },
        { l: 'Sostenibilit\u00e0', m: 'Il merino \u00e8 sostenibile? Come viene prodotto?' },
        { l: 'Scopri i prodotti', m: 'Dove posso vedere i prodotti in merino Albeni?' }
      ],
      en: [
        { l: 'What is merino?', m: 'What is merino fiber and why is it special?' },
        { l: 'Merino vs cotton', m: 'What are the differences between merino and cotton?' },
        { l: 'Sustainability', m: 'Is merino sustainable? How is it produced?' },
        { l: 'See products', m: 'Where can I see Albeni merino products?' }
      ],
      de: [
        { l: 'Was ist Merino?', m: 'Was ist Merinofaser und warum ist sie besonders?' },
        { l: 'Merino vs Baumwolle', m: 'Was sind die Unterschiede zwischen Merino und Baumwolle?' },
        { l: 'Nachhaltigkeit', m: 'Ist Merino nachhaltig? Wie wird es hergestellt?' },
        { l: 'Produkte entdecken', m: 'Wo kann ich Albeni Merino-Produkte sehen?' }
      ],
      fr: [
        { l: 'Qu\u2019est-ce que le m\u00e9rinos ?', m: 'Qu\u2019est-ce que la fibre m\u00e9rinos et pourquoi est-elle sp\u00e9ciale ?' },
        { l: 'M\u00e9rinos vs coton', m: 'Quelles sont les diff\u00e9rences entre le m\u00e9rinos et le coton ?' },
        { l: 'Durabilit\u00e9', m: 'Le m\u00e9rinos est-il durable ? Comment est-il produit ?' },
        { l: 'Voir les produits', m: 'O\u00f9 puis-je voir les produits Albeni en m\u00e9rinos ?' }
      ]
    },
    // MOFU: Technical education → push to perfectmerinoshirt or albeni1905
    mofu: {
      it: [
        { l: 'Cut & Sew vs Knit', m: 'Qual \u00e8 la differenza tra Cut & Sew e maglia?' },
        { l: '150g vs 190g', m: 'Che differenza c\u2019\u00e8 tra la versione 150g e 190g?' },
        { l: 'Certificazione ZQ', m: 'Cosa significa la certificazione ZQ del merino?' },
        { l: 'Voglio acquistare', m: 'Sono convinto, dove posso comprare?' }
      ],
      en: [
        { l: 'Cut & Sew vs Knit', m: 'What is the difference between Cut & Sew and knit?' },
        { l: '150g vs 190g', m: 'What is the difference between the 150g and 190g versions?' },
        { l: 'ZQ certification', m: 'What does the ZQ merino certification mean?' },
        { l: 'Ready to buy', m: 'I\u2019m convinced, where can I buy?' }
      ],
      de: [
        { l: 'Cut & Sew vs Strick', m: 'Was ist der Unterschied zwischen Cut & Sew und Strick?' },
        { l: '150g vs 190g', m: 'Was ist der Unterschied zwischen der 150g- und 190g-Version?' },
        { l: 'ZQ-Zertifizierung', m: 'Was bedeutet die ZQ-Merinozertifizierung?' },
        { l: 'Jetzt kaufen', m: 'Ich bin \u00fcberzeugt, wo kann ich kaufen?' }
      ],
      fr: [
        { l: 'Cut & Sew vs tricot', m: 'Quelle est la diff\u00e9rence entre Cut & Sew et tricot ?' },
        { l: '150g vs 190g', m: 'Quelle est la diff\u00e9rence entre les versions 150g et 190g ?' },
        { l: 'Certification ZQ', m: 'Que signifie la certification ZQ du m\u00e9rinos ?' },
        { l: 'Acheter', m: 'Je suis convaincu, o\u00f9 puis-je acheter ?' }
      ]
    },
    // BOFU Tech: Technical buyers → sizing, specs, direct purchase
    bofu_tech: {
      it: [
        { l: 'Trova la tua taglia', m: 'Aiutami a trovare la mia taglia' },
        { l: '150g o 190g?', m: 'Quale peso \u00e8 meglio per me, 150g o 190g?' },
        { l: 'Sotto la giacca', m: 'Funziona bene sotto un blazer?' },
        { l: 'Spedizione e resi', m: 'Come funzionano spedizione e resi?' }
      ],
      en: [
        { l: 'Find your size', m: 'Help me find my size' },
        { l: '150g or 190g?', m: 'Which weight is best for me, 150g or 190g?' },
        { l: 'Under a blazer', m: 'Does it work well under a blazer?' },
        { l: 'Shipping & returns', m: 'How do shipping and returns work?' }
      ],
      de: [
        { l: 'Gr\u00f6\u00dfe finden', m: 'Helfen Sie mir, meine Gr\u00f6\u00dfe zu finden' },
        { l: '150g oder 190g?', m: 'Welches Gewicht ist besser f\u00fcr mich, 150g oder 190g?' },
        { l: 'Unter dem Sakko', m: 'Funktioniert es gut unter einem Sakko?' },
        { l: 'Versand & Retouren', m: 'Wie funktionieren Versand und R\u00fccksendungen?' }
      ],
      fr: [
        { l: 'Trouver votre taille', m: 'Aidez-moi \u00e0 trouver ma taille' },
        { l: '150g ou 190g ?', m: 'Quel grammage est le mieux pour moi, 150g ou 190g ?' },
        { l: 'Sous la veste', m: 'Fonctionne-t-il bien sous un blazer ?' },
        { l: 'Livraison & retours', m: 'Comment fonctionnent la livraison et les retours ?' }
      ]
    },
    // BOFU Heritage (albeni1905.com): CONVERSION — sizing, purchase, post-purchase
    bofu_heritage: {
      it: [
        { l: 'Trova la tua taglia', m: 'Aiutami a trovare la mia taglia' },
        { l: 'Spedizione e resi', m: 'Come funzionano spedizione e resi?' },
        { l: 'Cura del capo', m: 'Come si lava la t-shirt in merino?' },
        { l: 'Ordine in corso', m: 'Ho un ordine in corso, a che punto \u00e8?' }
      ],
      en: [
        { l: 'Find your size', m: 'Help me find my size' },
        { l: 'Shipping & returns', m: 'How do shipping and returns work?' },
        { l: 'Garment care', m: 'How do I wash the merino t-shirt?' },
        { l: 'My order', m: 'I have a pending order, what\u2019s the status?' }
      ],
      de: [
        { l: 'Gr\u00f6\u00dfe finden', m: 'Helfen Sie mir, meine Gr\u00f6\u00dfe zu finden' },
        { l: 'Versand & Retouren', m: 'Wie funktionieren Versand und R\u00fccksendungen?' },
        { l: 'Pflege', m: 'Wie w\u00e4scht man das Merino-T-Shirt?' },
        { l: 'Meine Bestellung', m: 'Ich habe eine laufende Bestellung, was ist der Status?' }
      ],
      fr: [
        { l: 'Trouver votre taille', m: 'Aidez-moi \u00e0 trouver ma taille' },
        { l: 'Livraison & retours', m: 'Comment fonctionnent la livraison et les retours ?' },
        { l: 'Entretien', m: 'Comment laver le t-shirt en m\u00e9rinos ?' },
        { l: 'Ma commande', m: 'J\u2019ai une commande en cours, o\u00f9 en est-elle ?' }
      ]
    }
  };

  // ── I18N (shared strings) ──────────────────────────────
  var i18n = {
    placeholder: { it: 'Scrivi un messaggio...', en: 'Type a message...', de: 'Nachricht schreiben...', fr: '\u00c9crivez un message...' },
    error: {
      it: 'Mi dispiace, si \u00e8 verificato un errore. Riprova tra un momento.',
      en: 'Sorry, an error occurred. Please try again in a moment.',
      de: 'Entschuldigung, ein Fehler ist aufgetreten. Bitte versuchen Sie es sp\u00e4ter erneut.',
      fr: 'D\u00e9sol\u00e9, une erreur est survenue. Veuillez r\u00e9essayer dans un instant.'
    },
    fallbackWelcome: {
      it: 'Ciao! Come posso aiutarti?', en: 'Hello! How can I help you?',
      de: 'Hallo! Wie kann ich Ihnen helfen?', fr: 'Bonjour ! Comment puis-je vous aider ?'
    },
    eduHint: {
      it: 'Approfondisci su Merino University', en: 'Learn more on Merino University',
      de: 'Mehr erfahren auf der Merino University', fr: 'En savoir plus sur Merino University'
    },
    escalated: {
      it: 'Richiesta inoltrata al team', en: 'Request forwarded to team',
      de: 'Anfrage an das Team weitergeleitet', fr: 'Demande transmise \u00e0 l\u2019\u00e9quipe'
    },
    sizingTitle: {
      it: 'La tua taglia consigliata', en: 'Your recommended size',
      de: 'Ihre empfohlene Gr\u00f6\u00dfe', fr: 'Votre taille recommand\u00e9e'
    },
    chest: { it: 'Petto', en: 'Chest', de: 'Brust', fr: 'Poitrine' },
    outOfRange: { it: 'Fuori range', en: 'Out of range', de: 'Au\u00dferhalb', fr: 'Hors gamme' },
    // Quick actions are now domain-specific (see DOMAIN_QUICK_ACTIONS above)
    quickActions: DOMAIN_QUICK_ACTIONS[DOMAIN_TYPE] || DOMAIN_QUICK_ACTIONS.bofu_heritage
  };

  function t(key) { return (i18n[key] || {})[LANG] || (i18n[key] || {}).en || ''; }

  // ── STATE ───────────────────────────────────────────────
  var SESSION_ID = null;
  var SENDING = false;
  var CHAT_OPEN = false;
  var INITIALIZED = false;

  // ── INJECT CSS ──────────────────────────────────────────
  var css = document.createElement('style');
  css.textContent = [
    ':root{--ab:#1a1a1a;--aw:#2c2b28;--ag:#b8860b;--acr:#faf8f5;--awh:#fff;--ag1:#f5f3f0;--ag2:#e8e5e0;--ag4:#a09890;--ag6:#6b6560;--ard:#c0392b;--agr:#27ae60;--abl:#2a6496;--ar:16px;--ars:10px;--af:-apple-system,BlinkMacSystemFont,"Segoe UI","Helvetica Neue",Arial,sans-serif;--at:0.25s cubic-bezier(0.4,0,0.2,1)}',
    '#ab-toggle{position:fixed;bottom:24px;right:24px;width:60px;height:60px;border-radius:50%;background:var(--aw);border:none;cursor:pointer;z-index:99999;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 20px rgba(0,0,0,.25);transition:transform var(--at),box-shadow var(--at)}',
    '#ab-toggle:hover{transform:scale(1.08);box-shadow:0 6px 28px rgba(0,0,0,.3)}',
    '#ab-toggle .ic,#ab-toggle .ix{position:absolute;transition:opacity var(--at),transform var(--at)}',
    '#ab-toggle .ix{opacity:0;transform:rotate(-90deg)}',
    '#ab-toggle.open .ic{opacity:0;transform:rotate(90deg)}',
    '#ab-toggle.open .ix{opacity:1;transform:rotate(0)}',
    '#ab-win{position:fixed;bottom:96px;right:24px;width:380px;max-width:calc(100vw - 32px);height:560px;max-height:calc(100vh - 120px);background:var(--awh);border-radius:var(--ar);box-shadow:0 8px 32px rgba(0,0,0,.12);display:flex;flex-direction:column;overflow:hidden;z-index:99998;opacity:0;transform:translateY(16px) scale(0.96);pointer-events:none;transition:opacity var(--at),transform var(--at)}',
    '#ab-win.vis{opacity:1;transform:translateY(0) scale(1);pointer-events:all}',
    '.ab-hd{background:var(--aw);color:var(--awh);padding:16px 20px;display:flex;align-items:center;gap:12px;flex-shrink:0}',
    '.ab-av{width:38px;height:38px;border-radius:50%;background:var(--ag);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;letter-spacing:.5px;flex-shrink:0;font-family:var(--af);color:var(--awh)}',
    '.ab-hi{flex:1}.ab-ht{font-family:var(--af);font-size:15px;font-weight:600;letter-spacing:.3px}',
    '.ab-hs{font-family:var(--af);font-size:11px;color:var(--ag4);margin-top:2px}',
    '.ab-dot{display:inline-block;width:7px;height:7px;background:var(--agr);border-radius:50%;margin-right:4px;vertical-align:middle}',
    '.ab-ls{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);color:var(--awh);border-radius:6px;padding:4px 6px;font-size:11px;font-family:var(--af);cursor:pointer;outline:none}',
    '.ab-ls option{color:var(--ab);background:var(--awh)}',
    '.ab-msgs{flex:1;overflow-y:auto;padding:16px;background:var(--ag1);scroll-behavior:smooth}',
    '.ab-msgs::-webkit-scrollbar{width:4px}.ab-msgs::-webkit-scrollbar-thumb{background:var(--ag2);border-radius:4px}',
    '.ab-m{max-width:82%;margin-bottom:10px;animation:abFI .3s ease forwards}',
    '.ab-mb{margin-right:auto}.ab-mu{margin-left:auto}',
    '.ab-bbl{padding:10px 14px;border-radius:var(--ars);font-family:var(--af);font-size:13.5px;line-height:1.55;box-shadow:0 2px 8px rgba(0,0,0,.06);word-break:break-word}',
    '.ab-mb .ab-bbl{background:var(--awh);color:var(--ab);border-bottom-left-radius:4px}',
    '.ab-mu .ab-bbl{background:var(--aw);color:var(--awh);border-bottom-right-radius:4px}',
    '.ab-mt{font-size:10px;color:var(--ag4);margin-top:3px;padding:0 4px}',
    '.ab-mb .ab-mt{text-align:left}.ab-mu .ab-mt{text-align:right}',
    '.ab-mb .ab-bbl a{color:var(--abl);text-decoration:none;font-weight:500}',
    '.ab-mb .ab-bbl a:hover{text-decoration:underline}',
    '.ab-typ{display:flex;gap:4px;padding:10px 16px;align-items:center}',
    '.ab-td{width:7px;height:7px;background:var(--ag4);border-radius:50%;animation:abTB 1.2s infinite}',
    '.ab-td:nth-child(2){animation-delay:.15s}.ab-td:nth-child(3){animation-delay:.3s}',
    '.ab-qa{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}',
    '.ab-qb{background:var(--ag1);border:1px solid var(--ag2);color:var(--aw);padding:6px 12px;border-radius:20px;font-size:12px;font-family:var(--af);cursor:pointer;transition:background var(--at);white-space:nowrap}',
    '.ab-qb:hover{background:var(--ag2)}',
    '.ab-sc{background:var(--acr);border:1px solid var(--ag2);border-radius:var(--ars);padding:12px;margin-top:8px}',
    '.ab-sct{font-weight:600;font-size:13px;margin-bottom:8px;color:var(--aw)}',
    '.ab-sr{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--ag2);font-size:12.5px}',
    '.ab-sr:last-child{border-bottom:none}',
    '.ab-sl{color:var(--ag6)}.ab-sv{font-weight:600;color:var(--aw)}',
    '.ab-esc{display:inline-flex;align-items:center;gap:4px;background:#fef3cd;color:#856404;padding:4px 10px;border-radius:12px;font-size:11px;font-weight:500;margin-top:6px;font-family:var(--af)}',
    '.ab-el{display:flex;align-items:center;gap:8px;background:var(--acr);border:1px solid var(--ag2);border-radius:8px;padding:8px 12px;margin-top:8px;text-decoration:none;transition:border-color var(--at)}',
    '.ab-el:hover{border-color:var(--ag)}',
    '.ab-eli{width:28px;height:28px;background:var(--ag);border-radius:6px;display:flex;align-items:center;justify-content:center;flex-shrink:0}',
    '.ab-elt{font-size:12px;color:var(--aw);font-weight:500;line-height:1.3}',
    '.ab-elh{font-size:10px;color:var(--ag4);font-weight:400}',
    '.ab-ia{display:flex;align-items:flex-end;padding:12px 16px;gap:10px;background:var(--awh);border-top:1px solid var(--ag2);flex-shrink:0}',
    '.ab-in{flex:1;border:1px solid var(--ag2);border-radius:var(--ars);padding:10px 14px;font-size:13.5px;font-family:var(--af);resize:none;max-height:100px;min-height:40px;line-height:1.4;outline:none;transition:border-color var(--at);background:var(--ag1)}',
    '.ab-in:focus{border-color:var(--ag);background:var(--awh)}',
    '.ab-in::placeholder{color:var(--ag4)}',
    '.ab-sb{width:40px;height:40px;border-radius:50%;border:none;background:var(--aw);color:var(--awh);cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:background var(--at),transform var(--at)}',
    '.ab-sb:hover{background:var(--ag);transform:scale(1.06)}',
    '.ab-sb:disabled{opacity:.4;cursor:not-allowed;transform:none}',
    '.ab-pw{text-align:center;padding:6px;font-size:9.5px;color:var(--ag4);background:var(--awh);letter-spacing:.3px;font-family:var(--af)}',
    '@keyframes abFI{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}',
    '@keyframes abTB{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-5px)}}',
    '@media(max-width:480px){#ab-win{bottom:0;right:0;width:100vw;max-width:100vw;height:100vh;max-height:100vh;border-radius:0}#ab-toggle.open{display:none}.ab-hd{padding:14px 16px}}'
  ].join('\n');
  document.head.appendChild(css);

  // ── INJECT HTML ─────────────────────────────────────────
  var frag = document.createDocumentFragment();

  // Toggle button
  var toggle = document.createElement('button');
  toggle.id = 'ab-toggle';
  toggle.style.background = PROFILE.accentColor;
  toggle.setAttribute('aria-label', 'Chat ' + PROFILE.name);
  toggle.innerHTML = '<svg class="ic" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg><svg class="ix" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
  frag.appendChild(toggle);

  // Chat window
  var win = document.createElement('div');
  win.id = 'ab-win';
  var tagline = (PROFILE.tagline || {})[LANG] || (PROFILE.tagline || {}).en || 'Online';
  win.innerHTML = [
    '<div class="ab-hd" style="background:' + PROFILE.accentColor + '">',
    '  <div class="ab-av" style="background:rgba(255,255,255,0.2)">' + PROFILE.initials + '</div>',
    '  <div class="ab-hi">',
    '    <div class="ab-ht">' + PROFILE.name + '</div>',
    '    <div class="ab-hs"><span class="ab-dot"></span>' + tagline + '</div>',
    '  </div>',
    '  <select class="ab-ls" id="ab-lang">',
    '    <option value="it"' + (LANG === 'it' ? ' selected' : '') + '>IT</option>',
    '    <option value="en"' + (LANG === 'en' ? ' selected' : '') + '>EN</option>',
    '    <option value="de"' + (LANG === 'de' ? ' selected' : '') + '>DE</option>',
    '    <option value="fr"' + (LANG === 'fr' ? ' selected' : '') + '>FR</option>',
    '  </select>',
    '</div>',
    '<div class="ab-msgs" id="ab-msgs"></div>',
    '<div class="ab-ia">',
    '  <textarea class="ab-in" id="ab-in" rows="1" placeholder="' + t('placeholder') + '" maxlength="1000"></textarea>',
    '  <button class="ab-sb" id="ab-sb" aria-label="Invia" style="background:' + PROFILE.accentColor + '">',
    '    <svg width="18" height="18" viewBox="0 0 24 24" fill="white"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>',
    '  </button>',
    '</div>',
    '<div class="ab-pw">' + PROFILE.footerText + '</div>'
  ].join('');
  frag.appendChild(win);

  // Mount to DOM
  if (document.body) {
    document.body.appendChild(frag);
  } else {
    document.addEventListener('DOMContentLoaded', function () {
      document.body.appendChild(frag);
    });
  }

  // ── DOM REFS ────────────────────────────────────────────
  function $(id) { return document.getElementById(id); }

  // ── TOGGLE ──────────────────────────────────────────────
  function onToggle() {
    CHAT_OPEN = !CHAT_OPEN;
    $('ab-toggle').classList.toggle('open', CHAT_OPEN);
    $('ab-win').classList.toggle('vis', CHAT_OPEN);
    if (CHAT_OPEN && !INITIALIZED) {
      startSession();
      INITIALIZED = true;
    }
    if (CHAT_OPEN) $('ab-in').focus();

    // Track chat open/close for behavioral engine
    trackChatEvent(CHAT_OPEN ? 'chat_opened' : 'chat_closed');
  }

  // ── LANGUAGE SWITCH ────────────────────────────────────
  function onLangChange(e) {
    LANG = e.target.value;
    $('ab-in').placeholder = t('placeholder');
    INITIALIZED = false;
    $('ab-msgs').innerHTML = '';
    SESSION_ID = null;
    startSession();
    INITIALIZED = true;
  }

  // ── AUTO RESIZE ────────────────────────────────────────
  function onInputChange() {
    var el = $('ab-in');
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 100) + 'px';
  }

  // ── SEND ───────────────────────────────────────────────
  function onKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  }

  function send(customText) {
    var text = customText || $('ab-in').value.trim();
    if (!text || SENDING) return;
    if (!customText) { $('ab-in').value = ''; $('ab-in').style.height = 'auto'; }

    addMsg('user', text);
    var typing = showTyping();
    SENDING = true;
    $('ab-sb').disabled = true;

    var params = new URLSearchParams({ message: text, language: LANG, domain_type: DOMAIN_TYPE });
    if (SESSION_ID) params.append('session_id', SESSION_ID);
    if (USER_EMAIL) params.append('user_email', USER_EMAIL);
    if (USER_ID) params.append('user_id', USER_ID);

    fetch(API + '/v1/chat/message?' + params.toString(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function (data) {
      typing.remove();
      if (data.session_id) SESSION_ID = data.session_id;
      addBotResponse(data);

      // Track chat interaction for IDS
      trackChatEvent('chat_message_sent', {
        topic: data.topic,
        source: (data.sources || [])[0] || 'unknown',
        escalated: data.escalated || false
      });
    })
    .catch(function (err) {
      typing.remove();
      addMsg('bot', t('error'));
      log('Error:', err);
    })
    .finally(function () {
      SENDING = false;
      $('ab-sb').disabled = false;
      $('ab-in').focus();
    });
  }

  // ── START SESSION ──────────────────────────────────────
  function startSession() {
    fetch(API + '/v1/chat/start?language=' + LANG + '&domain_type=' + DOMAIN_TYPE, { method: 'POST' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (data) {
        SESSION_ID = data.session_id;
        addMsg('bot', data.welcome_message);
        showQuickActions();
      })
      .catch(function () {
        addMsg('bot', t('fallbackWelcome'));
        showQuickActions();
      });
  }

  // ── RENDER ─────────────────────────────────────────────
  function addMsg(role, text) {
    var m = document.createElement('div');
    m.className = 'ab-m ' + (role === 'bot' ? 'ab-mb' : 'ab-mu');
    var b = document.createElement('div');
    b.className = 'ab-bbl';
    b.innerHTML = fmt(text);
    m.appendChild(b);
    var mt = document.createElement('div');
    mt.className = 'ab-mt';
    mt.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    m.appendChild(mt);
    $('ab-msgs').appendChild(m);
    scroll();
    return m;
  }

  function addBotResponse(data) {
    var m = document.createElement('div');
    m.className = 'ab-m ab-mb';
    var b = document.createElement('div');
    b.className = 'ab-bbl';
    b.innerHTML = fmt(data.response);
    m.appendChild(b);

    // Sizing card
    if (data.sizing_data && data.sizing_data.recommendations) {
      m.appendChild(buildSizingCard(data.sizing_data));
    }

    // Educational link
    if (data.intent_update && data.intent_update.suggested_link) {
      m.appendChild(buildEduLink(data.intent_update));
    }

    // Escalation
    if (data.escalated) {
      var esc = document.createElement('div');
      esc.className = 'ab-esc';
      esc.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg> ' + t('escalated');
      m.appendChild(esc);
    }

    var mt = document.createElement('div');
    mt.className = 'ab-mt';
    var timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    mt.textContent = timeStr + (data.response_time_ms ? ' \u00b7 ' + data.response_time_ms + 'ms' : '');
    m.appendChild(mt);

    $('ab-msgs').appendChild(m);
    scroll();
  }

  function buildSizingCard(sd) {
    var c = document.createElement('div');
    c.className = 'ab-sc';
    var h = '<div class="ab-sct">' + t('sizingTitle') + '</div>';
    h += '<div class="ab-sr"><span class="ab-sl">' + t('chest') + '</span><span class="ab-sv">' + sd.user_chest_cm + ' cm</span></div>';
    for (var k in sd.recommendations) {
      var r = sd.recommendations[k];
      if (r.recommended_size) {
        h += '<div class="ab-sr"><span class="ab-sl">' + r.fit_label + '</span><span class="ab-sv">' + r.recommended_size + ' (' + r.garment_chest_cm + ' cm)</span></div>';
      } else {
        h += '<div class="ab-sr"><span class="ab-sl">' + r.fit_label + '</span><span class="ab-sv" style="color:var(--ard)">' + t('outOfRange') + '</span></div>';
      }
    }
    c.innerHTML = h;
    return c;
  }

  function buildEduLink(iu) {
    var a = document.createElement('a');
    a.className = 'ab-el';
    a.href = iu.suggested_link.url || iu.suggested_link;
    a.target = '_blank';
    a.rel = 'noopener';
    a.innerHTML = '<div class="ab-eli"><svg width="14" height="14" viewBox="0 0 24 24" fill="white"><path d="M12 3L1 9l4 2.18v6L12 21l7-3.82v-6l2-1.09V17h2V9L12 3zm6.82 6L12 12.72 5.18 9 12 5.28 18.82 9zM17 15.99l-5 2.73-5-2.73v-3.72L12 15l5-2.73v3.72z"/></svg></div><div><div class="ab-elt">' + (iu.suggested_link.label || iu.suggested_link) + '</div><div class="ab-elh">' + t('eduHint') + '</div></div>';
    return a;
  }

  function showQuickActions() {
    var acts = i18n.quickActions[LANG] || i18n.quickActions.en;
    var qa = document.createElement('div');
    qa.className = 'ab-qa';
    qa.id = 'ab-qa';
    acts.forEach(function (a) {
      var btn = document.createElement('button');
      btn.className = 'ab-qb';
      btn.textContent = a.l;
      btn.addEventListener('click', function () {
        var el = $('ab-qa');
        if (el) el.remove();
        send(a.m);
      });
      qa.appendChild(btn);
    });
    $('ab-msgs').appendChild(qa);
    scroll();
  }

  function showTyping() {
    var el = document.createElement('div');
    el.className = 'ab-m ab-mb';
    el.innerHTML = '<div class="ab-bbl"><div class="ab-typ"><div class="ab-td"></div><div class="ab-td"></div><div class="ab-td"></div></div></div>';
    $('ab-msgs').appendChild(el);
    scroll();
    return el;
  }

  function fmt(text) {
    if (!text) return '';
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
  }

  function scroll() {
    requestAnimationFrame(function () {
      var el = $('ab-msgs');
      if (el) el.scrollTop = el.scrollHeight;
    });
  }

  // ── BEHAVIORAL ENGINE BRIDGE ───────────────────────────
  // Dispatches custom events so the unified tracker / behavioral
  // engine can capture chat interactions as IDS signals.

  function trackChatEvent(eventName, meta) {
    log('Chat event:', eventName, meta);

    // 1. Dispatch custom DOM event (picked up by behavioral engine)
    var evt = new CustomEvent('albeni:chat', {
      detail: { event: eventName, session_id: SESSION_ID, language: LANG, meta: meta || {} }
    });
    document.dispatchEvent(evt);

    // 2. Also send directly to /v1/track/event if tracker sendSignal is available
    if (window.ALBENI_AI && typeof window.ALBENI_AI._sendSignal === 'function') {
      window.ALBENI_AI._sendSignal('chat_interaction', {
        chat_event: eventName,
        chat_session_id: SESSION_ID,
        language: LANG,
        topic: (meta || {}).topic || null,
        escalated: (meta || {}).escalated || false
      });
    }
  }

  // ── BIND EVENTS (after DOM ready) ─────────────────────
  function bind() {
    $('ab-toggle').addEventListener('click', onToggle);
    $('ab-lang').addEventListener('change', onLangChange);
    $('ab-in').addEventListener('input', onInputChange);
    $('ab-in').addEventListener('keydown', onKeydown);
    $('ab-sb').addEventListener('click', function () { send(); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }

})();
