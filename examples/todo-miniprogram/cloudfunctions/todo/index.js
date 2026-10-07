// cloudfunctions/todo/index.js
// 云函数 todo：所有待办增删改查的统一入口（对应 docs/06-实战/01-待办清单实战.md）
const cloud = require('wx-server-sdk');
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });
const db = cloud.database();
const todos = db.collection('todos');

exports.main = async (event) => {
  const { action, payload = {} } = event;
  const { openid } = cloud.getWXContext();   // 当前用户身份

  switch (action) {
    case 'list': {
      const { status, page = 1, size = 20 } = payload;
      const where = { openid };
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
      const { title } = payload;
      if (!title || title.length > 100) throw new Error('标题不合法');
      const res = await todos.add({
        data: { openid, title, done: false, createTime: Date.now() }
      });
      return { code: 0, id: res._id };
    }
    case 'toggle': {
      const { id, done } = payload;
      const res = await todos.where({ _id: id, openid }).update({
        data: { done: !!done }
      });
      return { code: 0, updated: res.stats.updated };
    }
    case 'remove': {
      const { id } = payload;
      await todos.where({ _id: id, openid }).remove();  // 只能删自己的
      return { code: 0 };
    }
    default:
      throw new Error(`未知操作: ${action}`);
  }
};
