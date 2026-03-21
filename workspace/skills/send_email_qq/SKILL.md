---
name: send_email_qq
description: 通过 QQ 邮箱 SMTP(465/SSL) 发送文本邮件（支持主题、收件人、抄送、可选附件）
metadata: '{"openclaw": {"always": true}}'
---

# send_email_qq

## 1. 功能

使用 QQ 邮箱的 **SMTP over SSL**（默认 `smtp.qq.com:465`）发送邮件。

支持：
- 纯文本正文（text/plain）
- 主题（Subject）
- 多收件人（To）
- 抄送（Cc，可选）
- 多附件（可选）
- **dry-run（不连 SMTP，仅构建并打印邮件摘要）**

> 本 skill 通过 `smtplib.SMTP_SSL` 连接并登录发送，不依赖浏览器。

## 2. 使用前准备（QQ 邮箱设置）

在 QQ 邮箱网页端设置中：
1) **开启 SMTP/IMAP 服务**（常见入口：设置 → 账户/邮箱设置 → POP3/IMAP/SMTP 服务）
2) 生成并使用 **“授权码”**（也叫客户端专用密码），**不要使用 QQ 邮箱登录密码**。

如果未开启服务或授权码不对，通常会报认证失败（login failed / authentication failed）。

## 3. 安全提示（非常重要）

- **不要在日志/控制台输出授权码 `auth_code`**（包括异常信息、调试打印、截图分享）。
- **不要把授权码写进代码仓库**；推荐使用环境变量或安全的密钥管理方式。
- 命令行直接传 `--auth_code` 可能会被：
  - shell 历史记录保存
  - 进程列表（某些系统上）可见
  因此更推荐使用环境变量 `QQ_EMAIL_AUTH_CODE`。

## 4. 参数说明

脚本支持：
- **命令行参数传入**；或
- 从 **环境变量**读取默认值（更安全）。

### 4.1 环境变量

- `QQ_EMAIL_SENDER`：默认发件人邮箱（例如 `123456@qq.com`）
- `QQ_EMAIL_AUTH_CODE`：默认 SMTP 授权码（不是登录密码）

当命令行未提供 `--from_email` / `--auth_code` 时，会尝试读取上述环境变量。

### 4.2 命令行参数

#### SMTP/账号

| 参数 | 说明 | 必填 |
|---|---|---|
| `--from_email` | 发件人 QQ 邮箱地址；未提供则读 `QQ_EMAIL_SENDER` | 否（建议提供其一） |
| `--auth_code` | QQ 邮箱 SMTP 授权码；未提供则读 `QQ_EMAIL_AUTH_CODE` | 否（建议提供其一） |
| `--smtp_host` | SMTP 服务器，默认 `smtp.qq.com` | 否 |
| `--smtp_port` | SMTP 端口，默认 `465`（SSL） | 否 |
| `--timeout` | 网络超时秒数，默认 20 | 否 |
| `--dry_run` | **仅构建并打印邮件摘要，不连接 SMTP**（用于排错/网络受限环境）；dry-run 下 `--auth_code` 可不提供 | 否 |

#### 邮件内容

| 参数 | 说明 | 必填 |
|---|---|---|
| `--to` | 收件人邮箱：可重复指定或逗号分隔 | 是 |
| `--cc` | 抄送邮箱：可重复指定或逗号分隔 | 否 |
| `--subject` | 邮件主题 | 是 |
| `--body` | 邮件正文（纯文本） | 是 |
| `--attachment` | 附件路径：可重复指定 | 否 |

## 5. 附件路径要求与校验规则

- 支持 **绝对路径** 或 **相对路径**：
  - 相对路径以“运行命令时的当前工作目录（cwd）”为基准解析。
- 发送前会做基本校验：
  - 路径必须存在
  - 必须是文件（不能是目录）
  - 不存在/非法会直接报错并中止发送

示例（Windows 绝对路径）：
- `--attachment "C:\\data\\report.pdf"`

示例（相对路径）：
- `--attachment "./report.pdf"`

## 6. 使用示例（不包含真实密码/授权码）

### 6.1 直接传参发送（不推荐长期使用，避免泄露）

```bash
python send_email_qq.py \
  --from_email "123456@qq.com" \
  --auth_code "YOUR_QQ_SMTP_AUTH_CODE" \
  --to "to1@example.com,to2@example.com" \
  --subject "测试邮件" \
  --body "这是一封通过 QQ SMTP(SSL 465) 发送的测试邮件。"
```

### 6.2 带抄送与多个附件

```bash
python send_email_qq.py \
  --from_email "123456@qq.com" \
  --auth_code "YOUR_QQ_SMTP_AUTH_CODE" \
  --to "to@example.com" \
  --cc "cc1@example.com,cc2@example.com" \
  --subject "日报" \
  --body "见附件。" \
  --attachment "./report.txt" \
  --attachment "./report.pdf"
```

### 6.3 使用环境变量（推荐）

Windows（PowerShell / CMD）：

```bat
set QQ_EMAIL_SENDER=123456@qq.com
set QQ_EMAIL_AUTH_CODE=YOUR_QQ_SMTP_AUTH_CODE
python send_email_qq.py --to "to@example.com" --subject "hello" --body "hi"
```

macOS / Linux：

```bash
export QQ_EMAIL_SENDER="123456@qq.com"
export QQ_EMAIL_AUTH_CODE="YOUR_QQ_SMTP_AUTH_CODE"
python send_email_qq.py --to "to@example.com" --subject "hello" --body "hi"
```

### 6.4 dry-run（不连 SMTP，仅检查参数/附件/收件人拼装）

```bat
set QQ_EMAIL_SENDER=123456@qq.com
python send_email_qq.py --to "to@example.com" --subject "hello" --body "hi" --dry_run
```

> dry-run 模式下不会登录 SMTP，因此 `QQ_EMAIL_AUTH_CODE` / `--auth_code` 可不提供。

## 7. Python 方式调用（可选）

如果你在代码中使用：

```python
from send_email_qq import send_email

# 实际发送
send_email(
    sender="123456@qq.com",
    auth_code="YOUR_QQ_SMTP_AUTH_CODE",
    to=["to@example.com"],
    subject="hello",
    body="hi",
    cc=["cc@example.com"],
    attachments=["./report.pdf"],
)

# dry-run（不连 SMTP）
send_email(
    sender="123456@qq.com",
    to="to@example.com",
    subject="hello",
    body="hi",
    dry_run=True,
)
```

## 8. 常见问题排查

- **认证失败**：确认已开启 SMTP/IMAP 服务，并且使用的是“授权码”（不是登录密码）。
- **收件人被拒绝 / refused**：确认邮箱地址格式正确，或收件方服务器策略限制。
- **附件找不到**：检查路径是否正确；相对路径与当前工作目录是否一致。
- **连接失败**：检查网络是否允许访问 `smtp.qq.com:465`（部分内网/CI 环境会拦截 465 端口）；可先用 `--dry_run` 验证参数拼装无误。
