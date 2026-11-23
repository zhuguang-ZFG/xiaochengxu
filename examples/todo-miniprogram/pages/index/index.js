// pages/index/index.js
function newClientToken() {
  return Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10);
}

Page({
  data: {
    title: '',
    status: 'all',
    list: []
  },

  onShow() {
    this.fetchList();
  },

  async fetchList() {
    const res = await this.callTodo('list', { status: this.data.status });
    this.setData({ list: res.list });
  },

  callTodo(action, payload) {
    return new Promise((resolve, reject) => {
      wx.cloud.callFunction({
        name: 'todo',
        data: { action, payload },
        success: (res) => {
          if (res.result.code === 0) resolve(res.result);
          else reject(new Error(res.result.errMsg));
        },
        fail: reject
      });
    });
  },

  onInput(e) {
    this.addToken = '';   // 输入变了，上一次未完成的提交不再复用幂等键
    this.setData({ title: e.detail.value });
  },

  async onAdd() {
    const title = this.data.title.trim();
    if (!title || this.submitting) return;
    this.submitting = true;
    this.addToken = this.addToken || newClientToken();   // 失败重试复用同一幂等键
    try {
      await this.callTodo('add', { title, clientToken: this.addToken });
      this.addToken = '';
      this.setData({ title: '' });
      await this.fetchList();
    } finally {
      this.submitting = false;
    }
  },

  async onToggle(e) {
    const { id, done } = e.currentTarget.dataset;
    await this.callTodo('toggle', { id, done: !done });
    this.fetchList();
  },

  async onRemove(e) {
    const { id } = e.currentTarget.dataset;
    const { confirm } = await wx.showModal({ title: '确认删除？' });
    if (!confirm) return;
    await this.callTodo('remove', { id });
    this.fetchList();
  },

  onFilter(e) {
    const { status } = e.currentTarget.dataset;
    this.setData({ status });
    this.fetchList();
  }
})
