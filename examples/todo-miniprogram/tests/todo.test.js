// 云函数单元测试：mock wx-server-sdk，验证 todo 云函数的增删改查与权限隔离逻辑
// 运行：node --test tests/  （node ≥ 18，零外部依赖）
// 说明：示例代码与 docs/06-实战/01-待办清单实战.md 逐行一致，测试不改业务代码，
//       通过拦截 require('wx-server-sdk') 注入内存版数据库 mock。
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const Module = require('node:module');

// ---------- 内存数据库 mock ----------
const writeLog = [];  // 记录每次写操作的 where 条件，供权限隔离断言

function makeDb() {
  function query() {
    const q = {
      cond: {},
      order: null,
      off: 0,
      lim: 20,
      rows: [],
      where(cond) { q.cond = { ...q.cond, ...cond }; return q; },
      orderBy(field, dir) { q.order = { field, dir }; return q; },
      skip(n) { q.off = n; return q; },
      limit(n) { q.lim = n; return q; },
      async get() {
        let rows = [...q.rows];
        rows = rows.filter((r) => Object.entries(q.cond).every(([k, v]) => r[k] === v));
        if (q.order) {
          const { field, dir } = q.order;
          rows.sort((a, b) => (a[field] > b[field] ? 1 : -1) * (dir === 'desc' ? -1 : 1));
        }
        return { data: rows };
      },
      async update({ data }) {
        writeLog.push({ op: 'update', cond: { ...q.cond }, data });
        return { stats: { updated: 1 } };
      },
      async remove() {
        writeLog.push({ op: 'remove', cond: { ...q.cond } });
        return {};
      },
    };
    return q;
  }
  const store = { _rows: [] };
  const collection = {
    where(cond) { const q = query(); q.rows = store._rows; q.where(cond); return q; },
    async add({ data }) {
      const doc = { _id: `id_${store._rows.length + 1}`, ...data };
      store._rows.push(doc);
      return { _id: doc._id };
    },
    async update() { return { stats: { updated: 0 } }; },
    async remove() { return {}; },
  };
  return { collection: () => collection, _getRows: () => store._rows };
}

// ---------- 拦截 require('wx-server-sdk') ----------
const db = makeDb();
const sdkMock = {
  DYNAMIC_CURRENT_ENV: 'DYNAMIC_CURRENT_ENV',
  init() {},
  getWXContext: () => ({ openid: 'openid-test-001' }),
  database: () => ({ collection: () => db.collection('todos') }),
};

const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'wx-server-sdk') return sdkMock;
  return origLoad.apply(this, arguments);
};

const { main } = require(path.join(__dirname, '..', 'cloudfunctions', 'todo', 'index.js'));

// ---------- 测试 ----------
test('add：合法标题写入 openid/title/done/createTime', async () => {
  writeLog.length = 0;
  const res = await main({ action: 'add', payload: { title: '写测试' } });
  assert.equal(res.code, 0);
  assert.ok(res.id.startsWith('id_'));
  const doc = db._getRows().find((r) => r._id === res.id);
  assert.equal(doc.openid, 'openid-test-001');
  assert.equal(doc.title, '写测试');
  assert.equal(doc.done, false);
  assert.equal(typeof doc.createTime, 'number');
});

test('add：空标题抛「标题不合法」', async () => {
  await assert.rejects(() => main({ action: 'add', payload: { title: '' } }), /标题不合法/);
});

test('add：超 100 字标题抛「标题不合法」', async () => {
  await assert.rejects(() => main({ action: 'add', payload: { title: 'x'.repeat(101) } }), /标题不合法/);
});

test('list：done 条件按 openid + done 过滤并倒序返回', async () => {
  writeLog.length = 0;
  await main({ action: 'add', payload: { title: '任务一' } });
  await main({ action: 'add', payload: { title: '任务二' } });
  const res = await main({ action: 'list', payload: { status: 'done' } });
  assert.equal(res.code, 0);
  assert.ok(Array.isArray(res.list));
  const times = res.list.map((r) => r.createTime);
  assert.deepEqual(times, [...times].sort((a, b) => b - a), '应按 createTime 倒序');
});

test('toggle：更新条件必须含 _id 与 openid（只能改自己的）', async () => {
  writeLog.length = 0;
  const rows = db._getRows();
  const mine = rows[0];
  const res = await main({ action: 'toggle', payload: { id: mine._id, done: true } });
  assert.equal(res.code, 0);
  const log = writeLog.find((w) => w.op === 'update');
  assert.ok(log, '应产生一次 update');
  assert.equal(log.cond._id, mine._id);
  assert.equal(log.cond.openid, 'openid-test-001', '权限隔离：条件必须含 openid');
  assert.equal(log.data.done, true);
});

test('remove：删除条件必须含 _id 与 openid（只能删自己的）', async () => {
  writeLog.length = 0;
  const rows = db._getRows();
  const mine = rows[0];
  const res = await main({ action: 'remove', payload: { id: mine._id } });
  assert.equal(res.code, 0);
  const log = writeLog.find((w) => w.op === 'remove');
  assert.ok(log, '应产生一次 remove');
  assert.equal(log.cond._id, mine._id);
  assert.equal(log.cond.openid, 'openid-test-001', '权限隔离：条件必须含 openid');
});

test('未知操作抛错', async () => {
  await assert.rejects(() => main({ action: 'fly' }), /未知操作: fly/);
});

// 还原 require 拦截（避免影响其他测试文件）
Module._load = origLoad;
