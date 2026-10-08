---
title: wx.API 速查索引
description: 按能力域整理的 wx.* API 速查矩阵，每条给出作用与详解所在文章
category: 学习路线
tags: [API, 速查, 索引]
difficulty: ★☆☆☆☆
reading_time: 5 分钟
updated: 2026-10-08
---

# wx.API 速查索引

> 为什么要读这篇：26 篇文章里散布着 40+ 个 `wx.*` API，遇到「想不起某个能力在哪个 API、去哪查」时，用这张表定位。它不是 API 手册——每条只给一句话作用 + 本库详解文章；官方完整参数见链接的官方文档。

## 用法

- 按能力域找 API → 点「详解」直达本库文章，点「官方」看完整参数
- 接口是否可用以基础库版本为准，官方文档每个 API 页顶部标注最低版本
- 异步 API 不传 success/fail/complete 就直接返回 Promise（[基础库 2.10.2 起](https://developers.weixin.qq.com/miniprogram/dev/framework/app-service/api.html)），可 `await`；`wx.request`/`wx.uploadFile`/`wx.downloadFile`/`wx.connectSocket` 例外——它们本身返回任务对象，要自行封装（见[网络请求与数据](../03-进阶/03-网络请求与数据.md)）
- `wx.cloud.*` 与 `cloud.*`（云函数端）是两套体系，见云开发篇

## 登录与身份

| API | 作用 | 详解 | 官方 |
|---|---|---|---|
| `wx.login` | 获取临时登录凭证 code，换 openid/session_key 的前置 | [网络请求与数据](../03-进阶/03-网络请求与数据.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/open-api/login/wx.login.html) |
| `wx.checkSession` | 检查登录态是否过期 | [网络请求与数据](../03-进阶/03-网络请求与数据.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/open-api/login/wx.checkSession.html) |
| `wx.getUserProfile` | 获取用户信息（每次调用都会弹授权，注意隐私新规） | [授权与隐私](../03-进阶/07-授权与隐私.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/open-api/user-info/wx.getUserProfile.html) |
| `wx.getUserInfo` | 旧接口（2021 后不再弹出授权，仅返回默认头像昵称） | [授权与隐私](../03-进阶/07-授权与隐私.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/open-api/user-info/wx.getUserInfo.html) |

## 网络

| API | 作用 | 详解 | 官方 |
|---|---|---|---|
| `wx.request` | 发起 HTTPS 请求（域名需在小程序后台配置） | [网络请求与数据](../03-进阶/03-网络请求与数据.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/network/request/wx.request.html) |
| `wx.uploadFile` | 上传文件到业务服务器（配合 tempFilePath） | [媒体能力](../03-进阶/05-媒体能力.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/network/upload/wx.uploadFile.html) |

## 数据缓存

| API | 作用 | 详解 | 官方 |
|---|---|---|---|
| `wx.setStorage` / `wx.setStorageSync` | 写入本地缓存（单 key 上限 1MB，总量 10MB） | [网络请求与数据](../03-进阶/03-网络请求与数据.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/storage/wx.setStorage.html) |
| `wx.getStorageSync` | 读取本地缓存 | 同上 | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/storage/wx.getStorageSync.html) |
| `wx.removeStorageSync` / `wx.clearStorageSync` | 删除单 key / 清空全部缓存 | 同上 | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/storage/wx.removeStorageSync.html) |

## 路由

| API | 作用 | 详解 | 官方 |
|---|---|---|---|
| `wx.navigateTo` | 打开新页面（页面栈上限 10） | [页面生命周期与事件](../02-基础/04-页面生命周期与事件.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/route/wx.navigateTo.html) |
| `wx.redirectTo` / `wx.reLaunch` / `wx.switchTab` | 重定向 / 关闭全部重开 / 切 tab | 同上 | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/route/wx.redirectTo.html) |
| `wx.navigateBack` | 返回上一页（携带 delta 可多级） | 同上 | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/route/wx.navigateBack.html) |

## 界面与交互

| API | 作用 | 详解 | 官方 |
|---|---|---|---|
| `wx.showToast` | 轻提示（图标/纯文字，1.5s 默认） | [媒体能力](../03-进阶/05-媒体能力.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/ui/interaction/wx.showToast.html) |
| `wx.showModal` | 模态对话框（`res.confirm` 区分确定/取消，可 await） | [授权与隐私](../03-进阶/07-授权与隐私.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/ui/interaction/wx.showModal.html) |
| `wx.previewImage` | 全屏预览图片（可多张左右滑动） | [媒体能力](../03-进阶/05-媒体能力.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/media/image/wx.previewImage.html) |
| `wx.openDocument` | 打开本地文档（pdf/doc/xls 等） | [云存储](../04-云开发/04-云存储.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/file/wx.openDocument.html) |
| `wx.stopPullDownRefresh` | 停止下拉刷新 loading | [页面生命周期与事件](../02-基础/04-页面生命周期与事件.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/ui/pull-down-refresh/wx.stopPullDownRefresh.html) |

## 媒体

| API | 作用 | 详解 | 官方 |
|---|---|---|---|
| `wx.chooseMedia` | 选图片/视频（相机+相册，返回临时文件） | [媒体能力](../03-进阶/05-媒体能力.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/media/video/wx.chooseMedia.html) |
| `wx.chooseImage` / `wx.chooseVideo` | 旧版选图/选视频（chooseMedia 的替代） | 同上 | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/media/image/wx.chooseImage.html) |
| `wx.getRecorderManager` | 录音管理（start/stop/onFrameRecorded） | 同上 | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/media/recorder/wx.getRecorderManager.html) |
| `wx.saveImageToPhotosAlbum` | 保存图片到相册（需 scope.writePhotosAlbum 授权） | [授权与隐私](../03-进阶/07-授权与隐私.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/media/image/wx.saveImageToPhotosAlbum.html) |

## 位置

| API | 作用 | 详解 | 官方 |
|---|---|---|---|
| `wx.getLocation` | 获取当前位置坐标（需 scope.userLocation 授权） | [地图与定位](../03-进阶/06-地图与定位.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/location/wx.getLocation.html) |
| `wx.startLocationUpdate` / `wx.onLocationChange` | 持续位置更新与监听 | 同上 | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/location/wx.startLocationUpdate.html) |
| `wx.openLocation` | 打开内置地图展示位置 | 同上 | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/location/wx.openLocation.html) |

## 授权与隐私

| API | 作用 | 详解 | 官方 |
|---|---|---|---|
| `wx.getSetting` | 查询已授权 scope 状态 | [授权与隐私](../03-进阶/07-授权与隐私.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/open-api/setting/wx.getSetting.html) |
| `wx.authorize` | 提前发起授权（不再推荐直接调用） | 同上 | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/open-api/authorize/wx.authorize.html) |
| `wx.openSetting` | 打开设置页引导用户改授权 | 同上 | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/open-api/setting/wx.openSetting.html) |
| `wx.onNeedPrivacyAuthorization` | 隐私协议弹窗监听（隐私新规） | 同上 | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/open-api/privacy/wx.onNeedPrivacyAuthorization.html) |

## 分享与订阅

| API | 作用 | 详解 | 官方 |
|---|---|---|---|
| `wx.showShareMenu` | 开启转发按钮（右上角菜单） | [分享与订阅消息](../03-进阶/08-分享与订阅消息.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/share/wx.showShareMenu.html) |
| `wx.requestSubscribeMessage` | 拉起订阅消息授权（一次最多 3 个模板） | 同上 | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/open-api/subscribe-message/wx.requestSubscribeMessage.html) |

## 更新与窗口

| API | 作用 | 详解 | 官方 |
|---|---|---|---|
| `wx.getUpdateManager` | 监听小程序版本更新并强制更新 | [上线发布](../05-发布/01-上线发布.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/base/update/wx.getUpdateManager.html) |
| `wx.getWindowInfo` | 窗口/屏幕尺寸信息（替代废弃的 getSystemInfoSync） | [Skyline 与适配](../03-进阶/09-Skyline与适配.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/base/system/wx.getWindowInfo.html) |
| `wx.onWindowResize` | 监听窗口尺寸变化 | 同上 | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/ui/window/wx.onWindowResize.html) |
| `wx.getMenuButtonBoundingClientRect` | 胶囊按钮位置（自定义导航必备） | 同上 | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/ui/menu/wx.getMenuButtonBoundingClientRect.html) |
| `wx.createAnimation` | 旧版动画接口（新项目用 this.animate） | [性能优化](../03-进阶/04-性能优化.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/api/ui/animation/wx.createAnimation.html) |

## 云开发

| API | 作用 | 详解 | 官方 |
|---|---|---|---|
| `wx.cloud.init` | 初始化云环境（app.js 全局一次） | [云开发入门](../04-云开发/01-云开发入门.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/wxcloudservice/wxcloud/reference-sdk-api/init/client.init.html) |
| `wx.cloud.callFunction` | 调用云函数 | [云函数](../04-云开发/02-云函数.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/wxcloudservice/wxcloud/reference-sdk-api/functions/Cloud.callFunction.html) |
| `wx.cloud.database` | 获取数据库引用 | [云数据库](../04-云开发/03-云数据库.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/wxcloudservice/wxcloud/reference-sdk-api/Cloud.database.html) |
| `wx.cloud.uploadFile` | 上传文件到云存储 | [云存储](../04-云开发/04-云存储.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/wxcloudservice/wxcloud/reference-sdk-api/storage/uploadFile/client.uploadFile.html) |
| `cloud.getTempFileURL` | 云存储文件换临时访问链接 | 同上 | [文档](https://developers.weixin.qq.com/miniprogram/dev/wxcloudservice/wxcloud/reference-sdk-api/storage/Cloud.getTempFileURL.html) |
| `wx.worklet.runOnUI` | Skyline：把 worklet 函数调度到渲染线程 | [Skyline 与适配](../03-进阶/09-Skyline与适配.md) | [文档](https://developers.weixin.qq.com/miniprogram/dev/framework/runtime/skyline/worklet.html) |

## 不在本表的情况

- **组件事件**（bindtap、scroll 等）不是 API，见 [页面生命周期与事件](../02-基础/04-页面生命周期与事件.md)
- **`Page` / `Component` / `App` 构造器** 不是 `wx.*`，见 [自定义组件](../03-进阶/02-自定义组件.md)
- **服务端 API**（access_token、code2Session、订阅消息下发）见 [云函数](../04-云开发/02-云函数.md) 与官方[服务端 API](https://developers.weixin.qq.com/miniprogram/dev/server/API/)
- 本表只收录本库文章实际用到的 API；完整清单见官方 [API 文档](https://developers.weixin.qq.com/miniprogram/dev/api/)

## 验证

- [ ] 说出「获取用户头像昵称」在当前版本的推荐做法（对比 getUserInfo 与 getUserProfile）
- [ ] 不查文档，说出本地缓存单 key 与总量的上限数字
- [ ] 遇到「页面一直停在某个旧版本」的场景，说出该用哪个 API
- [ ] 用 `wx.getMenuButtonBoundingClientRect` 的返回值画出自定义导航栏的布局
