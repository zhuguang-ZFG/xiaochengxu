# 待办清单示例工程

对应教程：[docs/06-实战/01-待办清单实战.md](../../docs/06-实战/01-待办清单实战.md)

一个**可运行**的微信小程序原生 + 云开发项目：待办增删改查 + 状态筛选 + 按用户数据隔离。

## 目录

```
todo-miniprogram/
├── app.js / app.json / app.wxss / sitemap.json
├── project.config.json
├── cloudfunctions/
│   └── todo/              # 云函数：所有增删改查统一入口
│       ├── index.js
│       └── package.json
└── pages/
    └── index/             # 单页面
        ├── index.wxml / index.wxss / index.js / index.json
```

## 运行步骤

1. 打开[微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) → 导入项目 → 选择本目录
2. `project.config.json` 中的 `appid` 改为你的真实 AppID（当前为 `touristappid` 测试号）
3. 开通云开发（工具栏「云开发」→ 按量付费），创建环境
4. 把 `app.js` 中 `wx.cloud.init` 的 `env` 改成你的环境 ID
5. 云开发控制台建集合 `todos`，权限设为「所有用户不可读写」（数据全部走云函数，见教程安全建议）
6. 右键 `cloudfunctions/todo` →「上传并部署：云端安装依赖」
7. 编译运行；用两个微信号扫码预览可验证数据隔离（每个用户只见自己的待办）

## 与教程的一致性

本工程的代码与 [实战篇](../../docs/06-实战/01-待办清单实战.md) 完全一致，教程中的每个知识点都能在本工程对应到代码位置。

- 云函数 `todo`：action 分发（list/add/toggle/remove）+ openid 归属校验
- 页面 `index.js`：setData 数据流、callFunction 封装、事件处理
- 安全：所有写操作带 `openid` 条件，集合权限全关，双保险

## 修改提示

- 换环境：只改 `app.js` 的 `env`
- 换集合：改 `cloudfunctions/todo/index.js` 里的 `db.collection('todos')`
