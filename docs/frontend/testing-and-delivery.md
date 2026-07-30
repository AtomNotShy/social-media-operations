# 前端测试、部署与验收

## 1. 测试层级

```text
Static Checks
→ Unit Tests
→ Component Tests
→ API Contract Tests
→ E2E Tests
→ Visual/Accessibility QA
```

测试重点是业务状态和失败恢复，不追求低价值的纯快照覆盖率。

## 2. 静态检查

每次提交执行：

- TypeScript strict typecheck。
- ESLint。
- Prettier/格式检查。
- Tailwind class 和 CSS 检查。
- 未使用导入。
- 生成 API Client 是否最新。
- 环境变量 Schema。
- 禁止前端代码出现 TikHub Key 名称或 Provider Secret。

## 3. 单元测试

重点：

- Query Key 规范化。
- URL 筛选解析。
- 指标 `null/0` 格式化。
- 数字缩写。
- 平台与 Grade 映射。
- Job 终态判断。
- 权限判断。
- Workbench Tab 去重和关闭规则。
- Problem Details 到 AppError。
- Idempotency Key 生命周期。

## 4. 组件测试

使用 Testing Library，以用户可见行为断言：

- 对标账号表格。
- 导入链接 Drawer。
- Filter Bar。
- Content Card。
- Job Status。
- Budget Warning。
- Script Version Conflict。
- Upload Progress。
- Error/Empty/Partial Data。

每个关键组件至少覆盖成功、Loading、Empty、Error、Viewer 权限、长中文文字和缺失指标。

## 5. API Mock

MSW Handler 以 OpenAPI DTO 为基础，集中放在：

```text
src/test/handlers/
```

需要固定场景：

- 200 成功。
- 202 创建 Job。
- 401。
- 403。
- 404。
- 409 Version Conflict。
- Provider 429 映射。
- Provider Budget Exceeded。
- 后端 5xx。
- 网络断开。
- 慢响应。
- Partial Data。

禁止每个组件自行构造不一致的随意 JSON。

## 6. 契约测试

CI 获取后端 `openapi.json`：

1. 检查破坏性变化。
2. 生成 Client。
3. Typecheck 全部 Feature。
4. 验证稳定错误码。
5. 验证状态机 Enum。

后端接口尚未实现时，前端 Feature 使用契约 Mock，但页面必须清楚标记开发状态，不能连接虚假生产数据。

## 7. E2E

### P0 必测流程

1. 使用开发身份进入应用。
2. 无工作区时创建工作区。
3. 切换工作区。
4. 查看对标账号空状态。
5. 新建对标账号。
6. 编辑优先级。
7. 暂停和恢复。
8. 发起同步，收到 Job。
9. Job Center 展示 Pending/Running/Failed/Succeeded。
10. 失败任务 Retry，排队任务 Cancel。
11. Viewer 无法执行付费/写操作。

### P1 必测流程

1. 导入单条灵感。
2. 等待详情任务。
3. 查看指标、评分和分析。
4. 请求转写/L2。
5. 转成选题。
6. TikHub 不可用时仍查看历史内容。
7. 达到预算后禁止新任务但不阻断站内浏览。

### P2 必测流程

1. 选题创建内容项目。
2. 生成和保存脚本版本。
3. 处理版本冲突。
4. 上传素材。
5. 审核并排期。
6. 生成发布包。
7. 标记已发布。
8. 完成 24 小时复盘。

## 8. 可访问性测试

自动化检查：

- 缺失 Label。
- 对比度。
- 无障碍名称。
- ARIA 属性。
- Dialog 焦点。

人工检查：

- 只用键盘完成 P0 流程。
- 200% 缩放。
- 屏幕阅读器读取关键状态。
- 减少动态效果。
- 错误提示不依赖颜色。
- 表格在窄宽下仍可理解。

## 9. 视觉 QA

固定视口：

- 1440 × 900：主要桌面。
- 1280 × 800：紧凑桌面。
- 1024 × 768：平板横向。
- 390 × 844：移动查看。

重点页面：

- App Shell。
- 对标账号。
- 灵感库。
- 灵感详情。
- 脚本编辑。
- 排期。
- Job Center。

视觉回归不应把动态时间、随机 ID 和动画帧纳入不稳定截图。

## 10. 性能目标

这是产品目标，不是框架默认保证：

- 初始工作台快速显示 Shell 和 Skeleton。
- LCP 目标小于 2.5 秒。
- INP 目标小于 200 ms。
- CLS 目标小于 0.1。
- 大列表滚动不持续掉帧。
- 打开 Command Palette 小于 100 ms。
- 切换已缓存标签有即时反馈。

措施：

- 路由级代码分割。
- 不把所有页面放进一个 Client Bundle。
- 图片使用合适尺寸和懒加载。
- 图表按页面动态加载。
- 列表服务端分页。
- 高成本编辑器只在脚本页加载。
- Query Cache 避免重复请求。
- 不在 Render 中处理大型原始 JSON。

## 11. 环境变量

只允许公开配置进入浏览器：

```dotenv
NEXT_PUBLIC_API_BASE_URL=
NEXT_PUBLIC_OIDC_ISSUER=
NEXT_PUBLIC_OIDC_CLIENT_ID=
NEXT_PUBLIC_OIDC_AUDIENCE=
NEXT_PUBLIC_APP_ENV=
```

禁止出现 TikHub API Key、LLM/ASR Key、数据库连接、对象存储 Secret 或 OIDC Client Secret。

构建时验证环境变量，缺失时失败。

## 12. 部署

前端独立部署：

```text
Browser
→ Frontend Origin
→ Backend API Origin
```

后端 CORS 只允许明确前端 Origin。

部署要求：

- Preview 环境连接 Staging 后端。
- Production 前端只连接 Production 后端。
- Source Map 上传错误监控后不公开暴露。
- 静态 Asset 使用长期缓存。
- 发布后执行 API、登录和工作区 Smoke Test。

## 13. CI/CD

Pull Request：

1. 安装锁定依赖。
2. 生成 API Client。
3. Format Check。
4. Lint。
5. Typecheck。
6. Unit/Component Tests。
7. Build。
8. 关键 E2E。
9. 可访问性检查。

Production：

1. 验证 OpenAPI 兼容。
2. 构建不可变 Artifact。
3. 部署 Preview/Staging。
4. 运行 E2E Smoke。
5. 部署 Production。
6. 检查错误率和 API 版本。

## 14. Feature Flag

后端尚未实现或高风险功能使用明确 Feature Flag：

- `inspiration_library`
- `ai_l2_analysis`
- `transcription`
- `content_workflow`
- `publishing`
- `semantic_search`

规则：

- Flag 决定入口是否可用。
- 不在浏览器中放 Secret。
- 关闭功能时路由返回明确的不可用页面。
- 不用 CSS 隐藏代替权限和 Feature Flag。

## 15. P0 验收

### Shell

- 登录后进入最近工作区。
- 工作区不存在时进入创建流程。
- 侧边栏、顶部标签、Command Palette 基础可用。
- 刷新后恢复标签和当前 URL。
- 切换工作区不泄漏旧工作区缓存。

### API

- 所有请求通过生成 Client。
- 自动附加 Token 和 Workspace Header。
- Problem Details 统一映射。
- Request ID 可查看。
- 401/403/409 有独立处理。

### 对标账号

- 列表、新建、编辑、暂停、恢复和同步可用。
- Cursor、筛选和排序进入 URL。
- 同步显示 Job，不显示虚假成功。
- Viewer 只读。

### Job Center

- Pending、Running、Retry Wait、Succeeded、Failed、Dead、Cancelled 均有展示。
- 终态停止轮询。
- Retry/Cancel 调用后端。
- Job 成功后刷新受影响实体。

### 质量

- 1440、1280、1024 三种宽度通过视觉 QA。
- 键盘完成关键流程。
- Typecheck、测试和 Production Build 通过。
- 前端 Artifact 不包含任何 Provider Secret。

## 16. P1 验收

- 灵感列表筛选可复制 URL。
- 指标 `null` 与 `0` 正确区分。
- 导入重复内容显示已有记录。
- 高成本操作显示调用量和费用。
- 详情、评论、转写和分析状态明确。
- TikHub 故障时显示旧数据和更新时间。
- L1/L2 引用来源证据。

## 17. P2 验收

- 从灵感到发布记录全流程可完成。
- 脚本保存不覆盖历史。
- 版本冲突不丢稿。
- 素材直传对象存储。
- 未审核内容不能发布。
- 人工发布后可记录链接和时间。
- 曝光、互动和转化在复盘中分开展示。

