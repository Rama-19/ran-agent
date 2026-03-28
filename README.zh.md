# Ran Agent

> 自托管 AI Agent 平台，支持技能驱动的任务规划、多 Agent 群聊、多用户认证与现代化 Web 界面。

**仓库地址：** [Gitee](https://gitee.com/mayangyu/ran-agent)（主要）· [GitHub](https://github.com/Rama-19/ran-agent)

**Ran Agent** 让你定义可复用的*技能（Skills）*，用自然语言描述目标，Agent 将自动规划并逐步执行多步任务——完全运行在你自己的基础设施上。

---

## ✨ 功能特性

| 类别 | 亮点 |
|------|------|
| **任务引擎** | 自动规划→执行、仅规划、直接问答三种模式 |
| **多 Agent 群聊** | 创建包含多个角色（协调者、研究员、执行者、审阅者、总结者、专家、自定义）的 Agent 群组，协作完成复杂任务 |
| **技能系统** | 在工作区放入 `SKILL.md`，Agent 自动读取并判断何时调用 |
| **多用户** | 邮箱+密码注册，SMTP 验证码；支持邮件链接激活账号；每用户独立会话、记忆与配置 |
| **认证** | JWT 鉴权、修改密码、忘记/重置密码流程 |
| **记忆** | 持久化键值存储，注入每次 Agent 上下文，按用户隔离 |
| **模型提供商** | 支持 OpenAI（Responses API）和 Anthropic（Messages API），可按用户覆盖配置 |
| **Token 用量** | 每次响应实时显示 Token 消耗量 |
| **工具** | 文件读写（支持下载按钮）、Shell 命令、HTTP 请求、目录列表、网页搜索 |
| **Web UI** | 对话管理（支持复制/删除）、计划查看、记忆管理、技能管理、Agent 群聊——深色主题 React SPA |

---

## 🗂 项目结构

```
ran-agent/
├── agentcore/              # Python 后端（FastAPI）
│   ├── server.py           # REST API（所有路由）
│   ├── auth.py             # JWT 认证、用户管理、SMTP 验证
│   ├── agent.py            # Agent 执行引擎
│   ├── llm.py              # 统一 LLM 客户端（OpenAI / Anthropic）
│   ├── planner.py          # 任务规划器（LLM → 结构化计划）
│   ├── executor.py         # 计划执行器（逐步执行）
│   ├── skills.py           # 技能发现与解析
│   ├── skill_manager.py    # 技能增删改查 + README 生成
│   ├── tools.py            # 工具实现
│   ├── memory.py           # 按用户键值记忆
│   ├── conversations.py    # 按用户对话持久化
│   ├── storage.py          # 按用户会话持久化
│   ├── email_sender.py     # 品牌化 HTML 邮件（SMTP）
│   ├── models.py           # 数据模型
│   └── config.py           # 配置管理（按用户 + 全局）
├── web/                    # React 前端（Vite）
│   ├── src/
│   │   ├── App.jsx         # 主应用（含认证门控）
│   │   ├── api.js          # API 客户端（自动注入 JWT）
│   │   └── components/
│   │       ├── AuthModal.jsx       # 登录 / 注册 / 忘记密码
│   │       ├── SettingsModal.jsx   # 模型配置 + 修改密码 + SMTP
│   │       ├── ConversationPanel.jsx
│   │       ├── GroupChatPanel.jsx  # 多 Agent 群聊
│   │       ├── CreateGroupModal.jsx
│   │       ├── SkillPanel.jsx
│   │       ├── SkillManager.jsx
│   │       ├── PlanCard.jsx
│   │       ├── MemoryPanel.jsx
│   │       └── BlockedBanner.jsx
│   └── vite.config.js      # 开发代理 → 后端 :8000
├── workspace/
│   └── skills/             # 在此放置自定义技能
└── data/                   # 运行时数据（已加入 .gitignore）
    └── users/{id}/
        ├── conversations/
        ├── sessions.json
        ├── memory.json
        └── config.json
```

---

## 🚀 快速开始

### 1. 克隆并安装依赖

```bash
git clone https://gitee.com/mayangyu/ran-agent.git
cd ran-agent

# 后端
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
pip install fastapi "uvicorn[standard]" openai anthropic python-dotenv \
            pyyaml python-jose[cryptography] bcrypt

# 前端
cd web && npm install
```

### 2. 配置

在项目根目录创建 `.env` 文件：

```env
# LLM 提供商（选其一）
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

# 可选：覆盖工作区路径
# WORKSPACE=/path/to/workspace

# 可选：覆盖 JWT 密钥（不填则自动生成）
# JWT_SECRET=your-secret-here
```

也可在登录后通过 Web UI 配置 LLM 提供商和 SMTP 设置。

### 3. 启动

```bash
# 终端 1 — 后端
venv/Scripts/python.exe -m uvicorn agentcore.server:app --reload --port 8000

# 终端 2 — 前端开发服务器
cd web && npm run dev
```

打开 **http://localhost:5173**，注册账号后即可开始使用。

> **生产构建**：`cd web && npm run build`，静态文件输出至 `web/dist/`。

---

## 👥 多 Agent 群聊

**群聊**标签页允许你组建一支由不同角色 Agent 构成的团队，协作解决复杂任务：

| 角色 | 图标 | 职责 |
|------|------|------|
| coordinator（协调者） | 🎯 | 统筹对话流程，分配子任务 |
| researcher（研究员） | 🔍 | 收集信息与背景资料 |
| executor（执行者） | ⚙️ | 运行代码与命令 |
| reviewer（审阅者） | 🔎 | 检查输出结果的正确性 |
| summarizer（总结者） | 📝 | 将结论提炼为最终答案 |
| expert（专家） | 🎓 | 提供特定领域的专业知识 |
| custom（自定义） | 🤖 | 用户自定义角色 |

创建群组、描述任务，观察各 Agent 轮番发言——每条回复以颜色区分的气泡展示。

---

## 🧩 编写技能

在 `workspace/skills/my_skill/` 下创建目录，并添加 `SKILL.md`：

```markdown
---
name: my_skill
description: 该技能的简要描述
bins:
  - python           # 依赖的可执行程序（用于可用性检查）
envVars:
  - MY_API_KEY       # 依赖的环境变量（未设置时技能不可见）
alwaysLoad: false
---

## 使用说明

向 Agent 提供详细说明——应运行哪些命令、传入哪些参数、期望的输出格式等。
```

Agent 在决定是否使用该技能前会读取 `SKILL.md`。所有技能可在 UI 的 **⚡ 技能** 标签页中管理。

---

## 🔌 API 参考

除认证接口外，所有接口均需携带 `Authorization: Bearer <token>`。

### 认证（`/api/auth/...`）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 发送验证码 |
| POST | `/api/auth/verify` | 验证码校验 → 创建账号 → 返回 JWT |
| POST | `/api/auth/login` | 登录 → 返回 JWT |
| GET | `/api/auth/me` | 当前用户信息 |
| POST | `/api/auth/change-password` | 修改密码 |
| POST | `/api/auth/forgot-password` | 发送重置验证码 |
| POST | `/api/auth/reset-password` | 使用验证码重置密码 |
| GET/POST | `/api/auth/user-config` | 按用户 LLM 提供商配置 |
| GET/POST | `/api/auth/smtp-config` | SMTP 配置 |

### Agent
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auto` | 自动规划 + 执行 |
| POST | `/api/plan` | 仅生成计划 |
| POST | `/api/run/{plan_id}` | 执行指定计划 |
| POST | `/api/ask` | 直接执行（跳过规划器） |
| POST | `/api/reply` | 恢复被阻塞的计划 |
| GET | `/api/plans` | 列出所有计划 |
| GET | `/api/session` | 当前会话状态 |

### 记忆 / 技能 / 对话
标准 CRUD 接口——启动后端后访问 `/docs`（FastAPI 自动文档）查看详情。

---

## 🔒 安全说明

- 密码使用 bcrypt 加密存储
- JWT Token 有效期 7 天
- 每个用户的数据（对话、计划、记忆、配置）完全隔离
- `.env` 和 `data/` 已加入 `.gitignore`，请勿提交敏感信息

---

## 许可证

MIT
