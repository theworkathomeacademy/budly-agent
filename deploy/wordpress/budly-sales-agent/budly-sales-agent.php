<?php
/**
 * Plugin Name: Budly Sales Agent
 * Description: Zero-cost guided sales assistant for Wake'n'Bake Lounge and CCCultivate.
 * Version: 1.6.0
 * Author: Compassionate Care Cultivators
 * Requires at least: 6.2
 * Requires PHP: 7.4
 * Text Domain: budly-sales
 */

if (!defined('ABSPATH')) { exit; }

define('BUDLY_SALES_VERSION', '1.6.0');
define('BUDLY_SALES_DIR', plugin_dir_path(__FILE__));
define('BUDLY_SALES_URL', plugin_dir_url(__FILE__));
require_once BUDLY_SALES_DIR . 'includes/tracking.php';
require_once BUDLY_SALES_DIR . 'includes/SecureMemory/Bootstrap.php';
\Budly\SecureMemory\Bootstrap::register();

function budly_sales_activate() {
    \Budly\SecureMemory\Bootstrap::activate();
    budly_sales_install_tracking_tables();
    $pages = array(
        'chat' => array('Ask Budly', '[budly_sales_agent]'),
        'policies' => array('Customer Policies', '[budly_sales_policies]'),
    );
    foreach ($pages as $key => $page) {
        $existing = get_page_by_path(sanitize_title($page[0]));
        if ($existing) {
            update_option('budly_sales_' . $key . '_page_id', $existing->ID);
            continue;
        }
        $page_id = wp_insert_post(array(
            'post_title' => $page[0],
            'post_content' => $page[1],
            'post_status' => 'publish',
            'post_type' => 'page',
        ));
        if (!is_wp_error($page_id)) {
            update_option('budly_sales_' . $key . '_page_id', $page_id);
        }
    }
    flush_rewrite_rules();
}
register_activation_hook(__FILE__, 'budly_sales_activate');
register_deactivation_hook(__FILE__, array('Budly\\SecureMemory\\Bootstrap', 'deactivate'));

/**
 * Repair the dedicated Ask Budly page once per application version.
 *
 * The historical production package included this recovery for installations
 * whose theme template rendered an empty page. It is deliberately limited to
 * the plugin-owned page and does not alter any other content.
 */
function budly_sales_repair_chat_page() {
    if (get_option('budly_sales_repaired_version') === BUDLY_SALES_VERSION) {
        return;
    }
    $page_id = (int) get_option('budly_sales_chat_page_id');
    $page = $page_id ? get_post($page_id) : get_page_by_path('ask-budly');
    if ($page instanceof WP_Post) {
        update_option('budly_sales_chat_page_id', $page->ID);
        update_post_meta($page->ID, '_wp_page_template', 'default');
        $content = trim((string) $page->post_content);
        if ($content === '' || strpos($content, '[budly_sales_agent]') === false) {
            wp_update_post(array('ID' => $page->ID, 'post_content' => '[budly_sales_agent]'));
        }
    }
    update_option('budly_sales_repaired_version', BUDLY_SALES_VERSION, false);
}
add_action('admin_init', 'budly_sales_repair_chat_page');

function budly_sales_dedicated_page_template($template) {
    if (is_admin()) {
        return $template;
    }
    $page_id = (int) get_option('budly_sales_chat_page_id');
    if (($page_id && is_page($page_id)) || is_page('ask-budly')) {
        $plugin_template = BUDLY_SALES_DIR . 'templates/ask-budly-page.php';
        if (is_readable($plugin_template)) {
            return $plugin_template;
        }
    }
    return $template;
}
add_filter('template_include', 'budly_sales_dedicated_page_template', 99);

function budly_sales_enqueue() {
    wp_enqueue_style('budly-sales', BUDLY_SALES_URL . 'assets/budly-sales.css', array(), BUDLY_SALES_VERSION);
    wp_enqueue_script('budly-secure-memory', BUDLY_SALES_URL . 'assets/budly-secure-memory.js', array(), BUDLY_SALES_VERSION, true);
    wp_enqueue_script('budly-sales', BUDLY_SALES_URL . 'assets/budly-sales.js', array('budly-secure-memory'), BUDLY_SALES_VERSION, true);
    wp_localize_script('budly-secure-memory', 'BudlyMemoryConfig', array(
        'restBase' => esc_url_raw(rest_url('budly-identity/v1')),
        'agentId' => 'sales-agent',
        'consentVersion' => '1.0',
    ));
    $policy_page = get_permalink((int) get_option('budly_sales_policies_page_id'));
    wp_localize_script('budly-sales', 'BudlySalesConfig', array(
        'ajaxUrl' => admin_url('admin-ajax.php'),
        'nonce' => wp_create_nonce('budly_sales_handoff'),
        'supportEmail' => 'budlysupport@gmail.com',
        'shopUrl' => home_url('/shop/'),
        'storeApiUrl' => home_url('/wp-json/wc/store/v1/products?per_page=100'),
        'decisionUrl' => esc_url_raw(rest_url('budly-identity/v1/decisions/evaluate')),
        'decisionNonce' => wp_create_nonce('wp_rest'),
        'policiesUrl' => $policy_page ? $policy_page : home_url('/customer-policies/'),
        'trackNonce' => wp_create_nonce('budly_sales_track'),
    ));
}

function budly_sales_global_style() {
    wp_enqueue_style('budly-sales', BUDLY_SALES_URL . 'assets/budly-sales.css', array(), BUDLY_SALES_VERSION);
    wp_enqueue_script('budly-sales-entry', BUDLY_SALES_URL . 'assets/budly-entry.js', array(), BUDLY_SALES_VERSION, true);
    wp_localize_script('budly-sales-entry', 'BudlyEntryConfig', array(
        'ajaxUrl' => admin_url('admin-ajax.php'),
        'nonce' => wp_create_nonce('budly_sales_track'),
    ));
}
add_action('wp_enqueue_scripts', 'budly_sales_global_style');

function budly_sales_floating_button() {
    if (is_admin() || is_page('ask-budly')) {
        return;
    }
    ?>
    <a class="budly-floating-button" data-budly-entry href="<?php echo esc_url(home_url('/ask-budly/')); ?>" aria-label="Ask Budly for shopping help">
      <span class="budly-floating-avatar" aria-hidden="true">B</span>
      <span><strong>Ask Budly</strong><small>Get shopping help</small></span>
    </a>
    <?php
}
add_action('wp_footer', 'budly_sales_floating_button');

function budly_sales_shortcode() {
    budly_sales_enqueue();
    $policy_page = get_permalink((int) get_option('budly_sales_policies_page_id'));
    ob_start(); ?>
    <div class="budly-experience" data-budly-sales>
      <header class="budly-hero-heading">
        <div class="budly-title-ornament" aria-hidden="true"><span></span><b>◆</b><span></span></div>
        <div class="budly-title-row"><i></i><h1>ASK BUDLY</h1><i></i></div>
        <p>Your Virtual Guide to Cannabis, CBD &amp; Culinary Wellness</p>
        <div class="budly-tagline-row"><i></i><h2>A Calmer Way To Find Your Fit</h2><i></i></div>
      </header>
      <div class="budly-main-grid">
        <aside class="budly-mascot-column" aria-label="Budly, your virtual guide">
          <div class="budly-mascot-stage"><img src="<?php echo esc_url(BUDLY_SALES_URL . 'assets/budly-cutout-v134.png'); ?>" alt="Budly holding a magnifying glass and book"></div>
          <div class="budly-guide-card"><span class="budly-guide-icon" aria-hidden="true">♢</span><div><strong>Always Here For You</strong><p>Budly is your no-pressure guide to better choices, real education, and products you can trust.</p><b>We’re here when you’re ready.</b></div></div>
        </aside>
        <section class="budly-interaction-panel">
          <div class="budly-welcome-card"><img src="<?php echo esc_url(BUDLY_SALES_URL . 'assets/budly-avatar.png'); ?>" alt="" aria-hidden="true"><div><h3>Hi, I’m Budly! 👋</h3><p>I’m here to help you understand your options before choosing a product, course, membership, or support path.</p><p><strong>What would you like help with today?</strong></p></div></div>
          <div class="budly-hero-starters" aria-label="Popular ways Budly can help">
            <button type="button" data-budly-hero-starter="Help me choose the right product">🌿 <span>Help me choose a product</span></button>
            <button type="button" data-budly-hero-starter="Help me shop within my budget">$ <span>I have a budget in mind</span></button>
            <button type="button" data-budly-hero-starter="Help me compare products">⚖ <span>Compare products</span></button>
            <button type="button" data-budly-hero-starter="I have questions about NFT membership terms and refunds">♛ <span>Learn about memberships</span></button>
            <button type="button" data-budly-hero-starter="I have a wholesale inquiry">▥ <span>Wholesale or bulk orders</span></button>
            <button type="button" data-budly-hero-starter="I need order, shipping, or human support">🚚 <span>Order, shipping, or support</span></button>
          </div>
          <section class="budly-chat" aria-label="Chat with Budly">
            <header class="budly-chat-status"><span class="budly-avatar">B</span><span><strong>Budly Sales</strong><small>● Ready to help</small></span><button type="button" data-budly-restart hidden>Start over</button></header>
            <div class="budly-messages" data-budly-messages aria-live="polite"></div>
            <form class="budly-composer" data-budly-form><div data-budly-fields></div><button type="submit" data-budly-send>Continue</button></form>
            <p class="budly-fine">For adults. Product information only—not medical or legal advice. <a href="<?php echo esc_url($policy_page ? $policy_page : home_url('/customer-policies/')); ?>">Customer policies</a></p>
          </section>
        </section>
      </div>
      <div class="budly-trust-row" aria-label="Budly commitments"><span>🔒 Your information is handled according to your explicit privacy choices.</span><strong>● No Pressure</strong><strong>● Just Guidance</strong><strong>● Customer Controlled</strong></div>
    </div>
    <?php return ob_get_clean();
}
add_shortcode('budly_sales_agent', 'budly_sales_shortcode');

function budly_sales_policies_shortcode() {
    ob_start(); ?>
    <div class="budly-policies">
      <p><strong>Last approved:</strong> July 17, 2026</p>
      <h2>CBD, body-care, and cooking products</h2><p>These consumable and personal-care products are final sale. Damaged and incorrect orders are handled under the exception below.</p>
      <h2>Damaged or incorrect orders</h2><p>Email <a href="mailto:budlysupport@gmail.com">budlysupport@gmail.com</a> within 7 days of delivery. Include your order number and photos of the item and packaging. Replacement and refund requests are reviewed individually.</p>
      <h2>Physical books</h2><p>Physical books may be returned within 14 days if unused and in their original condition. Customers pay return shipping unless the order was damaged or incorrect.</p>
      <h2>Digital products</h2><p>Digital products and downloaded books are final sale after delivery or download.</p>
      <h2>Courses</h2><p>A refund may be requested before course access is delivered. Courses are final sale after access, materials, or participation begins.</p>
      <h2>Subscriptions</h2><p>Subscriptions renew monthly until canceled. Cancel through your customer account profile before the next renewal. If profile cancellation is unavailable or unsuccessful, email support. Orders already processed are not automatically refundable.</p>
      <h2>Shipping</h2><p>Rates and available destinations appear at checkout. Delivery dates are estimates and are not guaranteed. Orders that cannot be fulfilled to the selected destination will be refunded.</p>
      <h2>NFT memberships</h2><p>Membership begins when the transaction finishes processing. You may cancel within 7 days for a full refund if the membership has not been used. Using a membership discount counts as use and disqualifies the purchase from a refund. No financial return, resale value, or appreciation is promised.</p>
      <h2>Wholesale</h2><p>Website-supported prices, minimums, shipping, labeling, and commercial terms may be completed online. Requests outside the website’s available options may require support assistance.</p>
      <h2>Support</h2><p>Email <a href="mailto:budlysupport@gmail.com">budlysupport@gmail.com</a>. We normally respond within 3 business days.</p>
    </div>
    <?php return ob_get_clean();
}
add_shortcode('budly_sales_policies', 'budly_sales_policies_shortcode');

function budly_sales_handoff() {
    check_ajax_referer('budly_sales_handoff', 'nonce');
    $ip_key = 'budly_rate_' . md5(isset($_SERVER['REMOTE_ADDR']) ? sanitize_text_field(wp_unslash($_SERVER['REMOTE_ADDR'])) : 'unknown');
    $attempts = (int) get_transient($ip_key);
    if ($attempts >= 5) {
        wp_send_json_error(array('message' => 'Please email budlysupport@gmail.com for assistance.'), 429);
    }
    set_transient($ip_key, $attempts + 1, HOUR_IN_SECONDS);
    $name = sanitize_text_field(isset($_POST['name']) ? wp_unslash($_POST['name']) : '');
    $email = sanitize_email(isset($_POST['email']) ? wp_unslash($_POST['email']) : '');
    $journey = sanitize_text_field(isset($_POST['journey']) ? wp_unslash($_POST['journey']) : '');
    $summary = sanitize_textarea_field(isset($_POST['summary']) ? wp_unslash($_POST['summary']) : '');
    if (!$name || !is_email($email) || !$summary) {
        wp_send_json_error(array('message' => 'Please provide a valid name, email, and request.'), 400);
    }
    $reference = strtoupper(wp_generate_password(8, false, false));
    $subject = 'Budly sales handoff ' . $reference . ' — ' . $journey;
    $body = "Reference: {$reference}\nName: {$name}\nEmail: {$email}\nJourney: {$journey}\n\nCustomer request:\n{$summary}";
    $headers = array('Reply-To: ' . $name . ' <' . $email . '>');
    $sent = wp_mail('budlysupport@gmail.com', $subject, $body, $headers);
    wp_send_json_success(array(
        'reference' => $reference,
        'sent' => (bool) $sent,
        'message' => $sent ? 'Your request was sent to Budly Support.' : 'Your reference was created. Please email Budly Support directly.',
    ));
}
add_action('wp_ajax_budly_sales_handoff', 'budly_sales_handoff');
add_action('wp_ajax_nopriv_budly_sales_handoff', 'budly_sales_handoff');
