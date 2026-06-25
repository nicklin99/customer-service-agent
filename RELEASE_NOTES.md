# Release Notes — v1.0.0

> 发布日期：2026-06-25

## ✨ 新功能

### 🧠 AI Agent 引擎升级
- **迁移至 OpenAI Agents SDK** — 使用官方 SDK 替代 LangGraph，模型调用更稳定、工具编排更灵活
- **工具模块解耦** — 将 `collect_lead`、`analyze_user_profile`、`save_to_crm` 等工具独立为 `_tools.py` 模块，方便扩展
- **企微工具集成** — 新增 `wecom_query_customer` / `wecom_query_agent` 工具，支持企业微信客户查询
- **系统提示词强化** — 引导 AI 主动收集客户线索、自动补齐用户画像

### 🌐 网页嵌入组件
- 一行 `<script>` 标签即可将智能客服嵌入任意网站
- 浮动气泡按钮 + iframe 聊天窗口，点击展开/收起
- 窗口内点击最小化 → 彻底关闭 iframe，气泡重新浮现
- 独立访问时自动隐藏最小化按钮

### 📋 线索管理
- 智能客服对话中自动识别并收集线索（姓名、电话、邮箱、公司、需求等）
- 线索表单支持保存，跨会话自动恢复回显
- 初始化时通过 API 查询已有线索数据

### 📊 用户画像
- AI 自动分析用户意图等级、客户类型、痛点、推荐服务、估值
- 画像面板直观展示分析结果
- 新消息后自动刷新画像

### 🔗 企微客服桥接
- 支持企业微信渠道活码，追踪渠道来源（`state` 参数）
- 企微消息自动转发 AI 回复，完整对话链路
- 企微渠道的线索收集、画像分析、CRM 同步

### 🗄 CRM API 模块化
- 云函数拆分为独立模块，更清晰可维护：
  - `api/crm/leads` — 线索查询
  - `api/crm/profile` — 用户画像
  - `api/crm/sync` — CRM 同步
  - `api/thread/message` — 历史消息
  - `api/assistant` — 远程品牌配置
- 线索和画像数据通过 API 查询，不再依赖消息解析

## 🔧 改进

- **嵌入脚本优化** — 新增 `demo.html` 演示页面，快速预览集成效果
- **SSE 流式渲染** — AI 回复实时显示打字效果，支持 Markdown（表格、代码块、链接）
- **消息自动滚动** — 新消息自动滑到底部
- **输入体验** — `Enter` 发送，`Shift+Enter` 换行
- **线程持久化** — 刷新页面自动恢复历史对话，无需从头开始
- **品牌动态化** — 品牌配置可从远程 API 拉取
- **版本号注入** — 构建时自动从 `package.json` 读取版本，显示在底部
- **EdgeOne 适配** — 完全兼容 EdgeOne Makers Agent Runtime 规范

## 🐛 修复

- 修复请求体中硬编码产品线的问题
- 修复 Checkpointer 属性调用错误
- 移除硬编码的 `await` 调用
- 适配 `context.request.body` → `context.body` 的接口变更
- 修复 Store API 数据格式兼容性问题

---

## 变更清单

| 文件 | 说明 |
|------|------|
| `agents/chat/index.py` | Agent 引擎迁移至 OpenAI Agents SDK |
| `agents/_tools.py` | 工具模块独立 |
| `agents/stop/index.py` | 调整停止逻辑适配新 SDK |
| `agents/requirements.txt` | 更新依赖 |
| `public/embed.js` | 新增嵌入脚本，iframe 通信 |
| `src/App.tsx` | 组件重构，嵌入检测，最小化、恢复提示 |
| `src/api.ts` | 新增 `getLead`、`getProfile` 等接口 |
| `src/components/ChatMessage.tsx` | Markdown 渲染优化 |
| `src/components/ChatWidget.tsx` | 交互调优 |
| `src/components/LeadForm.tsx` | 线索表单 UI + 远程保存 |
| `src/components/ProfilePanel.tsx` | 用户画像展示面板 |
| `src/config/brand.ts` | 版本号注入、远程配置 |
| `vite.config.ts` | `__APP_VERSION__` 构建注入 |
| `cloud-functions/api/` | 模块化重构 |
| `demo.html` | 新增演示页面 |
| `edgeone.json` | 部署配置更新 |
| `package.json` | 添加 `react-markdown` 依赖 |

## 📦 升级指南

无破坏性变更。直接构建部署即可：

```bash
npm run build
# 部署到 EdgeOne
```
