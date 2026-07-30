# 后端运行、部署与验收

## 1. 环境

至少包含：

- `local`
- `test`
- `staging`
- `production`

生产数据和 TikHub API Key 不得进入测试环境。

## 2. 运行进程

```text
api        FastAPI HTTP 服务
worker     后台任务消费者
scheduler  定时创建同步和刷新任务
postgres   业务数据库与任务事实来源
storage    S3 兼容对象存储
redis      可选；多 Worker 时用于分布式限流和短缓存
```

本地可使用 Docker Compose；生产环境优先使用托管 PostgreSQL 和对象存储。

## 3. 配置

示例仅列变量名，不保存真实值：

```dotenv
APP_ENV=
APP_BASE_URL=
DATABASE_URL=
OBJECT_STORAGE_PROVIDER=
OBJECT_STORAGE_ENDPOINT_URL=
OBJECT_STORAGE_BUCKET=
OBJECT_STORAGE_REGION=
OBJECT_STORAGE_ACCESS_KEY_ID=
OBJECT_STORAGE_SECRET_ACCESS_KEY=
OBJECT_STORAGE_SESSION_TOKEN=
OBJECT_STORAGE_ADDRESSING_STYLE=
OIDC_ISSUER=
OIDC_AUDIENCE=
TIKHUB_BASE_URL=
TIKHUB_API_KEY=
AI_CREDENTIALS_ENCRYPTION_KEY=
AI_CREDENTIALS_KEY_FILE=
AI_L1_ESTIMATED_COST_USD=
AI_L2_ESTIMATED_COST_USD=
AI_GENERATION_ESTIMATED_COST_USD=
ASR_PROVIDER=
ASR_MODEL=
ASR_ESTIMATED_COST_USD=
DEFAULT_TIMEZONE=
LOG_LEVEL=
LOG_JSON=
METRICS_ENABLED=
METRICS_BEARER_TOKEN=
TRUSTED_HOSTS=
PROVIDER_PAYLOAD_RETENTION_DAYS=
FAILED_PROVIDER_PAYLOAD_RETENTION_DAYS=
```

要求：

- Secret 通过部署平台 Secret Store 注入。
- 日志禁止打印 Secret。
- `TIKHUB_BASE_URL` 可配置，不硬编码区域域名。
- DeepSeek/OpenAI 等 Provider Key 由 Owner 通过 `/api/v1/ai/connections` 写入，
  数据库只保存 AES-256-GCM 密文；生产环境的主加密密钥
  `AI_CREDENTIALS_ENCRYPTION_KEY` 由 Secret Store 注入。
- 启动时验证必要配置，但错误信息不得回显 Secret。

## 4. 数据库迁移

- 迁移文件必须进入版本控制。
- 生产部署先执行兼容性迁移，再发布应用。
- 删除字段采用 Expand/Contract：
  1. 新增兼容字段。
  2. 双写/回填。
  3. 切换读取。
  4. 下一版本删除旧字段。
- 大表索引使用在线/并发方式创建。
- Worker 和 API 必须能够短时间跨两个 Schema 版本运行。

## 5. 健康检查

```text
GET /health/live
GET /health/ready
GET /health/dependencies
```

### `live`

只确认进程事件循环正常，不探测外部供应商。

### `ready`

确认：

- 数据库可连接。
- 当前 Schema 版本可用。
- 对象存储基本可用。

### `dependencies`

受保护接口，显示：

- TikHub 最近探测结果。
- LLM/ASR 状态。
- 队列深度。
- 熔断状态。

TikHub 不可用不应让 API `live` 失败。

## 6. 日志

使用结构化 JSON 日志，至少包含：

- `timestamp`
- `level`
- `service`
- `request_id`
- `workspace_id`
- `user_id`
- `job_id`
- `provider_fetch_id`
- `endpoint_key`
- `duration_ms`
- `error_code`

不得记录：

- Authorization Header。
- API Key。
- 完整用户 Token。
- 原始媒体二进制。
- 未去敏的第三方个人资料。

## 7. 指标

API 在 `METRICS_ENABLED=true` 时通过 `GET /metrics` 输出 Prometheus 文本格式。
生产环境必须配置 `METRICS_BEARER_TOKEN`，抓取请求使用
`Authorization: Bearer <token>`。HTTP 指标仅使用方法、路由模板和状态码标签，
不会写入用户、工作区或原始 URL，避免敏感信息和高基数时间序列。

数据库采集器同时输出队列状态/最旧任务、供应商请求与错误、预估费用、熔断状态、
AI/ASR 成本和逐工作区预算利用率。告警规则位于
`backend/monitoring/alerts.yml`，CI 使用固定摘要的 Prometheus `promtool check rules`
校验语法与 PromQL。

### API

- 请求量和 P50/P95/P99。
- 4xx/5xx。
- 慢查询。
- 数据库连接池。

### Worker

- 各任务类型队列深度。
- 最旧等待时间。
- 成功、失败、重试和 Dead Job 数。
- Worker 心跳。
- 单任务耗时。

### TikHub

- endpoint 成功率。
- 429/5xx/Schema 错误率。
- 延迟。
- 熔断状态。
- 请求数和预估费用。
- 缓存命中率。

### AI/ASR

- L1/L2 数量。
- 输入/输出 Token。
- ASR 分钟数。
- 成功率、延迟和费用。
- JSON Schema 校验失败率。

## 8. 告警

至少配置：

- API 5xx 持续升高。
- 数据库不可用。
- Worker 无心跳。
- 队列最旧任务超过阈值。
- TikHub endpoint 熔断。
- TikHub 401/402/403。
- 每日费用达到 70%、90%、100%。
- 解析器 Schema 不兼容。
- 备份失败。
- 对象存储失败。

预算达到 100% 后自动停止非关键外部调用，不影响站内业务。

Owner 需要人工紧急停止时调用：

```text
POST /api/v1/workspaces/{workspace_id}/external-calls/pause
POST /api/v1/workspaces/{workspace_id}/external-calls/resume
```

暂停请求必须填写原因。状态保存在工作区设置并进入写请求审计；TikHub 网关以及
AI/ASR 预算预留都会在网络请求前返回 `EXTERNAL_CALLS_PAUSED`。暂停不影响历史
数据查询、脚本编辑、人工发布包或复盘浏览。

## 9. 备份与恢复

### PostgreSQL

- 每日自动备份。
- 尽量启用持续归档/PITR。
- 至少保留 30 天。
- 每月执行一次真实恢复演练。

本地/自托管 PostgreSQL 可使用仓库脚本生成自定义格式备份及 SHA-256：

```bash
cd backend
./scripts/backup_postgres.sh backups/social_ops-$(date -u +%Y%m%dT%H%M%SZ).dump
```

恢复演练会校验 checksum，在同一 PostgreSQL 实例创建名称受限的临时数据库，
恢复后验证 Alembic Head、公共表数量、工作区与活动任务计数，最后自动删除临时库：

```bash
./scripts/rehearse_restore.sh backups/social_ops-YYYYMMDDTHHMMSSZ.dump
```

该脚本用于本地与自托管演练；托管 PostgreSQL 的 PITR 仍必须使用供应商快照在
隔离实例执行，不能用本地 `pg_dump` 结果替代 PITR 验收。

### 对象存储

- 开启版本控制或生命周期保护。
- 原始 Provider 响应按保留策略清理。
- 用户素材禁止因缓存清理被误删。

### Provider 响应保留

默认命令只报告候选数量，不修改数据：

```bash
uv run python -m app.cli.retention
```

执行去除响应正文需要两个显式开关：

```bash
uv run python -m app.cli.retention \
  --execute \
  --confirm-redact-provider-payloads
```

成功响应只有在超过保留期且没有被内容、指标、评论或发现结果引用时才会去除
`response_payload`。失败响应使用单独的较短保留期。ProviderFetch 费用、状态和
请求证据行不会删除。生产执行前必须先备份并保存 dry-run 输出。

### 恢复目标

MVP 建议：

- RPO：24 小时以内；托管 PITR 后缩短到 15 分钟以内。
- RTO：4 小时以内。

恢复步骤必须验证：

1. Schema 版本。
2. 数据库行数和关键约束。
3. 对象存储引用。
4. Worker 不会重复执行已完成的付费任务。

## 10. Worker 可靠性

- 任务领取使用数据库锁。
- 长任务定期写 `heartbeat_at`。
- Worker 崩溃后，超过锁超时的任务可被重新领取。
- 任务 Handler 必须幂等。
- 外部调用成功、数据库写入失败时，利用 ProviderFetch/request fingerprint 避免盲目再次付费。
- Dead Job 必须保留人工重试入口。
- Scheduler 只创建任务，不执行外部调用。

## 11. 安全

### API

- 所有业务查询强制按 `workspace_id` 过滤。
- `viewer` 禁止产生付费调用和修改内容。
- 管理设置和预算只允许 `owner` 修改。
- CORS 只允许配置中的前端域名，不使用通配来源。
- 文件上传使用预签名 URL 和服务端完成确认。
- URL 导入只允许支持的平台域名，防止 SSRF。
- 媒体代理限制协议、域名、重定向、MIME 和大小。

### 数据

- API Key 和 Token 加密保存或只存在 Secret Store。
- 评论作者信息最小化。
- 审计删除、发布、预算和权限变更。
- 数据导出需要权限检查。

### AI

- 外部内容使用明确数据边界包裹。
- Prompt 明确禁止执行内容中的指令。
- 输出必须过 JSON Schema。
- AI 不能直接触发发布。
- 高风险事实、法律、医疗、金融内容标记人工核验。

## 12. 性能基线

MVP 目标：

- 灵感列表 P95 小于 500 ms，不含外部调用。
- 内容详情 P95 小于 500 ms，不含外部调用。
- 所有 TikHub 调用异步执行。
- 搜索列表使用数据库索引，不在应用层全量过滤。
- 列表默认 20 条，最大 100 条。
- 对象存储使用预签名 URL，不经 API 转发用户素材。

## 13. 测试策略

### 单元测试

- 平台字段标准化。
- URL 规范化。
- 指标解析。
- R/M/Tier。
- 评级条件和证据冻结。
- 预算计算。
- 状态机。

### 集成测试

- PostgreSQL 事务和唯一约束。
- 任务领取与崩溃恢复。
- 对象存储。
- Provider Fixture 回放。
- API 鉴权和工作区隔离。

### 契约测试

- TikHub 各启用 endpoint。
- OpenAPI 向后兼容。
- LLM JSON Schema。
- ASR 标准化。

### 端到端测试

至少覆盖：

1. 导入链接。
2. 异步获取详情。
3. 产生指标快照。
4. 计算评分。
5. 完成 L1。
6. 转成选题。
7. 创建脚本版本。
8. 生成发布包。
9. 标记已发布。
10. 写入复盘。

## 14. CI/CD

每次合并必须执行：

1. 格式化和静态检查。
2. 单元测试。
3. 集成测试。
4. Alembic 迁移检查。
5. OpenAPI 生成和破坏性变更检测。
6. 容器构建。
7. Secret 扫描。
8. Staging Smoke Test。

当前仓库 CI 已自动执行 1–7；第 8 项需要部署平台 URL 和测试身份后才能启用。

CI 还会在真实 PostgreSQL 服务中写入 1000 条隔离 Fixture，对灵感列表和详情各
采样 30 次并强制 P95 小于 500 ms。该门禁证明当前查询与索引基线，不替代托管
环境网络、连接池和峰值并发压测。

仓库提供手动触发的 `Staging Smoke` 工作流。Staging 环境需配置：

- Variable：`STAGING_BASE_URL`、`STAGING_WORKSPACE_ID`
- Secret：`STAGING_ACCESS_TOKEN`
- 可选 Secret：`STAGING_METRICS_BEARER_TOKEN`

Smoke Test 全程只读，验证健康、身份、工作区、队列、今日看板、统一搜索、
Problem Details 和可选 Prometheus 指标，不触发 TikHub、AI、ASR 或发布调用。

生产发布：

1. 数据库备份。
2. 执行兼容性迁移。
3. 发布 API。
4. 发布 Worker/Scheduler。
5. 健康检查。
6. 运行小规模 TikHub Smoke Test。
7. 观察错误率和费用。

## 15. P0 验收

### 数据接入

- 小红书、抖音、B站或 YouTube 至少三个平台各导入 5 条真实公开内容。
- 同一链接连续导入两次只创建一条内容。
- 新鲜度有效期内第二次导入不再次调用 TikHub。
- Provider 原始响应和标准化结果可追溯。

### 对标账号

- 至少 10 个账号可按计划增量扫描。
- 扫描不会重复插入同一作品。
- 分页 Cursor 在失败时不前移。

### 评分

- 基线只使用候选内容发布前的作品。
- 样本不足时不强行评级。
- 首次评级证据被冻结。
- 阈值可按平台配置和版本化。

### 可靠性

- 模拟 429 后任务退避重试。
- 模拟 5xx 后最多重试 3 次。
- 模拟 401/403 后停止调用并报警。
- Worker 进程被终止后任务可以恢复。
- TikHub 不可用时历史内容仍可正常查询。

### 成本

- 每次 TikHub、AI、ASR 调用可归属工作区和任务。
- 每日费用看板可用。
- 预算到达 100% 后停止非关键任务。

### 安全

- API Key 不出现在前端、日志和原始响应文件名中。
- URL 导入无法访问任意内网地址。
- Viewer 无法创建付费任务。
- 所有业务 API 验证工作区隔离。

## 16. P1 验收

- L1 严格输出结构化 JSON。
- L2 只处理策略允许的高价值内容。
- 转写结果带版本、模型和时间轴。
- AI 结果引用来源实体。
- 模型或 Prompt 更新可重跑且保留旧版本。
- 内容可从灵感进入选题、脚本和排期流程。
