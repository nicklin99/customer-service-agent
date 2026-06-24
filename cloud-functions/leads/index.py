"""
线索查询云函数 — 查询已收集的客户线索。
"""
import json
import logging

logger = logging.getLogger("leads-query")


async def main(context):
    """
    POST /leads
    从对话存储中查询线索数据。

    请求体:
    {
        "action": "list" | "get",
        "conversation_id": "xxx"  // get 时需要
    }
    """
    try:
        body = await context.request.json()
    except Exception:
        return {"status": "error", "message": "请求体必须是有效的 JSON"}

    action = body.get("action", "list")

    if action == "list":
        # 列出所有会话
        try:
            conversations = await context.agent.store.list_conversations()
            leads = []
            for conv in conversations:
                messages = await context.agent.store.get_messages(conv.get("id", ""))
                # 从消息中提取线索信息
                lead_info = _extract_lead_from_messages(messages)
                if lead_info:
                    leads.append({
                        "conversation_id": conv.get("id"),
                        "updated_at": conv.get("updated_at", ""),
                        "lead": lead_info,
                    })
            return {"status": "success", "leads": leads}
        except Exception as e:
            logger.error(f"Failed to list leads: {e}")
            return {"status": "error", "message": str(e)}

    elif action == "get":
        conversation_id = body.get("conversation_id", "")
        if not conversation_id:
            return {"status": "error", "message": "缺少 conversation_id"}

        try:
            messages = await context.agent.store.get_messages(conversation_id)
            lead_info = _extract_lead_from_messages(messages)
            return {
                "status": "success",
                "conversation_id": conversation_id,
                "lead": lead_info,
                "message_count": len(messages) if messages else 0,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    else:
        return {"status": "error", "message": f"Unknown action: {action}"}


def _extract_lead_from_messages(messages: list) -> dict | None:
    """从消息列表中提取线索信息（精确匹配 tool 消息中的 JSON）"""
    if not messages:
        return None

    lead_fields = {}
    for msg in messages:
        # 只处理 tool 角色的消息
        role = msg.get("role", msg.get("type", ""))
        if role not in ("tool", "function"):
            continue
        content = msg.get("content", "")
        if not isinstance(content, str):
            continue
        # 精确匹配：内容以 { 开头且包含完整线索标记
        if not (content.strip().startswith("{") and '"status"' in content and '"collected"' in content):
            continue
        try:
            parsed = json.loads(content)
            if parsed.get("status") == "complete" and parsed.get("collected"):
                lead_fields = parsed["collected"]
        except (json.JSONDecodeError, TypeError):
            pass

    return lead_fields if lead_fields else None


__all__ = ["main"]
