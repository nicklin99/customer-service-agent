"""
CRM 同步云函数 — 将线索数据推送到外部 CRM API。
"""
import json
import logging
import os

import httpx

logger = logging.getLogger("crm-sync")


async def handler(context):
    """POST /crm-sync"""
    crm_endpoint = context.env.get(
        "CRM_API_ENDPOINT", os.environ.get("CRM_API_ENDPOINT", ""),
    )
    crm_api_key = context.env.get(
        "CRM_API_KEY", os.environ.get("CRM_API_KEY", ""),
    )

    if not crm_endpoint:
        return {"status_code": 500, "body": {"error": "CRM_API_ENDPOINT 未配置"}}

    body = context.body or {}
    lead = body.get("lead", {})
    default_source = context.env.get("DEFAULT_SOURCE", os.environ.get("DEFAULT_SOURCE", "trendee-智能客服"))

    required_fields = ["name", "phone", "email"]
    missing = [f for f in required_fields if not lead.get(f)]
    if missing:
        return {"status_code": 400, "body": {"error": f"缺少字段: {', '.join(missing)}"}}

    payload = {
        "lead": {
            "name": lead.get("name", ""),
            "phone": lead.get("phone", ""),
            "email": lead.get("email", ""),
            "company": lead.get("company", ""),
            "position": lead.get("position", ""),
            "needs": lead.get("needs", ""),
            "website": lead.get("website", ""),
        },
        "profile": body.get("profile", {}),
        "source": body.get("source", default_source),
        "conversation_id": body.get("conversation_id", ""),
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
            return {"status_code": 200, "body": {"status": "success", "crm_response": resp.json()}}
    except httpx.HTTPStatusError as e:
        logger.error(f"CRM API error: {e.response.status_code}")
        return {"status_code": e.response.status_code, "body": {"error": str(e)}}
    except Exception as e:
        logger.error(f"CRM sync failed: {e}")
        return {"status_code": 500, "body": {"error": str(e)}}
