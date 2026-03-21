import shlex
from typing import Dict, List, Optional

from .models import Plan, RunOptions, normalize_options, get_agent_round_limit, PLAN_STORE
from .skills import format_skills_for_prompt
from .agent import run_responses_agent
from .tools import get_response_tools


def show_plans(plans) -> str:
    if not isinstance(plans, (list, tuple)):
        plans = [plans]

    lines = []
    for p in plans:
        lines.append(f"{p.id}. {p.title}  [{p.status}]")
        lines.append(f"   goal: {p.goal}")
        for step in p.steps:
            hint = f"  (skill_hint={step.skill_hint})" if step.skill_hint else ""
            lines.append(f"   - {step.id}: {step.title} [{step.status}]{hint}")
            lines.append(f"     instruction: {step.instruction}")
            if step.output:
                lines.append(f"     output: {step.output}")
    return "\n".join(lines)


def show_skills(skills: List[Dict]) -> str:
    if not skills:
        return "没有可用 skills"
    lines = []
    for s in skills:
        lines.append(f"- {s['name']}: {s['description']}")
        lines.append(f"  location: {s['location']}")
    return "\n".join(lines)


def build_main_system_prompt(skills_xml: str) -> str:
    return f"""
你是一个智能助手。

当前可用 skills：
{skills_xml}

规则：
1. 如果任务与某个 skill 匹配，优先使用该 skill。
2. 使用 skill 前，必须先调用 read_skill_md(skill_name) 查看说明。
3. skill 不依赖 run.py / run.sh；skill 的执行由 execute_skill(skill_name, task) 完成。
4. execute_skill 的本质是：根据 SKILL.md 调用通用工具完成任务。
5. 如果没有合适 skill，再直接使用 read_file / write_file / list_dir / exec_cmd。
6. 不要臆造 skill 的能力，必须以 SKILL.md 为准。
"""


def run_direct_agent(
    user_input: str,
    eligible_skills: List[Dict],
    options: Optional[RunOptions] = None,
    history: Optional[List[Dict]] = None,
) -> str:
    options = normalize_options(options)
    skills_xml = format_skills_for_prompt(eligible_skills)
    system_prompt = build_main_system_prompt(skills_xml)
    tools = get_response_tools(options, include_execute_skill=True)

    return run_responses_agent(
        system_prompt=system_prompt,
        user_input=user_input,
        tools=tools,
        options=options,
        allow_execute_skill=True,
        allow_web_search=(options.web_mode != "off"),
        max_rounds=get_agent_round_limit(options, base=8),
        history=history,
    )


def parse_auto_command(text: str) -> tuple[RunOptions, str]:
    """
    输入: /auto --web --deep=2 --cite 帮我整理凯末尔评价并写入笔记
    输出: (RunOptions(...), "帮我整理凯末尔评价并写入笔记")
    """
    raw = text[len("/auto "):].strip()
    parts = shlex.split(raw)

    opts = RunOptions()
    task_parts = []

    for part in parts:
        if part == "--web":
            opts.web_mode = "on"
        elif part.startswith("--web="):
            value = part.split("=", 1)[1].strip()
            if value in ("auto", "on", "off"):
                opts.web_mode = value
        elif part == "--deep":
            opts.deep_think = 2
        elif part.startswith("--deep="):
            try:
                opts.deep_think = max(0, min(3, int(part.split("=", 1)[1])))
            except ValueError:
                pass
        elif part == "--cite":
            opts.require_citations = True
        elif part.startswith("--max-search="):
            try:
                opts.max_search_rounds = max(1, min(10, int(part.split("=", 1)[1])))
            except ValueError:
                pass
        else:
            task_parts.append(part)

    task = " ".join(task_parts).strip()
    return opts, task
