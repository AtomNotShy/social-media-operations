# 后端

当前后端已覆盖 P0–P2 的本地可运行主链路，并开始落地 P3/P4 的权限、审计和
供应商韧性：

- FastAPI 应用、统一响应和 `application/problem+json` 错误。
- 开发/OIDC 身份、工作区、成员管理和 `owner/editor/viewer` 权限边界。
- 小红书、抖音、Bilibili 安全链接导入与对标账号增量扫描；小红书搜索发现。
- PostgreSQL 持久任务、自然幂等、Scheduler、超时锁恢复和队列健康。
- TikHub 预算/缓存、调用证据、每日用量、运行状态和持久熔断。
- 版本化爆款评分、首次证据冻结、L1/L2 与转写任务账本。
- 灵感、可复用模式、自有账号、选题、内容项目和追加式脚本版本。
- 素材直传意图、审核排期、人工发布包、发布记录和复盘。
- S3 兼容素材直传、远端大小/MIME/SHA-256 完成校验。
- DeepSeek、OpenAI 与通用 OpenAI-Compatible 模型连接、工作区级 L1/L2/生成路由、
  AES-256-GCM 凭据加密、连接测试和严格 JSON Schema 校验。
- AI/ASR 费用预留与结算、写请求审计、依赖健康、17 个 Alembic 迁移和 OpenAPI 契约。
- 结构化请求日志、低基数 Prometheus HTTP 指标和受保护的 `/metrics`。
- 保存视图、版本化实验、幂等转化归因、证据化趋势与今日/绩效看板。
- AI 脚本/复盘生成账本、严格 Schema、项目版本锁和追加式结果。
- Worker/Scheduler 心跳、预算/队列/供应商指标、告警规则及 PostgreSQL 恢复演练。

测试使用代表性去敏 Fixture，不会产生 TikHub 费用。Fixture 不是用户账户的
真实响应；首次付费 Smoke Test 仍需在预算保护下单独执行并核对真实 Schema。

AI Provider Key 不写入前端或项目 JSON，通过 Owner 鉴权的 `/api/v1/ai/*`
接口保存到服务端加密存储。对象存储可配置为 `s3`；`fixture` Provider 只允许在
`APP_ENV=test` 中使用，不能作为生产能力。

## 本地启动

```bash
cp .env.example .env
docker compose up -d postgres
uv sync --dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

前端本地开发默认运行在 `http://localhost:3000`。请确保 `.env` 中包含：

```dotenv
ALLOWED_ORIGINS=["http://localhost:3000"]
```

生产环境只填写实际前端 Origin，不使用通配符。

另开一个终端运行 Worker：

```bash
uv run python -m app.jobs.worker
```

只领取一次任务可使用：

```bash
uv run python -m app.jobs.worker --once
```

另开一个终端运行只负责创建到期扫描任务的 Scheduler：

```bash
uv run python -m app.jobs.scheduler
```

只调度一个批次可使用：

```bash
uv run python -m app.jobs.scheduler --once
```

Scheduler 本身不调用 TikHub；实际外部请求只由 Worker 执行。

开发模式令牌格式为 `Bearer dev:<subject>`。例如：

```bash
curl -H 'Authorization: Bearer dev:local-owner' \
  http://127.0.0.1:8000/api/v1/me
```

首次创建工作区：

```bash
curl -X POST \
  -H 'Authorization: Bearer dev:local-owner' \
  -H 'Content-Type: application/json' \
  -d '{"name":"默认工作区","timezone":"Australia/Melbourne"}' \
  http://127.0.0.1:8000/api/v1/workspaces
```

### 配置 DeepSeek

先取得工作区 UUID，然后由 Owner 创建连接：

```bash
curl -X POST \
  -H 'Authorization: Bearer dev:local-owner' \
  -H 'X-Workspace-Id: <workspace-uuid>' \
  -H 'Content-Type: application/json' \
  -d '{
    "name":"DeepSeek",
    "provider":"deepseek",
    "api_key":"<deepseek-api-key>",
    "model":"deepseek-v4-flash",
    "use_for":["l1","l2","generation"],
    "json_mode":true
  }' \
  http://127.0.0.1:8000/api/v1/ai/connections
```

返回值只包含 `api_key_configured` 与 `api_key_masked`，不会回显完整 Key。随后调用
`POST /api/v1/ai/connections/{connection_id}/test` 获取真实模型列表并验证凭据。
也可以创建 `openai` 或 `openai_compatible` 连接，再通过
`PUT /api/v1/ai/routes/{l1|l2|generation}` 为不同任务选择不同连接和模型。

本地环境首次保存 Key 时会在 Docker `credentials-data` Volume 中生成仅服务端可读
的主密钥。Staging/Production 必须通过 Secret Store 注入
`AI_CREDENTIALS_ENCRYPTION_KEY`，不得依赖容器临时文件。

## 验证

```bash
uv run ruff check .
uv run pytest
uv run alembic check
uv run python ../scripts/check_secrets.py
uv export --quiet --frozen --no-dev --no-emit-project \
  --format requirements-txt --output-file /tmp/social-ops-requirements.txt
uv run pip-audit --requirement /tmp/social-ops-requirements.txt \
  --strict --require-hashes
```

`AUTH_MODE=development` 只允许在 `local` 或 `test` 环境使用。非本地环境必须
配置 OIDC issuer、audience 和 JWKS URL。

## 证据边界

当前自动验证覆盖 SQLite 空库迁移、真实 PostgreSQL 16 在线迁移、迁移漂移、
OpenAPI/文档契约、容器启动、本地测试套件、1000 行核心查询 P95 和隔离恢复演练。
以下仍然是生产发布阻塞项：

- PostgreSQL 并发压测和托管实例验收。
- 三个平台各 5 条真实内容、10 个真实账号的预算内 Smoke Test。
- 使用用户 DeepSeek/OpenAI/兼容 Provider Key 的首次付费 Smoke Test、真实 ASR
  Provider；S3 Provider 已实现但尚无用户 Bucket 凭据验收。
- 托管环境 PITR、告警投递、Secret Store 和 Staging E2E。
- 官方发布接口权限与供应商验收；MVP 当前只支持人工发布包。
