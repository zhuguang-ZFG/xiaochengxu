# -*- coding: utf-8 -*-
"""第 11 集 · 云函数。

骨架照 ep02：开场追一个问题 → 9 段正文 → 口诀 → 这一集结束你要留下 → 合上书三问。

内容全部来自 `docs/04-云开发/02-云函数.md`（含它自己的 6 道随堂测验），
只做口语化改写，不新增事实；不写文章里没有的实现细节。
"""
EPISODE = {
    "id": "11",
    "slug": "cloudfunc",
    "title": "云函数",
    "article": "docs/04-云开发/02-云函数.md",
    "cover_sub": "小程序之外的后端逻辑",
    "segments": [
        {
            "say": "欢迎来到第十一集。先接住前面那个问题：密钥、聚合、第三方接口，"
                   "这些前端不该做的事，代码到底写在哪儿？答案是云函数。"
                   "这一集讲透四件事：怎么写、怎么调、怎么拿用户身份、怎么定时跑。",
            "scene": {"kind": "cover", "title": "云函数",
                      "sub": "小程序之外的后端逻辑",
                      "points": ["免服务器 · 按调用计费 · 天然打通",
                                 "身份由微信注入 前端伪造不了"]},
        },
        {
            "say": "云函数是跑在腾讯云 Node.js 环境里的代码，不在你的小程序里。"
                   "四个特点：免部署服务器，右键上传就部署；按调用计费，没调用不计费；"
                   "跟小程序天然打通。长连接和超长任务不适合，平台限制执行时长。",
            "scene": {"kind": "bullets", "head": "它是什么",
                      "items": [["免服务器", "右键上传即部署 平台托管"],
                                ["按调用计费", "没调用不计费 免费额度内"],
                                ["天然打通", "callFunction 调用 身份直给"],
                                ["不适合", "长连接 超长任务"]]},
        },
        {
            "say": "链路四步。前端调 callFunction，参数放 data；云函数从 event 里取；"
                   "要数据就操作云数据库；return 的对象回到前端 res.result。"
                   "记住 data 进 event，return 出 result。",
            "scene": {"kind": "flow", "head": "调用链路",
                      "steps": [["小程序端", "wx.cloud.callFunction"],
                                ["云函数", "main 收 event 做逻辑"],
                                ["云数据库", "database 增删改查"],
                                ["回到前端", "return → res.result"]]},
        },
        {
            "say": "最小结构六行。先 require 云开发 SDK，init 时指定跟随调用方环境；"
                   "再导出 main，两个参数：event 收前端传的，context 是运行信息。"
                   "部署只有一个动作，右键上传并部署，有依赖就选云端安装依赖。",
            "scene": {"kind": "code", "head": "最小结构",
                      "caption": "cloudfunctions/getTodoList/index.js",
                      "lines": [["const cloud = require('wx-server-sdk');", "kw"],
                                ["cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })", "txt"],
                                ["exports.main = async (event, context) => {", "kw"],
                                ["  // event 前端参数 context 运行信息", "cmt"],
                                ["  return { code: 0, data: '返回值' };", "txt"],
                                ["}", "txt"]]},
        },
        {
            "say": "两边对照着记。前端传参塞进 data，云函数收在第一个参数 event 里；"
                   "云函数 return 什么，前端就在 res.result 拿到什么。云函数 throw 错误，"
                   "前端走 fail，errMsg 带着信息。",
            "scene": {"kind": "columns", "head": "传参与返回",
                      "cols": [{"title": "小程序端",
                                "rows": [["调用", "callFunction"],
                                         ["传参", "塞进 data"],
                                         ["取返回", "res.result"],
                                         ["报错", "走 fail 回调"]]},
                               {"title": "云函数端",
                                "rows": [["入口", "exports.main"],
                                         ["收参", "event"],
                                         ["返回", "return 纯对象"],
                                         ["身份", "getWXContext"]]}]},
        },
        {
            "say": "云函数里免鉴权就能拿到当前用户。一行 getWXContext，openid 就是用户唯一标识，"
                   "写库时存它，查询只查自己的，不用再走 login 换 code 那一套。"
                   "openid 伪造不了，因为它是微信侧注入的。",
            "scene": {"kind": "bullets", "head": "拿用户身份",
                      "items": [["openid", "用户唯一标识 云函数里拿"],
                                ["免登录", "不用 login 换 code"],
                                ["伪造不了", "openid 由微信侧注入"],
                                ["定时触发", "openid 为空 没有用户"]]},
        },
        {
            "say": "云函数跑在临时容器里，不是常驻服务。空闲五到十分钟，容器就被回收，"
                   "下次请求要冷启动，通常两百到八百毫秒，热路径不到五毫秒。"
                   "所以 require 和 init 全放 main 外面，只在冷启动执行一次，连接也放顶层。",
            "scene": {"kind": "bullets", "head": "冷启动与容器",
                      "items": [["回收", "空闲 5-10 分钟 容器被回收"],
                                ["顶层", "init 与 require 只跑一次"],
                                ["量化", "冷启动 200-800ms"],
                                ["优化", "少顶层依赖 连接放顶层"]]},
        },
        {
            "say": "云函数还能定时跑，比如每日统计、定时清理。函数目录建 config.json，"
                   "写 triggers，类型 timer，cron 七段：秒分时日月周年。"
                   "触发器改完要重新部署，定时触发时 openid 为空。",
            "scene": {"kind": "code", "head": "定时触发器",
                      "caption": "cloudfunctions/stat/config.json",
                      "lines": [["{", "txt"],
                                ["  \"triggers\": [{", "txt"],
                                ["    \"name\": \"dailyStat\",", "str"],
                                ["    \"type\": \"timer\",", "txt"],
                                ["    \"config\": \"0 0 3 * * * *\"", "str"],
                                ["  }]", "txt"]]},
        },
        {
            "say": "三个典型场景。第一，聚合统计：小程序端不能跨集合 join，聚合也受限，"
                   "复杂统计放云函数。第二，代理第三方接口：云函数没有域名白名单限制，"
                   "密钥还能藏在里面。第三，写库前校验：长度内容先过一遍，再入库。",
            "scene": {"kind": "flow", "head": "三个典型场景",
                      "steps": [["聚合统计", "跨集合 join 与聚合"],
                                ["代理三方", "没有域名白名单 藏密钥"],
                                ["写前校验", "敏感写操作先校验"]]},
        },
        {
            "say": "坑先记四条。忘了写 init，函数能跑，一碰数据库就报环境错误。"
                   "return 了 undefined 或者函数，前端 res.result 直接异常。"
                   "超时默认三秒，可配到二十秒，超时容器被强制终止，finally 都不执行。",
            "scene": {"kind": "bullets", "head": "六个坑 先记四条",
                      "items": [["忘 init", "第一行不 init 数据操作报错"],
                                ["返回怪东西", "return undefined 前端拿不到"],
                                ["超时", "默认 3s 可配 20s 后强杀"],
                                ["触发器", "改了 config 要重新部署"]]},
        },
        {
            "say": "口诀一句：前端只负责展示，可信都在云端。密钥、聚合、敏感校验这三样，"
                   "天生该在云函数里。反过来看，云函数不是万能：长连接、超长任务别往里塞。"
                   "判断标准就一条：这段代码能不能被前端看见。",
            "scene": {"kind": "outro", "head": "口诀",
                      "items": ["前端只负责展示 可信都在云端"],
                      "next": "密钥 聚合 校验 三样往云函数搬"},
        },
        {
            "say": "这一集结束，你应该留下三样。第一，能写出最小云函数：init 在顶层，"
                   "main 返回对象。第二，能说清一次调用：data 进 event，"
                   "return 出 result，throw 走 fail。第三，能判断一段逻辑该不该上云。",
            "scene": {"kind": "bullets", "head": "这一集结束 你要留下",
                      "items": [["最小结构", "init 顶层 main 返回纯对象"],
                                ["一次调用", "data 进 event result 出"],
                                ["一个判断", "密钥 聚合 校验 上云"]]},
        },
        {
            "say": "合上书，三问。忘了 cloud.init，云函数会怎样？前端 data 里传的 x，"
                   "云函数从哪儿取？定时触发器跑起来时，openid 是什么值？"
                   "下一集讲授权与隐私，那个让新手最困惑的系统。",
            "scene": {"kind": "outro", "head": "合上书 三问",
                      "items": ["忘了 init 会报什么错",
                                "data 里的 x 云函数怎么取",
                                "定时触发时 openid 是什么"],
                      "next": "下一集：《授权与隐私》 scope 与弹窗"},
        },
    ],
}
