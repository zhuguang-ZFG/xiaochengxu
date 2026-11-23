// 云函数单元测试：mock wx-server-sdk，验证 todo 云函数的增删改查、身份、幂等与日志
// 运行：node --test "tests/*.test.js"  （node ≥ 18，零外部依赖）
// 说明：示例代码与 docs/06-实战/01-待办清单实战.md 逐行一致，测试不改业务代码，
//       通过拦截 require('wx-server-sdk') 注入内存版数据库 mock。
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const Module = require('node:module');

const DEFAULT_OPENID = 'openid-test-001';
const writeLog = [];  // 记录每次写操作的 where 条件，供权限隔离断言

// ---------- 内存数据库 mock ----------
function makeDb() {
  const store = { rows: [] };
  let autoId = 0;
  const matches = (row, cond) => Object.entries(cond).every(([k, v]) => row[k] === v);

  function query() {
    const q = {
      cond: {},
      order: null,
      off: 0,
      lim: 20,
      rows: store.rows,
      where(cond) { q.cond = { ...q.cond, ...cond }; return q; },
      orderBy(field, dir) { q.order = { field, dir }; return q; },
      skip(n) { q.off = n; return q; },
      limit(n) { q.lim = n; return q; },
      async get() {
        let rows = q.rows.filter((r) => matches(r, q.cond));
        if (q.order) {
          const { field, dir } = q.order;
          rows = [...rows].sort((a, b) => (a[field] > b[field] ? 1 : -1) * (dir === 'desc' ? -1 : 1));
        }
        return { data: rows.slice(q.off, q.off + q.lim).map((r) => ({ ...r })) };
      },
      async update({ data }) {
        writeLog.push({ op: 'update', cond: { ...q.cond }, data });
        let updated = 0;
        for (const row of q.rows) {
          if (matches(row, q.cond)) {
            Object.assign(row, data);
            updated += 1;
          }
        }
        return { stats: { updated } };
      },
      async remove() {
        writeLog.push({ op: 'remove', cond: { ...q.cond } });
        const before = q.rows.length;
        for (let i = q.rows.length - 1; i >= 0; i--) {
          if (matches(q.rows[i], q.cond)) q.rows.splice(i, 1);
        }
        return { stats: { removed: before - q.rows.length } };
      },
    };
    return q;
  }

  const collection = {
    where(cond) { return query().where(cond); },
    async add({ data }) {
      const doc = { ...data };
      if (!doc._id) doc._id = `id_${++autoId}`;
      if (store.rows.some((r) => r._id === doc._id)) {
        const err = new Error(`duplicate _id: ${doc._id}`);
        err.code = 'DUPLICATE_ID';
        throw err;
      }
      store.rows.push(doc);
      return { _id: doc._id };
    },
    async update() { return { stats: { updated: 0 } }; },
    async remove() { return { stats: { removed: 0 } }; },
  };

  return {
    collection: () => collection,
    rows: () => store.rows,
    reset() { store.rows.length = 0; autoId = 0; },
  };
}

// ---------- 拦截 require('wx-server-sdk') ----------
const db = makeDb();
const state = { openid: DEFAULT_OPENID, logs: [] };
const sdkMock = {
  DYNAMIC_CURRENT_ENV: 'DYNAMIC_CURRENT_ENV',
  init() {},
  getWXContext: () => ({ OPENID: state.openid }),
  database: () => ({ collection: () => db.collection('todos') }),
  logger: () => ({
    log: (entry) => state.logs.push({ level: 'log', ...entry }),
    info: (entry) => state.logs.push({ level: 'info', ...entry }),
    warn: (entry) => state.logs.push({ level: 'warn', ...entry }),
    error: (entry) => state.logs.push({ level: 'error', ...entry }),
  }),
  setOpenid(value) { state.openid = value; },
  logs: () => state.logs,
  reset() { state.openid = DEFAULT_OPENID; state.logs.length = 0; },
};

const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === 'wx-server-sdk') return sdkMock;
  return origLoad.apply(this, arguments);
};
const { main } = require(path.join(__dirname, '..', 'cloudfunctions', 'todo', 'index.js'));
Module._load = origLoad;

// ---------- 测试 ----------
test.beforeEach(() => {
  db.reset();
  sdkMock.reset();
  writeLog.length = 0;
});

function add(title = '任务', token = 'token-add-1', extra = {}) {
  return main({ action: 'add', payload: { title, clientToken: token, ...extra } });
}

test('add：合法标题写入服务端身份、幂等键与初始状态', async () => {
  const res = await add('写测试', 'token-add-1');
  assert.equal(res.code, 0);
  const doc = db.rows().find((r) => r._id === res.id);
  assert.equal(doc.openid, DEFAULT_OPENID);
  assert.equal(doc.clientToken, 'token-add-1');
  assert.equal(doc.title, '写测试');
  assert.equal(doc.done, false);
  assert.equal(typeof doc.createTime, 'number');
});

test('add：服务端 trim 标题后再写入', async () => {
  const res = await add('  写测试  ', 'token-trim-1');
  const doc = db.rows().find((r) => r._id === res.id);
  assert.equal(doc.title, '写测试');
});

test('add：忽略 payload 中伪造的 openid', async () => {
  const res = await add('伪造身份', 'token-forge-1', { openid: 'openid-attacker' });
  const doc = db.rows().find((r) => r._id === res.id);
  assert.equal(doc.openid, DEFAULT_OPENID, '归属字段只能来自 getWXContext().OPENID');
  const list = await main({ action: 'list', payload: { status: 'all', openid: 'openid-attacker' } });
  assert.ok(list.list.every((r) => r.openid === DEFAULT_OPENID));
});

test('add：空标题、超长标题、非字符串标题都抛「标题不合法」', async () => {
  for (const title of ['', '   ', 'x'.repeat(101), 123, {}, [], null, undefined]) {
    await assert.rejects(
      () => main({ action: 'add', payload: { title, clientToken: 'token-bad-title' } }),
      /标题不合法/
    );
  }
});

test('add：clientToken 缺失或格式非法时拒绝', async () => {
  await assert.rejects(() => main({ action: 'add', payload: { title: '任务' } }), /幂等键不合法/);
  for (const clientToken of ['', 123, null, 'x'.repeat(65)]) {
    await assert.rejects(() => main({ action: 'add', payload: { title: '任务', clientToken } }), /幂等键不合法/);
  }
});

test('add：同一用户同一 clientToken 重复提交只写一条并返回同一 id', async () => {
  const first = await add('网络抖动', 'token-dup-1');
  const second = await add('网络抖动', 'token-dup-1');
  assert.equal(first.id, second.id);
  assert.notEqual(first.duplicated, true);
  assert.equal(second.duplicated, true);
  assert.equal(db.rows().filter((r) => r.clientToken === 'token-dup-1').length, 1);
});

test('add：幂等重试不会覆盖第一次写入的内容', async () => {
  const first = await add('第一次内容', 'token-dup-2');
  const second = await add('第二次内容', 'token-dup-2');
  assert.equal(second.id, first.id);
  assert.equal(db.rows().find((r) => r._id === first.id).title, '第一次内容');
});

test('add：不同用户使用相同 clientToken 会得到不同记录', async () => {
  const mine = await add('A 的任务', 'token-shared');
  sdkMock.setOpenid('openid-test-002');
  const other = await add('B 的任务', 'token-shared');
  assert.notEqual(other.id, mine.id);
  assert.equal(db.rows().length, 2);
});

test('list：只返回当前用户的待办，忽略伪造的 openid 参数', async () => {
  await add('A 的任务', 'token-list-a');
  sdkMock.setOpenid('openid-test-002');
  await add('B 的任务', 'token-list-b');
  const resB = await main({ action: 'list', payload: { status: 'all', openid: DEFAULT_OPENID } });
  assert.deepEqual(resB.list.map((r) => r.title), ['B 的任务']);
  sdkMock.setOpenid(DEFAULT_OPENID);
  const resA = await main({ action: 'list', payload: { status: 'all', openid: 'openid-test-002' } });
  assert.deepEqual(resA.list.map((r) => r.title), ['A 的任务']);
});

test('list：done 条件按当前用户 + done 过滤并倒序返回', async () => {
  const first = await add('任务一', 'token-done-1');
  await add('任务二', 'token-done-2');
  await main({ action: 'toggle', payload: { id: first.id, done: true } });
  const res = await main({ action: 'list', payload: { status: 'done' } });
  assert.deepEqual(res.list.map((r) => r.title), ['任务一']);
  const times = res.list.map((r) => r.createTime);
  assert.deepEqual(times, [...times].sort((a, b) => b - a), '应按 createTime 倒序');
});

test('toggle：只能修改自己的待办', async () => {
  const mine = await add('A 的任务', 'token-toggle-a');
  sdkMock.setOpenid('openid-test-002');
  const denied = await main({ action: 'toggle', payload: { id: mine.id, done: true } });
  assert.equal(denied.updated, 0);
  assert.equal(db.rows().find((r) => r._id === mine.id).done, false);
  assert.equal(writeLog.find((w) => w.op === 'update').cond.openid, 'openid-test-002');

  sdkMock.setOpenid(DEFAULT_OPENID);
  const allowed = await main({ action: 'toggle', payload: { id: mine.id, done: true } });
  assert.equal(allowed.updated, 1);
  assert.equal(db.rows().find((r) => r._id === mine.id).done, true);
});

test('remove：只能删除自己的待办', async () => {
  const mine = await add('A 的任务', 'token-remove-a');
  sdkMock.setOpenid('openid-test-002');
  await main({ action: 'remove', payload: { id: mine.id } });
  assert.ok(db.rows().some((r) => r._id === mine.id), 'B 不能删除 A 的记录');
  assert.equal(writeLog.find((w) => w.op === 'remove').cond.openid, 'openid-test-002');

  sdkMock.setOpenid(DEFAULT_OPENID);
  await main({ action: 'remove', payload: { id: mine.id } });
  assert.equal(db.rows().some((r) => r._id === mine.id), false);
});

test('身份缺失：没有 OPENID 时拒绝服务', async () => {
  sdkMock.setOpenid(null);
  await assert.rejects(() => main({ action: 'list', payload: { status: 'all' } }), /缺少用户身份/);
  await assert.rejects(() => add('任务', 'token-no-openid'), /缺少用户身份/);
});

test('日志：记录可检索字段，且不落明文 openid、标题与幂等键', async () => {
  const res = await add('写测试', 'token-log-1');
  const entry = sdkMock.logs().find((e) => e.event === 'todo.add');
  assert.ok(entry, 'add 应写一条结构化日志');
  assert.equal(entry.level, 'info');
  assert.equal(entry.action, 'add');
  assert.match(entry.openidHash, /^[0-9a-f]{12}$/);
  assert.equal(entry.id, res.id);
  assert.equal(entry.duplicated, false);
  const raw = JSON.stringify(entry);
  assert.equal(raw.includes(DEFAULT_OPENID), false, '日志不能含明文 openid');
  assert.equal(raw.includes('写测试'), false, '日志不能含用户标题');
  assert.equal(raw.includes('token-log-1'), false, '日志不能含幂等键');
});

test('未知操作抛错并记 warn 日志', async () => {
  await assert.rejects(() => main({ action: 'fly' }), /未知操作: fly/);
  const entry = sdkMock.logs().find((e) => e.event === 'todo.unknown');
  assert.ok(entry);
  assert.equal(entry.level, 'warn');
  assert.match(entry.openidHash, /^[0-9a-f]{12}$/);
});
