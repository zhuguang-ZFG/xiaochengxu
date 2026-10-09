---
title: WXML 数据绑定与渲染
description: WXML 核心语法：数据绑定、条件渲染、列表渲染、block 与模板，含完整代码示例
category: 基础
tags: [WXML, 数据绑定, 渲染, 模板]
difficulty: ★★☆☆☆
reading_time: 20 分钟
updated: 2026-10-07
---

# WXML 数据绑定与渲染

## 为什么读这篇

WXML（WeiXin Markup Language）是小程序的视图层语言，负责「把 JS 数据渲染成界面」。它与 HTML 最大的区别：**不支持操作 DOM，只做声明式数据绑定**——你声明数据和结构的映射关系，数据变了视图自动更新。这篇覆盖 WXML 最核心的四块：数据绑定、条件渲染、列表渲染、模板复用。

前置知识：[项目结构](../01-入门/03-项目结构.md) 页面四件套；基础 JS 语法。

> 📺 配套视频 · 第 4 集：[《WXML 数据绑定》](../assets/videos/video-04-wxml.mp4)（75 秒 · 竖屏 720×1280）——数据绑定、条件渲染、列表渲染的核心机制动画演示。点击在 GitHub 内置播放器打开（仓库 Markdown 不支持内嵌播放器）。

## 数据绑定：`{{}}`

WXML 用双花括号把 JS 的 `data` 绑定到视图。**任何想动态显示的内容都必须走 `{{}}`**，这是小程序数据驱动的根基（数据流详解见 [JS 逻辑层与数据驱动](../02-基础/03-JS逻辑层与数据驱动.md)）。

### 绑定文本

**index.js**

```js
Page({
  data: {
    name: '小明',
    score: 88,
    isVip: true
  }
})
```

**index.wxml**

```wxml
<view>{{name}}</view>
<view>我的分数：{{score}}</view>
<view>会员状态：{{isVip ? '是' : '否'}}</view>
```

### 绑定属性

```wxml
<image src="{{userAvatar}}" mode="aspectFill"></image>
<view class="{{isVip ? 'vip' : 'normal'}}">内容</view>
<button disabled="{{!isVip}}">按钮</button>
```

注意：**组件属性值里出现 `{{}}`，整个属性值会被当作绑定表达式解析**。所以布尔值、数字不能省略花括号，`disabled="{{true}}"` 是布尔 true，而 `disabled="true"` 是字符串 "true"。

### 绑定运算

`{{}}` 内支持有限表达式（不支持语句）：

```wxml
<view>{{score + 1}}</view>
<view>{{score > 90 ? '优秀' : '加油'}}</view>
<view>{{'前缀-' + name}}</view>
<view>{{[1, 2, 3].length}}</view>
```

不支持：变量赋值、函数调用（除非是 WXS 模块，见官方文档）。

## 条件渲染：`wx:if` 系列

### wx:if / wx:elif / wx:else

```wxml
<view wx:if="{{score >= 90}}">优秀</view>
<view wx:elif="{{score >= 60}}">及格</view>
<view wx:else>不及格</view>
```

`wx:if` 是**惰性渲染**：条件为假时节点不创建、不占位。适合切换不频繁、首屏不需要的场景。

### hidden 对比

`wx:if` vs `hidden` 演示（渲染示意图动画：show 切换时 wx:if 节点销毁重建，hidden 节点始终在 DOM 仅隐藏）：

![wx:if 与 hidden 对比演示](../assets/demo-ifhidden.gif)

```xml
<view hidden="{{!isVip}}">VIP 专属内容</view>
```

`hidden` 是**始终渲染、仅控制显示**（相当于 CSS `display:none`）。适合切换频繁的场景（性能更好），但节点一直在。

选择依据：

| 场景 | 用哪个 |
|---|---|
| 首次就不需要、条件很少变化 | `wx:if` |
| 频繁切换显示/隐藏 | `hidden` |
| 列表项内部的条件渲染 | `wx:if`（避免 hidden 造成布局抖动） |

## 列表渲染：`wx:for`

### 基本用法

列表渲染演示（渲染示意图动画：`wx:for` 逐条渲染数组项）：

![wx:for 列表渲染演示](../assets/demo-wxfor.gif)

**index.js**

```js
Page({
  data: {
    todos: [
      { id: 1, text: '学习 WXML' },
      { id: 2, text: '学习 WXSS' },
      { id: 3, text: '写个 demo' }
    ]
  }
})
```

**index.wxml**

```wxml
<view wx:for="{{todos}}" wx:key="id">
  {{index}} - {{item.text}}
</view>
```

- `item`：当前项（默认名，可用 `wx:for-item` 改名）
- `index`：当前下标（默认名，可用 `wx:for-index` 改名）

### 为什么必须写 wx:key

`wx:key` 重要性演示（渲染示意图动画：无 wx:key 时列表重排节点复用旧文字错乱，有 wx:key 后按 id 精确复用）：

![wx:key 重要性演示](../assets/demo-wxkey.gif)

`wx:key` 给每个列表项一个稳定标识，让渲染层在数据变化时**复用已有节点**而不是全量重建：

```wxml
<view wx:for="{{todos}}" wx:key="id">{{item.text}}</view>
```

- 数组元素是对象：`wx:key="唯一字段名"`（如上 `id`）
- 数组元素是字符串/数字：`wx:key="*this"`

**不写 wx:key**：列表数据增删/重排时可能复用错误节点，出现渲染错乱，且在 Console 有警告。这是新手最常见的坑。

### 嵌套列表

```wxml
<view wx:for="{{groups}}" wx:for-item="group" wx:for-index="gIndex" wx:key="id">
  <text>{{gIndex}}.{{group.name}}</text>
  <view wx:for="{{group.items}}" wx:for-item="item" wx:key="id">
    - {{item.title}}
  </view>
</view>
```

内层必须改名（`wx:for-item`），否则与外层 `item` 冲突。

### 为什么 wx:key 能决定性能：渲染机制

WXML 不是「读一行渲染一行」，真实链路是：

```text
WXML 模板 ──编译期──▶ 模板函数 + 数据绑定映射表
                          │
    JS data --setData-->  │ 数据更新算法（diff）
                          ▼
                    Shadow 树（渲染层节点树）──▶ 界面
```

三个推论，直接解释前文的规则：

1. **`{{}}` 表达式在编译期被定位**。计算尽量在 JS 里做完再放进 data——不只是风格，也影响更新算法能否走「免遍历」快路径。
2. **`wx:if`/`wx:for` 会改变节点结构**，使所在子树的字段更新**无法**命中免遍历的绑定映射表算法，退化为遍历整棵树（见 [性能优化](../03-进阶/04-性能优化.md) 的数据更新算法）。列表项的字段更新比普通节点更贵。
3. **`wx:key` 是 diff 的锚点**。有稳定 key，节点重排时被识别为「同一节点移动」而**复用**（只做位移）；无 key 则按位置比对，旧节点可能被套上新数据，导致内容错位。

第 3 点的隐蔽后果：**列表项内若有 `input`、`switch` 等带内部状态的组件，缺 `wx:key` 会让状态跟着「位置」走而不是跟着「数据」走**——比渲染错乱更难排查。

## block：无实体容器

`<block>` 不产生真实节点，只用来包裹条件/循环逻辑：

```wxml
<block wx:if="{{isLogin}}">
  <view>欢迎回来</view>
  <view>{{userName}}</view>
</block>

<block wx:for="{{todos}}" wx:key="id">
  <view>{{item.text}}</view>
</block>
```

渲染结果里没有 `<block>` 标签本身，只有内部节点——需要同时渲染多个节点又不能加包裹层时用。

## 模板复用：template

### 定义与引用

**定义模板（如 templates/item.wxml）**

```wxml
<template name="todoItem">
  <view class="todo-item">
    <text>{{text}}</text>
    <text class="status">{{done ? '已完成' : '未完成'}}</text>
  </view>
</template>
```

**使用模板**

```wxml
<import src="../../templates/item.wxml" />
<template is="todoItem" data="{{text: item.text, done: item.done}}" />
```

要点：

- `import` 引入模板文件；`template is` 指定名字；`data` 传参（**必须显式传**，模板不能访问页面 data）
- `import` 有作用域：不能递归引用，且 import 的模板里 import 的模板对当前文件不可见
- 另一种 `include`：把目标文件的**整个内容**原样展开到当前位置（适合公共头部/底部片段），无作用域概念

```wxml
<!-- header.wxml -->
<view class="header">公共头部</view>

<!-- 页面内 -->
<include src="../../templates/header.wxml" />
```

## 常见错误 / 避坑

1. **不写 wx:key**：列表重排/删除后渲染错乱（复用了错误的节点），且 Console 警告。数组对象给 `id`，基本类型给 `*this`。
2. **属性布尔值不带花括号**：`disabled="false"` 是字符串 `"false"`（恒真），必须 `disabled="{{false}}"` 才是布尔 false。这个坑会导致按钮永远不可点。
3. **`{{}}` 里写复杂逻辑**：只支持表达式不支持语句；需要计算就提前在 JS 里算好放进 data，或使用 WXS（详见官方文档）。
4. **template 忘记传 data**：模板里引用的变量不是页面 data 的全局可见，`<template is="xx" />` 不传 `data` 就是空数据，页面无内容且不报错。
5. **hidden 与 wx:if 混用直觉**：hidden 节点始终在 DOM 里，若其中包含高成本子组件，即使 hidden 也仍会初始化，此时应改用 wx:if。

## 随堂测验

**Q1**: 小红写了一个按钮组件，希望根据 `isVip` 的值动态设置 `disabled` 属性。她写了 `disabled="false"`，但发现按钮始终不可点击。正确的写法应该是什么？
- [ ] A. `disabled="disabled-false"`
- [ ] B. `disabled="{{false}}"`，用花括号包裹才能让属性值被当作布尔表达式解析
- [ ] C. `disabled=false`，去掉引号即可
- [ ] D. 小程序不支持动态 disabled，只能用 JS 控制

<details><summary>答案</summary>

**B**. 组件属性值中一旦出现 `{{}}`，整个值会被当作表达式解析；`disabled="{{false}}"` 才是布尔 false，而 `disabled="false"` 是字符串 `"false"`（非空字符串恒真），按钮永远禁用。

</details>

**Q2**: 小明用 `wx:for` 渲染一个待办列表，用户可以删除和重新排序列表项。他没有写 `wx:key`，结果发现删除某一项后，剩余项的文字显示错乱。根本原因是什么？
- [ ] A. `wx:for` 不支持删除操作
- [ ] B. 没有 `wx:key`，渲染层按位置比对节点，旧节点被错误地套上新数据，导致内容错位
- [ ] C. 数组的 `id` 字段重复了
- [ ] D. WXML 不支持动态列表渲染

<details><summary>答案</summary>

**B**. `wx:key` 是 diff 算法的锚点；没有它时渲染层按位置复用节点，列表增删/重排后旧节点会被绑定到新数据上，造成文字错乱——尤其是列表项内有 `input` 等带内部状态的组件时更加隐蔽。

</details>

**Q3**: 一个页面需要显示/隐藏一块 VIP 内容，用户可能频繁切换。以下哪种方案最合适？
- [ ] A. `wx:if="{{isVip}}"`，因为每次切换都会重新创建节点，数据最新
- [ ] B. `hidden="{{!isVip}}"`，因为节点始终在渲染树中，频繁切换时不需要反复创建和销毁节点，性能更好
- [ ] C. 用 JS 手动操作 DOM 来控制显示隐藏
- [ ] D. 每次切换时重新加载整个页面

<details><summary>答案</summary>

**B**. `hidden` 只是切换 CSS `display:none`，节点始终存在于渲染树中，频繁切换时避免了 `wx:if` 反复创建/销毁节点的开销；`wx:if` 更适合条件很少变化或首次就不需要渲染的场景。

</details>

**Q4**: 小红定义了一个 `<template name="todoItem">` 并在页面中用 `<template is="todoItem" />` 使用它，但页面上什么都没显示。最可能的原因是什么？
- [ ] A. template 的 name 拼写错误
- [ ] B. 使用 template 时没有通过 `data` 属性显式传入数据，模板无法访问页面的 data
- [ ] C. template 必须先 `<import>` 才能使用
- [ ] D. 小程序不支持 template 功能

<details><summary>答案</summary>

**B**. 模板有独立作用域，不能直接访问页面 data；使用 `<template is="xxx" />` 时必须通过 `data="{{text: item.text, done: item.done}}"` 显式传入变量，否则模板内变量为空，页面无内容且不报错。

</details>

## 验证

- [ ] 用 `{{}}` 完成：文本绑定、属性绑定（class 切换）、三元运算各一个
- [ ] 用 `wx:for` 渲染一个对象数组，正确设置 `wx:key`
- [ ] 实现「点击按钮切换某个区域显示/隐藏」，分别用 `wx:if` 和 `hidden` 各做一遍，并说明两者差异
- [ ] 用 template 抽出一个列表项模板，在页面中复用两次
- [ ] 故意不写 `wx:key`，在 Console 观察警告，再补上对比渲染行为

## 延伸阅读

- 本库上一篇：[项目结构](../01-入门/03-项目结构.md)
- 本库下一篇：[WXSS 样式与 rpx](../02-基础/02-WXSS样式与rpx.md)
- 官方：[WXML 语法参考](https://developers.weixin.qq.com/miniprogram/dev/reference/wxml/)
- 官方：[WXS 模块（视图层脚本）](https://developers.weixin.qq.com/miniprogram/dev/framework/view/wxs/)