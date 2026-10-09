Page({
  data: { userName: '' },
  onShow() {
    const app = getApp();
    this.setData({ userName: app.globalData.user.name });
  },
  goDetail() {
    wx.navigateTo({
      url: '/pages/detail/detail?id=1&title=小程序导航'
    });
  }
});
