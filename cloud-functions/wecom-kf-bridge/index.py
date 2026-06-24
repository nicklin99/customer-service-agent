"""
企业微信「微信客服 + 客户联系」桥接

双回调处理:
  1. 微信客服 KF → sync_msg 拉消息 → AI 回复 → send_msg 发回
  2. 客户联系 → add_external_contact 事件 → 记录渠道 state → 发欢迎语

管理员可用:
  ?action=create_qr_code → 生成带 state 的渠道活码
"""

import hashlib
import json
import logging
import time
import xml.etree.ElementTree as ET
from base64 import b64decode, b64encode

import httpx

logger = logging.getLogger("wecom-kf-bridge")

# ── 环境变量键名 ────────────────────────────────────────
ENV_WECOM_CORP_ID = "WECOM_CORP_ID"
ENV_WECOM_KF_SECRET = "WECOM_KF_SECRET"       # 微信客服应用 secret
ENV_WECOM_APP_SECRET = "WECOM_APP_SECRET"      # 自建应用 secret（客户联系用）
ENV_WECOM_TOKEN = "WECOM_TOKEN"               # 回调 Token
ENV_WECOM_ENCODING_AES_KEY = "WECOM_ENCODING_AES_KEY"

# ── Token 缓存 ──────────────────────────────────────────
_token_cache: dict = {"token": "", "expires_at": 0}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  工具函数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _get_access_token(context) -> str:
    """获取/刷新企业微信 access_token"""
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["token"]

    corp_id = context.env.get(ENV_WECOM_CORP_ID)
    secret = context.env.get(ENV_WECOM_KF_SECRET)
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


def _decrypt(encoding_aes_key: str, raw: str) -> str:
    """AES-256-CBC 解密"""
    from Crypto.Cipher import AES

    aes_key = b64decode(encoding_aes_key + "=")
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_key[:16])
    plain = cipher.decrypt(b64decode(raw))

    # PKCS7 去填充
    pad_len = plain[-1]
    plain = plain[:-pad_len]

    # 提取消息体: [16随机][4字节网络序长度][消息][corpid]
    msg_len = int.from_bytes(plain[16:20], "big")
    return plain[20 : 20 + msg_len].decode("utf-8")


def _verify_callback(
    token: str, aes_key: str, msg_signature: str,
    timestamp: str, nonce: str, echostr: str,
) -> str | None:
    """验证回调 URL 并返回解密后的 echostr"""
    # 1. 验证 msg_signature
    sig = hashlib.sha1(
        "".join(sorted([token, timestamp, nonce, echostr])).encode()
    ).hexdigest()
    if sig != msg_signature:
        logger.warning("回调签名验证失败")
        return None

    # 2. 解密 echostr
    try:
        return _decrypt(aes_key, echostr)
    except Exception as e:
        logger.error("解密 echostr 失败: %s", e)
        return None


def _encrypt(encoding_aes_key: str, plain_text: str, corpid: str) -> str:
    """AES-256-CBC 加密（PKCS7）"""
    from Crypto.Cipher import AES
    import os

    aes_key = b64decode(encoding_aes_key + "=")
    raw = (
        os.urandom(16)
        + len(plain_text).to_bytes(4, "big")
        + plain_text.encode()
        + corpid.encode()
    )
    # PKCS7 填充
    block_size = 32
    pad_len = block_size - (len(raw) % block_size)
    raw += bytes([pad_len] * pad_len)

    cipher = AES.new(aes_key, AES.MODE_CBC, aes_key[:16])
    return b64encode(cipher.encrypt(raw)).decode()


def _build_callback_xml(
    token: str, aes_key: str, corpid: str, reply: str,
    timestamp: str, nonce: str,
) -> str:
    """构建回调响应 XML"""
    encrypted = _encrypt(aes_key, reply, corpid)
    raw = f"{timestamp}\n{nonce}\n{encrypted}"
    signature = hashlib.sha1("".join(sorted([token, timestamp, nonce, encrypted])).encode()).hexdigest()
    return f"""<xml>
<Encrypt><![CDATA[{encrypted}]]></Encrypt>
<MsgSignature><![CDATA[{signature}]]></MsgSignature>
<TimeStamp>{timestamp}</TimeStamp>
<Nonce><![CDATA[{nonce}]]></Nonce>
</xml>"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  微信客服 API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _sync_msg(context, token: str, open_kfid: str) -> list[dict]:
    """增量拉取消息：基于已存的 cursor，只拉新消息"""
    access_token = await _get_access_token(context)
    all_msgs: list[dict] = []

    # 从 store 加载上次的 cursor
    cursor_key = f"wecom_kf_cursor:{open_kfid}"
    cursor = ""
    try:
        stored = await context.agent.store.get(cursor_key)
        cursor = stored or ""
    except Exception:
        pass

    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            body = {"token": token, "open_kfid": open_kfid, "limit": 100}
            if cursor:
                body["cursor"] = cursor

            resp = await client.post(
                "https://qyapi.weixin.qq.com/cgi-bin/kf/sync_msg",
                params={"access_token": access_token},
                json=body,
            )
            data = resp.json()
            if data.get("errcode"):
                logger.error("sync_msg 失败: %s", data)
                break

            msgs = data.get("msg_list", [])
            all_msgs.extend(msgs)
            next_cursor = data.get("next_cursor", "")

            if not data.get("has_more"):
                # 更新 cursor，下次只拉更新的
                if msgs and next_cursor:
                    try:
                        await context.agent.store.set(cursor_key, next_cursor)
                    except Exception as e:
                        logger.warning("保存 cursor 失败: %s", e)
                break
            cursor = next_cursor

    return all_msgs


async def _send_kf_msg(
    context, external_userid: str, open_kfid: str, content: str,
) -> bool:
    """通过微信客服 API 发送文本消息给客户"""
    access_token = await _get_access_token(context)
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  客户联系 API（渠道活码 · 欢迎语）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _get_app_access_token(context) -> str:
    """获取自建应用的 access_token（用于客户联系 API）"""
    now = time.time()
    cached = _token_cache.get("app_token")
    if cached and cached["expires_at"] > now + 60:
        return cached["token"]

    corp_id = context.env.get(ENV_WECOM_CORP_ID)
    secret = context.env.get(ENV_WECOM_APP_SECRET) or context.env.get(ENV_WECOM_KF_SECRET)
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


async def _create_contact_way(
    context, users: list[str], state: str, skip_verify: bool = True,
) -> dict:
    """创建带 state 的「联系我」渠道活码"""
    access_token = await _get_app_access_token(context)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://qyapi.weixin.qq.com/cgi-bin/externalcontact/add_contact_way",
            params={"access_token": access_token},
            json={
                "type": 1,
                "scene": 2,
                "state": state,
                "user": users,
                "skip_verify": skip_verify,
            },
        )
        return resp.json()


async def _send_welcome_msg(context, welcome_code: str, content: str) -> bool:
    """发送欢迎语（客户首次添加好友后自动触发）"""
    access_token = await _get_app_access_token(context)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://qyapi.weixin.qq.com/cgi-bin/externalcontact/send_welcome_msg",
            params={"access_token": access_token},
            json={
                "welcome_code": welcome_code,
                "text": {"content": content},
            },
        )
        data = resp.json()
        if data.get("errcode"):
            logger.error("send_welcome_msg 失败: %s", data)
            return False
        return True


async def _get_channel_state(context, external_userid: str) -> str:
    """查询客户的渠道 state"""
    try:
        return await context.agent.store.get(f"wecom_kf_channel:{external_userid}") or ""
    except Exception:
        return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  与 AI Agent 对话
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 复用 Agent 的系统提示词
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
- 不要承诺具体价格（可以说"稍后顾问会给您详细报价"）
- 不要在没有线索信号时强行收集信息
- 不要一次性问太多问题

## 可用的产品线
- 建站服务：企业官网、电商网站、小程序
- SEO 优化：搜索引擎优化、内容策略
- 品牌设计：VI 设计、品牌策略
- AI 解决方案：智能客服、数据分析、流程自动化
- 日常托管：网站运维、内容更新（400 元/月起）"""


def _build_conversation_messages(history: list[dict]) -> list[dict]:
    """将历史记录转为 LangChain 消息格式"""
    messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    for item in history:
        role = "user" if item.get("role") == "customer" else "assistant"
        messages.append({"role": role, "content": item.get("content", "")})
    return messages


async def _load_history(context, external_userid: str) -> list[dict]:
    """从 EdgeOne Store 加载用户对话历史"""
    store_key = f"wecom_kf:{external_userid}"
    try:
        stored = await context.agent.store.get(store_key)
        return json.loads(stored) if stored else []
    except Exception:
        return []


async def _save_to_history(
    context, external_userid: str, role: str, content: str,
) -> None:
    """追加一条记录到对话历史"""
    history = await _load_history(context, external_userid)
    history.append({"role": role, "content": content, "time": int(time.time())})
    try:
        await context.agent.store.set(
            f"wecom_kf:{external_userid}",
            json.dumps(history[-40:], ensure_ascii=False),
        )
    except Exception as e:
        logger.warning("保存对话历史失败: %s", e)


async def _call_ai_agent(context, external_userid: str, user_msg: str) -> str:
    """调用 AI 模型获取回复"""
    # 1. 从 EdgeOne Store 读取历史
    history = await _load_history(context, external_userid)

    # 2. 追加用户消息
    history.append({"role": "customer", "content": user_msg, "time": int(time.time())})

    # 3. 调用 LLM
    api_key = (context.env.get("AI_GATEWAY_API_KEY") or "").strip()
    base_url = (context.env.get("AI_GATEWAY_BASE_URL") or "").strip()
    model_name = context.env.get("AI_GATEWAY_MODEL") or "@makers/deepseek-v4-flash"

    if not api_key or not base_url:
        reply = "系统暂时无法回复，请稍后再试。"
    else:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)
        messages = _build_conversation_messages(history)

        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
            )
            reply = resp.choices[0].message.content or ""
        except Exception as e:
            logger.error("AI 调用失败: %s", e)
            reply = "抱歉，我暂时遇到了一些问题，请稍后再试。"

    # 4. 保存回复到历史
    await _save_to_history(context, external_userid, "ai", reply)

    return reply


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  主 Handler
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def handler(context):
    """
    EdgeOne Cloud Function handler。

    GET  → 企业微信回调 URL 验证
    POST → 接收消息事件回调
    """
    method = context.method or "GET"
    query = context.query or {}
    body = context.body or {}

    token = context.env.get(ENV_WECOM_TOKEN, "")
    aes_key = context.env.get(ENV_WECOM_ENCODING_AES_KEY, "")
    corp_id = context.env.get(ENV_WECOM_CORP_ID, "")

    # ── GET: URL 验证 ──────────────────────────────────
    if method == "GET":
        msg_signature = query.get("msg_signature", "")
        timestamp = query.get("timestamp", "")
        nonce = query.get("nonce", "")
        echostr = query.get("echostr", "")

        if not token or not aes_key:
            return {"status_code": 500, "body": "回调配置未完成: 缺少 WECOM_TOKEN 或 WECOM_ENCODING_AES_KEY"}

        decrypted = _verify_callback(token, aes_key, msg_signature, timestamp, nonce, echostr)
        if decrypted is None:
            return {"status_code": 403, "body": "verify fail"}

        return {"status_code": 200, "body": decrypted, "content_type": "text/plain"}

    # ── POST: 接收回调事件 ──────────────────────────────
    if method == "POST":
        # ── 管理操作 ──────────────────────────────────
        action = body.get("action", "") if isinstance(body, dict) else ""
        if action == "create_qr_code":
            users = body.get("users", [])
            state = body.get("state", "")
            if not users or not state:
                return {"status_code": 400, "body": {"error": "缺少 users 或 state"}}
            result = await _create_contact_way(context, users, state)
            return {"status_code": 200, "body": result}

        if not token or not aes_key:
            return {"status_code": 500, "body": "回调配置未完成"}

        # 1. 解密请求体
        raw_xml = body if isinstance(body, str) else json.dumps(body)
        try:
            root = ET.fromstring(raw_xml)
            encrypted = root.findtext("Encrypt", "")
            msg_signature = root.findtext("MsgSignature", "")
            timestamp = root.findtext("TimeStamp", "")
            nonce = root.findtext("Nonce", "")
        except ET.ParseError:
            return {"status_code": 400, "body": "invalid xml"}

        # 验证签名
        sig = hashlib.sha1(
            "".join(sorted([token, timestamp, nonce, encrypted])).encode()
        ).hexdigest()
        if sig != msg_signature:
            return {"status_code": 403, "body": "signature mismatch"}

        # 解密
        try:
            decrypted_xml = _decrypt(aes_key, encrypted)
        except Exception as e:
            logger.error("解密失败: %s", e)
            return {"status_code": 500, "body": "decrypt fail"}

        event_root = ET.fromstring(decrypted_xml)
        event_type = event_root.findtext("Event", "")

        # ── 处理客户联系事件（新增好友 · 渠道追踪）─────────
        if event_type == "change_external_contact":
            change_type = event_root.findtext("ChangeType", "")
            if change_type == "add_external_contact":
                external_userid = event_root.findtext("ExternalUserID", "")
                state = event_root.findtext("State", "")
                welcome_code = event_root.findtext("WelcomeCode", "")

                logger.info("新客户添加: %s, state=%s", external_userid, state)

                # 存储渠道 state
                if external_userid and state:
                    try:
                        await context.agent.store.set(
                            f"wecom_kf_channel:{external_userid}", state,
                        )
                    except Exception as e:
                        logger.warning("保存渠道 state 失败: %s", e)

                # 发欢迎语
                if welcome_code:
                    welcome_text = (
                        "您好！我是智能客服助手，很高兴为您服务。请问有什么可以帮您的吗？"
                    )
                    await _send_welcome_msg(context, welcome_code, welcome_text)

            return {"status_code": 200, "body": "success"}

        # ── 处理微信客服 KF 事件（消息收发）─────────────────
        if event_type != "kf_msg_or_event":
            return {"status_code": 200, "body": "success"}

        event_token = event_root.findtext("Token", "")
        open_kfid = event_root.findtext("OpenKfId", "")
        if not event_token or not open_kfid:
            return {"status_code": 200, "body": "success"}

        # 3. 拉取消息
        msg_list = await _sync_msg(context, event_token, open_kfid)
        logger.info("拉取到 %d 条消息/事件", len(msg_list))

        # 4. 加载已处理过的 msgid 列表（去重）
        processed_key = f"wecom_kf_processed:{open_kfid}"
        try:
            stored = await context.agent.store.get(processed_key)
            processed_ids: set[str] = set(json.loads(stored)) if stored else set()
        except Exception:
            processed_ids = set()

        # 5. 按用户分组收集本次回调中的新消息（已处理过 msgid 的跳过）
        user_texts: dict[str, list[str]] = {}
        user_entered: set[str] = set()
        batch_msgids: list[str] = []   # 本次新出现的 msgid，处理成功后一起保存

        for msg in msg_list:
            uid = msg.get("external_userid", "")
            msgid = msg.get("msgid", "")
            if not uid or not msgid:
                continue
            if msgid in processed_ids:
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

        # 6. 处理每个用户（所有处理成功后才标记 msgid 已处理）
        all_success = True
        for uid, texts in user_texts.items():
            is_new = uid in user_entered

            # 新会话先发欢迎语
            if is_new:
                welcome = "您好！我是智能客服助手，很高兴为您服务。请问有什么可以帮您的吗？"
                ok = await _send_kf_msg(context, uid, open_kfid, welcome)
                if ok:
                    await _save_to_history(context, uid, "ai", welcome)
                else:
                    all_success = False
                    continue

            # 先写入前面的消息到历史
            for t in texts[:-1]:
                await _save_to_history(context, uid, "customer", t)

            # 对最后一条调用 AI
            reply = await _call_ai_agent(context, uid, texts[-1])

            # 发送回复
            ok = await _send_kf_msg(context, uid, open_kfid, reply)
            if not ok:
                logger.error("send_msg 失败，用户 %s 未收到回复", uid)
                all_success = False

        # 7. 全部处理成功后才标记 msgid 已处理（防止丢消息）
        if batch_msgids and all_success:
            processed_ids.update(batch_msgids)
            trimmed = list(processed_ids)[-500:]
            try:
                await context.agent.store.set(processed_key, json.dumps(trimmed))
            except Exception as e:
                logger.warning("保存 processed_ids 失败: %s", e)

        return {"status_code": 200, "body": "success"}

    return {"status_code": 405, "body": "method not allowed"}
