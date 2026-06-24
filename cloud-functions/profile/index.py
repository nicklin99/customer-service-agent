"""
用户画像查询云函数 — 获取指定会话的画像分析结果。
"""
import json
import logging

logger = logging.getLogger("profile-query")


async def main(context):
    """
    POST /profile
    获取指定客户的画像分析结果。

    请求体:
    {
        "conversation_id": "xxx"
    }
    """
    try:
        body = await context.request.json()
    except Exception:
        return {"status": "error", "message": "请求体必须是有效的 JSON"}

    conversation_id = body.get("conversation_id", "")
    if not conversation_id:
        return {"status": "error", "message": "缺少 conversation_id"}

    try:
        messages = await context.agent.store.get_messages(conversation_id)
        if not messages:
            return {
                "status": "success",
                "conversation_id": conversation_id,
                "profile": None,
                "message": "该会话暂无消息记录",
            }

        # 从消息中提取画像分析结果
        profile_data = _extract_profile_from_messages(messages)

        # 构建对话摘要
        summary = _build_conversation_summary(messages)

        return {
            "status": "success",
            "conversation_id": conversation_id,
            "profile": profile_data,
            "summary": summary,
            "message_count": len(messages),
        }

    except Exception as e:
        logger.error(f"Failed to query profile: {e}")
        return {"status": "error", "message": str(e)}


def _extract_profile_from_messages(messages: list) -> dict | None:
    """从消息中提取画像分析 JSON（精确匹配 tool 消息）"""
    for msg in reversed(messages):
        role = msg.get("role", msg.get("type", ""))
        if role not in ("tool", "function", "ai", "assistant"):
            continue
        content = msg.get("content", "")
        if not isinstance(content, str):
            continue
        if "intent_level" not in content:
            continue
        try:
            text = content.strip()
            # 清理可能的 markdown 代码块
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
    """构建对话摘要"""
    user_msgs = []
    assistant_msgs = []

    for msg in messages:
        role = msg.get("role", msg.get("type", ""))
        content = msg.get("content", "")
        if role in ("user", "human"):
            user_msgs.append(str(content)[:200])
        elif role in ("assistant", "ai"):
            assistant_msgs.append(str(content)[:200])

    return {
        "total_rounds": len(user_msgs),
        "user_questions": user_msgs[-5:],  # 最近5轮
        "last_assistant_response": assistant_msgs[-1] if assistant_msgs else "",
    }


__all__ = ["main"]
