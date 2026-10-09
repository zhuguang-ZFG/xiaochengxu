# 商品列表示示例工程

对应教程：[docs/06-实战/03-商品列表实战.md](../../docs/06-实战/03-商品列表实战.md)

一个**可运行**的微信小程序原生项目：商品列表 + 搜索过滤 + scroll-view 加载更多 + 详情页动态标题。

## 目录

```text
product-list-miniprogram/
├── app.js / app.json / app.wxss / sitemap.json
├── project.config.json
└── pages/
    ├── list/        # 列表页：搜索框 + scroll-view + wx:for/wx:key
    │   └── list.wxml / list.wxss / list.js / list.json
    └── detail/      # 详情页：根据 id 展示商品 + 动态导航栏标题
        └── detail.wxml / detail.wxss / detail.js / detail.json
```

## 运行步骤

1. 打开[微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) → 导入项目 → 选择本目录
2. `project.config.json` 中的 `appid` 改为你的真实 AppID（当前为 `touristappid` 测试号）
3. 编译运行；列表展示 8 个商品
4. 搜索框输入关键词，列表实时过滤
5. 滚动到底部，触发「加载中」提示
6. 点击商品卡片，跳转详情页，导航栏标题变为商品名

## 与教程的一致性

本工程的代码与 [实战篇](../../docs/06-实战/03-商品列表实战.md) 完全一致，教程中的每个知识点都能在本工程对应到代码位置。

- `list.wxml`：`wx:for` + `wx:key="id"` 列表渲染 + `scroll-view` 滚动加载
- `list.js`：`onSearch` 搜索过滤 + `loadMore` 加载更多 + `goDetail` dataset 传参
- `detail.js`：`onLoad(options)` 接收 id + `wx.setNavigationBarTitle` 动态标题
- 数据硬编码在 `list.js` 的 `ALL_PRODUCTS` 数组中（教程重点：换成 `wx.request` 即可对接真实 API）

## 单元测试

工程带零依赖结构测试（node 内置 test runner，无需安装 npm 包）：

```bash
node --test examples/product-list-miniprogram/tests/*.test.js
```

测试验证 5 个结构不变量：

- `app.json` 声明了 `list` 和 `detail` 两个页面
- 所有声明的页面在磁盘上存在对应的 `.js` 和 `.wxml` 文件
- 列表页使用了 `wx:for` 和 `wx:key`
- 列表页使用了 `scroll-view` 组件
- 列表页的搜索逻辑包含 `onSearch` 和 `.filter`

测试不改业务代码，与教程代码逐行一致；CI 每次 push 自动运行。

## 修改提示

- 换数据源：把 `list.js` 里的 `ALL_PRODUCTS` 换成 `wx.request` 从服务器获取
- 加字段：在 `ALL_PRODUCTS` 对象里加属性，`list.wxml` 里用 `{{item.新字段}}` 展示
