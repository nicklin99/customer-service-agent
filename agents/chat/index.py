"""
Agent handler — EdgeOne Makers (OpenAI Agents SDK)

File path agents/chat/index.py → auto-mapped to **POST /chat**.

SSE protocol (frontend parses `data:` lines only):
  data: {"type":"text_delta","content":"..."}
  data: {"type":"tool_called","tool_name":"...","status":"started"}
  data: {"type":"tool_result","tool_name":"...","status":"completed","output":"..."}
  data: {"type":"done","thread_id":"..."}
  data: {"type":"error","message":"..."}
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator

from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent
from agents import Agent, OpenAIChatCompletionsModel, Runner, set_tracing_disabled

from .._tools import AgentToolContext, collect_lead, analyze_user_profile, save_to_crm

logger = logging.getLogger("customer-service-agent")

set_tracing_disabled(disabled=True)


def _build_system_prompt(brand_name: str, agent_name: str) -> str:
    return f"""你是一位专业、热情、自然的智能客服代表，服务于「{brand_name}」。你的核心职责是帮助客户解答问题，同时敏锐地识别潜在客户线索，并自然地收集关键信息。

## 你的身份
- 名字：{agent_name}
- 风格：专业但不死板，热情但不油腻，像一位经验丰富的客户顾问
- 语言：默认使用中文，如果客户使用英文则用英文回复

## 核心行为准则

### 1. 自然对话优先
- 先理解客户问题，给予有帮助的回应
- 不要一上来就索要联系方式，那会吓跑客户
- 在对话中自然过渡到线索收集

### 2. 线索识别与主动收集
当客户表达需求时，应立即识别为新线索，主动自然地收集线索信息：
- 客户询问价格、产品功能、方案对比
- 客户表示有采购意向或项目需求
- 客户询问合作流程、实施周期
- 客户透露了公司/团队规模
- 对话超过 3 轮且客户表达了明确需求

收集线索时使用 `collect_lead` 工具。该工具会验证信息完整性，不够的信息会返回缺失字段列表，你需要继续追问补齐。

线索字段包括：姓名、电话、邮箱、公司名称、职位、需求描述、官方网址（选填）、来源。

### 3. 用户画像自动补齐
线索收集完整后，自动使用 `analyze_user_profile` 工具分析客户画像，根据已收集线索自动补齐基础画像信息。该工具**无需任何参数**，会自动读取对话记录进行分析。

### 4. CRM 同步
当线索收集完整且用户画像已分析后，如果 CRM 工具可用，使用 `save_to_crm` 工具将客户线索、用户画像和对话 ID 提交到 CRM 系统。该工具**无需任何参数**，会自动提取最近的线索和画像数据。同步成功后告知客户后续会有专人联系。

## 不要做的事情
- 不要编造你没有的产品信息
- 不要承诺具体价格（可以说"稍后顾问会给您详细报价"）
- 不要在没有线索信号时强行收集信息
- 不要一次性问太多问题

## 关于服务介绍（供参考回答客户问题）
{brand_name} 致力于开发"LLM-原生"GEO 技术，通过解构大模型底层逻辑，实现品牌与全球用户需求的精准匹配。依托多模态内容生成与跨平台语义优化，提升品牌在 AI 问答引擎中的检索权重与可见性，驱动销量持续增长。"""


def sse_data(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _event_stream(
    message: str,
    agent_ctx: AgentToolContext,
    session,
    cancel_signal: asyncio.Event | None = None,
) -> AsyncGenerator[str, None]:
    agent = Agent(
        name=agent_ctx.agent_name,
        instructions=_build_system_prompt(agent_ctx.brand_name, agent_ctx.agent_name),
        tools=[collect_lead, analyze_user_profile, save_to_crm],
        model=OpenAIChatCompletionsModel(
            model=agent_ctx.llm_model,
            openai_client=agent_ctx.llm_client,
        ),
    )

    result = Runner.run_streamed(agent, input=message, context=agent_ctx, session=session)

    async for event in result.stream_events():
        if cancel_signal and cancel_signal.is_set():
            break

        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            yield sse_data({"type": "text_delta", "content": event.data.delta})

        elif event.type == "run_item_stream_event":
            if event.name == "tool_called":
                tool_name = (
                    getattr(event.item, "name", None)
                    or getattr(getattr(event.item, "raw_item", None), "name", None)
                )
                if tool_name:
                    yield sse_data({"type": "tool_called", "tool_name": tool_name, "status": "started"})

            elif event.name == "tool_output":
                tool_name = (
                    getattr(event.item, "name", None)
                    or getattr(getattr(event.item, "raw_item", None), "name", None)
                )
                output = getattr(event.item, "output", "") or ""
                yield sse_data({
                    "type": "tool_result",
                    "tool_name": tool_name or "unknown",
                    "status": "completed",
                    "output": str(output)[:500],
                })


async def handler(context: Any):
    request = context.request
    body = request.body or {}
    action = body.get("action", "chat")
    message = body.get("message", "")
    thread_id = context.conversation_id

    api_key = (context.env.get("AI_GATEWAY_API_KEY") or "").strip()
    base_url = (context.env.get("AI_GATEWAY_BASE_URL") or "").strip()
    model_name = context.env.get("AI_GATEWAY_MODEL") or "@makers/deepseek-v4-flash"
    brand_name = context.env.get("BRAND_NAME", "Trendee")
    agent_name = context.env.get("AGENT_NAME", "trendee")
    default_source = context.env.get("DEFAULT_SOURCE", "trendee-智能客服")

    if action == "history":
        messages = []
        try:
            raw = await context.store.get_messages(conversation_id=thread_id)
            for msg in raw or []:
                if msg.get("metadata", {}).get("agent_sdk_session"):
                    continue
                messages.append({"role": msg.get("role", "unknown"), "content": msg.get("content", "")})
        except Exception:
            pass
        try:
            session = context.store.openai_session(thread_id)
            items = await session.get_items()
            for item in items or []:
                messages.append({"role": getattr(item, "role", "assistant"), "content": getattr(item, "content", "")})
        except Exception:
            pass
        return {"status_code": 200, "body": {"messages": messages}}

    if action == "delete":
        try:
            await context.store.delete(thread_id)
            return {"status_code": 200, "body": {"deleted": True}}
        except Exception as e:
            return {"status_code": 500, "body": {"error": str(e)}}

    if not api_key or not base_url:
        return {"status_code": 500, "body": {"error": "Missing AI_GATEWAY_API_KEY or AI_GATEWAY_BASE_URL"}}

    llm_client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    agent_ctx = AgentToolContext(
        store=context.store,
        llm_client=llm_client,
        llm_model=model_name,
        thread_id=thread_id,
        brand_name=brand_name,
        agent_name=agent_name,
        default_source=default_source,
    )

    if not message:
        return {"status_code": 400, "body": {"error": "'message' is required"}}

    raw_user_id = body.get("userId") or body.get("user_id") or ""
    user_id = str(raw_user_id).strip() or None
    if user_id and thread_id:
        try:
            existing = await context.store.get_messages(conversation_id=thread_id, limit=1)
            if not existing:
                await context.store.append_message(
                    conversation_id=thread_id, role="user", content=message, user_id=user_id,
                )
        except Exception as e:
            logger.warning(f"User-index write failed (non-fatal): {e}")

    session = context.store.openai_session(thread_id) if thread_id else None
    cancel_signal = getattr(request, "signal", None)

    async def _chat_stream():
        stopped = False
        try:
            async for frame in _event_stream(message, agent_ctx, session, cancel_signal):
                if cancel_signal and cancel_signal.is_set():
                    stopped = True
                    break
                yield frame
        except asyncio.CancelledError:
            stopped = True
            logger.log(logging.INFO, "[stream] cancelled")
        except Exception as e:
            logger.error(f"[stream] error: {type(e).__name__}: {e}")
            detail: Any = str(e)
            status: Any = None
            response = getattr(e, "response", None)
            if response is not None:
                status = getattr(response, "status_code", None)
                try:
                    body_text = response.text if hasattr(response, "text") else None
                    if callable(body_text):
                        body_text = body_text()
                    if body_text:
                        try:
                            detail = json.loads(body_text)
                        except (json.JSONDecodeError, ValueError, TypeError):
                            detail = body_text
                except Exception:
                    pass
            body_attr = getattr(e, "body", None)
            if body_attr and detail == str(e):
                detail = body_attr
            yield sse_data({"type": "error", "message": str(e), "errorType": type(e).__name__, "status": status, "detail": detail})
        finally:
            yield sse_data({"type": "done", "thread_id": thread_id})

    return context.utils.stream_sse(_chat_stream())
