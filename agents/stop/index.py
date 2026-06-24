"""
中断当前正在运行的 Agent 执行。
"""
import logging

logger = logging.getLogger("customer-service-agent")


async def main(context):
    """POST /stop — 中断当前 conversation 的活跃 run"""
    conversation_id = getattr(context, "conversation_id", "")

    try:
        await context.utils.abort_active_run()
        logger.info(f"Agent run aborted for conversation: {conversation_id}")
        return {"status": "stopped", "conversation_id": conversation_id}
    except Exception as e:
        logger.error(f"Failed to stop agent: {e}")
        return {"status": "error", "message": str(e)}


__all__ = ["main"]
