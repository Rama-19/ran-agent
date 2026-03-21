#!/usr/bin/env python3
"""send_email_qq.py — 通过 QQ 邮箱 SMTP(465/SSL) 发送文本邮件（支持主题、收件人、抄送、可选附件）

实现要点：
- SMTP over SSL: smtp.qq.com:465（可通过参数覆盖 host/port）
- 建议使用 QQ 邮箱“授权码”而非登录密码
- 支持多收件人/抄送、多个附件
- from_email/auth_code 支持从环境变量读取（便于在自动化环境中使用）
- 支持 dry-run：仅构建并打印邮件摘要，不实际连接 SMTP（便于在网络受限或排错时使用）

环境变量：
- QQ_EMAIL_SENDER：默认发件人邮箱
- QQ_EMAIL_AUTH_CODE：默认 SMTP 授权码
"""

from __future__ import annotations

import argparse
import mimetypes
import os
import smtplib
from email.message import EmailMessage
from typing import Iterable, List, Optional, Sequence, Union

ENV_SENDER = "QQ_EMAIL_SENDER"
ENV_AUTH_CODE = "QQ_EMAIL_AUTH_CODE"


def _split_emails_one(value: Optional[str]) -> List[str]:
    """Split a single string which may contain comma/space separated emails."""
    if not value:
        return []
    parts = [p.strip() for p in value.replace(" ", ",").split(",")]
    return [p for p in parts if p]


def normalize_emails(value: Union[None, str, Sequence[str]]) -> List[str]:
    """Normalize recipient input to a flat list.

    Accepts:
    - None
    - "a@x.com,b@y.com"
    - ["a@x.com", "b@y.com"]
    - ["a@x.com,b@y.com", "c@z.com"]
    """

    if value is None:
        return []
    if isinstance(value, str):
        return _split_emails_one(value)

    out: List[str] = []
    for item in value:
        out.extend(_split_emails_one(item))
    return out


def _normalize_attachments(paths: Iterable[str]) -> List[str]:
    out: List[str] = []
    for p in paths:
        if not p:
            continue
        p2 = os.path.abspath(os.path.expanduser(p))
        if not os.path.exists(p2):
            raise FileNotFoundError(f"附件不存在: {p2}")
        if not os.path.isfile(p2):
            raise FileNotFoundError(f"附件不是文件: {p2}")
        out.append(p2)
    return out


def build_message(
    from_email: str,
    to: List[str],
    cc: List[str],
    subject: str,
    body: str,
    attachments: List[str],
) -> EmailMessage:
    if not to:
        raise ValueError("收件人 to 不能为空")

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg.set_content(body)

    for path in attachments:
        filename = os.path.basename(path)
        ctype, encoding = mimetypes.guess_type(path)
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)

        with open(path, "rb") as f:
            data = f.read()
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)

    return msg


def send_via_qq_smtp_ssl(
    from_email: str,
    auth_code: str,
    smtp_host: str,
    smtp_port: int,
    msg: EmailMessage,
    timeout: int = 20,
) -> None:
    """Send an email using QQ SMTP SSL.

    Raises RuntimeError with human-readable message on common failures.
    """

    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=timeout) as server:
            server.login(from_email, auth_code)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        raise RuntimeError(
            "SMTP 认证失败：请确认已开启 QQ 邮箱 SMTP 服务，并使用授权码（非登录密码）。"
        ) from e
    except smtplib.SMTPRecipientsRefused as e:
        refused = (
            ", ".join(sorted(e.recipients.keys()))
            if getattr(e, "recipients", None)
            else str(e)
        )
        raise RuntimeError(f"收件人被服务器拒绝: {refused}") from e
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError) as e:
        raise RuntimeError(
            f"SMTP 连接失败：host={smtp_host} port={smtp_port} timeout={timeout}s。"
            f"可能原因：网络不可达/端口被拦截/DNS 失败/服务器断开连接。detail={e}"
        ) from e
    except smtplib.SMTPException as e:
        raise RuntimeError(f"SMTP 发送失败：detail={e}") from e


def _print_dry_run_summary(
    *,
    from_email: str,
    to_list: List[str],
    cc_list: List[str],
    subject: str,
    body: str,
    attachments: List[str],
    smtp_host: str,
    smtp_port: int,
    timeout: int,
    auth_code_present: bool,
) -> None:
    # 注意：不要输出授权码明文。
    print("[send_email_qq][dry_run] 不连接 SMTP，仅输出邮件摘要")
    print(f"From: {from_email}")
    print(f"To: {', '.join(to_list)}")
    print(f"Cc: {', '.join(cc_list) if cc_list else '(none)'}")
    print(f"Subject: {subject}")
    print(f"Body length: {len(body)}")
    print(f"Attachments ({len(attachments)}):")
    for p in attachments:
        print(f"  - {p}")
    print(f"SMTP: {smtp_host}:{smtp_port} timeout={timeout}s")
    print(f"Auth code: {'(provided)' if auth_code_present else '(missing)'}")


def send_email(
    *,
    to: Union[str, Sequence[str]],
    subject: str,
    body: str,
    cc: Union[None, str, Sequence[str]] = None,
    attachments: Optional[Sequence[str]] = None,
    sender: Optional[str] = None,
    auth_code: Optional[str] = None,
    smtp_host: str = "smtp.qq.com",
    smtp_port: int = 465,
    timeout: int = 20,
    dry_run: bool = False,
) -> Optional[EmailMessage]:
    """Programmatic API (便于其他模块直接调用).

    - dry_run=True 时：仅构建 EmailMessage 并打印摘要，不实际发送；允许不提供 auth_code。
    """

    from_email = (sender or os.getenv(ENV_SENDER) or "").strip()
    code = (auth_code or os.getenv(ENV_AUTH_CODE) or "").strip()

    if not from_email:
        raise ValueError(f"缺少发件人邮箱：请传 sender 或设置环境变量 {ENV_SENDER}")
    if (not code) and (not dry_run):
        raise ValueError(f"缺少授权码：请传 auth_code 或设置环境变量 {ENV_AUTH_CODE}")

    to_list = normalize_emails(to)
    cc_list = normalize_emails(cc)
    att_list = _normalize_attachments(attachments or [])

    msg = build_message(
        from_email=from_email,
        to=to_list,
        cc=cc_list,
        subject=subject,
        body=body,
        attachments=att_list,
    )

    if dry_run:
        _print_dry_run_summary(
            from_email=from_email,
            to_list=to_list,
            cc_list=cc_list,
            subject=subject,
            body=body,
            attachments=att_list,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            timeout=timeout,
            auth_code_present=bool(code),
        )
        return msg

    send_via_qq_smtp_ssl(
        from_email=from_email,
        auth_code=code,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        msg=msg,
        timeout=timeout,
    )
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="通过 QQ 邮箱 SMTP(465/SSL) 发送文本邮件（支持主题、收件人、抄送、可选附件）"
    )

    parser.add_argument(
        "--from_email",
        default=None,
        help=f"发件人 QQ 邮箱，如 123456@qq.com；默认读取环境变量 {ENV_SENDER}",
    )
    parser.add_argument(
        "--auth_code",
        default=None,
        help=f"QQ 邮箱 SMTP 授权码；默认读取环境变量 {ENV_AUTH_CODE}",
    )

    parser.add_argument("--smtp_host", default="smtp.qq.com", help="SMTP 服务器，默认 smtp.qq.com")
    parser.add_argument("--smtp_port", type=int, default=465, help="SMTP 端口，默认 465(SSL)")

    parser.add_argument(
        "--to",
        action="append",
        required=True,
        help="收件人邮箱：可重复指定或逗号分隔，如 --to a@x.com --to b@y.com 或 --to a@x.com,b@y.com",
    )
    parser.add_argument(
        "--cc",
        action="append",
        default=[],
        help="抄送邮箱：可重复指定或逗号分隔，如 --cc c@x.com --cc d@y.com",
    )
    parser.add_argument("--subject", required=True, help="邮件主题")
    parser.add_argument("--body", required=True, help="邮件正文（纯文本）")
    parser.add_argument(
        "--attachment",
        action="append",
        default=[],
        help="附件路径（可重复指定）：--attachment a.txt --attachment b.pdf",
    )
    parser.add_argument("--timeout", type=int, default=20, help="网络超时秒数，默认 20")
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="仅构建并打印邮件摘要，不连接 SMTP；用于参数排错/网络受限环境",
    )

    args = parser.parse_args()

    from_email = (args.from_email or os.getenv(ENV_SENDER) or "").strip()
    code = (args.auth_code or os.getenv(ENV_AUTH_CODE) or "").strip()

    if not from_email:
        raise SystemExit(f"缺少发件人邮箱：请提供 --from_email 或设置环境变量 {ENV_SENDER}")
    if (not code) and (not args.dry_run):
        raise SystemExit(f"缺少授权码：请提供 --auth_code 或设置环境变量 {ENV_AUTH_CODE}")

    to_list = normalize_emails(args.to)
    cc_list = normalize_emails(args.cc)
    if not to_list:
        raise SystemExit("--to 不能为空")

    try:
        attachments = _normalize_attachments(args.attachment)
    except FileNotFoundError as e:
        raise SystemExit(str(e))

    msg = build_message(
        from_email=from_email,
        to=to_list,
        cc=cc_list,
        subject=args.subject,
        body=args.body,
        attachments=attachments,
    )

    if args.dry_run:
        _print_dry_run_summary(
            from_email=from_email,
            to_list=to_list,
            cc_list=cc_list,
            subject=args.subject,
            body=args.body,
            attachments=attachments,
            smtp_host=args.smtp_host,
            smtp_port=args.smtp_port,
            timeout=args.timeout,
            auth_code_present=bool(code),
        )
        print("[send_email_qq][dry_run] 完成")
        return

    try:
        send_via_qq_smtp_ssl(
            from_email=from_email,
            auth_code=code,
            smtp_host=args.smtp_host,
            smtp_port=args.smtp_port,
            msg=msg,
            timeout=args.timeout,
        )
    except RuntimeError as e:
        raise SystemExit(str(e))

    print("[send_email_qq] 邮件发送成功")


if __name__ == "__main__":
    main()
