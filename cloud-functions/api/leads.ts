/**
 * POST /api/leads — 线索查询
 */
import { json, extractLead } from './_utils';

export async function onRequest(context) {
  try {
    const body = await context.request.json();
    const action = body.action || 'list';

    if (action === 'list') {
      const { items } = await context.agent.store.listConversations({ limit: 100 });
      const leads = [];
      for (const conv of items || []) {
        const msgs = await context.agent.store.getMessages({
          conversationId: conv.id,
          limit: 100,
          order: 'desc',
        });
        const leadInfo = extractLead(msgs);
        if (leadInfo) {
          leads.push({ conversation_id: conv.id, updated_at: conv.updatedAt, lead: leadInfo });
        }
      }
      return json({ leads });
    }

    if (action === 'get') {
      const conversationId = body.conversation_id;
      if (!conversationId) return json({ error: '缺少 conversation_id' }, 400);
      const msgs = await context.agent.store.getMessages({
        conversationId,
        limit: 100,
        order: 'asc',
      });
      return json({
        conversation_id: conversationId,
        lead: extractLead(msgs),
        message_count: msgs?.length || 0,
      });
    }

    return json({ error: `Unknown action: ${action}` }, 400);
  } catch (err) {
    console.error('leads error:', err);
    return json({ error: err.message }, 500);
  }
}
