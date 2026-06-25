/**
 * POST /api/crm/leads — 线索 CRUD（Blob 存储）
 *
 * 请求体格式：
 *   { thread_id }               → 读取对话线索
 *   { thread_id, lead: {...} }  → 保存/更新对话线索
 *
 * 数据存储于 Blob key: lead:{thread_id}
 */
import { json } from '../_utils';
import { getStore } from '@edgeone/pages-blob';

const store = getStore('crm');
const LEAD_PREFIX = 'lead:';

export default async function onRequest(context) {
  try {
    const body = await context.request.json();
    const threadId = body.thread_id || '';

    if (!threadId) {
      return json({ error: 'thread_id is required' }, 400);
    }

    const key = `${LEAD_PREFIX}${threadId}`;

    // 保存线索（表单输入数据）
    if (body.lead) {
      const leadData = { ...body.lead, updated_at: new Date().toISOString() };
      await store.setJSON(key, leadData);
      return json({ thread_id: threadId, lead: leadData, saved: true });
    }

    // 读取线索
    const raw = await store.get(key, { type: 'json' });
    return json({ thread_id: threadId, lead: raw || null });
  } catch (err) {
    return json({ error: err.message }, 500);
  }
}
