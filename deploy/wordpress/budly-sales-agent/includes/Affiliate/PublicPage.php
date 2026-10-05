<?php
namespace Budly\Affiliate;

if (!defined('ABSPATH')) { exit; }

final class PublicPage {
    public static function register() {
        add_shortcode('budly_affiliate_public', array(__CLASS__, 'render'));
    }

    public static function render() {
        ob_start();
        ?>
        <div class="budly-affiliate-public-wrapper" data-surface="public-affiliate">
          <style>
            .budly-pub-wrap {
              max-width: 960px;
              margin: 20px auto 40px;
              padding: 0 16px;
              color: #17261d;
              font-family: Georgia, serif;
              line-height: 1.6;
              box-sizing: border-box;
            }
            .budly-pub-hero {
              background: #faf7f0;
              border: 1px solid #d9ddcf;
              border-radius: 24px;
              padding: clamp(28px, 6vw, 56px);
              text-align: center;
              box-shadow: 0 15px 45px rgba(23, 54, 36, 0.06);
              margin-bottom: 32px;
            }
            .budly-pub-eyebrow {
              text-transform: uppercase;
              letter-spacing: 0.16em;
              color: #2d6a4f;
              font: 700 13px Arial, sans-serif;
              margin-bottom: 10px;
              display: inline-block;
            }
            .budly-pub-title {
              font-size: clamp(30px, 5vw, 44px);
              color: #173624;
              margin: 0 0 16px;
              line-height: 1.15;
              font-weight: 700;
            }
            .budly-pub-lead {
              font-size: clamp(16px, 2.5vw, 19px);
              color: #3b4e43;
              max-width: 720px;
              margin: 0 auto 24px;
            }
            .budly-pub-badge {
              display: inline-flex;
              align-items: center;
              gap: 8px;
              background: #eaf1ec;
              border: 1px solid #c3d6c8;
              color: #1b4332;
              padding: 8px 18px;
              border-radius: 999px;
              font-family: Arial, sans-serif;
              font-size: 14px;
              font-weight: 600;
              margin-bottom: 8px;
            }
            .budly-pub-badge-dot {
              width: 10px;
              height: 10px;
              border-radius: 50%;
              background: #2d6a4f;
              display: inline-block;
            }
            .budly-pub-cta-row {
              display: flex;
              flex-wrap: wrap;
              gap: 14px;
              justify-content: center;
              margin-top: 24px;
            }
            .budly-pub-btn {
              display: inline-flex;
              align-items: center;
              justify-content: center;
              min-height: 48px;
              padding: 12px 28px;
              border-radius: 12px;
              font-family: Arial, sans-serif;
              font-weight: 700;
              font-size: 15px;
              text-decoration: none;
              transition: all 0.2s ease;
              box-sizing: border-box;
            }
            .budly-pub-btn-primary {
              background: #173624;
              color: #ffffff !important;
            }
            .budly-pub-btn-primary:hover {
              background: #245238;
              color: #ffffff !important;
            }
            .budly-pub-btn-secondary {
              background: #ffffff;
              color: #173624 !important;
              border: 1px solid #c8cdbf;
            }
            .budly-pub-btn-secondary:hover {
              background: #f0f3ec;
              color: #173624 !important;
            }
            .budly-pub-grid-2 {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
              gap: 24px;
              margin-bottom: 32px;
            }
            .budly-pub-card {
              background: #ffffff;
              border: 1px solid #e1e5da;
              border-radius: 18px;
              padding: clamp(20px, 4vw, 32px);
              box-shadow: 0 4px 18px rgba(23, 54, 36, 0.04);
              box-sizing: border-box;
            }
            .budly-pub-card h3 {
              font-size: 22px;
              color: #173624;
              margin: 0 0 12px;
              font-family: Georgia, serif;
            }
            .budly-pub-card p, .budly-pub-card li {
              font-family: Arial, sans-serif;
              font-size: 15px;
              color: #3e4f44;
              line-height: 1.55;
            }
            .budly-pub-rates-grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
              gap: 16px;
              margin: 20px 0;
            }
            .budly-pub-rate-card {
              background: #faf7f0;
              border: 1px solid #d9ddcf;
              border-radius: 14px;
              padding: 18px 14px;
              text-align: center;
              transition: transform 0.15s ease;
            }
            .budly-pub-rate-pct {
              font-size: 32px;
              font-weight: 700;
              color: #173624;
              font-family: Arial, sans-serif;
              line-height: 1;
              margin-bottom: 6px;
            }
            .budly-pub-rate-label {
              font-size: 13px;
              font-family: Arial, sans-serif;
              font-weight: 600;
              color: #2d6a4f;
              text-transform: uppercase;
              letter-spacing: 0.05em;
              margin-bottom: 4px;
            }
            .budly-pub-rate-desc {
              font-size: 12px;
              font-family: Arial, sans-serif;
              color: #55665b;
            }
            .budly-pub-sub-notice {
              background: #edf3ee;
              border-left: 4px solid #2d6a4f;
              padding: 16px 20px;
              border-radius: 10px;
              margin: 18px 0;
              font-family: Arial, sans-serif;
              font-size: 14px;
              line-height: 1.5;
              color: #173624;
            }
            .budly-pub-list {
              margin: 14px 0 0;
              padding-left: 20px;
            }
            .budly-pub-list li {
              margin-bottom: 10px;
            }
            .budly-pub-faq-item {
              border-top: 1px solid #e7ebe0;
              padding: 18px 0;
            }
            .budly-pub-faq-item:first-child {
              border-top: 0;
              padding-top: 0;
            }
            .budly-pub-faq-q {
              font-family: Georgia, serif;
              font-size: 18px;
              font-weight: 700;
              color: #173624;
              margin: 0 0 6px;
            }
            .budly-pub-faq-a {
              font-family: Arial, sans-serif;
              font-size: 14px;
              color: #425348;
              line-height: 1.55;
              margin: 0;
            }
            @media (max-width: 680px) {
              .budly-pub-rates-grid {
                grid-template-columns: 1fr 1fr;
              }
              .budly-pub-cta-row {
                flex-direction: column;
              }
              .budly-pub-btn {
                width: 100%;
              }
            }
          </style>

          <div class="budly-pub-wrap">
            <!-- HERO -->
            <section class="budly-pub-hero">
              <span class="budly-pub-eyebrow">Wake'n'Bake Lounge™ &amp; Compassionate Care Cultivators</span>
              <h1 class="budly-pub-title">The Affiliate Program</h1>
              <div class="budly-pub-badge">
                <span class="budly-pub-badge-dot"></span>
                <span>Private Pilot Phase &bull; Invite-Only Enrollment</span>
              </div>
              <p class="budly-pub-lead">
                A community-centered partnership empowering genuine wellness advocates, educators, and creators to earn transparent, sustainable commissions by sharing trusted herbal formulations, educational literature, courses, and premium lifestyle goods.
              </p>
              <div class="budly-pub-cta-row">
                <a href="<?php echo esc_url(home_url('/ask-budly/')); ?>" class="budly-pub-btn budly-pub-btn-primary">
                  Ask Budly About the Program
                </a>
                <a href="<?php echo esc_url(home_url('/affiliate-registration/')); ?>" class="budly-pub-btn budly-pub-btn-secondary">
                  Have an Invitation Code? Register Here
                </a>
              </div>
            </section>

            <!-- WHO IT IS FOR & NO FOLLOWER MINIMUM -->
            <div class="budly-pub-grid-2">
              <section class="budly-pub-card">
                <h3>Who It Is For</h3>
                <p>
                  We collaborate with authentic voices dedicated to holistic wellness, education, mindful cultivation, and community care:
                </p>
                <ul class="budly-pub-list">
                  <li><strong>Creators &amp; Storytellers:</strong> Sharing thoughtful, educational lifestyle and wellness content.</li>
                  <li><strong>Educators &amp; Herbalists:</strong> Guiding communities in natural remedies and mindful recipes.</li>
                  <li><strong>Wellness Practitioners:</strong> Recommending clean, tested botanical formulations.</li>
                  <li><strong>Community Advocates:</strong> Fostering safe, compassionate spaces for holistic health.</li>
                </ul>
              </section>

              <section class="budly-pub-card">
                <h3>No Follower Minimum</h3>
                <p>
                  We prioritize <strong>trust, alignment, and authentic engagement</strong> over raw follower vanity metrics. You do not need a massive audience or viral reach to partner with us.
                </p>
                <p>
                  Whether your community is 50 engaged local clients or 50,000 subscribers, what matters is genuine connection, educational honesty, and shared values. Every application undergoes careful human review by our founding team.
                </p>
              </section>
            </div>

            <!-- COMMISSION STRUCTURE -->
            <section class="budly-pub-card" style="margin-bottom: 32px;">
              <span class="budly-pub-eyebrow">Governed Commission Rates</span>
              <h2 style="font-size: 26px; color: #173624; margin: 6px 0 12px; font-family: Georgia, serif;">
                Fair, Category-Based Commissions
              </h2>
              <p style="font-family: Arial, sans-serif; font-size: 15px; color: #3e4f44;">
                Our commission schedule is governed by ratified policy (AFF-001 G9B.7C) ensuring predictable, sustainable payouts across all product classes:
              </p>

              <div class="budly-pub-rates-grid">
                <div class="budly-pub-rate-card">
                  <div class="budly-pub-rate-pct">30%</div>
                  <div class="budly-pub-rate-label">Wellness</div>
                  <div class="budly-pub-rate-desc">Herbal tinctures, elixirs &amp; body care</div>
                </div>
                <div class="budly-pub-rate-card">
                  <div class="budly-pub-rate-pct">25%</div>
                  <div class="budly-pub-rate-label">Books</div>
                  <div class="budly-pub-rate-desc">Physical recipe books &amp; digital guides</div>
                </div>
                <div class="budly-pub-rate-card">
                  <div class="budly-pub-rate-pct">15%</div>
                  <div class="budly-pub-rate-label">Courses</div>
                  <div class="budly-pub-rate-desc">Online masterclasses &amp; curriculum</div>
                </div>
                <div class="budly-pub-rate-card">
                  <div class="budly-pub-rate-pct">30%</div>
                  <div class="budly-pub-rate-label">Consults</div>
                  <div class="budly-pub-rate-desc">Personalized wellness consultations</div>
                </div>
                <div class="budly-pub-rate-card">
                  <div class="budly-pub-rate-pct">10%</div>
                  <div class="budly-pub-rate-label">Legends</div>
                  <div class="budly-pub-rate-desc">Premium lounge collector items</div>
                </div>
              </div>

              <!-- RECURRING SUBSCRIPTION RULES -->
              <div class="budly-pub-sub-notice">
                <strong style="display: block; font-size: 15px; margin-bottom: 4px;">Recurring Subscription Commission Policy</strong>
                When a referred customer joins an ongoing membership or product subscription, you receive <strong>30% intro commission</strong> on their initial sequence order, followed by <strong>5% ongoing recurring commission</strong> on all subsequent renewal orders for the active life of the subscription.
              </div>
            </section>

            <!-- HOW IT WORKS & PAYOUT BASICS -->
            <div class="budly-pub-grid-2">
              <section class="budly-pub-card">
                <h3>Payout Basics &amp; Holds</h3>
                <ul class="budly-pub-list">
                  <li><strong>Minimum Payout Threshold:</strong> \$50.00 accrued balance required for disbursement.</li>
                  <li><strong>30-Day Refund Hold:</strong> Orders carry a standard 30-day maturity hold to account for returns and cancellations.</li>
                  <li><strong>Governed Owner Review:</strong> Payout releases are reviewed and manually authorized by program leadership for financial integrity.</li>
                  <li><strong>No Automated Money Movement:</strong> Payout submissions are human-governed to prevent unauthorized disbursements.</li>
                </ul>
              </section>

              <section class="budly-pub-card">
                <h3>Compliance &amp; Ethics</h3>
                <ul class="budly-pub-list">
                  <li><strong>FTC Disclosures Required:</strong> All promotional social posts, newsletters, and videos must include clear disclosure (e.g., <code>#ad</code>, <code>#affiliate</code>).</li>
                  <li><strong>No Unapproved Medical Claims:</strong> We promote wellness lifestyle support, not disease cures or medical treatments.</li>
                  <li><strong>Truthful Recommendations:</strong> Partners only promote products they genuinely stand behind.</li>
                  <li><strong>Privacy First:</strong> Customer identities and private order data are strictly protected and never exposed to affiliates.</li>
                </ul>
              </section>
            </div>

            <!-- WHAT BUDLY CAN & CANNOT DO -->
            <section class="budly-pub-card" style="margin-bottom: 32px;">
              <span class="budly-pub-eyebrow">Conversational Assistant</span>
              <h3 style="margin-top: 6px;">How Budly Supports the Affiliate Program</h3>
              <div class="budly-pub-grid-2" style="margin-top: 16px; margin-bottom: 0;">
                <div>
                  <h4 style="font-family: Arial, sans-serif; font-size: 15px; color: #1b4332; margin: 0 0 8px;">
                    What Budly Can Help With:
                  </h4>
                  <ul class="budly-pub-list" style="margin-top: 6px;">
                    <li>Answering questions about our catalog, ingredients, and product benefits.</li>
                    <li>Explaining commission classes, subscription rules, and payout policies.</li>
                    <li>Guiding prospective partners to program information.</li>
                    <li>Assisting active affiliates with compliant messaging ideas and product educational facts.</li>
                  </ul>
                </div>
                <div>
                  <h4 style="font-family: Arial, sans-serif; font-size: 15px; color: #9c3b21; margin: 0 0 8px;">
                    What Budly Cannot Authorize:
                  </h4>
                  <ul class="budly-pub-list" style="margin-top: 6px;">
                    <li>Budly cannot approve or activate affiliate applications.</li>
                    <li>Budly cannot alter or negotiate commission rates.</li>
                    <li>Budly cannot disburse funds or authorize payouts.</li>
                    <li>Budly cannot expose private application tokens or confidential partner details.</li>
                  </ul>
                </div>
              </div>
            </section>

            <!-- FAQ & NEXT STEPS -->
            <section class="budly-pub-card">
              <span class="budly-pub-eyebrow">Frequently Asked Questions</span>
              <h3 style="margin-top: 6px; margin-bottom: 20px;">Program Questions &amp; Next Steps</h3>

              <div class="budly-pub-faq-item">
                <div class="budly-pub-faq-q">Are public applications currently open?</div>
                <p class="budly-pub-faq-a">
                  No. The program is currently operating in an invite-only private pilot with five selected creators. Public enrollment will be announced after pilot verification is complete.
                </p>
              </div>

              <div class="budly-pub-faq-item">
                <div class="budly-pub-faq-q">I have a private invitation code. How do I apply?</div>
                <p class="budly-pub-faq-a">
                  If you received an invitation token from our team, please visit the <a href="<?php echo esc_url(home_url('/affiliate-registration/')); ?>" style="color: #173624; font-weight: bold;">Private Registration Page</a> and enter your code to access the intake form.
                </p>
              </div>

              <div class="budly-pub-faq-item">
                <div class="budly-pub-faq-q">Where can I ask more questions about products or the program?</div>
                <p class="budly-pub-faq-a">
                  Our guided sales assistant is available 24/7. Visit <a href="<?php echo esc_url(home_url('/ask-budly/')); ?>" style="color: #173624; font-weight: bold;">Ask Budly</a> and ask any question about our products, policies, or affiliate structure.
                </p>
              </div>
            </section>
          </div>
        </div>
        <?php
        return ob_get_clean();
    }
}
