<?php
namespace Budly\Commerce;

if (!defined('ABSPATH')) { exit; }

/**
 * Commercial Catalog Provisioner for Budly 1.9.0 Hardening.
 *
 * Programmatically preconfigures canonical WooCommerce products, coupons,
 * and draft membership pages in accordance with owner decisions.
 */
final class CatalogProvisioner {

    public static function register() {
        add_action('init', array(__CLASS__, 'handle_redirects'), 1);
        add_action('budly_sales_provision_commercial_catalog', array(__CLASS__, 'provision_all'));
    }

    /**
     * Handle legacy URL redirects (e.g., Torque product ID 875 -> torque-nft-membership).
     *
     * PREDEPLOYMENT SAFETY GATE:
     * This redirect is strictly gated behind the 'budly_torque_slug_migrated' option.
     * It will NOT redirect until slug migration has been verified and the option is set to '1'.
     */
    public static function handle_redirects() {
        if (is_admin() || wp_doing_ajax() || wp_doing_cron()) {
            return;
        }

        // Safety gate: Torque redirect MUST NOT activate until migration flag is explicitly set
        if (get_option('budly_torque_slug_migrated') !== '1') {
            return;
        }

        $request_uri = isset($_SERVER['REQUEST_URI']) ? sanitize_text_field(wp_unslash($_SERVER['REQUEST_URI'])) : '';
        if (preg_match('#^/product/875/?$#i', $request_uri)) {
            wp_safe_redirect(home_url('/product/torque-nft-membership/'), 301);
            exit;
        }
    }

    /**
     * Migrate Torque slug safely: verify ID 875 and variation IDs 877-880, update post_name, set option.
     *
     * @return array Migration status result.
     */
    public static function migrate_torque_slug() {
        if (!function_exists('wc_get_product')) {
            return array('status' => 'error', 'reason' => 'woocommerce_not_active');
        }

        $product = wc_get_product(875);
        if (!$product) {
            return array('status' => 'error', 'reason' => 'product_875_not_found');
        }

        // Verify it is variable product with variations 877-880
        if ($product->get_type() === 'variable') {
            $children = $product->get_children();
            sort($children);
            $expected_variations = array(877, 878, 879, 880);
            $diff = array_diff($expected_variations, $children);
            if (!empty($diff)) {
                return array('status' => 'error', 'reason' => 'variation_ids_mismatch', 'found' => $children);
            }
        }

        // Update slug to torque-nft-membership
        $update_id = wp_update_post(array(
            'ID'        => 875,
            'post_name' => 'torque-nft-membership',
        ));

        if (is_wp_error($update_id) || !$update_id) {
            return array('status' => 'error', 'reason' => 'failed_to_update_slug');
        }

        // Set migration flag to enable redirect
        update_option('budly_torque_slug_migrated', '1');

        return array(
            'status'       => 'success',
            'product_id'   => 875,
            'new_slug'     => 'torque-nft-membership',
            'redirect_on'  => true,
        );
    }

    /**
     * Execute full commercial catalog provisioning.
     * Requires authenticated user with manage_woocommerce or manage_options capability.
     * Fail-closed: unauthenticated or unauthorized users are strictly rejected.
     *
     * @param bool $create_coupons Whether to create live coupon records (default: false, deferred until launch).
     * @return array Summary of provisioned entities.
     */
    public static function provision_all($create_coupons = false) {
        if (
            !is_user_logged_in() ||
            (!current_user_can('manage_woocommerce') && !current_user_can('manage_options'))
        ) {
            return array(
                'status' => 'error',
                'reason' => 'unauthorized'
            );
        }

        $results = array(
            'consultation_product' => self::provision_consultation_product(),
            'community_products'   => self::provision_community_products(),
            'coupons'              => self::provision_coupons($create_coupons),
            'wordpress_pages'      => self::provision_membership_pages(),
        );

        update_option('budly_commercial_alignment_provisioned', true);
        update_option('budly_commercial_alignment_results', $results);

        return $results;
    }

    /**
     * Provision $75 "Is Cannabis Right For Me?" consultation external product.
     * Points to verified Wix Bookings service URL.
     */
    public static function provision_consultation_product() {
        if (!function_exists('wc_get_product')) {
            return array('status' => 'skipped', 'reason' => 'woocommerce_not_active');
        }

        $canonical_id = 'ccc:service:is-cannabis-right-for-me';
        $slug = 'is-cannabis-right-for-me';
        $sku = 'CCC-SRV-ICRFM75';
        $external_url = 'https://wakenbakelounge.com/service-page/is-cannabis-right-for-me';

        // Check if product already exists by SKU or slug
        $existing_id = wc_get_product_id_by_sku($sku);
        if (!$existing_id) {
            $existing_post = get_page_by_path($slug, OBJECT, 'product');
            if ($existing_post) {
                $existing_id = $existing_post->ID;
            }
        }

        if ($existing_id) {
            update_post_meta($existing_id, '_budly_canonical_id', $canonical_id);
            update_post_meta($existing_id, '_budly_fulfillment_platform', 'wix_bookings');
            return array(
                'status'        => 'existing',
                'product_id'    => $existing_id,
                'canonical_id'  => $canonical_id,
                'sku'           => $sku,
                'slug'          => $slug,
                'price'         => 75.00,
                'external_url'  => $external_url,
            );
        }

        $product = new \WC_Product_External();
        $product->set_name('Is Cannabis Right For Me?');
        $product->set_slug($slug);
        $product->set_status('publish');
        $product->set_catalog_visibility('visible');
        $product->set_regular_price('75.00');
        $product->set_price('75.00');
        $product->set_sku($sku);
        $product->set_product_url($external_url);
        $product->set_button_text('Book Consultation');
        $product->set_description("1-on-1 personalized cannabis consultation appointment. Explore whether cannabis is right for your wellness goals with personalized guidance.\n\nFulfillment is scheduled directly through Wake'n'Bake Lounge.");
        $product->set_short_description("1-on-1 personalized cannabis consultation appointment ($75.00).");
        
        $product_id = $product->save();
        if ($product_id) {
            update_post_meta($product_id, '_budly_canonical_id', $canonical_id);
            update_post_meta($product_id, '_budly_fulfillment_platform', 'wix_bookings');
            return array(
                'status'        => 'created',
                'product_id'    => $product_id,
                'canonical_id'  => $canonical_id,
                'sku'           => $sku,
                'slug'          => $slug,
                'price'         => 75.00,
                'external_url'  => $external_url,
            );
        }

        return array('status' => 'error', 'reason' => 'failed_to_save');
    }

    /**
     * Provision Draft/Private Community Memberships with full verified benefit packages.
     * Explicitly documents WC_Product_Simple as a draft catalog placeholder with
     * billing_model = RECURRING_MONTHLY (or FREE), checkout_capability = NOT_CONFIGURED,
     * customer_purchasable = false, payment_processor = TBD_APPROVED_PROCESSOR (or NONE).
     *
     * Note: A simple Woo product is only a canonical catalog placeholder and does NOT implement recurring billing.
     */
    public static function provision_community_products() {
        if (!function_exists('wc_get_product')) {
            return array('status' => 'skipped', 'reason' => 'woocommerce_not_active');
        }

        $specs = array(
            array(
                'canonical_id'        => 'wnb:community:lounge-pass',
                'name'                => "Wake'n'Bake Lounge Pass",
                'slug'                => 'lounge-pass',
                'sku'                 => 'WNB-MBR-PASS',
                'price'               => '0.00',
                'wix_plan_id'         => 'a101970a-4600-4dbb-8e49-e91cfed93d80',
                'billing_model'       => 'FREE',
                'payment_processor'   => 'NONE',
                'benefit_count'       => 1,
                'description'         => "Free community access. Approved for future launch; currently unreleased.\n\nBenefits (1 approved benefit):\n- Community access",
                'short_desc'          => "Free Wake'n'Bake Lounge Community Pass (Approved / Unreleased).",
            ),
            array(
                'canonical_id'        => 'wnb:community:lounge-member',
                'name'                => "Wake'n'Bake Lounge Member",
                'slug'                => 'lounge-member',
                'sku'                 => 'WNB-MBR-MEMBER',
                'price'               => '9.99',
                'wix_plan_id'         => '1658a089-db78-418c-85ed-ac01d5bcabb0',
                'billing_model'       => 'RECURRING_MONTHLY',
                'payment_processor'   => 'TBD_APPROVED_PROCESSOR',
                'benefit_count'       => 6,
                'description'         => "Join the premium Wake'n'Bake Lounge community. Enjoy 10% off all Lounge Collection products, early access to new drops, exclusive forum sections, member badge, and priority event access.\n\nFull Benefits (6 approved benefits):\n- Community access\n- 10% off all Lounge Collection products (Coupon: LOUNGEMEMBER10)\n- Early access to new drops\n- Exclusive forum sections\n- Member badge\n- Priority event access",
                'short_desc'          => "Wake'n'Bake Lounge Member ($9.99/month, Approved / Unreleased).",
            ),
            array(
                'canonical_id'        => 'wnb:community:lounge-elite',
                'name'                => "Wake'n'Bake Lounge Elite",
                'slug'                => 'lounge-elite',
                'sku'                 => 'WNB-MBR-ELITE',
                'price'               => '24.99',
                'wix_plan_id'         => 'ac8a8d86-961d-417e-84a3-47cd6537db9f',
                'billing_model'       => 'RECURRING_MONTHLY',
                'payment_processor'   => 'TBD_APPROVED_PROCESSOR',
                'benefit_count'       => 6,
                'description'         => "The ultimate Wake'n'Bake Lounge membership. Enjoy 25% off all Lounge Collection products, first access to exclusive drops, VIP forum badge, priority event invitations, and monthly curated content from Budly T. Cannaguide.\n\nFull Benefits (6 approved benefits):\n- Community access\n- 25% off all Lounge Collection products (Coupon: LOUNGEELITE25)\n- First access to exclusive drops\n- VIP forum badge\n- Priority event invitations\n- Monthly curated content from Budly T. Cannaguide",
                'short_desc'          => "Wake'n'Bake Lounge Elite ($24.99/month, Approved / Unreleased).",
            ),
        );

        $out = array();
        foreach ($specs as $s) {
            $existing_id = wc_get_product_id_by_sku($s['sku']);
            if (!$existing_id) {
                $existing_post = get_page_by_path($s['slug'], OBJECT, 'product');
                if ($existing_post) {
                    $existing_id = $existing_post->ID;
                }
            }

            if ($existing_id) {
                update_post_meta($existing_id, '_budly_canonical_id', $s['canonical_id']);
                update_post_meta($existing_id, '_budly_wix_plan_id', $s['wix_plan_id']);
                update_post_meta($existing_id, '_budly_billing_model', $s['billing_model']);
                update_post_meta($existing_id, '_budly_checkout_capability', 'NOT_CONFIGURED');
                update_post_meta($existing_id, '_budly_customer_purchasable', 'false');
                update_post_meta($existing_id, '_budly_payment_processor', $s['payment_processor']);
                update_post_meta($existing_id, '_budly_release_status', 'APPROVED_NOT_RELEASED');
                update_post_meta($existing_id, '_budly_benefit_count', $s['benefit_count']);
                $out[$s['canonical_id']] = array(
                    'status'        => 'existing',
                    'product_id'    => $existing_id,
                    'sku'           => $s['sku'],
                    'wix_plan_id'   => $s['wix_plan_id'],
                    'benefit_count' => $s['benefit_count'],
                    'visibility'    => 'draft_private',
                );
                continue;
            }

            $product = new \WC_Product_Simple();
            $product->set_name($s['name']);
            $product->set_slug($s['slug']);
            // Crucial: Keep draft/private and hidden from shop search/catalog
            $product->set_status('draft');
            $product->set_catalog_visibility('hidden');
            $product->set_regular_price($s['price']);
            $product->set_price($s['price']);
            $product->set_sku($s['sku']);
            $product->set_description($s['description']);
            $product->set_short_description($s['short_desc']);

            $pid = $product->save();
            if ($pid) {
                update_post_meta($pid, '_budly_canonical_id', $s['canonical_id']);
                update_post_meta($pid, '_budly_wix_plan_id', $s['wix_plan_id']);
                update_post_meta($pid, '_budly_billing_model', $s['billing_model']);
                update_post_meta($pid, '_budly_checkout_capability', 'NOT_CONFIGURED');
                update_post_meta($pid, '_budly_customer_purchasable', 'false');
                update_post_meta($pid, '_budly_payment_processor', $s['payment_processor']);
                update_post_meta($pid, '_budly_release_status', 'APPROVED_NOT_RELEASED');
                update_post_meta($pid, '_budly_benefit_count', $s['benefit_count']);
                $out[$s['canonical_id']] = array(
                    'status'        => 'created',
                    'product_id'    => $pid,
                    'sku'           => $s['sku'],
                    'wix_plan_id'   => $s['wix_plan_id'],
                    'benefit_count' => $s['benefit_count'],
                    'visibility'    => 'draft_hidden',
                );
            }
        }

        return $out;
    }

    /**
     * Provision discount coupons for community memberships.
     *
     * SAFETY GATE / DEFERRAL POLICY:
     * By default ($execute = false), live WooCommerce coupon creation is DEFERRED until membership launch.
     * Prelaunch coupons are not created in live WooCommerce until runtime redemption behavior is verified or launch occurs.
     *
     * @param bool $execute Set to true to execute draft coupon creation. Default: false.
     * @return array Status of coupon provisioning.
     */
    public static function provision_coupons($execute = false) {
        if (!$execute) {
            return array(
                'status'           => 'deferred_until_launch',
                'policy'           => 'DEFER_LIVE_COUPON_CREATION_UNTIL_LAUNCH',
                'classification'   => 'PRELAUNCH_CONFIGURATION_PRESENT',
                'verification'     => 'REDEMPTION_BEHAVIOR_NOT_RUNTIME_VERIFIED',
                'planned_coupons'  => array(
                    'LOUNGEMEMBER10' => array('percent' => 10, 'tier' => 'Lounge Member'),
                    'LOUNGEELITE25'  => array('percent' => 25, 'tier' => 'Lounge Elite'),
                ),
            );
        }

        if (!class_exists('\\WC_Coupon')) {
            return array('status' => 'skipped', 'reason' => 'woocommerce_not_active');
        }

        $coupons = array(
            'LOUNGEMEMBER10' => array('percent' => 10, 'desc' => '10% off Lounge Collection for Lounge Members (Approved / Unreleased)'),
            'LOUNGEELITE25'  => array('percent' => 25, 'desc' => '25% off Lounge Collection for Lounge Elite Members (Approved / Unreleased)'),
        );

        $out = array();
        foreach ($coupons as $code => $data) {
            $coupon_id = wc_get_coupon_id_by_code($code);
            if ($coupon_id) {
                $out[$code] = array(
                    'status'     => 'existing',
                    'coupon_id'  => $coupon_id,
                    'percentage' => $data['percent'],
                    'state'      => 'inactive_unreleased',
                );
                continue;
            }

            $coupon = new \WC_Coupon();
            $coupon->set_code($code);
            $coupon->set_discount_type('percent');
            $coupon->set_amount($data['percent']);
            $coupon->set_description($data['desc']);
            $coupon->set_individual_use(true);
            // Inactive / unreleased: set expiry in past to prevent checkout application
            $coupon->set_date_expires(strtotime('-1 year'));
            $cid = $coupon->save();

            if ($cid) {
                // Ensure post status is draft so it cannot be applied at checkout
                wp_update_post(array('ID' => $cid, 'post_status' => 'draft'));
                update_post_meta($cid, '_budly_release_status', 'APPROVED_NOT_RELEASED');
                $out[$code] = array(
                    'status'     => 'created',
                    'coupon_id'  => $cid,
                    'percentage' => $data['percent'],
                    'state'      => 'draft_inactive',
                );
            }
        }

        return $out;
    }

    /**
     * Provision draft/private WordPress membership detail pages.
     */
    public static function provision_membership_pages() {
        $pages = array(
            'lounge-pass' => array(
                'title'         => "Wake'n'Bake Lounge Pass",
                'canonical_id'  => 'wnb:community:lounge-pass',
                'wix_plan_id'   => 'a101970a-4600-4dbb-8e49-e91cfed93d80',
                'price'         => 'Free',
                'benefit_count' => 1,
                'content'       => "<!-- wp:paragraph -->\n<p><strong>Status: APPROVED FOR FUTURE LAUNCH (CURRENTLY UNRELEASED)</strong></p>\n<!-- /wp:paragraph -->\n<!-- wp:paragraph -->\n<p>Free community access to the Wake'n'Bake Lounge digital ecosystem.</p>\n<!-- /wp:paragraph -->\n<!-- wp:list -->\n<ul><li>Community access</li></ul>\n<!-- /wp:list -->",
            ),
            'lounge-member' => array(
                'title'         => "Wake'n'Bake Lounge Member",
                'canonical_id'  => 'wnb:community:lounge-member',
                'wix_plan_id'   => '1658a089-db78-418c-85ed-ac01d5bcabb0',
                'price'         => '$9.99/month',
                'benefit_count' => 6,
                'content'       => "<!-- wp:paragraph -->\n<p><strong>Status: APPROVED FOR FUTURE LAUNCH (CURRENTLY UNRELEASED)</strong></p>\n<!-- /wp:paragraph -->\n<!-- wp:paragraph -->\n<p>Join the premium Wake'n'Bake Lounge community ($9.99/month).</p>\n<!-- /wp:paragraph -->\n<!-- wp:list -->\n<ul><li>Community access</li><li>10% off all Lounge Collection products</li><li>Early access to new drops</li><li>Exclusive forum sections</li><li>Member badge</li><li>Priority event access</li></ul>\n<!-- /wp:list -->",
            ),
            'lounge-elite' => array(
                'title'         => "Wake'n'Bake Lounge Elite",
                'canonical_id'  => 'wnb:community:lounge-elite',
                'wix_plan_id'   => 'ac8a8d86-961d-417e-84a3-47cd6537db9f',
                'price'         => '$24.99/month',
                'benefit_count' => 6,
                'content'       => "<!-- wp:paragraph -->\n<p><strong>Status: APPROVED FOR FUTURE LAUNCH (CURRENTLY UNRELEASED)</strong></p>\n<!-- /wp:paragraph -->\n<!-- wp:paragraph -->\n<p>The ultimate Wake'n'Bake Lounge membership tier ($24.99/month).</p>\n<!-- /wp:paragraph -->\n<!-- wp:list -->\n<ul><li>Community access</li><li>25% off all Lounge Collection products</li><li>First access to exclusive drops</li><li>VIP forum badge</li><li>Priority event invitations</li><li>Monthly curated content from Budly T. Cannaguide</li></ul>\n<!-- /wp:list -->",
            ),
        );

        $out = array();
        foreach ($pages as $slug => $p) {
            $existing = get_page_by_path($slug);
            if ($existing) {
                update_post_meta($existing->ID, '_budly_canonical_id', $p['canonical_id']);
                update_post_meta($existing->ID, '_budly_wix_plan_id', $p['wix_plan_id']);
                update_post_meta($existing->ID, '_budly_benefit_count', $p['benefit_count']);
                $out[$p['canonical_id']] = array(
                    'status'        => 'existing',
                    'page_id'       => $existing->ID,
                    'slug'          => $slug,
                    'benefit_count' => $p['benefit_count'],
                    'edit_url'      => admin_url('post.php?post=' . $existing->ID . '&action=edit'),
                );
                continue;
            }

            $pid = wp_insert_post(array(
                'post_title'   => $p['title'],
                'post_name'    => $slug,
                'post_content' => $p['content'],
                'post_status'  => 'draft',
                'post_type'    => 'page',
            ));

            if (!is_wp_error($pid) && $pid) {
                update_post_meta($pid, '_budly_canonical_id', $p['canonical_id']);
                update_post_meta($pid, '_budly_wix_plan_id', $p['wix_plan_id']);
                update_post_meta($pid, '_budly_release_status', 'APPROVED_NOT_RELEASED');
                update_post_meta($pid, '_budly_benefit_count', $p['benefit_count']);
                $out[$p['canonical_id']] = array(
                    'status'        => 'created',
                    'page_id'       => $pid,
                    'slug'          => $slug,
                    'benefit_count' => $p['benefit_count'],
                    'edit_url'      => admin_url('post.php?post=' . $pid . '&action=edit'),
                );
            }
        }

        return $out;
    }
}
