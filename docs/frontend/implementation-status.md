# 前端实现状态与证据边界

更新日期：2026-07-30。

## 1. 当前结论

前端 P0–P3 已按当前 OpenAPI 契约完成页面与主要交互实现。默认入口为今日工作台：

```text
/ → /w/demo/today
```

当前状态应表述为：

> P0–P3 前端契约主链已实现、自动化检查通过并部署私有版本；真实供应商、真实对象存储、托管后端和浏览器级生产验收仍未完成。

不能把“页面存在”“演示工作区可操作”或“构建通过”表述成外部生产集成已经验收。

## 2. 已实现范围

| 阶段 | 已实现 |
|---|---|
| P0 | 开发身份、工作区创建与切换、Workbench Shell、标签栏、导航、对标账号、任务中心、权限可见性、统一错误处理 |
| P1 | 灵感库与详情、指标快照、评分、评论、逐字稿、L1/L2 分析、搜索与热榜、模式库、AI/ASR/Provider 用量 |
| P2 | 今日工作台、自有账号定位、选题、内容项目、脚本追加版本、素材直传、审核排期、人工发布包、发布登记、复盘 |
| P3 | 跨实体关键词搜索、个人保存视图与共享视图读取、选题批量操作、键盘跳转、运营实验、项目负责人协作信息、移动端关键操作 |

### 2.1 P2 真实性约束

- AI 脚本生成返回异步任务；前端显示 Job 已进入队列，不显示“脚本已完成”。
- 人工脚本保存追加新版本，不覆盖历史版本。
- 409 版本冲突保留本地脚本，并提供复制本地草稿。
- 素材使用 `upload intent → 浏览器 PUT 对象存储 → complete`，不经 Next.js 中转大文件。
- 发布计划必须经后端审核状态机校验。
- 发布包生成不等于发布成功。
- 只有后端成功写入公开 HTTPS URL、实际发布时间和发布包匹配信息后，页面才显示已发布记录。
- 复盘将曝光、互动和转化分开统计。

### 2.2 P3 当前边界

当前统一搜索是后端 `/api/v1/search` 提供的可解释关键词匹配，覆盖：

- 灵感。
- 可复用模式。
- 选题。
- 内容项目。

它不是向量语义搜索。以下能力仍属于后续外部或后端工作，不应写成已完成：

- 向量语义搜索。
- 独立通知中心和真实消息投递。
- 官方平台自动发布。
- 自动回传平台表现数据。

当前团队协作由项目负责人、成员权限、共享保存视图读取和实验分组组成；页面明确说明未发送独立提醒。前端当前只创建个人保存视图，共享状态管理仍需补充 UI。

## 3. 已实现路由

### 3.1 入口与系统

```text
/
/login
/workspaces/new
/w/{id}/today
/w/{id}/jobs
/w/{id}/usage
/w/{id}/settings
```

### 3.2 账号、研究与洞察

```text
/w/{id}/channels
/w/{id}/channels/{channel_id}
/w/{id}/tracked-profiles
/w/{id}/tracked-profiles/{profile_id}
/w/{id}/inspirations
/w/{id}/inspirations/{inspiration_id}
/w/{id}/discover
/w/{id}/patterns
/w/{id}/patterns/{pattern_id}
```

### 3.3 内容生产与复盘

```text
/w/{id}/topics
/w/{id}/topics/{topic_id}
/w/{id}/content-projects
/w/{id}/content-projects/{project_id}
/w/{id}/content-projects/{project_id}/script
/w/{id}/content-projects/{project_id}/assets
/w/{id}/assets
/w/{id}/schedule
/w/{id}/reviews
/w/{id}/reviews/{record_id}
/w/{id}/experiments
```

发布包与发布登记在排期页内完成，当前没有独立的 `/publish-records/{id}` 前端路由。

## 4. 自动化证据

前端提交 `fbc5fde` 的本地结果：

- TypeScript strict typecheck 通过。
- ESLint 通过。
- 18 项 Vitest 单元测试通过。
- Production Build 通过。
- 9 项服务端渲染与路由验收通过。
- P2 所有独立路由均验证为可访问，且不再返回旧的“P2 页面尚未启用”占位内容。
- OpenAPI TypeScript Client 已从当前 `openapi.json` 重新生成。

同一工作区的后端测试套件通过；其中 3 项依赖 PostgreSQL 或性能环境的测试在普通套件中跳过。后端证据以[后端实现状态](../backend/implementation-status.md)为准。

## 5. 部署

当前私有部署：

[https://xuzhang-social-ops.guoxinyi0712.chatgpt.site](https://xuzhang-social-ops.guoxinyi0712.chatgpt.site)

部署对应前端提交 `fbc5fde`。站点默认进入 `demo` 工作区；演示数据只用于展示交互契约。真实工作区必须连接可访问的后端 API，并由后端提供真实实体、任务、对象存储上传意图和发布记录。

## 6. 尚未完成的验收

- 未完成基于真实托管后端的浏览器端端到端测试。
- 未完成真实 AI/ASR Provider、TikHub 账户和对象存储 Bucket 联调。
- 未完成固定视口的完整视觉回归和屏幕阅读器人工验收。
- 未完成生产 OIDC、托管 Secret、告警与错误监控验收。
- 未实现向量语义搜索、独立通知投递和官方平台自动发布。

因此，前端开发阶段可以标记为“P0–P3 契约主链完成”，但整个产品不能标记为“生产验收完成”。
