import wixData from 'wix-data';
import wixLocation from 'wix-location';
import wixWindow from 'wix-window';

// Configuration
const CMS_COLLECTION_ID = 'wnb-membership-presentation';
const APPROVED_DOMAIN = 'cccultivate.com';
const BUDLY_LIGHTBOX_NAME = 'Budly'; // Canonical lightbox name if installed

let cachedMemberships = null;

$w.onReady(async function () {
    // 1. Set up postMessage listener for the HTML embed
    setupHtmlEmbedBridge();

    // 2. Load CMS data and push to embed
    await loadAndSendMembershipData();
});

/**
 * Resolve HTML embed element dynamically by standard or canvas component ID
 */
function getHtmlElement() {
    try {
        const el = $w('#html1');
        if (el && typeof el.onMessage === 'function') return el;
    } catch (e) {}
    try {
        const el = $w('#comp-mr43y0jf');
        if (el && typeof el.onMessage === 'function') return el;
    } catch (e) {}
    return null;
}

/**
 * Configure bidirectional communication with the HTML iframe embed
 */
function setupHtmlEmbedBridge() {
    const htmlElement = getHtmlElement();
    if (!htmlElement) {
        console.error('[WnB Membership] HTML embed component (#html1 / #comp-mr43y0jf) not found on page.');
        return;
    }

    htmlElement.onMessage((event) => {
        const data = event.data;
        if (!data || typeof data !== 'object') return;

        switch (data.type) {
            case 'WNB_EMBED_READY':
                // The iframe is ready, send cached data or fetch fresh
                if (cachedMemberships) {
                    sendDataToEmbed(cachedMemberships);
                } else {
                    loadAndSendMembershipData();
                }
                break;

            case 'WNB_MEMBERSHIP_CTA':
                handleCtaAction(data.url);
                break;

            case 'WNB_ASK_BUDLY':
                handleAskBudlyAction();
                break;

            default:
                console.warn('[WnB Membership] Unknown message type:', data.type);
                break;
        }
    });
}

/**
 * Query Wix CMS wnb-membership-presentation and send records to iframe
 */
async function loadAndSendMembershipData() {
    try {
        const results = await wixData.query(CMS_COLLECTION_ID)
            .ascending('displayOrder')
            .find();

        if (results.items && results.items.length > 0) {
            cachedMemberships = results.items.map(item => ({
                tierKey: item.tierKey || item._id,
                name: item.name || '',
                priceDisplay: item.priceDisplay || '',
                billingDisplay: item.billingDisplay || '',
                statusLabel: item.statusLabel || '',
                description: item.description || '',
                benefits: item.benefits || '',
                ctaLabel: item.ctaLabel || '',
                ctaUrl: item.ctaUrl || '',
                ctaState: item.ctaState || '',
                displayOrder: typeof item.displayOrder === 'number' ? item.displayOrder : 0
            }));

            sendDataToEmbed(cachedMemberships);
        } else {
            console.warn(`[WnB Membership] No items found in collection ${CMS_COLLECTION_ID}`);
        }
    } catch (error) {
        console.error(`[WnB Membership] Error loading ${CMS_COLLECTION_ID}:`, error);
    }
}

/**
 * Send membership data payload to the HTML embed
 */
function sendDataToEmbed(memberships) {
    const htmlElement = getHtmlElement();
    if (!htmlElement) return;

    htmlElement.postMessage({
        type: 'WNB_MEMBERSHIP_DATA',
        memberships: memberships
    });
}

/**
 * Validate and navigate to approved WordPress / WooCommerce checkout URL
 */
function handleCtaAction(rawUrl) {
    if (!rawUrl || typeof rawUrl !== 'string') {
        console.error('[WnB Membership] Invalid CTA URL provided');
        return;
    }

    try {
        const urlObj = new URL(rawUrl);
        const host = urlObj.hostname.toLowerCase();

        // Validate destination domain
        if (host === APPROVED_DOMAIN || host.endsWith('.' + APPROVED_DOMAIN)) {
            wixLocation.to(rawUrl);
        } else {
            console.error(`[WnB Membership] Unauthorized CTA domain: ${host}`);
        }
    } catch (e) {
        console.error('[WnB Membership] Malformed URL:', rawUrl, e);
    }
}

/**
 * Handle Budly assistance action (Pending approved Wix-to-Budly mechanism configuration)
 */
function handleAskBudlyAction() {
    console.log('[WnB Membership] Ask Budly CTA action received (Budly mechanism pending configuration).');
}
