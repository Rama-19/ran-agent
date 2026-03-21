"""会话持久化 —— 将 PLAN_STORE 保存到磁盘（JSON）。"""
import json
from pathlib import Path

from .models import PLAN_STORE, Plan, PlanStep, RunOptions
from .config import DATA_DIR

SESSIONS_FILE = DATA_DIR / "sessions.json"


# ── 序列化 / 反序列化 ──────────────────────────────────────────────────────────


def _plan_to_dict(p: Plan) -> dict:
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
        "steps": [
            {
                "id": s.id,
                "title": s.title,
                "instruction": s.instruction,
                "skill_hint": s.skill_hint,
                "status": s.status,
                "output": s.output,
            }
            for s in p.steps
        ],
        "options": {
            "web_mode": opts.web_mode,
            "deep_think": opts.deep_think,
            "require_citations": opts.require_citations,
            "max_search_rounds": opts.max_search_rounds,
        } if opts else None,
    }


def _dict_to_plan(d: dict) -> Plan:
    steps = [
        PlanStep(
            id=s["id"],
            title=s["title"],
            instruction=s["instruction"],
            skill_hint=s.get("skill_hint", ""),
            status=s.get("status", "pending"),
            output=s.get("output", ""),
        )
        for s in d.get("steps", [])
    ]
    opts_d = d.get("options")
    opts = RunOptions(
        web_mode=opts_d["web_mode"],
        deep_think=opts_d["deep_think"],
        require_citations=opts_d["require_citations"],
        max_search_rounds=opts_d["max_search_rounds"],
    ) if opts_d else None
    return Plan(
        id=d["id"],
        title=d["title"],
        goal=d["goal"],
        status=d.get("status", "pending"),
        original_task=d.get("original_task", ""),
        current_step_index=d.get("current_step_index", 0),
        awaiting_user_input=d.get("awaiting_user_input", False),
        pending_question=d.get("pending_question", ""),
        steps=steps,
        options=opts,
    )


# ── 公开 API ──────────────────────────────────────────────────────────────────


def save_sessions() -> None:
    """把当前 PLAN_STORE 写入磁盘。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {pid: _plan_to_dict(p) for pid, p in PLAN_STORE.items()}
    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_sessions() -> None:
    """从磁盘加载历史会话到 PLAN_STORE。"""
    if not SESSIONS_FILE.exists():
        return
    try:
        with open(SESSIONS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        for pid, d in data.items():
            PLAN_STORE[pid] = _dict_to_plan(d)
        print(f"[storage] 已加载 {len(data)} 个历史会话")
    except Exception as e:
        print(f"[storage] 加载会话失败: {e}")


def clear_sessions() -> None:
    """清空内存中的会话并删除文件。"""
    PLAN_STORE.clear()
    if SESSIONS_FILE.exists():
        SESSIONS_FILE.unlink()


# ── Per-user session persistence ──────────────────────────────────────────────

def _user_sessions_path(user_id: str) -> Path:
    return DATA_DIR / "users" / user_id / "sessions.json"


def save_user_sessions(user_id: str, plan_store: dict) -> None:
    """将指定用户的 plan_store 写入磁盘。"""
    path = _user_sessions_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {pid: _plan_to_dict(p) for pid, p in plan_store.items()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_user_sessions(user_id: str, plan_store: dict) -> None:
    """从磁盘加载指定用户的会话到 plan_store（就地填充）。"""
    path = _user_sessions_path(user_id)
    if not path.exists():
        return
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for pid, d in data.items():
            plan_store[pid] = _dict_to_plan(d)
    except Exception as e:
        print(f"[storage] 加载用户 {user_id} 会话失败: {e}")


def clear_user_sessions(user_id: str, plan_store: dict) -> None:
    """清空指定用户的内存会话并删除文件。"""
    plan_store.clear()
    path = _user_sessions_path(user_id)
    if path.exists():
        path.unlink()
