import sys
import glob
import os
import pytest
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

def test_viewport_overflow():
    html_files = sorted(glob.glob(os.path.join(FIXTURES_DIR, "*.html")))
    total_checks = 0
    violations = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        
        for w, h in VIEWPORTS:
            context = browser.new_context(viewport={"width": w, "height": h})
            page = context.new_page()
            
            for f in html_files:
                fname = os.path.basename(f)
                file_url = f"file:///{os.path.abspath(f).replace(os.sep, '/')}"
                page.goto(file_url, wait_until="domcontentloaded")
                
                res = page.evaluate("""() => {
                    return {
                        scrollWidth: document.documentElement.scrollWidth,
                        docWidth: document.documentElement.clientWidth,
                        bodyScrollWidth: document.body.scrollWidth,
                        bodyWidth: document.body.clientWidth
                    }
                }""")
                
                total_checks += 1
                if res['scrollWidth'] > res['docWidth'] or res['bodyScrollWidth'] > res['bodyWidth']:
                    violations.append({
                        "file": fname,
                        "viewport": f"{w}x{h}",
                        "docScroll": res['scrollWidth'],
                        "docClient": res['docWidth'],
                        "bodyScroll": res['bodyScrollWidth'],
                        "bodyClient": res['bodyWidth']
                    })
            context.close()
        browser.close()

    assert len(violations) == 0, f"{len(violations)} viewport overflow violations: {violations}"

if __name__ == "__main__":
    test_viewport_overflow()
