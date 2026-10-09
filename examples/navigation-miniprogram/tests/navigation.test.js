const { describe, it } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');

describe('navigation-miniprogram', () => {
  it('app.json has tabBar with 3 tabs', () => {
    const cfg = JSON.parse(fs.readFileSync(path.join(ROOT, 'app.json'), 'utf8'));
    assert.strictEqual(cfg.tabBar.list.length, 3);
    assert.deepStrictEqual(
      cfg.tabBar.list.map(t => t.text),
      ['首页', '分类', '我的']
    );
  });

  it('all declared pages exist on disk', () => {
    const cfg = JSON.parse(fs.readFileSync(path.join(ROOT, 'app.json'), 'utf8'));
    for (const p of cfg.pages) {
      const dir = path.join(ROOT, p);
      assert.ok(fs.existsSync(dir + '.js'), `${p}.js missing`);
      assert.ok(fs.existsSync(dir + '.wxml'), `${p}.wxml missing`);
    }
  });

  it('detail page reads URL params in onLoad', () => {
    const src = fs.readFileSync(path.join(ROOT, 'pages/detail/detail.js'), 'utf8');
    assert.match(src, /onLoad\(options\)/);
    assert.match(src, /options\.id/);
  });
});
