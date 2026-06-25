/**
 * /api/assistant — 助手配置 CRUD（多助理，Blob 存储）
 *
 * GET     ?assistant_id=    — 读取指定助理配置
 * POST                     — 更新指定助理配置（body.assistant_id + body.data）
 * DELETE                   — 重置指定助理配置（body.assistant_id）
 *
 * assistant_id 不传时默认 default，数据存于 Blob key `settings:{assistant_id}`。
 */
import { json } from '../_utils';
import { getStore } from '@edgeone/pages-blob';

const store = getStore('assistant');

export default async function onRequest(context) {
  const { method, url } = context.request;
  const { env } = context;

  // 从 query（GET）或 body（POST/DELETE）获取 assistant_id
  let assistantId = 'default';
  if (method === 'GET') {
    assistantId = new URL(url).searchParams.get('assistant_id') || 'default';
  } else {
    try {
      const body = await context.request.json();
      assistantId = body.assistant_id || 'default';
    } catch {}
  }

  const blobKey = `settings:${assistantId}`;

  const defaults = {
    brandName: env.BRAND_NAME || 'trendee',
    brandTitle: env.BRAND_TITLE || 'trendee 智能客服',
    agentName: env.AGENT_NAME || 'trendee',
    logoText: env.LOGO_TEXT || 'T',
    welcomeMessage: env.WELCOME_MESSAGE || '您好！我是 trendee，trendee 的智能顾问 \n\n请问有什么可以帮您的？',
    footerText: env.FOOTER_TEXT || 'trendee · 智能客服系统',
    defaultSource: env.DEFAULT_SOURCE || 'trendee-智能客服',
    placeholder: env.PLACEHOLDER || '输入您的问题, trendee 随时为您解答...',
    streamingText: env.STREAMING_TEXT || 'trendee 正在输入...',
  };

  if (method === 'GET') {
    let overrides: any = {};
    try {
      const raw = await store.get(blobKey, { type: 'json' });
      if (raw) overrides = raw;
    } catch {}
    console.log("assistant:", overrides)
    return json({ assistant_id: assistantId, ...defaults, ...overrides });
  }

  if (method === 'POST') {
    try {
      const body = await context.request.json();
      const data = body.data || {};
      if (Object.keys(data).length === 0) {
        return json({ error: 'data 不能为空' }, 400);
      }

      let existing: any = {};
      try {
        const raw = await store.get(blobKey, { type: 'json' });
        if (raw) existing = raw;
      } catch {}

      const merged = { ...existing, ...data, assistant_id: assistantId, updated_at: new Date().toISOString() };
      await store.setJSON(blobKey, merged);

      return json({ assistant_id: assistantId, ...defaults, ...merged, updated: true });
    } catch (err) {
      return json({ error: err.message }, 500);
    }
  }

  if (method === 'DELETE') {
    try {
      await store.delete(blobKey);
      return json({ assistant_id: assistantId, ...defaults, reset: true });
    } catch (err) {
      return json({ error: err.message }, 500);
    }
  }

  return json({ error: 'Method not allowed' }, 405);
}
