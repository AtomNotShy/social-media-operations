# 社媒运营工作台

一个以前后端分离方式实现的社媒运营工作台。TikHub 负责外部公开社媒数据采集，系统自身负责数据标准化、爆款判断、AI 拆解、选题、脚本、素材、排期、发布记录和复盘。

后端已实现 P0–P2 的本地主链路并进入 P3/P4 外部集成与生产验收；前端仍主要处于 P0
Shell 与契约接入阶段。前端只通过版本化 REST API 与 OpenAPI Client 访问后端。

## 后端文档

- [后端总体架构](./docs/backend/README.md)
- [后端数据模型](./docs/backend/data-model.md)
- [前后端 API 契约](./docs/backend/api-contract.md)
- [TikHub 集成规范](./docs/backend/tikhub-integration.md)
- [运行、部署与验收](./docs/backend/operations.md)
- [后端实现与本地运行](./backend/README.md)

## 前端文档

- [前端总体架构](./docs/frontend/README.md)
- [信息架构与路由](./docs/frontend/information-architecture.md)
- [页面规格](./docs/frontend/page-specs.md)
- [设计系统](./docs/frontend/design-system.md)
- [状态管理与 API 集成](./docs/frontend/state-and-api.md)
- [测试、部署与验收](./docs/frontend/testing-and-delivery.md)
- [P0–P4 统一交付路线](./docs/roadmap-p0-p4.md)

## 当前实现

- FastAPI、SQLAlchemy 2、Alembic 和 PostgreSQL 16 本地运行配置。
- 统一 REST 响应、Problem Details 错误与 Request ID。
- 开发/OIDC 身份边界、工作区与基础 RBAC。
- 对标账号 API、同步 Worker 和 PostgreSQL 活跃任务去重。
- TikHub Client、预算/缓存 Gateway、小红书 App V2 Adapter 与调用证据。
- 标准化外部内容、指标快照、灵感关系和 Provider 费用记录。
- 版本化评分、分析/转写账本、评论采样、搜索发现和模式库。
- 自有账号、选题、项目、脚本、素材、排期、人工发布记录与复盘。
- 团队成员管理、写请求审计、持久熔断和依赖健康。
- Next.js 16、React 19 与 Tailwind CSS v4 前端工程。
- 工作台 Shell、开发身份与工作区流程、对标账号列表/详情和任务中心。
- OpenAPI 生成类型、统一 API Core、TanStack Query 与 URL 筛选。
- 明确标记的契约演示数据，以及可切换到真实工作区的后端接入层。

真实多平台、真实 AI/ASR/对象存储、托管 PostgreSQL 和 Staging 验收尚未完成，
不能把本地测试通过视为 P0–P4 已正式交付。

## 当前架构决策

- 后端采用模块化单体，不提前拆微服务。
- API、Worker、Scheduler 使用同一代码库并独立运行。
- PostgreSQL 同时承担业务数据库和持久任务事实来源。
- TikHub 被隔离在 Provider Adapter 后面，业务层不依赖其原始字段。
- 评分、指标、逐字稿和 AI 分析全部版本化并保留证据。
- TikHub 仅负责读取公开数据；发布采用人工确认或后续官方接口。
