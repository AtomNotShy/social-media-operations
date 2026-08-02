"use client";

import {
  Bot,
  CheckCircle2,
  KeyRound,
  LoaderCircle,
  Pencil,
  PlugZap,
  Plus,
  Save,
  TestTube2,
} from "lucide-react";
import { useState } from "react";
import { ErrorState } from "@/src/components/ui/error-state";
import {
  Dialog,
  InlineError,
  inputClass,
  primaryButton,
  secondaryButton,
} from "@/src/features/production/ui";
import {
  useAddAIConnection,
  useAISettings,
  useTestAIConnection,
  useUpdateAIConnection,
  useUpdateAIModelRoute,
} from "@/src/features/settings/queries";
import type {
  AIConnection,
  AIConnectionCreate,
  AIModelRoute,
  AIModelRouteUpsert,
  AISettings,
  AITaskType,
} from "@/src/features/settings/types";

const taskLabels: Record<AITaskType, string> = {
  l1: "L1 快速分析",
  l2: "L2 深度分析",
  generation: "脚本生成",
};

export function AISettingsPanel({
  workspaceId,
  canManage,
}: {
  workspaceId: string;
  canManage: boolean;
}) {
  const settings = useAISettings(workspaceId);
  const test = useTestAIConnection(workspaceId);
  const update = useUpdateAIConnection(workspaceId);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<AIConnection | null>(null);
  const [testedId, setTestedId] = useState<string | null>(null);

  if (settings.isLoading) {
    return <div className="h-44 animate-pulse rounded-xl bg-surface" />;
  }
  if (settings.error) {
    return (
      <section className="rounded-xl border border-border bg-surface shadow-panel">
        <ErrorState
          message={
            (settings.error as { message?: string }).message ??
            "AI 连接设置暂时无法读取。"
          }
          onRetry={() => settings.refetch()}
          requestId={(settings.error as { requestId?: string }).requestId}
        />
      </section>
    );
  }
  if (!settings.data) return null;

  return (
    <>
      <section className="rounded-xl border border-border bg-surface shadow-panel">
        <div className="flex flex-col gap-3 border-b border-border p-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="rounded-lg bg-primary-50 p-2 text-primary-600">
              <Bot aria-hidden="true" size={18} />
            </span>
            <div>
              <h2 className="font-semibold">AI 模型连接</h2>
              <p className="mt-1 text-xs leading-5 text-text-muted">
                在控制台配置 DeepSeek、OpenAI 或兼容服务。密钥加密保存在服务端，页面只返回掩码。
              </p>
            </div>
          </div>
          {canManage ? (
            <button
              className={primaryButton}
              onClick={() => setCreateOpen(true)}
              type="button"
            >
              <Plus size={15} />
              添加连接
            </button>
          ) : null}
        </div>

        <div className="p-5">
          {settings.data.connections.length ? (
            <div className="grid gap-3 md:grid-cols-2">
              {settings.data.connections.map((connection) => (
                <article
                  className="rounded-lg border border-border p-4"
                  key={connection.id}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="truncate text-sm font-semibold">
                          {connection.name}
                        </h3>
                        <span
                          className={`size-2 rounded-full ${
                            connection.enabled ? "bg-success" : "bg-text-muted"
                          }`}
                          title={connection.enabled ? "已启用" : "已停用"}
                        />
                      </div>
                      <p className="mt-1 truncate text-[11px] text-text-muted">
                        {providerLabel(
                          settings.data.providers,
                          connection.provider,
                        )}{" "}
                        · {connection.base_url}
                      </p>
                    </div>
                    <span
                      className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-medium ${
                        connection.api_key_configured
                          ? "bg-success/10 text-success"
                          : "bg-warning/10 text-warning"
                      }`}
                    >
                      {connection.api_key_configured
                        ? connection.api_key_masked || "密钥已配置"
                        : "未配置密钥"}
                    </span>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {canManage ? (
                      <>
                        <button
                          className={secondaryButton}
                          disabled={
                            test.isPending && testedId === connection.id
                          }
                          onClick={() => {
                            setTestedId(connection.id);
                            test.reset();
                            test.mutate({ connection });
                          }}
                          type="button"
                        >
                          {test.isPending && testedId === connection.id ? (
                            <LoaderCircle
                              className="animate-spin"
                              size={14}
                            />
                          ) : (
                            <TestTube2 size={14} />
                          )}
                          测试连接
                        </button>
                        <button
                          className={secondaryButton}
                          onClick={() => setEditing(connection)}
                          type="button"
                        >
                          <Pencil size={14} />
                          编辑
                        </button>
                        <button
                          className={secondaryButton}
                          disabled={update.isPending}
                          onClick={() =>
                            update.mutate({
                              connection,
                              input: {
                                enabled: !connection.enabled,
                                clear_api_key: false,
                              },
                            })
                          }
                          type="button"
                        >
                          {connection.enabled ? "停用" : "启用"}
                        </button>
                      </>
                    ) : null}
                  </div>
                  {testedId === connection.id && test.data ? (
                    <p className="mt-3 flex items-center gap-1.5 rounded-lg bg-success/10 p-2.5 text-xs text-success">
                      <CheckCircle2 size={14} />
                      连接正常 · {test.data.latency_ms}ms ·{" "}
                      {test.data.available_models.length} 个可用模型
                    </p>
                  ) : null}
                  {testedId === connection.id ? (
                    <InlineError error={test.error} />
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-border p-6 text-center">
              <PlugZap className="mx-auto text-text-muted" size={24} />
              <p className="mt-3 text-sm font-medium">尚未配置 AI 连接</p>
              <p className="mt-1 text-xs leading-5 text-text-muted">
                添加连接前，分析和生成任务会返回未配置状态，不会伪造结果。
              </p>
            </div>
          )}

          <div className="my-5 h-px bg-border" />
          <div>
            <h3 className="text-sm font-semibold">任务模型路由</h3>
            <p className="mt-1 text-xs leading-5 text-text-muted">
              分别指定快速分析、深度分析与脚本生成使用的连接和模型。
            </p>
          </div>
          <div className="mt-4 grid gap-3">
            {(["l1", "l2", "generation"] as AITaskType[]).map((taskType) => {
              const route = settings.data.routes.find(
                (item) => item.task_type === taskType,
              );
              return (
                <RouteEditor
                  canManage={canManage}
                  connections={settings.data.connections}
                  key={`${taskType}:${route?.connection_id}:${route?.model}`}
                  providers={settings.data.providers}
                  route={route}
                  taskType={taskType}
                  workspaceId={workspaceId}
                />
              );
            })}
          </div>
        </div>
      </section>

      <CreateConnectionDialog
        onClose={() => setCreateOpen(false)}
        open={createOpen}
        providers={settings.data.providers}
        workspaceId={workspaceId}
      />
      <EditConnectionDialog
        connection={editing}
        onClose={() => setEditing(null)}
        workspaceId={workspaceId}
      />
    </>
  );
}

function RouteEditor({
  workspaceId,
  taskType,
  route,
  connections,
  providers,
  canManage,
}: {
  workspaceId: string;
  taskType: AITaskType;
  route?: AIModelRoute;
  connections: AIConnection[];
  providers: AISettings["providers"];
  canManage: boolean;
}) {
  const update = useUpdateAIModelRoute(workspaceId);
  const firstConnection =
    connections.find((item) => item.enabled) ?? connections[0];
  const [value, setValue] = useState<AIModelRouteUpsert>({
    connection_id: route?.connection_id ?? firstConnection?.id ?? "",
    model: route?.model ?? "",
    temperature: route?.temperature ?? "0.2",
    max_tokens: route?.max_tokens ?? 2000,
    input_cost_per_million_usd:
      route?.input_cost_per_million_usd ?? "0",
    output_cost_per_million_usd:
      route?.output_cost_per_million_usd ?? "0",
  });
  const selectedConnection = connections.find(
    (item) => item.id === value.connection_id,
  );
  const selectedCatalog = providers.find(
    (item) => item.provider === selectedConnection?.provider,
  );
  const modelPricing = selectedCatalog?.model_pricing?.find(
    (item) => item.model === value.model.trim(),
  );

  return (
    <form
      className="grid gap-3 rounded-lg bg-surface-subtle p-4 lg:grid-cols-[150px_1fr_1fr_90px_auto] lg:items-end"
      onSubmit={(event) => {
        event.preventDefault();
        update.mutate({ taskType, input: value });
      }}
    >
      <div>
        <p className="text-xs font-semibold">{taskLabels[taskType]}</p>
        <p className="mt-1 text-[10px] text-text-muted">
          {route?.configured ? "已配置" : "未配置"}
        </p>
      </div>
      <label className="text-[11px] font-medium">
        连接
        <select
          className={`${inputClass} mt-1 min-h-9`}
          disabled={!canManage || !connections.length}
          onChange={(event) =>
            setValue({ ...value, connection_id: event.target.value })
          }
          value={value.connection_id}
        >
          {!connections.length ? <option value="">暂无连接</option> : null}
          {connections.map((connection) => (
            <option key={connection.id} value={connection.id}>
              {connection.name}
              {connection.enabled ? "" : "（已停用）"}
            </option>
          ))}
        </select>
      </label>
      <label className="text-[11px] font-medium">
        模型
        <input
          className={`${inputClass} mt-1 min-h-9`}
          disabled={!canManage}
          onChange={(event) => setValue({ ...value, model: event.target.value })}
          placeholder="模型 ID"
          value={value.model}
        />
      </label>
      <label className="text-[11px] font-medium">
        Max tokens
        <input
          className={`${inputClass} mt-1 min-h-9`}
          disabled={!canManage}
          max={32768}
          min={256}
          onChange={(event) =>
            setValue({ ...value, max_tokens: Number(event.target.value) })
          }
          type="number"
          value={value.max_tokens}
        />
      </label>
      {canManage ? (
        <button
          className={secondaryButton}
          disabled={
            update.isPending || !value.connection_id || !value.model.trim()
          }
          type="submit"
        >
          {update.isPending ? (
            <LoaderCircle className="animate-spin" size={14} />
          ) : (
            <Save size={14} />
          )}
          保存
        </button>
      ) : null}
      {modelPricing ? (
        <p className="text-[10px] leading-4 text-text-muted lg:col-start-2 lg:col-span-4">
          官方定价（{selectedCatalog?.pricing_catalog_version}）：输入 $
          {modelPricing.input_cost_per_million_usd}/M · 输出 $
          {modelPricing.output_cost_per_million_usd}/M，保存后由系统维护，无需手填。
        </p>
      ) : null}
      <div className="lg:col-start-2 lg:col-span-4">
        <InlineError error={update.error} />
      </div>
    </form>
  );
}

function CreateConnectionDialog({
  workspaceId,
  providers,
  open,
  onClose,
}: {
  workspaceId: string;
  providers: AISettings["providers"];
  open: boolean;
  onClose: () => void;
}) {
  const create = useAddAIConnection(workspaceId);
  const first = providers[0];
  const [provider, setProvider] =
    useState<AIConnectionCreate["provider"]>(first?.provider ?? "deepseek");
  const selected = providers.find((item) => item.provider === provider);
  const [name, setName] = useState("DeepSeek Production");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(first?.default_base_url ?? "");
  const [model, setModel] = useState(first?.suggested_models[0] ?? "");

  return (
    <Dialog
      description="密钥通过加密接口写入服务端；提交后浏览器只能读取掩码。"
      onClose={onClose}
      open={open}
      title="添加 AI 连接"
    >
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate(
            {
              name: name.trim(),
              provider,
              api_key: apiKey.trim() || null,
              base_url: baseUrl.trim() || null,
              model: model.trim(),
              use_for: ["l1", "l2", "generation"],
              timeout_seconds: 60,
              json_mode: true,
              temperature: 0.2,
              max_tokens: 2000,
              input_cost_per_million_usd: 0,
              output_cost_per_million_usd: 0,
            },
            {
              onSuccess: () => {
                setApiKey("");
                onClose();
              },
            },
          );
        }}
      >
        <label className="text-sm font-medium">
          连接名称
          <input
            className={`${inputClass} mt-2`}
            maxLength={255}
            onChange={(event) => setName(event.target.value)}
            required
            value={name}
          />
        </label>
        <label className="text-sm font-medium">
          服务商
          <select
            className={`${inputClass} mt-2`}
            onChange={(event) => {
              const next = event.target
                .value as AIConnectionCreate["provider"];
              const catalog = providers.find(
                (item) => item.provider === next,
              );
              setProvider(next);
              setBaseUrl(catalog?.default_base_url ?? "");
              setModel(catalog?.suggested_models[0] ?? "");
            }}
            value={provider}
          >
            {providers.map((item) => (
              <option key={item.provider} value={item.provider}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium">
          API Key
          <div className="relative mt-2">
            <KeyRound
              className="absolute left-3 top-3.5 text-text-muted"
              size={15}
            />
            <input
              autoComplete="off"
              className={`${inputClass} pl-9`}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="仅本次提交使用，不会回显"
              required={provider !== "openai_compatible"}
              type="password"
              value={apiKey}
            />
          </div>
        </label>
        <label className="text-sm font-medium">
          Base URL
          <input
            className={`${inputClass} mt-2`}
            disabled={!selected?.custom_base_url}
            onChange={(event) => setBaseUrl(event.target.value)}
            placeholder="https://api.example.com/v1"
            required={Boolean(selected?.custom_base_url)}
            type="url"
            value={baseUrl}
          />
        </label>
        <label className="text-sm font-medium">
          默认模型
          <input
            className={`${inputClass} mt-2`}
            list="ai-model-suggestions"
            onChange={(event) => setModel(event.target.value)}
            required
            value={model}
          />
          <datalist id="ai-model-suggestions">
            {selected?.suggested_models.map((item) => (
              <option key={item} value={item} />
            ))}
          </datalist>
        </label>
        {(() => {
          const pricing = selected?.model_pricing?.find(
            (item) => item.model === model.trim(),
          );
          if (!pricing) return null;
          return (
            <div className="rounded-md bg-surface-subtle p-3 text-[11px] leading-5 text-text-muted">
              <p className="font-semibold text-text">
                官方定价（{selected?.pricing_catalog_version}）
              </p>
              <p>
                输入 ${pricing.input_cost_per_million_usd}/M · 输出 $
                {pricing.output_cost_per_million_usd}/M
                {pricing.cache_hit_input_cost_per_million_usd
                  ? ` · 缓存命中输入 $${pricing.cache_hit_input_cost_per_million_usd}/M`
                  : ""}
              </p>
              {pricing.notes ? <p>{pricing.notes}</p> : null}
              <p>
                来源：{" "}
                <span className="break-all">{selected?.pricing_source_url}</span>
              </p>
            </div>
          );
        })()}
        <InlineError error={create.error} />
        <button
          className={primaryButton}
          disabled={
            create.isPending ||
            !name.trim() ||
            !model.trim() ||
            (provider !== "openai_compatible" && !apiKey.trim())
          }
          type="submit"
        >
          {create.isPending ? (
            <LoaderCircle className="animate-spin" size={15} />
          ) : (
            <Plus size={15} />
          )}
          保存连接
        </button>
      </form>
    </Dialog>
  );
}

function EditConnectionDialog({
  workspaceId,
  connection,
  onClose,
}: {
  workspaceId: string;
  connection: AIConnection | null;
  onClose: () => void;
}) {
  if (!connection) return null;
  return (
    <EditConnectionForm
      connection={connection}
      onClose={onClose}
      workspaceId={workspaceId}
    />
  );
}

function EditConnectionForm({
  workspaceId,
  connection,
  onClose,
}: {
  workspaceId: string;
  connection: AIConnection;
  onClose: () => void;
}) {
  const update = useUpdateAIConnection(workspaceId);
  const [name, setName] = useState(connection.name);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(connection.base_url);
  const [clearKey, setClearKey] = useState(false);

  return (
    <Dialog
      description="API Key 留空会保留原值；只有勾选清除才会删除服务端密钥。"
      onClose={onClose}
      open
      title="编辑 AI 连接"
    >
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          update.mutate(
            {
              connection,
              input: {
                name: name.trim(),
                base_url: baseUrl.trim() || null,
                api_key: apiKey.trim() || null,
                clear_api_key: clearKey,
              },
            },
            { onSuccess: onClose },
          );
        }}
      >
        <label className="text-sm font-medium">
          连接名称
          <input
            className={`${inputClass} mt-2`}
            onChange={(event) => setName(event.target.value)}
            required
            value={name}
          />
        </label>
        <label className="text-sm font-medium">
          Base URL
          <input
            className={`${inputClass} mt-2`}
            disabled={connection.provider !== "openai_compatible"}
            onChange={(event) => setBaseUrl(event.target.value)}
            type="url"
            value={baseUrl}
          />
        </label>
        <label className="text-sm font-medium">
          更新 API Key
          <input
            autoComplete="off"
            className={`${inputClass} mt-2`}
            disabled={clearKey}
            onChange={(event) => setApiKey(event.target.value)}
            placeholder={connection.api_key_masked || "留空保持不变"}
            type="password"
            value={apiKey}
          />
        </label>
        <label className="flex items-start gap-3 rounded-lg bg-danger/5 p-3 text-sm">
          <input
            checked={clearKey}
            className="mt-1"
            onChange={(event) => setClearKey(event.target.checked)}
            type="checkbox"
          />
          <span>
            <strong className="block text-xs">清除已保存的 API Key</strong>
            <span className="mt-1 block text-[11px] leading-5 text-text-muted">
              清除后依赖此连接的真实模型调用会失败，直到重新配置密钥。
            </span>
          </span>
        </label>
        <InlineError error={update.error} />
        <button
          className={primaryButton}
          disabled={update.isPending || !name.trim()}
          type="submit"
        >
          {update.isPending ? (
            <LoaderCircle className="animate-spin" size={15} />
          ) : (
            <Save size={15} />
          )}
          保存修改
        </button>
      </form>
    </Dialog>
  );
}

function providerLabel(
  providers: AISettings["providers"],
  provider: string,
): string {
  return (
    providers.find((item) => item.provider === provider)?.label ?? provider
  );
}
