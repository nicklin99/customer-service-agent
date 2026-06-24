"""
中断当前正在运行的 Agent 执行。
"""
import logging

logger = logging.getLogger("customer-service-agent")


async def handler(context):
    """POST /stop — 中断当前 conversation 的活跃 run"""
    conversation_id = context.conversation_id

    try:
        await context.utils.abort_active_run()
        logger.info(f"Agent run aborted for conversation: {conversation_id}")
        return {"status_code": 200, "body": {"status": "stopped"}}
    except Exception as e:
        logger.error(f"Failed to stop agent: {e}")
        return {"status_code": 500, "body": {"error": str(e)}}
