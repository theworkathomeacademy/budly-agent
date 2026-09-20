import os
import re
import pytest

WIX_DEPLOY_DIR = os.path.join(os.path.dirname(__file__), "..", "deploy", "wix")
EMBED_HTML_PATH = os.path.join(WIX_DEPLOY_DIR, "wnb-membership-presentation-embed.html")
VELO_JS_PATH = os.path.join(WIX_DEPLOY_DIR, "wnb-membership-velo-page-code.js")

def test_artifacts_exist():
    assert os.path.exists(EMBED_HTML_PATH), "HTML embed artifact must exist"
    assert os.path.exists(VELO_JS_PATH), "Velo page code artifact must exist"

def test_embed_html_structure_and_neutral_fallback():
    with open(EMBED_HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    # Must contain HTML5 doctype and responsive viewport
    assert "<!DOCTYPE html>" in html
    assert '<meta name="viewport"' in html

    # Initial state must use neutral skeleton loading, not hard-coded pricing or commercial facts
    assert "skeleton" in html
    assert "cardsGrid" in html
    assert "loadingStatus" in html

    # PostMessage contract checks
    assert "WNB_MEMBERSHIP_DATA" in html
    assert "WNB_MEMBERSHIP_CTA" in html
    assert "WNB_EMBED_READY" in html

    # Sanitization check
    assert "escapeHtml" in html

def test_embed_html_supports_all_active_commercial_tiers():
    with open(EMBED_HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    # Active tier CSS classes must exist
    assert "card-active-tier" in html
    assert "badge-active" in html
    assert "btn-primary" in html
    assert "btn-disabled" in html

    # Check that ctaState === 'ACTIVE' activates primary button with ctaUrl
    assert "ctaState === 'ACTIVE'" in html or 'ctaState === "ACTIVE"' in html
    assert "handleCtaClick" in html

def test_negative_routing_checks_in_presentation():
    with open(EMBED_HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    with open(VELO_JS_PATH, "r", encoding="utf-8") as f:
        js = f.read()

    # No direct Stripe payment URLs in presentation artifacts
    assert "buy.stripe.com" not in html, "Direct Stripe payment links must not exist in embed HTML"
    assert "buy.stripe.com" not in js, "Direct Stripe payment links must not exist in Velo JS"

    # No /members Wix page acquisition route
    assert "/members" not in html, "Pass acquisition must not route to /members in embed HTML"
    assert "/members" not in js, "Pass acquisition must not route to /members in Velo JS"

def test_velo_page_code_contract():
    with open(VELO_JS_PATH, "r", encoding="utf-8") as f:
        js = f.read()

    # Must import required Wix modules
    assert "import wixData from 'wix-data';" in js
    assert "import wixLocation from 'wix-location';" in js
    assert "import wixWindow from 'wix-window';" in js

    # Collection ID
    assert "wnb-membership-presentation" in js
    assert "displayOrder" in js

    # Approved domain validation
    assert "cccultivate.com" in js

    # PostMessage handlers
    assert "WNB_EMBED_READY" in js
    assert "WNB_MEMBERSHIP_CTA" in js
    assert "WNB_MEMBERSHIP_DATA" in js

    # Broken openLightbox('Budly') call must NOT be actively invoked
    assert "wixWindow.openLightbox('Budly')" not in js
    assert 'wixWindow.openLightbox("Budly")' not in js

    # Dynamic element resolution
    assert "getHtmlElement" in js
