# 更新日志

本仓库遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 风格；版本号遵循语义化版本。

> 版本说明：`v1.0.0` 为未打标签的构建期快照（内容对应提交 `6a323fd`）；自 `v1.1.0` 起正式发布 GitHub Release。

## [v1.1.0] - 2026-10-08

### 新增

- **教学视频**：`docs/assets/videos/` 3 集竖屏 MP4（720×1280 / 24fps / H.264 / 单集 ≤ 291KB），由新增的 `tools/gen_videos.py` 程序化生成——场景脚本 + 字幕帧 + ffmpeg 合成，无需录音录屏
  - 第 1 集《学习路径导览》(60s) → 学习路径总览；第 2 集《认识小程序》(75s) → 认识小程序；第 3 集《环境准备》(75s) → 环境准备
- 新增 `check_video_assets()` 校验：`video-*.mp4` 命名规范 + 3MB 体积上限

### 修复

- **`check_repo.py` 四处静默失效**（校验不报错、CI 绿灯，但检查根本没生效）：
  - **孤儿资产检查漏掉子目录**：`ASSETS.iterdir()` 不递归，新增的 `videos/*.mp4` 从未被检查。改为 `rglob("*")`
  - **根目录文档完全不在扫描范围**：只有 `README.md` 被硬编码进扫描列表，`CONTRIBUTING.md`／`CHANGELOG.md` 的断链无人校验。新增 `all_md_files()` 统一覆盖
  - **契约/CONTRIBUTING 里的「用法示例」被当成真实链接**：例如 `![说明](../assets/screen-hello.png)`、`../assets/videos/video-NN-slug.mp4` 是格式示范而非引用，直接扩大会产生成片误报。新增 `strip_code()` 先剥围栏代码块再剥行内代码
  - **围栏正则锚定行首**：CommonMark 允许围栏缩进 ≤3 空格，契约把示例围栏写在列表项里（缩进 2 空格）因而配不上对。全库 360 个围栏中有 2 个被漏检，`strip_code()` 与 `check_fences_language()` 一并修正
- **`check_repo.py` 在 Windows 上必然崩溃**：`print("✅ ...")` 触发 `UnicodeEncodeError`（GBK 控制台无法编码 emoji），使校验"实际全绿却以 traceback 非零退出"。stdout 统一切 UTF-8
- **字体路径写死 Windows**：`render.py` 的 `C:\Windows\Fonts\msyh.ttc` 使资产在 macOS/Linux 上无法复现，与契约「改脚本重跑即可」矛盾。改为按平台顺序查找（微软雅黑 → 苹方 → Noto CJK → 文泉驿），粗体缺失时退化常规体，均不存在时报错并给出安装命令；`load_font` 加 `lru_cache`。已验证重构前后渲染输出**像素级一致**
- **`gen_videos.py` 内存爆炸导致后两集从未生成**：每集先把 1440~1800 帧全量存入列表，720×1280 RGB 单帧 2.7MB，峰值约 5GB 内存（实测只能产出第 1 集）。改为生成器 `yield` + ffmpeg `rawvideo` 管道逐帧流式写入，峰值内存降至数帧，同时省去上千个 PNG 临时文件；并补上失败时回读 ffmpeg stderr、超 3MB 契约上限即报错退出
- `gen_videos.py` 清理死代码（`stages`/`stage_pts`/`round_card`/未用颜色常量）、字幕换行不再产生空行
- 取消跟踪误提交的编译产物 `tools/__pycache__/render.cpython-313.pyc`（已跟踪文件会绕过 `.gitignore`）

### 新增（校验器自测）

- `tools/test_check_repo.py`：16 个用例，用迷你仓库夹具反证校验逻辑本身有效（孤儿递归、根目录断链、代码块示例误报、缩进围栏语言标注、视频命名与体积、`strip_code` 行为）
- `tools/test_mutations.py`：把 4 个已修复缺陷逐条还原成变异体，确认自测确实变红（4/4 捕获），证明自测不是碰巧全绿
- 两者均接入 CI；`CONTRIBUTING.md` 增补「改动校验器须跑自测+变异测试」的自查项

### 变更

- `README.md`：新增「教学视频」小节、仓库规模行与校验器自测说明；`docs/_契约.md` 补充视频引用方式（GitHub 过滤 `<video>` 标签，必须用引用块 + 链接而非 `![]()` 内嵌）与字体/流式渲染约束
- `.gitattributes`：`*.mp4 binary`（不做换行符转换）

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
