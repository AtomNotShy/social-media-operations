# AI 交互架构（P2 审计结论与实现）

更新日期：2026-08-02。范围：`backend/app/modules/ai_connections`、
`backend/app/providers/ai`、`backend/app/jobs/worker.py` 与 AI 任务 Handler。

## 1. 审计结论：AI 交互要解决的问题

AI 调用和 TikHub 调用本质相同：花钱、失败、会重复。原实现只覆盖了
"能调通"，缺少四道与钱和可靠性直接相关的闸门：

1. **定价来源**：input/output 单价由用户在设置里手填，填 0 时成本追踪、
   预算预留和结算全部失真（真实环境曾出现 0 成本账本）。
2. **熔断**：供应商持续 5xx/429/超时时，任务会反复重试烧钱，没有快速失败。
3. **幂等**：worker 崩溃恢复后重放同一个 run，可能对上游重复计费、重复落库。
4. **耦合**：worker 强制要求 `TIKHUB_API_KEY`，纯 AI/ASR 负载无法独立部署。

## 2. 目标架构

```text
API / Scheduler
    │ 建 run、算 input_hash、按官方价预估、预留日预算
    ▼
SyncJob（PostgreSQL 持久任务表，SKIP LOCKED 领取）
    ▼
Worker
    ├─ TikHub 任务：TikHubGateway（缓存 + 预算 + 熔断 + 审计）
    └─ AI 任务：AIGateway
           ├─ 工作区暂停门禁
           ├─ 熔断（provider_circuit_states，provider="ai"）
           ├─ 按连接限流（进程内滑动窗口）
           └─ 上游调用（带稳定 Idempotency-Key）
                ▼
        ai_attempt_logs（每次尝试一行）+ ai_cost_ledger（预留→结算）
```

### 2.1 官方定价目录（`ai_connections/pricing.py`）

- 内置版本化快照：DeepSeek 官方 2026-07-23 定价
  （`deepseek-v4-flash` 0.14/0.28、`deepseek-v4-pro` 0.435/0.87，含缓存命中价）。
- 写路由时：DeepSeek 官方模型直接覆盖为目录价，用户不需要也不能手填。
- 读路由时：即使存量行还是 0 价，`resolve_route` 也按目录价生效；
  迁移 `20260802_0024` 已把真实库三条 0 价路由回填为 0.14/0.28。
- 自定义 OpenAI-Compatible 端点保留用户自填价格（不在任何官方目录中）。
- 目录版本化：`PRICING_CATALOG_VERSION` + `PRICING_SOURCE_URL` 随
  `/api/v1/ai/settings` 返回；后续可加同步任务替换快照，历史 run 仍保留自己的
  token 数与已结算成本，不做追溯改写。
- 已知漂移点：DeepSeek 已公布峰谷定价与缓存命中价，快照需要周期性刷新；
  前端展示来源 URL 与版本号，避免把快照当永恒事实。

### 2.2 AI 网关（`providers/ai/gateway.py`）

镜像 `TikHubGateway` 的契约，状态落在同一张
`provider_circuit_states` 表（`provider="ai"`，`endpoint_key=连接ID:模型`）：

- 连续失败达到阈值打开熔断，期间请求直接抛 `AI_CIRCUIT_OPEN`（retryable），
  不发上游请求。
- 半开状态只放一个探测；成功即关闭，失败即重新打开。
- `AI_AUTH_FAILED` 立即熔断（凭据坏了重试没用）。
- 工作区 `external_calls.paused` 时调用前拦截（`AI_CALLS_PAUSED`）。
- 按连接 `rate_limit_rpm`（capabilities 配置，默认 0=不限）做进程内滑动窗口；
  多 worker 扩容前切换 Redis 计数。

### 2.3 幂等

- 每个真实 run 构造稳定 `Idempotency-Key`：
  `socialops:{workspace_id}:{analysis|generation}:{run_id}`，
  作为 HTTP 头随聊天请求发出；上游若遵循 OpenAI-Compatible 约定，
  重放会返回首次结果而不是二次计费。
- 应用层兜底：Handler 开始时若 run 已 `succeeded`，直接复用已提交结果，
  不再调上游（覆盖"结果已提交但 job 提交丢失"的崩溃窗口）。
- `ai_attempt_logs` 以 `(sync_job_id, attempt_no)` 唯一约束，防止并发重复记账。

### 2.4 Worker 解耦 TikHub

- `run_worker` 不再要求 `TIKHUB_API_KEY`：有 key 建 TikHub 客户端并领取全部任务；
  没有 key 只领取 `AI_ANALYSIS` / `TRANSCRIBE` / `CONTENT_GENERATION`。
- `process_one` 的 `client` 变为可选；TikHub 任务若被无 key worker 领到，
  立即以 `TIKHUB_NOT_CONFIGURED` 判死，不留热循环。

## 3. 成本闭环

1. 建 run 时：`estimate_generation_cost_usd` 使用目录价预估并 `reserve_ai_budget`。
2. 执行时：成功/失败都写 `ai_attempt_logs`（每次 attempt 一行）。
3. 完成后：`settle_ai_budget` 用真实 usage 结算，账本从 reserved 变 settled。

真实验证（2026-08-02，DeepSeek Production + deepseek-v4-flash）：
脚本生成 3769 in / 4700 out tokens、40s，结算 $0.001844，attempt 日志与账本一致；
`provider_circuit_states` 生成 `ai` 行并保持 closed。

## 4. 后续（未实现，明确留到下一阶段）

- 官方定价目录的自动同步任务（替换快照而非改写历史）。
- 多 worker 部署时把限流改为 Redis/DB 分布式窗口。
- 评估闭环：黄金样例回放 + 人工评分回流，尚未开始。
- DeepSeek 峰谷定价策略（2026-08 起）进入目录后的费率选择逻辑。
