const { describe, it } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');

describe('product-list-miniprogram', () => {
  it('app.json declares list and detail pages', () => {
    const cfg = JSON.parse(fs.readFileSync(path.join(ROOT, 'app.json'), 'utf8'));
    assert.deepStrictEqual(cfg.pages, ['pages/list/list', 'pages/detail/detail']);
  });

  it('all declared pages exist on disk', () => {
    const cfg = JSON.parse(fs.readFileSync(path.join(ROOT, 'app.json'), 'utf8'));
    for (const p of cfg.pages) {
      const dir = path.join(ROOT, p);
      assert.ok(fs.existsSync(dir + '.js'), `${p}.js missing`);
      assert.ok(fs.existsSync(dir + '.wxml'), `${p}.wxml missing`);
    }
  });

  it('list page uses wx:for with wx:key', () => {
    const src = fs.readFileSync(path.join(ROOT, 'pages/list/list.wxml'), 'utf8');
    assert.match(src, /wx:for=/);
    assert.match(src, /wx:key=/);
  });

  it('list page uses scroll-view', () => {
    const src = fs.readFileSync(path.join(ROOT, 'pages/list/list.wxml'), 'utf8');
    assert.match(src, /scroll-view/);
  });

  it('search filters products by keyword', () => {
    const src = fs.readFileSync(path.join(ROOT, 'pages/list/list.js'), 'utf8');
    assert.match(src, /onSearch/);
    assert.match(src, /\.filter/);
  });
});
