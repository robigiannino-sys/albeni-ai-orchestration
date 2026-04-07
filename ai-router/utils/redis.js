/**
 * Redis Client Utility
 * Ultra-fast caching layer for IDS scores and routing decisions (<120ms)
 */

const Redis = require('ioredis');
const dotenv = require('dotenv');
dotenv.config();

let client = null;

function getClient() {
    if (!client) {
        client = new Redis(process.env.REDIS_URL || 'redis://redis:6379', {
            retryStrategy(times) {
                const delay = Math.min(times * 50, 2000);
                return delay;
            },
            maxRetriesPerRequest: 3,
            lazyConnect: false,
            enableReadyCheck: true
        });

        client.on('connect', () => {
            console.log('Redis connected');
        });

        client.on('error', (err) => {
            console.error('Redis error:', err.message);
        });
    }
    return client;
}

module.exports = { getClient };
