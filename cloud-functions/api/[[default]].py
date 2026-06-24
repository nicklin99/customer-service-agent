"""
业务 API 云函数 — FastAPI (profile / leads / crm-sync / settings / wecom-kf-bridge)
"""
import hashlib
import json
import logging
import os
import time
import xml.etree.ElementTree as ET
from base64 import b64decode, b64encode

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from edgeone_functions import agent

logger = logging.getLogger("business-api")
app = FastAPI()


# =====================================================================
#  WeCom 环境变量与 Token 缓存
# =====================================================================

ENV_WECOM_CORP_ID = "WECOM_CORP_ID"
ENV_WECOM_KF_SECRET = "WECOM_KF_SECRET"
ENV_WECOM_APP_SECRET = "WECOM_APP_SECRET"
ENV_WECOM_TOKEN = "WECOM_TOKEN"
ENV_WECOM_ENCODING_AES_KEY = "WECOM_ENCODING_AES_KEY"

_token_cache: dict = {"token": "", "expires_at": 0}


# =====================================================================
#  WeCom API 工具
# =====================================================================

async def _get_access_token() -> str:
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["token"]
    corp_id = os.environ.get(ENV_WECOM_CORP_ID, "")
    secret = os.environ.get(ENV_WECOM_KF_SECRET, "")
    if not corp_id or not secret:
        raise ValueError("缺少 WECOM_CORP_ID 或 WECOM_KF_SECRET 配置")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
            params={"corpid": corp_id, "corpsecret": secret},
        )
        data = resp.json()
        if data.get("errcode"):
            raise RuntimeError(f"获取 access_token 失败: {data}")
        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = now + data["expires_in"]
        return data["access_token"]


async def _get_app_access_token() -> str:
    now = time.time()
    cached = _token_cache.get("app_token")
    if cached and cached["expires_at"] > now + 60:
        return cached["token"]
    corp_id = os.environ.get(ENV_WECOM_CORP_ID, "")
    secret = os.environ.get(ENV_WECOM_APP_SECRET, "") or os.environ.get(ENV_WECOM_KF_SECRET, "")
    if not corp_id or not secret:
        raise ValueError("缺少 WECOM_CORP_ID 和 WECOM_APP_SECRET")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
            params={"corpid": corp_id, "corpsecret": secret},
        )
        data = resp.json()
        if data.get("errcode"):
            raise RuntimeError(f"获取 app access_token 失败: {data}")
        _token_cache["app_token"] = {
            "token": data["access_token"],
            "expires_at": now + data["expires_in"],
        }
        return data["access_token"]


def _decrypt(encoding_aes_key: str, raw: str) -> str:
    from Crypto.Cipher import AES
    aes_key = b64decode(encoding_aes_key + "=")
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_key[:16])
    plain = cipher.decrypt(b64decode(raw))
    pad_len = plain[-1]
    plain = plain[:-pad_len]
    msg_len = int.from_bytes(plain[16:20], "big")
    return plain[20 : 20 + msg_len].decode("utf-8")


def _encrypt(encoding_aes_key: str, plain_text: str, corpid: str) -> str:
    from Crypto.Cipher import AES
    aes_key = b64decode(encoding_aes_key + "=")
    raw = (
        os.urandom(16)
        + len(plain_text).to_bytes(4, "big")
        + plain_text.encode()
        + corpid.encode()
    )
    block_size = 32
    pad_len = block_size - (len(raw) % block_size)
    raw += bytes([pad_len] * pad_len)
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_key[:16])
    return b64encode(cipher.encrypt(raw)).decode()


def _build_callback_xml(token: str, aes_key: str, corpid: str, reply: str, timestamp: str, nonce: str) -> str:
    encrypted = _encrypt(aes_key, reply, corpid)
    raw = f"{timestamp}\n{nonce}\n{encrypted}"
    signature = hashlib.sha1("".join(sorted([token, timestamp, nonce, encrypted])).encode()).hexdigest()
    return f"""<xml>
<Encrypt><![CDATA[{encrypted}]]></Encrypt>
<MsgSignature><![CDATA[{signature}]]></MsgSignature>
<TimeStamp>{timestamp}</TimeStamp>
<Nonce><![CDATA[{nonce}]]></Nonce>
</xml>"""


async def _sync_msg(token: str, open_kfid: str) -> list[dict]:
    access_token = await _get_access_token()
    all_msgs: list[dict] = []
    cursor_key = f"wecom_kf_cursor:{open_kfid}"
    cursor = ""
    try:
        stored = agent.store.get(cursor_key)
        cursor = stored or ""
    except Exception:
        pass
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            req_body = {"token": token, "open_kfid": open_kfid, "limit": 100}
            if cursor:
                req_body["cursor"] = cursor
            resp = await client.post(
                "https://qyapi.weixin.qq.com/cgi-bin/kf/sync_msg",
                params={"access_token": access_token},
                json=req_body,
            )
            data = resp.json()
            if data.get("errcode"):
                logger.error("sync_msg 失败: %s", data)
                break
            msgs = data.get("msg_list", [])
            all_msgs.extend(msgs)
            next_cursor = data.get("next_cursor", "")
            if not data.get("has_more"):
                if msgs and next_cursor:
                    try:
                        agent.store.set(cursor_key, next_cursor)
                    except Exception as e:
                        logger.warning("保存 cursor 失败: %s", e)
                break
            cursor = next_cursor
    return all_msgs


async def _send_kf_msg(external_userid: str, open_kfid: str, content: str) -> bool:
    access_token = await _get_access_token()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://qyapi.weixin.qq.com/cgi-bin/kf/send_msg",
            params={"access_token": access_token},
            json={
                "touser": external_userid,
                "open_kfid": open_kfid,
                "msgtype": "text",
                "text": {"content": content},
            },
        )
        data = resp.json()
        if data.get("errcode"):
            logger.error("send_msg 失败: %s", data)
            return False
        return True


async def _create_contact_way(users: list[str], state: str, skip_verify: bool = True) -> dict:
    access_token = await _get_app_access_token()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://qyapi.weixin.qq.com/cgi-bin/externalcontact/add_contact_way",
            params={"access_token": access_token},
            json={"type": 1, "scene": 2, "state": state, "user": users, "skip_verify": skip_verify},
        )
        return resp.json()


async def _send_welcome_msg(welcome_code: str, content: str) -> bool:
    access_token = await _get_app_access_token()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://qyapi.weixin.qq.com/cgi-bin/externalcontact/send_welcome_msg",
            params={"access_token": access_token},
            json={"welcome_code": welcome_code, "text": {"content": content}},
        )
        data = resp.json()
        if data.get("errcode"):
            logger.error("send_welcome_msg 失败: %s", data)
            return False
        return True


async def _get_channel_state(external_userid: str) -> str:
    try:
        return agent.store.get(f"wecom_kf_channel:{external_userid}") or ""
    except Exception:
        return ""


# =====================================================================
#  WeCom AI 对话
# =====================================================================

AGENT_SYSTEM_PROMPT = """你是一位专业、热情、自然的智能客服代表。你的核心职责是帮助客户解答问题，同时敏锐地识别潜在客户线索，并自然地收集关键信息。

## 你的身份
- 风格：专业但不死板，热情但不油腻，像一位经验丰富的客户顾问
- 语言：默认使用中文，如果客户使用英文则用英文回复

## 核心行为准则

### 1. 自然对话优先
- 先理解客户问题，给予有帮助的回应
- 不要一上来就索要联系方式，那会吓跑客户

### 2. 线索识别与主动收集
当客户表达需求时，应立即识别为新线索，主动自然地收集线索信息：
- 客户询问价格、产品功能、方案对比
- 客户表示有采购意向或项目需求
- 客户询问合作流程、实施周期
- 客户透露了公司/团队规模
- 对话超过 3 轮且客户表达了明确需求

线索字段包括：姓名、电话、邮箱、公司名称、职位、需求描述、官方网址（选填）。预算和时间线不再收集。

### 3. 用户画像
当收集到姓名、电话、邮箱、需求描述这些基本信息后，你应该给出一个简要的用户画像分析（客户类型、核心需求、意向程度）。

### 4. CRM 同步
收集到足够线索后，应通过 CRM API 提交客户线索信息。

## 不要做的事情
- 不要编造你没有的产品信息
- 不要承诺具体价格（可以说稍后顾问会给您详细报价）
- 不要在没有线索信号时强行收集信息
- 不要一次性问太多问题"""


def _build_conversation_messages(history: list[dict]) -> list[dict]:
    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    for item in history:
        role = "user" if item.get("role") == "customer" else "assistant"
        messages.append({"role": role, "content": item.get("content", "")})
    return messages


async def _load_history(external_userid: str) -> list[dict]:
    store_key = f"wecom_kf:{external_userid}"
    try:
        stored = agent.store.get(store_key)
        return json.loads(stored) if stored else []
    except Exception:
        return []


async def _save_to_history(external_userid: str, role: str, content: str) -> None:
    history = await _load_history(external_userid)
    history.append({"role": role, "content": content, "time": int(time.time())})
    try:
        agent.store.set(
            f"wecom_kf:{external_userid}",
            json.dumps(history[-40:], ensure_ascii=False),
        )
    except Exception as e:
        logger.warning("保存对话历史失败: %s", e)


async def _call_ai_agent(external_userid: str, user_msg: str) -> str:
    history = await _load_history(external_userid)
    history.append({"role": "customer", "content": user_msg, "time": int(time.time())})
    api_key = (os.environ.get("AI_GATEWAY_API_KEY") or "").strip()
    base_url = (os.environ.get("AI_GATEWAY_BASE_URL") or "").strip()
    model_name = os.environ.get("AI_GATEWAY_MODEL") or "@makers/deepseek-v4-flash"
    if not api_key or not base_url:
        reply = "系统暂时无法回复，请稍后再试。"
    else:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=_build_conversation_messages(history),
                temperature=0.7,
                max_tokens=1024,
            )
            reply = resp.choices[0].message.content or ""
        except Exception as e:
            logger.error("AI 调用失败: %s", e)
            reply = "抱歉，我暂时遇到了一些问题，请稍后再试。"
    await _save_to_history(external_userid, "ai", reply)
    return reply


# =====================================================================
#  WeCom Routes
# =====================================================================

@app.get("/wecom-kf-bridge")
async def verify_callback(
    msg_signature: str = Query(""),
    timestamp: str = Query(""),
    nonce: str = Query(""),
    echostr: str = Query(""),
):
    token = os.environ.get(ENV_WECOM_TOKEN, "")
    aes_key = os.environ.get(ENV_WECOM_ENCODING_AES_KEY, "")
    if not token or not aes_key:
        return PlainTextResponse("回调配置未完成: 缺少 WECOM_TOKEN 或 WECOM_ENCODING_AES_KEY", status_code=500)
    sig = hashlib.sha1("".join(sorted([token, timestamp, nonce, echostr])).encode()).hexdigest()
    if sig != msg_signature:
        return PlainTextResponse("verify fail", status_code=403)
    try:
        decrypted = _decrypt(aes_key, echostr)
    except Exception as e:
        logger.error("解密 echostr 失败: %s", e)
        return PlainTextResponse("decrypt fail", status_code=500)
    return PlainTextResponse(decrypted)


@app.post("/wecom-kf-bridge")
async def receive_callback(request: Request):
    token = os.environ.get(ENV_WECOM_TOKEN, "")
    aes_key = os.environ.get(ENV_WECOM_ENCODING_AES_KEY, "")
    content_type = request.headers.get("content-type", "").lower()

    if "json" in content_type:
        body = await request.json()
        action = body.get("action", "")
        if action == "create_qr_code":
            users = body.get("users", [])
            state = body.get("state", "")
            if not users or not state:
                return JSONResponse({"error": "缺少 users 或 state"}, status_code=400)
            return await _create_contact_way(users, state)
        return JSONResponse({"error": "unknown action"}, status_code=400)

    raw_xml = await request.body()
    xml_str = raw_xml.decode("utf-8")
    if not token or not aes_key:
        return PlainTextResponse("回调配置未完成", status_code=500)
    try:
        root = ET.fromstring(xml_str)
        encrypted = root.findtext("Encrypt", "")
        msg_signature = root.findtext("MsgSignature", "")
        timestamp = root.findtext("TimeStamp", "")
        nonce = root.findtext("Nonce", "")
    except ET.ParseError:
        return PlainTextResponse("invalid xml", status_code=400)
    sig = hashlib.sha1("".join(sorted([token, timestamp, nonce, encrypted])).encode()).hexdigest()
    if sig != msg_signature:
        return PlainTextResponse("signature mismatch", status_code=403)
    try:
        decrypted_xml = _decrypt(aes_key, encrypted)
    except Exception as e:
        logger.error("解密失败: %s", e)
        return PlainTextResponse("decrypt fail", status_code=500)
    event_root = ET.fromstring(decrypted_xml)
    event_type = event_root.findtext("Event", "")

    # 客户联系事件
    if event_type == "change_external_contact":
        change_type = event_root.findtext("ChangeType", "")
        if change_type == "add_external_contact":
            external_userid = event_root.findtext("ExternalUserID", "")
            state = event_root.findtext("State", "")
            welcome_code = event_root.findtext("WelcomeCode", "")
            logger.info("新客户添加: %s, state=%s", external_userid, state)
            if external_userid and state:
                try:
                    agent.store.set(f"wecom_kf_channel:{external_userid}", state)
                except Exception as e:
                    logger.warning("保存渠道 state 失败: %s", e)
            if welcome_code:
                await _send_welcome_msg(welcome_code, "您好！我是智能客服助手，很高兴为您服务。请问有什么可以帮您的吗？")
        return PlainTextResponse("success")

    # 微信客服 KF 事件
    if event_type != "kf_msg_or_event":
        return PlainTextResponse("success")
    event_token = event_root.findtext("Token", "")
    open_kfid = event_root.findtext("OpenKfId", "")
    if not event_token or not open_kfid:
        return PlainTextResponse("success")

    msg_list = await _sync_msg(event_token, open_kfid)
    logger.info("拉取到 %d 条消息/事件", len(msg_list))

    processed_key = f"wecom_kf_processed:{open_kfid}"
    try:
        stored = agent.store.get(processed_key)
        processed_ids: set[str] = set(json.loads(stored)) if stored else set()
    except Exception:
        processed_ids = set()

    user_texts: dict[str, list[str]] = {}
    user_entered: set[str] = set()
    batch_msgids: list[str] = []

    for msg in msg_list:
        uid = msg.get("external_userid", "")
        msgid = msg.get("msgid", "")
        if not uid or not msgid or msgid in processed_ids:
            continue
        batch_msgids.append(msgid)
        origin = msg.get("origin", 0)
        msgtype = msg.get("msgtype", "")
        if origin == 4 and msgtype == "event":
            et = msg.get("event", {}).get("event_type", "")
            if et == "enter_session":
                user_entered.add(uid)
        if origin == 3 and msgtype == "text":
            text_content = msg.get("text", {}).get("content", "")
            if text_content:
                user_texts.setdefault(uid, []).append(text_content)

    all_success = True
    for uid, texts in user_texts.items():
        is_new = uid in user_entered
        if is_new:
            ok = await _send_kf_msg(uid, open_kfid, "您好！我是智能客服助手，很高兴为您服务。请问有什么可以帮您的吗？")
            if ok:
                await _save_to_history(uid, "ai", "您好！我是智能客服助手，很高兴为您服务。请问有什么可以帮您的吗？")
            else:
                all_success = False
                continue
        for t in texts[:-1]:
            await _save_to_history(uid, "customer", t)
        reply = await _call_ai_agent(uid, texts[-1])
        ok = await _send_kf_msg(uid, open_kfid, reply)
        if not ok:
            logger.error("send_msg 失败, 用户 %s 未收到回复", uid)
            all_success = False

    if batch_msgids and all_success:
        processed_ids.update(batch_msgids)
        trimmed = list(processed_ids)[-500:]
        try:
            agent.store.set(processed_key, json.dumps(trimmed))
        except Exception as e:
            logger.warning("保存 processed_ids 失败: %s", e)

    return PlainTextResponse("success")


# =====================================================================
#  Profile
# =====================================================================

@app.post("/profile")
async def get_profile(request: Request):
    body = await request.json()
    conversation_id = body.get("conversation_id", "")
    if not conversation_id:
        return JSONResponse({"error": "缺少 conversation_id"}, status_code=400)
    try:
        messages = agent.store.get_messages(conversation_id)
        if not messages:
            return {"profile": None, "message": "该会话暂无消息记录"}
        return {
            "profile": _extract_profile_from_messages(messages),
            "summary": _build_conversation_summary(messages),
            "message_count": len(messages),
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


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


# =====================================================================
#  Leads
# =====================================================================

@app.post("/leads")
async def get_leads(request: Request):
    body = await request.json()
    action = body.get("action", "list")
    if action == "list":
        try:
            conversations = agent.store.list_conversations()
            leads = []
            for conv in conversations:
                messages = agent.store.get_messages(conv.get("id", ""))
                lead_info = _extract_lead_from_messages(messages)
                if lead_info:
                    leads.append({
                        "conversation_id": conv.get("id"),
                        "updated_at": conv.get("updated_at", ""),
                        "lead": lead_info,
                    })
            return {"leads": leads}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    elif action == "get":
        conversation_id = body.get("conversation_id", "")
        if not conversation_id:
            return JSONResponse({"error": "缺少 conversation_id"}, status_code=400)
        try:
            messages = agent.store.get_messages(conversation_id)
            lead_info = _extract_lead_from_messages(messages)
            return {
                "conversation_id": conversation_id,
                "lead": lead_info,
                "message_count": len(messages) if messages else 0,
            }
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    return JSONResponse({"error": f"Unknown action: {action}"}, status_code=400)


def _extract_lead_from_messages(messages: list) -> dict | None:
    if not messages:
        return None
    for msg in reversed(messages):
        content = msg.get("content", "")
        if not isinstance(content, str):
            continue
        if '"status"' not in content or '"collected"' not in content:
            continue
        try:
            parsed = json.loads(content)
            if parsed.get("status") == "complete" and parsed.get("collected"):
                return parsed["collected"]
        except (json.JSONDecodeError, TypeError):
            continue
    return None


# =====================================================================
#  CRM Sync
# =====================================================================

@app.post("/crm-sync")
async def sync_crm(request: Request):
    body = await request.json()
    crm_endpoint = os.environ.get("CRM_API_ENDPOINT", "")
    crm_api_key = os.environ.get("CRM_API_KEY", "")
    if not crm_endpoint:
        return JSONResponse({"error": "CRM_API_ENDPOINT 未配置"}, status_code=500)
    lead = body.get("lead", {})
    default_source = os.environ.get("DEFAULT_SOURCE", "trendee-智能客服")
    missing = [f for f in ["name", "phone", "email"] if not lead.get(f)]
    if missing:
        return JSONResponse({"error": f"缺少字段: {', '.join(missing)}"}, status_code=400)
    payload = {
        "lead": {k: lead.get(k, "") for k in ("name", "phone", "email", "company", "position", "needs", "website")},
        "profile": body.get("profile", {}),
        "source": body.get("source", default_source),
        "conversation_id": body.get("conversation_id", ""),
    }
    headers = {"Content-Type": "application/json", "User-Agent": "EdgeOne-Makers-CRM-Sync/1.0"}
    if crm_api_key:
        headers["Authorization"] = f"Bearer {crm_api_key}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(crm_endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            return {"status": "success", "crm_response": resp.json()}
    except httpx.HTTPStatusError as e:
        logger.error(f"CRM API error: {e.response.status_code}")
        return JSONResponse({"error": str(e)}, status_code=e.response.status_code)
    except Exception as e:
        logger.error(f"CRM sync failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# =====================================================================
#  Settings
# =====================================================================

@app.get("/settings")
async def get_settings():
    return {
        "brandName": os.environ.get("BRAND_NAME", "trendee"),
        "brandTitle": os.environ.get("BRAND_TITLE", "trendee 智能客服"),
        "agentName": os.environ.get("AGENT_NAME", "trendee"),
        "logoText": os.environ.get("LOGO_TEXT", "T"),
        "welcomeMessage": os.environ.get("WELCOME_MESSAGE", "您好！我是 trendee，trendee 的智能顾问 \n\n请问有什么可以帮您的？"),
        "footerText": os.environ.get("FOOTER_TEXT", "trendee \u00b7 智能客服系统"),
        "defaultSource": os.environ.get("DEFAULT_SOURCE", "trendee-智能客服"),
        "placeholder": os.environ.get("PLACEHOLDER", "输入您的问题, trendee 随时为您解答..."),
        "streamingText": os.environ.get("STREAMING_TEXT", "trendee 正在输入..."),
    }
