/**
 * Albeni Email Bridge -- collega le lead dei form al profilo comportamentale.
 *
 * IL PROBLEMA CHE RISOLVE
 * albeni-behavioral-engine.js chiama /v1/crm/sync-lead quando IDS >= 65 e legge
 * l'email da localStorage `albeni_visitor_email` (_getStoredEmail, riga 586).
 * La cattura esiste gia' (initEmailCapture, riga 699) ma e' agganciata
 * all'evento `submit`. I form dei lead magnet su WoM/MU non emettono submit:
 * sono <input> + <button> con un listener 'click' che chiama fetch() verso le
 * Client API di Klaviyo -- non c'e' proprio un elemento <form> in pagina.
 * Quindi il listener non scatta mai, l'email resta ignota, il sync parte con
 * email=null e le proprieta' comportamentali (cluster_tag, intent_stage,
 * ids_score) non atterrano su nessun profilo lead.
 *
 * COSA FA
 * Sposta l'aggancio dove il dato passa davvero: intercetta le POST verso
 * a.klaviyo.com/client/subscriptions|events, estrae l'email dal payload e la
 * memorizza in `albeni_visitor_email`. Se il motore comportamentale e' gia' in
 * pagina, ri-arma il sync cosi' che il profilo venga arricchito subito invece
 * che alla visita successiva.
 *
 * CONSENSO (non negoziabile)
 * `albeni_visitor_email` e' un identificatore di profilazione: EDPB 2/2023
 * estende l'art. 5(3) ePrivacy a localStorage. Quindi si scrive SOLO con
 * consenso "statistics" (categoria "Esperienza e misurazione" di Complianz).
 * Senza consenso il form funziona identico e la lead entra in Klaviyo: cambia
 * solo che resta senza arricchimento comportamentale. E' il comportamento
 * corretto, non un degrado da compensare.
 *
 * RE-SYNC DIFFERITO (2026-07-29)
 * L'ordine naturale e' form prima, banner dopo: chi compila e poi accetta
 * perdeva l'arricchimento per sempre, perche' al momento della cattura non
 * c'era consenso e un istante dopo non c'era piu' l'email. Ora l'email attesa
 * resta in una variabile di modulo -- memoria di pagina, non storage, quindi
 * fuori dall'art. 5(3) -- e viene scaricata su localStorage nel momento esatto
 * in cui il consenso statistics arriva. Se il consenso non arriva prima che la
 * pagina muoia, l'email si perde: e' il limite voluto, non un difetto.
 * Non copre il consenso dato in una sessione successiva, e non deve: a quel
 * punto sul dispositivo non esiste piu' nulla che leghi quel visitatore a
 * quell'email.
 *
 * DEPLOY -- WPCode, "Esegui ovunque", footer, su WoM e MU.
 * Snippet normale (NON text/plain): deve girare anche senza consenso, perche'
 * e' lui a controllare il consenso prima di scrivere.
 */
(function () {
  'use strict';

  var KEY = 'albeni_visitor_email';

  // Email catturata prima del consenso. Vive in una variabile che muore con la
  // pagina: non e' informazione archiviata sul terminale, quindi resta fuori
  // dall'art. 5(3) ePrivacy e non richiede consenso per esistere. Serve a
  // coprire l'ordine naturale degli eventi -- prima si compila il form, poi si
  // guarda il banner -- che altrimenti perde l'arricchimento per sempre.
  var pendingEmail = null;
  var consentWatch = null;

  // Complianz espone cmplz_has_consent lato client; se il CMP non e' ancora
  // caricato assumiamo NO consenso (fail-closed).
  function hasStatisticsConsent() {
    try {
      if (typeof window.cmplz_has_consent === 'function') {
        return window.cmplz_has_consent('statistics') === true;
      }
    } catch (e) { /* fail-closed */ }
    return false;
  }

  function persistEmail(email) {
    try {
      if (localStorage.getItem(KEY) === email) return;
      localStorage.setItem(KEY, email);
      // Il motore marca il sync come gia' fatto una volta per visitatore:
      // lo sblocchiamo cosi' che riparta ora che l'email e' nota.
      localStorage.removeItem('albeni_klaviyo_synced');
      window.dispatchEvent(new CustomEvent('albeni:email_captured', { detail: { email: email } }));
    } catch (e) { /* storage pieno o negato: non bloccare il form */ }
  }

  function stopConsentWatch() {
    if (consentWatch) { clearInterval(consentWatch); consentWatch = null; }
  }

  // Ritorna true solo se ha davvero scaricato l'email in attesa.
  function flushPendingEmail() {
    if (!pendingEmail || !hasStatisticsConsent()) return false;
    var email = pendingEmail;
    pendingEmail = null;
    stopConsentWatch();
    persistEmail(email);
    return true;
  }

  // Complianz cambia nome all'evento di consenso fra le versioni: invece di
  // scommettere su quale sia, si ascoltano quelli noti e si tiene un polling
  // breve come rete di sicurezza. Si spegne da solo dopo 2 minuti -- oltre quel
  // punto il banner non e' stato toccato e non c'e' niente da recuperare.
  function watchForConsent() {
    if (consentWatch) return;
    var attempts = 0;
    consentWatch = setInterval(function () {
      attempts++;
      if (flushPendingEmail() || attempts > 60) stopConsentWatch();
    }, 2000);
  }

  ['cmplz_status_change', 'cmplz_enable_category', 'cmplz_fire_categories'].forEach(function (evt) {
    document.addEventListener(evt, function () { flushPendingEmail(); });
  });

  function storeEmail(email) {
    if (!email || email.indexOf('@') < 0) return;
    if (hasStatisticsConsent()) { persistEmail(email); return; }
    // Niente consenso: non si scrive nulla sul dispositivo, si tiene l'email in
    // memoria e si aspetta. Se il consenso non arriva entro la vita della
    // pagina, l'email si perde -- ed e' il comportamento corretto, non un
    // degrado da compensare.
    pendingEmail = email;
    watchForConsent();
  }

  // Estrae l'email dai due payload che i form usano davvero:
  // /client/subscriptions/ -> data.attributes.profile.data.attributes.email
  // /client/events/        -> data.attributes.profile.data.attributes.email
  function extractEmail(body) {
    try {
      var p = typeof body === 'string' ? JSON.parse(body) : body;
      return (p && p.data && p.data.attributes && p.data.attributes.profile &&
              p.data.attributes.profile.data && p.data.attributes.profile.data.attributes &&
              p.data.attributes.profile.data.attributes.email) || null;
    } catch (e) { return null; }
  }

  var origFetch = window.fetch;
  if (typeof origFetch !== 'function') return;

  window.fetch = function (input, init) {
    try {
      var url = typeof input === 'string' ? input : (input && input.url) || '';
      if (url.indexOf('a.klaviyo.com/client/') >= 0 && init && init.body) {
        storeEmail(extractEmail(init.body));
      }
    } catch (e) { /* mai rompere il form */ }
    return origFetch.apply(this, arguments);
  };

  // Fallback per form nativi con submit (Klaviyo embed classico). Ridondante
  // con initEmailCapture del motore quando questo e' caricato; serve solo se in
  // futuro un form torna a fare submit e il motore non e' in pagina.
  document.addEventListener('submit', function (ev) {
    try {
      var f = ev.target;
      if (!f || !f.querySelector) return;
      var input = f.querySelector('input[type="email"]');
      if (input && input.value) storeEmail(input.value.trim().toLowerCase());
    } catch (e) { /* noop */ }
  }, true);
})();
