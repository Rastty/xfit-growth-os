<?php
/**
 * Plugin Name: XFIT Verified Affiliate Click Analytics
 * Description: Consent-gated first-party product CTA event instrumentation for two XFIT advisors.
 * Version: 0.1.2
 * Requires at least: 6.0
 * Requires PHP: 7.4
 * Author: XFIT.cz
 * License: GPL-2.0-or-later
 * Text Domain: xfit-affiliate-analytics
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

// This plugin MUST NOT set up GA4 itself or create a consent banner. It
// relies on the site's existing Google Tag and WebToffee 3.x CMP.
// Missing or denied analytics consent means ZERO custom event dispatch.
function xfit_enqueue_verified_affiliate_analytics() {
    if ( ! is_singular( 'post' ) ) {
        return;
    }

    $post = get_post();
    if ( ! ( $post instanceof WP_Post ) ) {
        return;
    }

    $approved_slugs = array(
        'xfit-os-kreatin-poradce',
        'xfit-os-syrovatkovy-protein-porovnani',
    );
    if ( ! in_array( $post->post_name, $approved_slugs, true ) ) {
        return;
    }

    $version = '0.1.2';
    wp_enqueue_script(
        'xfit-webtoffee-analytics-consent',
        plugins_url( 'assets/xfit-webtoffee-bridge.js', __FILE__ ),
        array(),
        $version,
        true
    );

    wp_enqueue_script(
        'xfit-verified-affiliate-outbound',
        plugins_url( 'assets/xfit-outbound.js', __FILE__ ),
        array( 'xfit-webtoffee-analytics-consent' ),
        $version,
        true
    );
}
add_action( 'wp_enqueue_scripts', 'xfit_enqueue_verified_affiliate_analytics', 30 );
