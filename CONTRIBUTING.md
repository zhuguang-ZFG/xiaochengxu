# 贡献指南

欢迎共建「小程序开发之路」。这是一个仿照「通往 AGI 之路（WayToAGI）」模式的开源知识库：**学习路径 + 分类文章 + README 索引**，每篇文章独立可读、代码可复现、事实链接官方文档。

## 你可以做什么

| 方式 | 入口 | 说明 |
|---|---|---|
| 提纠错 | [纠错报告模板](.github/ISSUE_TEMPLATE/01-bug-report.md) | 发现事实错误、代码示例错误、失效链接、过期信息 |
| 写文章 | [新增文章模板](.github/ISSUE_TEMPLATE/02-article-request.md) | 新增教程或扩展已有文章 |
| 补视觉资产 | `tools/` 脚本 | 所有动画/示意图/教学视频程序化生成，改脚本重跑即可；CI 会重跑并逐字节比对，**手工改资产会被打回** |
| 做工程 | PR | 示例工程、CI 校验、工具脚本 |

## 写作规范（必读）

**提交文章前必须读 [docs/_契约.md](docs/_契约.md)**，核心要求：

- **元数据**：每篇顶部 YAML frontmatter（title/description/category/tags/difficulty/reading_time/updated），category 与所在目录一致
- **结构**：为什么读这篇 → 正文（概念→代码→说明）→ 常见错误/避坑（≥2 条）→ 验证 → 延伸阅读
- **代码**：必须可运行或可直接对照官方；代码块必须标注语言（`js`/`wxml`/`wxss`/`json`/`bash`/`text`）
- **深度**：至少一层「机制与原理 / 为什么 / 边界 / 量化」，禁止停留在 API 罗列
- **事实**：以官方文档为准（https://developers.weixin.qq.com/miniprogram/dev/），数字/版本不确定就链接官方而非猜测
- **交叉引用**：文末「上一篇/下一篇」必须指向 README 教学顺序表中的相邻篇

## 提 PR 前自查

1. 本地跑 `python tools/check_repo.py`（CI 同一套校验）——应全绿
2. 如果你改了 `tools/check_repo.py` 本身：跑 `python tools/test_check_repo.py`（校验器自测）与 `python tools/test_mutations.py`（变异测试）。本仓库已多次出现「校验逻辑静默失效、CI 依旧全绿」的缺陷（孤儿检查不递归、根目录文档不在扫描范围、代码块示例被当成真实链接），改动校验器必须证明它仍能抓到问题，而不只是「跑完没报错」
3. 若新增文章：
   - [ ] README 表格加行（教学顺序 = 表格顺序）
   - [ ] 前后篇的「上一篇/下一篇」交叉引用已更新
   - [ ] 视觉资产（如有）由 `tools/` 脚本生成且 ≤200KB，已在文中引用
   - [ ] [docs/00-学习路线/01-学习路径总览.md](docs/00-学习路线/01-学习路径总览.md) 阶段列表同步
4. 若改动示例工程：`node --check` 全部 JS 通过，且与实战篇代码保持一致——CI 会逐行比对（见[契约「实战篇与示例工程必须逐行一致」](docs/_契约.md#实战篇与示例工程必须逐行一致)）。只贴要点的代码块须在标题或上文标注「要点/节选」，否则按全文比对会报漂移
5. 若新增/修改教学视频：`python tools/gen_videos.py` 重新生成，确认单集 ≤3MB、`video-*.mp4` 命名；引用必须用**引用块 + 链接**（`> 📺 配套视频 · 第 N 集：[…](../assets/videos/video-NN-slug.mp4)`），**不要用 `![]()` 内嵌**——GitHub 会过滤 `<video>` 标签，`![]()` 引用 mp4 会显示为坏图
6. 若改了任何资产生成脚本（`render.py` / `gen_*.py`）：**必须重跑生成并连同资产一起提交**。CI 的 `assets` job 会清空 `docs/assets/` 重跑四个脚本，然后要求 `git status` 干净——漏提交、手工改过的资产都会红。本地自查：`python tools/check_assets_fresh.py`（要求工作区干净，会清空并重新生成 `docs/assets/`，可 `git checkout -- docs/assets` 还原）
7. 可选：`python tools/check_repo.py --external` 全量外链 HTTP 校验

## 提交信息规范

`<type>: <摘要>`

- `feat:` 新文章/新资产/新功能
- `fix:` 事实错误/代码错误/断链
- `refine:` 精品化（核验、审计、格式统一）
- 摘要用中文，概括「改了什么、为什么」，可带 2-4 行正文说明证据

## 需要帮助？

- 看 [docs/00-学习路线/01-学习路径总览.md](docs/00-学习路线/01-学习路径总览.md) 了解内容组织
- 看 [README](README.md) 了解仓库概览
- 在 issue 里 @ 维护者，或直接提 PR 说明意图
