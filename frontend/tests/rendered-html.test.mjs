import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const templateRoot = new URL("../", import.meta.url);

async function render(pathname) {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${pathname}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("redirects the root to the daily production workbench", async () => {
  const response = await render("/");
  assert.equal(response.status, 307);
  assert.equal(
    response.headers.get("location"),
    "http://localhost/w/demo/today",
  );
});

test("server-renders the tracked profiles workbench", async () => {
  const response = await render("/w/demo/tracked-profiles");
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>对标账号 · 序章<\/title>/i);
  assert.match(html, /对标账号/);
  assert.match(html, /演示工作区/);
  assert.match(html, /搜索或跳转/);
  assert.doesNotMatch(
    html,
    /连接开发后端|连接真实后端|连接本地后端/,
  );
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape/i);
});

test("keeps development login out of the production build", async () => {
  const [login, workspace] = await Promise.all([
    render("/login"),
    render("/workspaces/new"),
  ]);
  assert.equal(login.status, 307);
  assert.equal(
    login.headers.get("location"),
    "http://localhost/w/demo/today",
  );
  assert.equal(workspace.status, 200);
  assert.match(await workspace.text(), /创建第一个工作区/);
});

test("serves the tracked profile detail route", async () => {
  const response = await render(
    "/w/demo/tracked-profiles/80b12167-923c-4ec0-b3df-79f2ce64d76c",
  );
  assert.equal(response.status, 200);
  assert.match(await response.text(), /正在加载账号详情/);
});

test("serves the inspiration library and detail routes", async () => {
  const [library, detail] = await Promise.all([
    render("/w/demo/inspirations"),
    render("/w/demo/inspirations/a11d18b5-aeb6-4fc1-a146-1c1cd843a001"),
  ]);
  assert.equal(library.status, 200);
  assert.equal(detail.status, 200);
  assert.match(await library.text(), /<title>灵感库 · 序章<\/title>/i);
  assert.match(await detail.text(), /正在加载灵感详情/);
});

test("serves every P1 route instead of the generic placeholder", async () => {
  const responses = await Promise.all([
    render("/w/demo/discover"),
    render("/w/demo/patterns"),
    render("/w/demo/patterns/807dd26b-7cc0-4882-b421-6333f1938001"),
    render("/w/demo/usage"),
  ]);
  for (const response of responses) assert.equal(response.status, 200);
  const html = await Promise.all(responses.map((response) => response.text()));
  assert.match(html[0], /搜索与热榜/);
  assert.match(html[1], /可复用模式/);
  assert.match(html[2], /正在加载模式详情/);
  assert.match(html[3], /用量与费用/);
  for (const page of html) assert.doesNotMatch(page, /页面骨架已准备/);
});

test("serves the complete P2 production workflow instead of placeholders", async () => {
  const routes = [
    ["/w/demo/today", /正在整理今天的工作/],
    ["/w/demo/channels", /自有账号/],
    [
      "/w/demo/channels/46dddb37-1d09-45c8-8645-852e60cf1001",
      /正在加载账号分析/,
    ],
    ["/w/demo/topics", /候选选题/],
    [
      "/w/demo/topics/f52aa031-0c87-4ec6-b183-e2ed764a2001",
      /正在加载选题/,
    ],
    ["/w/demo/content-projects", /内容项目/],
    [
      "/w/demo/content-projects/a3c3ba95-55a9-479c-a32b-7a8fca5d3001",
      /正在加载内容项目/,
    ],
    [
      "/w/demo/content-projects/a3c3ba95-55a9-479c-a32b-7a8fca5d3001/script",
      /正在加载脚本工作台/,
    ],
    [
      "/w/demo/content-projects/a3c3ba95-55a9-479c-a32b-7a8fca5d3001/assets",
      /项目素材/,
    ],
    ["/w/demo/assets", /素材库/],
    ["/w/demo/schedule", /内容排期/],
    ["/w/demo/reviews", /内容表现/],
    [
      "/w/demo/reviews/65c5fed1-5ea2-4b87-852d-f95d326a7001",
      /正在加载复盘记录/,
    ],
  ];
  for (const [route, expected] of routes) {
    const response = await render(route);
    assert.equal(response.status, 200, route);
    const html = await response.text();
    assert.match(html, expected, route);
    assert.doesNotMatch(html, /P2 页面尚未启用/, route);
  }
});

test("serves P3 search, saved views, experiments, and productivity surfaces", async () => {
  const [experiments, topics] = await Promise.all([
    render("/w/demo/experiments"),
    render("/w/demo/topics"),
  ]);
  assert.equal(experiments.status, 200);
  assert.equal(topics.status, 200);
  const experimentHtml = await experiments.text();
  const topicHtml = await topics.text();
  assert.match(experimentHtml, /运营实验/);
  assert.match(experimentHtml, /搜索或跳转/);
  assert.match(experimentHtml, /共享保存视图和实验分组/);
  assert.match(topicHtml, /保存视图/);
  assert.doesNotMatch(experimentHtml, /P2 页面尚未启用/);
});

test("serves the live settings center without milestone placeholder copy", async () => {
  const response = await render("/w/demo/settings");
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /<title>工作区设置 · 序章<\/title>/i);
  assert.match(html, /管理工作区信息、调用预算、运行安全与成员权限/);
  assert.match(html, /数据连接/);
  assert.match(html, /任务通知/);
  assert.doesNotMatch(html, /P0 先展示系统边界|status: "P0"|>P0</);
  assert.doesNotMatch(html, /规划中/);
});

test("removes all disposable starter-preview artifacts", async () => {
  const [layout, packageJson] = await Promise.all([
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);

  assert.match(layout, /序章 · 社媒运营工作台/);
  assert.doesNotMatch(layout, /Starter Project|codex-preview|_sites-preview/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);

  await assert.rejects(access(new URL("../app/_sites-preview", import.meta.url)));
  await access(new URL("../public/og.png", import.meta.url));
  await access(new URL("../src/api/generated/schema.ts", import.meta.url));
  await access(new URL("../openapi.json", import.meta.url));
  await access(new URL(".openai/hosting.json", templateRoot));
});
