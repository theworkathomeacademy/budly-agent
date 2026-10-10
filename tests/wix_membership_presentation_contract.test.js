const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(
  path.join(root, 'deploy', 'wix', 'wnb-membership-presentation-embed.html'),
  'utf8'
);
const velo = fs.readFileSync(
  path.join(root, 'deploy', 'wix', 'wnb-membership-velo-page-code.js'),
  'utf8'
);

function createClassList(initial) {
  const values = new Set(initial);
  return {
    add: (...names) => names.forEach((name) => values.add(name)),
    remove: (...names) => names.forEach((name) => values.delete(name)),
    has: (name) => values.has(name),
    snapshot: () => [...values].sort(),
  };
}

const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.ok(scripts.length > 0, 'embed must contain an inline script');

const classList = createClassList(['wnb-desktop']);
const messageHandlers = {};
const context = {
  console,
  URL,
  document: {
    body: { classList },
    getElementById: () => null,
  },
  window: {
    addEventListener: (type, handler) => { messageHandlers[type] = handler; },
    parent: { postMessage: () => {} },
  },
};

vm.createContext(context);
vm.runInContext(scripts.at(-1)[1], context);

for (const mode of ['desktop', 'tablet', 'mobile']) {
  vm.runInContext(`applyLayoutMode('${mode}')`, context);
  assert.deepEqual(classList.snapshot(), [`wnb-${mode}`], `${mode} mode must be applied exactly`);
}

vm.runInContext("applyLayoutMode('unsupported')", context);
assert.deepEqual(classList.snapshot(), ['wnb-mobile'], 'invalid mode must be ignored');

vm.runInContext("applyLayoutMode('desktop')", context);
assert.deepEqual(classList.snapshot(), ['wnb-desktop'], 'missing-message default must remain desktop');

assert.match(velo, /import \{ window as siteWindow \} from '@wix\/site-window';/);
assert.match(velo, /siteWindow\.getBoundingRect\(\)/);
assert.match(velo, /width <= 480/);
assert.match(velo, /width <= 900/);
assert.match(velo, /defaulting to desktop/);
assert.match(velo, /if \(width <= 480\) return 'mobile';/);
assert.match(velo, /if \(width <= 900\) return 'tablet';/);
assert.match(velo, /return 'desktop';/);
assert.match(velo, /type: LAYOUT_MESSAGE_TYPE,[\s\S]*mode: mode/);

const combined = `${html}\n${velo}`;
assert.doesNotMatch(combined, /buy\.stripe\.com/);
assert.doesNotMatch(combined, /\/members/);
assert.doesNotMatch(combined, /openLightbox\s*\(\s*['"]Budly['"]\s*\)/);
assert.match(velo, /cccultivate\.com/);
assert.match(html, /WNB_MEMBERSHIP_DATA/);
assert.match(html, /WNB_MEMBERSHIP_CTA/);

console.log('Wix membership layout contract: 3 modes and regression checks passed.');
