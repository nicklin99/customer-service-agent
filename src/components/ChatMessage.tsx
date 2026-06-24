import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import type { ChatMessage } from '../api'
import AiSparkle from './AiSparkle'

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
        className={`w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center ${
          isUser
            ? 'bg-gold text-white text-xs font-bold'
            : 'bg-white border border-gray-200 text-gold'
        }`}
      >
        {isUser ? '我' : <AiSparkle className="w-5 h-5" />}
      </div>

      {/* 消息气泡 */}
      <div
        className={`max-w-[75%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
          isUser
            ? 'bg-primary text-white rounded-tr-sm'
            : 'bg-white border border-gray-200 text-gray-800 rounded-tl-sm shadow-sm'
        }`}
      >
        {message.content ? (
          isUser ? (
            <span className="whitespace-pre-wrap">{message.content}</span>
          ) : (
            <div className="prose prose-sm max-w-none prose-headings:text-gray-900 prose-a:text-primary prose-code:bg-gray-100 prose-code:px-1 prose-code:rounded prose-code:text-xs prose-ul:pl-4 prose-ol:pl-4 prose-li:my-0.5">
              <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                {message.content}
              </ReactMarkdown>
            </div>
          )
        ) : (
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
