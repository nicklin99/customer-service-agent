/**
 * 智能客服 API 封装
 * 处理 SSE 流式响应和 REST API 调用
 */

const BASE_URL = '/api'

// ── 类型定义 ────────────────────────────────────

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  toolName?: string
  timestamp: number
}

export interface LeadData {
  name: string
  phone: string
  email: string
  company: string
  position: string
  needs: string
  source: string
  budget: string
  timeline: string
}

export interface ProfileData {
  intent_level: string
  customer_type: string
  primary_need: string
  pain_points: string[]
  recommended_services: string[]
  estimated_value: string
  urgency: string
  persona_summary: string
  key_insights: string[]
}

export interface SSEEvent {
  type: 'text_delta' | 'tool_called' | 'tool_result' | 'done' | 'error'
  content?: string
  tool_name?: string
  status?: string
  output?: string
  message?: string
  conversation_id?: string
}

// ── SSE 流式聊天 ─────────────────────────────────

export function streamChat(
  message: string,
  conversationId: string,
  onEvent: (event: SSEEvent) => void,
  onDone: () => void,
  onError: (error: Error) => void,
): AbortController {
  const controller = new AbortController()

  fetch('/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'makers-conversation-id': conversationId,
    },
    body: JSON.stringify({ message, action: 'chat' }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim()
            if (!data || data === '[DONE]') continue
            try {
              const event = JSON.parse(data) as SSEEvent
              onEvent(event)
              if (event.type === 'done') {
                onDone()
              }
            } catch {
              // 非 JSON 行，忽略
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError(err)
      }
    })

  return controller
}

// ── 停止生成 ─────────────────────────────────────

export async function stopGeneration(conversationId: string): Promise<void> {
  await fetch('/stop', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'makers-conversation-id': conversationId,
    },
    body: JSON.stringify({}),
  })
}

// ── 获取对话历史 ─────────────────────────────────

export async function getHistory(conversationId: string): Promise<ChatMessage[]> {
  const resp = await fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'makers-conversation-id': conversationId,
    },
    body: JSON.stringify({ action: 'history' }),
  })
  const data = await resp.json()
  const body = data.body || data
  return body.messages || []
}

// ── 查询线索 ─────────────────────────────────────

export async function getLeads(): Promise<any[]> {
  const resp = await fetch(`${BASE_URL}/leads`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'list' }),
  })
  const data = await resp.json()
  const body = data.body || data
  return body.leads || []
}

// ── 查询用户画像 ─────────────────────────────────

export async function getProfile(conversationId: string): Promise<{
  profile: ProfileData | null
  summary: any
}> {
  const resp = await fetch(`${BASE_URL}/profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId }),
  })
  const data = await resp.json()
  return data.body || data
}

// ── 工具函数 ─────────────────────────────────────

export function generateConversationId(): string {
  return `conv_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}
