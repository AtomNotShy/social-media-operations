# 后端实现状态与证据边界

更新日期：2026-08-02。

## 已实现并自动验证

| 阶段 | 当前实现 |
|---|---|
| P0 | 小红书、抖音、Bilibili、X、TikTok 链接导入/账号扫描 Adapter；小红书详情、评论与发现；Provider 证据、预算/缓存、任务调度与恢复 |
| P1 | 评分证据冻结、分析/转写账本、DeepSeek/OpenAI/OpenAI-Compatible 真实模型适配器、工作区模型路由、加密凭据、严格结果 Schema、L2 门控、AI/ASR 预算预留与结算、模式库、趋势证据流 |
| P1.5（AI 交互架构） | 官方模型定价目录（DeepSeek 快照自动计价，路由无需手填）、AI 网关（熔断/半开探测、按连接限流、工作区暂停门禁、稳定 Idempotency-Key）、attempt 级成本日志、worker 解耦 TikHub（无 TIKHUB_API_KEY 可独立跑 AI/ASR 任务） |
| P2 | 自有账号（创建即入队基本信息扫描，回填昵称/头像/简介并支持手动重新扫描）、选题、项目状态机、人工/AI 脚本追加版本、S3 直传与远端校验、审核排期、人工发布、生成式复盘与看板 |
| P3 | 保存视图、统一关键词搜索、版本化运营实验、项目分组、幂等归因事件与证据化结果 |
| P4 | 成员权限、最后 Owner 保护、写请求审计、Provider 健康/熔断、工作区外部调用紧急停机、进程心跳、Prometheus 指标/告警、生产配置门禁、容器、CI、Secret/依赖扫描、保留与备份恢复脚本 |

当前本地证据：

- Ruff 通过。
- 193 项后端测试通过；2 项 PostgreSQL 集成测试和 1 项 PostgreSQL 性能测试在普通套件中跳过，并在 PostgreSQL 环境单独通过。
- SQLite 空库可从 0001 顺序升级至 0024；PostgreSQL 16 容器已在线升级至 0024（0024 为官方定价回填数据迁移）。
- SQLite 与 PostgreSQL 的 `alembic check` 均无模型/迁移漂移。
- OpenAPI 可生成 112 条路径、146 个操作；文档契约均有自动覆盖，前端 TypeScript 类型检查与 66 项 Vitest 通过。
- 非 root 生产镜像可构建并启动，API 对 PostgreSQL readiness 返回 `ok`。
- 源码 Secret 扫描和哈希锁定依赖的 `pip-audit` 通过，当前无已知漏洞。
- 真实 PostgreSQL 16 中写入 1000 条灵感后进行 30 次采样，列表 P95 为 55.50 ms，详情 P95 为 14.98 ms。
- 自托管备份脚本已生成 checksum 并在隔离临时数据库完成恢复演练；托管 PITR 仍需单独验收。

## 尚未完成的验收

- 自动化测试使用代表性去敏 Fixture，不是 TikHub 真实账户响应。
- 自有账号信息扫描复用 TikHub 平台绑定（X/小红书/抖音/TikTok/Bilibili）；YouTube、
  快手、微博、视频号、Instagram 等平台创建后会被如实标记为“暂不支持自动扫描”，
  需等待对应平台绑定后再验收真实昵称/头像回填。
- PostgreSQL 工作区预算行锁并发已验证；更高并发压力与托管实例性能仍未验收。
- 抖音/Bilibili 使用官方端点契约与去敏 Fixture；小红书/抖音/Bilibili 的目标仍是各 5 条真实内容与 10 个真实账号扫描。X 的四个端点、小红书全部主链路端点（资料/发帖列表/图文与视频详情/评论）与 TikTok 视频详情已用真实 TikHub 响应核对并固化为契约测试（小红书搜索发现与 TikTok 资料/发帖/评论端点仍是去敏 Fixture）；X 尚未完成真实对标账号的端到端同步验收，抖音、Bilibili 仍在等真实响应。
- AI 已实现 DeepSeek、OpenAI 和通用 OpenAI-Compatible Provider、真实 HTTP
  错误映射、JSON Mode、L1/L2/内容生成模型路由及加密凭据；当前仓库没有用户
  Provider Key，因此自动测试使用 MockTransport。已用真实 DeepSeek 凭据完成付费
  Smoke Test：脚本生成成功（3769 in / 4700 out tokens，40s），按官方定价结算
  $0.001844，attempt 日志与预算账本一致。ASR 尚无生产 Provider；S3 Provider 已
  实现但未连接真实 Bucket。
- 官方定价目录是 2026-07-23 DeepSeek 文档快照；DeepSeek 已公布峰谷定价与缓存命中
  价，目录版本化可被同步任务替换，历史 run 仍保留自己的 token 与结算成本。
- 熔断/限流/幂等已实现并由测试覆盖：连续失败阈值打开熔断、半开探测后关闭、
  AI_AUTH_FAILED 立即熔断、工作区暂停门禁生效、按连接 RPM 进程内限流（多 worker
  扩容前需换 Redis）；请求携带稳定 Idempotency-Key，运行已完成时直接复用结果。
- 前端仍有 1 项既有 rendered-html 失败（`/` 根重定向在本地构建下返回 200 而非
  307，`app/page.tsx` 未改动），与本次 AI 架构改动无关。
- 实验归因已实现；官方发布、向量语义搜索和真实多供应商切换仍属于 P3 后续。当前统一搜索是可解释关键词匹配，不冒充语义检索。
- 14 条告警规则已由 Prometheus `promtool` 校验通过并纳入 CI。
- 托管部署、托管备份/PITR 恢复、告警投递、Secret Store、Staging E2E 和签字验收仍属于 P4。

因此当前状态是“后端功能主链本地可运行”，不是“P0–P4 生产验收完成”。
