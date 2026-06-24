import { useState, useRef, useEffect, useCallback } from 'react'
import ChatWidget from './components/ChatWidget'
import LeadForm from './components/LeadForm'
import ProfilePanel from './components/ProfilePanel'
import {
  streamChat,
  stopGeneration,
  getProfile,
  generateConversationId,
  type ChatMessage,
  type SSEEvent,
  type LeadData,
  type ProfileData,
} from './api'

type Panel = 'chat' | 'lead' | 'profile'

export default function App() {
  const [conversationId] = useState(() => {
    const saved = sessionStorage.getItem('cs_conversation_id')
    if (saved) return saved
    const id = generateConversationId()
    sessionStorage.setItem('cs_conversation_id', id)
    return id
  })

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        '您好！我是小星，星帆科技的智能顾问 ☀️\n\n无论您是想了解我们的建站服务、SEO 优化、品牌设计，还是 AI 解决方案，我都可以为您解答。请问有什么可以帮您的？',
      timestamp: Date.now(),
    },
  ])

  const [isStreaming, setIsStreaming] = useState(false)
  const [activePanel, setActivePanel] = useState<Panel>('chat')
  const [leadData, setLeadData] = useState<LeadData | null>(null)
  const [profileData, setProfileData] = useState<ProfileData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  const streamingContentRef = useRef('')
  const assistantMsgIdRef = useRef<string>('')
  const mountedRef = useRef(true)

  // 组件卸载标记 — 防止 SSE 回调在卸载后 setState
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      abortRef.current?.abort()
    }
  }, [])

  const safeSetState = <T,>(setter: (value: T) => void, value: T) => {
    if (mountedRef.current) setter(value)
  }

  const fetchProfile = useCallback(async () => {
    try {
      const result = await getProfile(conversationId)
      if (result.profile) {
        safeSetState(setProfileData, result.profile)
      }
    } catch {
      // 静默失败
    }
  }, [conversationId])

  const handleSend = useCallback(
    async (text: string) => {
      if (!text.trim() || isStreaming) return

      safeSetState(setError, null)
      const userMsg: ChatMessage = {
        id: `user_${Date.now()}`,
        role: 'user',
        content: text,
        timestamp: Date.now(),
      }
      safeSetState(setMessages, (prev: ChatMessage[]) => [...prev, userMsg])

      const assistantMsgId = `assistant_${Date.now()}`
      assistantMsgIdRef.current = assistantMsgId
      const assistantMsg: ChatMessage = {
        id: assistantMsgId,
        role: 'assistant',
        content: '',
        timestamp: Date.now(),
      }
      safeSetState(setMessages, (prev: ChatMessage[]) => [...prev, assistantMsg])
      streamingContentRef.current = ''
      safeSetState(setIsStreaming, true)

      const controller = streamChat(
        text,
        conversationId,
        (event: SSEEvent) => {
          if (!mountedRef.current) return
          switch (event.type) {
            case 'text_delta':
              if (event.content) {
                streamingContentRef.current += event.content
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsgIdRef.current
                      ? { ...m, content: streamingContentRef.current }
                      : m,
                  ),
                )
              }
              break

            case 'tool_called':
              if (event.tool_name) {
                const toolMsg: ChatMessage = {
                  id: `tool_${Date.now()}`,
                  role: 'tool',
                  content: `🔧 正在执行: ${getToolLabel(event.tool_name)}`,
                  toolName: event.tool_name,
                  timestamp: Date.now(),
                }
                setMessages((prev) => [...prev, toolMsg])
              }
              break

            case 'tool_result':
              if (event.output) {
                try {
                  const result = JSON.parse(event.output)
                  if (event.tool_name === 'collect_lead' && result.collected) {
                    safeSetState(setLeadData, result.collected)
                  }
                } catch {
                  // 非 JSON 输出忽略
                }
              }
              break

            case 'error':
              safeSetState(setError, event.message || '发生未知错误')
              break

            case 'done':
              break
          }
        },
        () => {
          if (!mountedRef.current) return
          safeSetState(setIsStreaming, false)
          fetchProfile()
        },
        (err) => {
          if (!mountedRef.current) return
          safeSetState(setError, err.message)
          safeSetState(setIsStreaming, false)
        },
      )

      abortRef.current = controller
    },
    [conversationId, isStreaming, fetchProfile],
  )

  const handleStop = useCallback(async () => {
    abortRef.current?.abort()
    try {
      await stopGeneration(conversationId)
    } catch {
      // 忽略
    }
    safeSetState(setIsStreaming, false)
  }, [conversationId])

  const handleLeadUpdate = useCallback((data: LeadData) => {
    safeSetState(setLeadData, data)
  }, [])

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* 顶部导航 */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <span className="text-gold text-sm font-bold">星</span>
            </div>
            <div>
              <h1 className="text-sm font-semibold text-gray-900">星帆智能客服</h1>
              <p className="text-xs text-gray-500">Powered by AI · 小星</p>
            </div>
          </div>

          {/* Tab 导航 */}
          <nav className="flex gap-1">
            {([
              ['chat', '💬', '对话'],
              ['lead', '📋', '线索'],
              ['profile', '📊', '画像'],
            ] as [Panel, string, string][]).map(([key, icon, label]) => (
              <button
                key={key}
                onClick={() => setActivePanel(key)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  activePanel === key
                    ? 'bg-primary text-white'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                }`}
              >
                <span className="mr-1">{icon}</span>
                {label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* 错误提示 */}
      {error && (
        <div className="max-w-6xl mx-auto px-4 mt-2">
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-lg text-sm flex justify-between items-center">
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              className="text-red-400 hover:text-red-600 ml-4"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* 主内容区 */}
      <main className="flex-1 max-w-6xl mx-auto w-full px-4 py-4">
        {activePanel === 'chat' && (
          <ChatWidget
            messages={messages}
            isStreaming={isStreaming}
            onSend={handleSend}
            onStop={handleStop}
          />
        )}

        {activePanel === 'lead' && (
          <LeadForm
            leadData={leadData}
            onUpdate={handleLeadUpdate}
          />
        )}

        {activePanel === 'profile' && (
          <ProfilePanel
            profileData={profileData}
            leadData={leadData}
            conversationId={conversationId}
            onRefresh={fetchProfile}
          />
        )}
      </main>

      {/* 底部信息 */}
      <footer className="text-center py-3 text-xs text-gray-400 border-t border-gray-100 bg-white">
        星帆科技 · 智能客服系统 · Conversation: {conversationId}
      </footer>
    </div>
  )
}

/** 工具名称中文映射 */
function getToolLabel(name: string): string {
  const map: Record<string, string> = {
    collect_lead: '收集客户线索',
    analyze_user_profile: '分析用户画像',
    save_to_crm: '同步到 CRM',
  }
  return map[name] || name
}
