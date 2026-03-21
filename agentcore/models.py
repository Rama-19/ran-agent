from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .config import WebMode, get_provider_config


@dataclass
class PlanStep:
    id: str
    title: str
    instruction: str
    skill_hint: str = ""
    status: str = "pending"   # pending/running/done/blocked
    output: str = ""


@dataclass
class RunOptions:
    web_mode: WebMode = "off"
    deep_think: int = 0          # 0=关闭, 1=轻度, 2=中度, 3=重度
    require_citations: bool = False
    max_search_rounds: int = 3


@dataclass
class Plan:
    id: str
    title: str
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    status: str = "pending"   # pending/running/done/blocked
    original_task: str = ""
    current_step_index: int = 0
    awaiting_user_input: bool = False
    pending_question: str = ""
    options: RunOptions | None = None


@dataclass
class NeedInput:
    plan_id: str
    step_id: str
    question: str


@dataclass
class PlanExecResult:
    status: str   # done / blocked / failed
    message: str
    need_input: Optional[NeedInput] = None


@dataclass
class PendingContinuation:
    plan_id: str
    step_id: str
    question: str


@dataclass
class SessionState:
    pending: Optional[PendingContinuation] = None


class SessionManager:
    def __init__(self):
        self.state = SessionState()

    def set_pending(self, need_input: NeedInput):
        self.state.pending = PendingContinuation(
            plan_id=need_input.plan_id,
            step_id=need_input.step_id,
            question=need_input.question
        )

    def clear_pending(self):
        self.state.pending = None


SESSION = SessionManager()

PLAN_STORE: Dict[str, Plan] = {}

# ── Per-user stores ───────────────────────────────────────────────────────────
_user_plan_stores: Dict[str, Dict[str, "Plan"]] = {}
_user_sessions: Dict[str, SessionManager] = {}


def get_user_plan_store(user_id: str) -> Dict[str, "Plan"]:
    if user_id not in _user_plan_stores:
        _user_plan_stores[user_id] = {}
    return _user_plan_stores[user_id]


def get_user_session(user_id: str) -> SessionManager:
    if user_id not in _user_sessions:
        _user_sessions[user_id] = SessionManager()
    return _user_sessions[user_id]


def normalize_options(options: Optional[RunOptions]) -> RunOptions:
    return options if options else RunOptions()


def select_model(options: Optional[RunOptions] = None) -> str:
    opts = normalize_options(options)
    prov = get_provider_config()
    return prov["deep_model"] if opts.deep_think >= 2 else prov["model"]


def pick_reasoning_effort(options: Optional[RunOptions] = None) -> Optional[str]:
    opts = normalize_options(options)
    mapping = {0: None, 1: "low", 2: "medium", 3: "high"}
    return mapping.get(opts.deep_think, "medium")


def get_agent_round_limit(options: Optional[RunOptions] = None, base: int = 8) -> int:
    opts = normalize_options(options)
    return base + opts.deep_think * 4
