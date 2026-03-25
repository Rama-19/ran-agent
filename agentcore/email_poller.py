"""邮件轮询模块 —— 监听收件箱，处理 @ran 指令并用 agent 回复。

格式：
  @ran <任务>       → /auto 模式（规划执行）
  @ran/ask <任务>   → /ask 模式（直接对话）
"""
from __future__ import annotations

import email
import imaplib
import logging
import os
import threading
from email.header import decode_header
from typing import Optional

from .config import get_smtp_config, set_current_user
from .email_sender import send_agent_reply, send_blocked_question
from .skills import load_eligible_skills
from .ui import run_direct_agent
from .planner import make_plans
from .executor import execute_plan_structured
from .models import get_user_plan_store, get_user_session, RunOptions, PlanExecResult
from .storage import save_user_sessions
from .conversations import create_conversation, append_message

logger = logging.getLogger(__name__)

# 轮询间隔（秒）
POLL_INTERVAL = int(os.environ.get("EMAIL_POLL_INTERVAL", "30"))

# user_id → conv_id：记录当前正在等待用户回复的 auto 会话（blocked）
_pending_conv_ids: dict[str, str] = {}

# user_id → conv_id：记录最近一次 ask 会话，用于邮件继续对话
_ask_conv_ids: dict[str, str] = {}


# ── 用户查找 ──────────────────────────────────────────────────────────────────

def _find_registered_user(email_addr: str) -> Optional[dict]:
    """根据邮箱地址查找已注册用户，未找到返回 None。"""
    from .auth import _get_user_by_email  # 避免循环导入
    return _get_user_by_email(email_addr.lower().strip())


# ── 邮件解码工具 ──────────────────────────────────────────────────────────────

def _decode_str(raw) -> str:
    """解码邮件 Header 字段（Subject/From）。"""
    if raw is None:
        return ""
    parts = decode_header(raw)
    result = []
    for fragment, charset in parts:
        if isinstance(fragment, bytes):
            result.append(fragment.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(fragment)
    return "".join(result)


def _get_text_body(msg: email.message.Message) -> str:
    """从邮件中提取纯文本正文。"""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = part.get("Content-Disposition", "")
            if ct == "text/plain" and "attachment" not in cd:
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                return payload.decode(charset, errors="replace") if payload else ""
    else:
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True)
        return payload.decode(charset, errors="replace") if payload else ""
    return ""


def _parse_sender_email(from_header: str) -> str:
    """从 From 头提取邮箱地址，例如 '张三 <foo@bar.com>' → 'foo@bar.com'。"""
    from_header = _decode_str(from_header)
    if "<" in from_header and ">" in from_header:
        return from_header.split("<")[-1].split(">")[0].strip().lower()
    return from_header.strip().lower()


# ── 指令解析 ──────────────────────────────────────────────────────────────────

def _parse_command(body: str) -> Optional[tuple[str, str]]:
    """
    解析邮件正文中的 @ran 指令。
    返回 (mode, task)，mode 为 'auto' 或 'ask'。
    找不到 @ran 前缀返回 None。
    """
    text = body.strip()
    # 找到第一行（指令行可能只在开头）
    first_line = text.split("\n")[0].strip()

    if first_line.lower().startswith("@ran/ask"):
        task = first_line[len("@ran/ask"):].strip()
        # 如果任务为空，使用剩余全文
        if not task:
            task = "\n".join(text.split("\n")[1:]).strip()
        return ("ask", task) if task else None

    if first_line.lower().startswith("@ran"):
        task = first_line[len("@ran"):].strip()
        if not task:
            task = "\n".join(text.split("\n")[1:]).strip()
        return ("auto", task) if task else None

    return None


# 邮件处理默认选项：开启网络检索 + 轻度思考
_EMAIL_OPTIONS = RunOptions(web_mode="on", deep_think=1)


# ── 邮件引用内容清理 ──────────────────────────────────────────────────────────

def _strip_reply_quotes(body: str) -> str:
    """从回复邮件正文中提取用户新写的内容，去除引用部分。"""
    lines = body.split("\n")
    clean: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">"):          # 引用行
            break
        if stripped.startswith("On ") and "wrote:" in stripped:  # Gmail/Outlook 引用头
            break
        if stripped.startswith("-----") or stripped.startswith("_____"):
            break
        clean.append(line)
    return "\n".join(clean).strip()


# ── Agent 执行 ────────────────────────────────────────────────────────────────

def _run_ask(user_id: str, task: str, history=None) -> str:
    eligible = load_eligible_skills()
    set_current_user(user_id)
    try:
        return run_direct_agent(task, eligible, options=_EMAIL_OPTIONS, history=history)
    finally:
        set_current_user(None)


def _run_auto(user_id: str, task: str) -> tuple[str, Optional[PlanExecResult]]:
    """执行 auto 模式，返回 (消息文本, 最终执行结果)。"""
    eligible = load_eligible_skills()
    ps = get_user_plan_store(user_id)
    set_current_user(user_id)
    try:
        plans = make_plans(task, eligible, options=_EMAIL_OPTIONS, plan_store=ps)
        outputs = []
        last_result = None
        for p in plans:
            last_result = execute_plan_structured(p.id, eligible, plan_store=ps)
            if last_result.message:
                outputs.append(last_result.message)
            if last_result.status in ("done", "blocked"):
                break
        save_user_sessions(user_id, ps)
        msg = "\n\n".join(outputs) if outputs else "任务已完成（无输出）"
        return msg, last_result
    finally:
        set_current_user(None)


def _run_reply_email(user_id: str, reply_text: str) -> tuple[str, Optional[PlanExecResult]]:
    """通过邮件回复恢复被中断的 plan。"""
    sess = get_user_session(user_id)
    if not sess.state.pending:
        return "当前没有待回复的任务", None
    pending = sess.state.pending
    eligible = load_eligible_skills()
    ps = get_user_plan_store(user_id)
    set_current_user(user_id)
    try:
        result = execute_plan_structured(pending.plan_id, eligible, resume_reply=reply_text, plan_store=ps)
        save_user_sessions(user_id, ps)
        return result.message or "任务已继续执行", result
    finally:
        set_current_user(None)


# ── IMAP 轮询 ─────────────────────────────────────────────────────────────────

def _poll_once() -> None:
    """连接 IMAP，处理所有未读的 @ran 邮件。"""
    smtp_cfg = get_smtp_config()
    username = smtp_cfg.get("username", "")
    password = smtp_cfg.get("password", "")
    imap_host = smtp_cfg.get("imap_host") or os.environ.get("IMAP_HOST", "imap.qq.com")
    imap_port = int(smtp_cfg.get("imap_port") or os.environ.get("IMAP_PORT", 993))

    if not username or not password:
        logger.debug("邮件轮询跳过：SMTP 未配置")
        return

    try:
        imap = imaplib.IMAP4_SSL(imap_host, imap_port)
        imap.login(username, password)
        imap.select("INBOX")

        _, data = imap.search(None, "UNSEEN")
        if not data or not data[0]:
            imap.logout()
            return

        ids = data[0].split()
        logger.info(f"邮件轮询：发现 {len(ids)} 封未读邮件")

        for num in ids:
            try:
                _, msg_data = imap.fetch(num, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                # 立即标为已读，防止处理途中异常导致下轮重复处理
                imap.store(num, "+FLAGS", "\\Seen")

                sender = _parse_sender_email(msg.get("From", ""))
                subject = _decode_str(msg.get("Subject", ""))
                body = _get_text_body(msg)

                user = _find_registered_user(sender)
                if user is None:
                    logger.warning(f"邮件来自未注册用户 {sender}，忽略")
                    imap.store(num, "+FLAGS", "\\Seen")
                    continue

                user_id = user["id"]
                sess = get_user_session(user_id)
                parsed = _parse_command(body)

                # ── 回复模式：用户回复了等待中的 blocked 任务 ──
                if parsed is None and sess.state.pending:
                    reply_text = _strip_reply_quotes(body)
                    if not reply_text:
                        continue

                    logger.info(f"收到任务回复：from={sender} reply={reply_text[:60]!r}")
                    conv_id = _pending_conv_ids.get(user_id)
                    if conv_id:
                        append_message(conv_id, "user", f"[回复] {reply_text}", user_id=user_id)

                    try:
                        result_text, result = _run_reply_email(user_id, reply_text)
                    except Exception as e:
                        result_text = f"继续执行时出错：{e}"
                        result = None
                        logger.exception(f"回复执行失败 from={sender}")

                    if conv_id:
                        append_message(conv_id, "agent", result_text, user_id=user_id)

                    if result and result.status == "blocked" and result.need_input:
                        sess.set_pending(result.need_input)
                        send_blocked_question(sender, subject, result.need_input.question)
                        logger.info(f"任务再次中断，已向 {sender} 发送追问")
                    else:
                        sess.clear_pending()
                        _pending_conv_ids.pop(user_id, None)
                        send_agent_reply(sender, subject, result_text)
                        logger.info(f"任务继续完成，已回复 {sender}")
                    continue

                # ── ask 对话继续：只响应明确的 Re: 回复邮件 ──
                is_reply_email = subject.lower().startswith("re:")
                # 优先从内存取；若服务重启则回退到最近一条邮件会话
                _resolved_ask_conv = _ask_conv_ids.get(user_id)
                if not _resolved_ask_conv and is_reply_email:
                    from .conversations import list_conversations
                    _email_convs = sorted(
                        [c for c in list_conversations(user_id=user_id)
                         if c["title"].startswith("[邮件]")],
                        key=lambda c: c.get("updated_at", ""), reverse=True,
                    )
                    if _email_convs:
                        _resolved_ask_conv = _email_convs[0]["id"]
                        _ask_conv_ids[user_id] = _resolved_ask_conv  # 恢复内存缓存
                if parsed is None and is_reply_email and _resolved_ask_conv:
                    reply_text = _strip_reply_quotes(body)
                    if not reply_text:
                        continue

                    ask_conv_id = _resolved_ask_conv
                    logger.info(f"ask 对话继续：from={sender} reply={reply_text[:60]!r}")

                    from .conversations import get_conversation
                    conv_data = get_conversation(ask_conv_id, user_id=user_id)
                    history = []
                    if conv_data:
                        for m in conv_data.get("messages", []):
                            role = m.get("role", "")
                            if role in ("user", "assistant", "agent"):
                                history.append({
                                    "role": "assistant" if role == "agent" else role,
                                    "content": m.get("text", ""),
                                })

                    append_message(ask_conv_id, "user", reply_text, user_id=user_id)
                    try:
                        result_text = _run_ask(user_id, reply_text, history=history)
                    except Exception as e:
                        result_text = f"继续对话时出错：{e}"
                        logger.exception(f"ask 继续对话失败 from={sender}")

                    append_message(ask_conv_id, "agent", result_text, user_id=user_id)
                    send_agent_reply(sender, subject, result_text)
                    logger.info(f"ask 对话已继续回复 {sender}")
                    continue

                # ── 忽略：非 @ran 且无需处理 ──
                if parsed is None:
                    continue

                # ── 新任务模式 ──
                mode, task = parsed
                logger.info(f"处理邮件：from={sender} mode={mode} task={task[:60]!r}")

                # 创建会话并记录用户消息
                conv_title = f"[邮件] {subject}" if subject else "[邮件] @ran 任务"
                conv = create_conversation(conv_title, user_id=user_id)
                conv_id = conv["id"]
                append_message(conv_id, "user", task, user_id=user_id)

                # ask 会话 ID 在执行前就记录，确保异常或重启后仍可继续对话
                if mode == "ask":
                    _ask_conv_ids[user_id] = conv_id

                exec_result: Optional[PlanExecResult] = None
                try:
                    if mode == "ask":
                        result_text = _run_ask(user_id, task)
                    else:
                        result_text, exec_result = _run_auto(user_id, task)
                except Exception as e:
                    result_text = f"处理任务时出错：{e}"
                    logger.exception(f"agent 执行失败 from={sender}")

                append_message(conv_id, "agent", result_text, user_id=user_id)

                # 检查是否中断等待用户输入
                if exec_result and exec_result.status == "blocked" and exec_result.need_input:
                    sess.set_pending(exec_result.need_input)
                    _pending_conv_ids[user_id] = conv_id
                    send_blocked_question(sender, subject, exec_result.need_input.question)
                    logger.info(f"任务中断，已向 {sender} 发送等待回复邮件")
                else:
                    send_agent_reply(sender, subject, result_text)
                    logger.info(f"已回复 {sender}")

            except Exception:
                logger.exception(f"处理邮件 {num} 时出错，跳过")

        imap.logout()

    except Exception:
        logger.exception("邮件轮询连接失败")


# ── 后台线程 ──────────────────────────────────────────────────────────────────

_stop_event = threading.Event()
_thread: Optional[threading.Thread] = None


def _loop() -> None:
    logger.info(f"邮件轮询线程已启动，间隔 {POLL_INTERVAL}s")
    while not _stop_event.is_set():
        try:
            _poll_once()
        except Exception:
            logger.exception("邮件轮询意外错误")
        _stop_event.wait(POLL_INTERVAL)
    logger.info("邮件轮询线程已停止")


def start() -> None:
    """启动后台轮询线程（幂等）。"""
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, name="email-poller", daemon=True)
    _thread.start()


def stop() -> None:
    """停止后台轮询线程。"""
    _stop_event.set()
    if _thread:
        _thread.join(timeout=5)
