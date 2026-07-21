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

function budly_sales_track_event() {
    check_ajax_referer('budly_sales_track', 'nonce');
    $allowed = array('budly_button_clicked','conversation_started','starter_selected','journey_selected','recommendation_shown','product_clicked','human_support_requested','conversation_completed');
    $event = sanitize_key(isset($_POST['event']) ? wp_unslash($_POST['event']) : '');
    if (!in_array($event, $allowed, true)) {
        wp_send_json_error(array('message' => 'Unsupported event.'), 400);
    }
    $session = sanitize_text_field(isset($_POST['session']) ? wp_unslash($_POST['session']) : '');
    if (!$session || strlen($session) > 64) {
        wp_send_json_error(array('message' => 'Invalid session.'), 400);
    }
    $email = sanitize_email(isset($_POST['email']) ? wp_unslash($_POST['email']) : '');
    $phone = budly_sales_normalize_phone(isset($_POST['phone']) ? wp_unslash($_POST['phone']) : '');
    $name = sanitize_text_field(isset($_POST['name']) ? wp_unslash($_POST['name']) : '');
    $journey = sanitize_text_field(isset($_POST['journey']) ? wp_unslash($_POST['journey']) : '');
    $product_url = esc_url_raw(isset($_POST['product_url']) ? wp_unslash($_POST['product_url']) : '');
    $summary = sanitize_textarea_field(isset($_POST['summary']) ? wp_unslash($_POST['summary']) : '');
    $memory_consent = !empty($_POST['memory_consent']);
    $metadata = sanitize_textarea_field(isset($_POST['metadata']) ? wp_unslash($_POST['metadata']) : '');
    global $wpdb;
    $tables = budly_sales_tracking_tables();
    $wpdb->insert($tables['events'], array(
        'created_at' => current_time('mysql', true),
        'event_name' => $event,
        'session_id' => $session,
        'journey' => $journey,
        'product_url' => $product_url,
        'email_hash' => budly_sales_identity_hash($email),
        'phone_hash' => budly_sales_identity_hash($phone),
        'metadata' => $metadata,
    ));
    if ($memory_consent && $email && is_email($email)) {
        $email_hash = budly_sales_identity_hash($email);
        $customer_id = (int) $wpdb->get_var($wpdb->prepare("SELECT id FROM {$tables['customers']} WHERE email_hash = %s", $email_hash));
        $values = array('updated_at'=>current_time('mysql', true),'name'=>$name,'email'=>$email,'phone'=>$phone,'phone_hash'=>budly_sales_identity_hash($phone),'memory_consent'=>1);
        if ($customer_id) {
            $wpdb->update($tables['customers'], $values, array('id'=>$customer_id));
        } else {
            $values['created_at'] = current_time('mysql', true);
            $values['email_hash'] = $email_hash;
            $wpdb->insert($tables['customers'], $values);
            $customer_id = (int) $wpdb->insert_id;
        }
        if ($summary && $event === 'conversation_completed') {
            $wpdb->insert($tables['conversations'], array('created_at'=>current_time('mysql', true),'customer_id'=>$customer_id,'session_id'=>$session,'journey'=>$journey,'summary'=>$summary));
        }
    }
    budly_sales_send_to_sheet(array('event'=>$event,'session'=>$session,'name'=>$memory_consent?$name:'','email'=>$memory_consent?$email:'','phone'=>$memory_consent?$phone:'','journey'=>$journey,'product_url'=>$product_url,'summary'=>($memory_consent&&$event==='conversation_completed')?$summary:'','created_at'=>gmdate('c')));
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
      <p>First-party totals. Conversation content is stored only when the customer explicitly chooses memory consent.</p>
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
