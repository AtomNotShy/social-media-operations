# 前端设计系统

本文档保留完整设计目标。当前共享组件和验收状态以[前端实现状态](./implementation-status.md)为准。

## 1. 视觉方向

工作台采用安静、克制、信息密度适中的桌面工具风格：

- 大面积中性背景。
- 白色内容面板。
- 蓝色作为主要操作和当前选择。
- 爆款等级是页面中最强的业务颜色。
- 状态颜色只表达状态，不作为装饰。
- 阴影轻，主要依靠边框、间距和层级组织信息。

参考截图用于确定产品气质，但组件必须基于统一 Token 实现，不能逐页复制样式。

## 2. Design Tokens

Tailwind CSS v4 使用 CSS-first `@theme` 定义 Token。下例是语义结构，不是最终品牌色锁定：

```css
@import "tailwindcss";

@theme {
  --font-sans:
    "Inter", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei",
    system-ui, sans-serif;

  --color-canvas: oklch(0.975 0.004 255);
  --color-surface: oklch(1 0 0);
  --color-surface-subtle: oklch(0.96 0.005 255);
  --color-border: oklch(0.90 0.008 255);
  --color-text: oklch(0.20 0.015 255);
  --color-text-muted: oklch(0.52 0.015 255);

  --color-primary-50: oklch(0.96 0.025 255);
  --color-primary-500: oklch(0.62 0.19 255);
  --color-primary-600: oklch(0.55 0.20 255);
  --color-primary-700: oklch(0.48 0.18 255);

  --color-grade-t1: oklch(0.58 0.23 28);
  --color-grade-t2: oklch(0.70 0.18 55);
  --color-grade-t3: oklch(0.78 0.16 82);
  --color-success: oklch(0.62 0.16 150);
  --color-warning: oklch(0.74 0.16 75);
  --color-danger: oklch(0.58 0.23 28);

  --radius-sm: 0.5rem;
  --radius-md: 0.75rem;
  --radius-lg: 1rem;
  --radius-xl: 1.25rem;

  --shadow-panel: 0 1px 2px rgb(15 23 42 / 0.04);
  --shadow-popover:
    0 12px 36px rgb(15 23 42 / 0.12),
    0 2px 8px rgb(15 23 42 / 0.06);

  --breakpoint-compact: 48rem;
  --breakpoint-workbench: 80rem;
  --breakpoint-wide: 100rem;
}
```

页面组件只使用语义 Token，禁止直接散落品牌十六进制颜色。

## 3. 颜色语义

### 中性色

| Token | 用途 |
|---|---|
| Canvas | 应用背景 |
| Surface | 卡片、面板、弹窗 |
| Surface Subtle | 筛选区、分段控件、Skeleton |
| Border | 边界 |
| Text | 主文字 |
| Text Muted | 辅助信息 |

### 业务状态

| 状态 | 颜色 | 要求 |
|---|---|---|
| T1 现象级 | 红 | 只用于等级与关键数字 |
| T2 爆款 | 橙 | 不作为普通警告色 |
| T3 小爆 | 琥珀 | 与 Warning 保持形态差异 |
| 成功 | 绿 | 同步完成、保存成功 |
| 警告 | 黄/橙 | 预算接近、部分数据 |
| 错误 | 红 | 失败、危险操作 |
| 处理中 | 蓝 | Running、Syncing |
| 普通/归档 | 灰 | Ordinary、Archived |

颜色不是唯一信号，必须同时显示文字、图标或形状。

## 4. 排版

### 字体

- 中文正文优先系统中文无衬线。
- 数字和英文可使用 Inter。
- 不加载过多字重。
- 指标数字使用 Tabular Numerals，避免跳动。

### 层级

| 用途 | 建议 |
|---|---|
| 页面标题 | 32–40 px，Semibold/Bold |
| 区块标题 | 18–22 px，Semibold |
| 卡片标题 | 15–17 px，Semibold |
| 正文 | 14–16 px |
| 辅助信息 | 12–14 px |
| 表格 | 13–14 px |

正文行高至少 1.5。中文长文编辑区建议 16 px 和 1.75 行高。

## 5. 间距与布局

采用 4 px 基础网格：

```text
4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48
```

建议：

- 页面水平 Padding：24–40 px。
- 面板 Padding：16–24 px。
- 卡片间距：16–20 px。
- 表单字段垂直间距：16 px。
- Page Header 与主体：24–32 px。
- 筛选面板与结果：12–16 px。

内容最大宽度由页面决定：

- 数据密集型列表使用全宽。
- 脚本正文限制舒适阅读宽度。
- 设置表单建议 720–880 px。

## 6. App Shell 尺寸

| 元素 | 建议尺寸 |
|---|---|
| 顶部标签栏 | 48–52 px |
| 侧边栏展开 | 240–272 px |
| 侧边栏折叠 | 64–72 px |
| Page Header | 最小 96 px |
| 命令面板 | 最大宽度 680 px |
| 详情 Drawer | 480–720 px |

侧边栏和标签栏使用 Sticky，不让页面长列表把导航滚走。

## 7. 核心组件

### 7.1 Workbench

- `AppShell`
- `WorkspaceSwitcher`
- `SidebarNavigation`
- `WorkbenchTabs`
- `CommandPalette`
- `UserMenu`
- `ConnectionStatus`
- `JobCenterTrigger`

### 7.2 页面结构

- `PageHeader`
- `PageActions`
- `StatsStrip`
- `Section`
- `Panel`
- `SplitPane`
- `StickyActionBar`

### 7.3 导航和筛选

- `SearchInput`
- `FilterBar`
- `FilterPopover`
- `SegmentedControl`
- `Tabs`
- `Breadcrumbs`
- `PaginationCursor`
- `SavedViewPicker`，P3

### 7.4 数据展示

- `DataTable`
- `ContentCard`
- `ProfileCard`
- `Metric`
- `MetricDelta`
- `TrendSparkline`
- `StatusBadge`
- `GradeBadge`
- `PlatformBadge`
- `Tag`
- `TagCloud`
- `Timeline`
- `VersionList`
- `EvidenceList`

### 7.5 反馈

- `Skeleton`
- `EmptyState`
- `ErrorState`
- `PartialDataBanner`
- `InlineAlert`
- `Toast`
- `Progress`
- `JobStatus`
- `BudgetWarning`
- `ConfirmationDialog`

Toast 只表示短暂确认；需要用户处理的问题必须留在页面或任务中心，不能只用 Toast。

### 7.6 表单

- `FormField`
- `TextInput`
- `TextArea`
- `Select`
- `Combobox`
- `DateTimePicker`
- `TagInput`
- `FileDropzone`
- `SubmitBar`
- `UnsavedChangesGuard`

错误文字紧邻字段。提交失败时聚焦第一个错误，同时保留全部输入。

## 8. 灵感卡片

卡片推荐结构：

```text
Cover: 16:9 或平台原比例裁切
Metadata
Title: 最多 2–3 行
Body preview: 最多 2 行
Metrics
Grade / Category / AI Status
```

交互：

- 整卡可打开详情。
- 复选框与更多菜单有独立点击区域。
- Hover 只显示次要操作，不隐藏主要信息。
- 缺失封面时显示稳定占位，不显示破图。
- 指标为 `null` 时显示 `—` 并提供“平台未提供”提示。

## 9. 表格

要求：

- Header Sticky。
- 行选择与打开详情分离。
- 排序状态进入 URL。
- 列配置只存在界面偏好中。
- 大量数据使用服务端分页，不一次加载全部。
- 批量操作条只在有选择时出现。
- 表格空状态放在表格容器内。

移动端不强行压缩所有列，切换成卡片摘要。

## 10. 弹窗、Drawer 与页面

使用原则：

- 简短确认：Dialog。
- 快速创建/编辑：Drawer。
- 需要引用 URL、刷新或复杂编辑：独立页面。
- 不在多层弹窗中打开第三层弹窗。
- 关闭带未保存内容的弹窗前确认。

灵感详情和脚本编辑必须是独立路由，不只使用 Drawer。

## 11. Motion

- 普通过渡 120–200 ms。
- Drawer/Popover 150–220 ms。
- 不使用大幅弹跳。
- 列表刷新不整体闪烁。
- 新数据进入时避免改变用户当前滚动位置。
- 尊重 `prefers-reduced-motion`，通过 `motion-reduce` 禁用非必要动画。

## 12. 明暗模式

当前 P0–P3 只验收浅色模式。Token 必须语义化，为后续暗色模式保留能力，但不为了“支持”暗色模式提交未经完整 QA 的简单反色版本。

P3 若启用暗色模式：

- 使用 `.dark` 或等价应用级模式。
- 所有 Grade、Chart 和媒体遮罩重新检查对比度。
- 用户选择优先，其次系统偏好。

当前 P3 未启用暗色模式。

## 13. 可访问性

最低要求：

- 所有操作可用键盘完成。
- 焦点样式清晰，不移除 Outline。
- Dialog 打开后正确管理焦点。
- 表单字段有可访问名称。
- 图标按钮有文字名称。
- 颜色不是唯一状态信号。
- 图片有恰当 Alt；装饰图使用空 Alt。
- 数据图表提供文字摘要或表格。
- 动态任务状态通过适当的 Live Region 提示，但不频繁打扰。
- 点击目标保持足够尺寸。
- 支持 200% 缩放不丢失主要操作。

## 14. 文案

使用用户语言，不暴露内部实现：

| 避免 | 使用 |
|---|---|
| Hydration | 获取完整详情 |
| Provider Fetch | 数据获取 |
| Endpoint Error | 数据源暂时不可用 |
| Dead Job | 需要人工处理 |
| 409 Conflict | 内容已被其他位置更新 |

诊断信息放在可展开详情中，保留 Error Code 和 Request ID。

## 15. 组件验收

当前已落地的共享基础包括 `PageHeader`、`StatusBadge`、`EmptyState`、`ErrorState`、Workbench Shell，以及生产模块的 Dialog、Metric、InlineError、表单样式和 `SavedViewPicker`。本节其余组件状态是后续组件库验收目标。

每个共享组件至少有：

- Default。
- Hover/Focus/Active。
- Disabled。
- Loading。
- Error。
- Long Chinese Text。
- Missing Data。
- Viewer Permission。
- Compact Width。
- Reduced Motion。
