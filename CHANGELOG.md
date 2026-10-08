# 更新日志

本仓库遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 风格；版本号遵循语义化版本。

> 版本说明：`v1.0.0` 为未打标签的构建期快照（内容对应提交 `6a323fd`）；自 `v1.1.0` 起正式发布 GitHub Release。

## [v1.4.0] - 2026-10-08

### 修复（事实错误，均已对照官方文档核实）

- **实战篇避坑 #6 与示例工程自相矛盾**：教程写「showModal 是回调式 API，用 Promise 包装再 await，否则 `confirm` 拿不到」，而示例工程 `pages/index/index.js` 正是 `await wx.showModal(...)`。官方文档：异步 API 不传 success/fail/complete 时直接返回 Promise（基础库 2.10.2 起），`wx.showModal` 页面明确标注「以 Promise 风格调用：支持」；官方 TypeScript 类型 `PromisifySuccessResult` 编码的就是这条规则。错的是教程不是代码——改为准确的版本条件与两种真正拿不到的情形。逐行一致校验抓不到这个：它只比代码文本，不比正文对代码的断言
- **速查索引收录了不存在的接口 `wx.promisify`**（「官方」列是 `—`，本该是信号）：官方 API 索引页 504 个 `wx.*` 中没有它，三个可能的文档路径全部 404。真实的批量转换方案是官方 npm 包 `miniprogram-api-promise`（`promisifyAll`）。删除该行；Promise 规则移入「用法」一节，对表里每个 API 都适用 <!-- api-ignore -->
- **网络篇把同一个虚构接口写成「微信提供的工具」**，还附带了无法核实的「`util.promisify` 在部分基础库可用」。改为官方原话：`wx.request`/`uploadFile`/`downloadFile`/`connectSocket` 本身有返回值，promisify 需开发者自行封装
- **地图篇手工 `new Promise` 包装 `wx.showModal` 却只处理 success**：fail 触发时 Promise 永不 settle，`await` 挂死。同一段代码两行之上已经在 `await wx.getSetting()`，改为一致的原生 Promise 风格，fail 走外层 try/catch
- `test_check_repo.py` / `test_assets_fresh.py` 的 UTF-8 兜底只切了 stdout，而 unittest 把用例名写到 **stderr**——v1.2.0 声称修掉的「用例名乱码」实际没修到那条流。两个流一起切

### 新增

- **API 真实性校验** `check_api_names()`：正文与示例工程源码里出现的每个一级 `wx.<name>` 必须在 `tools/data/wx-api-names.txt`（`--update-api-list` 抓自官方 API 索引页，504 个）里。这是第二次在库里发现虚构接口（上一次是 Skyline 篇的 worklet `animate()`），链接/语法类检查对此毫无感知。在真实仓库上跑：51 个不同名字，恰好只报出 `wx.promisify` 两处，零误报 <!-- api-ignore -->
  - 名单随工具走而非随仓库走；缺失时显式失败而不是按空名单继续（否则全库真实 API 都被报成虚构）
  - 刷新名单有下限保护：抽到的名字少于 300 个视为抓取失败，拒绝覆盖
  - 只认小写开头（`wx.API 速查索引` 这类标题不误中）；`<!-- api-ignore -->` 行级豁免给反面例子用；明说只校验一级标识符，`wx.cloud.xxx` 只看到 `wx.cloud`
- 契约新增「API 名必须真实存在」一节，并把 Promise 规则写进去——写「X 是回调式要自己包」之前先查这一条；CONTRIBUTING 自查清单同步

### 新增（校验器自测）

- `test_check_repo.py` 补 7 个用例（共 30）：虚构名必报、真实名与 `wx.cloud` 不报、标题不误报、`api-ignore` 豁免、示例工程源码拼错必报、名单缺失显式失败、抓取逻辑
- `test_mutations.py` 补 4 项变异（共 16/16 捕获）：检查形同虚设、正则不限小写、示例工程源码不在范围、名单缺失时静默继续

## [v1.3.0] - 2026-10-08

### 新增

- **资产复现校验**：`tools/check_assets_fresh.py` + CI `assets` job（windows-latest）。契约声称「资产全部程序化生成，改脚本重跑即可」，但此前无任何机制校验——CI 只查已提交文件的体积与命名，从不重新生成，因此「改了脚本忘了重跑」或「手工改了 GIF」这类漂移完全无人发现。现在：先确认 `docs/assets` 相对 HEAD 干净 → **清空目录**重跑四个生成脚本 → `git status` 必须仍干净
  - 三种漂移方向都能报出：内容变化（仓库里是旧版本）、新增未提交、消失（脚本已不再产出）
  - 清空目录这一步不能省：不清空的话，脚本已不再产出的旧资产会原样躺着，git 看不出差别，「生成器删掉某个资产」这个方向永远测不到
  - 必须跑在 windows 上：`render.py` 按平台选字体（微软雅黑/苹方/Noto CJK），同一份脚本在 Linux 上渲染出的像素与已提交资产完全不同——这不是改脚本能绕开的差异
  - 依赖锁 `pillow==12.3.0` + `imageio-ffmpeg==0.6.0`（资产就是这套工具链生成的）
- `tools/test_assets_fresh.py`：8 个用例，重点是**比对基准**——以 HEAD 为基准，而非「重跑前的工作区」

### 修复

- **`ffmpeg` 未锁线程导致视频不可复现**：libx264 的帧级多线程会让同一份输入在不同核数的机器上编出不同字节（实测 1/2/4/8 线程四个哈希全不同），不锁的话 CI 的资产比对会永远失败。`gen_videos.py` 加 `-threads 1`，代价约 +7 秒/集。3 个 MP4 因此重新生成（204/277/298 KB，仍远低于 3MB 上限）
- **生成脚本在 cp1252 控制台崩溃**（CI 首次运行即抓到）：英文版 Windows runner 的 stdout 是 cp1252，无法编码中文，`gen_statics.py` 末尾那句 `print("静态图生成完成…")` 抛 `UnicodeEncodeError`——**资产其实已经写好，脚本却以 traceback 非零退出**。本地是 GBK（能编码中文），所以一直藏着。这是同一问题第三次出现（`check_repo.py`、`test_mutations.py` 之后），根因都是「脚本假设控制台能编码中文」，这次把兜底放进 `render.py` 模块级：四个生成脚本都 import 它，一次覆盖全部，新脚本也自动继承
- CI `validate` job 里的 `pip install pillow` 是死代码（`check_repo.py` 与两个测试脚本都不 import PIL），注释「PIL 供部分检查」属误导，删除

### 新增（校验器自测）

- `test_mutations.py` 改为多目标结构，新增 3 项变异（共 12/12 捕获）：不校验工作区是否干净（漏提交时假通过）、不清空资产目录、生成脚本失败被当成成功
- `test_assets_fresh.py` 接入 CI `validate` job

## [v1.2.0] - 2026-10-08

### 新增

- **`check_example_sync()` 校验：实战篇与示例工程必须逐行一致**。README 与实战篇都写着「代码与教程逐行对应」，但此前无任何机制校验，实测已出现漂移。现在把这句话变成 CI 不变量：正文提到 `todo-miniprogram` 的文档里，未标注「要点/节选」的源码块必须与工程文件逐行一致（忽略缩进与块首文件头注释）
  - 豁免规则：标题或上文含「要点 / 节选 / 片段 / 省略 / 仅列」的块按摘要对待，不参与全等比对；`bash`/`text` 块（操作指令、目录树）也不参与
  - 生效范围限定为「正文提到工程目录名」的文档：入门/基础/进阶各篇同样有 `app.json`、`index.js` 同名代码块，但那是各自独立的教学示例（`我的小程序`、`pages/detail/detail`），按文件名全局匹配会全部误判为漂移
- 契约新增「实战篇与示例工程必须逐行一致」一节；CONTRIBUTING 自查清单同步

### 修复

- **实战篇 `app.json` 缺 `"sitemapLocation": "sitemap.json"`**（示例工程有、教程没有），属上述漂移的首个实例
- **示例工程内的 Markdown 不在扫描范围**：`all_md_files()` 只覆盖 `docs/**` 与根目录，`examples/todo-miniprogram/README.md` 的断链、图片、代码块语言标注全部无人校验（实测其目录树围栏未标语言）。补齐扫描范围，并新增 `reference_md_files()` 供孤儿/外链检查复用（排除写作契约——契约里的 `assets/...` 是格式示例而非引用）
- `tools/test_mutations.py` 在 Windows 上必然崩溃：`print("✅ ...")` 触发 `UnicodeEncodeError`，本地以 traceback 退出。CI 跑在 UTF-8 的 Linux 上，一直掩盖着这个差异（与 `check_repo.py` 早先那个崩溃同源）；`test_check_repo.py` 的用例名乱码一并修掉
- CONTRIBUTING 自查清单序号重复（1,2,2,3,4,5）

### 新增（校验器自测）

- `test_check_repo.py` 补 7 个用例（共 23）：漂移必须报出、逐行一致不报、未引用工程的文章不参与比对、非源码块不参与比对、「要点」块豁免、示例工程 README 的裸围栏与断链必须报出
- `test_mutations.py` 补 5 项变异（共 9/9 捕获）：同步检查形同虚设、按文件名全局匹配、「要点」豁免失效、非源码块也参与比对、示例工程文档不在扫描范围

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
