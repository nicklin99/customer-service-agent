"""
品牌设置云函数 — 返回站点品牌配置信息。
从环境变量读取，支持灵活配置。
"""

import logging
import os

logger = logging.getLogger("settings")


async def handler(request):
    """GET /settings — 返回品牌 JSON"""
    brand_config = {
        "brandName": os.environ.get("BRAND_NAME", "trendee"),
        "brandTitle": os.environ.get("BRAND_TITLE", "trendee 智能客服"),
        "agentName": os.environ.get("AGENT_NAME", "trendee"),
        "logoText": os.environ.get("LOGO_TEXT", "T"),
        "welcomeMessage": os.environ.get(
            "WELCOME_MESSAGE",
            "您好！我是 trendee，trendee 的智能顾问 ☀️\n\n请问有什么可以帮您的？",
        ),
        "footerText": os.environ.get("FOOTER_TEXT", "trendee · 智能客服系统"),
        "defaultSource": os.environ.get("DEFAULT_SOURCE", "trendee-智能客服"),
        "placeholder": os.environ.get("PLACEHOLDER", "输入您的问题，trendee 随时为您解答..."),
        "streamingText": os.environ.get("STREAMING_TEXT", "trendee 正在输入..."),
    }

    return {"status_code": 200, "body": brand_config}
