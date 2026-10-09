# 多页面导航示例工程

对应教程：[docs/06-实战/02-多页面导航实战.md](../../docs/06-实战/02-多页面导航实战.md)

一个**可运行**的微信小程序原生项目：三 Tab 应用 + 页面跳转 + URL 传参 + globalData 跨页共享 + 生命周期演示。

## 目录

```text
navigation-miniprogram/
├── app.js / app.json / app.wxss / sitemap.json
├── project.config.json
└── pages/
    ├── home/        # Tab 1：首页 + 跳转详情按钮
    │   └── home.wxml / home.wxss / home.js / home.json
    ├── category/    # Tab 2：分类列表 + dataset 传参跳详情
    │   └── category.wxml / category.wxss / category.js / category.json
    ├── profile/     # Tab 3：globalData 用户信息 + onShow 计数
    │   └── profile.wxml / profile.wxss / profile.js / profile.json
    └── detail/      # 普通页面（不在 tabBar 里）：接收 URL 参数 + 显示来源页
        └── detail.wxml / detail.wxss / detail.js / detail.json
```

## 运行步骤

1. 打开[微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) → 导入项目 → 选择本目录
2. `project.config.json` 中的 `appid` 改为你的真实 AppID（当前为 `touristappid` 测试号）
3. 编译运行；底部三个 Tab 可切换
4. 首页点击「查看详情」按钮，跳转到详情页（带 URL 参数）
5. 分类页点击列表项，跳转到详情页（动态传 id 和标题）
6. 切到「我的」Tab 再切回来，观察加载次数 +1（onShow 触发）

## 与教程的一致性

本工程的代码与 [实战篇](../../docs/06-实战/02-多页面导航实战.md) 完全一致，教程中的每个知识点都能在本工程对应到代码位置。

- `app.json`：tabBar 配置（3 个 Tab + 4 个页面声明）
- `home.js`：`wx.navigateTo` 跳转 + URL 参数拼接
- `category.js`：`dataset` 传参 + 动态 URL 构造
- `detail.js`：`onLoad(options)` 接收参数 + `getCurrentPages()` 获取来源页
- `profile.js`：`globalData` 读取 + `onShow` 计数（Tab 页不销毁）

## 单元测试

工程带零依赖结构测试（node 内置 test runner，无需安装 npm 包）：

```bash
node --test examples/navigation-miniprogram/tests/*.test.js
```

测试验证 3 个结构不变量：

- `app.json` 声明了 3 个 tabBar 项（首页 / 分类 / 我的）
- 所有声明的页面在磁盘上存在对应的 `.js` 和 `.wxml` 文件
- 详情页在 `onLoad` 里通过 `options` 接收 URL 参数

测试不改业务代码，与教程代码逐行一致；CI 每次 push 自动运行。

## 修改提示

- 加 Tab：在 `app.json` 的 `tabBar.list` 里加一项，同时在 `pages/` 下建对应目录
- 加页面：在 `app.json` 的 `pages` 数组里声明，新建页面四件套
