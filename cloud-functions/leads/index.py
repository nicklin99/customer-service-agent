"""
线索查询云函数 — 查询已收集的客户线索。
"""
import json
import logging

logger = logging.getLogger("leads-query")


async def handler(context):
    """POST /leads"""
    body = context.body or {}
    action = body.get("action", "list")

    if action == "list":
        try:
            conversations = await context.agent.store.list_conversations()
            leads = []
            for conv in conversations:
                messages = await context.agent.store.get_messages(conv.get("id", ""))
                lead_info = _extract_lead_from_messages(messages)
                if lead_info:
                    leads.append({
                        "conversation_id": conv.get("id"),
                        "updated_at": conv.get("updated_at", ""),
                        "lead": lead_info,
                    })
            return {"status_code": 200, "body": {"leads": leads}}
        except Exception as e:
            return {"status_code": 500, "body": {"error": str(e)}}

    elif action == "get":
        conversation_id = body.get("conversation_id", "")
        if not conversation_id:
            return {"status_code": 400, "body": {"error": "缺少 conversation_id"}}
        try:
            messages = await context.agent.store.get_messages(conversation_id)
            lead_info = _extract_lead_from_messages(messages)
            return {
                "status_code": 200,
                "body": {
                    "conversation_id": conversation_id,
                    "lead": lead_info,
                    "message_count": len(messages) if messages else 0,
                },
            }
        except Exception as e:
            return {"status_code": 500, "body": {"error": str(e)}}

    return {"status_code": 400, "body": {"error": f"Unknown action: {action}"}}


def _extract_lead_from_messages(messages: list) -> dict | None:
    if not messages:
        return None
    lead_fields = {}
    for msg in messages:
        role = msg.get("role", msg.get("type", ""))
        if role not in ("tool", "function"):
            continue
        content = msg.get("content", "")
        if not isinstance(content, str):
            continue
        if not (content.strip().startswith("{") and '"status"' in content and '"collected"' in content):
            continue
        try:
            parsed = json.loads(content)
            if parsed.get("status") == "complete" and parsed.get("collected"):
                lead_fields = parsed["collected"]
        except (json.JSONDecodeError, TypeError):
            pass
    return lead_fields if lead_fields else None
