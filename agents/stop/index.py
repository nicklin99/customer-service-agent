"""
中断当前正在运行的 Agent 执行。
POST /stop — EdgeOne Makers (OpenAI Agents SDK)
"""
import logging

logger = logging.getLogger("customer-service-agent")


async def handler(context):
    """POST /stop — 中断当前 thread 的活跃 run"""
    body = context.request.body or {}
    thread_id = body.get("thread_id") or context.conversation_id

    if not thread_id:
        return {
            "status_code": 400,
            "body": {"status": "error", "message": "thread_id is required"},
        }

    try:
        result = context.utils.abort_active_run()
        logger.info(f"Agent run aborted for thread: {thread_id}")
        return {
            "status_code": 200,
            "body": {
                "status": "stopped",
                "threadId": thread_id,
                "aborted": True,
            },
        }
    except Exception as e:
        logger.error(f"Failed to stop agent: {e}")
        return {"status_code": 500, "body": {"error": str(e)}}
