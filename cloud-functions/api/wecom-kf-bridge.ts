/**
 * GET/POST /api/wecom-kf-bridge — 企业微信回调 + 消息处理
 *
 * GET  — 回调 URL 验证（msg_signature / timestamp / nonce / echostr）
 * POST — JSON 管理操作（create_qr_code）或 XML 回调事件
 */
import { json } from './_utils';

const ENV_WECOM_TOKEN = 'WECOM_TOKEN';
const ENV_WECOM_ENCODING_AES_KEY = 'WECOM_ENCODING_AES_KEY';
const ENV_WECOM_CORP_ID = 'WECOM_CORP_ID';
const ENV_WECOM_KF_SECRET = 'WECOM_KF_SECRET';
const ENV_WECOM_APP_SECRET = 'WECOM_APP_SECRET';

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const method = request.method;

  // ── GET: URL 验证 ────────────────────────────────────
  if (method === 'GET') {
    const msgSignature = url.searchParams.get('msg_signature') || '';
    const timestamp = url.searchParams.get('timestamp') || '';
    const nonce = url.searchParams.get('nonce') || '';
    const echostr = url.searchParams.get('echostr') || '';

    const token = env[ENV_WECOM_TOKEN] || '';
    const aesKey = env[ENV_WECOM_ENCODING_AES_KEY] || '';

    if (!token || !aesKey) {
      return text('回调配置未完成: 缺少 WECOM_TOKEN 或 WECOM_ENCODING_AES_KEY', 500);
    }

    // 验证签名
    const sig = await sha1([token, timestamp, nonce, echostr].sort().join(''));
    if (sig !== msgSignature) return text('verify fail', 403);

    try {
      const decrypted = await decryptAes(aesKey, echostr);
      return text(decrypted);
    } catch (e) {
      console.error('解密 echostr 失败:', e);
      return text('decrypt fail', 500);
    }
  }

  // ── POST ──────────────────────────────────────────────
  if (method === 'POST') {
    const contentType = request.headers.get('content-type') || '';

    // JSON 管理操作
    if (contentType.includes('json')) {
      const body = await request.json();
      if (body.action === 'create_qr_code') {
        const users = body.users, state = body.state;
        if (!users?.length || !state) return json({ error: '缺少 users 或 state' }, 400);
        const result = await createContactWay(env, users, state);
        return json(result);
      }
      return json({ error: 'unknown action' }, 400);
    }

    // XML 回调事件
    const token = env[ENV_WECOM_TOKEN] || '';
    const aesKey = env[ENV_WECOM_ENCODING_AES_KEY] || '';
    const corpId = env[ENV_WECOM_CORP_ID] || '';
    if (!token || !aesKey) return text('回调配置未完成', 500);

    const rawXml = await request.text();
    const xml = parseXml(rawXml);

    const encrypted = xml.Encrypt || '';
    const msgSignature = xml.MsgSignature || '';
    const timestamp = xml.TimeStamp || '';
    const nonce = xml.Nonce || '';

    // 验证签名
    const sig = await sha1([token, timestamp, nonce, encrypted].sort().join(''));
    if (sig !== msgSignature) return text('signature mismatch', 403);

    // 解密
    let decryptedXml;
    try {
      decryptedXml = await decryptAes(aesKey, encrypted);
    } catch (e) {
      console.error('解密失败:', e);
      return text('decrypt fail', 500);
    }

    const eventXml = parseXml(decryptedXml);
    const eventType = eventXml.Event || '';

    // ── 客户联系事件 ──────────────────────────────
    if (eventType === 'change_external_contact') {
      if (eventXml.ChangeType === 'add_external_contact') {
        const externalUserid = eventXml.ExternalUserID || '';
        const state = eventXml.State || '';
        const welcomeCode = eventXml.WelcomeCode || '';
        console.log(`新客户添加: ${externalUserid}, state=${state}`);

        if (externalUserid && state) {
          try {
            await context.agent.store.set(`wecom_kf_channel:${externalUserid}`, state);
          } catch (e) {
            console.warn('保存渠道 state 失败:', e);
          }
        }

        if (welcomeCode) {
          await sendWelcomeMsg(env, welcomeCode, '您好！我是智能客服助手，很高兴为您服务。请问有什么可以帮您的吗？');
        }
      }
      return text('success');
    }

    // ── 微信客服 KF 事件 ──────────────────────────
    if (eventType !== 'kf_msg_or_event') return text('success');

    const eventToken = eventXml.Token || '';
    const openKfid = eventXml.OpenKfId || '';
    if (!eventToken || !openKfid) return text('success');

    const msgList = await syncMsg(env, context.agent.store, eventToken, openKfid);
    console.log(`拉取到 ${msgList.length} 条消息/事件`);

    const processedKey = `wecom_kf_processed:${openKfid}`;
    let processedIds = new Set();
    try {
      const stored = await context.agent.store.get(processedKey);
      if (stored) processedIds = new Set(JSON.parse(stored));
    } catch {}

    const userTexts = {};
    const userEntered = new Set();
    const batchMsgids = [];

    for (const msg of msgList) {
      const uid = msg.external_userid, msgid = msg.msgid;
      if (!uid || !msgid || processedIds.has(msgid)) continue;
      batchMsgids.push(msgid);

      if (msg.origin === 4 && msg.msgtype === 'event' && msg.event?.event_type === 'enter_session') {
        userEntered.add(uid);
      }
      if (msg.origin === 3 && msg.msgtype === 'text' && msg.text?.content) {
        (userTexts[uid] || (userTexts[uid] = [])).push(msg.text.content);
      }
    }

    let allSuccess = true;
    for (const [uid, texts] of Object.entries(userTexts)) {
      const isNew = userEntered.has(uid);
      if (isNew) {
        const ok = await sendKfMsg(env, uid, openKfid, '您好！我是智能客服助手，很高兴为您服务。请问有什么可以帮您的吗？');
        if (ok) await saveToHistory(context.agent.store, uid, 'ai', '您好！我是智能客服助手，很高兴为您服务。请问有什么可以帮您的吗？');
        else { allSuccess = false; continue; }
      }

      for (const t of texts.slice(0, -1)) {
        await saveToHistory(context.agent.store, uid, 'customer', t);
      }
      const reply = await callAiAgent(env, context.agent.store, uid, texts[texts.length - 1]);
      const ok = await sendKfMsg(env, uid, openKfid, reply);
      if (!ok) { console.error(`send_msg 失败, 用户 ${uid} 未收到回复`); allSuccess = false; }
    }

    if (batchMsgids.length && allSuccess) {
      batchMsgids.forEach((id) => processedIds.add(id));
      const trimmed = [...processedIds].slice(-500);
      try {
        await context.agent.store.set(processedKey, JSON.stringify(trimmed));
      } catch (e) {
        console.warn('保存 processed_ids 失败:', e);
      }
    }

    return text('success');
  }

  return text('method not allowed', 405);
}

// ── Helpers ───────────────────────────────────────────────

function text(data, status = 200) {
  return new Response(data, {
    status,
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
}

async function sha1(str) {
  const buf = new TextEncoder().encode(str);
  const hash = await crypto.subtle.digest('SHA-1', buf);
  return Array.from(new Uint8Array(hash)).map((b) => b.toString(16).padStart(2, '0')).join('');
}

function base64Decode(str) {
  // Add padding if needed
  const padded = str.length % 4 ? str + '='.repeat(4 - (str.length % 4)) : str;
  const binary = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

async function decryptAes(encodingAesKey, cipherBase64) {
  const aesKey = base64Decode(encodingAesKey);
  const ciphertext = base64Decode(cipherBase64);

  const key = await crypto.subtle.importKey(
    'raw',
    aesKey,
    { name: 'AES-CBC' },
    false,
    ['decrypt'],
  );

  const iv = aesKey.slice(0, 16);
  const plain = await crypto.subtle.decrypt({ name: 'AES-CBC', iv }, key, ciphertext);
  const bytes = new Uint8Array(plain);

  // 去除 PKCS7 填充
  const padLen = bytes[bytes.length - 1];
  const unpadded = bytes.slice(0, bytes.length - padLen);

  // 提取消息: [16随机][4字节网络序长度][消息][corpid]
  const msgLenView = new DataView(unpadded.buffer, unpadded.byteOffset + 16, 4);
  const msgLen = msgLenView.getUint32(0, false); // big-endian
  const msgBytes = unpadded.slice(20, 20 + msgLen);
  return new TextDecoder().decode(msgBytes);
}

function parseXml(xml) {
  const result = {};
  const tagRegex = /<(\w+)>([^<]*)<\/\1>/g;
  let match;
  while ((match = tagRegex.exec(xml)) !== null) {
    result[match[1]] = match[2];
  }
  // Also handle CDATA
  const cdataRegex = /<(\w+)><!\[CDATA\[([^]*?)\]\]><\/\1>/g;
  while ((match = cdataRegex.exec(xml)) !== null) {
    result[match[1]] = match[2];
  }
  return result;
}

// ── WeCom API ─────────────────────────────────────────────

let tokenCache = { token: '', expiresAt: 0 };
let appTokenCache = { token: '', expiresAt: 0 };

async function getAccessToken(env) {
  const now = Date.now() / 1000;
  if (tokenCache.token && tokenCache.expiresAt > now + 60) return tokenCache.token;

  const corpId = env[ENV_WECOM_CORP_ID], secret = env[ENV_WECOM_KF_SECRET];
  if (!corpId || !secret) throw new Error('缺少 WECOM_CORP_ID 或 WECOM_KF_SECRET');

  const resp = await fetch(`https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=${corpId}&corpsecret=${secret}`);
  const data = await resp.json();
  if (data.errcode) throw new Error(`获取 access_token 失败: ${JSON.stringify(data)}`);
  tokenCache = { token: data.access_token, expiresAt: now + data.expires_in };
  return data.access_token;
}

async function getAppAccessToken(env) {
  const now = Date.now() / 1000;
  if (appTokenCache.token && appTokenCache.expiresAt > now + 60) return appTokenCache.token;

  const corpId = env[ENV_WECOM_CORP_ID];
  const secret = env[ENV_WECOM_APP_SECRET] || env[ENV_WECOM_KF_SECRET];
  if (!corpId || !secret) throw new Error('缺少 WECOM_CORP_ID 和 WECOM_APP_SECRET');

  const resp = await fetch(`https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=${corpId}&corpsecret=${secret}`);
  const data = await resp.json();
  if (data.errcode) throw new Error(`获取 app access_token 失败: ${JSON.stringify(data)}`);
  appTokenCache = { token: data.access_token, expiresAt: now + data.expires_in };
  return data.access_token;
}

async function syncMsg(env, store, token, openKfid) {
  const accessToken = await getAccessToken(env);
  const allMsgs = [];
  const cursorKey = `wecom_kf_cursor:${openKfid}`;
  let cursor = '';
  try { cursor = (await store.get(cursorKey)) || ''; } catch {}

  while (true) {
    const body = { token, open_kfid: openKfid, limit: 100 };
    if (cursor) body.cursor = cursor;

    const resp = await fetch(
      `https://qyapi.weixin.qq.com/cgi-bin/kf/sync_msg?access_token=${accessToken}`,
      { method: 'POST', body: JSON.stringify(body), headers: { 'Content-Type': 'application/json' } },
    );
    const data = await resp.json();
    if (data.errcode) { console.error('sync_msg 失败:', data); break; }

    const msgs = data.msg_list || [];
    allMsgs.push(...msgs);

    if (!data.has_more) {
      if (msgs.length && data.next_cursor) {
        try { await store.set(cursorKey, data.next_cursor); } catch (e) { console.warn('保存 cursor 失败:', e); }
      }
      break;
    }
    cursor = data.next_cursor;
  }
  return allMsgs;
}

async function sendKfMsg(env, externalUserid, openKfid, content) {
  const accessToken = await getAccessToken(env);
  const resp = await fetch(
    `https://qyapi.weixin.qq.com/cgi-bin/kf/send_msg?access_token=${accessToken}`,
    {
      method: 'POST',
      body: JSON.stringify({ touser: externalUserid, open_kfid: openKfid, msgtype: 'text', text: { content } }),
      headers: { 'Content-Type': 'application/json' },
    },
  );
  const data = await resp.json();
  if (data.errcode) { console.error('send_msg 失败:', data); return false; }
  return true;
}

async function createContactWay(env, users, state) {
  const accessToken = await getAppAccessToken(env);
  const resp = await fetch(
    `https://qyapi.weixin.qq.com/cgi-bin/externalcontact/add_contact_way?access_token=${accessToken}`,
    {
      method: 'POST',
      body: JSON.stringify({ type: 1, scene: 2, state, user: users, skip_verify: true }),
      headers: { 'Content-Type': 'application/json' },
    },
  );
  return resp.json();
}

async function sendWelcomeMsg(env, welcomeCode, content) {
  const accessToken = await getAppAccessToken(env);
  const resp = await fetch(
    `https://qyapi.weixin.qq.com/cgi-bin/externalcontact/send_welcome_msg?access_token=${accessToken}`,
    {
      method: 'POST',
      body: JSON.stringify({ welcome_code: welcomeCode, text: { content } }),
      headers: { 'Content-Type': 'application/json' },
    },
  );
  const data = await resp.json();
  if (data.errcode) { console.error('send_welcome_msg 失败:', data); return false; }
  return true;
}

async function saveToHistory(store, externalUserid, role, content) {
  const storeKey = `wecom_kf:${externalUserid}`;
  let history = [];
  try {
    const stored = await store.get(storeKey);
    if (stored) history = JSON.parse(stored);
  } catch {}
  history.push({ role, content, time: Math.floor(Date.now() / 1000) });
  try {
    await store.set(storeKey, JSON.stringify(history.slice(-40)));
  } catch (e) {
    console.warn('保存对话历史失败:', e);
  }
}

async function loadHistory(store, externalUserid) {
  const storeKey = `wecom_kf:${externalUserid}`;
  try {
    const stored = await store.get(storeKey);
    return stored ? JSON.parse(stored) : [];
  } catch { return []; }
}

async function callAiAgent(env, store, externalUserid, userMsg) {
  const history = await loadHistory(store, externalUserid);
  history.push({ role: 'customer', content: userMsg, time: Math.floor(Date.now() / 1000) });

  const apiKey = (env.AI_GATEWAY_API_KEY || '').trim();
  const baseUrl = (env.AI_GATEWAY_BASE_URL || '').trim();
  const modelName = env.AI_GATEWAY_MODEL || '@makers/deepseek-v4-flash';

  if (!apiKey || !baseUrl) {
    const reply = '系统暂时无法回复，请稍后再试。';
    await saveToHistory(store, externalUserid, 'ai', reply);
    return reply;
  }

  const messages = [
    { role: 'system', content: AGENT_SYSTEM_PROMPT },
    ...history.map((h) => ({ role: h.role === 'customer' ? 'user' : 'assistant', content: h.content })),
  ];

  try {
    const resp = await fetch(`${baseUrl}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({ model: modelName, messages, temperature: 0.7, max_tokens: 1024 }),
    });
    const data = await resp.json();
    const reply = data.choices?.[0]?.message?.content || '';
    await saveToHistory(store, externalUserid, 'ai', reply);
    return reply;
  } catch (e) {
    console.error('AI 调用失败:', e);
    const reply = '抱歉，我暂时遇到了一些问题，请稍后再试。';
    await saveToHistory(store, externalUserid, 'ai', reply);
    return reply;
  }
}

const AGENT_SYSTEM_PROMPT = `你是一位专业、热情、自然的智能客服代表。你的核心职责是帮助客户解答问题，同时敏锐地识别潜在客户线索，并自然地收集关键信息。

## 你的身份
- 风格：专业但不死板，热情但不油腻，像一位经验丰富的客户顾问
- 语言：默认使用中文，如果客户使用英文则用英文回复

## 核心行为准则

### 1. 自然对话优先
- 先理解客户问题，给予有帮助的回应
- 不要一上来就索要联系方式，那会吓跑客户

### 2. 线索识别与主动收集
当客户表达需求时，应立即识别为新线索，主动自然地收集线索信息：
- 客户询问价格、产品功能、方案对比
- 客户表示有采购意向或项目需求
- 客户询问合作流程、实施周期
- 客户透露了公司/团队规模
- 对话超过 3 轮且客户表达了明确需求

线索字段包括：姓名、电话、邮箱、公司名称、职位、需求描述、官方网址（选填）。预算和时间线不再收集。

### 3. 用户画像
当收集到姓名、电话、邮箱、需求描述这些基本信息后，你应该给出一个简要的用户画像分析（客户类型、核心需求、意向程度）。

### 4. CRM 同步
收集到足够线索后，应通过 CRM API 提交客户线索信息。

## 不要做的事情
- 不要编造你没有的产品信息
- 不要承诺具体价格（可以说稍后顾问会给您详细报价）
- 不要在没有线索信号时强行收集信息
- 不要一次性问太多问题`;
