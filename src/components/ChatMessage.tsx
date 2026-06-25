import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import type { ChatMessage } from '../api'
import AiSparkle from './AiSparkle'

interface Props {
  message: ChatMessage
}

/** 合并所有文本块 */
function joinTextBlocks(blocks: any[]): string {
  return blocks
    .filter((b: any) => b.type === 'output_text' || b.type === 'text')
    .map((b: any) => b.text || '')
    .join('')
}

/** 提取可显示的文本内容（兼容全部已知格式） */
function extractMessageText(message: ChatMessage): string {
  const c = message.content
  if (!c) return ''

  // 纯文本
  if (typeof c === 'string') return c

  // 扁平内容块数组: [{ type: "output_text", text: "..." }]
  if (Array.isArray(c)) return joinTextBlocks(c)

  // 包装对象
  if (typeof c === 'object') {
    // 用户消息: { role: "user", content: "你好" }
    if (c.role === 'user' && typeof c.content === 'string') return c.content

    // assistant 消息: { type: "message", content: [{ type: "output_text", text: "..." }] }
    if (Array.isArray(c.content)) return joinTextBlocks(c.content)

    // 直接带 text 字段
    if (typeof c.text === 'string') return c.text
  }

  // 兜底：JSON 序列化以便调试实际结构
  return JSON.stringify(c, null, 2)
}

export default function ChatMessageView({ message }: Props) {
  const isUser = message.role === 'user'
  const isTool = message.role === 'tool'
  const content = message.content

  // 推理消息直接隐藏
  if (!isUser && !isTool && typeof content === 'object' && content?.type === 'reasoning') {
    return null
  }

  if (isTool) {
    return (
      <div className="flex justify-center">
        <div className="px-3 py-1 text-xs text-gray-500 bg-gray-100 rounded-full animate-pulse">
          {typeof content === 'string' ? content : ''}
        </div>
      </div>
    )
  }



  // 提取可显示文本
  const text = extractMessageText(message)

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
        {text ? (
          isUser ? (
            <span className="whitespace-pre-wrap">{text}</span>
          ) : (
            <div className="prose prose-sm max-w-none prose-headings:text-gray-900 prose-a:text-primary prose-code:bg-gray-100 prose-code:px-1 prose-code:rounded prose-code:text-xs prose-ul:pl-4 prose-ol:pl-4 prose-li:my-0.5">
              <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                {text}
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
