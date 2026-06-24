/**
 * POST /api/profile — 用户画像查询
 */
import { json, extractProfile, buildSummary } from './_utils';

export async function onRequest(context) {
  try {
    const body = await context.request.json();
    const conversationId = body.conversation_id;
    if (!conversationId) return json({ error: '缺少 conversation_id' }, 400);

    const messages = await context.agent.store.getMessages({
      conversationId,
      limit: 100,
      order: 'asc',
    });

    if (!messages || messages.length === 0) {
      return json({ profile: null, message: '该会话暂无消息记录' });
    }

    return json({
      profile: extractProfile(messages),
      summary: buildSummary(messages),
      message_count: messages.length,
    });
  } catch (err) {
    console.error('profile error:', err);
    return json({ error: err.message }, 500);
  }
}
