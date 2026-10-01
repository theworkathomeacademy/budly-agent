import urllib.request
import ssl
import json
import subprocess

def verify_g6():
    ctx = ssl.create_default_context()
    headers = {'User-Agent': 'Mozilla/5.0'}

    print("====================================================")
    print("AFF-001 PHASE G - G6 FINAL CONTAINMENT VERIFICATION")
    print("====================================================")

    # 1. Ask Budly Live Page
    print("\n1. Checking Ask Budly Live Page...")
    try:
        req = urllib.request.Request('https://cccultivate.com/ask-budly/', headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            html = r.read().decode('utf-8', errors='ignore')
            print(f"   - HTTP Status: {r.status} (Len: {len(html)})")
            print(f"   - Budly experience present: {'budly-experience' in html}")
    except Exception as e:
        print("   - Error:", e)

    # 2. WooCommerce Store API
    print("\n2. Checking WooCommerce Store API...")
    try:
        req = urllib.request.Request('https://cccultivate.com/wp-json/wc/store/v1/products', headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            prods = json.loads(r.read().decode('utf-8'))
            print(f"   - HTTP Status: {r.status} (Products returned: {len(prods)})")
    except Exception as e:
        print("   - Error:", e)

    # 3. Check GoAffPro and SliceWP Frontend Trackers
    print("\n3. Checking Frontend Tracker Elimination...")
    for path in ['/', '/?sld=1', '/?ref=1']:
        req = urllib.request.Request('https://cccultivate.com' + path, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            body = r.read().decode('utf-8', errors='ignore')
            has_goaffpro_loader = 'api.goaffpro.com/loader.js' in body
            has_slicewp_trk = 'slicewp/assets/js/script-trk.js' in body
            has_slicewp_var = 'var slicewp =' in body
            print(f"   Path '{path}':")
            print(f"     - GoAffPro loader.js present: {has_goaffpro_loader}")
            print(f"     - SliceWP script-trk.js present: {has_slicewp_trk}")
            print(f"     - SliceWP var present: {has_slicewp_var}")

    # 4. Check GoAffPro REST Endpoint
    print("\n4. Checking GoAffPro REST Endpoint Status...")
    try:
        req = urllib.request.Request('https://cccultivate.com/wp-json/goaffpro/config', headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            print(f"   - GoAffPro REST config HTTP Status: {r.status}")
    except urllib.error.HTTPError as e:
        print(f"   - GoAffPro REST config HTTP Status: {e.code} (Plugin deactivated)")
    except Exception as e:
        print("   - Error:", e)

    # 5. Check n8n Revenue Spine and AFF Workflow States
    print("\n5. Checking n8n Revenue Spine and Workflow States...")
    sql = "SELECT id, name, active FROM workflow_entity ORDER BY id;"
    cmd = ['docker', 'exec', 'bros-n8n-development-postgres-1', 'psql', '-U', 'n8n', '-d', 'n8n', '-c', sql]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)

    # 6. Check executions count in n8n
    print("\n6. Checking n8n Execution Count...")
    sql_exec = "SELECT count(*) FROM execution_entity;"
    cmd_exec = ['docker', 'exec', 'bros-n8n-development-postgres-1', 'psql', '-U', 'n8n', '-d', 'n8n', '-c', sql_exec]
    res_exec = subprocess.run(cmd_exec, capture_output=True, text=True)
    print(res_exec.stdout)

if __name__ == '__main__':
    verify_g6()
