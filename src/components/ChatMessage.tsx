import type { ChatMessage } from '../api'

interface Props {
  message: ChatMessage
}

export default function ChatMessageView({ message }: Props) {
  const isUser = message.role === 'user'
  const isTool = message.role === 'tool'

  if (isTool) {
    return (
      <div className="flex justify-center">
        <div className="px-3 py-1 text-xs text-gray-500 bg-gray-100 rounded-full animate-pulse">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* 头像 */}
      <div
        className={`w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center text-xs font-bold ${
          isUser
            ? 'bg-gold text-white'
            : 'bg-primary text-gold'
        }`}
      >
        {isUser ? '我' : '星'}
      </div>

      {/* 消息气泡 */}
      <div
        className={`max-w-[75%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
          isUser
            ? 'bg-primary text-white rounded-tr-sm'
            : 'bg-white border border-gray-200 text-gray-800 rounded-tl-sm shadow-sm'
        }`}
      >
        {message.content || (
          <span className="typing-cursor text-gray-400">思考中</span>
        )}
        <div className={`text-[10px] mt-1 opacity-50 ${isUser ? 'text-right' : ''}`}>
          {new Date(message.timestamp).toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </div>
      </div>
    </div>
  )
}
