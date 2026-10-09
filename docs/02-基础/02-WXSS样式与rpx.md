---
title: WXSS 样式与 rpx
description: WXSS 响应式单位 rpx、选择器、flex 布局、样式导入与全局/页面样式隔离，速查式教程
category: 基础
tags: [WXSS, rpx, flex, 布局]
difficulty: ★★☆☆☆
reading_time: 20 分钟
updated: 2026-10-07
---

# WXSS 样式与 rpx

## 为什么读这篇

WXSS（WeiXin Style Sheets）是 CSS 的小程序方言：语法与 CSS 一致，但引入了 **rpx 响应式单位**，并规定了全局/页面样式的作用域规则。会写 CSS 的话这篇可作速查；不会的话这是你写页面样式的第一课。

前置知识：[WXML 数据绑定与渲染](../02-基础/01-WXML数据绑定与渲染.md)；基本 CSS 概念（选择器、盒模型）。

## rpx：响应式单位

rpx（responsive pixel）是小程序的核心长度单位。规则一句话：

> **任何屏幕宽度 = 750rpx**。

### 为什么基准是 750 而不是 100

rpx 的设计沿用了早期移动端「以 375px 逻辑宽（iPhone 6）为设计稿基准」的惯例：375px 是当年事实上的设计标准，`750 = 375 × 2` 恰好等于 iPhone 6 的物理像素宽，于是设计稿按 750 画（1:1 物理像素），开发时 1rpx ≈ 1px 直觉成立。

推导出的换算公式（对你写代码有用的唯一一条）：

```text
rpx 值 = px 值 × 750 ÷ 屏幕逻辑宽
```

- 屏幕逻辑宽 375px → `750rpx = 375px`（1rpx = 0.5px）
- 屏幕逻辑宽 390px → `750rpx = 390px`（1rpx ≈ 0.52px）

rpx 之所以**等比缩放**，是因为渲染层拿到 rpx 后按当前屏幕宽度实时换算成 px；同样的 750rpx 在窄屏上换算出的 px 少、在宽屏上多，但**占屏宽比例恒为 100%**。相比之下 px 是绝对单位，不会缩放——这就是「布局用 rpx、固定细节用 px」的机制依据。

- iPhone 6（375px 逻辑宽）：`1px = 2rpx`
- 全面屏手机（如 390px 逻辑宽）：`1px ≈ 1.95rpx`

所以用 rpx 写尺寸，**同一套代码在不同宽度机型上自动等比缩放**，无需媒体查询。

```css
.container {
  width: 750rpx;        /* 撑满全屏 */
  padding: 32rpx;
}
.card {
  width: 690rpx;        /* 常见留白卡片：750 - 2*30 */
  height: 200rpx;
  font-size: 32rpx;
}
```

### 单位对比

rpx 响应式演示（渲染示意图动画：同一套 750rpx 代码在 375px 与 390px 逻辑宽机型上等比铺满，无需媒体查询）：

![rpx 响应式演示](../assets/demo-rpx.gif)

| 单位 | 含义 | 特点 | 建议场景 |
|---|---|---|---|
| rpx | 屏幕宽 1/750 | 自适应缩放 | **布局、字号、间距的主力单位** |
| px | 物理无关的 CSS 像素 | 固定不缩放 | 1px 边框、固定小元素 |
| vw/vh | 视口宽/高百分比 | 跟随视口 | 全屏容器、吸顶栏 |
| % | 父容器百分比 | 跟随父级 | 常规布局 |
| rem | 根字号倍数 | 小程序里不常用 | 一般不用 |

经验：**默认用 rpx，需要「固定不随机型缩放」的细节（如 1px 分隔线）用 px**。

## 选择器

WXSS 支持的选择器比 CSS 少，常用这些：

| 选择器 | 示例 | 说明 |
|---|---|---|
| 类 | `.card` | 最常用 |
| ID | `#title` | 尽量少用 |
| 标签 | `view` | 作用于所有同类组件 |
| 后代 | `.card .title` | 后代选择 |
| 伪类 | `::after`、`:active` | 支持一部分 |

**不支持**：属性选择器 `[data-x]`、`*` 通配符（部分版本）、兄弟选择器等高级选择器。样式中少依赖复杂选择器，多用 class。

```css
/* 合法示例 */
.card { border-radius: 16rpx; }
.card .title { font-weight: bold; }
.button:active { opacity: 0.7; }
```

### 为什么 WXSS 只支持 CSS 子集：渲染机制

浏览器有完整的 CSS 引擎（Blink/WebKit），能解析全部 CSS 选择器和属性。小程序的渲染层不是浏览器——它运行在微信客户端内置的渲染引擎里，这个引擎为了**启动速度**和**包体积**只实现了 CSS 的一个子集。

具体影响链路：

```text
WXSS 文件 → 编译层解析 → 生成样式规则 JSON → 传给渲染层
                                                  ↓
                              渲染层按规则匹配组件树（Shadow Tree）
```

渲染层的样式匹配算法是**按选择器类型分发的**：class 选择器走哈希表 O(1) 查找，标签选择器走标签名映射，后代选择器走祖先链遍历。而属性选择器 `[data-x="y"]` 需要遍历每个组件的所有属性再匹配正则——这在移动端组件数量大时性能代价高，所以渲染层直接不支持。

这就是为什么「多用 class」不仅是编码习惯，而是**配合渲染层的数据结构选型**。理解了这个机制，你就能推断哪些选择器可能被支持：凡是能 O(1) 或 O(log n) 匹配的（class、ID、标签、后代），支持；需要遍历或正则的（属性、通配、正则伪类），不支持。

## flex 布局：小程序布局主力

小程序页面基本用 flex 完成 90% 的布局。三个必会属性：

```css
.row {
  display: flex;              /* 横向排列 */
  align-items: center;        /* 垂直居中 */
  justify-content: space-between; /* 主轴分布 */
  gap: 20rpx;                 /* 间距（较新基础库支持，不确定时用 margin） */
}
.column {
  display: flex;
  flex-direction: column;     /* 纵向排列 */
}
.flex-1 {
  flex: 1;                    /* 占据剩余空间 */
}
```

### 为什么 flex 是主力而不是 float / position

浏览器时代布局方案很多（float、position、table、inline-block、flex、grid），但小程序渲染层**对 float 和 position 的支持非常有限**：

| 布局方式 | 浏览器 | 小程序渲染层 | 原因 |
|---|---|---|---|
| flex | ✅ | ✅ **推荐** | 声明式、单向数据流，渲染层可一次性计算布局 |
| float | ✅ | ⚠️ 部分支持 | float 需要脱离文档流再回绕，渲染层实现复杂且行为不一致 |
| position: absolute | ✅ | ⚠️ 仅相对定位 | 绝对定位需要脱离文档流，在小程序双线程模型下跨线程同步坐标开销大 |
| position: fixed | ✅ | ⚠️ 仅吸顶/吸底 | 同上，且 fixed 在 scroll-view 内行为不可预期 |
| grid | ✅ | ❌ 不支持 | 二维布局计算复杂，渲染层未实现 |

核心原因：小程序是**双线程架构**（逻辑层 + 渲染层分离），布局计算全在渲染层完成。flex 布局是**单遍线性扫描**即可完成的（主轴→交叉轴两趟），而 float 需要多次回流（reflow）、position 需要坐标系同步——这些在双线程间通信的开销下性能差。

所以写小程序布局的心法是：**能 flex 就 flex，需要固定位置用 sticky 或小程序原生组件（如 scroll-view 的 sticky-header）**。

典型布局：顶部导航 + 底部操作栏 + 中间滚动区。

```css
.page {
  display: flex;
  flex-direction: column;
  height: 100vh;
}
.content {
  flex: 1;                    /* 中间自适应 */
  overflow-y: auto;
}
.footer {
  height: 100rpx;
}
```

```wxml
<view class="page">
  <view class="content">滚动内容</view>
  <view class="footer">底部按钮</view>
</view>
```

## 样式导入：@import

公共样式抽成文件，用 `@import` 引入（注意结尾分号，路径相对当前文件）：

```css
/* app.wxss */
@import "styles/common.wxss";
```

```css
/* styles/common.wxss */
.btn-primary {
  background: #07c160;
  color: #fff;
  border-radius: 12rpx;
}
```

## 全局样式与页面样式隔离

三条规则：

1. **app.wxss 全局生效**：所有页面可用，适合 reset 与公共类
2. **页面 wxss 仅本页生效**：不影响其他页面（这点与普通 CSS 不同，天然隔离）
3. **同名规则优先级**：页面样式优先于全局样式（后加载者胜出，页面 wxss 后于 app.wxss 加载）

自定义组件内另有**样式隔离**规则（默认组件内样式不影响外部、外部也不影响组件内），见 [自定义组件](../03-进阶/02-自定义组件.md)。

### 样式隔离的实现机制：编译期作用域

浏览器里所有 CSS 是全局的——两个页面写了同名 `.card` 会互相污染，必须靠 BEM/模块化 手动规避。小程序的页面样式隔离是**框架在编译期自动做的**：

```text
页面 WXML + WXSS
      ↓ 编译
  WXSS 中每条规则的选择器被加上页面级前缀
      ↓
  渲染层收到的实际规则：
    .card { ... }  →  page-index .card { ... }
```

每个页面的 WXML 根节点在渲染层会被包裹一个页面级容器（类似 `page-index`），编译期给该页面的 WXSS 选择器都加上这个前缀后，样式就**只能匹配到本页组件树内的节点**——这就是天然隔离的原理。

所以你在 `pages/index/index.wxss` 里写 `.card`，不会影响到 `pages/detail/detail.wxss` 里的 `.card`，因为编译后它们实际上是不同的选择器。

**这个机制的边界**：app.wxss 不加页面前缀（它是全局的），所以 app.wxss 里的 `.card` 会匹配所有页面的 `.card`。页面 wxss 的同名规则之所以能覆盖，是因为页面样式后加载、选择器优先级相同时后者胜出——不是因为它更"具体"。

## 常见错误 / 避坑

1. **rpx 与 px 混用想当然**：写了 `width: 375px` 的意图可能是「一半屏」，但不同机型结果完全不同；布局尺寸一律 rpx，px 只留给固定细节。
2. **flex 忘写 `flex-direction` 或容器没高度**：`justify-content` 是主轴（默认水平）对齐，想纵向分布要先 `flex-direction: column`；flex 布局中高度塌陷时检查父容器高度。
3. **`gap` 依赖基础库版本**：低版本基础库不认 `gap`，间距用 margin 更保险（margin 注意最后一个元素的边距问题）。
4. **选择器写复杂导致样式不生效**：属性选择器、`>` 子选择器在部分环境失效，换成 class 组合。
5. **页面样式「没生效」其实是全局覆盖**：如果 app.wxss 和页面 wxss 都有 `.card`，想覆盖必须保证选择器优先级相同或更高；用更具体的 class 命名（`.detail-card`）规避。
6. **rpx 在 Skyline 下的差异**：Skyline 渲染引擎（基础库 ≥ 3.0.2、客户端 ≥ 8.0.40）对部分 CSS 能力支持不同，迁移时用官方 [Skyline 迁移指南](https://developers.weixin.qq.com/miniprogram/dev/framework/runtime/skyline/migration/best-practice.html) 检查。

## 随堂测验

**Q1**: 小红用 rpx 写了一个 `width: 375rpx` 的卡片。在 iPhone 6（375px 逻辑宽）上它恰好占半屏。当她换到一台 390px 逻辑宽的全面屏手机时，这个卡片占屏宽的比例会怎么变化？
- [ ] A. 变小，因为 375rpx 换算出的 px 值在宽屏上更小
- [ ] B. 不变，仍然占半屏，因为任何屏幕宽度都等于 750rpx，375rpx 恒为 50%
- [ ] C. 变大，因为屏幕更宽了
- [ ] D. 无法确定，取决于手机型号

<details><summary>答案</summary>

**B**. rpx 的核心规则是「任何屏幕宽度 = 750rpx」，所以 375rpx 在任何机型上都恰好占屏宽的 50%；渲染层会按当前屏幕宽度实时等比换算 rpx 到 px，这就是响应式的原理。

</details>

**Q2**: 小明想写一个「顶部导航 + 中间内容区自适应 + 底部操作栏」的页面布局。以下哪种方案最合适？
- [ ] A. 用 px 写死每个区域的高度
- [ ] B. 用 flex 布局，容器 `flex-direction: column` + `height: 100vh`，中间内容区 `flex: 1` 占据剩余空间
- [ ] C. 用 `position: fixed` 固定所有区域
- [ ] D. 用 float 布局实现三栏

<details><summary>答案</summary>

**B**. flex 是小程序布局的主力方案：纵向容器用 `flex-direction: column`，中间区域设 `flex: 1` 自动填满剩余空间，顶栏和底栏用固定高度——这是小程序中最常见的页面骨架写法。

</details>

**Q3**: 小红在 `app.wxss` 里定义了 `.title { color: red; }`，又在 `pages/index/index.wxss` 里定义了 `.title { color: blue; }`。在 index 页面中，一个 `class="title"` 的 view 文字会显示什么颜色？
- [ ] A. 红色，因为全局样式优先级最高
- [ ] B. 蓝色，因为页面样式优先于全局样式
- [ ] C. 紫色，两种颜色混合
- [ ] D. 黑色，样式冲突导致都不生效

<details><summary>答案</summary>

**B**. 同名规则下页面 wxss 优先于 app.wxss 全局样式（页面样式后加载，覆盖全局），所以文字显示蓝色。

</details>

**Q4**: 小明在项目中写了 `.card[data-type="vip"] { ... }` 的样式规则，但在模拟器中发现样式没有生效。最可能的原因是什么？
- [ ] A. WXSS 不支持属性选择器，应选择器改为 class 组合（如 `.card-vip`）
- [ ] B. data-type 的值拼写错误
- [ ] C. `.card` 组件不支持自定义样式
- [ ] D. 需要加 `!important` 才能生效

<details><summary>答案</summary>

**A**. WXSS 支持的选择器是 CSS 的子集，属性选择器 `[data-x]`、通配符 `*` 等高级选择器不被支持或支持不完整；样式不生效时应先检查选择器是否在支持范围内，改用 class 组合（如 `.card-vip`）是最稳妥的方案。

</details>

## 验证

- [ ] 用 rpx 写出一个「上中下」布局：顶栏 + 自适应中部 + 底栏
- [ ] 用 flex 实现横向导航（3 个按钮均匀分布）与纵向卡片列表
- [ ] 抽一个 `common.wxss` 放公共按钮样式，在页面 `@import` 使用
- [ ] 在 app.wxss 和页面 wxss 里同时定义同名 class，验证页面优先规则
- [ ] 换不同机型模拟器查看布局是否等比缩放

## 延伸阅读

- 本库上一篇：[WXML 数据绑定与渲染](../02-基础/01-WXML数据绑定与渲染.md)
- 本库下一篇：[JS 逻辑层与数据驱动](../02-基础/03-JS逻辑层与数据驱动.md)
- 官方：[WXSS 样式](https://developers.weixin.qq.com/miniprogram/dev/framework/view/wxss.html)
- 官方：[Skyline 渲染引擎迁移](https://developers.weixin.qq.com/miniprogram/dev/framework/runtime/skyline/migration/best-practice.html)