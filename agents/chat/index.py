"""
智能客服 DeepAgent — 线索收集 · 用户画像 · CRM 同步
基于 EdgeOne Makers Agent Runtime + DeepAgents (LangGraph)

v2 修订：
- analyze_user_profile 自动从 checkpointer 拉取对话历史，LLM 无参调用
- save_to_crm 自动从 checkpointer 提取线索+画像，LLM 无参调用
- collect_lead 返回 suggested_labels
- _handle_action 直接用 checkpointer，不创建空 agent
"""

import json
import os
import logging
from typing import Any

import httpx
from deepagents import create_deep_agent
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger("customer-service-agent")

# ── 工具运行时状态（闭包捕获）──────────────────────────────
# 存储当前 agent 实例和 config，供工具读取 checkpointer
_agent_state: dict = {}


def _set_agent_state(agent: Any, config: dict) -> None:
    _agent_state["agent"] = agent
    _agent_state["config"] = config


# ── 模型配置 ──────────────────────────────────────────────

def _build_model(context: Any) -> ChatOpenAI:
    api_key = context.env.get("AI_GATEWAY_API_KEY", "")
    base_url = context.env.get(
        "AI_GATEWAY_BASE_URL", "https://ai-gateway.edgeone.link/v1"
    )
    model_name = context.env.get("AI_GATEWAY_MODEL", "@makers/deepseek-v4-flash")
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.7,
        streaming=True,
    )


# ── 系统提示词 ────────────────────────────────────────────

SYSTEM_PROMPT = """你是一位专业、热情、自然的智能客服代表，服务于「星帆科技」。你的核心职责是帮助客户解答问题，同时敏锐地识别潜在客户线索，并自然地收集关键信息。

## 你的身份
- 名字：小星
- 风格：专业但不死板，热情但不油腻，像一位经验丰富的客户顾问
- 语言：默认使用中文，如果客户使用英文则用英文回复

## 核心行为准则

### 1. 自然对话优先
- 先理解客户问题，给予有帮助的回应
- 不要一上来就索要联系方式，那会吓跑客户
- 在对话中自然过渡到线索收集

### 2. 线索识别与收集
当对话中出现以下信号时，你应该自然地收集线索信息：
- 客户询问价格、产品功能、方案对比
- 客户表示有采购意向或项目需求
- 客户询问合作流程、实施周期
- 客户透露了公司/团队规模
- 对话超过 3 轮且客户表达了明确需求

收集线索时使用 `collect_lead` 工具。该工具会验证信息完整性，不够的信息会返回缺失字段列表，你需要继续追问补齐。

### 3. 用户画像分析
当收集到足够信息后，使用 `analyze_user_profile` 工具分析客户画像。该工具**无需任何参数**，会自动读取对话历史进行分析。

### 4. CRM 同步
当线索收集完整且用户画像已分析后，使用 `save_to_crm` 工具将线索同步到 CRM 系统。该工具**无需任何参数**，会自动提取最近的线索和画像数据。同步成功后告知客户后续会有专人联系。

## 不要做的事情
- 不要编造你没有的产品信息
- 不要承诺具体价格（可以说"稍后顾问会给您详细报价"）
- 不要在没有线索信号时强行收集信息
- 不要一次性问太多问题

## 可用的产品线（供参考回答客户问题）
- 建站服务：企业官网、电商网站、小程序
- SEO 优化：搜索引擎优化、内容策略
- 品牌设计：VI 设计、品牌策略
- AI 解决方案：智能客服、数据分析、流程自动化
- 日常托管：网站运维、内容更新（400 元/月起）
"""


# ── 工具：线索收集 ────────────────────────────────────────

def collect_lead(
    name: str = "",
    phone: str = "",
    email: str = "",
    company: str = "",
    position: str = "",
    needs: str = "",
    source: str = "智能客服",
    budget: str = "",
    timeline: str = "",
) -> str:
    """
    收集客户线索信息。当你识别到潜在客户信号时调用此工具。
    传入你已知的信息，未知留空即可。工具会返回缺失字段列表。

    Args:
        name: 客户姓名
        phone: 电话号码
        email: 电子邮箱
        company: 公司名称
        position: 职位
        needs: 需求描述（越详细越好）
        source: 线索来源
        budget: 预算范围
        timeline: 预期时间线
    """
    lead = {
        "name": name.strip(),
        "phone": phone.strip(),
        "email": email.strip(),
        "company": company.strip(),
        "position": position.strip(),
        "needs": needs.strip(),
        "source": source.strip(),
        "budget": budget.strip(),
        "timeline": timeline.strip(),
    }

    required = {"name": "姓名", "phone": "电话", "email": "邮箱", "needs": "需求描述"}
    missing = []
    for field, label in required.items():
        if not lead.get(field):
            missing.append({"field": field, "label": label})

    suggested = []
    suggested_fields = {
        "company": "公司名称", "position": "职位",
        "budget": "预算范围", "timeline": "预期时间线",
    }
    for field, label in suggested_fields.items():
        if not lead.get(field):
            suggested.append({"field": field, "label": label})

    if missing:
        missing_labels = "、".join(item["label"] for item in missing)
        suggested_labels = (
            "、".join(item["label"] for item in suggested) if suggested else "无"
        )
        return json.dumps({
            "status": "incomplete",
            "message": f"线索信息不完整。还缺少必填信息：{missing_labels}",
            "missing_fields": missing,
            "suggested_fields": suggested,
            "suggested_labels": suggested_labels,
            "collected": lead,
        }, ensure_ascii=False)

    return json.dumps({
        "status": "complete",
        "message": "线索信息已收集完整，可以进行用户画像分析和 CRM 同步。",
        "collected": lead,
    }, ensure_ascii=False)


# ── 工具：用户画像分析（无参，自动读对话历史）─────────────

async def analyze_user_profile() -> str:
    """
    分析用户画像。基于当前对话历史自动提炼客户特征、需求类型、意向程度等。
    调用此工具前确保已用 collect_lead 收集了基本信息。
    **无需传入任何参数**，工具自动读取对话记录。
    """
    context = _agent_state.get("context")
    if not context:
        return json.dumps({"error": "Agent 状态丢失，请重试"}, ensure_ascii=False)

    model = _build_model(context)

    # 从 checkpointer 拉取对话历史
    conversation_text = await _read_conversation_text()

    analysis_prompt = f"""基于以下客服对话记录，分析客户画像。输出 JSON 格式。

对话记录：
{conversation_text}

请分析并返回以下 JSON（不要包含 markdown 代码块标记）：
{{
    "intent_level": "高/中/低",
    "customer_type": "个人创业者/中小企业/大型企业/不确定",
    "primary_need": "核心需求概括（一句话）",
    "pain_points": ["痛点1", "痛点2"],
    "recommended_services": ["推荐服务1", "推荐服务2"],
    "estimated_value": "预估客单价范围",
    "urgency": "紧急/一般/不急",
    "persona_summary": "一句话用户画像总结",
    "key_insights": ["洞察1", "洞察2"]
}}
"""
    try:
        response = await model.ainvoke([HumanMessage(content=analysis_prompt)])
        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
        return text
    except Exception as e:
        logger.error(f"Profile analysis failed: {e}")
        return json.dumps({
            "error": f"画像分析失败: {str(e)}",
            "intent_level": "未知",
            "primary_need": "待人工判断",
        }, ensure_ascii=False)


# ── 工具：CRM 同步（无参，自动提取线索和画像）─────────────

async def save_to_crm() -> str:
    """
    将客户线索保存到 CRM 系统。
    仅在 collect_lead 返回 complete 且 analyze_user_profile 已完成后调用。
    **无需传入任何参数**，工具自动提取最近的线索和画像数据。
    """
    context = _agent_state.get("context")
    if not context:
        return json.dumps({"error": "Agent 状态丢失，请重试"}, ensure_ascii=False)

    crm_endpoint = context.env.get(
        "CRM_API_ENDPOINT", os.environ.get("CRM_API_ENDPOINT", ""),
    )
    crm_api_key = context.env.get(
        "CRM_API_KEY", os.environ.get("CRM_API_KEY", ""),
    )

    if not crm_endpoint:
        return json.dumps({
            "status": "error",
            "message": "CRM API 端点未配置。请联系管理员设置 CRM_API_ENDPOINT 环境变量。",
            "note": "线索信息已保留在对话记录中，不会丢失。",
        }, ensure_ascii=False)

    # 从 checkpointer 提取最近的工具调用结果
    lead_data = {}
    profile_data = {}
    conversation_id = _agent_state.get("config", {}).get("configurable", {}).get("thread_id", "")

    try:
        agent = _agent_state.get("agent")
        if agent:
            state = await agent.aget_state(_agent_state["config"])
            if state and state.values:
                for msg in reversed(state.values.get("messages", [])):
                    content = getattr(msg, "content", "")
                    if isinstance(content, str):
                        if not lead_data and '"collected"' in content and '"status": "complete"' in content:
                            try:
                                parsed = json.loads(content)
                                lead_data = parsed.get("collected", {})
                            except (json.JSONDecodeError, TypeError):
                                pass
                        if not profile_data and '"intent_level"' in content:
                            try:
                                parsed = json.loads(content)
                                if "intent_level" in parsed:
                                    profile_data = parsed
                            except (json.JSONDecodeError, TypeError):
                                pass
                    if lead_data and profile_data:
                        break
    except Exception as e:
        logger.warning(f"Failed to extract lead from state: {e}")

    payload = {
        "lead": lead_data,
        "profile": profile_data,
        "source": "智能客服-小星",
        "conversation_id": conversation_id,
    }

    headers = {"Content-Type": "application/json"}
    if crm_api_key:
        headers["Authorization"] = f"Bearer {crm_api_key}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(crm_endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            result = resp.json()
        return json.dumps({
            "status": "success",
            "message": "✅ 客户线索已成功同步到 CRM 系统！我们的顾问会在 1 个工作日内联系您。",
            "crm_response": result,
        }, ensure_ascii=False)
    except httpx.HTTPStatusError as e:
        logger.error(f"CRM sync HTTP error: {e.response.status_code}")
        return json.dumps({
            "status": "error",
            "message": f"CRM 同步失败（HTTP {e.response.status_code}）。线索已保留，将稍后重试。",
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"CRM sync failed: {e}")
        return json.dumps({
            "status": "error",
            "message": f"CRM 同步失败: {str(e)}。线索已保留在对话记录中。",
        }, ensure_ascii=False)


# ── 辅助：从 checkpointer 读取对话历史 ────────────────────

async def _read_conversation_text() -> str:
    """从 checkpointer 读取当前会话的完整对话历史"""
    try:
        agent = _agent_state.get("agent")
        config = _agent_state.get("config", {})
        if agent:
            state = await agent.aget_state(config)
            if state and state.values:
                lines = []
                for msg in state.values.get("messages", []):
                    role = getattr(msg, "type", "unknown")
                    content = getattr(msg, "content", "")
                    lines.append(f"[{role}]: {content}")
                return "\n".join(lines) if lines else "暂无对话记录"
    except Exception as e:
        logger.warning(f"Failed to read conversation: {e}")
    return "（无法读取对话历史）"


# ── 内部：非流式 Action 处理 ──────────────────────────────


async def _handle_action(context: Any, action: str) -> dict:
    """处理 history / delete，直接操作 checkpointer"""
    conversation_id = getattr(context, "conversation_id", "default")
    checkpointer = context.store.langgraph_checkpointer()
    config = {"configurable": {"thread_id": conversation_id}}

    if action == "history":
        try:
            checkpoint = await checkpointer.aget(config)
            messages = []
            if checkpoint and "channel_values" in checkpoint:
                for msg in checkpoint["channel_values"].get("messages", []):
                    messages.append({
                        "role": getattr(msg, "type", "unknown"),
                        "content": getattr(msg, "content", ""),
                    })
            return {"messages": messages}
        except Exception:
            return {"messages": []}

    elif action == "delete":
        try:
            await context.store.delete(conversation_id)
            return {"status": "deleted"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {"error": f"Unknown action: {action}"}


# ── 内部：SSE 流式聊天生成器 ──────────────────────────────


async def _stream_chat(context: Any, body: dict):
    """异步生成器：逐 token 流式输出 DeepAgent 响应"""
    user_message = body.get("message", "")
    conversation_id = getattr(context, "conversation_id", "default")
    model = _build_model(context)
    config = {"configurable": {"thread_id": conversation_id}}

    agent = create_deep_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[collect_lead, analyze_user_profile, save_to_crm],
        checkpointer=context.store.langgraph_checkpointer(),
    )

    # 存储 agent 引用供工具读取状态
    _set_agent_state(agent, config)
    _agent_state["context"] = context

    try:
        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=user_message)]},
            config=config,
            version="v2",
        ):
            kind = event.get("event")

            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if hasattr(chunk, "content") and chunk.content:
                    yield {"type": "text_delta", "content": chunk.content}

            elif kind == "on_tool_start":
                yield {
                    "type": "tool_called",
                    "tool_name": event.get("name", "unknown"),
                    "status": "started",
                }

            elif kind == "on_tool_end":
                output = event.get("data", {}).get("output", "")
                yield {
                    "type": "tool_result",
                    "tool_name": event.get("name", "unknown"),
                    "status": "completed",
                    "output": str(output)[:500],
                }

        yield {"type": "done", "conversation_id": conversation_id}

    except Exception as e:
        logger.error(f"Agent stream error: {e}")
        yield {"type": "error", "message": f"处理请求时出错: {str(e)}"}
    finally:
        _agent_state.clear()


# ── 主 Handler ────────────────────────────────────────────


async def main(context: Any) -> Any:
    """
    EdgeOne Makers Agent 主入口。
    - history / delete → 返回 dict（JSON 响应）
    - chat → 返回 async generator（SSE 流式响应）
    """
    body = await context.request.json()
    action = body.get("action", "chat")

    if action in ("history", "delete"):
        return await _handle_action(context, action)

    return _stream_chat(context, body)


__all__ = ["main"]
