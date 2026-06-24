"""
CRM 同步云函数 — 将线索数据推送到外部 CRM API。
无状态模式，按请求弹性扩缩容。
"""
import json
import logging
import os

import httpx

logger = logging.getLogger("crm-sync")


async def main(context):
    """
    POST /crm-sync
    接收线索数据，转发到配置的 CRM API 端点。

    请求体:
    {
        "lead": { "name": "...", "phone": "...", ... },
        "profile": { ... },
        "source": "智能客服-小星",
        "conversation_id": "..."
    }
    """
    crm_endpoint = context.env.get(
        "CRM_API_ENDPOINT",
        os.environ.get("CRM_API_ENDPOINT", ""),
    )
    crm_api_key = context.env.get(
        "CRM_API_KEY",
        os.environ.get("CRM_API_KEY", ""),
    )

    if not crm_endpoint:
        return {
            "status": "error",
            "message": "CRM_API_ENDPOINT 未配置。请在环境变量中设置 CRM API 地址。",
        }

    try:
        body = await context.request.json()
    except Exception:
        return {"status": "error", "message": "请求体必须是有效的 JSON"}

    lead = body.get("lead", {})
    profile = body.get("profile", {})
    source = body.get("source", "智能客服")
    conversation_id = body.get("conversation_id", "")

    # 基础验证
    required_fields = ["name", "phone", "email"]
    missing = [f for f in required_fields if not lead.get(f)]
    if missing:
        return {
            "status": "error",
            "message": f"线索信息不完整，缺少: {', '.join(missing)}",
        }

    # 构建 CRM 请求
    payload = {
        "lead": {
            "name": lead.get("name", ""),
            "phone": lead.get("phone", ""),
            "email": lead.get("email", ""),
            "company": lead.get("company", ""),
            "position": lead.get("position", ""),
            "needs": lead.get("needs", ""),
            "budget": lead.get("budget", ""),
            "timeline": lead.get("timeline", ""),
        },
        "profile": profile,
        "source": source,
        "conversation_id": conversation_id,
        "created_at": "",  # CRM 系统自行打时间戳
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "EdgeOne-Makers-CRM-Sync/1.0",
    }
    if crm_api_key:
        headers["Authorization"] = f"Bearer {crm_api_key}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(crm_endpoint, json=payload, headers=headers)
            resp.raise_for_status()

            logger.info(
                f"CRM sync success: {lead.get('name')} ({lead.get('company', 'N/A')})"
            )

            return {
                "status": "success",
                "message": "线索已成功同步到 CRM",
                "crm_response": resp.json() if resp.text else {},
            }

    except httpx.HTTPStatusError as e:
        logger.error(f"CRM API error: {e.response.status_code} - {e.response.text}")
        return {
            "status": "error",
            "message": f"CRM API 返回错误 ({e.response.status_code})",
            "detail": e.response.text[:500],
        }
    except httpx.RequestError as e:
        logger.error(f"CRM API request failed: {e}")
        return {
            "status": "error",
            "message": f"无法连接到 CRM API: {str(e)}",
        }


__all__ = ["main"]
