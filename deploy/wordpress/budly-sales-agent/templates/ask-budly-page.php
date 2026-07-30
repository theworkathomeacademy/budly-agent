<?php
/**
 * Plugin-owned template for the dedicated Ask Budly page.
 */
if (!defined('ABSPATH')) { exit; }
?><!doctype html>
<html <?php language_attributes(); ?>>
<head>
  <meta charset="<?php bloginfo('charset'); ?>">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <?php wp_head(); ?>
</head>
<body <?php body_class('budly-dedicated-page'); ?>>
<?php wp_body_open(); ?>
<main id="primary" class="budly-dedicated-main">
  <?php echo do_shortcode('[budly_sales_agent]'); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?>
</main>
<?php wp_footer(); ?>
</body>
</html>
