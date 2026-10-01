import urllib.request
import ssl
import re
import json

def check_legacy():
    ctx = ssl.create_default_context()
    headers = {'User-Agent': 'Mozilla/5.0'}

    print("================================================")
    print("AFF-001 PHASE G - G6 LEGACY AFFILIATE AUDIT")
    print("================================================")

    # 1. Check Goaffpro REST configuration
    print("\n1. Goaffpro REST Config:")
    try:
        req = urllib.request.Request('https://cccultivate.com/wp-json/goaffpro/config', headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            data = json.loads(r.read().decode('utf-8'))
            print("   - Store Name:", data.get('store_name'))
            print("   - Public Token:", data.get('goaffpro_public_token'))
            print("   - Plugin Version:", data.get('plugin_version'))
    except Exception as e:
        print("   - Error fetching Goaffpro config:", e)

    # 2. Check HTML script sources on live pages
    print("\n2. Checking Page Assets & Legacy Affiliate Scripts:")
    for path in ['/', '/?sld=1', '/?ref=1']:
        req = urllib.request.Request('https://cccultivate.com' + path, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            html = r.read().decode('utf-8', errors='ignore')
            
            goaffpro_scripts = re.findall(r'src=["\']([^"\']*goaffpro[^"\']*)["\']', html)
            slicewp_scripts = re.findall(r'src=["\']([^"\']*slicewp[^"\']*)["\']', html)
            
            print(f"\n   Path '{path}' (Status: {r.status}):")
            print("     - Goaffpro scripts:", goaffpro_scripts)
            print("     - SliceWP scripts:", slicewp_scripts)
            
            # Check for tracking inline variables
            has_goaffpro_loader = 'api.goaffpro.com/loader.js' in html
            has_slicewp_js = 'slicewp' in html.lower()
            print("     - Has Goaffpro loader.js:", has_goaffpro_loader)
            print("     - Has SliceWP markup/script:", has_slicewp_js)

if __name__ == '__main__':
    check_legacy()
