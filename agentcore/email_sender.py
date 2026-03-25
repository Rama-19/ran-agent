"""邮件发送模块 —— QQ SMTP_SSL，支持品牌化 HTML 模板。"""
from __future__ import annotations

import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import get_smtp_config


# ── 自包含 Markdown → HTML 转换器（无外部依赖，全内联样式）────────────────────

def _inline_md(text: str) -> str:
    """处理行内 Markdown：先转义 HTML，再转换 code / bold / italic / link。"""
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    # 行内代码
    text = re.sub(
        r'`([^`]+)`',
        r'<code style="background:#f3f4f6;border:1px solid #d1d5db;border-radius:3px;'
        r'padding:1px 5px;font-family:Consolas,\'Courier New\',monospace;'
        r'font-size:12.5px;color:#4f46e5">\1</code>',
        text,
    )
    # 粗体
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong style="font-weight:700;color:#111827">\1</strong>', text)
    text = re.sub(r'__(.+?)__',     r'<strong style="font-weight:700;color:#111827">\1</strong>', text)
    # 斜体
    text = re.sub(r'\*(.+?)\*', r'<em style="font-style:italic;color:#374151">\1</em>', text)
    text = re.sub(r'_(.+?)_',   r'<em style="font-style:italic;color:#374151">\1</em>', text)
    # 链接
    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        r'<a href="\2" style="color:#7c6af7;text-decoration:none">\1</a>',
        text,
    )
    return text


def _md_to_html(text: str) -> str:
    """纯 Python Markdown → 内联样式 HTML，适配邮件客户端（QQ / Gmail / Outlook）。"""
    lines = text.split('\n')
    out: list[str] = []
    in_code = False
    code_buf: list[str] = []
    in_ul = False
    in_ol = False

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append('</ul>')
            in_ul = False
        if in_ol:
            out.append('</ol>')
            in_ol = False

    for line in lines:
        # ── 代码围栏 ──
        if line.startswith('```'):
            close_lists()
            if not in_code:
                in_code = True
                code_buf = []
            else:
                in_code = False
                code = '\n'.join(code_buf)
                code = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                out.append(
                    '<pre style="background:#f6f8fa;border:1px solid #d0d7de;border-radius:6px;'
                    'padding:14px 16px;margin:0 0 14px;overflow-x:auto;font-family:Consolas,'
                    '\'Courier New\',monospace;font-size:13px;line-height:1.6;color:#24292f">'
                    f'<code style="background:none;border:none;padding:0">{code}</code></pre>'
                )
            continue

        if in_code:
            code_buf.append(line)
            continue

        s = line.strip()

        # 空行 → 关闭列表
        if not s:
            close_lists()
            continue

        # 标题
        m = re.match(r'^(#{1,4})\s+(.+)', s)
        if m:
            close_lists()
            lvl = len(m.group(1))
            content = _inline_md(m.group(2))
            sizes  = {1: '22px', 2: '18px', 3: '15px', 4: '14px'}
            margins = {1: '20px 0 10px', 2: '18px 0 8px', 3: '14px 0 6px', 4: '12px 0 5px'}
            border = 'border-bottom:1px solid #e5e7eb;padding-bottom:6px;' if lvl <= 2 else ''
            out.append(
                f'<h{lvl} style="margin:{margins[lvl]};color:#111827;font-size:{sizes[lvl]};'
                f'font-weight:700;line-height:1.3;{border}">{content}</h{lvl}>'
            )
            continue

        # 水平线
        if re.match(r'^[-*_]{3,}\s*$', s):
            close_lists()
            out.append('<hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0" />')
            continue

        # 引用块
        if s.startswith('> '):
            close_lists()
            content = _inline_md(s[2:])
            out.append(
                f'<blockquote style="margin:0 0 12px;padding:10px 16px;border-left:3px solid #7c6af7;'
                f'background:#f5f3ff;border-radius:0 6px 6px 0;color:#4b5563;font-size:14px;'
                f'line-height:1.7">{content}</blockquote>'
            )
            continue

        # 无序列表
        m = re.match(r'^[-*+]\s+(.+)', s)
        if m:
            if in_ol:
                out.append('</ol>')
                in_ol = False
            if not in_ul:
                out.append('<ul style="margin:0 0 12px;padding-left:22px;color:#374151">')
                in_ul = True
            out.append(
                f'<li style="margin-bottom:5px;font-size:14px;line-height:1.7">'
                f'{_inline_md(m.group(1))}</li>'
            )
            continue

        # 有序列表
        m = re.match(r'^\d+\.\s+(.+)', s)
        if m:
            if in_ul:
                out.append('</ul>')
                in_ul = False
            if not in_ol:
                out.append('<ol style="margin:0 0 12px;padding-left:22px;color:#374151">')
                in_ol = True
            out.append(
                f'<li style="margin-bottom:5px;font-size:14px;line-height:1.7">'
                f'{_inline_md(m.group(1))}</li>'
            )
            continue

        # 普通段落
        close_lists()
        out.append(
            f'<p style="margin:0 0 12px;color:#374151;font-size:14px;line-height:1.8">'
            f'{_inline_md(s)}</p>'
        )

    close_lists()
    return '\n'.join(out)


# ── HTML 邮件模板（验证码）────────────────────────────────────────────────────

def _make_html(title: str, code: str, subtitle: str, action_desc: str) -> str:
    return f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 16px">
      <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#7c6af7 0%,#5a4fcf 100%);padding:28px 32px">
            <div style="font-size:22px;font-weight:700;color:#fff;letter-spacing:-0.5px">⚡ Ran Agent</div>
            <div style="font-size:13px;color:rgba(255,255,255,.8);margin-top:4px">{subtitle}</div>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px">
            <p style="margin:0 0 8px;color:#6b7280;font-size:14px">{action_desc}</p>
            <p style="margin:0 0 24px;color:#374151;font-size:14px">你的验证码是：</p>

            <div style="background:#f5f3ff;border:2px solid #7c6af7;border-radius:10px;padding:20px;text-align:center;margin-bottom:24px">
              <span style="font-size:36px;font-weight:700;letter-spacing:10px;color:#4f46e5;font-family:'Courier New',monospace">{code}</span>
            </div>

            <div style="background:#fafafa;border-left:3px solid #7c6af7;border-radius:0 6px 6px 0;padding:12px 16px;margin-bottom:24px">
              <p style="margin:0;color:#6b7280;font-size:13px;line-height:1.6">
                ⏱ 此验证码 <strong style="color:#374151">5 分钟</strong>内有效<br>
                🔒 请勿将验证码分享给任何人<br>
                ❌ 如非本人操作，请忽略此邮件
              </p>
            </div>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f9fafb;padding:16px 32px;border-top:1px solid #e5e7eb">
            <p style="margin:0;color:#9ca3af;font-size:12px;text-align:center">
              此邮件由 Ran Agent 系统自动发送，请勿直接回复
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _send(to_email: str, subject: str, plain_text: str, html_body: str) -> None:
    """底层发送函数：读取最新 SMTP 配置并发送。"""
    smtp_cfg = get_smtp_config()
    host     = smtp_cfg.get("host", "smtp.qq.com")
    port     = int(smtp_cfg.get("port", 465))
    username = smtp_cfg.get("username", "")
    password = smtp_cfg.get("password", "")
    from_name = smtp_cfg.get("from_name", "Agent")

    if not username or not password:
        raise RuntimeError("SMTP 未配置，请在设置 → SMTP 邮件中填写用户名和授权码")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{from_name} <{username}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body,  "html",  "utf-8"))

    with smtplib.SMTP_SSL(host, port) as server:
        server.login(username, password)
        server.sendmail(username, to_email, msg.as_string())


# ── 公开发送函数 ──────────────────────────────────────────────────────────────

def send_verification(to_email: str, code: str) -> None:
    plain = f"您的注册验证码是：{code}\n\n5 分钟内有效，请勿泄露。"
    html  = _make_html(
        title="注册验证码", code=code,
        subtitle="账号注册验证",
        action_desc="您正在注册 Ran Agent 账号，请在注册页面输入以下验证码：",
    )
    _send(to_email, "【Ran Agent】注册验证码", plain, html)


def send_password_reset(to_email: str, code: str) -> None:
    plain = f"您的密码重置验证码是：{code}\n\n5 分钟内有效，请勿泄露。如非本人操作请忽略。"
    html  = _make_html(
        title="密码重置", code=code,
        subtitle="密码重置验证",
        action_desc="您正在重置 Ran Agent 账号密码，请在重置页面输入以下验证码：",
    )
    _send(to_email, "【Ran Agent】密码重置验证码", plain, html)


def send_agent_reply(to_email: str, original_subject: str, result_text: str) -> None:
    """发送 agent 处理结果回复邮件（Markdown 渲染为内联样式 HTML）。"""
    subject      = f"Re: {original_subject}" if original_subject else "【Ran Agent】回复"
    content_html = _md_to_html(result_text)
    html = f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 16px">
      <table width="620" cellpadding="0" cellspacing="0" style="background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden">
        <tr>
          <td style="background:linear-gradient(135deg,#7c6af7 0%,#5a4fcf 100%);padding:22px 32px">
            <div style="font-size:20px;font-weight:700;color:#fff">⚡ Ran Agent</div>
            <div style="font-size:12px;color:rgba(255,255,255,.8);margin-top:3px">任务已完成</div>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px">{content_html}</td>
        </tr>
        <tr>
          <td style="background:#f9fafb;padding:14px 32px;border-top:1px solid #e5e7eb">
            <p style="margin:0;color:#9ca3af;font-size:12px;text-align:center">
              此邮件由 Ran Agent 自动回复 · 直接回复此邮件可继续对话
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    _send(to_email, subject, result_text, html)


def send_blocked_question(to_email: str, original_subject: str, question: str) -> None:
    """任务中断，向用户发送等待回复的邮件。"""
    subject      = f"[Ran 需要回复] {original_subject}" if original_subject else "[Ran 需要回复]"
    question_html = _md_to_html(question)
    plain = f"Agent 执行中断，需要您的回复：\n\n{question}\n\n请直接回复此邮件即可继续。"
    html = f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 16px">
      <table width="620" cellpadding="0" cellspacing="0" style="background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden">
        <tr>
          <td style="background:linear-gradient(135deg,#f59e0b 0%,#d97706 100%);padding:22px 32px">
            <div style="font-size:20px;font-weight:700;color:#fff">⚡ Ran Agent</div>
            <div style="font-size:12px;color:rgba(255,255,255,.8);margin-top:3px">任务中断 · 需要您的回复</div>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px">
            {question_html}
            <p style="color:#6b7280;font-size:13px;margin:16px 0 0;padding-top:14px;border-top:1px solid #e5e7eb">
              💬 直接回复此邮件即可继续执行任务
            </p>
          </td>
        </tr>
        <tr>
          <td style="background:#f9fafb;padding:14px 32px;border-top:1px solid #e5e7eb">
            <p style="margin:0;color:#9ca3af;font-size:12px;text-align:center">
              此邮件由 Ran Agent 自动发送，请勿修改邮件主题
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    _send(to_email, subject, plain, html)
