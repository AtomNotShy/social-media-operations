# 后端 API 契约

本文定义前后端分离时的 HTTP 契约。后端以 OpenAPI 为唯一机器可读事实来源，前端从 OpenAPI 生成 TypeScript Client。

## 1. 通用规范

### 1.1 基础路径

```text
/api/v1
```

### 1.2 鉴权

```http
Authorization: Bearer <access_token>
X-Workspace-Id: <workspace_uuid>
```

服务端任务使用单独的服务身份，不复用用户 Token。

### 1.3 成功响应

单对象：

```json
{
  "data": {},
  "meta": {
    "request_id": "uuid"
  }
}
```

列表：

```json
{
  "data": [],
  "meta": {
    "request_id": "uuid",
    "next_cursor": "opaque-or-null"
  }
}
```

### 1.4 错误响应

Content-Type：

```text
application/problem+json
```

示例：

```json
{
  "type": "https://errors.example.com/provider-budget-exceeded",
  "title": "Provider budget exceeded",
  "status": 409,
  "code": "PROVIDER_BUDGET_EXCEEDED",
  "detail": "The workspace daily TikHub budget has been reached.",
  "request_id": "uuid",
  "retryable": false
}
```

稳定错误码至少包括：

- `VALIDATION_ERROR`
- `UNAUTHENTICATED`
- `FORBIDDEN`
- `NOT_FOUND`
- `VERSION_CONFLICT`
- `DUPLICATE_RESOURCE`
- `JOB_ALREADY_RUNNING`
- `PROVIDER_RATE_LIMITED`
- `PROVIDER_UNAVAILABLE`
- `PROVIDER_BUDGET_EXCEEDED`
- `PROVIDER_PAYMENT_REQUIRED`
- `ANALYSIS_BUDGET_EXCEEDED`
- `EXTERNAL_CALLS_PAUSED`
- `UNSUPPORTED_PLATFORM_CAPABILITY`
- `SOURCE_CONTENT_UNAVAILABLE`

### 1.5 幂等

以下操作必须支持：

```http
Idempotency-Key: <client-generated-uuid>
```

- URL 导入。
- 批量导入账号。
- 创建同步任务。
- 创建 AI 分析。
- 创建转写。
- 创建发布任务。

后端对相同工作区、路由和 Idempotency Key 返回首次结果。

### 1.6 并发编辑

选题、内容项目和排期对象包含 `version`。更新请求必须带当前版本：

```json
{
  "version": 4,
  "title": "新标题"
}
```

版本不匹配返回 `409 VERSION_CONFLICT`。

## 2. 身份与工作区

```text
GET    /me
GET    /workspaces
POST   /workspaces
GET    /workspaces/{workspace_id}
PATCH  /workspaces/{workspace_id}
POST   /workspaces/{workspace_id}/external-calls/pause
POST   /workspaces/{workspace_id}/external-calls/resume
GET    /workspaces/{workspace_id}/members
POST   /workspaces/{workspace_id}/members
PATCH  /workspaces/{workspace_id}/members/{user_id}
DELETE /workspaces/{workspace_id}/members/{user_id}
```

## 3. 自有账号

```text
GET    /owned-channels
POST   /owned-channels
GET    /owned-channels/{channel_id}
PATCH  /owned-channels/{channel_id}
DELETE /owned-channels/{channel_id}
```

定位单独更新，便于审计：

```text
GET  /owned-channels/{channel_id}/positioning
PUT  /owned-channels/{channel_id}/positioning
```

## 4. 对标账号

```text
GET    /tracked-profiles
POST   /tracked-profiles
POST   /tracked-profiles/import
GET    /tracked-profiles/{profile_id}
GET    /tracked-profiles/{profile_id}/overview
PATCH  /tracked-profiles/{profile_id}
DELETE /tracked-profiles/{profile_id}
POST   /tracked-profiles/{profile_id}/sync
POST   /tracked-profiles/{profile_id}/pause
POST   /tracked-profiles/{profile_id}/resume
GET    /tracked-profiles/{profile_id}/contents
GET    /tracked-profiles/{profile_id}/metrics
GET    /tracked-profiles/{profile_id}/sync-runs
```

内容情报首屏使用 `GET /tracked-profiles/{profile_id}/overview`。查询参数：

- `window_days`：近期采集统计窗口，默认 30 天，范围 1–365 天。
- `limit`：返回的最近内容数量，默认 12，范围 1–50。

返回账号摘要、全部已采集内容数、窗口内采集数、窗口内最新评分的
`t1/t2/t3/qualified/normal` 分布，以及最近内容。每条内容包含封面、标题、发布时间、
最新互动指标、最新评分、是否已进入灵感库及灵感 ID。内容没有评分时计入
`normal`，缺失指标或评分时对应摘要为 `null`。
来源侧已删除（`deleted_at_source` 非空）的内容不计入总数、分布或最近内容。

后端契约变化后从 `backend/` 目录运行
`uv run python -m app.cli.export_openapi ../frontend/openapi.json`，再从
`frontend/` 目录运行 `npm run api:generate` 更新 TypeScript 类型；生成文件不手改。

创建对标账号可以接受主页 URL，返回同步任务：

```json
{
  "profile_url": "https://...",
  "priority": 50,
  "scan_policy_id": "uuid"
}
```

返回：

```http
202 Accepted
```

```json
{
  "data": {
    "job_id": "uuid",
    "status": "pending"
  }
}
```

## 5. 灵感库

### 5.1 链接导入

```text
POST /inspirations/import-url
```

请求：

```json
{
  "url": "https://...",
  "hydrate": "detail",
  "analyze": true
}
```

若数据库已有且足够新鲜：

```http
200 OK
```

```json
{
  "data": {
    "inspiration_id": "uuid",
    "external_content_id": "uuid",
    "existing": true,
    "job_id": null
  }
}
```

若需要异步获取：

```http
202 Accepted
```

### 5.2 查询

```text
GET   /inspirations
GET   /inspirations/{inspiration_id}
PATCH /inspirations/{inspiration_id}
POST  /inspirations/{inspiration_id}/archive
POST  /inspirations/{inspiration_id}/restore
```

推荐筛选参数：

```text
platform
tracked_profile_id
status
grade
category_id
tag
published_from
published_to
has_transcript
has_l1
has_l2
query
sort
cursor
limit
```

### 5.3 详情增强

```text
POST /inspirations/{inspiration_id}/hydrate-detail
POST /inspirations/{inspiration_id}/fetch-comments
POST /inspirations/{inspiration_id}/refresh-metrics
POST /inspirations/{inspiration_id}/transcribe
POST /inspirations/{inspiration_id}/analyze
```

分析请求：

```json
{
  "level": "l1",
  "force": false
}
```

`force=true` 只有 `owner/editor` 可用，并仍受预算限制。

## 6. 搜索与发现

TikHub 搜索属于异步、高成本操作：

```text
POST /discover/search
GET  /discover/search-jobs/{job_id}
POST /discover/search-jobs/{job_id}/import
GET  /discover/trending
POST /discover/trending/refresh
```

请求：

```json
{
  "platform": "xiaohongshu",
  "query": "餐饮运营",
  "max_pages": 2,
  "hydrate_top": 10
}
```

`max_pages`、`hydrate_top` 需受服务端上限和费用预算约束。

## 7. 评分与分析

```text
GET  /inspirations/{id}/scores
POST /inspirations/{id}/scores/recalculate
GET  /inspirations/{id}/analyses
GET  /analyses/{analysis_id}
POST /analyses/{analysis_id}/retry
GET  /scoring-policies
POST /scoring-policies
POST /scoring-policies/{policy_id}/activate
```

激活新的评分策略只影响新评分；历史初始证据不被改写。

### 7.1 AI 连接与模型路由

```text
GET   /ai/settings
POST  /ai/connections
PATCH /ai/connections/{connection_id}
POST  /ai/connections/{connection_id}/test
PUT   /ai/routes/{task_type}
```

`task_type` 为 `l1`、`l2` 或 `generation`。连接支持：

- `deepseek`：固定使用 DeepSeek 官方 API 地址。
- `openai`：固定使用 OpenAI 官方 API 地址。
- `openai_compatible`：允许配置其他兼容 `/chat/completions` 与 `/models`
  的服务地址；非本地环境必须使用公开 HTTPS 地址。

创建 DeepSeek 连接并同时用于 L1/L2：

```json
{
  "name": "DeepSeek Production",
  "provider": "deepseek",
  "api_key": "<redacted>",
  "model": "deepseek-v4-flash",
  "use_for": ["l1", "l2"],
  "json_mode": true,
  "temperature": 0.2,
  "max_tokens": 2000
}
```

API Key 使用服务端 AES-256-GCM 加密，读取接口只返回 `configured` 和末四位掩码。
更新时省略或提交空 Key 会保留旧值，只有 `clear_api_key=true` 会明确清除。Provider
调用返回的 JSON 仍需通过 L1/L2 Pydantic Schema 和来源引用校验，模型输出不能直接
写入业务表。

## 8. 可复用模式

```text
GET    /patterns
POST   /patterns
GET    /patterns/{pattern_id}
PATCH  /patterns/{pattern_id}
DELETE /patterns/{pattern_id}
POST   /patterns/from-analysis/{analysis_id}
POST   /patterns/{pattern_id}/validate
POST   /patterns/{pattern_id}/retire
```

## 9. 选题和内容项目

```text
GET    /topics
POST   /topics
POST   /topics/from-inspiration/{inspiration_id}
GET    /topics/{topic_id}
PATCH  /topics/{topic_id}
DELETE /topics/{topic_id}

GET    /content-projects
POST   /content-projects
GET    /content-projects/{project_id}
PATCH  /content-projects/{project_id}
POST   /content-projects/{project_id}/transition
```

状态跳转请求：

```json
{
  "from": "scripting",
  "to": "producing",
  "version": 3
}
```

## 10. 脚本

```text
GET  /content-projects/{project_id}/scripts
POST /content-projects/{project_id}/scripts
GET  /scripts/{script_version_id}
POST /content-projects/{project_id}/scripts/generate
POST /content-projects/{project_id}/scripts/{version_no}/duplicate
```

脚本采用追加版本，不原地覆盖历史版本。

## 11. 素材

```text
POST   /assets/upload-intents
POST   /assets/complete
GET    /assets
GET    /assets/{asset_id}
DELETE /assets/{asset_id}
```

前端通过预签名 URL 直传对象存储；后端完成 MIME、大小、Hash 和权限校验。

## 12. 排期与发布

```text
GET    /publish-plans
POST   /publish-plans
GET    /publish-plans/{plan_id}
PATCH  /publish-plans/{plan_id}
POST   /publish-plans/{plan_id}/approve
POST   /publish-plans/{plan_id}/cancel
POST   /publish-plans/{plan_id}/publish
POST   /publish-plans/{plan_id}/mark-published
GET    /publish-records/{record_id}
```

MVP 中 `publish` 生成发布包，不自动操作平台。`mark-published` 记录人工发布结果。

## 13. 复盘

```text
GET  /publish-records/{record_id}/reviews
POST /publish-records/{record_id}/reviews
POST /publish-records/{record_id}/reviews/generate
GET  /dashboard/today
GET  /dashboard/performance
```

## 14. 任务、费用与系统状态

```text
GET  /jobs
GET  /jobs/{job_id}
POST /jobs/{job_id}/retry
POST /jobs/{job_id}/cancel

GET /usage/provider
GET /usage/ai
GET /usage/asr
GET /system/provider-health
GET /system/queue-health
```

任务返回字段：

```json
{
  "id": "uuid",
  "job_type": "CONTENT_DETAIL_FETCH",
  "status": "retry_wait",
  "attempt": 2,
  "max_attempts": 3,
  "progress": {
    "current": 1,
    "total": 1
  },
  "retry_at": "2026-07-30T10:30:00Z",
  "error": {
    "code": "PROVIDER_RATE_LIMITED",
    "message": "Provider request was rate limited."
  }
}
```

错误信息不得包含 API Key、完整请求头或第三方敏感字段。

## 15. 前端 Client 生成

CI 中执行：

1. 后端生成并校验 `openapi.json`。
2. 对比是否存在破坏性 API 变更。
3. 生成 TypeScript 类型和 Client。
4. 前端只通过生成 Client 调用，禁止散落手写 `fetch`。

前后端独立部署，但必须共享：

- API 版本。
- OpenAPI Artifact。
- 错误码枚举。
- 状态机枚举。
