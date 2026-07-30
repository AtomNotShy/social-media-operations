# 序章 · 社媒运营工作台前端

P0 前端实现，基于 Next.js 16、React 19、Tailwind CSS v4、TanStack Query 与 OpenAPI 生成类型。

## 本地运行

```bash
cp .env.example .env.local
npm install
npm run dev
```

默认入口：

```text
http://localhost:3000/w/demo/tracked-profiles
```

`demo` 工作区展示明确标记的契约演示数据。连接本地后端后，将 URL 中的 `demo` 替换为真实工作区 UUID。

## 质量检查

```bash
npm run typecheck
npm run lint
npm run test:unit
npm run build
```

后端 OpenAPI 契约变化后：

```bash
npm run api:generate
```

生成目录 `src/api/generated/` 不手工编辑。

## 当前范围

- 工作台 Shell、侧边导航、工作区标签与命令面板。
- 开发身份登录、工作区创建/切换与 Owner/Editor/Viewer 权限。
- 对标账号列表、详情、编辑、URL 筛选、新建、暂停/恢复和同步任务。
- 任务中心列表、动态轮询、重试与取消。
- 统一 API Core、连接状态、工作区 Header 和 Problem Details 错误映射。
- 响应式桌面/平板/移动查看布局。

今日、灵感、选题、内容项目、排期、复盘等路由已预留，按 P1/P2 后端契约逐步启用。
