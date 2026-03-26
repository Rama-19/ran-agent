"""
多 Agent 协作引擎

流程：
  用户输入 → 协调者 (Coordinator)
    → 输出调度计划 JSON (dispatch)
    → 逐个调用各 agent (researcher / executor / reviewer / ...)
    → 总结者 (Summarizer) 整合所有输出
    → 最终回复
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# 内置角色模板
# ────────────────────────────────────────────────────────────────────────────

BUILTIN_ROLES = {
    "coordinator": {
        "name": "协调者",
        "description": "分解大任务、制定调度计划、管理整体流程",
        "system_prompt": (
            "你是一个专业的任务协调者（Coordinator）。你的职责是：\n"
            "1. 分析用户的请求，理解其核心目标\n"
            "2. 将复杂任务拆解为子任务，分配给最合适的专业 agent\n"
            "3. 制定清晰的执行顺序\n\n"
            "你必须以如下 JSON 格式输出调度计划（不加代码块标记）：\n"
            "{\n"
            '  "thinking": "（你对任务的分析）",\n'
            '  "dispatch": [\n'
            '    {"agent_role": "researcher", "task": "具体子任务描述"},\n'
            '    {"agent_role": "executor", "task": "具体子任务描述"}\n'
            "  ]\n"
            "}\n\n"
            "如果任务非常简单，无需其他 agent，可以 dispatch 为空数组，\n"
            '并加上 "direct": "你的直接回答" 字段。\n\n'
            "可用 agent 角色：{available_roles}\n"
            "注意：只调度群组中实际存在的 agent 角色。"
        ),
    },
    "researcher": {
        "name": "研究员",
        "description": "上网搜索、收集数据、查询知识库",
        "system_prompt": (
            "你是一个专业研究员（Researcher）。你的职责是：\n"
            "1. 根据给定的子任务，搜索和收集相关信息\n"
            "2. 分析和整理信息，去除噪音\n"
            "3. 提供清晰、有据可查的研究结果\n\n"
            "你拥有以下工具：网络搜索、文件读取、执行命令。\n"
            "请先思考需要哪些信息，然后系统地收集，最后输出结构化的研究报告。"
        ),
    },
    "executor": {
        "name": "执行者",
        "description": "写代码、调用 API、生成内容、运行工具",
        "system_prompt": (
            "你是一个高效的执行者（Executor）。你的职责是：\n"
            "1. 根据给定的子任务，编写代码、调用 API 或生成所需内容\n"
            "2. 利用可用的工具和 skill 完成具体操作\n"
            "3. 报告执行结果，包括成功/失败状态和输出\n\n"
            "你拥有文件读写、命令执行、HTTP 请求等工具。\n"
            "执行过程中如遇到问题，尝试自我修复，并说明采取的步骤。"
        ),
    },
    "reviewer": {
        "name": "审核者",
        "description": "检查错误、评估质量、提出改进建议",
        "system_prompt": (
            "你是一个严格的审核者（Reviewer）。你的职责是：\n"
            "1. 仔细检查其他 agent 的输出，发现错误和不足\n"
            "2. 评估输出质量是否满足用户需求\n"
            "3. 提出具体、可操作的改进建议\n"
            "4. 如有严重问题，明确指出需要重做的部分\n\n"
            "请保持批判性思维，但也要客观公正。重点关注：准确性、完整性、实用性。"
        ),
    },
    "summarizer": {
        "name": "总结者",
        "description": "整合所有结果，生成最终答案",
        "system_prompt": (
            "你是一个专业的总结者（Summarizer）。你的职责是：\n"
            "1. 整合所有其他 agent 的输出和工作成果\n"
            "2. 剔除冗余信息，提取核心内容\n"
            "3. 生成清晰、结构化、易于理解的最终答案\n"
            "4. 确保最终答案直接回应用户的原始问题\n\n"
            "输出应当简洁有力，用 Markdown 格式组织，让用户一眼看到关键结果。"
        ),
    },
    "expert": {
        "name": "领域专家",
        "description": "特定领域专业建议（可自定义领域）",
        "system_prompt": (
            "你是一位{domain}领域的资深专家。你的职责是：\n"
            "1. 根据你的专业知识，对所给任务提供专业见解\n"
            "2. 指出专业领域中的关键注意事项和最佳实践\n"
            "3. 给出基于专业经验的建议\n\n"
            "请以专家的视角，用通俗易懂的方式解释专业内容。"
        ),
    },
    "custom": {
        "name": "自定义 Agent",
        "description": "自定义角色和职责",
        "system_prompt": "你是一个专业助手，请根据任务要求完成工作。",
    },
}


# ────────────────────────────────────────────────────────────────────────────
# 数据结构
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class AgentDef:
    id: str                        # agent 唯一 ID
    role: str                      # 角色类型: coordinator / researcher / executor / reviewer / summarizer / expert / custom
    name: str                      # 显示名称
    description: str               # 描述
    system_prompt: str             # LLM system prompt
    enabled: bool = True
    skills: List[str] = field(default_factory=list)   # 允许使用的 skill 名称，空 = 全部

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "enabled": self.enabled,
            "skills": self.skills,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AgentDef":
        return cls(
            id=d["id"],
            role=d.get("role", "custom"),
            name=d.get("name", "Agent"),
            description=d.get("description", ""),
            system_prompt=d.get("system_prompt", ""),
            enabled=d.get("enabled", True),
            skills=d.get("skills", []),
        )

    @classmethod
    def from_builtin(cls, role: str, agent_id: str, overrides: dict | None = None) -> "AgentDef":
        template = BUILTIN_ROLES.get(role, BUILTIN_ROLES["custom"])
        overrides = overrides or {}
        return cls(
            id=agent_id,
            role=role,
            name=overrides.get("name", template["name"]),
            description=overrides.get("description", template["description"]),
            system_prompt=overrides.get("system_prompt", template["system_prompt"]),
            enabled=overrides.get("enabled", True),
            skills=overrides.get("skills", []),
        )


@dataclass
class AgentGroup:
    id: str
    name: str
    description: str
    agents: List[AgentDef]         # 组内所有 agent（包含协调者）
    created_at: str = ""
    updated_at: str = ""

    @property
    def coordinator(self) -> Optional[AgentDef]:
        """返回协调者 agent（必须存在）"""
        for a in self.agents:
            if a.role == "coordinator" and a.enabled:
                return a
        # 若无明确协调者，取第一个启用的 agent
        for a in self.agents:
            if a.enabled:
                return a
        return None

    @property
    def enabled_agents(self) -> List[AgentDef]:
        return [a for a in self.agents if a.enabled]

    def get_agent(self, agent_id: str) -> Optional[AgentDef]:
        for a in self.agents:
            if a.id == agent_id:
                return a
        return None

    def get_by_role(self, role: str) -> Optional[AgentDef]:
        for a in self.agents:
            if a.role == role and a.enabled:
                return a
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agents": [a.to_dict() for a in self.agents],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AgentGroup":
        return cls(
            id=d["id"],
            name=d["name"],
            description=d.get("description", ""),
            agents=[AgentDef.from_dict(a) for a in d.get("agents", [])],
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )


@dataclass
class AgentTurn:
    """一个 agent 的完整发言记录"""
    agent_id: str
    agent_name: str
    role: str
    subtask: str                   # 分配给它的子任务
    output: str                    # agent 的输出
    timestamp: str = ""
    error: str = ""                # 若执行出错

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "role": self.role,
            "subtask": self.subtask,
            "output": self.output,
            "timestamp": self.timestamp,
            "error": self.error,
        }


@dataclass
class GroupChatResult:
    """群聊执行结果"""
    group_id: str
    user_input: str
    turns: List[AgentTurn]         # 所有 agent 的发言
    final_answer: str              # 最终答案
    coordinator_plan: dict         # 协调者输出的计划
    usage: dict = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "group_id": self.group_id,
            "user_input": self.user_input,
            "turns": [t.to_dict() for t in self.turns],
            "final_answer": self.final_answer,
            "coordinator_plan": self.coordinator_plan,
            "usage": self.usage,
            "error": self.error,
        }


# ────────────────────────────────────────────────────────────────────────────
# 核心调度引擎
# ────────────────────────────────────────────────────────────────────────────

def _build_prev_context(turns: List[AgentTurn]) -> str:
    """将已完成的 agent 发言整理为上下文字符串"""
    if not turns:
        return ""
    lines = ["### 已完成的工作：\n"]
    for t in turns:
        lines.append(f"**{t.agent_name}（{t.role}）** 的输出：\n{t.output}\n")
    return "\n".join(lines)


def _call_agent(
    agent: AgentDef,
    subtask: str,
    prev_context: str,
    skills: list,
    history: list,
    original_question: str,
) -> str:
    """调用单个 agent 执行子任务，返回输出文本"""
    from .llm import run_agent
    from .config import get_provider_config
    from .agent import dispatch_tool
    from .tools import build_responses_tools

    cfg = get_provider_config()
    model = cfg.get("model", "")

    sys_prompt = agent.system_prompt

    # 构建用户消息
    parts = [f"## 原始用户问题\n{original_question}"]
    if prev_context:
        parts.append(prev_context)
    parts.append(f"## 你的子任务\n{subtask}")
    parts.append(
        "\n请完成你的子任务。输出应清晰、完整，方便后续 agent 使用。"
    )
    user_msg = "\n\n".join(parts)

    tools = build_responses_tools(include_execute_skill=True)

    try:
        result = run_agent(
            system_prompt=sys_prompt,
            user_input=user_msg,
            tools=tools,
            dispatch=dispatch_tool,
            model=model,
            max_rounds=6,
            history=history[-4:] if history else [],
        )
        return result
    except Exception as e:
        logger.error("Agent %s error: %s", agent.name, e)
        return f"[执行出错] {e}"


def _call_coordinator(
    coordinator: AgentDef,
    user_input: str,
    group: AgentGroup,
    history: list,
) -> dict:
    """调用协调者生成调度计划，返回 dict"""
    from .llm import run_agent
    from .config import get_provider_config

    cfg = get_provider_config()
    model = cfg.get("model", "")

    # 列出可用的非协调者 agent
    other_agents = [a for a in group.enabled_agents if a.role != "coordinator"]
    available_roles = ", ".join(f"{a.role}（{a.name}）" for a in other_agents)

    sys_prompt = coordinator.system_prompt.replace("{available_roles}", available_roles or "无其他 agent")

    # 构建历史上下文
    ctx = ""
    if history:
        lines = []
        for h in history[-6:]:
            label = "用户" if h["role"] == "user" else "助手"
            lines.append(f"{label}: {h['content']}")
        ctx = "【对话历史】\n" + "\n".join(lines) + "\n\n"

    user_msg = f"{ctx}【当前请求】\n{user_input}"

    try:
        raw = run_agent(
            system_prompt=sys_prompt,
            user_input=user_msg,
            tools=[],
            dispatch=lambda n, a: "",
            model=model,
            max_rounds=1,
        )
        # 尝试提取 JSON（可能包含多余文本）
        raw = raw.strip()
        # 去掉 markdown 代码块
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw
        plan = json.loads(raw)
        return plan
    except Exception as e:
        logger.warning("Coordinator parse error: %s, raw=%r", e, raw[:200] if 'raw' in dir() else "")
        # fallback：直接调度给 executor
        other = [a for a in group.enabled_agents if a.role != "coordinator"]
        dispatch = []
        for a in other:
            if a.role != "summarizer":
                dispatch.append({"agent_role": a.role, "task": user_input})
        return {"thinking": "fallback plan", "dispatch": dispatch}


def run_group_chat(
    group: AgentGroup,
    user_input: str,
    history: list,
    skills: list,
    user_id: str,
) -> GroupChatResult:
    """
    主入口：运行多 agent 群聊。

    流程：
    1. 协调者分析并生成调度计划
    2. 按顺序调用各 agent
    3. 总结者（若存在）生成最终答案
    4. 返回 GroupChatResult
    """
    from .llm import get_usage, run_agent
    from .config import get_provider_config

    turns: List[AgentTurn] = []
    coordinator = group.coordinator

    if not coordinator:
        return GroupChatResult(
            group_id=group.id,
            user_input=user_input,
            turns=[],
            final_answer="群组中没有可用的 agent。",
            coordinator_plan={},
            error="no_coordinator",
        )

    # ── Step 1: 协调者制定计划 ─────────────────────────────────────────────
    logger.info("[MultiAgent] Coordinator analyzing task...")
    coordinator_plan = _call_coordinator(coordinator, user_input, group, history)

    coordinator_turn = AgentTurn(
        agent_id=coordinator.id,
        agent_name=coordinator.name,
        role=coordinator.role,
        subtask="分析用户需求，制定调度计划",
        output=f"**调度计划**\n\n{coordinator_plan.get('thinking', '')}\n\n"
               + "**分配任务：**\n"
               + "\n".join(
                   f"- {d.get('agent_role', '?')}: {d.get('task', '')}"
                   for d in coordinator_plan.get("dispatch", [])
               ),
        timestamp=datetime.now().isoformat(),
    )
    turns.append(coordinator_turn)

    # ── Step 2: 若协调者直接回答（无需其他 agent）────────────────────────────
    direct = coordinator_plan.get("direct", "")
    if direct and not coordinator_plan.get("dispatch"):
        return GroupChatResult(
            group_id=group.id,
            user_input=user_input,
            turns=turns,
            final_answer=direct,
            coordinator_plan=coordinator_plan,
            usage=get_usage(),
        )

    # ── Step 3: 按调度计划逐个调用 agent ─────────────────────────────────────
    dispatch_list = coordinator_plan.get("dispatch", [])

    # 若调度列表为空，把所有非协调者、非总结者 agent 都加进来
    if not dispatch_list:
        for a in group.enabled_agents:
            if a.role not in ("coordinator", "summarizer"):
                dispatch_list.append({"agent_role": a.role, "task": user_input})

    for item in dispatch_list:
        role = item.get("agent_role", "")
        subtask = item.get("task", user_input)

        # 找到对应 agent
        agent = group.get_by_role(role)
        if not agent:
            logger.warning("Agent role '%s' not found in group, skipping", role)
            continue

        logger.info("[MultiAgent] Running agent: %s (%s)", agent.name, role)
        prev_ctx = _build_prev_context(turns)

        output = _call_agent(
            agent=agent,
            subtask=subtask,
            prev_context=prev_ctx,
            skills=skills,
            history=history,
            original_question=user_input,
        )

        turn = AgentTurn(
            agent_id=agent.id,
            agent_name=agent.name,
            role=agent.role,
            subtask=subtask,
            output=output,
            timestamp=datetime.now().isoformat(),
        )
        turns.append(turn)

    # ── Step 4: 总结者整合输出 ───────────────────────────────────────────────
    summarizer = group.get_by_role("summarizer")
    final_answer = ""

    if summarizer and len(turns) > 1:
        logger.info("[MultiAgent] Running summarizer...")
        prev_ctx = _build_prev_context(turns)
        cfg = get_provider_config()
        model = cfg.get("model", "")

        from .agent import dispatch_tool
        from .tools import build_responses_tools

        sum_user_msg = (
            f"## 原始用户问题\n{user_input}\n\n"
            f"{prev_ctx}\n\n"
            "## 你的任务\n请整合以上所有 agent 的工作成果，生成最终的综合答案。"
            "直接回答用户问题，语言清晰，格式美观。"
        )

        try:
            final_answer = run_agent(
                system_prompt=summarizer.system_prompt,
                user_input=sum_user_msg,
                tools=build_responses_tools(include_execute_skill=False),
                dispatch=dispatch_tool,
                model=model,
                max_rounds=3,
            )
        except Exception as e:
            logger.error("Summarizer error: %s", e)
            final_answer = f"[总结出错] {e}"

        sum_turn = AgentTurn(
            agent_id=summarizer.id,
            agent_name=summarizer.name,
            role=summarizer.role,
            subtask="整合所有 agent 的输出，给出最终答案",
            output=final_answer,
            timestamp=datetime.now().isoformat(),
        )
        turns.append(sum_turn)
    else:
        # 没有总结者，取最后一个非协调者 agent 的输出作为最终答案
        non_coord_turns = [t for t in turns if t.role != "coordinator"]
        final_answer = non_coord_turns[-1].output if non_coord_turns else turns[-1].output if turns else ""

    return GroupChatResult(
        group_id=group.id,
        user_input=user_input,
        turns=turns,
        final_answer=final_answer,
        coordinator_plan=coordinator_plan,
        usage=get_usage(),
    )
