# 前端信息架构与路由

## 1. 信息架构原则

- 导航按用户工作流组织，不按后端表名组织。
- “自有账号”和“对标账号”保持明确区分。
- 灵感、选题、脚本、内容、排期、复盘形成固定生产顺序。
- 系统任务、费用和设置放在次级导航，不干扰主流程。
- 每个详情页都能回到来源和去往下一步。

## 2. 主导航

```text
工作区
├── 今日
├── 账号与定位
│   ├── 自有账号
│   └── 对标账号
├── 内容生产
│   ├── 选题
│   ├── 内容项目
│   ├── 排期
│   ├── 复盘
│   └── 运营实验
├── 我的资料
│   ├── 灵感库
│   ├── 搜索与热榜
│   ├── 素材库
│   └── 可复用模式
└── 系统
    ├── 任务中心
    ├── 用量与费用
    └── 设置
```

导航项可以显示待处理数量，但 Badge 只用于可行动项目：

- 待审核。
- 失败任务。
- 今日待发布。
- 待复盘。

不把总内容数当成导航 Badge。

## 3. 路由

所有工作区页面位于：

```text
/w/{workspace_id}
```

### 3.1 身份与入口

| 路由 | 页面 |
|---|---|
| `/login` | 本地开发身份入口；生产构建重定向至演示工作台 |
| `/workspaces/new` | 创建工作区 |
| `/` | 当前演示部署重定向到 `/w/demo/today` |

### 3.2 工作台

| 路由 | 页面 | 阶段 | 状态 |
|---|---|---|---|
| `/w/{id}/today` | 今日工作台 | P2 | 已实现 |
| `/w/{id}/channels` | 自有账号 | P2 | 已实现 |
| `/w/{id}/channels/{channel_id}` | 账号定位详情 | P2 | 已实现 |
| `/w/{id}/tracked-profiles` | 对标账号 | P0 | 已实现 |
| `/w/{id}/tracked-profiles/{profile_id}` | 对标账号详情 | P1 | 已实现 |
| `/w/{id}/inspirations` | 灵感库 | P1 | 已实现 |
| `/w/{id}/inspirations/{inspiration_id}` | 灵感详情 | P1 | 已实现 |
| `/w/{id}/discover` | 搜索与热榜 | P1 | 已实现 |
| `/w/{id}/topics` | 选题 | P2/P3 | 已实现，含批量操作和保存视图 |
| `/w/{id}/topics/{topic_id}` | 选题详情 | P2 | 已实现 |
| `/w/{id}/content-projects` | 内容项目 | P2/P3 | 已实现，含保存视图 |
| `/w/{id}/content-projects/{project_id}` | 项目概览 | P2 | 已实现 |
| `/w/{id}/content-projects/{project_id}/script` | 脚本 | P2 | 已实现 |
| `/w/{id}/content-projects/{project_id}/assets` | 项目素材 | P2 | 已实现 |
| `/w/{id}/schedule` | 排期、发布包与发布登记 | P2/P3 | 已实现，含保存视图 |
| `/w/{id}/reviews` | 复盘列表 | P2/P3 | 已实现，含保存视图 |
| `/w/{id}/reviews/{record_id}` | 复盘详情 | P2 | 已实现 |
| `/w/{id}/experiments` | 运营实验 | P3 | 已实现 |
| `/w/{id}/patterns` | 可复用模式 | P1 | 已实现 |
| `/w/{id}/patterns/{pattern_id}` | 模式详情 | P1 | 已实现 |
| `/w/{id}/assets` | 素材库 | P2 | 已实现 |
| `/w/{id}/jobs` | 任务中心 | P0 | 已实现 |
| `/w/{id}/usage` | 用量与费用 | P1 | 已实现 |
| `/w/{id}/settings` | 工作区设置 | P0–P3 | 已实现，含工作区、预算、成员、健康状态和外部调用开关 |

发布记录由排期页生成和登记，复盘详情以 `record_id` 打开；当前没有独立的 `/publish-records/{record_id}` 页面。

## 4. 页面层级

列表详情遵循：

```text
List Page
→ Detail Page
→ Contextual Action
→ Next Workflow Stage
```

示例：

```text
灵感库
→ 灵感详情
→ 转成选题
→ 选题详情
→ 创建内容项目
→ 脚本页
```

详情页顶部固定显示：

- 来源。
- 当前状态。
- 主要操作。
- 上一步/下一步。
- 更新时间。
- 后台任务状态。

## 5. 顶部工作台标签

### 5.1 标签模型

```ts
type WorkbenchTab = {
  key: string
  workspaceId: string
  href: string
  title: string
  entityType?: string
  entityId?: string
  pinned?: boolean
  lastVisitedAt: number
}
```

### 5.2 行为

- 点击侧边栏：复用对应固定页面标签。
- 打开实体详情：按 `entityType + entityId` 去重。
- 最多保留 12 个非固定标签。
- 超出数量时关闭最久未使用且未固定的标签。
- 关闭当前标签后跳到右侧相邻标签；无右侧时跳左侧。
- 刷新页面后从本地恢复标签，但只激活当前 URL。
- 切换工作区时切换到该工作区自己的标签集合。
- 标签只保存非敏感信息，不缓存后端实体正文。

### 5.3 固定标签

以下可以作为固定标签：

- 今日。
- 灵感库。
- 选题。
- 排期。

用户可取消固定，但当前页面至少保留一个活动标签。

## 6. Command Palette

快捷键：

```text
macOS: Command + K
Windows/Linux: Ctrl + K
```

支持：

- 跳转页面。
- 导入内容链接。
- 新建对标账号。
- 新建选题。
- 打开任务中心。

当前已实现页面跳转、创建入口，以及灵感、模式、选题和内容项目的跨实体关键词搜索。搜索结果显示实体类型和匹配摘要。

统一搜索当前不是向量语义搜索。前端不使用“语义相似”文案，也不把关键词命中解释成语义召回。

命令结果必须遵守工作区权限。Viewer 不显示会产生费用或修改数据的命令。

### 6.1 键盘跳转

焦点不在输入框、文本域或可编辑区域时支持：

```text
G → T：今日
G → O：选题
G → P：内容项目
G → S：排期
G → R：复盘
```

## 7. URL 查询参数

列表状态放入 URL：

```text
?q=
&platform=
&status=
&grade=
&profile_id=
&category_id=
&tag=
&published_from=
&published_to=
&sort=
&cursor=
&view=
```

规则：

- 空值不写入 URL。
- 多选使用重复参数或稳定的逗号编码，项目统一一种方式。
- Query Key 使用规范化后的参数。
- 改变筛选后清除旧 Cursor。
- 搜索输入 300–500 ms 防抖后更新 URL。
- 浏览器后退可以恢复筛选和滚动位置。

## 8. 权限可见性

| 功能 | Owner | Editor | Viewer |
|---|---:|---:|---:|
| 查看工作区数据 | 是 | 是 | 是 |
| 修改内容和标签 | 是 | 是 | 否 |
| 创建 TikHub/AI 任务 | 是 | 是 | 否 |
| 修改预算和评分策略 | 是 | 否 | 否 |
| 管理成员 | 是 | 否 | 否 |
| 生成发布包 | 是 | 是 | 否 |
| 确认发布 | 是 | 是 | 否 |

前端权限隐藏只用于体验，后端仍必须做最终授权。

## 9. 响应式导航

### Desktop：`>= 1280px`

- 完整侧边栏。
- 顶部标签。
- 详情页可双栏。
- 灵感卡片 3–4 列。

### Compact Desktop/Tablet：`768–1279px`

- 可折叠侧边栏。
- 标签可横向滚动。
- 详情页单栏或主栏 + Drawer。
- 灵感卡片 2 列。

### Mobile：`< 768px`

- 底部或 Drawer 导航。
- 不展示完整多标签栏。
- 优先支持查看、审批、记录发布结果和简单编辑。
- 脚本长文编辑、复杂排期和批量操作提示使用桌面端。

## 10. 页面状态

每个路由必须实现：

- `loading`
- `empty`
- `error`
- `forbidden`
- `not_found`
- `partial_data`
- `offline_or_backend_unavailable`

禁止所有页面共用一句“出错了”。错误状态需给出：

- 发生了什么。
- 是否可重试。
- 是否已保留用户输入。
- 下一步动作。
- Request ID（放在可展开详情中）。
