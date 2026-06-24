/**
 * 共享工具函数
 */
export function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
}

export function extractProfile(messages) {
  if (!messages) return null;
  for (const msg of [...messages].reverse()) {
    if (!['tool', 'function', 'ai', 'assistant'].includes(msg.role || msg.type)) continue;
    const content = msg.content || '';
    if (typeof content !== 'string' || !content.includes('intent_level')) continue;
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

export function buildSummary(messages) {
  const userMsgs = [], assistantMsgs = [];
  for (const msg of messages || []) {
    const role = msg.role || msg.type || '';
    const content = (msg.content || '').slice(0, 200);
    if (['user', 'human'].includes(role)) userMsgs.push(content);
    else if (['assistant', 'ai'].includes(role)) assistantMsgs.push(content);
  }
  return {
    total_rounds: userMsgs.length,
    user_questions: userMsgs.slice(-5),
    last_assistant_response: assistantMsgs[assistantMsgs.length - 1] || '',
  };
}

export function extractLead(messages) {
  if (!messages) return null;
  for (const msg of [...messages].reverse()) {
    if (!['tool', 'function'].includes(msg.role || msg.type)) continue;
    const content = msg.content || '';
    if (typeof content !== 'string') continue;
    if (!content.includes('"status"') || !content.includes('"collected"')) continue;
    try {
      const parsed = JSON.parse(content);
      if (parsed.status === 'complete' && parsed.collected) return parsed.collected;
    } catch {}
  }
  return null;
}
