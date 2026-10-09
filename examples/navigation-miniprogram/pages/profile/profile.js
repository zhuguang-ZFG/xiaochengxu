Page({
  data: { user: {}, loadCount: 0 },
  onLoad() {
    const app = getApp();
    this.setData({
      user: app.globalData.user,
      loadCount: 1
    });
  },
  onShow() {
    if (this.data.loadCount > 0) {
      this.setData({ loadCount: this.data.loadCount + 1 });
    }
  }
});
