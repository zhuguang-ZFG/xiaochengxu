# -*- coding: utf-8 -*-
"""第 13 集 · 调试与排错。

骨架照 ep02：开场追一个问题 → 9 段正文 → 口诀 → 这一集结束你要留下 → 合上书三问。

内容全部来自 `docs/03-进阶/11-调试与排错.md`（含它自己的 4 道随堂测验），
只做口语化改写，不新增事实。第 6、8 段用 code 展示调用片段（每行 ≤46 字符）。
"""
EPISODE = {
    "id": "13",
    "slug": "debug",
    "title": "调试与排错",
    "article": "docs/03-进阶/11-调试与排错.md",
    "cover_sub": "先看现场 再改代码",
    "segments": [
        {
            "say": "欢迎来到第十三集。代码写对八成，剩下两成时间都在排错。新手三个困境：报错看不懂、"
                   "模拟器正常真机挂了、线上出 bug 拿不到现场。这一集把排错链路完整走一遍。",
            "scene": {"kind": "cover", "title": "调试排错",
                      "sub": "先看现场 再改代码",
                      "points": ["六块面板 · 真机调试 · 线上日志",
                                 "顺序固定 别凭感觉猜"]},
        },
        {
            "say": "先认工具。调试器一共六块面板，最常用这五块：Console 看日志和报错，"
                   "Wxml 看节点树和绑定数据，AppData 是 data 的实时快照、能直接改，"
                   "Network 看请求耗时，Audits 一键体检。",
            "scene": {"kind": "bullets", "head": "六块面板",
                      "items": [["Console", "日志与报错 第一步看它"],
                                ["Wxml", "节点树与绑定数据"],
                                ["AppData", "data 快照 可直接改"],
                                ["Network", "请求 耗时 状态码"],
                                ["Audits", "一键性能体检"]]},
        },
        {
            "say": "排错顺序固定下来，别乱猜：Console 看报错，AppData 验证数据，Wxml 验证渲染，"
                   "Network 验证链路。多数界面没变的 bug，在 AppData 一步就能劈开："
                   "是 data 没变，还是变了没渲染。",
            "scene": {"kind": "flow", "head": "排错顺序",
                      "steps": [["Console", "先看有没有异常"],
                                ["AppData", "再看数据变没变"],
                                ["Wxml", "然后看渲染同步没"],
                                ["Network", "最后看链路通不通"]]},
        },
        {
            "say": "模拟器正常，真机可能挂。四类系统性差异：能力上，部分 API 模拟器不支持；"
                   "性能上，桌面快，低端机才暴露卡顿；网络上，模拟器能勾选跳过域名校验，真机严格校验；"
                   "隐私上，弹窗时机不一样。",
            "scene": {"kind": "bullets", "head": "模拟器不等于真机",
                      "items": [["能力", "部分 API 模拟器不支持"],
                                ["性能", "桌面快 低端机才暴露"],
                                ["网络", "真机严格校验白名单"],
                                ["隐私", "弹窗时机与真机不同"]]},
        },
        {
            "say": "预览二维码只能看，要调试得用真机调试：真机跑起来，工具这边开调试器，"
                   "Console、Network、AppData 全都能查，还能远程调试线上版本。"
                   "真机上看日志，用 vConsole。",
            "scene": {"kind": "phone", "head": "真机调试",
                      "screens": ["debug"]},
        },
        {
            "say": "真机上日志不出来，多半不是代码没跑，是没开 vConsole。"
                   "一行 setEnableDebug 打开，右上角出现小绿标。但发布前务必移除，或者用环境判断关掉，"
                   "它会展示内部日志，还有性能开销。",
            "scene": {"kind": "code", "head": "打开 vConsole",
                      "caption": "app.js",
                      "lines": [["// 真机上 console 不输出 就先开它", "cmt"],
                                ["wx.setEnableDebug({", "kw"],
                                ["  enableDebug: true", "txt"],
                                ["});", "txt"],
                                ["// 发布前移除 或用环境判断包裹", "cmt"]]},
        },
        {
            "say": "感觉卡不能复现，性能要用指标说话。两个入口：一是 Audits 一键审计，"
                   "给出首屏时间、setData 频率、耗时 Top 项；二是自定义上报，"
                   "把关键路径耗时打进性能体系。更细的就订阅测量条目。",
            "scene": {"kind": "bullets", "head": "性能用数字说话",
                      "items": [["一键审计", "Audits 报首屏与耗时 Top"],
                                ["自定义指标", "reportPerformance 上报"],
                                ["更细测量", "getPerformance 订阅"]]},
        },
        {
            "say": "线上 bug 的难点是拿不到现场，所以要有兜底。App 里加 onError 兜未捕获错误，"
                   "加 onUnhandledRejection 兜未处理的 Promise 拒绝，然后主动上报。"
                   "不写这两处，线上出事你什么也收不到。",
            "scene": {"kind": "code", "head": "全局错误兜底",
                      "caption": "app.js",
                      "lines": [["App({", "kw"],
                                ["  onError(err) {", "kw"],
                                ["    console.error('全局错误:', err);", "txt"],
                                ["  },", "txt"],
                                ["  onUnhandledRejection(e) { /* 上报 */ }", "cmt"]]},
        },
        {
            "say": "再加两样。实时日志用 getRealtimeLogManager 写，线上出问题让用户反馈，"
                   "后台能查现场；生产版是按配置抽样，不是全量。还有 sourcemap："
                   "报错只有压缩后的行列号，传上去才能还原源码位置。",
            "scene": {"kind": "bullets", "head": "线上还能拿到两样",
                      "items": [["实时日志", "getRealtimeLogManager 记录"],
                                ["查现场", "后台按用户查 抽样收集"],
                                ["sourcemap", "压缩行列号还原源码"]]},
        },
        {
            "say": "五个坑，记住四个。真机 console 不输出，先确认调试通道，再怀疑逻辑。"
                   "模拟器能请求、真机全失败，是域名没配白名单或者没上 HTTPS。"
                   "AppData 改值无效，是因为你改的是快照。vConsole 千万别留正式版。",
            "scene": {"kind": "bullets", "head": "五个坑",
                      "items": [["没日志", "先确认调试通道 再怀疑逻辑"],
                                ["请求全挂", "真机校验 域名白名单"],
                                ["改值无效", "AppData 改的是快照"],
                                ["泄露", "vConsole 别留正式版"]]},
        },
        {
            "say": "口诀一句：先看现场，再改代码。顺序是固定的：Console、AppData、Wxml、Network，"
                   "一路看下去。感觉不能当证据，性能要用数字，线上要靠兜底和日志。"
                   "排错越早练，后面越省时间。",
            "scene": {"kind": "outro", "head": "口诀",
                      "items": ["先看现场 再改代码"],
                      "next": "顺序固定 别凭感觉猜"},
        },
        {
            "say": "这一集结束，你应该留下三样。第一，一个固定的排错顺序：报错、数据、渲染、链路。"
                   "第二，一套兜底：onError 加上实时日志。第三，一次真机验证：预览扫码，"
                   "打开 vConsole，看见自己打的那条日志。",
            "scene": {"kind": "bullets", "head": "这一集结束 你要留下",
                      "items": [["一个顺序", "报错 数据 渲染 链路"],
                                ["一套兜底", "onError 加实时日志"],
                                ["一次真机", "真机跑通 再看日志"]]},
        },
        {
            "say": "合上书，三问。模拟器正常、真机请求全挂，最可能是什么？AppData 里改的值，"
                   "为什么刷新就没了？线上偶发 bug，靠哪三件套查？"
                   "全系列到这里收官，把这些手艺带走。",
            "scene": {"kind": "outro", "head": "合上书 三问",
                      "items": ["真机请求全挂 先查什么",
                                "AppData 改的值为何消失",
                                "线上偶发 bug 靠哪三件套"],
                      "next": "全系列收官 先看现场 再改代码"},
        },
    ],
}
