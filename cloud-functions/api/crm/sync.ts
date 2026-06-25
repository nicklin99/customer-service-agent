/**
 * POST /api/crm/sync — CRM 同步
 *
 * { lead, profile, thread_id } → 同步到外部 CRM API
 */
import { json } from '../_utils';

export default async function onRequest(context) {
  try {
    const body = await context.request.json();
    const { env } = context;
    const crmEndpoint = env.CRM_API_ENDPOINT;
    const crmApiKey = env.CRM_API_KEY;

    if (!crmEndpoint) return json({ error: 'CRM_API_ENDPOINT 未配置' }, 500);

    const lead = body.lead || {};
    const missing = ['name', 'phone', 'email'].filter((f) => !lead[f]);
    if (missing.length) return json({ error: `缺少字段: ${missing.join(', ')}` }, 400);

    const payload = {
      lead: {
        name: lead.name, phone: lead.phone, email: lead.email,
        company: lead.company || '', position: lead.position || '',
        needs: lead.needs || '', website: lead.website || '',
      },
      profile: body.profile || {},
      source: body.source || env.DEFAULT_SOURCE || 'trendee-智能客服',
      thread_id: body.thread_id || '',
    };

    const resp = await fetch(crmEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'User-Agent': 'EdgeOne-Makers-CRM-Sync/1.0',
        ...(crmApiKey ? { Authorization: `Bearer ${crmApiKey}` } : {}),
      },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      const errText = await resp.text();
      return json({ error: `CRM API error: ${resp.status} ${errText}` }, resp.status);
    }

    return json({ status: 'success', crm_response: await resp.json() });
  } catch (err) {
    console.error('crm sync error:', err);
    return json({ error: err.message }, 500);
  }
}
