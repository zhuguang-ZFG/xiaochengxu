# 待办清单示例工程

对应教程：[docs/06-实战/01-待办清单实战.md](../../docs/06-实战/01-待办清单实战.md)

一个**可运行**的微信小程序原生 + 云开发项目：待办增删改查 + 状态筛选 + 按用户数据隔离。

## 目录

```text
todo-miniprogram/
├── app.js / app.json / app.wxss / sitemap.json
├── project.config.json
├── cloudfunctions/
│   └── todo/              # 云函数：所有增删改查统一入口
│       ├── index.js
│       └── package.json
├── pages/
│   └── index/             # 单页面
│       ├── index.wxml / index.wxss / index.js / index.json
└── tests/
    └── todo.test.js       # 云函数零依赖单元测试
```

## 运行步骤

1. 打开[微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) → 导入项目 → 选择本目录
2. `project.config.json` 中的 `appid` 改为你的真实 AppID（当前为 `touristappid` 测试号）
3. 开通云开发（工具栏「云开发」→ 按量付费），创建环境
4. 把 `app.js` 中 `wx.cloud.init` 的 `env` 改成你的环境 ID
5. 云开发控制台建集合 `todos`，权限设为「仅管理端可读写」（前端 SDK 全部禁读写，数据只走云函数，见教程安全建议）
6. 右键 `cloudfunctions/todo` →「上传并部署：云端安装依赖」
7. 编译运行；用两个微信号扫码预览可验证数据隔离（每个用户只见自己的待办）

## 与教程的一致性

本工程的代码与 [实战篇](../../docs/06-实战/01-待办清单实战.md) 完全一致，教程中的每个知识点都能在本工程对应到代码位置。

- 云函数 `todo`：action 分发（list/add/toggle/remove）+ `OPENID` 归属校验 + 输入校验
- 页面 `index.js`：setData 数据流、callFunction 封装、事件处理、`clientToken` 幂等键
- 安全：所有写操作带 `openid` 条件，集合权限设「仅管理端可读写」，双保险
- 幂等：同一 `OPENID + clientToken` 派生确定性 `_id`，重试不产生重复待办
- 日志：`cloud.logger()` 记录 `openidHash` 与事件字段，不落明文 openid、标题、幂等键

## 单元测试

云函数 `todo` 带零依赖单元测试（node 内置 test runner，无需安装 npm 包）：

```bash
node --test "examples/todo-miniprogram/tests/*.test.js"
```

测试通过拦截 `require('wx-server-sdk')` 注入内存数据库 mock，验证 15 个行为：

- `add`：合法标题写入 `OPENID`、`clientToken`、title、done、createTime；标题 trim
- `add`：空/超 100 字/非字符串标题抛「标题不合法」；非法幂等键抛「幂等键不合法」
- `add`：忽略 `payload.openid` 伪造；同一用户同一 `clientToken` 只写一条；不同用户同 token 互不影响
- `list`：只返回当前用户的数据，按 done 过滤，createTime 倒序
- `toggle` / `remove`：**写操作条件必须含 `openid`**（权限隔离——只能改/删自己的记录）
- 身份缺失：没有 `OPENID` 时拒绝服务
- 日志：结构化字段可检索，且不含明文 openid、标题、幂等键
- 未知 `action`：抛错并记 warn 日志

测试不改业务代码，与教程代码逐行一致；CI 每次 push 自动运行。mock 的 `getWXContext()` 返回官方大写字段 `OPENID`，避免小写字段在测试里被掩盖。

## 修改提示

- 换环境：只改 `app.js` 的 `env`
- 换集合：改 `cloudfunctions/todo/index.js` 里的 `db.collection('todos')`
