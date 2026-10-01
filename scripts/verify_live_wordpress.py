import urllib.request
import re
import ssl
import json

def check_live_site():
    ctx = ssl.create_default_context()
    
    # 1. Check Ask Budly Page
    req = urllib.request.Request('https://cccultivate.com/ask-budly/', headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        html = resp.read().decode('utf-8')
        print("=== ASK BUDLY LIVE PAGE ===")
        print("HTTP Status:", resp.status)
        titles = re.findall(r'<title>(.*?)</title>', html)
        print("Title:", titles[0] if titles else "None")
        scripts = re.findall(r'src=["\']([^"\']*budly[^"\']*\.js(?:\?ver=[^"\']+)?)["\']', html)
        print("Budly Scripts:", scripts)
        styles = re.findall(r'href=["\']([^"\']*budly[^"\']*\.css(?:\?ver=[^"\']+)?)["\']', html)
        print("Budly Styles:", styles)
        print("Has 'budly-experience':", 'budly-experience' in html)
        print("Has 'budly-chat':", 'budly-chat' in html)
        print("Has '[budly_affiliate_portal]':", '[budly_affiliate_portal]' in html)

    # 2. Check WooCommerce Store API
    req_store = urllib.request.Request('https://cccultivate.com/wp-json/wc/store/v1/products?per_page=10', headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req_store, context=ctx, timeout=15) as resp:
        products = json.loads(resp.read().decode('utf-8'))
        print("\n=== WOOCOMMERCE STORE API ===")
        print("Products returned:", len(products))
        for p in products[:3]:
            print(f"- {p.get('name')} (ID: {p.get('id')}, Price: {p.get('prices', {}).get('price')})")

    # 3. Check Budly Runtime API
    req_rt = urllib.request.Request('https://cccultivate.com/wp-json/budly-runtime/v1', headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req_rt, context=ctx, timeout=15) as resp:
        rt_info = json.loads(resp.read().decode('utf-8'))
        print("\n=== BUDLY RUNTIME API ===")
        print("Runtime Routes:", list(rt_info.get('routes', {}).keys()))

    # 4. Check Budly Identity API
    req_id = urllib.request.Request('https://cccultivate.com/wp-json/budly-identity/v1', headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req_id, context=ctx, timeout=15) as resp:
        id_info = json.loads(resp.read().decode('utf-8'))
        print("\n=== BUDLY IDENTITY API ===")
        print("Identity Routes Count:", len(id_info.get('routes', {})))

    # 5. Check if any Affiliate portal or admin endpoint is publicly exposed
    req_portal = urllib.request.Request('https://cccultivate.com/affiliate-portal/', headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req_portal, context=ctx, timeout=15) as resp:
            portal_html = resp.read().decode('utf-8')
            print("\n=== AFFILIATE PORTAL ROUTE ===")
            print("Status:", resp.status)
            print("Contains 'Affiliate Portal':", 'Affiliate Portal' in portal_html)
    except urllib.error.HTTPError as e:
        print("\n=== AFFILIATE PORTAL ROUTE ===")
        print("HTTP Status:", e.code, "(Protected / 404 as expected when not published)")
    except Exception as e:
        print("\n=== AFFILIATE PORTAL ROUTE ===", e)

if __name__ == '__main__':
    check_live_site()
