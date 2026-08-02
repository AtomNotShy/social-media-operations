# 后端数据模型

本文定义逻辑模型和关键约束。具体字段可在实现阶段通过 SQLAlchemy Model 和 Alembic Migration 固化。

## 1. 通用约定

所有工作区业务表至少包含：

- `id UUID PK`
- `workspace_id UUID NOT NULL`
- `created_at timestamptz NOT NULL`
- `updated_at timestamptz NOT NULL`

约定：

- 时间统一保存 UTC。
- 金额保存整数最小单位或 `numeric`，同时记录币种。
- 平台枚举初始为 `douyin | xiaohongshu | youtube | bilibili | kuaishou | weibo | wechat_channels | tiktok | instagram | x`。
- 外部平台 ID 一律保存字符串，避免长整型和前导零问题。
- TikHub 原始响应保存 JSONB 或对象存储地址，不把供应商字段扩散到业务表。
- 软删除只用于用户可恢复的业务对象；指标、调用审计和分析记录采用追加写。

## 2. 身份与工作区

### `users`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `external_subject` | text | OIDC 用户标识 |
| `email` | citext | 登录邮箱 |
| `display_name` | text | 显示名 |
| `status` | text | `active/disabled` |

唯一约束：`external_subject`、`email`。

### `workspaces`

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | text | 工作区名称 |
| `timezone` | text | 例如 `Australia/Melbourne` |
| `daily_provider_budget_usd` | numeric | TikHub 每日预算 |
| `daily_ai_budget_usd` | numeric | AI 每日预算 |
| `settings` | jsonb | 非敏感工作区设置 |

### `workspace_members`

| 字段 | 类型 | 说明 |
|---|---|---|
| `workspace_id` | UUID | 工作区 |
| `user_id` | UUID | 用户 |
| `role` | text | `owner/editor/viewer` |

唯一约束：`(workspace_id, user_id)`。

## 3. 自有账号与对标账号

### `owned_channels`

自有运营账号。

| 字段 | 类型 | 说明 |
|---|---|---|
| `platform` | text | 平台 |
| `external_id` | text nullable | 平台账号 ID |
| `display_name` | text | 账号名称 |
| `handle` | text nullable | 平台账号名 |
| `positioning` | text | 定位 |
| `audience` | jsonb | 目标受众 |
| `content_pillars` | jsonb | 内容支柱 |
| `tone_rules` | jsonb | 语气规则 |
| `prohibited_topics` | jsonb | 禁区 |
| `publishing_mode` | text | `manual/official_api/disabled` |
| `active` | boolean | 是否启用 |

唯一约束：`(workspace_id, platform, external_id)`，`external_id` 非空时生效。

### `tracked_profiles`

对标账号。

| 字段 | 类型 | 说明 |
|---|---|---|
| `platform` | text | 平台 |
| `external_id` | text | 平台账号 ID |
| `profile_url` | text | 规范化主页 URL |
| `display_name` | text | 最新昵称 |
| `handle` | text nullable | 账号名 |
| `bio` | text nullable | 简介 |
| `avatar_url` | text nullable | 原始头像地址 |
| `follower_count_latest` | bigint nullable | 最近粉丝数 |
| `priority` | smallint | 扫描优先级 |
| `scan_policy_id` | UUID | 扫描策略 |
| `sync_cursor` | jsonb | 平台分页游标 |
| `last_synced_at` | timestamptz nullable | 最近成功扫描 |
| `next_scan_at` | timestamptz nullable | 下次扫描 |
| `sync_status` | text | `idle/syncing/error/paused` |
| `active` | boolean | 是否监控 |

唯一约束：`(workspace_id, platform, external_id)`。

### `profile_metric_snapshots`

| 字段 | 类型 | 说明 |
|---|---|---|
| `tracked_profile_id` | UUID | 对标账号 |
| `captured_at` | timestamptz | 快照时间 |
| `followers` | bigint nullable | 粉丝数 |
| `following` | bigint nullable | 关注数 |
| `total_likes` | bigint nullable | 总获赞 |
| `content_count` | bigint nullable | 作品数 |
| `metrics` | jsonb | 平台扩展指标 |
| `provider_fetch_id` | UUID | 来源调用 |

索引：`(tracked_profile_id, captured_at desc)`。

## 4. 外部内容与灵感

### `external_contents`

| 字段 | 类型 | 说明 |
|---|---|---|
| `platform` | text | 平台 |
| `external_id` | text | 平台内容 ID |
| `tracked_profile_id` | UUID nullable | 来源对标账号 |
| `canonical_url` | text | 规范化链接 |
| `content_type` | text | `video/image_text/article/live/other` |
| `title` | text nullable | 标题 |
| `body_text` | text nullable | 正文或描述 |
| `published_at` | timestamptz nullable | 发布时间 |
| `duration_ms` | bigint nullable | 视频时长 |
| `language` | text nullable | 语言 |
| `author_snapshot` | jsonb | 作者快照 |
| `media_manifest` | jsonb | 媒体元数据 |
| `content_hash` | text nullable | 内容版本 Hash |
| `detail_status` | text | `summary/detail` |
| `original_content` | jsonb nullable | 结构化原文（按平台还原正文、媒体位置与引用），无则回退 `body_text` |
| `comments_hydrated_at` | timestamptz nullable | 最近评论增强时间 |
| `first_seen_at` | timestamptz | 首次发现 |
| `last_seen_at` | timestamptz | 最近确认存在 |
| `deleted_at_source` | timestamptz nullable | 来源已删除/不可见 |
| `latest_provider_fetch_id` | UUID nullable | 最新原始响应 |

唯一约束：`(workspace_id, platform, external_id)`。

索引：

- `(workspace_id, published_at desc)`
- `(tracked_profile_id, published_at desc)`
- `canonical_url`
- 标题和正文全文搜索索引

### `workspace_inspirations`

工作区对外部内容的业务关系。

| 字段 | 类型 | 说明 |
|---|---|---|
| `external_content_id` | UUID | 外部内容 |
| `status` | text | `inbox/analyzed/candidate/archived` |
| `source` | text | `tracked_profile/search/manual_url/manual_file` |
| `category_id` | UUID nullable | 分类 |
| `manual_score` | smallint nullable | 人工评分 |
| `notes` | text nullable | 人工备注 |
| `created_by` | UUID nullable | 收藏人 |

唯一约束：`(workspace_id, external_content_id)`。

### `content_metric_snapshots`

| 字段 | 类型 | 说明 |
|---|---|---|
| `external_content_id` | UUID | 内容 |
| `captured_at` | timestamptz | 快照时间 |
| `views` | bigint nullable | 播放/观看 |
| `likes` | bigint nullable | 点赞 |
| `comments` | bigint nullable | 评论 |
| `favorites` | bigint nullable | 收藏 |
| `shares` | bigint nullable | 分享 |
| `downloads` | bigint nullable | 下载，平台支持时 |
| `metrics` | jsonb | 平台扩展指标 |
| `provider_fetch_id` | UUID | 来源 |

索引：`(external_content_id, captured_at desc)`。

### `comment_samples`

默认保存高价值内容的有限评论样本，不默认全量抓取。

| 字段 | 类型 | 说明 |
|---|---|---|
| `external_content_id` | UUID | 所属内容 |
| `external_comment_id` | text | 平台评论 ID |
| `parent_external_id` | text nullable | 父评论 |
| `author_snapshot` | jsonb | 最小化作者信息 |
| `body_text` | text | 评论正文 |
| `like_count` | bigint nullable | 点赞 |
| `published_at` | timestamptz nullable | 发布时间 |
| `captured_at` | timestamptz | 抓取时间 |

唯一约束：`(workspace_id, external_content_id, external_comment_id)`。

## 5. Provider 调用与任务

### `provider_fetches`

| 字段 | 类型 | 说明 |
|---|---|---|
| `provider` | text | `tikhub` |
| `platform` | text nullable | 平台 |
| `endpoint_key` | text | 内部 endpoint 别名 |
| `endpoint_path` | text | 实际调用路径 |
| `endpoint_version` | text nullable | 供应商版本 |
| `request_fingerprint` | text | 规范化请求 Hash |
| `request_params_redacted` | jsonb | 去敏参数 |
| `provider_request_id` | text nullable | TikHub request ID |
| `http_status` | integer nullable | HTTP 状态 |
| `provider_code` | text nullable | 业务状态码 |
| `latency_ms` | integer nullable | 延迟 |
| `billable` | boolean | 是否计费 |
| `estimated_cost_usd` | numeric | 预估费用 |
| `response_storage_key` | text nullable | 原始响应对象存储地址 |
| `response_excerpt` | jsonb nullable | 小型去敏摘要 |
| `fetched_at` | timestamptz | 调用时间 |
| `fresh_until` | timestamptz nullable | 我方缓存有效期 |
| `error_code` | text nullable | 统一错误码 |

索引：

- `(request_fingerprint, fetched_at desc)`
- `(workspace_id, fetched_at desc)`
- `(endpoint_key, fetched_at desc)`

### `sync_jobs`

| 字段 | 类型 | 说明 |
|---|---|---|
| `job_type` | text | 任务类型 |
| `dedupe_key` | text | 幂等键 |
| `priority` | smallint | 优先级 |
| `payload` | jsonb | 任务参数 |
| `status` | text | 任务状态 |
| `attempt` | integer | 已尝试次数 |
| `max_attempts` | integer | 最大尝试 |
| `run_after` | timestamptz | 可执行时间 |
| `locked_at` | timestamptz nullable | 领取时间 |
| `locked_by` | text nullable | Worker ID |
| `heartbeat_at` | timestamptz nullable | 心跳 |
| `last_error_code` | text nullable | 最后错误 |
| `last_error_message` | text nullable | 去敏错误 |
| `result` | jsonb nullable | 小型结果摘要 |
| `finished_at` | timestamptz nullable | 完成时间 |

对未结束任务建立部分唯一索引：`(workspace_id, dedupe_key)`。

### `scan_policies`

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | text | 策略名 |
| `schedule` | jsonb | Cron 或间隔 |
| `max_pages` | integer | 最大分页 |
| `detail_policy` | jsonb | 详情 Hydration 条件 |
| `metric_refresh_policy` | jsonb | 指标刷新频率 |
| `comment_policy` | jsonb | 评论抽样策略 |
| `active` | boolean | 是否启用 |

### `provider_usage_daily`

| 字段 | 类型 | 说明 |
|---|---|---|
| `usage_date` | date | 工作区时区日期 |
| `provider` | text | 供应商 |
| `endpoint_key` | text | endpoint |
| `request_count` | bigint | 请求数 |
| `success_count` | bigint | 成功数 |
| `billable_count` | bigint | 计费数 |
| `estimated_cost_usd` | numeric | 费用 |

唯一约束：`(workspace_id, usage_date, provider, endpoint_key)`。

## 6. 评分、转写和 AI

### `scoring_policies`

| 字段 | 类型 | 说明 |
|---|---|---|
| `platform` | text | 平台 |
| `version` | integer | 版本 |
| `core_metric_formula` | jsonb | 指标权重 |
| `tier_thresholds` | jsonb | 粉丝层级 |
| `grade_thresholds` | jsonb | R/M 阈值 |
| `minimum_age_minutes` | integer | 最小观察时间 |
| `minimum_baseline_count` | integer | 最小样本 |
| `active` | boolean | 当前版本 |

唯一约束：`(workspace_id, platform, version)`。

### `content_scores`

| 字段 | 类型 | 说明 |
|---|---|---|
| `external_content_id` | UUID | 内容 |
| `scoring_policy_id` | UUID | 策略版本 |
| `calculated_at` | timestamptz | 计算时间 |
| `r_value` | numeric nullable | 相对倍数 |
| `m_value` | numeric nullable | 破圈指标 |
| `tier` | text nullable | 账号体量层 |
| `grade` | text | `t3/t2/t1/low_quality/ordinary/insufficient` |
| `core_metric` | numeric nullable | 核心指标 |
| `baseline_value` | numeric nullable | 基线 |
| `is_initial` | boolean | 是否首次评级 |
| `evidence` | jsonb | 冻结证据 |

首次评分不可更新；后续评分追加写。

### `transcripts`

| 字段 | 类型 | 说明 |
|---|---|---|
| `external_content_id` | UUID | 内容 |
| `provider` | text | ASR 供应商 |
| `model` | text | 模型 |
| `language` | text nullable | 语言 |
| `status` | text | `queued/running/succeeded/failed` |
| `text` | text nullable | 完整文本 |
| `segments` | jsonb nullable | 时间轴 |
| `confidence` | numeric nullable | 置信度 |
| `input_hash` | text | 输入版本 |
| `cost_usd` | numeric | 成本 |

唯一约束：`(workspace_id, external_content_id, input_hash, provider, model)`。

### `analysis_runs`

| 字段 | 类型 | 说明 |
|---|---|---|
| `external_content_id` | UUID | 内容 |
| `analysis_level` | text | `l1/l2` |
| `model_provider` | text | 模型供应商 |
| `model` | text | 模型 |
| `prompt_version` | text | Prompt 版本 |
| `input_hash` | text | 去重 Hash |
| `status` | text | `queued/running/succeeded/failed` |
| `result` | jsonb nullable | 结构化结果 |
| `evidence_refs` | jsonb | 引用实体 ID |
| `input_tokens` | bigint nullable | 输入 Token |
| `output_tokens` | bigint nullable | 输出 Token |
| `cost_usd` | numeric | 成本 |
| `latency_ms` | integer nullable | 延迟 |
| `error_code` | text nullable | 错误 |

唯一成功结果约束：`(workspace_id, analysis_level, input_hash)`。

### `ai_cost_ledger`

AI 与 ASR 共用工作区每日预算。任务创建前在工作区行锁下写入 `reserved`，
成功后写入真实费用并切换为 `settled`。按 `sync_job_id` 唯一，防止同一任务
重试时重复预留；无法确认供应商是否计费的任务保守占用预估金额，等待人工对账。

### `generation_runs`

记录内部内容生成，不与外部内容拆解混为一类。

| 字段 | 类型 | 说明 |
|---|---|---|
| `content_project_id` | UUID | 内容项目 |
| `generation_type` | text | `script_draft/rewrite/review/summary` |
| `model_provider` | text | 模型供应商 |
| `model` | text | 模型 |
| `prompt_version` | text | Prompt 版本 |
| `input_hash` | text | 去重 Hash |
| `status` | text | `queued/running/succeeded/failed` |
| `result` | jsonb nullable | 结构化输出 |
| `input_tokens` | bigint nullable | 输入 Token |
| `output_tokens` | bigint nullable | 输出 Token |
| `cost_usd` | numeric | 成本 |
| `error_code` | text nullable | 错误 |

### `reusable_patterns`

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | text | 模式名称 |
| `description` | text | 描述 |
| `pattern_type` | text | 钩子、结构、选题等 |
| `applicable_channels` | jsonb | 适用自有账号 |
| `source_content_ids` | jsonb | 来源内容 |
| `evidence` | jsonb | 证据 |
| `status` | text | `draft/validated/retired` |

## 7. 内容生产

### `topics`

| 字段 | 类型 | 说明 |
|---|---|---|
| `owned_channel_id` | UUID nullable | 目标账号 |
| `title` | text | 选题 |
| `audience_problem` | text nullable | 受众问题 |
| `angle` | text nullable | 切入角度 |
| `hook` | text nullable | 钩子 |
| `evidence_refs` | jsonb | 来源灵感与分析 |
| `status` | text | `idea/selected/rejected/archived` |
| `version` | integer | 乐观锁 |

### `content_projects`

| 字段 | 类型 | 说明 |
|---|---|---|
| `topic_id` | UUID nullable | 来源选题 |
| `owned_channel_id` | UUID | 目标账号 |
| `title` | text | 项目名 |
| `status` | text | 内容生产状态 |
| `owner_user_id` | UUID nullable | 负责人 |
| `due_at` | timestamptz nullable | 截止时间 |
| `version` | integer | 乐观锁 |

### `script_versions`

| 字段 | 类型 | 说明 |
|---|---|---|
| `content_project_id` | UUID | 内容项目 |
| `version_no` | integer | 版本号 |
| `body` | text | 脚本 |
| `structured_body` | jsonb nullable | 分镜/段落 |
| `created_by` | UUID nullable | 用户 |
| `generation_run_id` | UUID nullable | AI 生成记录 |
| `change_note` | text nullable | 修改说明 |

唯一约束：`(content_project_id, version_no)`。

### `assets`

| 字段 | 类型 | 说明 |
|---|---|---|
| `content_project_id` | UUID nullable | 项目 |
| `asset_type` | text | 图片、视频、音频、字幕等 |
| `storage_key` | text | 对象存储 |
| `mime_type` | text | MIME |
| `size_bytes` | bigint | 大小 |
| `checksum` | text | 文件 Hash |
| `source_type` | text | `uploaded/generated/reference` |
| `rights_note` | text nullable | 授权/来源说明 |

### `publish_plans`

| 字段 | 类型 | 说明 |
|---|---|---|
| `content_project_id` | UUID | 内容项目 |
| `owned_channel_id` | UUID | 发布账号 |
| `scheduled_at` | timestamptz | 计划时间 |
| `status` | text | `draft/approved/queued/publishing/published/failed/cancelled` |
| `publishing_mode` | text | `manual/official_api` |
| `publish_payload` | jsonb | 标题、正文、话题、素材 ID |
| `approved_by` | UUID nullable | 审核人 |
| `approved_at` | timestamptz nullable | 审核时间 |

### `publish_records`

| 字段 | 类型 | 说明 |
|---|---|---|
| `publish_plan_id` | UUID | 计划 |
| `platform_content_id` | text nullable | 平台内容 ID |
| `published_url` | text | 发布链接 |
| `published_at` | timestamptz | 实际时间 |
| `result_payload` | jsonb | 去敏发布结果 |

### `review_insights`

| 字段 | 类型 | 说明 |
|---|---|---|
| `publish_record_id` | UUID | 发布记录 |
| `review_window` | text | `24h/7d/30d/manual` |
| `metrics` | jsonb | 指标 |
| `analysis` | jsonb | 复盘 |
| `next_actions` | jsonb | 下一步 |
| `created_by` | UUID nullable | 人或 AI |

## 8. 删除与保留

- 用户删除选题、脚本和素材时先进入可恢复状态。
- Provider 原始响应按配置保留 30–90 天；用于证据冻结的响应需更久保留。
- 临时音视频在转写完成后按策略清理。
- 封面和缩略图可长期缓存，但需保留来源 URL 和删除能力。
- 对标内容从来源删除后，不继续展示媒体，只保留最小审计和内部分析证据。
- 所有删除操作必须写入审计日志。
