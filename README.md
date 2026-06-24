# 智能客服 Agent

基于 EdgeOne Makers Agent Runtime 的 AI 智能客服系统，支持网站聊天 + 企业微信双渠道，自动收集线索、分析用户画像、同步 CRM。

---

## 项目结构

```
customer-service-agent/
│
├── index.html                 # 前端入口
├── package.json               # 前端依赖
├── vite.config.ts             # Vite 构建配置
├── tailwind.config.js         # Tailwind CSS 配置
├── edgeone.json               # EdgeOne 部署配置
├── requirements.txt           # Python 依赖
│
├── src/                       # 前端（React + TypeScript）
│   ├── App.tsx                # 主应用组件
│   ├── main.tsx               # 入口
│   ├── api.ts                 # API 客户端
│   ├── components/
│   │   ├── ChatWidget.tsx     # 聊天组件
│   │   ├── ChatMessage.tsx    # 消息气泡
│   │   ├── LeadForm.tsx       # 线索表单
│   │   └── ProfilePanel.tsx   # 画像面板
│   └── config/
│       └── brand.ts           # 品牌配置
│
├── agents/                    # AI Agent（Python）
│   └── chat/
│       └── index.py           # 智能客服 Agent
│
└── cloud-functions/           # 云函数（Python）
    ├── crm-sync/
    │   └── index.py           # CRM 同步
    ├── leads/
    │   └── index.py           # 线索查询
    ├── profile/
    │   └── index.py           # 画像查询
    ├── settings/
    │   └── index.py           # 设置管理
    └── wecom-kf-bridge/
        ├── index.py           # 企业微信桥接
        └── README.md          # 企微部署文档
```

---

## 核心流程

### 网站渠道

```
用户在网页打开聊天组件
    → 与 AI Agent 对话
    → 识别线索 → 收集（姓名/电话/邮箱/公司/官网）
    → 自动分析用户画像
    → 同步 CRM
```

### 企业微信渠道

```
客户微信扫码渠道活码
    → 记录渠道来源（state）
    → 发送欢迎语
    → 客户发消息 → AI 自动回复
    → 收集线索 → 分析画像 → 同步 CRM
```

详细说明见：[cloud-functions/wecom-kf-bridge/README.md](./cloud-functions/wecom-kf-bridge/README.md)

---

## 技术栈

| 层 | 技术 |
|----|------|
| **前端** | React + TypeScript + Tailwind CSS + Vite |
| **AI Agent** | Python + LangGraph + DeepAgents |
| **LLM** | DeepSeek（通过 AI Gateway） |
| **持久化** | EdgeOne Store（LangGraph Checkpointer） |
| **企业微信** | 微信客服 API + 客户联系 API |
| **部署** | EdgeOne Makers Agent Runtime + Cloud Functions |

---

## 环境变量

参考 `.env.example`，需要配置：

| 变量 | 说明 |
|------|------|
| `AI_GATEWAY_API_KEY` | AI Gateway 密钥 |
| `AI_GATEWAY_BASE_URL` | AI Gateway 地址 |
| `AI_GATEWAY_MODEL` | 模型名称 |
| `CRM_API_ENDPOINT` | CRM 同步地址 |
| `CRM_API_KEY` | CRM 密钥 |
| `BRAND_NAME` | 品牌名称 |
| `AGENT_NAME` | Agent 名称 |
| `WECOM_CORP_ID` | 企业 ID |
| `WECOM_KF_SECRET` | 微信客服 Secret |
| `WECOM_APP_SECRET` | 自建应用 Secret |
| `WECOM_TOKEN` | 回调 Token |
| `WECOM_ENCODING_AES_KEY` | 回调加密密钥 |

---

## 本地开发

```bash
# 前端
npm install
npm run dev

# Agent（需要 EdgeOne 环境）
# 通过 EdgeOne Studio 调试
```

---

## 部署

```bash
# 构建前端
npm run build

# 通过 EdgeOne CLI 部署
edgeone deploy
```

---

## Todo

- [ ] 部署上线，配置企微回调，跑通完整链路
- [ ] 接入 CRM，同步线索和画像
- [ ] 管理面板：线索列表、对话记录、渠道统计
- [ ] 多模态消息支持（图片、语音）
