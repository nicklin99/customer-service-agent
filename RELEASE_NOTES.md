# Release Notes - v1.0.0

> 发布日期：2026-06-25

## ✨ 新增

### 网页嵌入组件 (`embed.js`)
- 支持通过 `<script>` 标签将智能客服一键嵌入任意网站
- 浮动气泡按钮 + iframe 聊天窗口，点击展开/收起
- 窗口内最小化按钮可彻底关闭 iframe，气泡重新浮现
- 仅在嵌入模式下显示最小化按钮，独立访问时隐藏

### CRM API 模块化重构
- 线索查询、用户画像、CRM 同步拆分为独立云函数，便于维护
- 新增 `GET /api/crm/leads` — 按 thread_id 查询线索
- 新增 `GET /api/crm/profile` — 按 thread_id 查询用户画像
- 新增 `POST /api/crm/sync` — 同步线索到 CRM 系统

### 对话 API 模块
- `GET /api/thread/message?thread_id=...` — 获取指定会话的历史消息
- `POST /api/assistant` — 获取远程品牌配置，支持品牌定制

### 智能客服 Agent 升级
- 接入 DeepSeek 模型（通过 AI Gateway）
- 集成 LangGraph Checkpointer，消息持久化到 EdgeOne Store
- 新增工具：
  - `collect_lead` — 自动收集客户线索（姓名、电话、邮箱、需求等）
  - `analyze_user_profile` — 分析用户意图、画像
  - `save_to_crm` — 一键同步到 CRM
  - `wecom_query_customer` / `wecom_query_agent` — 企微客户查询
- 基于操作系统环境变量动态配置（品牌名、客服名、提示词等）

### 企微客服桥接
- 支持企业微信渠道活码，追踪渠道来源（`state` 参数）
- 企微消息 → AI 自动回复完整链路
- 企微渠道的线索收集、画像分析、CRM 同步

### 前端 UI 功能
- 线索表单（姓名、电话、邮箱、公司、职位、需求描述、预算、时间线）
- 表单保存后自动恢复，支持跨会话回显
- 用户画像面板（意图等级、客户类型、痛点、推荐服务、估值）
- 品牌配置可远程拉取，支持动态化
- 底部显示版本号（自动从 `package.json` 注入）

## 🔧 改进

- **SSE 流式响应优化** — 实时显示 AI 打字效果，支持中断生成
- **Markdown 渲染** — 消息支持 Markdown 格式（表格、代码块、链接等）
- **消息自动滚动** — 新消息自动滚动到底部
- **输入体验** — `Enter` 发送，`Shift+Enter` 换行
- **暂停/恢复线程** — 刷新页面后自动恢复历史对话
- **错误提示** — 网络异常时显示友好的错误提醒条
- **EdgeOne 适配** — 遵循 EdgeOne Makers Agent Runtime 规范

## 🐛 修复

- 修复请求体中硬编码产品线的问题
- 修复 Checkpointer 属性调用错误
- 修复 Store API 数据格式兼容性问题
- 移除不必要的 `await` 调用

---

## 技术详情

| 模块 | 变更 |
|------|------|
| `public/embed.js` | 新增嵌入脚本，iframe 通信 |
| `src/App.tsx` | 组件重构，嵌入检测，最小化逻辑 |
| `src/api.ts` | 新增 `getLead`、`getProfile` 等 API |
| `src/components/LeadForm.tsx` | 线索表单 UI + 远程保存 |
| `src/components/ProfilePanel.tsx` | 用户画像展示面板 |
| `src/config/brand.ts` | 品牌配置，远程拉取，Vite 注入版本号 |
| `src/context/BrandContext.tsx` | 品牌上下文 Provider |
| `cloud-functions/api/` | 模块化重构（crm/、thread/、assistant/） |
| `agents/chat/index.py` | Agent 重写，LangGraph + DeepSeek |
| `agents/_tools.py` | 工具函数模块 |
| `vite.config.ts` | `__APP_VERSION__` 构建注入 |

## 升级指南

无破坏性变更。直接部署即可。
