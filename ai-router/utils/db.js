'use strict';

/**
 * Pool Postgres per ai-router.
 *
 * Fino al 2026-07-28 ai-router non parlava con il database: l'unico stato che
 * scriveva — le transizioni paid→organic dell'ADV allocator — finiva in un file
 * dentro il container. Su Railway il filesystem del container e' effimero, e
 * ogni deploy lo azzerava. E' lo stesso motivo per cui i dati GSC erano stati
 * spostati su Postgres il 2026-05-14.
 *
 * Il pool e' volutamente piccolo: ai-router usa il DB solo per le transizioni,
 * poche righe lette e riscritte di rado. Il 28/07 ml-worker ha esaurito il
 * proprio pool e ha portato giu' tutto cio' che passa dal database — non e' il
 * caso di aggiungere pressione su max_connections per un uso cosi' marginale.
 */

const { Pool } = require('pg');

let pool = null;

function getPool() {
    if (pool) return pool;

    const connectionString = process.env.DATABASE_URL;
    if (!connectionString) {
        // Meglio un errore esplicito che un fallback silenzioso su filesystem:
        // il fallback e' esattamente il guasto che stiamo togliendo di mezzo.
        throw new Error(
            'DATABASE_URL non configurata su questo servizio: le transizioni ADV ' +
            'non possono essere persistite. Impostarla su Railway come riferimento ' +
            'al servizio Postgres (${{Postgres.DATABASE_URL}}).'
        );
    }

    // La rete interna di Railway non fa TLS: postgres.railway.internal va in
    // chiaro. Serve SSL solo se qualcuno punta all'host pubblico.
    const isInternal = /\.railway\.internal(:|\/|$)/.test(connectionString);

    pool = new Pool({
        connectionString,
        ssl: isInternal ? false : { rejectUnauthorized: false },
        max: 3,
        idleTimeoutMillis: 30000,
        connectionTimeoutMillis: 8000,
    });

    pool.on('error', (err) => {
        console.error('[db] errore sul pool Postgres:', err.message);
    });

    return pool;
}

module.exports = { getPool };
