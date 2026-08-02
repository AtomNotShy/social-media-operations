# 内容包设计：从"脚本"到"可直接进视频管线的完整内容"

更新日期：2026-08-03。状态：P0（内容包生成）已实现并通过真实 DeepSeek 验证；
P1（渲染适配器）与 P2（素材/反馈闭环）尚未实现。

## 1. 现状与问题

当前生成链路只产出**口播文字稿**：

```json
{
  "body": "光练不记，等于白练。…（口播全文）",
  "structured_body": { "hook": "...", "main_points": [...], "call_to_action": "...", "spoken_length_chars": 248 },
  "rationale": "…",
  "evidence_refs": ["content:…"]
}
```

它回答了"说什么"，但没有回答"怎么拍、怎么剪、怎么发"：

- 没有分镜（每段话配什么画面/字幕/布局）。
- 没有时长估算（口播 248 字 ≈ 多少秒？每镜几秒？）。
- 没有标题、封面文案、话题标签、正文描述（发布包需要）。
- 没有素材需求清单（需要哪些 B  Roll、截图、演示画面）。
- 没有配音/BGM 提示（口播音色、语速、音乐情绪）。
- 没有平台规格（抖音 vs 小红书的口播节奏、字幕样式、封面比例不同）。

结果：脚本到成片之间是断的。AI 生成视频（Replicast）没有输入契约；人工剪辑也拿不到素材清单和发布文案。

## 2. 目标：单一内容包契约，多下游适配

在脚本之后增加一个结构化的 **ContentPackage（内容包）**，一次生成，按消费者导出：

```text
GenerationRun（AI）
   │  脚本（现有）
   ▼
ContentPackage（新，JSONB，版本化）
   ├── 剪辑包视图：分镜 + 字幕 + 素材清单 + 封面/标题/话题 → 人工剪
   └── 渲染适配器（未定稿，二选一或都做）：
        ├── Replicast Storyboard（storyboardSchema）
        └── HyperFrames 合成（HTML/GSAP 组件，由 Codex CLI 生成视频）
```

原则：

1. **单契约多视图**。数据库只存一份 ContentPackage；导出成剪辑包或 Storyboard 都是同一份数据的派生，避免多套生成互相漂移。
2. **脚本与包分层**。脚本（说什么）是内容包（怎么呈现）的上游；人工先定稿脚本，再生成/编辑内容包。内容包不反向改写脚本。
3. **平台感知**。生成时传入目标平台，内容包内带平台规格；同一条内容换平台时允许重新生成（新 input_hash，旧包保留）。
4. **人工可编辑、可冻结**。AI 生成的是草稿，人工可改分镜/素材清单/标题候选，确认后冻结版本。
5. **证据与溯源不断链**。内容包的每个分镜都能追溯到 evidence_refs 中的原文/脚本片段。
6. **渲染器中立**。ContentPackage 不携带任何渲染器字段；Replicast 与 HyperFrames
   都是下游适配器，先选哪个、甚至换哪个，都不改内容包本身与生成链路。

## 3. ContentPackage 数据契约（草案）

```json
{
  "schema_version": 1,
  "target_platform": "douyin",
  "content_type": "talking_video",
  "target_duration_seconds": 45,
  "narration": {
    "full_text": "光练不记，等于白练。…",
    "spoken_length_chars": 248,
    "estimated_duration_seconds": 62
  },
  "scenes": [
    {
      "id": "scene_01",
      "layout": "avatar_corner",
      "narration_chunk": "光练不记，等于白练。每天练口语，练完就忘，错误明天照犯。",
      "visual_hint": "真人出镜，中景，低头看手机后抬头说话",
      "on_screen_text": "练完就忘 = 白练",
      "subtitle": "光练不记，等于白练。",
      "estimated_seconds": 8,
      "cta": null,
      "evidence_refs": ["content:729c6f75-…"]
    },
    {
      "id": "scene_02",
      "layout": "broll",
      "narration_chunk": "把 GPT Live 当陪练、Obsidian 当账本。",
      "visual_hint": "录屏：GPT Live 对话 + Obsidian 笔记页切换",
      "on_screen_text": "GPT Live × Obsidian",
      "subtitle": "把 GPT Live 当陪练、Obsidian 当账本。",
      "estimated_seconds": 10,
      "asset_queries": ["GPT Live 对话界面", "Obsidian 复盘笔记"],
      "evidence_refs": ["content:729c6f75-…"]
    }
  ],
  "title_candidates": [
    { "text": "每天练口语却感觉没进步？你缺的不是努力，是记录", "length_chars": 23, "has_emoji": false },
    { "text": "0 元口语陪练法🔥GPT Live + Obsidian 记复盘", "length_chars": 20, "has_emoji": true }
  ],
  "cover": {
    "headline": "光练不记，等于白练",
    "subheadline": "GPT Live 陪练 + Obsidian 账本",
    "visual_hint": "深色背景 + 大字标题 + 两个 App 图标"
  },
  "hashtags": ["#口语练习", "#GPTLive", "#Obsidian", "#英语学习"],
  "publish_caption": "练完口语的下一步：把错的话记下来。…",
  "assets_required": [
    { "kind": "broll", "query": "GPT Live 对话界面", "source_hint": "content:729c6f75-…", "rights_note": "自录/截图需确认授权" },
    { "kind": "screenshot", "query": "Obsidian 复盘笔记模板", "source_hint": null, "rights_note": "自录" }
  ],
  "audio": {
    "voice_hint": "清晰女声/男声，语速中速偏快，适合口播",
    "music_mood": "轻快、无版权、低音量垫底",
    "music_ducking": "口播时 -8dB 左右"
  },
  "publish_timing_hint": "工作日 20:00-22:00",
  "evidence_refs": ["project:…", "channel:…", "topic:…", "content:…"]
}
```

字段刻意保持"提示"而非"定稿"：`visual_hint`、`asset_queries`、`voice_hint` 都是给人工/AI 的输入，不是不可变命令。人工剪辑时据此找素材；Replicast 渲染时把 `asset_queries` 变成可检索的素材源。

## 4. 渲染适配器（未定稿）

内容包是平台/剪辑通用层，渲染适配器把内容包转成具体渲染器的输入。当前候选：

### 4.1 Replicast Storyboard

Storyboard 是 Replicast 的渲染契约。导出逻辑（后端一个纯函数）：

| ContentPackage | Replicast storyboardSchema |
|---|---|
| 整体 | `title`、`durationSeconds`、`fps=30`、`width=1080`、`height=1920` |
| `scenes[].layout` | `scene.layout`（avatar_full / avatar_corner / broll / comparison / cta） |
| `scenes[].narration_chunk` | `scene.narration` |
| `scenes[].on_screen_text` | `scene.headline` |
| `scenes[].subtitle` | `subtitles[].text`（秒数由 estimated_seconds 拆分） |
| `scenes[].asset_queries` | `scene.assetQueries` |
| `cover.headline/subheadline` | `brand` + 开场 scene 的 headline/subheadline |
| `audio.music_mood` | `soundtrack`（title/gainDb/ducking 需人工或 TTS/库选择后回填） |
| `title_candidates` | 发布环节使用，不进渲染 |

映射在社媒运营后端做（导出 `/content-packages/{id}/storyboard`），避免 Replicast 反向理解业务字段。生成 Storyboard 后仍需 Replicast 侧校验 `storyboardSchema` 并补齐资产/音频状态（`READY` 等）。

### 4.2 HyperFrames（Codex 调用）

HyperFrames 以 HTML 合成描述视频（场景、字幕、动画、音频反应），由 CLI 渲染成
MP4。适配器将 ContentPackage 转为 composition 输入：

| ContentPackage | HyperFrames |
|---|---|
| `scenes[].narration_chunk` + subtitle | 场景文本/字幕轨道 |
| `scenes[].visual_hint` + `on_screen_text` | HTML 场景内容与动效提示 |
| `scenes[].estimated_seconds` | 场景时间轴 |
| `audio.voice_hint` | `hyperframes tts` 配音参数 |
| `audio.music_mood` | 音轨/音频反应动画提示 |
| `cover.headline/subheadline` | 片头 title card |

### 4.3 两条渲染路径的取舍（决策参考）

| 维度 | Replicast Storyboard | HyperFrames（Codex 调用） |
|---|---|---|
| 可重复性/工厂化 | 结构化契约 + 版本化渲染，适合批量产线 | 由 Codex 按 composition 生成，更偏"试做/一次性" |
| 视觉自由度 | 预设布局（avatar/broll/comparison/cta） | HTML/CSS/GSAP 几乎无限，适合强视觉创意 |
| 素材权利追踪 | 内置 assetRights/license 校验 | 无，需自行约束 |
| 配音/音频 | 成熟（TTS + 音轨混合 + QA） | CLI 提供 TTS，能力较基础 |
| 生产环境集成 | 自托管服务/API，确定性高 | 依赖 codex CLI 与每次生成的人机介入 |

建议：先用一条真实内容分别走两条路径各出一版对比（内容包不变），再定产线标准；
若追求"工厂化、可审计、带权利追踪"选 Replicast，若追求"视觉实验快、低启动成本"
选 HyperFrames。两者可以共存：内容包同一份，适配器各自独立。

## 5. 存储与版本

- 新表 `content_packages`：`generation_run_id`、`script_version_id`、`content_project_id`、`schema_version`、`target_platform`、`package`（JSONB）、`status`（draft / frozen）、`version`（人工编辑递增）、`created_by`、时间戳。
- 生成时用 `input_hash = hash(script_version_id + target_platform + prompt_version + schema_version)`，同输入可复用；换平台/换脚本自动产生新包，旧包保留。
- 人工编辑 = 复制当前包 + 递增 version，不覆盖已冻结版本（与 ScriptVersion 追加模式一致）。

## 6. 实现切分

### P0：内容包生成（后端契约 + 真实验证）

- 新增 `GeneratedContentPackageResult` schema + 提示词版本（在 script-v3 之上扩展"成片化"输出）。
- `content_packages` 表 + 迁移；生成任务在脚本定稿后可选触发（不阻塞现有脚本流程）。
- API：查看内容包、人工编辑、冻结。
- 测试 + 真实 DeepSeek 生成 3-5 条，人工核对分镜/时长/标题质量。

**P0 完成证据（2026-08-03）**：

- `content_packages` 表（迁移 `20260803_0026`）已上线真实 PostgreSQL，`alembic check` 无漂移。
- API：`POST /content-projects/{id}/content-packages`（触发）、
  `GET /content-packages/{id}`、`GET /content-projects/{id}/content-packages`、
  `PATCH /content-packages/{id}`（人工编辑递增版本）、
  `POST /content-packages/{id}/freeze`（冻结）。
- 6 项自动化测试覆盖生成/读取/编辑版本/冻结/非法合并/平台过滤/超参。
- 真实 DeepSeek 生成成功：`l1-v1:package-v1`，248 字脚本 → 5 分镜
  （avatar_full→broll→broll→comparison→cta，合计约 68s），narration 与脚本逐字一致，
  3 个标题候选、封面、话题、正文、素材需求、配音/BGM 提示齐全；17.6s、$0.001122。

**P0 发现并修复的运行时问题**：DeepSeek V4 默认开启 thinking，推理 token 计入
max_tokens，导致内容包输出被截断（10000 与 16000 上限都失败）。修复：deepseek 的
内容包任务发送 `thinking: {"type": "disabled"}`（格式化任务无需推理）并设
max_tokens 下限 16000。副作用：关闭 thinking 后调用约 17s、成本约 $0.001/次。

**遗留（P1 硬化）**：若未来启用长推理任务（thinking 开启），单次调用可能超过
300s 任务锁超时导致 stale recovery 重跑；需按任务类型延长租约或调用中续心跳。

### P1：渲染适配器（先选一条路径打通）

- 后端导出 `clip-package`（剪辑清单：分镜表、素材清单、封面/标题/话题）+ 首个渲染适配器
  （Replicast Storyboard 或 HyperFrames composition，二选一）。
- 前端：脚本页新增"内容包"tab，可编辑场景、一键导出。
- 验证内容包 → 适配器 → 渲染 → 出片全链路；另一条适配器在第一条跑通后作为可选加装。

### P2：素材与反馈闭环

- 从 evidence 内容自动提取可复用画面/截图（配权利说明）。
- 发布后真实数据回流，校准"标题候选/分镜节奏/爆火筛选"。

## 7. 验收标准

- 一条真实对标内容，从灵感 → 脚本 → 内容包 →（人工剪辑 **或** 任一渲染适配器出片）→ 发布 → 复盘全链路走通。
- 内容包无需改写即可被人工剪辑组使用（分镜/字幕/封面/话题齐备）。
- AI 渲染路径：导出的渲染器输入通过对应契约校验（Storyboard 过 `storyboardSchema`，
  HyperFrames 过 composition lint/预览）。

在这条链路有真实产出之前，"选题到成片一站式"不作为已完成表述。
