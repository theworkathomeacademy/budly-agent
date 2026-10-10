import { chromium } from 'file:///C:/Users/19196/AppData/Local/OpenAI/Codex/runtimes/cua_node/2c9e75c4e9c71beb/bin/node_modules/playwright/index.mjs';
import * as fs from 'fs';
import * as path from 'path';

const tempHtmlPath = path.resolve('tests/test_account_responsive.html');
if (!fs.existsSync(tempHtmlPath)) {
    console.error('Error: test_account_responsive.html does not exist!');
    process.exit(1);
}

const viewports = [
    { name: '1440px Desktop', width: 1440, height: 900 },
    { name: '820px Tablet', width: 820, height: 1180 },
    { name: '390px Mobile', width: 390, height: 844 }
];

async function runResponsiveTests() {
    console.log('Launching browser for responsive verification...');
    const browser = await chromium.launch({
        executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        headless: true
    });

    const results = [];

    for (const vp of viewports) {
        const page = await browser.newPage({
            viewport: { width: vp.width, height: vp.height }
        });

        await page.goto('file:///' + tempHtmlPath.replace(/\\/g, '/'));
        await page.waitForTimeout(1000);

        const check = await page.evaluate((vpWidth) => {
            const bodyScrollWidth = document.body.scrollWidth;
            const docScrollWidth = document.documentElement.scrollWidth;
            const windowInnerWidth = window.innerWidth;
            const hasHorizontalOverflow = docScrollWidth > windowInnerWidth || bodyScrollWidth > windowInnerWidth;

            // Check all buttons
            const buttons = Array.from(document.querySelectorAll('.ccc-wnb-btn, .ccc-wnb-budly-link')).map(btn => {
                const rect = btn.getBoundingClientRect();
                return {
                    text: btn.innerText.trim(),
                    visible: rect.width > 0 && rect.height > 0,
                    width: rect.width,
                    right: rect.right,
                    fitsViewport: rect.right <= windowInnerWidth + 5 // small tolerance for scrollbar
                };
            });

            return {
                windowInnerWidth,
                docScrollWidth,
                bodyScrollWidth,
                hasHorizontalOverflow,
                buttonsCount: buttons.length,
                allButtonsVisible: buttons.every(b => b.visible),
                allButtonsFit: buttons.every(b => b.fitsViewport)
            };
        }, vp.width);

        console.log(`[${vp.name}] Inner: ${check.windowInnerWidth}px | DocScroll: ${check.docScrollWidth}px | Overflow: ${check.hasHorizontalOverflow} | Buttons: ${check.buttonsCount} (all visible: ${check.allButtonsVisible}, all fit: ${check.allButtonsFit})`);
        results.push({ viewport: vp.name, ...check });
        await page.close();
    }

    await browser.close();

    const allPassed = results.every(r => !r.hasHorizontalOverflow && r.allButtonsVisible && r.allButtonsFit);
    if (!allPassed) {
        console.error('Responsive tests failed!');
        process.exit(1);
    }
    console.log('\nALL RESPONSIVE VIEWPORT CHECKS PASSED (1440px, 820px, 390px)!');
}

runResponsiveTests().catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
});
