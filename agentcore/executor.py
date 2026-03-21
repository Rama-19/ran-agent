import re
from typing import Dict, List, Optional

from .models import (
    Plan, PlanStep, NeedInput, PlanExecResult, PLAN_STORE,
    RunOptions, normalize_options, get_agent_round_limit,
)
from .skills import format_skills_for_prompt
from .agent import run_responses_agent
from .tools import get_response_tools

PROTO_LINE_RE = re.compile(r'^(DONE|BLOCKED|FAILED):\s*(.*)$', re.MULTILINE)


def strip_code_fence(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", text)
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def parse_step_agent_result(text: str) -> tuple[str, str]:
    text = strip_code_fence(text or "")

    if not text:
        return "failed", "模型未返回内容"

    matches = list(PROTO_LINE_RE.finditer(text))
    if matches:
        m = matches[-1]
        state = m.group(1).lower()
        detail = m.group(2).strip()

        if state == "done":
            return "done", detail or "执行完成"
        elif state == "blocked":
            return "blocked", detail or "请补充必要信息"
        else:
            return "failed", detail or "执行失败"

    short = text[:300].replace("\n", " ")
    return "failed", f"step agent 未按协议返回结果: {short}"


def build_history_from_plan(plan: Plan) -> List[str]:
    history_lines = []
    for i, step in enumerate(plan.steps):
        if i >= plan.current_step_index:
            break
        if step.status == "done":
            history_lines.append(f"[DONE] {step.title}: {step.output}")
        elif step.status == "failed":
            history_lines.append(f"[FAILED] {step.title}: {step.output}")
    return history_lines


def build_executor_prompt(skills_xml: str, plan: Plan, step: PlanStep, history: str, options: RunOptions) -> str:
    return f"""
你是一个执行代理（executor agent）。

当前可用 skills：
{skills_xml}

当前计划：
- plan_id: {plan.id}
- title: {plan.title}
- goal: {plan.goal}

当前步骤：
- step_id: {step.id}
- title: {step.title}
- instruction: {step.instruction}
- skill_hint: {step.skill_hint or "(none)"}

当前运行选项：
- web_mode: {options.web_mode}
- deep_think: {options.deep_think}
- require_citations: {options.require_citations}
- max_search_rounds: {options.max_search_rounds}

已完成历史：
{history or "（暂无）"}

规则：
1. 你一次只执行当前这一个步骤，不要越过当前步骤去做后续步骤。
2. 如果当前步骤涉及某个 skill，必须先调用 read_skill_md(skill_name) 阅读说明，再决定是否调用 execute_skill。
3. 你可以使用 list_skills / read_skill_md / execute_skill / read_file / write_file / list_dir / exec_cmd。
4. 当 web_mode=off 时，不要联网。
5. 当 web_mode=on 时，如步骤需要外部事实、最新信息、官网、新闻、资料核验，可以使用内置 web_search。
6. 当 web_mode=auto 时，仅在确实需要外部资料时才使用内置 web_search。
7. 如果 deep_think >= 2，请先分析依赖、输出格式和验证方式，再决定调用工具。
8. 如果 require_citations=true 且你使用了 web_search，请在正文中附简短来源说明。
9. 最后一行必须单独输出且只能是以下三种之一：
   DONE: <结果摘要>
   BLOCKED: <阻塞原因或需要用户补充的问题>
   FAILED: <失败原因>
10. 协议行必须是最后一行。
""".strip()


def run_step_agent(
    plan: Plan,
    step: PlanStep,
    eligible_skills: List[Dict],
    history: str = "",
    options: Optional[RunOptions] = None
) -> str:
    options = normalize_options(options or plan.options)
    skills_xml = format_skills_for_prompt(eligible_skills)
    system_prompt = build_executor_prompt(skills_xml, plan, step, history, options)
    tools = get_response_tools(options, include_execute_skill=True)

    return run_responses_agent(
        system_prompt=system_prompt,
        user_input="开始执行当前步骤。",
        tools=tools,
        options=options,
        allow_execute_skill=True,
        allow_web_search=(options.web_mode != "off"),
        max_rounds=get_agent_round_limit(options, base=8),
    )


def execute_plan_structured(
    plan_id: str,
    eligible_skills: List[Dict],
    resume_reply: Optional[str] = None,
    options: Optional[RunOptions] = None,
    plan_store: Optional[Dict] = None,
) -> PlanExecResult:
    ps = plan_store if plan_store is not None else PLAN_STORE
    plan = ps.get(plan_id)
    effective_options = normalize_options(options or plan.options)
    plan.options = effective_options

    if not plan:
        return PlanExecResult(status="failed", message=f"找不到计划: {plan_id}")

    if plan.status == "done":
        return PlanExecResult(status="done", message=f"计划已完成：{plan.title}")

    history_lines = build_history_from_plan(plan)

    for i, s in enumerate(plan.steps):
        if i >= plan.current_step_index:
            break
        if s.status == "done":
            history_lines.append(f"[DONE] {s.title}: {s.output}")
        elif s.status == "failed":
            history_lines.append(f"[FAILED] {s.title}: {s.output}")

    start_index = plan.current_step_index

    if plan.status == "blocked":
        if not resume_reply:
            current_step = plan.steps[plan.current_step_index]
            return PlanExecResult(
                status="blocked",
                message=f"计划仍在等待补充信息：{plan.title}",
                need_input=NeedInput(
                    plan_id=plan.id,
                    step_id=current_step.id,
                    question=plan.pending_question or "请补充必要信息。"
                )
            )

        current_step = plan.steps[plan.current_step_index]
        if current_step.output:
            history_lines.append(f"[BLOCKED] {current_step.title}: {current_step.output}")
        history_lines.append(f"[USER_REPLY] {resume_reply}")

        plan.awaiting_user_input = False
        plan.pending_question = ""
        plan.status = "running"
    else:
        plan.status = "running"

    for idx in range(start_index, len(plan.steps)):
        step = plan.steps[idx]
        plan.current_step_index = idx
        step.status = "running"

        result = run_step_agent(
            plan=plan,
            step=step,
            eligible_skills=eligible_skills,
            history="\n".join(history_lines),
            options=effective_options
        )

        step.output = result
        step_state, detail = parse_step_agent_result(result)

        if step_state == "done":
            step.status = "done"
            history_lines.append(f"[DONE] {step.title}: {result}")
            plan.current_step_index = idx + 1
            continue

        if step_state == "blocked":
            step.status = "blocked"
            plan.status = "blocked"
            plan.awaiting_user_input = True
            plan.pending_question = detail or "请补充必要信息。"
            plan.current_step_index = idx

            return PlanExecResult(
                status="blocked",
                message=f"计划执行中断：{step.title}",
                need_input=NeedInput(
                    plan_id=plan.id,
                    step_id=step.id,
                    question=plan.pending_question
                )
            )

        step.status = "failed"
        plan.status = "failed"
        plan.current_step_index = idx

        return PlanExecResult(
            status="failed",
            message=f"计划执行失败：{step.title}\nFAILED: {detail}"
        )

    plan.status = "done"
    plan.awaiting_user_input = False
    plan.pending_question = ""
    plan.current_step_index = len(plan.steps)

    return PlanExecResult(status="done", message=f"计划执行完成：{plan.title}")


def execute_plan(plan_id: str, eligible_skills: List[Dict], plan_store: Optional[Dict] = None) -> str:
    result = execute_plan_structured(plan_id, eligible_skills, plan_store=plan_store)
    if result.status == "blocked" and result.need_input:
        return f"{result.message}\nBLOCKED: {result.need_input.question}"
    return result.message
