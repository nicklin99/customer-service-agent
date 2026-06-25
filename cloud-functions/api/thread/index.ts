/**
 * /api/thread — 对话 CRUD（HTTP 方法路由）
 *
 * GET              — 列出所有对话
 * GET ?thread_id=  — 获取指定对话的消息 + 元数据
 * POST             — 创建/更新对话元数据（body.data）
 * DELETE           — 删除对话元数据
 */
import { json } from '../_utils';

export async function onRequest(context) {
  const { method, url } = context.request;
  const store = context.agent.store;

  if (method === 'GET') {
    const searchParams = new URL(url).searchParams;
    const threadId = searchParams.get('thread_id') || '';

    if (!threadId) {
      const { items } = await store.listConversations({ limit: 100 });
      const threads = [];
      for (const conv of items || []) {
        let meta = {};
        try {
          const raw = await store.get(`thread_meta:${conv.id}`);
          if (raw) meta = JSON.parse(raw);
        } catch {}
        threads.push({ thread_id: conv.id, updated_at: conv.updatedAt, ...meta });
      }
      return json({ threads });
    }

    const raw = await store.getMessages({ conversationId: threadId, limit: 100, order: 'asc' });
    const messages = (raw || []).map((msg) => ({
      id: msg.id || `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      role: ((r) => (r === 'human' ? 'user' : r === 'ai' ? 'assistant' : r))(msg.role || msg.type || ''),
      content: extractText(msg.content),
      toolName: msg.tool_name || msg.name || undefined,
      timestamp: msg.createdAt ? new Date(msg.createdAt).getTime() : Date.now(),
    })).filter((m) => m.content || m.role === 'tool');

    let meta = {};
    try {
      const raw = await store.get(`thread_meta:${threadId}`);
      if (raw) meta = JSON.parse(raw);
    } catch {}

    return json({ thread_id: threadId, messages, meta, total: messages.length });
  }

  if (method === 'POST') {
    try {
      const body = await context.request.json();
      const threadId = body.thread_id || '';
      const data = body.data || {};

      if (!threadId) return json({ error: '缺少 thread_id' }, 400);
      if (Object.keys(data).length === 0) return json({ error: 'data 不能为空' }, 400);

      const metaKey = `thread_meta:${threadId}`;
      let existing = {};
      try {
        const raw = await store.get(metaKey);
        if (raw) existing = JSON.parse(raw);
      } catch {}

      const merged = { ...existing, ...data, updated_at: new Date().toISOString() };
      await store.set(metaKey, JSON.stringify(merged));

      return json({ thread_id: threadId, updated: true, meta: merged });
    } catch (err) {
      return json({ error: err.message }, 500);
    }
  }

  if (method === 'DELETE') {
    try {
      const body = await context.request.json();
      const threadId = body.thread_id || '';
      if (!threadId) return json({ error: '缺少 thread_id' }, 400);

      await store.set(`thread_meta:${threadId}`, '');
      return json({ thread_id: threadId, deleted: true });
    } catch (err) {
      return json({ error: err.message }, 500);
    }
  }

  return json({ error: 'Method not allowed' }, 405);
}

function extractText(raw: any): string {
  if (typeof raw === 'string') return raw;
  if (Array.isArray(raw)) {
    return raw
      .map((part: any) => {
        if (part.type === 'text' || part.type === 'output_text') return part.text || '';
        if (part.type === 'tool_result') return part.content || '';
        if (typeof part === 'string') return part;
        return '';
      })
      .join('');
  }
  if (raw && typeof raw === 'object') {
    return '';
  }
  return '';
}
