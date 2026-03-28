# Ran Agent

> A self-hosted AI Agent platform with skill-based task planning, multi-agent group chat, multi-user auth, and a modern web UI.

**Repositories:** [Gitee](https://gitee.com/mayangyu/ran-agent) · [GitHub](https://github.com/Rama-19/ran-agent)

**Ran Agent** lets you define reusable *Skills*, describe goals in plain language, and watch the agent autonomously plan and execute multi-step tasks — all running on your own infrastructure.

---

## ✨ Features

| Category | Highlights |
|----------|-----------|
| **Task Engine** | Auto-plan → execute, Plan-only, or Direct-ask modes |
| **Multi-Agent Group Chat** | Spin up a group of role-based agents (coordinator, researcher, executor, reviewer, summarizer, expert, custom) that collaborate in a shared conversation |
| **Skill System** | Drop a `SKILL.md` in your workspace — the agent reads it and decides when to use the skill |
| **Multi-user** | Email + password registration with SMTP verification codes; per-user sessions, memory, and config |
| **Auth** | JWT authentication, password change, forgot/reset-password flow; activate account via email link |
| **Memory** | Persistent key-value store injected into every agent context, isolated per user |
| **Providers** | OpenAI (Responses API) and Anthropic (Messages API), per-user provider config override |
| **Token Usage** | Real-time token consumption display per response |
| **Tools** | File read/write (with download button), shell exec, HTTP requests, directory listing, web search |
| **Web UI** | Conversations (copy/delete), plan viewer, memory manager, skill manager, group chat — dark-themed React SPA |

---

## 🗂 Project Structure

```
ran-agent/
├── agentcore/              # Python backend (FastAPI)
│   ├── server.py           # REST API (all routes)
│   ├── auth.py             # JWT auth, user management, SMTP verification
│   ├── agent.py            # Agent execution engine
│   ├── llm.py              # Unified LLM client (OpenAI / Anthropic)
│   ├── planner.py          # Task planner (LLM → structured plan)
│   ├── executor.py         # Plan executor (step-by-step)
│   ├── skills.py           # Skill discovery and parsing
│   ├── skill_manager.py    # Skill CRUD + README generation
│   ├── tools.py            # Tool implementations
│   ├── memory.py           # Per-user key-value memory
│   ├── conversations.py    # Per-user conversation persistence
│   ├── storage.py          # Per-user session persistence
│   ├── email_sender.py     # Branded HTML email (SMTP)
│   ├── models.py           # Data models
│   └── config.py           # Config management (per-user + global)
├── web/                    # React frontend (Vite)
│   ├── src/
│   │   ├── App.jsx         # Main app with auth gate
│   │   ├── api.js          # API client (auto-injects JWT)
│   │   └── components/
│   │       ├── AuthModal.jsx       # Login / Register / Forgot-password
│   │       ├── SettingsModal.jsx   # Provider config + change password + SMTP
│   │       ├── ConversationPanel.jsx
│   │       ├── GroupChatPanel.jsx  # Multi-agent group chat
│   │       ├── CreateGroupModal.jsx
│   │       ├── SkillPanel.jsx
│   │       ├── SkillManager.jsx
│   │       ├── PlanCard.jsx
│   │       ├── MemoryPanel.jsx
│   │       └── BlockedBanner.jsx
│   └── vite.config.js      # Dev proxy → backend :8000
├── workspace/
│   └── skills/             # Drop your custom Skills here
└── data/                   # Runtime data (gitignored)
    └── users/{id}/
        ├── conversations/
        ├── sessions.json
        ├── memory.json
        └── config.json
```

---

## 🚀 Quick Start

### 1. Clone & install

```bash
git clone https://github.com/Rama-19/ran-agent.git
cd ran-agent

# Backend
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
pip install fastapi "uvicorn[standard]" openai anthropic python-dotenv \
            pyyaml python-jose[cryptography] bcrypt

# Frontend
cd web && npm install
```

### 2. Configure

Create `.env` in the project root:

```env
# LLM Provider (choose one)
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

# Optional: override workspace path
# WORKSPACE=/path/to/workspace

# Optional: override JWT secret (auto-generated if omitted)
# JWT_SECRET=your-secret-here
```

You can also configure the LLM provider and SMTP settings from the web UI after logging in.

### 3. Start

```bash
# Terminal 1 — backend
uvicorn agentcore.server:app --reload --port 8000

# Terminal 2 — frontend dev server
cd web && npm run dev
```

Open **http://localhost:5173** — register an account and start chatting.

> **Production build**: `cd web && npm run build` — serves static files from `web/dist/`.

---

## 👥 Multi-Agent Group Chat

The **Group Chat** tab lets you assemble a team of agents with distinct roles that collaborate to solve a task:

| Role | Icon | Purpose |
|------|------|---------|
| coordinator | 🎯 | Orchestrates the conversation and delegates sub-tasks |
| researcher | 🔍 | Gathers information and context |
| executor | ⚙️ | Runs code and commands |
| reviewer | 🔎 | Checks outputs for correctness |
| summarizer | 📝 | Distills findings into a final answer |
| expert | 🎓 | Provides domain-specific knowledge |
| custom | 🤖 | Any user-defined role |

Create a group, describe the task, and watch agents take turns — each response is shown in a colour-coded bubble.

---

## 🧩 Writing a Skill

Create a directory under `workspace/skills/my_skill/` with a `SKILL.md`:

```markdown
---
name: my_skill
description: Brief description of what this skill does
bins:
  - python           # required executables (used for eligibility check)
envVars:
  - MY_API_KEY       # required env vars (skill hidden if unset)
alwaysLoad: false
---

## How to use

Detailed instructions for the agent — what commands to run, what arguments to
pass, what output format to expect, etc.
```

The agent reads `SKILL.md` before deciding whether to use the skill. Manage all skills from the **⚡ Skills** tab in the UI.

---

## 🔌 API Reference

All endpoints require `Authorization: Bearer <token>` except the auth endpoints.

### Auth (`/api/auth/...`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Send verification code |
| POST | `/api/auth/verify` | Verify code → create account → JWT |
| POST | `/api/auth/login` | Login → JWT |
| GET | `/api/auth/me` | Current user info |
| POST | `/api/auth/change-password` | Change password |
| POST | `/api/auth/forgot-password` | Send reset code |
| POST | `/api/auth/reset-password` | Reset password with code |
| GET/POST | `/api/auth/user-config` | Per-user LLM provider config |
| GET/POST | `/api/auth/smtp-config` | SMTP configuration |

### Agent
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auto` | Auto-plan + execute |
| POST | `/api/plan` | Generate plans only |
| POST | `/api/run/{plan_id}` | Execute a plan |
| POST | `/api/ask` | Direct execution (skip planner) |
| POST | `/api/reply` | Resume a blocked plan |
| GET | `/api/plans` | List plans |
| GET | `/api/session` | Current session state |

### Memory / Skills / Conversations
Standard CRUD — see `/docs` (FastAPI auto-docs) after starting the backend.

---

## 🔒 Security Notes

- Passwords are hashed with bcrypt
- JWT tokens expire after 7 days
- Each user's data (conversations, plans, memory, config) is fully isolated
- `.env` and `data/` are gitignored — never commit secrets

---

## License

MIT
