<?php
/**
 * CRO Conversion Proxy — Albeni 1905 AI Stack
 * Step 7.3 (2026-05-14).
 *
 * Perché esiste:
 *   - Il widget JS pubblico NON può conoscere API_KEY del ml-worker
 *     (esposta nel browser → chiunque potrebbe scrivere conversion fake)
 *   - Quindi WordPress espone un endpoint proxy /wp-json/albeni/v1/cro-conversion
 *     che riceve la conversion dal widget e la inoltra al ml-worker firmandola
 *     server-side con l'API_KEY salvata negli env del server WP.
 *
 * Setup WPCode:
 *   - Code Type: PHP Snippet
 *   - Location: Run Everywhere
 *   - Auto Insert: enabled
 *   - Title suggerito: "Albeni CRO Conversion Proxy"
 *   - Copia tutto il contenuto sotto l'<?php
 *
 * Env required (in wp-config.php oppure WPCode > Settings > Constants):
 *   define('ALBENI_API_KEY', 'albeni1905-internal-api-v1');
 *   define('ALBENI_ML_WORKER_URL', 'https://albeni-ai-orchestration-production.up.railway.app');
 *
 * Rate limiting basico: 1 conversion / 5 secondi per IP (per evitare abuso).
 */

add_action('rest_api_init', function () {
    register_rest_route('albeni/v1', '/cro-conversion', [
        'methods'  => 'POST',
        'callback' => 'albeni_cro_conversion_proxy',
        'permission_callback' => '__return_true',  // public — auth via firma server-side
    ]);
});

function albeni_cro_conversion_proxy(WP_REST_Request $request) {
    // Basic rate limit: 1 req / 5s per IP (transient-based, sopravvive a OPcache)
    $ip = $_SERVER['HTTP_CF_CONNECTING_IP'] ?? $_SERVER['REMOTE_ADDR'] ?? 'unknown';
    $rl_key = 'albeni_cro_rl_' . md5($ip);
    if (get_transient($rl_key)) {
        return new WP_REST_Response(['status' => 'rate_limited'], 429);
    }
    set_transient($rl_key, 1, 5);

    $body = $request->get_json_params();
    $exposure_id = intval($body['exposure_id'] ?? 0);
    $conversion_type = sanitize_text_field($body['conversion_type'] ?? 'click');
    $value_eur = isset($body['value_eur']) ? floatval($body['value_eur']) : null;

    if ($exposure_id <= 0) {
        return new WP_REST_Response(['status' => 'error', 'message' => 'missing exposure_id'], 400);
    }

    $api_key = defined('ALBENI_API_KEY') ? ALBENI_API_KEY : getenv('ALBENI_API_KEY');
    $ml_worker_url = defined('ALBENI_ML_WORKER_URL')
        ? ALBENI_ML_WORKER_URL
        : (getenv('ALBENI_ML_WORKER_URL') ?: 'https://albeni-ai-orchestration-production.up.railway.app');

    if (!$api_key) {
        return new WP_REST_Response(['status' => 'error', 'message' => 'server misconfigured'], 500);
    }

    $payload = [
        'exposure_id' => $exposure_id,
        'conversion_type' => $conversion_type,
    ];
    if ($value_eur !== null) $payload['value_eur'] = $value_eur;

    $response = wp_remote_post($ml_worker_url . '/v1/cro/conversion', [
        'timeout' => 10,
        'headers' => [
            'Content-Type' => 'application/json',
            'x-api-key' => $api_key,
        ],
        'body' => wp_json_encode($payload),
    ]);

    if (is_wp_error($response)) {
        return new WP_REST_Response(['status' => 'error', 'message' => $response->get_error_message()], 502);
    }

    $code = wp_remote_retrieve_response_code($response);
    $body_raw = wp_remote_retrieve_body($response);
    $body_json = json_decode($body_raw, true) ?: [];

    return new WP_REST_Response($body_json, $code);
}
