import sys
import glob
import os
from playwright.sync_api import sync_playwright

VIEWPORTS = [
    (320, 568),
    (375, 667),
    (390, 844),
    (430, 932),
    (820, 1180),
    (1440, 900)
]

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "html_fixtures")
html_files = sorted(glob.glob(os.path.join(FIXTURES_DIR, "*.html")))

print(f"Starting Multi-Viewport Overflow Test across {len(html_files)} fixtures and {len(VIEWPORTS)} viewports...")

total_checks = 0
violations = []

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome")
    
    for w, h in VIEWPORTS:
        print(f"\n--- Testing Viewport: {w}px x {h}px ---")
        context = browser.new_context(viewport={"width": w, "height": h})
        page = context.new_page()
        
        for fpath in html_files:
            fname = os.path.basename(fpath)
            file_url = fpath.replace("\\", "/")
            if not file_url.startswith("/"):
                file_url = "/" + file_url
            url = f"file://{file_url}"
            page.goto(url)
            page.wait_for_load_state("domcontentloaded")
            
            # Execute JS assertion inside page
            # Check documentElement scrollWidth vs clientWidth/innerWidth
            res = page.evaluate("""() => {
                const docWidth = document.documentElement.clientWidth;
                const scrollWidth = document.documentElement.scrollWidth;
                
                // Allow up to 1px rounding variance
                const hasPageOverflow = scrollWidth > docWidth + 1;
                
                // Find all elements extending beyond docWidth, excluding intentionally scrollable containers
                const overflowingElements = [];
                const allElements = document.querySelectorAll('*');
                
                for (const el of allElements) {
                    // Exclude intentionally scrollable horizontal containers
                    if (el.classList.contains('wnb-filter-bar') || 
                        el.classList.contains('wnb-nav-list') || 
                        el.closest('.wnb-filter-bar') ||
                        el.closest('.wnb-nav-list')) {
                        continue;
                    }
                    
                    const rect = el.getBoundingClientRect();
                    // Check if element's right edge exceeds docWidth + 1
                    if (rect.right > docWidth + 1) {
                        overflowingElements.push({
                            tag: el.tagName.toLowerCase(),
                            className: el.className,
                            right: Math.round(rect.right),
                            docWidth: docWidth,
                            diff: Math.round(rect.right - docWidth)
                        });
                    }
                }
                
                return {
                    docWidth,
                    scrollWidth,
                    hasPageOverflow,
                    overflowingElements: overflowingElements.slice(0, 5) // return first 5
                };
            }""")
            
            total_checks += 1
            if res["hasPageOverflow"] or len(res["overflowingElements"]) > 0:
                violations.append({
                    "viewport": f"{w}x{h}",
                    "fixture": fname,
                    "docWidth": res["docWidth"],
                    "scrollWidth": res["scrollWidth"],
                    "elements": res["overflowingElements"]
                })
                print(f"  [FAIL] {fname} at {w}px: scrollWidth={res['scrollWidth']} > docWidth={res['docWidth']}")
                for el in res["overflowingElements"]:
                    print(f"         Offending: <{el['tag']} class='{el['className']}'> right={el['right']} diff={el['diff']}px")
            else:
                print(f"  [PASS] {fname} at {w}px: Clean layout (scrollWidth={res['scrollWidth']} <= {res['docWidth']})")
                
        context.close()
    
    browser.close()

print("\n" + "=" * 60)
if len(violations) == 0:
    print(f"ALL {total_checks} VIEWPORT ASSERTIONS PASSED: ZERO HORIZONTAL OVERFLOW DETECTED")
    print("Tested 320px, 375px, 390px, 430px, 820px, and 1440px successfully.")
    print("=" * 60)
    sys.exit(0)
else:
    print(f"FAILED: {len(violations)} VIEWPORT VIOLATIONS DETECTED")
    print("=" * 60)
    sys.exit(1)
