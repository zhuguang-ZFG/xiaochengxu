# 更新日志

本仓库遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 风格；版本号遵循语义化版本（截至当前为构建期快照，未发布正式 release）。

## [v1.0.0] - 2026-10-08

### 新增

- **内容库**：29 篇文档（学习路径 2 篇 + 教学链 27 篇），覆盖认知/入门/基础/进阶/云开发/发布/实战/资源全链路
  - 进阶新增《调试与排错》《微信支付》（云调用接入/回调幂等/退款）
  - 新增《wx.API 速查索引》：40+ API 按能力域速查矩阵
- **视觉资产**：43 个（34 动画 GIF + 9 示意图 PNG），全部由 `tools/` 脚本程序化生成（2x 超采样 + 真补间），单文件 ≤200KB
- **示例工程**：`examples/todo-miniprogram` 可运行完整工程（待办清单 + 云函数），代码与实战篇逐行对应；**云函数单元测试**（node:test + mock wx-server-sdk，零依赖，7 用例覆盖增删改查与 openid 权限隔离）
- **CI**：`.github/workflows/check.yml`——链接/元数据/序号/孤儿资产/GIF 体积/代码块语言标注/交叉引用顺序/示例工程结构/JSON/JS 语法 + **云函数单元测试**
- **共建入口**：`.github/ISSUE_TEMPLATE`（纠错报告 / 新增文章两类模板）、`CONTRIBUTING.md` 贡献指南、`CHANGELOG.md`、`.gitattributes`（LF 归一化）

### 校验强化

- 代码块语言标注硬校验（契约「代码块必须标注语言」转 CI 门槛），历史 16 处示意图补标 `text`
- 交叉引用自动校验：教学顺序（README 表格）与每篇「上一篇/下一篇」一致性，修复 9 处历史断链
- 外链 HTTP 状态校验（`--external` 可选开关，本地/需要时启用，CI 默认不跑避免外部网络波动）

### 修复

- Skyline 篇 worklet 动画代码虚构 API（`animate(...)` 签名不存在）→ 改为官方 `wx.worklet.runOnUI` 写法 + 双引擎区分说明
- 性能篇 `onPageScroll` 节流 `_lastTop` 未初始化导致的 NaN 永不触发 bug
- 支付篇回调云函数返回协议（官方要求 `{ errcode: 0, errmsg: '' }`）、回调入参字段（v2 通知参数）、`refund` 必填 `outRefundNo`
- 官方事实核验：`getUserProfile` 授权弹窗行为、录音 format 合法值、Skyline 兼容表口径
- 失效外链：云开发计费页（404→新路径）、飞书 wiki（302 循环→GitHub 仓库）、Skyline 组件差异/WXSS、云存储 API 路径等 7 处

## [v0.x] - 2026-10-07

- 从零搭建：内容库骨架（25 篇）→ 动画全覆盖 → 共享调色板渲染管线 → CI + 示例工程 → 6 篇薄弱知识点补全 → 精品化轮（事实核验/交叉引用审计/组件库文章）
