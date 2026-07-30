import type {
  AISettings,
  ProviderHealth,
  QueueHealth,
  Workspace,
  WorkspaceMember,
} from "@/src/features/settings/types";

export const demoAISettings: AISettings = {
  providers: [
    {
      provider: "deepseek",
      label: "DeepSeek",
      default_base_url: "https://api.deepseek.com",
      suggested_models: ["deepseek-chat", "deepseek-reasoner"],
      custom_base_url: false,
    },
    {
      provider: "openai",
      label: "OpenAI",
      default_base_url: "https://api.openai.com/v1",
      suggested_models: ["gpt-5-mini", "gpt-5"],
      custom_base_url: false,
    },
    {
      provider: "openai_compatible",
      label: "OpenAI-Compatible",
      default_base_url: null,
      suggested_models: [],
      custom_base_url: true,
    },
  ],
  connections: [
    {
      id: "94ed33fc-bb4c-4197-928c-2c55baca5001",
      name: "DeepSeek Production",
      provider: "deepseek",
      base_url: "https://api.deepseek.com",
      enabled: true,
      timeout_seconds: 60,
      json_mode: true,
      api_key_configured: true,
      api_key_masked: "••••7A2C",
      created_at: "2026-07-28T00:00:00Z",
      updated_at: "2026-07-31T00:00:00Z",
    },
  ],
  routes: [
    {
      task_type: "l1",
      connection_id: "94ed33fc-bb4c-4197-928c-2c55baca5001",
      connection_name: "DeepSeek Production",
      provider: "deepseek",
      model: "deepseek-chat",
      temperature: "0.2",
      max_tokens: 2000,
      input_cost_per_million_usd: "0",
      output_cost_per_million_usd: "0",
      configured: true,
    },
    {
      task_type: "l2",
      connection_id: "94ed33fc-bb4c-4197-928c-2c55baca5001",
      connection_name: "DeepSeek Production",
      provider: "deepseek",
      model: "deepseek-reasoner",
      temperature: "0.2",
      max_tokens: 4000,
      input_cost_per_million_usd: "0",
      output_cost_per_million_usd: "0",
      configured: true,
    },
    {
      task_type: "generation",
      connection_id: "94ed33fc-bb4c-4197-928c-2c55baca5001",
      connection_name: "DeepSeek Production",
      provider: "deepseek",
      model: "deepseek-chat",
      temperature: "0.7",
      max_tokens: 4000,
      input_cost_per_million_usd: "0",
      output_cost_per_million_usd: "0",
      configured: true,
    },
  ],
};

export const demoWorkspace: Workspace = {
  id: "demo",
  name: "演示工作区",
  timezone: "Australia/Melbourne",
  daily_provider_budget_usd: "5.00",
  daily_ai_budget_usd: "5.00",
  settings: {
    external_calls: {
      paused: false,
      reason: null,
      changed_at: "2026-07-31T01:30:00Z",
    },
  },
  created_at: "2026-07-01T00:00:00Z",
  updated_at: "2026-07-31T01:30:00Z",
};

export const demoMembers: WorkspaceMember[] = [
  {
    id: "80c9be44-953a-4fe8-8022-5504cb9a1001",
    role: "owner",
    created_at: "2026-07-01T00:00:00Z",
    user: {
      id: "a49342c8-dcd9-40aa-9801-209f71c72001",
      display_name: "工作区 Owner",
      email: "owner@example.com",
      external_subject: "demo-owner",
      status: "active",
    },
  },
  {
    id: "80c9be44-953a-4fe8-8022-5504cb9a1002",
    role: "editor",
    created_at: "2026-07-15T00:00:00Z",
    user: {
      id: "a49342c8-dcd9-40aa-9801-209f71c72002",
      display_name: "内容编辑",
      email: "editor@example.com",
      external_subject: "demo-editor",
      status: "active",
    },
  },
];

export const demoQueueHealth: QueueHealth = {
  counts: { pending: 2, running: 1, succeeded: 18 },
  active_count: 3,
  oldest_active_created_at: "2026-07-31T01:18:00Z",
  stale_running_count: 0,
};

export const demoProviderHealth: ProviderHealth = {
  provider: "tikhub",
  endpoints: [
    {
      endpoint_key: "xiaohongshu.note.detail",
      request_count_24h: 42,
      success_count_24h: 40,
      failure_count_24h: 2,
      average_latency_ms_24h: 618,
      estimated_cost_usd_24h: "0.840000",
      last_request_at: "2026-07-31T01:28:00Z",
      circuit: {
        state: "closed",
        consecutive_failures: 0,
        retry_after: null,
        last_error_code: null,
      },
    },
  ],
};
