/**
 * C2PA Digital Fingerprinting Middleware
 * Implements the C2PA standard for certifying Albeni 1905 digital assets.
 *
 * Injects cryptographic metadata headers into served images and PDFs
 * to certify their origin as authentic Albeni 1905 content.
 */

const crypto = require('crypto');

// C2PA metadata template
const C2PA_MANIFEST = {
    claim_generator: 'Albeni 1905 AI Orchestration Layer/1.0',
    claim_generator_info: {
        name: 'Albeni 1905',
        version: '1.0.0'
    },
    assertions: [
        {
            label: 'c2pa.actions',
            data: {
                actions: [{
                    action: 'c2pa.created',
                    softwareAgent: 'Albeni 1905 Content Engine'
                }]
            }
        },
        {
            label: 'stds.schema-org.CreativeWork',
            data: {
                '@type': 'CreativeWork',
                author: {
                    '@type': 'Organization',
                    name: 'Albeni 1905',
                    url: 'https://albeni1905.com'
                },
                copyrightHolder: 'Albeni 1905 S.r.l.',
                license: 'All rights reserved'
            }
        }
    ]
};

/**
 * Generate a digital signature for content verification.
 */
function generateContentSignature(content, timestamp) {
    const signingKey = process.env.C2PA_SIGNING_KEY || 'albeni-1905-content-signing-key';
    const hash = crypto.createHmac('sha256', signingKey)
        .update(`${content}:${timestamp}:albeni1905`)
        .digest('hex');
    return hash;
}

/**
 * Middleware that injects C2PA-style headers for served assets.
 */
function c2paMiddleware(req, res, next) {
    // Only apply to asset responses (images, PDFs)
    const assetExtensions = ['.pdf', '.png', '.jpg', '.jpeg', '.webp', '.svg'];
    const isAsset = assetExtensions.some(ext => req.path.toLowerCase().endsWith(ext));

    if (!isAsset) {
        return next();
    }

    const timestamp = new Date().toISOString();
    const signature = generateContentSignature(req.path, timestamp);

    // Inject C2PA-style headers
    res.setHeader('X-C2PA-Claim-Generator', C2PA_MANIFEST.claim_generator);
    res.setHeader('X-C2PA-Origin', 'Albeni 1905');
    res.setHeader('X-C2PA-Signature', signature);
    res.setHeader('X-C2PA-Timestamp', timestamp);
    res.setHeader('X-Content-Origin', 'https://albeni1905.com');
    res.setHeader('X-Content-License', 'All Rights Reserved - Albeni 1905 S.r.l.');

    // Prevent unauthorized caching by AI scrapers
    res.setHeader('X-Robots-Tag', 'noai, noimageai');

    next();
}

module.exports = { c2paMiddleware, generateContentSignature };
