"""
用户画像查询云函数 — 获取指定会话的画像分析结果。
"""
import json
import logging

logger = logging.getLogger("profile-query")


async def handler(context):
    """POST /profile"""
    body = context.body or {}
    conversation_id = body.get("conversation_id", "")
    if not conversation_id:
        return {"status_code": 400, "body": {"error": "缺少 conversation_id"}}

    try:
        messages = await context.agent.store.get_messages(conversation_id)
        if not messages:
            return {
                "status_code": 200,
                "body": {"profile": None, "message": "该会话暂无消息记录"},
            }
        profile_data = _extract_profile_from_messages(messages)
        summary = _build_conversation_summary(messages)
        return {
            "status_code": 200,
            "body": {
                "profile": profile_data,
                "summary": summary,
                "message_count": len(messages),
            },
        }
    except Exception as e:
        return {"status_code": 500, "body": {"error": str(e)}}


def _extract_profile_from_messages(messages: list) -> dict | None:
    for msg in reversed(messages):
        role = msg.get("role", msg.get("type", ""))
        if role not in ("tool", "function", "ai", "assistant"):
            continue
        content = msg.get("content", "")
        if not isinstance(content, str) or "intent_level" not in content:
            continue
        try:
            text = content.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
            profile = json.loads(text)
            if "intent_level" in profile:
                return profile
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _build_conversation_summary(messages: list) -> dict:
    user_msgs, assistant_msgs = [], []
    for msg in messages:
        role = msg.get("role", msg.get("type", ""))
        content = msg.get("content", "")
        if role in ("user", "human"):
            user_msgs.append(str(content)[:200])
        elif role in ("assistant", "ai"):
            assistant_msgs.append(str(content)[:200])
    return {
        "total_rounds": len(user_msgs),
        "user_questions": user_msgs[-5:],
        "last_assistant_response": assistant_msgs[-1] if assistant_msgs else "",
    }
