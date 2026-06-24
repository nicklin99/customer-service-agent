import { useState, useRef, useEffect } from 'react'
import type { ChatMessage } from '../api'
import ChatMessageView from './ChatMessage'
import { useBrand } from '../context/BrandContext'

interface Props {
  messages: ChatMessage[]
  isStreaming: boolean
  onSend: (text: string) => void
  onStop: () => void
}

export default function ChatWidget({ messages, isStreaming, onSend, onStop }: Props) {
  const brand = useBrand()
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // 自动滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 自动聚焦
  useEffect(() => {
    if (!isStreaming) {
      inputRef.current?.focus()
    }
  }, [isStreaming])

  const handleSubmit = () => {
    if (!input.trim() || isStreaming) return
    onSend(input.trim())
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-12rem)]">
      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.map((msg) => (
          <ChatMessageView key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* 快捷引导（预留） */}

      {/* 输入区 */}
      <div className="border border-gray-200 rounded-xl bg-white shadow-sm">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={brand.placeholder}
          rows={2}
          disabled={isStreaming}
          className="w-full px-4 py-3 text-sm resize-none rounded-t-xl focus:outline-none disabled:bg-gray-50 disabled:text-gray-400"
        />
        <div className="flex items-center justify-between px-4 py-2 border-t border-gray-100">
          <span className="text-xs text-gray-400">
            {isStreaming ? brand.streamingText : 'Enter 发送 · Shift+Enter 换行'}
          </span>
          <div className="flex gap-2">
            {isStreaming && (
              <button
                onClick={onStop}
                className="px-4 py-1.5 text-xs font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition-colors"
              >
                停止生成
              </button>
            )}
            <button
              onClick={handleSubmit}
              disabled={!input.trim() || isStreaming}
              className="px-5 py-1.5 text-xs font-medium text-white bg-primary rounded-lg hover:bg-primary-light disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              发送
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
