Page({
  data: {
    categories: [
      { id: 1, name: '入门基础' },
      { id: 2, name: '进阶技巧' },
      { id: 3, name: '云开发' },
      { id: 4, name: '性能优化' }
    ]
  },
  onTap(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/detail/detail?id=${id}&title=${this.data.categories[id-1].name}` });
  }
});
