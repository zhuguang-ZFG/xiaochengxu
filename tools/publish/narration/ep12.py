# -*- coding: utf-8 -*-
"""第 12 集 · 授权与隐私。

骨架照 ep02：开场追一个问题 → 9 段正文 → 口诀 → 这一集结束你要留下 → 合上书三问。

内容全部来自 `docs/03-进阶/07-授权与隐私.md`（含它自己的 4 道随堂测验）。
合规敏感：只写文章里明确写了的东西——scope 模型、系统弹窗机制、头像昵称填写、
requiredPrivateInfos 与隐私保护指引；不扩展、不推测平台规则。
"""
EPISODE = {
    "id": "12",
    "slug": "auth",
    "title": "授权与隐私",
    "article": "docs/03-进阶/07-授权与隐私.md",
    "cover_sub": "先解释 再发起授权",
    "segments": [
        {
            "say": "欢迎来到第十二集。你肯定撞见过这两种困惑：为什么有时授权能弹框，有时怎么调都不弹？"
                   "为什么头像昵称拿不到了？这一集把授权讲成一张图：权限模型、系统弹窗、"
                   "头像昵称、隐私指引。",
            "scene": {"kind": "cover", "title": "授权与隐私",
                      "sub": "先解释 再发起授权",
                      "points": ["scope 管设备能力 指引管数据用途",
                                 "拒绝是强记忆 只能引导去设置"]},
        },
        {
            "say": "小程序把敏感能力切成一个个 scope，一个 scope 一个开关，各自独立授权、独立记忆。"
                   "位置、录音、相机、相册，各占一个。用户信息也是个 scope，但已经废弃，"
                   "后面单独讲。状态只有三态：已授权、未授权、已拒绝。",
            "scene": {"kind": "bullets", "head": "scope 模型",
                      "items": [["位置", "scope.userLocation"],
                                ["录音", "scope.record"],
                                ["相机", "scope.camera"],
                                ["相册", "scope.writePhotosAlbum"],
                                ["用户信息", "scope.userInfo 已废弃"]]},
        },
        {
            "say": "弹窗有两个反直觉的点。第一，弹窗不是小程序画的，是微信客户端弹的，文案你也改不了，"
                   "想解释用途，只能在自己页面上先说。第二，wx.authorize 只在从没处理过时弹一次。"
                   "点过拒绝，再调就失败，不弹了。",
            "scene": {"kind": "flow", "head": "弹窗三件事",
                      "steps": [["查状态", "getSetting 看授权表"],
                                ["先解释", "自己页面写清用途"],
                                ["发起", "wx.authorize 弹系统框"],
                                ["兜底", "拒绝了引导 openSetting"]]},
        },
        {
            "say": "为什么不让再弹？这是反骚扰。如果每次调用都能弹框，恶意小程序就能拿弹窗轰炸用户。"
                   "微信把选择权完全交给用户，拒绝是强记忆的，表过态的事不再追问。"
                   "代价是引导去设置这一步，你必须做进流程，这是故意留的摩擦。",
            "scene": {"kind": "bullets", "head": "为什么不让再弹",
                      "items": [["防骚扰", "每次都能弹 就会被轰炸"],
                                ["强记忆", "用户表过态 不再追问"],
                                ["代价", "引导去设置 做进流程"],
                                ["故意的", "用摩擦挡住误授权"]]},
        },
        {
            "say": "正确姿势是这个闭环：先 getSetting 查状态，没授权就先在自己页面解释，再调 authorize。"
                   "如果失败，就是之前拒绝过。这时候弹一个自己的弹窗，确认后 openSetting，"
                   "把用户送到设置页手动打开。",
            "scene": {"kind": "code", "head": "正确闭环",
                      "caption": "pages/location/index.js",
                      "lines": [["const s = await wx.getSetting();", "kw"],
                                ["if (!s.authSetting['scope.userLocation']) {", "txt"],
                                ["  await wx.authorize({", "kw"],
                                ["    scope: 'scope.userLocation' });", "str"],
                                ["}  // 失败就说明被拒绝过 → 去设置", "cmt"]]},
        },
        {
            "say": "2023 年 9 月后，隐私接口要过两道关。代码侧在 app.json 声明 requiredPrivateInfos；"
                   "后台侧配用户隐私保护指引。分工不同：scope 管设备能力能不能用，"
                   "隐私指引管数据拿去干嘛。",
            "scene": {"kind": "columns", "head": "两个层面",
                      "cols": [{"title": "scope 授权",
                                "rows": [["管什么", "设备能力能不能用"],
                                         ["时机", "首次处理弹一次"],
                                         ["拒绝后", "不再弹 去设置"],
                                         ["范围", "逐个能力 独立记忆"]]},
                               {"title": "隐私指引",
                                "rows": [["管什么", "数据收集拿去干嘛"],
                                         ["代码侧", "声明隐私接口名"],
                                         ["后台侧", "配置隐私保护指引"],
                                         ["漏配", "privacy 报错"]]}]},
        },
        {
            "say": "报错写得很具体：隐私权限没授权。原因就两个：声明里没写接口，或者后台没配指引。"
                   "修法两步：代码补声明，后台补指引。默认弹窗不够用，"
                   "可以用 onNeedPrivacyAuthorization 接管。",
            "scene": {"kind": "bullets", "head": "必配两处",
                      "items": [["代码侧", "app.json 里声明接口名"],
                                ["后台侧", "配置用户隐私保护指引"],
                                ["漏配后", "privacy permission 报错"],
                                ["不够用", "onNeedPrivacyAuthorization"]]},
        },
        {
            "say": "回到界面上看。用户第一次碰隐私接口，会看到这样的弹窗；同意之后，状态就记在这个 scope 上。"
                   "记住一条产品原则：先在自己的页面把用途写清楚，再发起系统授权。"
                   "别指望系统弹窗替你解释。",
            "scene": {"kind": "phone", "head": "授权弹窗",
                      "screens": ["auth"]},
        },
        {
            "say": "头像昵称：服务器拿不到真实的，只能拿到用户填的。姿势是 chooseAvatar 选头像，"
                   "nickname 输入框填昵称。头像是临时文件路径，得先上传。"
                   "getUserProfile 还在，但每次得用户点。",
            "scene": {"kind": "code", "head": "头像昵称填写",
                      "caption": "pages/profile/profile.wxml",
                      "lines": [["<button open-type=\"chooseAvatar\"", "kw"],
                                ["  bindchooseavatar=\"onAvatar\">", "txt"],
                                ["<input type=\"nickname\"", "kw"],
                                ["  bindblur=\"onNickname\" />", "txt"],
                                ["// avatarUrl 是临时路径 先上传", "cmt"]]},
        },
        {
            "say": "四个坑。照抄旧教程用 getUserInfo，拿不到真头像。拒绝后还反复调 authorize，"
                   "只换来失败。漏配隐私声明，定位相册直接报错。"
                   "openid 和头像昵称混着用，登录校验就废了。",
            "scene": {"kind": "bullets", "head": "四个坑",
                      "items": [["旧教程", "getUserInfo 拿不到真头像"],
                                ["反复调", "拒绝后再 authorize 只失败"],
                                ["漏声明", "定位相册直接报隐私错"],
                                ["混着用", "openid 是身份 昵称是数据"]]},
        },
        {
            "say": "口诀一句：先解释用途，再发起授权。系统弹窗改不了文案，能改的只有你自己页面上那几句话。"
                   "用户拒绝之后，唯一的出路是引导他去设置页开。记住这两句，"
                   "你就不会写出骚扰用户的产品。",
            "scene": {"kind": "outro", "head": "口诀",
                      "items": ["先解释用途 再发起授权"],
                      "next": "弹窗不能改文案 拒绝就引导设置"},
        },
        {
            "say": "这一集结束，你应该留下三样。第一，一张图：scope 管设备能力，隐私指引管数据用途。"
                   "第二，一个闭环：查状态、解释、发起、拒绝了引导设置。第三，一次替换："
                   "把 getUserInfo 那套换掉，改用头像昵称填写。",
            "scene": {"kind": "bullets", "head": "这一集结束 你要留下",
                      "items": [["一张图", "scope 管设备 指引管用途"],
                                ["一个闭环", "查状态 解释 发起 引导"],
                                ["一次替换", "getUserInfo 换成头像填写"]]},
        },
        {
            "say": "合上书，三问。用户拒绝过之后，再调 authorize 还会弹吗？privacy 报错，"
                   "代码侧和后台侧该查哪两处？openid 和头像昵称能互换用途吗？"
                   "下一集讲调试与排错，从六块面板到线上日志。",
            "scene": {"kind": "outro", "head": "合上书 三问",
                      "items": ["拒绝后 authorize 还弹吗",
                                "privacy 报错先查哪两处",
                                "openid 和昵称能互换吗"],
                      "next": "下一集：《调试与排错》 从面板到线上"},
        },
    ],
}
