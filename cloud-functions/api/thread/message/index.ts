/**
 * /api/thread/message — 对话消息 CRUD（REST）
 *
 * GET     ?thread_id=  — 列出消息（store + 自定义备注合并）
 * POST                 — 创建自定义消息（body.data）
 * PUT                  — 更新自定义消息（body.message_id + body.data）
 * DELETE               — 删除自定义消息（body.message_id）
 *
 * 自定义消息存于 KV thread_notes:{thread_id}，ID 以 note_ 开头。
 */
import { json } from '../../_utils';

export async function onRequest(context) {
  const { method, url } = context.request;
  const store = context.agent.store;

  const searchParams = new URL(url).searchParams;

  async function getThreadId(): Promise<string> {
    if (method === 'GET') return searchParams.get('thread_id') || '';
    try {
      const body = await context.request.json();
      return body.thread_id || '';
    } catch {
      return '';
    }
  }

  const threadId = await getThreadId();
  if (!threadId) return json({ error: '缺少 thread_id' }, 400);

  const NOTES_KEY = `thread_notes:${threadId}`;

  if (method === 'GET') {
    const raw = await store.getMessages({ conversationId: threadId, limit: 100, order: 'asc' });

    const messages = (raw || []).map((msg) => ({
      id: msg.messageId,
      role: ((r) => (r === 'human' ? 'user' : r === 'ai' ? 'assistant' : r))(msg.role || msg.type || ''),
      content: extractText(msg.content),
      toolName: msg.tool_name || msg.name || undefined,
      timestamp: msg.createdAt ? new Date(msg.createdAt).getTime() : Date.now(),
    })).filter((m) => m.content || m.role === 'tool');

    let notes = [];
    try {
      const raw = await store.get(NOTES_KEY);
      if (raw) notes = JSON.parse(raw);
    } catch {}
    for (const note of notes) {
      if (!messages.find((m) => m.id === note.id)) messages.push(note);
    }
    messages.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));

    return json({ thread_id: threadId, messages, total: messages.length });
  }

  let body: any = {};
  try { body = await context.request.json(); } catch {}

  if (method === 'POST') {
    const msgData = body.data || {};
    if (!msgData.content) return json({ error: 'data.content 不能为空' }, 400);

    const message = {
      id: `note_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      role: msgData.role || 'system',
      content: msgData.content,
      toolName: msgData.toolName || undefined,
      metadata: msgData.metadata || {},
      timestamp: Date.now(),
    };

    let notes: any[] = [];
    try { const raw = await store.get(NOTES_KEY); if (raw) notes = JSON.parse(raw); } catch {}
    notes.push(message);
    await store.set(NOTES_KEY, JSON.stringify(notes));

    return json({ thread_id: threadId, message, created: true });
  }

  if (method === 'PUT') {
    const messageId = body.message_id || '';
    const msgData = body.data || {};
    if (!messageId) return json({ error: '缺少 message_id' }, 400);

    let notes: any[] = [];
    try { const raw = await store.get(NOTES_KEY); if (raw) notes = JSON.parse(raw); } catch {}

    const idx = notes.findIndex((n) => n.id === messageId);
    if (idx === -1) return json({ error: '消息不存在或不是自定义消息' }, 404);

    notes[idx] = { ...notes[idx], ...msgData, id: messageId, updated_at: Date.now() };
    await store.set(NOTES_KEY, JSON.stringify(notes));

    return json({ thread_id: threadId, message: notes[idx], updated: true });
  }

  if (method === 'DELETE') {
    const messageId = body.message_id || '';
    if (!messageId) return json({ error: '缺少 message_id' }, 400);

    let notes: any[] = [];
    try { const raw = await store.get(NOTES_KEY); if (raw) notes = JSON.parse(raw); } catch {}

    const before = notes.length;
    notes = notes.filter((n) => n.id !== messageId);
    if (notes.length === before) return json({ error: '消息不存在或不是自定义消息' }, 404);

    await store.set(NOTES_KEY, JSON.stringify(notes));

    return json({ thread_id: threadId, message_id: messageId, deleted: true });
  }

  return json({ error: 'Method not allowed' }, 405);
}

function extractText(raw: any) {
  return raw
  // if (typeof raw === 'string') return raw;
  // if (Array.isArray(raw)) {
  //   return raw
  //     .map((part: any) => { if (part.type === 'text' || part.type === 'output_text') return part.text || ''; if (part.type === 'tool_result') return part.content || ''; if (typeof part === 'string') return part; return ''; })
  //     .join('');
  // }
  // if (raw && typeof raw === 'object') return raw.text || raw.content || JSON.stringify(raw);
  // return '';
}
