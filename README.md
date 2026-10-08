# 小程序开发之路

![CI](https://github.com/zhuguang-ZFG/xiaochengxu/actions/workflows/check.yml/badge.svg)

> 仿照「[通往 AGI 之路（WayToAGI）](https://www.waytoagi.com/)」知识库模式，把分散的微信小程序知识组织成一条人人都能走、也能一起修的路。
> 让更多人少走弯路，因小程序而强大。

![小程序开发之路知识库总览](docs/assets/hero-knowledge.png)

本知识库是**开源共建**的微信小程序原生开发教程：从认识小程序、搭建开发环境，到 WXML/WXSS/JS 三件套、组件化、云开发，最后上线发布。每篇文章独立可读，代码可直接复现，事实链接官方文档。

## 学习路径

按「认知 → 理解 → 应用 → 实战 → 发布」五个阶段组织，与 [docs/00-学习路线/01-学习路径总览.md](docs/00-学习路线/01-学习路径总览.md) 对应：

```mermaid
flowchart LR
    A[认识小程序<br/>是什么·生态·适用场景] --> B[环境准备<br/>注册账号·开发者工具]
    B --> C[项目结构<br/>app.json·页面四件套]
    C --> D[基础三件套<br/>WXML·WXSS·JS逻辑层]
    D --> E[进阶能力<br/>组件·网络·性能·媒体·授权·分享]
    E --> F[云开发<br/>云函数·云数据库·云存储]
    F --> G[实战项目<br/>完整案例]
    G --> H[上线发布<br/>体验版·审核·发布]
```

| 阶段 | 文章 | 说明 |
|---|---|---|
| 认知 | [认识小程序](docs/01-入门/01-认识小程序.md) | 小程序是什么，与 H5/原生 App 的差别 |
| 认知 | [编程语言与技术栈](docs/01-入门/04-编程语言与技术栈.md) | 四种语言（JS/WXML/WXSS/JSON）如何分工协作 |
| 准备 | [环境准备](docs/01-入门/02-环境准备.md) | 注册账号、安装开发者工具、跑通 Hello World |
| 结构 | [项目结构](docs/01-入门/03-项目结构.md) | 全局配置与页面四件套 |
| 基础 | [WXML 数据绑定与渲染](docs/02-基础/01-WXML数据绑定与渲染.md) | 视图层语法：绑定、条件、列表 |
| 基础 | [WXSS 样式与 rpx](docs/02-基础/02-WXSS样式与rpx.md) | 响应式样式单位与布局 |
| 基础 | [JS 逻辑层与数据驱动](docs/02-基础/03-JS逻辑层与数据驱动.md) | setData 数据流、模块化 |
| 基础 | [页面生命周期与事件](docs/02-基础/04-页面生命周期与事件.md) | 页面/应用生命周期、事件系统 |
| 进阶 | [内置组件](docs/03-进阶/01-内置组件.md) | 高频组件速查 |
| 进阶 | [自定义组件](docs/03-进阶/02-自定义组件.md) | Component 构造器、组件通信 |
| 进阶 | [网络请求与数据](docs/03-进阶/03-网络请求与数据.md) | wx.request、本地存储、登录态 |
| 进阶 | [性能优化](docs/03-进阶/04-性能优化.md) | 数据更新算法、setData 军规、分包、长列表 |
| 进阶 | [媒体能力](docs/03-进阶/05-媒体能力.md) | 选图/拍照/录音、临时文件机制、上传持久化 |
| 进阶 | [地图与定位](docs/03-进阶/06-地图与定位.md) | getLocation、map 组件、坐标系机制 |
| 进阶 | [授权与隐私](docs/03-进阶/07-授权与隐私.md) | scope 模型、隐私指引、头像昵称填写 |
| 进阶 | [分享与订阅消息](docs/03-进阶/08-分享与订阅消息.md) | 转发/朋友圈、订阅授权模型 |
| 进阶 | [Skyline 与适配](docs/03-进阶/09-Skyline与适配.md) | 渲染引擎机制、safe-area 与刘海屏 |
| 进阶 | [第三方组件库](docs/03-进阶/10-第三方组件库.md) | vant/TDesign、npm 构建机制、按需引入 |
| 进阶 | [调试与排错](docs/03-进阶/11-调试与排错.md) | 面板地图、真机调试与 vConsole、线上错误监控 |
| 进阶 | [微信支付](docs/03-进阶/12-微信支付.md) | 云调用接入、requestPayment、回调幂等与退款 |
| 云开发 | [云开发入门](docs/04-云开发/01-云开发入门.md) | Serverless 后端能力全景 |
| 云开发 | [云函数](docs/04-云开发/02-云函数.md) | 后端逻辑、身份获取、定时触发 |
| 云开发 | [云数据库](docs/04-云开发/03-云数据库.md) | 集合文档、权限、增删改查 |
| 云开发 | [云存储](docs/04-云开发/04-云存储.md) | 上传下载、临时链接、配额与安全 |
| 发布 | [上线发布](docs/05-发布/01-上线发布.md) | 体验版、审核、发布与回退 |
| 实战 | [实战项目](docs/06-实战/01-待办清单实战.md) | 完整端到端案例 |
| 资源 | [资源与工具](docs/07-资源/01-资源与工具.md) | 官方文档、社区、常用工具 |

## 如何阅读

- **零基础起步**：按上表从上往下读，每篇末尾的「验证」小节做完再进入下一篇。
- **查速查**：直接看对应分类文章；`内置组件`、`WXSS` 等篇章按速查风格组织；找 API 先看 [API 速查索引](docs/00-学习路线/02-API速查索引.md)。
- **进阶目标**：读完「进阶」十一篇 + 「云开发」四篇后，跟随实战项目做一遍完整上线。

## 项目结构

```text
.
├── README.md               # 总览：学习路径 + 文章索引 + 仓库规模
├── CHANGELOG.md            # 版本历史（Keep a Changelog 风格）
├── CONTRIBUTING.md         # 贡献指南（写作规范 + 提 PR 自查清单）
├── LICENSE
├── .github/
│   ├── ISSUE_TEMPLATE/     # 纠错报告 / 新增文章模板
│   └── workflows/check.yml # CI：仓库一致性校验
├── docs/                   # 知识库正文
│   ├── 00-学习路线/         # 学习路径总览 + API 速查索引
│   ├── 01-入门/ … 07-资源/  # 教学链 27 篇（教学顺序见 README 表格）
│   ├── _契约.md            # 写作契约（元数据/结构/视觉资产/深度要求）
│   └── assets/             # 43 个视觉资产 + videos/ 教学视频（脚本生成，勿手改）
├── examples/
│   └── todo-miniprogram/   # 可运行示例工程（对应实战篇）
└── tools/                  # 资产生成（render/gen_animations/gen_statics/gen_diagrams/gen_videos）
                            # 校验：check_repo.py + check_assets_fresh.py + 三者各自的自测
                            # data/wx-api-names.txt：官方 API 名单（校验 API 真实性用，脚本抓取）
```

## 参与共建

本知识库与 WayToAGI 一样，是开放共建项目。贡献方式：

1. **提纠错**：发现错误、过期信息，提 issue 说明文章与问题。
2. **写文章**：遵循 [docs/_契约.md](docs/_契约.md)（元数据 schema、结构、风格），`write` 后提 PR。
3. **补案例**：在「实战」分类下新增完整项目教程。
4. **改视觉资产**：所有动画/示意图由 `tools/` 下脚本程序化生成（2x 超采样渲染管线 + 补间动画），改脚本重跑即可，见 [docs/_契约.md](docs/_契约.md) 的「视觉资产的生成」一节。

写作规范、元数据格式与命名规则见 [docs/_契约.md](docs/_契约.md)；完整贡献流程与提 PR 自查清单见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 内容范围

- ✅ 微信小程序**原生开发**（WXML/WXSS/JS + 微信开发者工具）
- ✅ 云开发（CloudBase：云函数/云数据库/云存储/云托管）
- ✅ **第三方组件库**（vant-weapp / TDesign，见[进阶篇](docs/03-进阶/10-第三方组件库.md)）
- ✅ 上线发布与运营基础
- ✅ **微信支付**（云开发云调用接入，见[进阶篇](docs/03-进阶/12-微信支付.md)）
- ❌ 跨端框架（Taro、uni-app 等）不在当前范围（可另行共建）
- ❌ 微信小游戏不在当前范围

## 仓库规模

| 指标 | 数值 |
|---|---|
| 教程文章 | 29 篇（学习路线 2 篇 + 入门/基础/进阶/云开发/发布/实战/资源 27 篇教学链） |
| 视觉资产 | 43 个（34 动画 GIF + 9 示意图 PNG），全部可脚本复现，CI 逐字节比对 |
| 教学视频 | 3 集（`docs/assets/videos/`，720×1280 竖屏 MP4，含字幕帧，由脚本生成） |
| 示例工程 | `examples/todo-miniprogram`（可运行，对应实战篇） |
| 自动校验 | 链接/元数据/序号/孤儿资产/GIF 与视频体积/代码块语言/交叉引用顺序/示例工程结构/实战篇与示例工程逐行一致/**API 真实性**（每个 `wx.*` 对照官方名单），见 CI（外链 HTTP 校验为本地可选：`python tools/check_repo.py --external`） |
| 资产复现校验 | `tools/check_assets_fresh.py` 清空 `docs/assets/` 重跑四个生成脚本，要求与 HEAD 逐字节一致（CI 在 windows-latest 上跑，1m50s） |

## 示例工程

[examples/todo-miniprogram](examples/todo-miniprogram/) 是可运行的完整工程（待办清单，对应[实战篇](docs/06-实战/01-待办清单实战.md)）：导入微信开发者工具 + 开通云开发即可跑通，代码与教程逐行对应。

## 质量保障

- **CI 校验**：每次 push/PR 自动运行 [tools/check_repo.py](tools/check_repo.py)（链接断链、元数据、目录序号、孤儿资产、GIF/视频体积上限、代码块语言、交叉引用顺序、实战篇与示例工程逐行一致、API 真实性）+ 示例工程 JS 语法检查与云函数单元测试，见 [.github/workflows/check.yml](.github/workflows/check.yml)
- **API 真实性**：正文与示例代码里出现的每个 `wx.<name>` 都要在 [tools/data/wx-api-names.txt](tools/data/wx-api-names.txt)（抓自官方 API 索引页，504 个）里，拼错或虚构的接口名直接红——本库曾把一个 npm 包的能力当成 `wx.` 接口收进速查索引
- **资产复现校验**：另有一个 CI job 清空 `docs/assets/` 重跑全部生成脚本，要求与仓库内容逐字节一致——「改了脚本忘了重跑」或「手工改了 GIF」都会红。跑在 windows 上是因为字体解析（见 [docs/_契约.md](docs/_契约.md)）
- **校验器自测**：[tools/test_check_repo.py](tools/test_check_repo.py) 用迷你仓库夹具反证校验逻辑本身有效（30 用例）；[tools/test_assets_fresh.py](tools/test_assets_fresh.py) 守护资产比对「以 HEAD 为基准」这一属性（8 用例）；[tools/test_mutations.py](tools/test_mutations.py) 把已知缺陷还原成变异体验证自测确实会变红（16/16 捕获）——防止出现「校验静默失效、CI 依旧全绿」
- 本地可随时运行 `python tools/check_repo.py` 自查

## 教学视频

`docs/assets/videos/` 下有 3 集竖屏教学视频（720×1280、24fps、H.264，单集 ≤ 300KB），由 `python tools/gen_videos.py` 程序化生成——含字幕帧，不需要录音或录屏：

| 集 | 主题 | 时长 | 对应文章 |
|---|---|---|---|
| 第 1 集 | 学习路径导览 | 60 秒 | [学习路径总览](docs/00-学习路线/01-学习路径总览.md) |
| 第 2 集 | 认识小程序 | 75 秒 | [认识小程序](docs/01-入门/01-认识小程序.md) |
| 第 3 集 | 环境准备 | 75 秒 | [环境准备](docs/01-入门/02-环境准备.md) |

GitHub 渲染仓库 Markdown 时会过滤 `<video>` 标签，因此文章内以**引用块 + 链接**形式给出，点击后由 GitHub 内置播放器播放（见 [docs/_契约.md](docs/_契约.md) 的「视觉资产规范」）。

## 参考

- 官方文档：[微信开放文档 · 小程序](https://developers.weixin.qq.com/miniprogram/dev/framework/)（深度阅读清单见[资源篇](docs/07-资源/01-资源与工具.md)）
- 官方源码：[wechat-miniprogram](https://github.com/wechat-miniprogram)（组件扩展、API Promise 化等官方工程）
- 参考模式：[通往 AGI 之路](https://www.waytoagi.com/) · [WayToAGI_Documents](https://github.com/WayToAGI/WayToAGI_Documents)

## License

见 [LICENSE](LICENSE)。
