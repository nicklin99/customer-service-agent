export interface BrandConfig {
  /** 品牌名称，如 trendee */
  brandName: string
  /** 页面标题 / 顶部标题 */
  brandTitle: string
  /** AI 助手名称 */
  agentName: string
  /** Logo 文字（品牌首字母/字） */
  logoText: string
  /** 欢迎消息 */
  welcomeMessage: string
  /** 底部版权文字 */
  footerText: string
  /** 线索来源默认值 */
  defaultSource: string
  /** 输入框占位文案 */
  placeholder: string
  /** 正在输入提示 */
  streamingText: string
}

export const defaultBrand: BrandConfig = {
  brandName: 'trendee',
  brandTitle: 'trendee 智能客服',
  agentName: 'trendee',
  logoText: 'T',
  welcomeMessage:
    '您好！我是 trendee，trendee 的智能顾问 ☀️\n\n请问有什么可以帮您的？',
  footerText: 'trendee · 智能客服系统',
  defaultSource: 'trendee-智能客服',
  placeholder: '输入您的问题，trendee 随时为您解答...',
  streamingText: 'trendee 正在输入...',
}

/**
 * 从远程 API 获取品牌配置
 */
export async function fetchBrandConfig(): Promise<BrandConfig> {
  try {
    const resp = await fetch('/api/settings')
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    // 兼容 EdgeOne Makers 的 body 包装
    const config = data.body || data
    return { ...defaultBrand, ...config }
  } catch (err) {
    console.warn('[brand] 获取远程设置失败，使用默认配置:', err)
    return defaultBrand
  }
}
