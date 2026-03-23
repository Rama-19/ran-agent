"""邮件发送模块 —— QQ SMTP_SSL，支持品牌化 HTML 模板。"""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import get_smtp_config

# ── HTML 邮件模板 ─────────────────────────────────────────────────────────────

def _make_html(title: str, code: str, subtitle: str, action_desc: str) -> str:
    return f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0f1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 16px">
      <table width="480" cellpadding="0" cellspacing="0" style="background:#1a1d24;border:1px solid #2a2d35;border-radius:12px;overflow:hidden">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#7c6af7 0%,#5a4fcf 100%);padding:28px 32px">
            <div style="font-size:22px;font-weight:700;color:#fff;letter-spacing:-0.5px">⚡ Ran Agent</div>
            <div style="font-size:13px;color:rgba(255,255,255,.7);margin-top:4px">{subtitle}</div>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px">
            <p style="margin:0 0 8px;color:#9ca3af;font-size:14px">{action_desc}</p>
            <p style="margin:0 0 24px;color:#e5e7eb;font-size:14px">
              你的验证码是：
            </p>

            <!-- Code box -->
            <div style="background:#0f1117;border:2px solid #7c6af7;border-radius:10px;padding:20px;text-align:center;margin-bottom:24px">
              <span style="font-size:36px;font-weight:700;letter-spacing:10px;color:#fff;font-family:'Courier New',monospace">{code}</span>
            </div>

            <div style="background:#1e2028;border-left:3px solid #7c6af7;border-radius:0 6px 6px 0;padding:12px 16px;margin-bottom:24px">
              <p style="margin:0;color:#9ca3af;font-size:13px;line-height:1.6">
                ⏱ 此验证码 <strong style="color:#e5e7eb">5 分钟</strong>内有效<br>
                🔒 请勿将验证码分享给任何人<br>
                ❌ 如非本人操作，请忽略此邮件
              </p>
            </div>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#0f1117;padding:16px 32px;border-top:1px solid #2a2d35">
            <p style="margin:0;color:#4b5563;font-size:12px;text-align:center">
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
    host = smtp_cfg.get("host", "smtp.qq.com")
    port = int(smtp_cfg.get("port", 465))
    username = smtp_cfg.get("username", "")
    password = smtp_cfg.get("password", "")
    from_name = smtp_cfg.get("from_name", "Agent")

    if not username or not password:
        raise RuntimeError("SMTP 未配置，请在设置 → SMTP 邮件中填写用户名和授权码")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{username}>"
    msg["To"] = to_email
    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL(host, port) as server:
        server.login(username, password)
        server.sendmail(username, to_email, msg.as_string())


# ── 公开发送函数 ──────────────────────────────────────────────────────────────

def send_verification(to_email: str, code: str) -> None:
    """发送注册验证码邮件。"""
    plain = f"您的注册验证码是：{code}\n\n5 分钟内有效，请勿泄露。"
    html = _make_html(
        title="注册验证码",
        code=code,
        subtitle="账号注册验证",
        action_desc="您正在注册 Ran Agent 账号，请在注册页面输入以下验证码：",
    )
    _send(to_email, "【Ran Agent】注册验证码", plain, html)


def send_password_reset(to_email: str, code: str) -> None:
    """发送密码重置验证码邮件。"""
    plain = f"您的密码重置验证码是：{code}\n\n5 分钟内有效，请勿泄露。如非本人操作请忽略。"
    html = _make_html(
        title="密码重置",
        code=code,
        subtitle="密码重置验证",
        action_desc="您正在重置 Ran Agent 账号密码，请在重置页面输入以下验证码：",
    )
    _send(to_email, "【Ran Agent】密码重置验证码", plain, html)


def send_agent_reply(to_email: str, original_subject: str, result_text: str) -> None:
    """发送 agent 处理结果回复邮件。"""
    subject = f"Re: {original_subject}" if original_subject else "【Ran Agent】回复"
    # 将换行转为 <br>，保留格式
    html_body = result_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
    html = f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0f1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 16px">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#1a1d24;border:1px solid #2a2d35;border-radius:12px;overflow:hidden">
        <tr>
          <td style="background:linear-gradient(135deg,#7c6af7 0%,#5a4fcf 100%);padding:24px 32px">
            <div style="font-size:20px;font-weight:700;color:#fff">⚡ Ran Agent</div>
            <div style="font-size:12px;color:rgba(255,255,255,.7);margin-top:4px">任务已完成</div>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px">
            <div style="background:#0f1117;border-radius:8px;padding:20px;color:#e5e7eb;font-size:14px;line-height:1.8;white-space:pre-wrap;font-family:'Courier New',monospace">
              {html_body}
            </div>
          </td>
        </tr>
        <tr>
          <td style="background:#0f1117;padding:14px 32px;border-top:1px solid #2a2d35">
            <p style="margin:0;color:#4b5563;font-size:12px;text-align:center">
              此邮件由 Ran Agent 自动回复，发送 @ran &lt;任务&gt; 可继续使用
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    _send(to_email, subject, result_text, html)
