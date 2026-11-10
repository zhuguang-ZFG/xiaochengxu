# -*- coding: utf-8 -*-
"""第 5 集 · 自定义组件。

骨架照 `D:\\Users\\STM32\\tools\\narration.py` 每章的固定套路：
    开场追一个问题 → 正文分节 → 口诀 → 这一集结束你要留下 → 合上书三问

内容全部来自 `docs/03-进阶/02-自定义组件.md`（含它自己的 4 道随堂测验），
只做口语化改写，不新增事实。

画面文字只用渲染字体画得出的字符（→ ← ↑ ↓ √ × ● ○ ★ ·）。
"""
EPISODE = {
    "id": "05",
    "slug": "component",
    "title": "自定义组件",
    "article": "docs/03-进阶/02-自定义组件.md",
    "cover_sub": "封装界面 · 逻辑 · 样式",
    "segments": [
        {
            "say": "欢迎来到第五集。页面一多，重复的卡片、弹窗、输入框组合就会让代码爆炸。"
                   "这一集解决这件事：把一段界面连同它的逻辑和样式封装成组件，"
                   "父组件传参数，子组件抛事件。链路通了，项目才算有结构。",
            "scene": {"kind": "cover", "title": "自定义组件",
                      "sub": "封装界面 逻辑 样式",
                      "points": ["properties 传参 · triggerEvent 抛事件",
                                 "本集结尾有口诀与三问自测"]},
        },
        {
            "say": "组件和页面几乎一样，也是四件套，只是多一件事：json 里必须写"
                   " component 为 true，工具才认它是组件。忘了这行，"
                   "js 里写 Component 就报错或者行为异常。这是第一个坑。",
            "scene": {"kind": "bullets", "head": "组件也是四件套",
                      "items": [["json", "必须写 component true"],
                                ["wxml", "结构和数据绑定"],
                                ["wxss", "样式 默认不外泄"],
                                ["js", "Component 构造器"],
                                ["易错", "漏了 component 就报错"]]},
        },
        {
            "say": "组件用 Component 包起来，里面三块：properties 收父组件传来的数据，"
                   "要写类型和默认值；data 放内部状态；methods 放方法。"
                   "子组件通知父组件，就在方法里调 triggerEvent。",
            "scene": {"kind": "code", "head": "组件的骨架",
                      "lines": [["Component({", "kw"],
                                ["  properties: { text: { type: String } },", "kw"],
                                ["  data: { count: 0 },", "txt"],
                                ["  methods: {", "kw"],
                                ["    onToggle() {", "txt"],
                                ["      this.triggerEvent('toggle', detail);", "str"],
                                ["    }", "txt"],
                                ["  }", "txt"],
                                ["})", "txt"]],
                      "caption": "todo-item.js"},
        },
        {
            "say": "properties 和 data 的区别，记来源就够了。"
                   "前者是外面传进来的，父组件给新值会自动同步；"
                   "后者是组件自己的状态，只能靠 setData 改。"
                   "在 wxml 里写法一样，差别只在 js 里。",
            "scene": {"kind": "columns", "head": "properties 与 data",
                      "cols": [{"title": "properties",
                                "rows": [["来源", "父组件传入 外部数据"],
                                         ["更新", "父组件传新值 自动同步"],
                                         ["js 里", "this.properties.xxx"],
                                         ["适合", "配置项 展示数据"]]},
                               {"title": "data",
                                "rows": [["来源", "组件自身 内部状态"],
                                         ["更新", "只能 this.setData"],
                                         ["js 里", "this.data.xxx"],
                                         ["适合", "内部交互状态"]]}]},
        },
        {
            "say": "在页面里用组件，两步：json 的 usingComponents 里登记标签名和路径；"
                   "然后在 wxml 里当标签用。标签名必须小写或带横线。"
                   "传参用属性，听事件写 bind 加事件名，全小写最稳。",
            "scene": {"kind": "code", "head": "页面里怎么用",
                      "lines": [["<todo-item wx:for=\"{{todos}}\" wx:key=\"id\"", "kw"],
                                ["  text=\"{{item.text}}\" done=\"{{item.done}}\"", "txt"],
                                ["  bindtoggle=\"onTodoToggle\" />", "kw"],
                                ["", "txt"],
                                ["// 页面事件里取参", "cmt"],
                                ["const { id } = event.currentTarget.dataset;", "txt"],
                                ["const { done } = event.detail;", "txt"]],
                      "caption": "index.wxml / index.js"},
        },
        {
            "say": "父子通信就三条路。properties，父传子，单向；"
                   "triggerEvent，子抛事件，带 detail，父页面 bind 接；"
                   "selectComponent，父拿子实例调方法。推荐单向数据流：数据向下，事件向上。",
            "scene": {"kind": "bullets", "head": "父子通信三条路",
                      "items": [["properties", "父 → 子 单向传数据"],
                                ["triggerEvent", "子 → 父 事件带 detail"],
                                ["selectComponent", "父拿子实例 调它的方法"],
                                ["推荐", "数据向下 事件向上"]]},
        },
        {
            "say": "把一次点击走完：子组件绑 tap，triggerEvent 抛 toggle 带 detail；"
                   "页面用 bindtoggle 接住，detail 里就是数据；"
                   "最后页面 setData，列表和界面跟着变。",
            "scene": {"kind": "flow", "head": "一次点击的链路",
                      "steps": [["子组件 bindtap", "点一下 进 onToggle"],
                                ["triggerEvent", "抛 toggle 带 detail"],
                                ["父页面 bindtoggle", "event.detail 取数据"],
                                ["setData 回传", "新 properties 驱动重渲染"]]},
        },
        {
            "say": "组件生命周期写在 lifetimes 里：created 创建时不能 setData，"
                   "attached 插入页面可以，ready 渲染完成，detached 移除。"
                   "逻辑相同就抽成 behavior 共用。",
            "scene": {"kind": "bullets", "head": "生命周期与复用",
                      "items": [["created", "实例创建 不能 setData"],
                                ["attached", "插入页面 可 setData"],
                                ["ready", "渲染完成 可操作节点"],
                                ["detached", "组件被移除"],
                                ["behaviors", "公共逻辑 多个组件共用"]]},
        },
        {
            "say": "样式默认完全隔离：组件的样式出不去，页面样式进不来。三档："
                   "isolated 完全隔离，apply-shared 外部样式能进组件，shared 双向。"
                   "规范做法是 properties 传 class，别关隔离。",
            "scene": {"kind": "columns", "head": "styleIsolation 三档",
                      "cols": [{"title": "isolated",
                                "rows": [["默认", "完全隔离"],
                                         ["里面", "组件样式不出门"],
                                         ["外面", "页面样式进不来"]]},
                               {"title": "apply-shared",
                                "rows": [["方向", "外部 → 组件"],
                                         ["效果", "页面样式能进来"],
                                         ["组件样式", "仍不影响外部"]]},
                               {"title": "shared",
                                "rows": [["方向", "双向"],
                                         ["效果", "里外都通"],
                                         ["代价", "容易互相误伤"]]}]},
        },
        {
            "say": "隔离不是运行时算的，是编译期做的：给组件每个标签加私有属性，"
                   "给每条选择器加属性前缀。所以运行时改配置不生效。"
                   "页面样式进不去组件，那是正常行为，不是出错。"
                   "坑还有几个：类型不匹配，事件名大小写混用。",
            "scene": {"kind": "bullets", "head": "几个坑 先绕开",
                      "items": [["漏 component", "json 不写 true 组件不工作"],
                                ["类型不匹配", "Number 传字符串 值异常"],
                                ["默认值写错", "数组默认值要用函数返回"],
                                ["事件名大小写", "全小写 bindtoggle 最稳"],
                                ["拿到 null", "id 没写 或还在 wx:if 里"]]},
        },
        {
            "say": "口诀一句：数据向下，事件向上。父组件只管传，子组件只管抛，"
                   "谁的状态谁 setData。守住单向数据流，组件才不会互相改数据改到失控；"
                   "一旦你开始到处 selectComponent，多半是组件边界画错了。",
            "scene": {"kind": "outro", "head": "口诀",
                      "items": ["数据向下 事件向上"],
                      "next": "谁的状态谁 setData → 别互相改"},
        },
        {
            "say": "这一集结束，你要留下三样东西。一，封装一个待办项组件，"
                   "properties 收 text 和 done，点击抛 toggle。二，页面里 wx:for 复用它，"
                   "点击能拿到 id。三，selectComponent 调子组件方法。",
            "scene": {"kind": "bullets", "head": "这一集结束 你要留下",
                      "items": [["封装组件", "properties 收 text 与 done"],
                                ["复用它", "wx:for 渲染 点击拿到 id"],
                                ["拿到实例", "selectComponent 调方法"]]},
        },
        {
            "say": "合上书，三问。页面样式改不动组件内部，为什么？"
                   "子组件抛 toggle，页面该写 bindtoggle 还是 bindToggle？"
                   "数组的默认值为什么必须用函数？下一集：没有服务器，数据存哪。",
            "scene": {"kind": "outro", "head": "合上书 三问",
                      "items": ["页面样式为什么进不去",
                                "bindtoggle 还是 bindToggle",
                                "数组默认值为什么要用函数"],
                      "next": "下一集：《云开发入门》 没有服务器 数据存哪"},
        },
    ],
}
