'use strict';

const crypto = require('crypto');

/**
 * Confronto a tempo costante che non trapela la lunghezza del segreto.
 * timingSafeEqual pretende buffer di pari lunghezza, quindi si confrontano
 * gli hash e non i valori.
 */
function safeEqual(a, b) {
    if (typeof a !== 'string' || typeof b !== 'string') return false;
    const ha = crypto.createHash('sha256').update(a).digest();
    const hb = crypto.createHash('sha256').update(b).digest();
    return crypto.timingSafeEqual(ha, hb);
}

/**
 * Verifica la chiave di una richiesta contro API_KEY e, se presente,
 * API_KEY_PREVIOUS.
 *
 * API_KEY_PREVIOUS esiste solo per le rotazioni: i detentori della chiave sono
 * sei (due servizi Railway, il wp-config.php di tre domini e lo script GSC in
 * locale) e non si aggiornano nello stesso istante. Tenendo valida la vecchia
 * per la durata del giro, non c'e' la finestra in cui meta' sistema prende 401.
 * Va rimossa appena tutti i detentori sono passati alla nuova.
 *
 * Nessun default hardcoded: se API_KEY non e' configurata non passa nessuno.
 */
function isValidApiKey(provided) {
    const current = process.env.API_KEY;
    const previous = process.env.API_KEY_PREVIOUS;
    if (!current && !previous) return false;
    const value = String(provided || '');
    if (!value) return false;
    if (current && safeEqual(value, current)) return true;
    if (previous && safeEqual(value, previous)) return true;
    return false;
}

/** Estrae la chiave da header o query string e la valida. */
function requestHasValidApiKey(req) {
    return isValidApiKey(req.headers['x-api-key'] || req.query.api_key);
}

module.exports = { safeEqual, isValidApiKey, requestHasValidApiKey };
