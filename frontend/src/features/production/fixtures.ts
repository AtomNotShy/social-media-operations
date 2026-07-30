import type {
  Asset,
  ContentProject,
  Experiment,
  OwnedChannel,
  PerformanceDashboard,
  PublishPlan,
  PublishRecord,
  Review,
  SavedView,
  ScriptVersion,
  TodayDashboard,
  Topic,
} from "@/src/features/production/types";

const now = Date.now();
const at = (offsetHours: number) =>
  new Date(now + offsetHours * 3_600_000).toISOString();

export const demoChannels: OwnedChannel[] = [
  {
    id: "46dddb37-1d09-45c8-8645-852e60cf1001",
    platform: "xiaohongshu",
    external_id: "ordrly-growth",
    display_name: "序章增长实验室",
    handle: "@growth_lab",
    positioning: "帮助小团队把零散灵感变成可验证、可持续的内容增长实验。",
    audience: {
      primary: "5–30 人品牌与内容团队",
      problem: "有内容产出，但缺少可复用流程和清晰复盘",
    },
    content_pillars: ["真实增长案例", "内容生产系统", "数据复盘方法"],
    tone_rules: ["先给结论", "使用具体数字", "避免居高临下"],
    prohibited_topics: ["无证据的收入承诺", "未核实的竞品数据"],
    publishing_mode: "manual",
    active: true,
    created_at: at(-720),
    updated_at: at(-8),
  },
  {
    id: "46dddb37-1d09-45c8-8645-852e60cf1002",
    platform: "douyin",
    external_id: "ordrly-video",
    display_name: "一分钟内容系统",
    handle: "@one_minute_ops",
    positioning: "用一分钟演示一个可直接照做的内容运营动作。",
    audience: { primary: "创业者与运营负责人", problem: "时间少、试错成本高" },
    content_pillars: ["一分钟拆解", "现场改稿", "工具实测"],
    tone_rules: ["口语化", "前三秒具体", "结尾只留一个行动"],
    prohibited_topics: ["夸大工具能力", "未经授权的客户案例"],
    publishing_mode: "manual",
    active: true,
    created_at: at(-540),
    updated_at: at(-12),
  },
];

export const demoTopics: Topic[] = [
  {
    id: "f52aa031-0c87-4ec6-b183-e2ed764a2001",
    owned_channel_id: demoChannels[0].id,
    title: "为什么你的内容日历越排越满，转化却没有变好",
    audience_problem: "团队把发布频率当成目标，缺少可验证的业务假设。",
    angle: "从一张失败排期表反推选题、证据与转化动作。",
    hook: "一周发 14 条，线索还是 0：问题不在勤奋。",
    evidence_refs: ["inspiration:a11d18b5-aeb6-4fc1-a146-1c1cd843a001"],
    status: "selected",
    version: 2,
    created_by: null,
    created_at: at(-76),
    updated_at: at(-10),
  },
  {
    id: "f52aa031-0c87-4ec6-b183-e2ed764a2002",
    owned_channel_id: demoChannels[1].id,
    title: "把模糊选题改成前三秒就能判断的场景",
    audience_problem: "选题正确但开场过于抽象，用户无法判断与自己是否相关。",
    angle: "现场对照 3 个改稿版本。",
    hook: "别再用“你是不是也…”开场了。",
    evidence_refs: ["pattern:807dd26b-7cc0-4882-b421-6333f1938001"],
    status: "idea",
    version: 1,
    created_by: null,
    created_at: at(-28),
    updated_at: at(-6),
  },
  {
    id: "f52aa031-0c87-4ec6-b183-e2ed764a2003",
    owned_channel_id: demoChannels[0].id,
    title: "五分钟复盘模板：把点赞和成交分开看",
    audience_problem: "团队用互动指标替代业务结果。",
    angle: "曝光、互动、转化三层指标的最小复盘表。",
    hook: "高赞不等于有效，这张表先帮你把指标分开。",
    evidence_refs: [],
    status: "idea",
    version: 1,
    created_by: null,
    created_at: at(-20),
    updated_at: at(-4),
  },
];

export const demoProjects: ContentProject[] = [
  {
    id: "a3c3ba95-55a9-479c-a32b-7a8fca5d3001",
    topic_id: demoTopics[0].id,
    owned_channel_id: demoChannels[0].id,
    title: "内容日历为什么救不了转化",
    status: "review",
    owner_user_id: null,
    due_at: at(4),
    version: 4,
    created_at: at(-52),
    updated_at: at(-2),
  },
  {
    id: "a3c3ba95-55a9-479c-a32b-7a8fca5d3002",
    topic_id: demoTopics[1].id,
    owned_channel_id: demoChannels[1].id,
    title: "三种具体开场的现场改稿",
    status: "scripting",
    owner_user_id: null,
    due_at: at(28),
    version: 2,
    created_at: at(-22),
    updated_at: at(-3),
  },
];

export const demoScripts: ScriptVersion[] = [
  {
    id: "3c0315e8-19ce-4b92-92be-fea9054b4001",
    content_project_id: demoProjects[0].id,
    version_no: 2,
    body: "一周发 14 条，线索还是 0：问题不在勤奋。\n\n我拿一张真实排期表给你看。它写满了发布日期，却没有一条内容写清受众问题、证据和下一步行动。\n\n把日历改成实验表：每条内容只验证一个假设，曝光、互动和转化分开记录。下周不要先加数量，先淘汰没有证据的选题。",
    structured_body: {
      hook: "一周发 14 条，线索还是 0：问题不在勤奋。",
      sections: ["失败排期表", "实验表改造", "单一行动"],
    },
    created_by: null,
    generation_run_id: "09a30aac-a88b-4a90-8cf5-b7a273e44001",
    change_note: "缩短开场并补充证据段",
    created_at: at(-2),
  },
  {
    id: "3c0315e8-19ce-4b92-92be-fea9054b4002",
    content_project_id: demoProjects[0].id,
    version_no: 1,
    body: "你的内容日历可能正在让团队更忙，却没有让结果更好。",
    structured_body: null,
    created_by: null,
    generation_run_id: null,
    change_note: "人工初稿",
    created_at: at(-18),
  },
  {
    id: "3c0315e8-19ce-4b92-92be-fea9054b4003",
    content_project_id: demoProjects[1].id,
    version_no: 1,
    body: "别再用“你是不是也…”开场了。先给出一个只有目标用户会遇到的具体瞬间。",
    structured_body: null,
    created_by: null,
    generation_run_id: null,
    change_note: "人工初稿",
    created_at: at(-3),
  },
];

export const demoAssets: Asset[] = [
  {
    id: "7dc930ff-8f31-42b0-ad7b-229121825001",
    content_project_id: demoProjects[0].id,
    asset_type: "image",
    storage_key: "demo/content-calendar-before-after.png",
    mime_type: "image/png",
    size_bytes: 824_120,
    checksum: "a".repeat(64),
    source_type: "uploaded",
    rights_note: "内部团队制作，可用于品牌自有账号。",
    created_by: null,
    created_at: at(-7),
  },
  {
    id: "7dc930ff-8f31-42b0-ad7b-229121825002",
    content_project_id: demoProjects[0].id,
    asset_type: "document",
    storage_key: "demo/experiment-calendar-template.pdf",
    mime_type: "application/pdf",
    size_bytes: 284_010,
    checksum: "b".repeat(64),
    source_type: "generated",
    rights_note: "由团队原创模板生成。",
    created_by: null,
    created_at: at(-5),
  },
];

export const demoPlans: PublishPlan[] = [
  {
    id: "e0806dff-404f-4bea-97d7-ed8629986001",
    content_project_id: demoProjects[0].id,
    owned_channel_id: demoChannels[0].id,
    scheduled_at: at(5),
    status: "draft",
    publishing_mode: "manual",
    publish_payload: {
      title: "内容日历为什么救不了转化",
      body: "发布正文随最新脚本版本更新",
      hashtags: ["内容运营", "增长实验", "团队协作"],
      cover_note: "使用排期表前后对比图",
    },
    approved_by: null,
    approved_at: null,
    version: 2,
    created_at: at(-20),
    updated_at: at(-2),
  },
  {
    id: "e0806dff-404f-4bea-97d7-ed8629986002",
    content_project_id: demoProjects[1].id,
    owned_channel_id: demoChannels[1].id,
    scheduled_at: at(30),
    status: "approved",
    publishing_mode: "manual",
    publish_payload: {
      title: "三种具体开场的现场改稿",
      hashtags: ["短视频文案", "开场钩子"],
    },
    approved_by: null,
    approved_at: at(-1),
    version: 2,
    created_at: at(-12),
    updated_at: at(-1),
  },
  {
    id: "e0806dff-404f-4bea-97d7-ed8629986003",
    content_project_id: demoProjects[0].id,
    owned_channel_id: demoChannels[0].id,
    scheduled_at: at(-48),
    status: "published",
    publishing_mode: "manual",
    publish_payload: { title: "增长实验表：先别追发布数量" },
    approved_by: null,
    approved_at: at(-52),
    version: 4,
    created_at: at(-80),
    updated_at: at(-47),
  },
];

export const demoRecords: PublishRecord[] = [
  {
    id: "65c5fed1-5ea2-4b87-852d-f95d326a7001",
    publish_plan_id: demoPlans[2].id,
    platform_content_id: "xhs-demo-published-01",
    published_url: "https://www.xiaohongshu.com/explore/demo-published",
    published_at: at(-48),
    result_payload: { matched_publish_package: true },
    created_by: null,
    created_at: at(-47.8),
  },
];

export const demoReviews: Review[] = [
  {
    id: "8d2bd906-4920-458e-9926-674b52ab8001",
    publish_record_id: demoRecords[0].id,
    review_window: "24h",
    metrics: {
      impressions: 18400,
      likes: 836,
      comments: 91,
      favorites: 412,
      shares: 58,
      leads: 13,
    },
    analysis: {
      hypothesis: "具体损失开场会提高收藏和线索率",
      outcome: "收藏率高于近 30 天基线，线索数仍需 7 天窗口确认。",
      baseline_favorites_rate: "1.7%",
      actual_favorites_rate: "2.2%",
    },
    next_actions: ["保留具体损失开场", "测试更短的行动指令", "7 天后补录线索质量"],
    created_by: null,
    created_at: at(-23),
  },
];

export const demoToday: TodayDashboard = {
  timezone: "Australia/Melbourne",
  window_start: new Date().toISOString().slice(0, 10) + "T00:00:00+10:00",
  window_end: new Date(now + 86_400_000).toISOString(),
  projects_due: [demoProjects[0]],
  publish_plans: [demoPlans[0]],
  active_job_count: 2,
  published_waiting_review_count: 1,
};

export const demoPerformance: PerformanceDashboard = {
  from_at: at(-720),
  to_at: at(0),
  totals: {
    published_count: 12,
    review_count: 9,
    exposure: 284_300,
    interactions: 18_942,
    conversions: 137,
  },
  records: [
    {
      publish_record_id: demoRecords[0].id,
      publish_plan_id: demoPlans[2].id,
      published_at: demoRecords[0].published_at,
      published_url: demoRecords[0].published_url,
      latest_review_window: "24h",
      exposure: 18_400,
      interactions: 1_397,
      conversions: 13,
    },
  ],
};

export const demoSavedViews: SavedView[] = [
  {
    id: "987399bd-2179-4c49-aa35-2eb813db9001",
    entity_type: "topics",
    user_id: "6fd367fb-88b5-4e9c-91d0-bb850ef79001",
    name: "本周已选",
    query_params: { status: "selected" },
    is_shared: true,
    version: 1,
    created_at: at(-24),
    updated_at: at(-24),
  },
];

export const demoExperiments: Experiment[] = [
  {
    id: "bf64d91b-fccb-41d7-b589-53148899a001",
    owned_channel_id: demoChannels[0].id,
    name: "具体损失 vs 结果承诺开场",
    hypothesis: "具体损失场景比抽象结果承诺带来更高收藏率。",
    primary_metric: "favorites_rate",
    variants: [
      { key: "loss", name: "具体损失", description: "用可量化损失开场" },
      { key: "promise", name: "结果承诺", description: "用目标结果开场" },
    ],
    status: "running",
    version: 2,
    created_by: null,
    started_at: at(-168),
    ended_at: null,
    created_at: at(-180),
    updated_at: at(-24),
  },
];

