import json
import re
from typing import Dict, List, Optional

from .models import Plan, PlanStep, PLAN_STORE, RunOptions, normalize_options
from .skills import format_skills_for_prompt
from .agent import run_responses_agent


def extract_json(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("空响应，无法解析 JSON")

    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.search(r"\{.*\}", text, re.S)
    if m:
        return json.loads(m.group(0))

    raise ValueError(f"无法从文本中提取 JSON: {text[:200]}")


def build_planner_prompt(skills_xml: str, options: RunOptions) -> str:
    return f"""
你是一个 planner，负责为用户任务制定 1~3 个可执行计划。

当前可用 skills：
{skills_xml}

当前运行选项：
- web_mode: {options.web_mode}
- deep_think: {options.deep_think}
- require_citations: {options.require_citations}
- max_search_rounds: {options.max_search_rounds}

要求：
1. 输出必须是 JSON，不要输出 markdown，不要解释。
2. 输出格式必须是：
{{
  "plans": [
    {{
      "title": "计划标题",
      "goal": "计划目标",
      "steps": [
        {{
          "title": "步骤标题",
          "instruction": "执行说明",
          "skill_hint": "可选，若无则空字符串"
        }}
      ]
    }}
  ]
}}
3. 如果某个步骤打算使用 skill，instruction 中必须明确先读取该 skill 的 SKILL.md。
4. 优先使用已有 skill；没有合适 skill 时再使用 read_file / write_file / list_dir / exec_cmd。
5. 每个计划应尽量短小、可执行、可验证。
6. 如果 web_mode=off，不要规划任何联网搜索步骤。
7. 如果 web_mode=on，可以在必要时规划"用 web_search 搜索资料/核验事实/整理来源"的步骤。
8. 如果 web_mode=auto，仅当任务涉及最新信息、事实核验、官网/论文/新闻/价格/对比时才规划联网步骤。
9. 如果 deep_think >= 2，请增加必要的验证或回退步骤。
10. 如果 require_citations=true，并且使用了外部资料，请在相关步骤中要求整理来源。
""".strip()


def make_plans(
    user_input: str,
    eligible_skills: List[Dict],
    options: Optional[RunOptions] = None,
    plan_store: Optional[Dict] = None,
) -> List[Plan]:
    ps = plan_store if plan_store is not None else PLAN_STORE
    options = normalize_options(options)
    skills_xml = format_skills_for_prompt(eligible_skills)
    system_prompt = build_planner_prompt(skills_xml, options)

    content = run_responses_agent(
        system_prompt=system_prompt,
        user_input=user_input,
        tools=[],
        options=options,
        allow_execute_skill=False,
        allow_web_search=False,
        max_rounds=1,
    )

    try:
        data = extract_json(content)
        plans: List[Plan] = []

        for i, p in enumerate(data.get("plans", []), start=1):
            plan_id = f"plan_{len(ps) + 1}"
            steps = []

            for j, s in enumerate(p.get("steps", []), start=1):
                steps.append(PlanStep(
                    id=f"{plan_id}_step_{j}",
                    title=s.get("title", f"step_{j}"),
                    instruction=s.get("instruction", ""),
                    skill_hint=s.get("skill_hint", "") or ""
                ))

            plan = Plan(
                id=plan_id,
                title=p.get("title", f"计划 {i}"),
                goal=p.get("goal", user_input),
                steps=steps,
                status="pending",
                original_task=user_input,
                current_step_index=0,
                awaiting_user_input=False,
                pending_question="",
                options=options,
            )
            ps[plan.id] = plan
            plans.append(plan)

        if plans:
            return plans

    except Exception as e:
        print(f"[planner JSON解析失败] {e}")
        print(f"[planner原始输出]\n{content}")

    fallback_id = f"plan_{len(ps) + 1}"
    fallback = Plan(
        id=fallback_id,
        title="默认计划",
        goal=user_input,
        original_task=user_input,
        current_step_index=0,
        awaiting_user_input=False,
        pending_question="",
        options=options,
        steps=[
            PlanStep(
                id=f"{fallback_id}_step_1",
                title="分析任务并尝试执行",
                instruction="先查看可用 skills；如果有合适 skill，先读取其 SKILL.md 后执行；否则直接使用通用工具完成任务。",
                skill_hint=""
            )
        ]
    )
    ps[fallback.id] = fallback
    return [fallback]
