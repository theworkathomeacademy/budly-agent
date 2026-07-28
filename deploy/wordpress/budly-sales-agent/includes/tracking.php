<?php
if (!defined('ABSPATH')) { exit; }

function budly_sales_tracking_tables() {
    global $wpdb;
    return array(
        'events' => $wpdb->prefix . 'budly_sales_events',
        'customers' => $wpdb->prefix . 'budly_sales_customers',
        'conversations' => $wpdb->prefix . 'budly_sales_conversations',
    );
}

function budly_sales_install_tracking_tables() {
    global $wpdb;
    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    $tables = budly_sales_tracking_tables();
    $charset = $wpdb->get_charset_collate();
    dbDelta("CREATE TABLE {$tables['events']} (
        id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
        created_at datetime NOT NULL,
        event_name varchar(50) NOT NULL,
        session_id varchar(64) NOT NULL,
        journey varchar(80) NOT NULL DEFAULT '',
        product_url text NULL,
        email_hash char(64) NOT NULL DEFAULT '',
        phone_hash char(64) NOT NULL DEFAULT '',
        metadata text NULL,
        PRIMARY KEY (id),
        KEY event_name (event_name),
        KEY created_at (created_at),
        KEY session_id (session_id)
    ) $charset;");
    dbDelta("CREATE TABLE {$tables['customers']} (
        id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
        created_at datetime NOT NULL,
        updated_at datetime NOT NULL,
        name varchar(120) NOT NULL DEFAULT '',
        email varchar(190) NOT NULL,
        phone varchar(40) NOT NULL DEFAULT '',
        email_hash char(64) NOT NULL,
        phone_hash char(64) NOT NULL DEFAULT '',
        memory_consent tinyint(1) NOT NULL DEFAULT 0,
        PRIMARY KEY (id),
        UNIQUE KEY email_hash (email_hash)
    ) $charset;");
    dbDelta("CREATE TABLE {$tables['conversations']} (
        id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
        created_at datetime NOT NULL,
        customer_id bigint(20) unsigned NOT NULL,
        session_id varchar(64) NOT NULL,
        journey varchar(80) NOT NULL DEFAULT '',
        summary text NOT NULL,
        PRIMARY KEY (id),
        KEY customer_id (customer_id),
        KEY session_id (session_id)
    ) $charset;");
    update_option('budly_sales_tracking_db_version', '1.0');
}

function budly_sales_maybe_upgrade_tracking() {
    if (get_option('budly_sales_tracking_db_version') !== '1.0') {
        budly_sales_install_tracking_tables();
    }
}
add_action('plugins_loaded', 'budly_sales_maybe_upgrade_tracking');

function budly_sales_normalize_phone($phone) {
    return preg_replace('/[^0-9+]/', '', (string) $phone);
}

function budly_sales_identity_hash($value) {
    return $value ? hash_hmac('sha256', strtolower(trim($value)), wp_salt('auth')) : '';
}

function budly_sales_recall_rate_limit($scope, $limit, $window) {
    $ip = isset($_SERVER['REMOTE_ADDR']) ? sanitize_text_field(wp_unslash($_SERVER['REMOTE_ADDR'])) : 'unknown';
    $key = 'budly_recall_rate_' . md5($scope . '|' . $ip);
    $attempts = (int) get_transient($key);
    if ($attempts >= $limit) { return false; }
    set_transient($key, $attempts + 1, $window);
    return true;
}

function budly_sales_request_recall_code() {
    check_ajax_referer('budly_sales_recall', 'nonce');
    if (!budly_sales_recall_rate_limit('request', 5, 15 * MINUTE_IN_SECONDS)) {
        wp_send_json_error(array('message' => 'Too many attempts. Please wait 15 minutes and try again.'), 429);
    }
    $email = sanitize_email(isset($_POST['email']) ? wp_unslash($_POST['email']) : '');
    if (!is_email($email)) {
        wp_send_json_error(array('message' => 'Please enter a valid email address.'), 400);
    }
    global $wpdb;
    $tables = budly_sales_tracking_tables();
    $email_hash = budly_sales_identity_hash($email);
    $customer_id = (int) $wpdb->get_var($wpdb->prepare(
        "SELECT id FROM {$tables['customers']} WHERE email_hash = %s AND memory_consent = 1",
        $email_hash
    ));
    if ($customer_id) {
        $code = (string) wp_rand(100000, 999999);
        set_transient('budly_recall_code_' . $email_hash, array(
            'hash' => wp_hash_password($code),
            'customer_id' => $customer_id,
            'attempts' => 0,
        ), 10 * MINUTE_IN_SECONDS);
        wp_mail(
            $email,
            'Your Budly verification code',
            "Your Budly verification code is {$code}. It expires in 10 minutes.\n\nIf you did not request this code, you can ignore this email.",
            array('Reply-To: Budly Support <budlysupport@gmail.com>')
        );
    }
    wp_send_json_success(array(
        'message' => 'If Budly has a consented profile for that email, a six-digit code is on its way. Check spam if it does not arrive shortly.',
    ));
}
// Legacy recall is intentionally not registered. Secure recall is REST/session based.

function budly_sales_verify_recall_code() {
    check_ajax_referer('budly_sales_recall', 'nonce');
    if (!budly_sales_recall_rate_limit('verify', 10, 15 * MINUTE_IN_SECONDS)) {
        wp_send_json_error(array('message' => 'Too many attempts. Please wait 15 minutes and try again.'), 429);
    }
    $email = sanitize_email(isset($_POST['email']) ? wp_unslash($_POST['email']) : '');
    $code = preg_replace('/[^0-9]/', '', isset($_POST['code']) ? wp_unslash($_POST['code']) : '');
    if (!is_email($email) || strlen($code) !== 6) {
        wp_send_json_error(array('message' => 'Enter the six-digit code from your email.'), 400);
    }
    $email_hash = budly_sales_identity_hash($email);
    $key = 'budly_recall_code_' . $email_hash;
    $record = get_transient($key);
    if (!is_array($record) || empty($record['hash']) || empty($record['customer_id'])) {
        wp_send_json_error(array('message' => 'That code is invalid or expired. Request a new code.'), 403);
    }
    $record['attempts'] = isset($record['attempts']) ? (int) $record['attempts'] + 1 : 1;
    if ($record['attempts'] > 5) {
        delete_transient($key);
        wp_send_json_error(array('message' => 'That code is invalid or expired. Request a new code.'), 403);
    }
    if (!wp_check_password($code, $record['hash'])) {
        set_transient($key, $record, 10 * MINUTE_IN_SECONDS);
        wp_send_json_error(array('message' => 'That code is invalid or expired. Request a new code.'), 403);
    }
    delete_transient($key);
    global $wpdb;
    $tables = budly_sales_tracking_tables();
    $customer = $wpdb->get_row($wpdb->prepare(
        "SELECT id,name,email,phone FROM {$tables['customers']} WHERE id = %d AND email_hash = %s AND memory_consent = 1",
        (int) $record['customer_id'],
        $email_hash
    ));
    if (!$customer) {
        wp_send_json_error(array('message' => 'No consented Budly profile is available for that email.'), 404);
    }
    $rows = $wpdb->get_results($wpdb->prepare(
        "SELECT created_at,journey,summary FROM {$tables['conversations']} WHERE customer_id = %d ORDER BY id DESC LIMIT 5",
        (int) $customer->id
    ), ARRAY_A);
    $history = array_map(function ($row) {
        return array(
            'created_at' => sanitize_text_field($row['created_at']),
            'journey' => sanitize_text_field($row['journey']),
            'summary' => sanitize_textarea_field($row['summary']),
        );
    }, $rows ?: array());
    wp_send_json_success(array(
        'profile' => array('name'=>$customer->name,'email'=>$customer->email,'phone'=>$customer->phone),
        'history' => $history,
        'message' => $history ? 'Welcome back. I found your recent Budly conversations.' : 'Welcome back. Your profile is verified.',
    ));
}
// Legacy verification is intentionally not registered. Do not restore these AJAX actions.

function budly_sales_track_event() {
    check_ajax_referer('budly_sales_track', 'nonce');
    $rate_key = 'budly_track_' . hash_hmac('sha256', isset($_SERVER['REMOTE_ADDR']) ? (string) $_SERVER['REMOTE_ADDR'] : 'unknown', wp_salt('nonce'));
    $rate_count = (int) get_transient($rate_key);
    if ($rate_count >= 120) { wp_send_json_error(array('message'=>'Please wait before sending more activity.'), 429); }
    set_transient($rate_key, $rate_count + 1, 10 * MINUTE_IN_SECONDS);
    $allowed = array('budly_button_clicked','conversation_started','identity_verified','history_recalled','starter_selected','journey_selected','recommendation_shown','product_clicked','human_support_requested','conversation_completed');
    $event = sanitize_key(isset($_POST['event']) ? wp_unslash($_POST['event']) : '');
    if (!in_array($event, $allowed, true)) {
        wp_send_json_error(array('message' => 'Unsupported event.'), 400);
    }
    $session = sanitize_text_field(isset($_POST['session']) ? wp_unslash($_POST['session']) : '');
    if (!$session || strlen($session) > 64) {
        wp_send_json_error(array('message' => 'Invalid session.'), 400);
    }
    $journey = sanitize_text_field(isset($_POST['journey']) ? wp_unslash($_POST['journey']) : '');
    $product_url = esc_url_raw(isset($_POST['product_url']) ? wp_unslash($_POST['product_url']) : '');
    $metadata = sanitize_textarea_field(isset($_POST['metadata']) ? wp_unslash($_POST['metadata']) : '');
    global $wpdb;
    $tables = budly_sales_tracking_tables();
    $wpdb->insert($tables['events'], array(
        'created_at' => current_time('mysql', true),
        'event_name' => $event,
        'session_id' => $session,
        'journey' => $journey,
        'product_url' => $product_url,
        // Public analytics must never establish identity, consent, or memory.
        'email_hash' => '',
        'phone_hash' => '',
        'metadata' => $metadata,
    ));
    budly_sales_send_to_sheet(array(
        'event'=>$event,
        'session'=>$session,
        'name'=>'',
        'email'=>'',
        'phone'=>'',
        'journey'=>$journey,
        'product_url'=>$product_url,
        'summary'=>'',
        'created_at'=>gmdate('c'),
    ));
    wp_send_json_success(array('recorded'=>true));
}
add_action('wp_ajax_budly_sales_track', 'budly_sales_track_event');
add_action('wp_ajax_nopriv_budly_sales_track', 'budly_sales_track_event');

function budly_sales_send_to_sheet($payload) {
    $url = esc_url_raw(get_option('budly_sales_sheet_webhook', ''));
    if (!$url) { return; }
    wp_remote_post($url, array('timeout'=>3,'blocking'=>false,'headers'=>array('Content-Type'=>'application/json'),'body'=>wp_json_encode($payload)));
}

function budly_sales_tracking_admin_menu() {
    add_menu_page('Budly Sales Tracking','Budly Sales','manage_woocommerce','budly-sales-tracking','budly_sales_tracking_dashboard','dashicons-chart-line',56);
}
add_action('admin_menu', 'budly_sales_tracking_admin_menu');

function budly_sales_tracking_dashboard() {
    if (!current_user_can('manage_woocommerce')) { return; }
    global $wpdb;
    $tables = budly_sales_tracking_tables();
    if (isset($_POST['budly_save_settings'])) {
        check_admin_referer('budly_sales_settings');
        update_option('budly_sales_sheet_webhook', esc_url_raw(isset($_POST['sheet_webhook']) ? wp_unslash($_POST['sheet_webhook']) : ''));
        echo '<div class="notice notice-success"><p>Budly tracking settings saved.</p></div>';
    }
    $counts = array();
    foreach (array('budly_button_clicked','conversation_started','recommendation_shown','product_clicked','human_support_requested','conversation_completed') as $event) {
        $counts[$event] = (int) $wpdb->get_var($wpdb->prepare("SELECT COUNT(*) FROM {$tables['events']} WHERE event_name = %s", $event));
    }
    $recent = $wpdb->get_results("SELECT created_at,event_name,journey,session_id FROM {$tables['events']} ORDER BY id DESC LIMIT 25");
    ?>
    <div class="wrap"><h1>Budly Sales Tracking</h1>
      <p>First-party aggregate sales events only. This tracking system cannot establish customer identity, consent, or secure memory.</p>
      <div style="display:flex;gap:12px;flex-wrap:wrap"><?php foreach ($counts as $key=>$value): ?><div style="background:#fff;border:1px solid #ccd0d4;padding:16px;min-width:150px"><strong><?php echo esc_html(ucwords(str_replace('_',' ',$key))); ?></strong><div style="font-size:30px"><?php echo esc_html($value); ?></div></div><?php endforeach; ?></div>
      <h2>Google Sheets connection</h2><form method="post"><?php wp_nonce_field('budly_sales_settings'); ?><p><label>Apps Script webhook URL<br><input type="url" name="sheet_webhook" value="<?php echo esc_attr(get_option('budly_sales_sheet_webhook','')); ?>" class="regular-text" placeholder="https://script.google.com/macros/s/.../exec"></label></p><p><button class="button button-primary" name="budly_save_settings" value="1">Save connection</button></p></form>
      <p><a class="button" href="<?php echo esc_url(wp_nonce_url(admin_url('admin-post.php?action=budly_sales_export'),'budly_sales_export')); ?>">Export CSV</a></p>
      <h2>Recent activity</h2><table class="widefat striped"><thead><tr><th>Time (UTC)</th><th>Event</th><th>Journey</th><th>Session</th></tr></thead><tbody><?php foreach ($recent as $row): ?><tr><td><?php echo esc_html($row->created_at); ?></td><td><?php echo esc_html($row->event_name); ?></td><td><?php echo esc_html($row->journey); ?></td><td><?php echo esc_html($row->session_id); ?></td></tr><?php endforeach; ?></tbody></table>
    </div><?php
}

function budly_sales_export() {
    if (!current_user_can('manage_woocommerce')) { wp_die('Not allowed.'); }
    check_admin_referer('budly_sales_export');
    global $wpdb;
    $tables = budly_sales_tracking_tables();
    $rows = $wpdb->get_results("SELECT created_at,event_name,session_id,journey,product_url FROM {$tables['events']} ORDER BY id DESC", ARRAY_A);
    nocache_headers();
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename=budly-sales-events.csv');
    $out = fopen('php://output', 'w');
    fputcsv($out, array('created_at','event_name','session_id','journey','product_url'));
    foreach ($rows as $row) { fputcsv($out, $row); }
    fclose($out);
    exit;
}
add_action('admin_post_budly_sales_export', 'budly_sales_export');
