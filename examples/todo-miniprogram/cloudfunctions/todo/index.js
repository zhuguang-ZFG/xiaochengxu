// cloudfunctions/todo/index.js
// 云函数 todo：所有待办增删改查的统一入口（对应 docs/06-实战/01-待办清单实战.md）
const crypto = require('crypto');
const cloud = require('wx-server-sdk');
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });
const db = cloud.database();
const todos = db.collection('todos');

function checkTitle(title) {
  if (typeof title !== 'string') throw new Error('标题不合法');
  const value = title.trim();
  if (!value || value.length > 100) throw new Error('标题不合法');
  return value;
}

function checkToken(clientToken) {
  if (typeof clientToken !== 'string' || !clientToken || clientToken.length > 64) {
    throw new Error('幂等键不合法');
  }
  return clientToken;
}

function checkId(id) {
  if (typeof id !== 'string' || !id) throw new Error('待办 ID 不合法');
  return id;
}

function todoId(openid, clientToken) {
  return 'todo_' + crypto.createHash('sha256')
    .update(openid + '\n' + clientToken)
    .digest('hex')
    .slice(0, 24);
}

exports.main = async (event = {}) => {
  const { action, payload = {} } = event;
  const { OPENID } = cloud.getWXContext();   // 身份由微信注入，payload 里的 openid 不可信
  if (!OPENID) throw new Error('缺少用户身份');

  const log = cloud.logger();
  const openidHash = crypto.createHash('sha256').update(OPENID).digest('hex').slice(0, 12);

  switch (action) {
    case 'list': {
      const { status, page = 1, size = 20 } = payload;
      const where = { openid: OPENID };
      if (status !== 'all') where.done = status === 'done';
      const res = await todos
        .where(where)
        .orderBy('createTime', 'desc')
        .skip((page - 1) * size)
        .limit(size)
        .get();
      return { code: 0, list: res.data };
    }
    case 'add': {
      const title = checkTitle(payload.title);
      const clientToken = checkToken(payload.clientToken);
      const id = todoId(OPENID, clientToken);
      try {
        await todos.add({
          data: { _id: id, openid: OPENID, clientToken, title, done: false, createTime: Date.now() }
        });
        log.info({ event: 'todo.add', action, openidHash, id, duplicated: false });
        return { code: 0, id };
      } catch (err) {
        const res = await todos.where({ _id: id, openid: OPENID }).limit(1).get();
        if (res.data.length === 0) throw err;
        log.info({ event: 'todo.add', action, openidHash, id, duplicated: true });
        return { code: 0, id, duplicated: true };
      }
    }
    case 'toggle': {
      const id = checkId(payload.id);
      const res = await todos.where({ _id: id, openid: OPENID }).update({
        data: { done: !!payload.done }
      });
      log.info({ event: 'todo.toggle', action, openidHash, id, updated: res.stats.updated });
      return { code: 0, updated: res.stats.updated };
    }
    case 'remove': {
      const id = checkId(payload.id);
      const res = await todos.where({ _id: id, openid: OPENID }).remove();  // 只能删自己的
      log.info({ event: 'todo.remove', action, openidHash, id, removed: res.stats.removed });
      return { code: 0 };
    }
    default:
      log.warn({ event: 'todo.unknown', openidHash, action: String(action).slice(0, 64) });
      throw new Error(`未知操作: ${action}`);
  }
};
