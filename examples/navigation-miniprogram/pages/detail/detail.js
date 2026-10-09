Page({
  data: { id: '', title: '', from: '' },
  onLoad(options) {
    const from = getCurrentPages().length > 1
      ? getCurrentPages()[getCurrentPages().length - 2].route
      : '直接打开';
    this.setData({
      id: options.id || '',
      title: options.title || '未知',
      from: from
    });
  },
  goBack() {
    wx.navigateBack();
  }
});
