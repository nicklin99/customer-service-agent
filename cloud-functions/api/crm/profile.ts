/**
 * POST /api/crm/profile — 用户画像查询
 *
 * 画像和摘要独立存储于 Blob，首次从消息中提取后缓存，后续直接读取。
 * { thread_id } → { profile, summary, message_count }
 */
import { json } from '../_utils';
import { getStore } from '@edgeone/pages-blob';

const blob = getStore('crm');

export default async function onRequest(context) {
  try {
    const body = await context.request.json();
    const threadId = body.thread_id;
    if (!threadId) return json({ error: '缺少 thread_id' }, 400);

    // 先读缓存
    const cached = await blob.get(`profile:${threadId}`, { type: 'json' }).catch(() => null);
    if (cached && cached.profile) {
      return json(cached);
    }

    // 缓存未命中，从消息中提取
    const messages = await context.agent.store.getMessages({
      conversationId: threadId, limit: 100, order: 'asc',
    });

    if (!messages || messages.length === 0) {
      return json({ profile: null, summary: null, message_count: 0 });
    }

    const profile = extractProfile(messages);
    const summary = buildSummary(messages);
    const result = { profile, summary, message_count: messages.length };

    // 缓存到 Blob
    if (profile) {
      await blob.setJSON(`profile:${threadId}`, result).catch(() => {});
    }

    return json(result);
  } catch (err) {
    console.error('crm profile error:', err);
    return json({ error: err.message }, 500);
  }
}

function extractText(raw: any): string {
  if (typeof raw === 'string') return raw;
  if (Array.isArray(raw)) {
    return raw.map((part: any) => {
      if (part.type === 'text' || part.type === 'output_text') return part.text || '';
      if (part.type === 'tool_result') return part.content || '';
      if (typeof part === 'string') return part;
      return '';
    }).join('');
  }
  if (raw && typeof raw === 'object') return '';
  return '';
}

function extractProfile(messages: any[]): any | null {
  if (!messages) return null;
  for (const msg of [...messages].reverse()) {
    if (!['tool', 'function', 'ai', 'assistant'].includes(msg.role || msg.type)) continue;
    const content = extractText(msg.content);
    if (!content.includes('intent_level')) continue;
    try {
      let text = content.trim();
      if (text.startsWith('```')) {
        const lines = text.split('\n');
        text = lines.slice(1, lines[lines.length - 1] === '```' ? -1 : undefined).join('\n');
      }
      const parsed = JSON.parse(text);
      if (parsed.intent_level) return parsed;
    } catch {}
  }
  return null;
}

function buildSummary(messages: any[]) {
  const userMsgs: string[] = [], assistantMsgs: string[] = [];
  for (const msg of messages || []) {
    const role = msg.role || msg.type || '';
    const content = extractText(msg.content).slice(0, 200);
    if (['user', 'human'].includes(role)) userMsgs.push(content);
    else if (['assistant', 'ai'].includes(role)) assistantMsgs.push(content);
  }
  return {
    total_rounds: userMsgs.length,
    user_questions: userMsgs.slice(-5),
    last_assistant_response: assistantMsgs[assistantMsgs.length - 1] || '',
  };
}
