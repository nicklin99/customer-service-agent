# 企业微信 AI 智能客服桥接

将微信客服（KF）与 AI Agent 打通，客户在微信里扫码即可与 AI 对话，自动收集线索、追踪渠道来源。

---

## 云函数结构

```
cloud-functions/api/
├── _utils.ts               # 共享工具函数
├── profile.ts              # POST /api/profile        — 用户画像查询
├── leads.ts                # POST /api/leads          — 线索列表/详情
├── crm-sync.ts             # POST /api/crm-sync       — CRM 同步
├── settings.ts             # GET  /api/settings       — 品牌配置
└── wecom-kf-bridge.ts      # GET+POST /api/wecom-kf-bridge — 企微回调
```

## 整体架构

```
客户用微信扫码 → 渠道活码（带 state）
    ↓
添加企业微信 → 客户联系回调（add_external_contact）
    → 记录 ExternalUserID + state（渠道来源）
    → 发送欢迎语（send_welcome_msg）
    ↓
客户在微信发消息 → 微信客服回调（kf_msg_or_event）
    → sync_msg 增量拉取消息（cursor + msgid 去重）
    → AI Agent 生成回复
    → send_msg 写回微信
    ↓
客户在微信收到 AI 回复
```

## 前置准备

### 企微后台配置

1. 已有企业微信管理员账号，企业已开通**微信客服**功能
2. 已创建自建应用，开通**客户联系 API** 权限
3. 有公网 HTTPS 接口（回调地址）

### 凭证清单

登录企微管理后台 `work.weixin.qq.com` 获取：

| 凭证 | 在哪找 | 用途 |
|------|--------|------|
| CorpID | 我的企业 → 企业信息 → 企业ID | 所有 API 鉴权 |
| KF Secret | 应用管理 → 微信客服 → Secret | KF 消息收发 |
| App Secret | 应用管理 → 自建应用 → Secret | 渠道活码 + 欢迎语 |
| Token | 回调配置自己填 | 回调签名验证 |
| EncodingAESKey | 回调配置随机生成 | 消息加解密 |

### 企微权限配置

**客户联系权限（自建应用）：**
1. 左侧【客户与上下游】→【客户联系】→【API】
2. 把自建应用添加到「可调用客户联系接口的应用」
3. 勾选权限：添加客户、发送客户消息、获取外部联系人

**微信客服：**
1. 左侧【应用管理】→【微信客服】→ 开启 API
2. 记录 Secret

---

## 部署步骤

### 1. 配置环境变量

在 EdgeOne Makers 中设置以下环境变量：

```bash
# 企业微信凭证
WECOM_CORP_ID=your_corp_id
WECOM_KF_SECRET=your_kf_secret          # 微信客服应用的 secret
WECOM_APP_SECRET=your_app_secret        # 自建应用 secret（客户联系用）

# 回调配置（两个地方填一样的值）
WECOM_TOKEN=your_random_token
WECOM_ENCODING_AES_KEY=your_aes_key

# AI Gateway（复用现有的）
AI_GATEWAY_API_KEY=your_api_key
AI_GATEWAY_BASE_URL=https://your-gateway.com
AI_GATEWAY_MODEL=@makers/deepseek-v4-flash

# CRM（可选）
CRM_API_ENDPOINT=https://your-crm.com/api
CRM_API_KEY=your_crm_key
```

### 2. 配置两处回调 URL

| 位置 | 路径 |
|------|------|
| 客户联系 → API → 接收消息 | `https://your-domain.com/api/wecom-kf-bridge` |
| 微信客服 → 回调配置 | `https://your-domain.com/api/wecom-kf-bridge` |

两个地方的 URL、Token、EncodingAESKey **保持一致**。

### 3. 验证部署

**URL 验证：** 企微后台保存回调配置时，会自动 GET 请求你的地址验证签名。验证通过后保存成功。

**测试：** 在企微后台发一条客服消息 → 检查日志 → 确认 AI 回复已发送。

### 4. 生成渠道活码

```bash
curl -X POST https://your-domain.com/api/wecom-kf-bridge \
  -H "Content-Type: application/json" \
  -d '{
    "action": "create_qr_code",
    "users": ["user001","user002"],
    "state": "ad_baidu_2026"
  }'

# 返回
# {"errcode": 0, "qr_code": "https://weixin.qq.com/qrcode/..."}
```

参数说明：
| 参数 | 必填 | 说明 |
|------|------|------|
| `users` | 是 | 承接客户的客服员工 UserID 列表 |
| `state` | 是 | 渠道唯一标识，用于区分来源 |
| `skip_verify` | 否 | 是否自动通过好友（默认 true） |

---

## 回调事件支持

| Event | ChangeType | 处理逻辑 |
|-------|-----------|---------|
| `kf_msg_or_event` | — | sync_msg 拉取 → AI 回复 |
| `change_external_contact` | `add_external_contact` | 记录 state + 发欢迎语 |

---

## 数据存储

使用 EdgeOne Store（Key-Value）：

| Key 模式 | 存储内容 |
|---------|---------|
| `wecom_kf:{external_userid}` | 对话历史（最多 20 轮） |
| `wecom_kf_cursor:{open_kfid}` | sync_msg 游标（增量拉取） |
| `wecom_kf_processed:{open_kfid}` | 已处理 msgid 列表（去重，500 条） |
| `wecom_kf_channel:{external_userid}` | 客户的渠道 state |

---

## Todo

- [ ] 部署上线，跑通企微 → AI 完整链路
- [ ] 接入 CRM，同步线索和用户画像
- [ ] 管理面板：线索列表、对话记录、渠道统计
- [ ] 多模态消息支持（图片、语音）
