/**
 * GET /api/settings — 品牌配置
 */
import { json } from './_utils';

export async function onRequest(context) {
  const { env } = context;
  return json({
    brandName: env.BRAND_NAME || 'trendee',
    brandTitle: env.BRAND_TITLE || 'trendee 智能客服',
    agentName: env.AGENT_NAME || 'trendee',
    logoText: env.LOGO_TEXT || 'T',
    welcomeMessage: env.WELCOME_MESSAGE || '您好！我是 trendee，trendee 的智能顾问 \n\n请问有什么可以帮您的？',
    footerText: env.FOOTER_TEXT || 'trendee · 智能客服系统',
    defaultSource: env.DEFAULT_SOURCE || 'trendee-智能客服',
    placeholder: env.PLACEHOLDER || '输入您的问题, trendee 随时为您解答...',
    streamingText: env.STREAMING_TEXT || 'trendee 正在输入...',
  });
}
