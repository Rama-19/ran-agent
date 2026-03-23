import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any

from .models import RunOptions, normalize_options, select_model, pick_reasoning_effort, get_agent_round_limit
from .skills import find_skill, load_eligible_skills
from .tools import (
    read_file, write_file, list_dir, exec_cmd,
    list_skills, read_skill_md,
    memory_tool_get, memory_tool_set, memory_tool_delete, memory_tool_list,
    http_request,
    build_responses_tools, get_response_tools,
)
from . import memory as mem
from .memory import get_user_memory
from .config import _current_user_id
from .llm import run_agent


# ── skill 执行 ────────────────────────────────────────────────────────────────


def execute_skill(skill_name: str, tool_args: dict = None):
    eligible = load_eligible_skills()
    skill = next((s for s in eligible if s["name"] == skill_name), None)
    if not skill:
        return f"❌ 找不到 skill: {skill_name}"

    skill_dir = Path(skill["location"])
    candidates = [
        skill_dir / "run.py",
        skill_dir / f"{skill_name}.py",
        skill_dir / "run.sh",
        skill_dir / "execute.py",
    ]
    entrypoint = None
    for p in candidates:
        if p.exists():
            entrypoint = p
            break

    if not entrypoint:
        return (
            f"❌ 没有找到执行入口文件！\n"
            f"请在 {skill_dir} 里放以下任意一个：\n"
            f"  • run.py\n  • {skill_name}.py\n  • run.sh"
        )

    cmd_list = (
        ["python", str(entrypoint)] if entrypoint.suffix == ".py"
        else ["bash", str(entrypoint)] if entrypoint.suffix == ".sh"
        else [str(entrypoint)]
    )

    if tool_args:
        for k, v in tool_args.items():
            cmd_list.extend([f"--{k}", str(v)])

    try:
        print(f"🚀 执行入口: {entrypoint.name}  (目录: {skill_dir})")
        print(f"   参数: {tool_args}")
        result = subprocess.run(
            cmd_list, cwd=skill_dir, capture_output=True,
            text=True, timeout=60, encoding="utf-8"
        )
        output = result.stdout.strip()
        if result.stderr.strip():
            output += "\n[stderr]\n" + result.stderr.strip()
        return f"✅ 执行成功！\n{output or '（无输出）'}" if result.returncode == 0 \
            else f"⚠️ 执行失败 (code={result.returncode})\n{output}"
    except subprocess.TimeoutExpired:
        return "❌ 执行超时（超过 60 秒）"
    except Exception as e:
        return f"❌ 执行异常: {str(e)}"


def build_skill_executor_prompt(skill: Dict) -> str:
    return f"""
你现在是一个 skill executor。

当前 skill:
- name: {skill["name"]}
- description: {skill["description"]}
- location: {skill["location"]}

下面是该 skill 的完整 SKILL.md，请严格遵守：

================ SKILL.md BEGIN ================
{skill["content"]}
================ SKILL.md END ==================

规则：
1. 你必须严格按照 SKILL.md 的要求执行任务。
2. 你可以使用 read_file / write_file / list_dir / exec_cmd 等通用工具。
3. 你不能调用 execute_skill，避免无限递归。
4. 如果需要引用 skill 目录中的资源文件，请以 {skill["location"]} 作为根目录。
5. 不要虚构不存在的文件、命令结果或执行结果。
6. 最终输出必须以以下两种格式之一结束：
   - DONE: <结果摘要>
   - BLOCKED: <阻塞原因>
"""


def execute_skill_by_agent(skill_name: str, task: str) -> str:
    skill = find_skill(skill_name)
    if not skill:
        return f"Skill not found: {skill_name}"

    system_prompt = build_skill_executor_prompt(skill)

    def _dispatch(name: str, args: dict) -> str:
        return dispatch_tool(name, args, allow_execute_skill=False)

    return run_agent(
        system_prompt=system_prompt,
        user_input=task,
        tools=build_responses_tools(include_execute_skill=False),
        dispatch=_dispatch,
        model=select_model(),
        reasoning_effort=None,
        max_rounds=8,
    )


# ── tool dispatch ─────────────────────────────────────────────────────────────


def dispatch_tool(
    name: str,
    args: dict,
    allow_execute_skill: bool = True,
    allow_web_search: bool = False,
) -> str:
    if name == "list_skills":
        return list_skills()
    elif name == "read_skill_md":
        return read_skill_md(args["skill_name"])
    elif name == "read_file":
        return read_file(args["path"])
    elif name == "write_file":
        return write_file(args["path"], args["content"])
    elif name == "list_dir":
        return list_dir(args["path"])
    elif name == "exec_cmd":
        return exec_cmd(args["command"], args["cwd"])
    elif name == "http_request":
        return http_request(
            args["method"], args["url"],
            args.get("headers", "{}"), args.get("body", "")
        )
    elif name == "memory_get":
        return memory_tool_get(args["key"])
    elif name == "memory_set":
        return memory_tool_set(args["key"], args["value"])
    elif name == "memory_delete":
        return memory_tool_delete(args["key"])
    elif name == "memory_list":
        return memory_tool_list()
    elif name == "execute_skill":
        if not allow_execute_skill:
            return "execute_skill is disabled in this agent context"
        return execute_skill_by_agent(args["skill_name"], args["task"])
    return f"Unknown tool: {name}"


# ── 主 agent 入口 ─────────────────────────────────────────────────────────────


def run_responses_agent(
    system_prompt: str,
    user_input: str,
    tools: Optional[List[Dict]] = None,
    options: Optional[RunOptions] = None,
    allow_execute_skill: bool = True,
    allow_web_search: bool = False,
    max_rounds: Optional[int] = None,
    history: Optional[List[Dict]] = None,
) -> str:
    opts = normalize_options(options)
    model = select_model(opts)
    effort = pick_reasoning_effort(opts)
    round_limit = max_rounds or get_agent_round_limit(opts, base=8)

    # 注入记忆上下文（优先用用户记忆，否则回退到全局记忆）
    user_id = _current_user_id.get()
    if user_id:
        mem_ctx = get_user_memory(user_id).format_for_prompt()
    else:
        mem_ctx = mem.format_for_prompt()
    if mem_ctx:
        system_prompt = f"{system_prompt}\n\n{mem_ctx}"

    def _dispatch(name: str, args: dict) -> str:
        return dispatch_tool(
            name, args,
            allow_execute_skill=allow_execute_skill,
            allow_web_search=allow_web_search,
        )

    return run_agent(
        system_prompt=system_prompt,
        user_input=user_input,
        tools=tools or [],
        dispatch=_dispatch,
        model=model,
        reasoning_effort=effort,
        max_rounds=round_limit,
        history=history,
    )
