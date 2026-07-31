# 序章 · 社媒运营工作台前端

P0–P3 前端契约主链实现，基于 Next.js 16、React 19、Tailwind CSS v4、
TanStack Query 与 OpenAPI 生成类型。

当前已完成页面、主要交互和真实工作区 API 接入；真实供应商、对象存储、
托管后端、生产 OIDC 和浏览器级端到端验收仍未完成。页面存在、演示工作区
可操作或本地构建通过，不代表整个产品已经通过生产验收。

## 本地运行

```bash
cp .env.example .env.local
npm install
npm run dev
```

默认入口：

```text
http://localhost:3000/w/demo/today
```

`demo` 工作区展示明确标记的契约演示数据。本地开发构建可以通过
`/login` 选择调试身份；生产构建会关闭该入口。连接本地后端后，将 URL 中的
`demo` 替换为真实工作区 UUID。非 `demo` 工作区通过版本化 REST API 读取和
修改后端数据。

## 质量检查

```bash
npm test
npm run typecheck
npm run lint
```

后端 OpenAPI 契约变化后：

```bash
npm run api:generate
```

生成目录 `src/api/generated/` 不手工编辑。

## 当前范围

### P0：工作台与数据内核

- 工作台 Shell、侧边导航、工作区标签、命令面板和响应式布局。
- 开发身份、工作区创建/切换与 Owner/Editor/Viewer 权限可见性。
- 对标账号列表/详情、新建、编辑、暂停、恢复和同步任务。
- 任务中心列表、动态轮询、重试与取消。
- 统一 API Core、工作区 Header、OpenAPI 类型和 Problem Details 错误映射。

### P1：灵感与分析

- 灵感库与详情、链接导入、指标快照、评分和评论。
- 逐字稿、L1/L2 分析及异步任务状态。
- 搜索与热榜、可复用模式、AI/ASR/Provider 用量页面。

### P2：内容生产

- 今日工作台、自有账号和账号定位。
- 选题、内容项目、脚本追加版本和版本冲突处理。
- 素材直传、审核排期、人工发布包和发布结果登记。
- 24h/7d/30d 复盘页面。

### P3：效率增强

- 跨实体关键词搜索、个人保存视图和共享视图读取。
- 选题批量操作、键盘跳转和运营实验。
- 项目负责人协作信息和移动端关键操作。

统一搜索当前是关键词匹配，不是向量语义搜索。官方平台自动发布、独立通知
投递、自动回传平台表现数据和多供应商容灾仍属于后续能力。

## 当前证据边界

- 自动化检查覆盖 TypeScript、ESLint、Vitest、生产构建和路由渲染。
- OpenAPI Client 从 `openapi.json` 生成，禁止手工修改生成文件。
- `demo` 数据只用于展示交互契约，不作为真实业务或供应商联调证据。
- 真实 AI/ASR、TikHub、对象存储、托管 PostgreSQL 和生产 OIDC 尚未完成验收。
- 尚未完成基于真实托管后端的浏览器端到端测试和 Staging 签字验收。

详细状态与未完成项见
[前端实现状态与证据边界](../docs/frontend/implementation-status.md)。
