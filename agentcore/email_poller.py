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
import time
from email.header import decode_header
from typing import Optional

from .config import get_smtp_config, set_current_user
from .email_sender import send_agent_reply
from .skills import load_eligible_skills
from .ui import run_direct_agent
from .planner import make_plans
from .executor import execute_plan_structured
from .models import get_user_plan_store, RunOptions
from .storage import save_user_sessions

logger = logging.getLogger(__name__)

# 轮询间隔（秒）
POLL_INTERVAL = int(os.environ.get("EMAIL_POLL_INTERVAL", "30"))


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


# ── Agent 执行 ────────────────────────────────────────────────────────────────

def _run_ask(user_id: str, task: str) -> str:
    eligible = load_eligible_skills()
    set_current_user(user_id)
    try:
        return run_direct_agent(task, eligible, options=_EMAIL_OPTIONS)
    finally:
        set_current_user(None)


def _run_auto(user_id: str, task: str) -> str:
    eligible = load_eligible_skills()
    ps = get_user_plan_store(user_id)
    set_current_user(user_id)
    try:
        plans = make_plans(task, eligible, options=_EMAIL_OPTIONS, plan_store=ps)
        outputs = []
        for p in plans:
            result = execute_plan_structured(p.id, eligible, plan_store=ps)
            if result.message:
                outputs.append(result.message)
            if result.status in ("done", "blocked"):
                break
        save_user_sessions(user_id, ps)
        return "\n\n".join(outputs) if outputs else "任务已完成（无输出）"
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

                sender = _parse_sender_email(msg.get("From", ""))
                subject = _decode_str(msg.get("Subject", ""))
                body = _get_text_body(msg)

                parsed = _parse_command(body)
                if parsed is None:
                    # 不是 @ran 指令，忽略但标为已读
                    imap.store(num, "+FLAGS", "\\Seen")
                    continue

                mode, task = parsed
                user = _find_registered_user(sender)
                if user is None:
                    logger.warning(f"邮件来自未注册用户 {sender}，忽略")
                    imap.store(num, "+FLAGS", "\\Seen")
                    continue

                logger.info(f"处理邮件：from={sender} mode={mode} task={task[:60]!r}")

                try:
                    if mode == "ask":
                        reply_text = _run_ask(user["id"], task)
                    else:
                        reply_text = _run_auto(user["id"], task)
                except Exception as e:
                    reply_text = f"处理任务时出错：{e}"
                    logger.exception(f"agent 执行失败 from={sender}")

                send_agent_reply(sender, subject, reply_text)
                imap.store(num, "+FLAGS", "\\Seen")
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
