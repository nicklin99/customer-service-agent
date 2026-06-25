import { useState, useRef, useEffect, useCallback } from 'react'
import ChatWidget from './components/ChatWidget'
import LeadForm from './components/LeadForm'
import ProfilePanel from './components/ProfilePanel'
import { BrandProvider, useBrand } from './context/BrandContext'
import {
  streamChat,
  stopGeneration,
  getHistory,
  getProfile,
  getLead,
  generateThreadId,
  type ChatMessage,
  type SSEEvent,
  type LeadData,
  type ProfileData,
} from './api'

type Panel = 'chat' | 'lead' | 'profile'

function AppContent() {
  const isEmbedded = window !== window.parent
  const brand = useBrand()
  const [threadId] = useState(() => {
    const saved = localStorage.getItem('cs_thread_id')
    if (saved) return saved
    const id = generateThreadId()
    localStorage.setItem('cs_thread_id', id)
    return id
  })

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: brand.welcomeMessage,
      timestamp: Date.now(),
    },
  ])

  const [isStreaming, setIsStreaming] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [activePanel, setActivePanel] = useState<Panel>('chat')
  const [leadData, setLeadData] = useState<LeadData | null>(null)
  const [profileData, setProfileData] = useState<ProfileData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  const streamingContentRef = useRef('')
  const assistantMsgIdRef = useRef<string>('')
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    restoreThread()
    return () => {
      mountedRef.current = false
      abortRef.current?.abort()
    }
  }, [])

  async function restoreThread() {
    if (!localStorage.getItem('cs_thread_id')) {
      safeSetState(setLoadingHistory, false)
      return
    }
    try {
      const [profileResult, history, leadResult] = await Promise.all([
        getProfile(threadId),
        getHistory(threadId),
        getLead(threadId),
      ])
      if (profileResult.profile) {
        safeSetState(setProfileData, profileResult.profile)
      }
      if (leadResult) {
        safeSetState(setLeadData, leadResult)
      }
      if (history.length > 0) {
        safeSetState(setMessages, history)
      }
    } catch {
      // 没有历史或出错，保留欢迎消息
    } finally {
      safeSetState(setLoadingHistory, false)
    }
  }

  const safeSetState = <T,>(setter: (value: T) => void, value: T) => {
    if (mountedRef.current) setter(value)
  }

  const fetchProfile = useCallback(async () => {
    try {
      const result = await getProfile(threadId)
      if (result.profile) {
        safeSetState(setProfileData, result.profile)
      }
    } catch {
      // 静默失败
    }
  }, [threadId])

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
        threadId,
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
    [threadId, isStreaming, fetchProfile],
  )

  const handleStop = useCallback(async () => {
    abortRef.current?.abort()
    try {
      await stopGeneration(threadId)
    } catch {
      // 忽略
    }
    safeSetState(setIsStreaming, false)
  }, [threadId])

  const handleLeadUpdate = useCallback((data: LeadData) => {
    safeSetState(setLeadData, data)
  }, [])

  return (
    <div className="h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <span className="text-gold text-sm font-bold">{brand.logoText}</span>
            </div>
            <div>
              <h1 className="text-sm font-semibold text-gray-900">{brand.brandTitle}</h1>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <nav className="flex gap-1">
              {([
                ['chat', '💬', '对话'],
                ['lead', '📋', '线索'],
                ['profile', '📊', '画像'],
              ] as [Panel, string, string][]).map(([key, icon, label]) => (
                <button
                  key={key}
                  onClick={() => setActivePanel(key)}
                  className={`flex flex-col items-center gap-0.5 px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                    activePanel === key
                      ? 'bg-primary text-white'
                      : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <span className="text-base leading-none">{icon}</span>
                  <span className="text-[10px] leading-tight">{label}</span>
                </button>
              ))}
            </nav>
            {isEmbedded && (
              <button
                onClick={() => {
                  window.parent.postMessage({ type: '__aa_minimize' }, '*')
                }}
                className="ml-2 p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                title="最小化"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </header>


      {error && (
        <div className="max-w-6xl mx-auto px-4 mt-2">
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-lg text-sm flex justify-between items-center">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600 ml-4">✕</button>
          </div>
        </div>
      )}

      <main className="flex-1 min-h-0 max-w-6xl mx-auto w-full py-4 flex flex-col">
        <div key={activePanel} className="flex-1 min-h-0 flex flex-col panel-enter">
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
              threadId={threadId}
              leadData={leadData}
              onUpdate={handleLeadUpdate}
            />
          )}

          {activePanel === 'profile' && (
            <ProfilePanel
              profileData={profileData}
              leadData={leadData}
              threadId={threadId}
              onRefresh={fetchProfile}
            />
          )}
        </div>
      </main>

      <footer className="text-center py-3 text-xs text-gray-400 border-t border-gray-100 bg-white">
        {brand.footerText} · {brand.version}
      </footer>
    </div>
  )
}

export default function App() {
  return (
    <BrandProvider>
      <AppContent />
    </BrandProvider>
  )
}

function getToolLabel(name: string): string {
  const map: Record<string, string> = {
    collect_lead: '收集客户线索',
    analyze_user_profile: '分析用户画像',
    save_to_crm: '同步到 CRM',
  }
  return map[name] || name
}
