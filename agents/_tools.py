"""
客户服务 Agent 工具集 — collect_lead · analyze_user_profile · save_to_crm
使用 OpenAI Agents SDK @function_tool 装饰器定义。
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from agents import RunContextWrapper, function_tool

logger = logging.getLogger("customer-service-agent")


@dataclass
class AgentToolContext:
    """工具运行时上下文"""
    store: Any
    llm_client: Any
    llm_model: str
    thread_id: str          # 当前会话 ID
    brand_name: str
    agent_name: str
    default_source: str


@function_tool
def collect_lead(
    name: str = "",
    phone: str = "",
    email: str = "",
    company: str = "",
    position: str = "",
    needs: str = "",
    source: str = "",
    website: str = "",
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
        website: 官方网址（选填）
    """
    lead = {
        "name": name.strip(),
        "phone": phone.strip(),
        "email": email.strip(),
        "company": company.strip(),
        "position": position.strip(),
        "needs": needs.strip(),
        "source": source.strip(),
        "website": website.strip(),
    }

    required = {"name": "姓名", "phone": "电话", "email": "邮箱", "needs": "需求描述"}
    missing = []
    for field, label in required.items():
        if not lead.get(field):
            missing.append({"field": field, "label": label})

    suggested = []
    suggested_fields = {"company": "公司名称", "position": "职位", "website": "官方网址"}
    for field, label in suggested_fields.items():
        if not lead.get(field):
            suggested.append({"field": field, "label": label})

    if missing:
        missing_labels = "、".join(item["label"] for item in missing)
        suggested_labels = "、".join(item["label"] for item in suggested) if suggested else "无"
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


@function_tool
async def analyze_user_profile(ctx: RunContextWrapper[AgentToolContext]) -> str:
    """
    分析用户画像。基于当前对话历史自动提炼客户特征、需求类型、意向程度等。
    调用此工具前确保已用 collect_lead 收集了基本信息。
    **无需传入任何参数**，工具自动读取对话记录。
    """
    try:
        messages = await ctx.context.store.get_messages(
            conversation_id=ctx.context.thread_id,
        )
        conversation_text = _format_messages(messages)
    except Exception as e:
        logger.warning(f"Failed to read conversation: {e}")
        conversation_text = "（无法读取对话历史）"

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
        response = await ctx.context.llm_client.chat.completions.create(
            model=ctx.context.llm_model,
            messages=[{"role": "user", "content": analysis_prompt}],
            temperature=0.3,
        )
        text = response.choices[0].message.content.strip()
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


@function_tool
async def save_to_crm(ctx: RunContextWrapper[AgentToolContext]) -> str:
    """
    将客户线索保存到 CRM 系统。
    仅在 collect_lead 返回 complete 且 analyze_user_profile 已完成后调用。
    **无需传入任何参数**，工具自动提取线索和画像数据。
    """
    crm_endpoint = ctx.context.store.env.get("CRM_API_ENDPOINT", "")
    crm_api_key = ctx.context.store.env.get("CRM_API_KEY", "")

    if not crm_endpoint:
        return json.dumps({
            "status": "error",
            "message": "CRM API 端点未配置。请联系管理员设置 CRM_API_ENDPOINT 环境变量。",
            "note": "线索信息已保留在对话记录中，不会丢失。",
        }, ensure_ascii=False)

    lead_data = {}
    profile_data = {}
    try:
        messages = await ctx.context.store.get_messages(
            conversation_id=ctx.context.thread_id,
        )
        for msg in (messages or []):
            content = msg.get("content", "") or ""
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
        logger.warning(f"Failed to extract from store: {e}")

    payload = {
        "lead": lead_data,
        "profile": profile_data,
        "source": f"{ctx.context.default_source}-{ctx.context.agent_name}",
        "thread_id": ctx.context.thread_id,
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


def _format_messages(messages: list) -> str:
    if not messages:
        return "暂无对话记录"
    lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        lines.append(f"[{role}]: {content}")
    return "\n".join(lines) if lines else "暂无对话记录"
