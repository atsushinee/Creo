# DESIGN.md — Creo Design System

Creo 的 UI Design System。所有前端改动必须遵守本文档。

设计参考：[Apple DESIGN.md — VoltAgent awesome-design-md](https://github.com/VoltAgent/awesome-design-md)。**不是复制 Apple UI**，而是吸收其设计原则，并针对 Agent UI 做调整。

---

## 1. 设计原则

Creo 的核心风格：

```text
Apple visual restraint
+ Linear information density
+ AI Agent native interaction
+ Professional creative workspace
```

关键词：

```text
Quiet · Precise · Creative · Intelligent · Editorial · Professional · Minimal
```

原则：

- **克制**：UI Chrome 退后，内容（对话、代码、结果）成为视觉主体。
- **大留白**：靠间距而不是线框划分区域。
- **清晰层级**：一眼分清「用户输入 / Agent 过程 / 最终答案」。
- **单一强调色**：只有一个品牌主色，语义色不得抢夺主视觉。
- **精细 Typography**：字体栈、字号、行高有明确刻度。
- **少装饰**：少量阴影、无渐变滥用、无发光。

### 绝对不要做成

- ❌ ChatGPT clone
- ❌ SaaS dashboard
- ❌ 大面积渐变 / Neon AI / 发光边框
- ❌ 玻璃拟态滥用 / 巨型圆角卡片
- ❌ AI 机器人插画 / 彩色背景
- ❌ 到处阴影 / 复杂动画

---

## 2. 色彩

### Token 定义

| Token | Light | Dark | 用途 |
| --- | --- | --- | --- |
| `--background` | `#FFFFFF` | `#000000` | 页面背景 |
| `--surface` | `#F5F5F7` | `#1C1C1E` | 侧栏、代码块、次级面板 |
| `--surface-raised` | `#FFFFFF` | `#2C2C2E` | 浮层、工具卡片 |
| `--foreground` | `#1D1D1F` | `#F5F5F7` | 主文本 |
| `--muted-foreground` | `#6E6E73` | `#A1A1A6` | 次要文本、占位符、时间戳 |
| `--border` | `#E5E5E7` | `#2C2C2E` | 分隔线、描边 |
| `--primary` | `#0066CC` | `#2997FF` | **唯一品牌主色**：发送按钮、链接、激活态、Focus Ring |
| `--primary-foreground` | `#FFFFFF` | `#FFFFFF` | 主色之上的文字 |
| `--success` | `#34C759` | `#30D158` | 工具成功（仅小图标） |
| `--warning` | `#FF9F0A` | `#FF9F0A` | 警告 |
| `--error` | `#FF3B30` | `#FF453A` | 错误、工具失败 |

规则：

- **不引入第二个品牌主色。**
- 语义色（success / warning / error）只用于状态指示，不做大面积填充。
- Dark 模式下背景为纯黑（Apple 风格），面板用 `#1C1C1E` / `#2C2C2E` 抬升层级。

---

## 3. Typography

### 字体栈

```css
/* UI 与正文 */
system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text",
"Inter", "Segoe UI", sans-serif;

/* 代码 */
"SF Mono", "JetBrains Mono", Menlo, Monaco, Consolas, monospace;
```

### 字号刻度

| 用途 | 字号 | 行高 | 字重 |
| --- | --- | --- | --- |
| 应用标题（Header「Creo」） | 15px | 1.4 | 600 |
| 消息正文 | 14px | 1.65 | 400 |
| 侧栏 / 辅助文本 | 13px | 1.5 | 400 |
| 工具卡参数 / 结果 | 12.5px | 1.6 | 400（mono） |
| 标签（NEW、工具名） | 11–12px | 1.4 | 500–600 |

- 正文不使用两端对齐。
- Markdown 标题从 `h1` 起按 1.4em / 1.25em / 1.1em 递减，不超过正文 1.4 倍（编辑感，不是文档站）。

---

## 4. 布局

```text
┌──────────────────────────────────────────────┐
│ Header  h-12（48px）                          │
├───────────────┬──────────────────────────────┤
│ Sidebar w-64  │  Workspace（消息主列）         │
│ (256px)       │  max-w-3xl 居中               │
├───────────────┴──────────────────────────────┤
│ Composer（固定底部，随内容增高）                │
└──────────────────────────────────────────────┘
```

- 右侧 Context Panel **默认不显示**，只在需要时出现（当前阶段不实现）。
- 消息主列 `max-w-3xl mx-auto`，保证编辑感行宽。
- 小屏（< 768px）侧栏隐藏。

---

## 5. 组件规范

### 用户消息

- 右对齐的浅色气泡：`bg-surface`，圆角 12px（角落 4px），无描边。
- 不使用头像。

### Agent 消息（助手）

- **无气泡**，纯文本排版（内容是主体）。
- 一次 Run 的输出聚合成一条消息，内部按顺序混排文本块与工具卡片。

### Tool Call 卡片（一等公民）

- 默认折叠为一行：状态图标 + 工具名。
- 状态必须可视化：
  - `running`：旋转 spinner + 工具名
  - `success`：绿色 check + 工具名
  - `error`：红色 X + 工具名（结果以红色调显示）
- 展开后显示 **Arguments** 与 **Result** 两段，mono 字体，圆角内嵌面板。
- 卡片：`bg-surface`（dark: `surface-raised`）、1px border、圆角 10px。
- **不能把 Tool Call 隐藏在普通文本流里。**

### Agent 状态行（Thinking）

- 不显示模型私有 Chain-of-Thought。
- 只显示高层状态：`Thinking…` / `Running calculator…` / `Preparing result…`
- 样式：muted-foreground + 呼吸动画的点，前缀小 spinner。

### Composer（输入区）

- 底部固定，圆角 12px，1px border，聚焦时 primary 色 ring。
- 右下角发送按钮：圆形，`bg-primary`，ArrowUp 图标；流式进行中变为 Stop（方块图标）。
- 占位符：`Ask Creo anything…`

### 空状态

- 居中「Creo」字标 + 一句副标题 + 3 个安静的建议提示（描边小按钮）。

### 错误横幅

- 1px `--error` 描边 + 8% 透明度背景，红点 + 错误文案，可关闭。

---

## 6. 形状 · 阴影 · 动效

| Token | 值 | 用途 |
| --- | --- | --- |
| 圆角 | 4 / 6 / 8 / 10 / 12px | 小控件 → 卡片 → 气泡；**禁止 > 16px 的巨型圆角** |
| 阴影 | 仅一层：`0 1px 2px rgb(0 0 0 / 0.05)` | 浮层与弹起元素；平面元素不用阴影 |
| 动效 | 120–180ms · ease-out | 仅用于：hover、展开/收起、消息淡入、spinner |

- 不使用弹跳、视差、发光、大型过渡动画。
- 尊重 `prefers-reduced-motion`。

---

## 7. 代码块

- 独立卡片：`bg-surface` + 1px border + 圆角 8px。
- 头部：左侧语言标签（11px mono 大写），右侧复制按钮（点击后短暂变为 Check）。
- 语法高亮使用克制的低饱和配色（`highlight.js` token 自定义，明暗两套），**不使用彩虹色**。
- 横向滚动，行高 1.6。
