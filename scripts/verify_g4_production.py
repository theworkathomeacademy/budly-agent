import urllib.request
import re
import ssl
import json
import time

def safe_fetch(url, headers, ctx, retries=3, delay=2):
    time.sleep(delay)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                return resp.status, resp.read().decode('utf-8'), None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"  [429 Rate limited on {url}, backing off 10s... (attempt {attempt+1}/{retries})]")
                time.sleep(10)
                continue
            return e.code, None, e.read().decode('utf-8')
        except Exception as e:
            return None, None, str(e)
    return 429, None, "Rate limit exceeded after retries"

def verify_g4_production():
    ctx = ssl.create_default_context()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    print("====================================================")
    print("AFF-001 PHASE G - G4 LIVE PRODUCTION VERIFICATION")
    print("====================================================")

    # 1. Ask Budly Live Page Check
    print("\n1. Checking Ask Budly Live Page...")
    status, html, err = safe_fetch('https://cccultivate.com/ask-budly/', headers, ctx)
    print(f"   - HTTP Status: {status}")
    if status == 200 and html:
        print(f"   - Has 'budly-experience': {'budly-experience' in html}")
        print(f"   - Has 'budly-chat': {'budly-chat' in html}")
        print(f"   - Has 'data-budly-sales': {'data-budly-sales' in html}")
        scripts = re.findall(r'src=["\']([^"\']*budly[^"\']*\.js(?:\?ver=[^"\']+)?)["\']', html)
        print(f"   - Budly scripts loaded: {scripts}")
        styles = re.findall(r'href=["\']([^"\']*budly[^"\']*\.css(?:\?ver=[^"\']+)?)["\']', html)
        print(f"   - Budly styles loaded: {styles}")
    else:
        print(f"   - Error/Status: {err}")

    # 2. WooCommerce Store API Check
    print("\n2. Checking WooCommerce Store API...")
    status, json_str, err = safe_fetch('https://cccultivate.com/wp-json/wc/store/v1/products?per_page=10', headers, ctx)
    print(f"   - HTTP Status: {status}")
    if status == 200 and json_str:
        products = json.loads(json_str)
        print(f"   - Products returned: {len(products)}")
        for p in products[:3]:
            print(f"     * {p.get('name')} (ID: {p.get('id')}, Price: {p.get('prices', {}).get('price')})")
    else:
        print(f"   - Error: {err}")

    # 3. Budly Runtime API
    print("\n3. Checking Budly Runtime API...")
    status, json_str, err = safe_fetch('https://cccultivate.com/wp-json/budly-runtime/v1', headers, ctx)
    print(f"   - HTTP Status: {status}")
    if status == 200 and json_str:
        rt_info = json.loads(json_str)
        print(f"   - Runtime Routes: {list(rt_info.get('routes', {}).keys())}")
    else:
        print(f"   - Error: {err}")

    # 4. Budly Identity API
    print("\n4. Checking Budly Identity API...")
    status, json_str, err = safe_fetch('https://cccultivate.com/wp-json/budly-identity/v1', headers, ctx)
    print(f"   - HTTP Status: {status}")
    if status == 200 and json_str:
        id_info = json.loads(json_str)
        print(f"   - Total Routes: {len(id_info.get('routes', {}))}")
    else:
        print(f"   - Error: {err}")

    # 5. Admin Surface Protection Check
    print("\n5. Checking Admin Surface Protection...")
    status, body, err = safe_fetch('https://cccultivate.com/wp-json/budly-identity/v1/admin/health', headers, ctx)
    print(f"   - HTTP Status: {status} (Expected: 403 Forbidden)")
    if status == 403:
        print(f"   - Correctly protected: {err[:150] if err else 'Forbidden'}")
    else:
        print(f"   - Response: {body or err}")

    # 6. Affiliate Portal / Shortcode Gate Test
    print("\n6. Checking Affiliate Portal Route...")
    status, html, err = safe_fetch('https://cccultivate.com/affiliate-portal/', headers, ctx)
    print(f"   - HTTP Status: {status} (Expected: 404 Not Found / No public portal exposed)")
    if status == 404:
        print("   - Portal route fails closed as expected")
    elif status == 200 and html:
        print(f"   - Portal output contains 'Affiliate Portal': {'Affiliate Portal' in html}")

    # 7. Customer Policies Check
    print("\n7. Checking Customer Policies Page...")
    status, html, err = safe_fetch('https://cccultivate.com/customer-policies/', headers, ctx)
    print(f"   - HTTP Status: {status}")
    if status == 200 and html:
        print(f"   - Has NFT membership policy: {'NFT memberships' in html}")
        print(f"   - Has July 17, 2026 date: {'July 17, 2026' in html}")

    print("\n====================================================")
    print("ALL LIVE HTTP / REST PROBES COMPLETE")
    print("====================================================")

if __name__ == '__main__':
    verify_g4_production()
