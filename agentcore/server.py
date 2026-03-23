"""
FastAPI 后端服务 —— 封装 agentcore 的所有功能

启动方式：
  uvicorn agentcore.server:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Set

import mimetypes
import shutil

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .models import PLAN_STORE, SESSION, RunOptions, Plan, PlanStep
from .models import get_user_plan_store, get_user_session
from .skills import load_eligible_skills
from .planner import make_plans
from .executor import execute_plan_structured
from .ui import run_direct_agent, parse_auto_command
from .storage import load_sessions, save_sessions, clear_sessions
from .storage import save_user_sessions, load_user_sessions, clear_user_sessions
from .config import get_provider_config, update_provider_config, set_current_user
from .llm import reset_usage, get_usage
from . import usage_tracker
from . import memory as mem
from .memory import get_user_memory
from . import skill_manager as sm
from . import conversations as conv_store
from .auth import router as auth_router, get_current_user
from . import email_poller

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_sessions()          # 启动时加载全局历史会话（兼容旧数据）
    email_poller.start()     # 启动邮件轮询
    yield
    email_poller.stop()      # 停止邮件轮询
    save_sessions()          # 关闭时保存


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Ran Agent API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth")

# ---------------------------------------------------------------------------
# Per-user session lazy-loading
# ---------------------------------------------------------------------------

_sessions_loaded: Set[str] = set()   # 已加载过会话的 user_id


def _get_user_store(user_id: str) -> Dict[str, Any]:
    """返回该用户的 plan_store、session、memory，并确保会话已从磁盘加载。"""
    ps = get_user_plan_store(user_id)
    if user_id not in _sessions_loaded:
        load_user_sessions(user_id, ps)
        _sessions_loaded.add(user_id)
    return {
        "plan_store": ps,
        "session": get_user_session(user_id),
        "memory": get_user_memory(user_id),
    }


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class RunOptionsModel(BaseModel):
    web_mode: str = "off"
    deep_think: int = 0
    require_citations: bool = False
    max_search_rounds: int = 3


class TaskRequest(BaseModel):
    task: str
    options: Optional[RunOptionsModel] = None
    conv_id: Optional[str] = None


class AutoRequest(BaseModel):
    command: Optional[str] = None
    task: Optional[str] = None
    options: Optional[RunOptionsModel] = None
    conv_id: Optional[str] = None


class ReplyRequest(BaseModel):
    reply: str


class ProviderConfigRequest(BaseModel):
    name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    deep_model: Optional[str] = None


class MemorySetRequest(BaseModel):
    value: str


class SkillCreateRequest(BaseModel):
    name: str
    content: str


class SkillUpdateRequest(BaseModel):
    content: str


class SkillToggleRequest(BaseModel):
    enabled: bool


class SkillReadmeSaveRequest(BaseModel):
    content: str


class ConvCreateRequest(BaseModel):
    title: Optional[str] = ""


class ConvAppendRequest(BaseModel):
    role: str
    text: str


class ConvRenameRequest(BaseModel):
    title: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_history(conv_id: Optional[str], user_id: Optional[str] = None) -> List[Dict]:
    if not conv_id:
        return []
    data = conv_store.get_conversation(conv_id, user_id)
    if not data:
        return []
    history = []
    for m in data.get("messages", []):
        role = m.get("role", "")
        text = m.get("text", "")
        if role == "user":
            history.append({"role": "user", "content": text})
        elif role in ("agent", "assistant"):
            history.append({"role": "assistant", "content": text})
    return history


def _opts(m: Optional[RunOptionsModel]) -> RunOptions:
    if not m:
        return RunOptions()
    return RunOptions(
        web_mode=m.web_mode,          # type: ignore[arg-type]
        deep_think=m.deep_think,
        require_citations=m.require_citations,
        max_search_rounds=m.max_search_rounds,
    )


def _step_dict(s: PlanStep) -> Dict[str, Any]:
    return {
        "id": s.id,
        "title": s.title,
        "instruction": s.instruction,
        "skill_hint": s.skill_hint,
        "status": s.status,
        "output": s.output,
    }


def _plan_dict(p: Plan) -> Dict[str, Any]:
    opts = p.options
    return {
        "id": p.id,
        "title": p.title,
        "goal": p.goal,
        "status": p.status,
        "original_task": p.original_task,
        "current_step_index": p.current_step_index,
        "awaiting_user_input": p.awaiting_user_input,
        "pending_question": p.pending_question,
        "steps": [_step_dict(s) for s in p.steps],
        "options": {
            "web_mode": opts.web_mode if opts else "off",
            "deep_think": opts.deep_think if opts else 0,
            "require_citations": opts.require_citations if opts else False,
            "max_search_rounds": opts.max_search_rounds if opts else 3,
        },
    }


def _exec_result_dict(result, plan_id: str, plan_store: dict, session) -> Dict[str, Any]:
    resp: Dict[str, Any] = {
        "status": result.status,
        "message": result.message,
    }
    if result.need_input:
        ni = result.need_input
        session.set_pending(ni)
        resp["need_input"] = {
            "plan_id": ni.plan_id,
            "step_id": ni.step_id,
            "question": ni.question,
        }
    elif result.status in ("done", "failed"):
        session.clear_pending()

    if plan_id in plan_store:
        resp["plan"] = _plan_dict(plan_store[plan_id])

    return resp


# ---------------------------------------------------------------------------
# Routes — Skills
# ---------------------------------------------------------------------------


@app.get("/api/skills")
def get_skills(_u: dict = Depends(get_current_user)):
    eligible = load_eligible_skills()
    return [
        {"name": s["name"], "description": s["description"], "location": s["location"]}
        for s in eligible
    ]


@app.get("/api/skills/all")
def get_all_skills(_u: dict = Depends(get_current_user)):
    return sm.get_all_skills()


@app.post("/api/skills")
def create_skill(req: SkillCreateRequest, _u: dict = Depends(get_current_user)):
    try:
        return sm.create_skill(req.name, req.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class SkillGenerateRequest(BaseModel):
    name: str = ""
    description: str = ""
    bins: List[str] = []
    env_vars: List[str] = []
    always: bool = True


@app.post("/api/skills/generate")
def generate_skill_content(req: SkillGenerateRequest, _u: dict = Depends(get_current_user)):
    set_current_user(_u["id"])
    try:
        content = sm.generate_skill_md(req.name, req.description, req.bins, req.env_vars, req.always)
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/skills/{name}")
def get_skill(name: str, _u: dict = Depends(get_current_user)):
    detail = sm.get_skill_detail(name)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' 未找到")
    return detail


@app.put("/api/skills/{name}")
def update_skill(name: str, req: SkillUpdateRequest, _u: dict = Depends(get_current_user)):
    try:
        sm.update_skill_content(name, req.content)
        return sm.get_skill_detail(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.patch("/api/skills/{name}/enabled")
def toggle_skill(name: str, req: SkillToggleRequest, _u: dict = Depends(get_current_user)):
    sm.set_skill_enabled(name, req.enabled)
    return {"name": name, "enabled": req.enabled}


@app.delete("/api/skills/{name}")
def delete_skill(name: str, _u: dict = Depends(get_current_user)):
    try:
        sm.delete_skill(name)
        return {"message": f"已删除 skill '{name}'"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/skills/{name}/readme")
def generate_readme(name: str, _u: dict = Depends(get_current_user)):
    try:
        readme = sm.generate_readme(name)
        return {"name": name, "readme": readme}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.put("/api/skills/{name}/readme")
def save_readme(name: str, req: SkillReadmeSaveRequest, _u: dict = Depends(get_current_user)):
    try:
        sm.save_readme(name, req.content)
        return {"name": name, "readme": req.content}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Routes — Plans
# ---------------------------------------------------------------------------


@app.get("/api/plans")
def get_plans(_u: dict = Depends(get_current_user)):
    store = _get_user_store(_u["id"])
    return [_plan_dict(p) for p in store["plan_store"].values()]


@app.get("/api/plans/{plan_id}")
def get_plan(plan_id: str, _u: dict = Depends(get_current_user)):
    store = _get_user_store(_u["id"])
    plan = store["plan_store"].get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"计划不存在: {plan_id}")
    return _plan_dict(plan)


@app.delete("/api/plans/{plan_id}")
def delete_plan(plan_id: str, _u: dict = Depends(get_current_user)):
    store = _get_user_store(_u["id"])
    ps = store["plan_store"]
    if plan_id not in ps:
        raise HTTPException(status_code=404, detail=f"计划不存在: {plan_id}")
    del ps[plan_id]
    save_user_sessions(_u["id"], ps)
    return {"message": "已删除"}


@app.delete("/api/plans")
def delete_all_plans(_u: dict = Depends(get_current_user)):
    store = _get_user_store(_u["id"])
    clear_user_sessions(_u["id"], store["plan_store"])
    return {"message": "已清除所有会话"}


@app.post("/api/plan")
def create_plan(req: TaskRequest, _u: dict = Depends(get_current_user)):
    store = _get_user_store(_u["id"])
    eligible = load_eligible_skills()
    opts = _opts(req.options)
    set_current_user(_u["id"])
    try:
        plans = make_plans(req.task, eligible, options=opts, plan_store=store["plan_store"])
    finally:
        set_current_user(None)
    save_user_sessions(_u["id"], store["plan_store"])
    return [_plan_dict(p) for p in plans]


@app.post("/api/run/{plan_id}")
def run_plan(plan_id: str, _u: dict = Depends(get_current_user)):
    store = _get_user_store(_u["id"])
    ps = store["plan_store"]
    if plan_id not in ps:
        raise HTTPException(status_code=404, detail=f"计划不存在: {plan_id}")
    eligible = load_eligible_skills()
    set_current_user(_u["id"])
    try:
        result = execute_plan_structured(plan_id, eligible, plan_store=ps)
    finally:
        set_current_user(None)
    save_user_sessions(_u["id"], ps)
    return _exec_result_dict(result, plan_id, ps, store["session"])


@app.post("/api/auto")
def auto_run(req: AutoRequest, _u: dict = Depends(get_current_user)):
    store = _get_user_store(_u["id"])
    ps = store["plan_store"]
    sess = store["session"]
    eligible = load_eligible_skills()

    if req.command:
        opts, task = parse_auto_command(f"/auto {req.command}")
    else:
        task = req.task or ""
        opts = _opts(req.options)

    if not task:
        raise HTTPException(status_code=400, detail="task 不能为空")

    history = _load_history(req.conv_id, _u["id"])
    if history:
        ctx_lines = []
        for h in history[-10:]:
            label = "用户" if h["role"] == "user" else "助手"
            ctx_lines.append(f"{label}: {h['content']}")
        task = f"【对话上下文】\n{chr(10).join(ctx_lines)}\n\n【当前任务】\n{task}"

    reset_usage()
    set_current_user(_u["id"])
    try:
        plans = make_plans(task, eligible, options=opts, plan_store=ps)
        results: List[Dict[str, Any]] = []
        for p in plans:
            result = execute_plan_structured(p.id, eligible, plan_store=ps)
            entry = _exec_result_dict(result, p.id, ps, sess)
            results.append(entry)
            if result.status in ("done", "blocked"):
                break
    finally:
        set_current_user(None)

    usage = get_usage()
    usage_tracker.record(_u["id"], usage.get("provider", ""), usage.get("model", ""), usage["input"], usage["output"])
    save_user_sessions(_u["id"], ps)
    return {"plans": [_plan_dict(p) for p in plans], "results": results, "usage": usage}


@app.post("/api/ask")
def ask(req: TaskRequest, _u: dict = Depends(get_current_user)):
    eligible = load_eligible_skills()
    opts = _opts(req.options)
    history = _load_history(req.conv_id, _u["id"])
    reset_usage()
    set_current_user(_u["id"])
    try:
        text = run_direct_agent(req.task, eligible, options=opts, history=history)
    finally:
        set_current_user(None)
    usage = get_usage()
    usage_tracker.record(_u["id"], usage.get("provider", ""), usage.get("model", ""), usage["input"], usage["output"])
    return {"result": text, "usage": usage}


@app.post("/api/reply")
def reply(req: ReplyRequest, _u: dict = Depends(get_current_user)):
    store = _get_user_store(_u["id"])
    ps = store["plan_store"]
    sess = store["session"]
    if not sess.state.pending:
        raise HTTPException(status_code=400, detail="当前没有待补充的任务")
    pending = sess.state.pending
    eligible = load_eligible_skills()
    reset_usage()
    set_current_user(_u["id"])
    try:
        result = execute_plan_structured(pending.plan_id, eligible, resume_reply=req.reply, plan_store=ps)
    finally:
        set_current_user(None)
    usage = get_usage()
    usage_tracker.record(_u["id"], usage.get("provider", ""), usage.get("model", ""), usage["input"], usage["output"])
    save_user_sessions(_u["id"], ps)
    return _exec_result_dict(result, pending.plan_id, ps, sess)


@app.post("/api/cancel")
def cancel(_u: dict = Depends(get_current_user)):
    store = _get_user_store(_u["id"])
    ps = store["plan_store"]
    sess = store["session"]
    if not sess.state.pending:
        raise HTTPException(status_code=400, detail="当前没有待补充的任务")
    pending = sess.state.pending
    plan = ps.get(pending.plan_id)
    if plan and plan.status == "blocked":
        plan.status = "failed"
        plan.awaiting_user_input = False
        plan.pending_question = ""
    sess.clear_pending()
    save_user_sessions(_u["id"], ps)
    return {"message": "已取消当前待补充任务"}


@app.get("/api/session")
def get_session(_u: dict = Depends(get_current_user)):
    store = _get_user_store(_u["id"])
    sess = store["session"]
    if sess.state.pending:
        p = sess.state.pending
        return {"pending": {"plan_id": p.plan_id, "step_id": p.step_id, "question": p.question}}
    return {"pending": None}


# ---------------------------------------------------------------------------
# Routes — Memory (per-user)
# ---------------------------------------------------------------------------


@app.get("/api/memory")
def get_memory(_u: dict = Depends(get_current_user)):
    return _get_user_store(_u["id"])["memory"].all_entries()


@app.put("/api/memory/{key}")
def set_memory(key: str, req: MemorySetRequest, _u: dict = Depends(get_current_user)):
    _get_user_store(_u["id"])["memory"].set_value(key, req.value)
    return {"key": key, "value": req.value}


@app.delete("/api/memory/{key}")
def delete_memory(key: str, _u: dict = Depends(get_current_user)):
    if not _get_user_store(_u["id"])["memory"].delete(key):
        raise HTTPException(status_code=404, detail=f"key '{key}' 不存在")
    return {"message": f"已删除 {key!r}"}


@app.delete("/api/memory")
def clear_memory(_u: dict = Depends(get_current_user)):
    _get_user_store(_u["id"])["memory"].clear()
    return {"message": "已清空所有记忆"}


@app.get("/api/usage")
def get_user_usage(_u: dict = Depends(get_current_user)):
    return usage_tracker.get_stats(_u["id"])


@app.get("/api/download")
def download_file(path: str, _u: dict = Depends(get_current_user)):
    """下载 agent 生成的文件，仅限 WORKSPACE 目录内。"""
    from pathlib import Path as _Path
    from .config import WORKSPACE_ENV
    try:
        p = _Path(path).resolve()
        workspace = _Path(WORKSPACE_ENV).resolve()
        if not str(p).startswith(str(workspace)):
            raise HTTPException(status_code=403, detail="只允许下载 workspace 目录内的文件")
        if not p.exists() or not p.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    media_type, _ = mimetypes.guess_type(str(p))
    return FileResponse(str(p), filename=p.name, media_type=media_type or "application/octet-stream")


# ---------------------------------------------------------------------------
# Routes — Provider Config (per-user via /api/auth/user-config)
# 保留全局 /api/config 用于系统级配置（仅用管理员场景）
# ---------------------------------------------------------------------------


@app.get("/api/config")
def get_config(provider: Optional[str] = None, _u: dict = Depends(get_current_user)):
    try:
        prov = get_provider_config(provider)
        key = prov.get("api_key", "")
        prov["api_key"] = f"****{key[-4:]}" if len(key) > 4 else "****"
        return prov
    except RuntimeError as e:
        return {"name": provider or "未配置", "error": str(e)}


@app.post("/api/config")
def update_config(req: ProviderConfigRequest, _u: dict = Depends(get_current_user)):
    updates: Dict[str, Any] = {"name": req.name}
    if req.api_key:
        updates["api_key"] = req.api_key
    if req.base_url is not None:
        updates["base_url"] = req.base_url
    if req.model:
        updates["model"] = req.model
    if req.deep_model:
        updates["deep_model"] = req.deep_model
    update_provider_config(updates)
    return {"message": "配置已更新"}


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


@app.get("/api/conversations")
def get_conversations(_u: dict = Depends(get_current_user)):
    return conv_store.list_conversations(_u["id"])


@app.post("/api/conversations")
def new_conversation(req: ConvCreateRequest, _u: dict = Depends(get_current_user)):
    return conv_store.create_conversation(req.title or "", _u["id"])


@app.get("/api/conversations/{conv_id}")
def get_conv(conv_id: str, _u: dict = Depends(get_current_user)):
    data = conv_store.get_conversation(conv_id, _u["id"])
    if data is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return data


@app.delete("/api/conversations/{conv_id}")
def del_conversation(conv_id: str, _u: dict = Depends(get_current_user)):
    if not conv_store.delete_conversation(conv_id, _u["id"]):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"message": "已删除"}


@app.post("/api/conversations/{conv_id}/messages")
def add_message(conv_id: str, req: ConvAppendRequest, _u: dict = Depends(get_current_user)):
    msg_id = conv_store.append_message(conv_id, req.role, req.text, _u["id"])
    if msg_id is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"message": "已追加", "id": msg_id}


@app.delete("/api/conversations/{conv_id}/messages/{msg_id}")
def del_message(conv_id: str, msg_id: str, _u: dict = Depends(get_current_user)):
    deleted = conv_store.delete_message(conv_id, msg_id, _u["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="消息不存在")
    return {"deleted": deleted}


@app.patch("/api/conversations/{conv_id}")
def patch_conversation(conv_id: str, req: ConvRenameRequest, _u: dict = Depends(get_current_user)):
    if not conv_store.rename_conversation(conv_id, req.title, _u["id"]):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"message": "已更新"}


@app.get("/api/current-model")
def current_model(_u: dict = Depends(get_current_user)):
    set_current_user(_u["id"])
    try:
        cfg = get_provider_config()
        return {"provider": cfg["name"], "model": cfg["model"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), _u: dict = Depends(get_current_user)):
    from .config import DATA_DIR
    MAX_SIZE = 20 * 1024 * 1024  # 20 MB
    upload_dir = DATA_DIR / "users" / _u["id"] / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    from pathlib import Path as _Path
    safe_name = _Path(file.filename or "upload").name or "upload"
    dest = upload_dir / safe_name
    # Avoid overwriting
    stem, suffix = dest.stem, dest.suffix
    i = 1
    while dest.exists():
        dest = upload_dir / f"{stem}_{i}{suffix}"
        i += 1

    size = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(65536):
            size += len(chunk)
            if size > MAX_SIZE:
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="文件超过 20MB 限制")
            f.write(chunk)

    mime = mimetypes.guess_type(str(dest))[0] or "application/octet-stream"
    return {"name": dest.name, "path": str(dest), "size": size, "type": mime}
