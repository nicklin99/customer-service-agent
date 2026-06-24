"""
品牌设置云函数 — 返回站点品牌配置信息。
从 EdgeOne 环境变量读取，支持灵活配置。
"""

import logging

logger = logging.getLogger("settings")


async def handler(context):
    """GET /settings — 返回品牌 JSON"""
    env = context.env

    brand_config = {
        "brandName": env.get("BRAND_NAME", "trendee"),
        "brandTitle": env.get("BRAND_TITLE", "trendee 智能客服"),
        "agentName": env.get("AGENT_NAME", "trendee"),
        "logoText": env.get("LOGO_TEXT", "T"),
        "welcomeMessage": env.get(
            "WELCOME_MESSAGE",
            "您好！我是 trendee，trendee 的智能顾问 ☀️\n\n无论您是想了解我们的建站服务、SEO 优化、品牌设计，还是 AI 解决方案，我都可以为您解答。请问有什么可以帮您的？",
        ),
        "footerText": env.get("FOOTER_TEXT", "trendee · 智能客服系统"),
        "defaultSource": env.get("DEFAULT_SOURCE", "trendee-智能客服"),
        "placeholder": env.get("PLACEHOLDER", "输入您的问题，trendee 随时为您解答..."),
        "streamingText": env.get("STREAMING_TEXT", "trendee 正在输入..."),
    }

    return {"status_code": 200, "body": brand_config}
