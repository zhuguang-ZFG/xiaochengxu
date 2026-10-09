---
title: 常见问题（FAQ）
description: 学习者高频问题汇总，按阶段分类，覆盖环境、语法、架构、发布等常见困惑
category: 学习路线
tags: [FAQ, 常见问题, 答疑]
difficulty: ★☆☆☆☆
reading_time: 20 分钟
updated: 2026-10-09
---

# 常见问题（FAQ）

汇总学习者在各阶段的高频问题。如果这里没有你的问题，欢迎到 [Issues](https://github.com/zhuguang-ZFG/xiaochengxu/issues) 提问。

## 入门阶段

**Q1**: 没有编程基础能学小程序吗？

<details><summary>回答</summary>

可以，但建议先花 1-2 天了解 HTML/CSS/JavaScript 基础。小程序的 WXML/WXSS 与 HTML/CSS 非常相似，有基础后上手会快很多。本路径从「什么是小程序」讲起，但代码示例假设你认识基本的 JS 语法（变量、函数、对象）。

</details>

**Q2**: 个人主体和企业主体怎么选？

<details><summary>回答</summary>

如果你的小程序需要接入微信支付、需要企业认证，选企业主体（需要营业执照）。个人主体功能受限但注册简单，且**后期不能升级为企业主体**，只能重新注册。详见[认识小程序](../01-入门/01-认识小程序.md)的「小程序类型」段落。

</details>

## 基础阶段

**Q3**: 为什么改了 JS 里的变量，页面没有变化？

<details><summary>回答</summary>

小程序的视图更新**只认 `setData`**。直接修改 `this.data.xxx` 只改了逻辑层的对象，不会触发跨线程通信，渲染层不知道数据变了。必须调用 `this.setData({ xxx: newValue })` 才能触发视图更新。详见 [JS 逻辑层与数据驱动](../02-基础/03-JS逻辑层与数据驱动.md)。

</details>

**Q4**: rpx 和 px 有什么区别？什么时候用哪个？

<details><summary>回答</summary>

`rpx` 是小程序的响应式单位，以 750rpx = 屏幕宽度为基准，会自动适配不同屏幕尺寸。`px` 是物理像素，不会自适应。**布局尺寸（宽高、间距）统一用 rpx**，只有边框粗细等需要固定像素的场景才用 px。详见 [WXSS 样式与 rpx](../02-基础/02-WXSS样式与rpx.md)。

</details>

**Q5**: wx:if 和 hidden 都能控制显示隐藏，该用哪个？

<details><summary>回答</summary>

- **wx:if**：真正的条件渲染，切换时会销毁/重建组件。适合运行时条件很少变化的场景。
- **hidden**：只是 CSS 级别的 display 切换，组件始终存在。适合频繁切换的场景。

判断依据：如果需要频繁切换，用 `hidden`（避免反复销毁重建的开销）；如果条件很少变，用 `wx:if`（初始渲染成本更低）。详见[内置组件](../03-进阶/01-内置组件.md)。

</details>

**Q6**: bind 和 catch 事件有什么区别？

<details><summary>回答</summary>

两者都绑定事件处理函数，区别在于**是否阻止事件冒泡**：

- `bindtap`：正常触发，事件会继续向父组件冒泡
- `catchtap`：触发后**阻止冒泡**，父组件的 tap 事件不会被触发

典型场景：列表项里有一个删除按钮，点击删除时不想触发列表项的点击事件——删除按钮用 `catchtap`，列表项用 `bindtap`。详见[页面生命周期与事件](../02-基础/04-页面生命周期与事件.md)。

</details>

**Q7**: WXS 和 JS 有什么区别？什么时候用 WXS？

<details><summary>回答</summary>

WXS 是小程序的**视图层脚本语言**，运行在渲染层（而非逻辑层），主要用途：

1. **作为过滤器/格式化器**：在 WXML 里直接调用（如 `{{fmtPrice(item.price)}}`），避免逻辑层频繁 setData
2. **响应事件**：作为 `bindchange` 等的处理函数（如手势跟随），减少逻辑层与渲染层的通信开销

限制：WXS 不能调用 JS API（如 `wx.request`），不能操作 DOM，语法是 ES5 子集。只有**性能敏感的场景**（高频事件、列表格式化）才需要用 WXS，普通逻辑用 JS 即可。

</details>

## 进阶阶段

**Q8**: 自定义组件之间怎么通信？

<details><summary>回答</summary>

三种方式：
1. **父 → 子**：通过 `properties` 传数据（类似 React 的 props）
2. **子 → 父**：通过 `this.triggerEvent('事件名', detail)` 抛事件
3. **跨层级**：通过 `getApp().globalData` 或事件总线（不推荐滥用）

详见[自定义组件](../03-进阶/02-自定义组件.md)。

</details>

**Q9**: setData 数据量大了会卡顿，怎么优化？

<details><summary>回答</summary>

六条军规：
1. 只传差异，不传全量（路径写法 `this.setData({'list[0].done': true})`）
2. 把大对象拆成小组件（Shadow 树规模与 diff 成本正相关）
3. 避免在 scroll/touch 等高频事件里频繁 setData
4. 用 `wx:key` 帮助列表 diff
5. 长列表按需渲染（可视区域 ± 缓冲）
6. 用 `setUpdatePerformanceListener` 测量而不是猜

详见[性能优化](../03-进阶/04-性能优化.md)。

</details>

**Q10**: 授权弹窗被用户拒绝了怎么办？

<details><summary>回答</summary>

用户拒绝授权后，再次调用授权接口不会弹窗，而是直接走 fail。需要引导用户去设置页手动开启：先 `wx.getSetting` 检查 scope 状态，如果已拒绝则用 `wx.openSetting` 让用户手动打开。详见[授权与隐私](../03-进阶/07-授权与隐私.md)。

</details>

**Q11**: scroll-view 的 `bindscrolltolower` 不触发？

<details><summary>回答</summary>

三个常见原因：

1. **没设固定高度**：`scroll-view` 必须有明确的 CSS 高度（`height: 500rpx` 或 `calc(100vh - 200rpx)`），否则无法计算滚动区域
2. **内容没超出容器**：列表项总高度没超过 scroll-view 高度，没有滚动就不可能触发触底
3. **用了页面滚动**：如果整个页面在滚动而不是 scroll-view 内部滚动，应该用页面的 `onReachBottom` 而不是 scroll-view 的事件

详见[内置组件](../03-进阶/01-内置组件.md)的 scroll-view 段落。

</details>

**Q12**: 选择图片后，过一段时间临时路径失效了？

<details><summary>回答</summary>

`wx.chooseImage` / `wx.chooseMedia` 返回的是**临时文件路径**（`wxfile://` 或 `http://tmp/` 开头），系统会在合适时机回收临时文件。如果需要长期保留：

1. **展示用**：在同一个 App 生命周期内使用没问题，杀进程后路径失效
2. **持久化**：用 `wx.getFileSystemManager().saveFile` 保存到本地（有 100MB 限制）或上传到云存储
3. **上传**：用 `wx.uploadFile` 传到服务器后再用服务端 URL

详见[媒体能力](../03-进阶/05-媒体能力.md)。

</details>

**Q13**: 地图定位有偏移，和实际位置对不上？

<details><summary>回答</summary>

微信小程序的 `wx.getLocation` 默认返回 **GCJ-02 坐标系**（国测局坐标，又称「火星坐标系」），不是 GPS 的 WGS-84。如果你拿 GPS 坐标直接在地图上显示，会有 100-700 米的偏移。

解决方案：
- 使用腾讯地图（小程序内置）时直接用 GCJ-02，无需转换
- 如果数据源是 WGS-84（如外部 GPS 设备），需要先做坐标转换
- `wx.getLocation` 的 `type` 参数可以指定返回 WGS-84（但安卓端可能不支持）

详见[地图与定位](../03-进阶/06-地图与定位.md)。

</details>

**Q14**: 订阅消息发送失败，报「模板不存在」或「用户未授权」？

<details><summary>回答</summary>

两种常见原因：

1. **模板未审核**：在 MP 后台 → 功能 → 订阅消息里选用的模板必须通过审核才能使用。新模板需要等审核通过
2. **用户未授权**：订阅消息需要用户主动点击按钮授权（`wx.requestSubscribeMessage`），不能静默获取。且每次授权只对一次发送有效——用户必须每次都点同意

注意：订阅消息**不能**在云函数里直接发送，需要在小程序端调用 `wx.requestSubscribeMessage` 获取授权后，由后端（云函数或自己的服务器）调用服务端 API 发送。详见[分享与订阅消息](../03-进阶/08-分享与订阅消息.md)。

</details>

**Q15**: Skyline 和 WebView 渲染引擎怎么选？

<details><summary>回答</summary>

- **WebView**（默认）：成熟稳定，兼容性好，社区资源丰富。绝大多数小程序用这个
- **Skyline**：新引擎，性能更好（原生渲染、共享元素过渡），但要求基础库 ≥ 3.0.2，部分组件/API 还不支持

建议：新项目可以先用 WebView，等 Skyline 的组件覆盖度满足你的需求后再迁移。迁移时在 `app.json` 加 `"renderer": "skyline"` 即可全局切换，也可以按页面粒度配置。详见[Skyline 与适配](../03-进阶/09-Skyline与适配.md)。

</details>

**Q26**: wx.request 请求失败，怎么排查？

<details><summary>回答</summary>

按顺序检查：

1. **域名没配到白名单**：MP 后台 → 开发管理 → 开发设置 → 服务器域名 → request 合法域名。注意：开发阶段可以勾选「不校验合法域名」，但上线前必须配好
2. **HTTPS 要求**：线上环境只允许 HTTPS（开发时可以 HTTP），证书必须有效（自签名证书不行）
3. **跨域问题**：小程序没有浏览器的同源策略，但域名必须在白名单里。如果后端没返回 CORS 头不影响小程序（CORS 是浏览器概念）
4. **超时**：默认超时 60 秒，可在 `wx.request` 的 `timeout` 参数里改。如果接口本身慢，考虑后端优化或加 loading 态
5. **返回数据解析**：`res.data` 的类型取决于 `dataType`（默认 `json`，会自动 JSON.parse）。如果后端返回的不是合法 JSON，会进 fail 回调

调试技巧：在开发者工具的 Network 面板看请求详情（请求头、响应头、耗时），或 `console.log(res)` 打印完整响应对象。详见[网络请求与数据](../03-进阶/03-网络请求与数据.md)。

</details>

**Q27**: 微信支付接入后，调起支付时报「支付验证签名失败」？

<details><summary>回答</summary>

这个错误几乎一定是**后端签名计算错误**。`wx.requestPayment` 需要的 5 个参数（`timeStamp`、`nonceStr`、`package`、`signType`、`paySign`）全部由后端生成，签名算法是：

```text
signStr = "appId=xxx&nonceStr=xxx&package=prepay_id=xxx&signType=MD5&timeStamp=xxx&key=xxx"
paySign = MD5(signStr).toUpperCase()
```

常见错误：
1. **key 用错了**：签名用的 key 是商户号 API 密钥（32 位），不是小程序的 AppSecret
2. **参数大小写**：参数名区分大小写（`appId` 不是 `appid`）
3. **package 格式**：必须是 `prepay_id=xxx`，不是单纯的 prepay_id 值
4. **signType 不匹配**：用 MD5 签名时 signType 写 `MD5`，用 HMAC-SHA256 时写 `HMAC-SHA256`，两者签名算法不同

建议：先用微信支付官方的[签名校验工具](https://pay.weixin.qq.com/wiki/doc/apiv3/apis/chapter3_1_4.shtml)验证签名是否正确。详见[微信支付](../03-进阶/12-微信支付.md)。

</details>

**Q28**: 真机上出了 bug 但模拟器正常，怎么调试？

<details><summary>回答</summary>

模拟器和真机的渲染环境不同（模拟器用 Chrome 内核，真机用系统 WebView 或 Skyline），有些差异只在真机暴露。调试方法：

1. **真机调试**（推荐）：开发者工具 → 真机调试按钮。可以实时看 Console、Network、AppData，还能打断点。要求手机和电脑在同一 WiFi
2. **vConsole**：在 `app.js` 的 `onLaunch` 里加 `wx.setEnableDebug({ enableDebug: true })`，真机上会出现一个绿色的 vConsole 按钮，点开可以看日志和网络请求。发布前记得关掉
3. **体验版 + 错误监控**：发布体验版后，在 MP 后台 → 运维中心 → 性能监控里看线上错误日志（需要用户同意数据上报）
4. **场景值还原**：有些 bug 只在特定入口触发（如扫码进入、分享卡片进入），在开发者工具的「编译模式」里模拟不同场景值

常见模拟器与真机差异：`position: fixed` 在 scroll-view 内行为不同、`canvas` API 差异、音频播放策略不同。详见[调试与排错](../03-进阶/11-调试与排错.md)。

</details>

## 云开发阶段

**Q16**: 云函数调用失败，报「函数不存在」？

<details><summary>回答</summary>

最常见原因：云函数写了但**没有上传部署**。在开发者工具中右键云函数目录 → 「上传并部署：云端安装依赖」。另外检查 `app.js` 的 `wx.cloud.init` 是否填了正确的环境 ID。详见[云函数](../04-云开发/02-云函数.md)。

</details>

**Q17**: 云数据库的权限怎么设？

<details><summary>回答</summary>

四种模式：所有用户可读/仅创建者可写（最常用）、仅创建者读写、所有用户不可读写（最安全，只能走云函数）、自定义规则。建议默认用「仅创建者可读写」保证数据隔离，需要跨用户操作时走云函数。详见[云数据库](../04-云开发/03-云数据库.md)。

</details>

**Q18**: 云函数执行超时怎么办？

<details><summary>回答</summary>

云函数默认超时时间是 **3 秒**（可在 `cloudfunctions/函数名/package.json` 里改 `timeout` 字段，最长 60 秒）。超时原因通常是：

1. **数据库查询慢**：加索引（在云开发控制台 → 数据库 → 集合 → 索引管理里添加）
2. **外部 HTTP 请求慢**：设合理的超时时间，考虑用缓存
3. **冷启动**：第一次调用时需要初始化运行环境，后续调用会快很多。可以把初始化逻辑（如 `cloud.init`）放在函数外层

详见[云函数](../04-云开发/02-云函数.md)。

</details>

**Q19**: 云存储的文件怎么公开访问？

<details><summary>回答</summary>

云存储文件默认是私有的，需要通过 `wx.cloud.getTempFileURL` 获取**临时链接**（有效期 2 小时）。如果需要长期可访问的 URL：

1. **CDN 加速域名**：在云开发控制台 → 存储 → 设置里开启，绑定自定义域名后文件可以通过 `https://你的域名/cloud1-xxx/文件路径` 直接访问
2. **云托管**：把静态文件放在云托管（CloudBase Run）里，通过 HTTP 访问

注意：临时链接过期后需要重新获取，不要把临时链接存数据库。详见[云存储](../04-云开发/04-云存储.md)。

</details>

## 发布阶段

**Q20**: 审核被驳回了怎么办？

<details><summary>回答</summary>

先看驳回原因（在 MP 后台 → 版本管理里），常见原因：
1. **类目不符**：小程序内容与选择的类目不匹配，换类目或改内容
2. **功能不完整**：体验版里有空页面或死链接
3. **隐私问题**：缺少隐私指引或未说明数据用途
4. **诱导分享**：包含「分享到群可获得 XX」等文案

修改后重新提交即可，不需要重新上传代码（除非改了代码）。详见[上线发布](../05-发布/01-上线发布.md)。

</details>

**Q21**: 体验版二维码过期了怎么办？

<details><summary>回答</summary>

体验版二维码**不会过期**——如果扫码提示「二维码已失效」，通常是以下原因：

1. **体验版被覆盖**：上传了新版本并设为体验版后，旧二维码指向的版本已不存在。重新在 MP 后台生成二维码即可
2. **不是体验成员**：体验版只有被添加为体验成员的人才能访问。在 MP 后台 → 成员管理 → 体验成员里添加
3. **小程序已下线**：如果小程序被下架或封禁，体验版也无法访问

</details>

**Q22**: 发布后发现严重 bug，怎么回退到旧版本？

<details><summary>回答</summary>

MP 后台 → 版本管理 → 线上版本，点「版本回退」可以回退到上一个版本。**回退是即时的**，不需要审核。注意：

- 只能回退一个版本（回到上一个），不能回退多个版本
- 回退后旧版本重新成为线上版本，用户可以正常使用
- 回退不影响开发版和体验版

建议：每次发布前记录版本号，方便定位问题。详见[上线发布](../05-发布/01-上线发布.md)。

</details>

## 实战阶段

**Q23**: 示例工程导入开发者工具后报错？

<details><summary>回答</summary>

常见原因：

1. **AppID 问题**：`project.config.json` 里的 `appid` 是 `touristappid`（游客模式），需要改成你自己的 AppID。没有 AppID 可以勾选「不使用云服务」（仅待办清单需要云开发）
2. **基础库版本太低**：部分示例用了较新的 API，在开发者工具里把基础库版本切到最新
3. **文件不完整**：确认是从 GitHub 完整 clone 的仓库，不是只下载了单个文件

</details>

**Q24**: 待办清单示例需要开通云开发，具体步骤是什么？

<details><summary>回答</summary>

1. 打开微信开发者工具，导入 `examples/todo-miniprogram/`
2. 点工具栏的「云开发」按钮（云朵图标）
3. 首次使用会提示开通，选择「按量付费」（有免费额度）
4. 创建环境，记下环境 ID
5. 打开 `app.js`，把 `wx.cloud.init` 里的 `env` 改成你的环境 ID
6. 在云开发控制台 → 数据库里创建集合 `todos`，权限设为「所有用户不可读写」
7. 右键 `cloudfunctions/todo` → 「上传并部署：云端安装依赖」
8. 编译运行

详见[实战项目：待办清单](../06-实战/01-待办清单实战.md)。

</details>

**Q25**: tabBar 图标不显示或显示异常？

<details><summary>回答</summary>

三个检查点：

1. **路径错误**：`iconPath` 和 `selectedIconPath` 的路径是相对于 `app.json` 所在目录的，不要写成绝对路径
2. **图片格式**：只支持 PNG、JPG，不支持 SVG、GIF。建议用 PNG（支持透明背景）
3. **图片大小**：建议 81×81 px（推荐尺寸），最大不超过 40KB

如果还是不行，在开发者工具的 Console 里看有没有报错信息。详见[实战项目：多页面导航](../06-实战/02-多页面导航实战.md)。

</details>

## 延伸阅读

- [学习路径总览](01-学习路径总览.md) — 完整学习路线图
- [API 速查索引](02-API速查索引.md) — 按能力域分类的 API 速查
- 官方：[小程序常见问题](https://developers.weixin.qq.com/miniprogram/dev/framework/faq.html)
