import os
import json
import yaml
import platform
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal
import openai
from openai import OpenAI
from dotenv import load_dotenv
from dataclasses import dataclass, field, asdict
import subprocess
import logging
from datetime import datetime
import shlex

load_dotenv()
api_key = os.environ.get("OPENAI_API_KEY")
base_url = os.environ.get("OPENAI_BASE_URL")
model_name = os.environ.get("OPENAI_MODEL", "gpt-5.4")
deep_model_name = os.environ.get("OPENAI_MODEL_DEEP", model_name)
LAST_BLOCKED = None
now = datetime.now().strftime("%Y-%m-%d")
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename=f"../log/{now}.log",
    filemode="a",
    encoding="utf-8",
    )
if not api_key:
    raise RuntimeError("缺少 OPENAI_API_KEY")

client = OpenAI(api_key=api_key, base_url=base_url)
# ====================== 配置 ======================
CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
print(f"使用配置文件: {CONFIG_PATH}")
WORKSPACE_ENV = os.getenv("WORKSPACE") or str(Path.home() / "workspace")  # 可改
print(f"工作空间路径: {WORKSPACE_ENV}")

WebMode = Literal["auto", "on", "off"]

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
    # 为续跑增加的字段
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

def load_config() -> Dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"skills": {"load": {"extraDirs": []}, "entries": {}}}

config = load_config()

def normalize_options(options: Optional[RunOptions]) -> RunOptions:
    return options if options else RunOptions()

def select_model(options: Optional[RunOptions] = None) -> str:
    opts = normalize_options(options)
    return deep_model_name if opts.deep_think >= 2 else model_name

def pick_reasoning_effort(options: Optional[RunOptions] = None) -> Optional[str]:
    opts = normalize_options(options)
    mapping = {
        0: None,
        1: "low",
        2: "medium",
        3: "high",
    }
    return mapping.get(opts.deep_think, "medium")

def get_agent_round_limit(options: Optional[RunOptions] = None, base: int = 8) -> int:
    opts = normalize_options(options)
    return base + opts.deep_think * 4

def build_responses_tools(
    include_execute_skill: bool = True,
    include_web_search: bool = False
) -> List[Dict]:
    tools = [
        {
            "type": "function",
            "name": "list_skills",
            "description": "列出所有当前可用的 skills",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "type": "function",
            "name": "read_skill_md",
            "description": "读取某个 skill 的 SKILL.md 内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {"type": "string"}
                },
                "required": ["skill_name"]
            }
        },
        {
            "type": "function",
            "name": "read_file",
            "description": "读取本地文件内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        },
        {
            "type": "function",
            "name": "write_file",
            "description": "写入本地文件内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["path", "content"]
            }
        },
        {
            "type": "function",
            "name": "list_dir",
            "description": "列出某个目录下的文件和子目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        },
        {
            "type": "function",
            "name": "exec_cmd",
            "description": "执行本地命令",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "cwd": {"type": "string"}
                },
                "required": ["command", "cwd"]
            }
        }
    ]

    if include_web_search:
        tools.append({
            "type": "web_search"
        })

    if include_execute_skill:
        tools.append({
            "type": "function",
            "name": "execute_skill",
            "description": "执行指定 skill 对应的任务。skill 本身不需要 run.py / run.sh，而是由 agent 根据 SKILL.md 调用通用工具完成。",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {"type": "string"},
                    "task": {"type": "string"}
                },
                "required": ["skill_name", "task"]
            }
        })

    return tools

def get_response_tools(options: Optional[RunOptions] = None, include_execute_skill: bool = True) -> List[Dict]:
    opts = normalize_options(options)
    return build_responses_tools(
        include_execute_skill=include_execute_skill,
        include_web_search=(opts.web_mode != "off")
    )
    
def run_responses_agent(
    system_prompt: str,
    user_input: str,
    tools: Optional[List[Dict]] = None,
    options: Optional[RunOptions] = None,
    allow_execute_skill: bool = True,
    allow_web_search: bool = False,
    max_rounds: Optional[int] = None,
) -> str:
    opts = normalize_options(options)
    model = select_model(opts)
    effort = pick_reasoning_effort(opts)
    round_limit = max_rounds or get_agent_round_limit(opts, base=8)

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        tools=tools or [],
        reasoning={"effort": effort} if effort else None,
    )

    for _ in range(round_limit):
        function_calls = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) == "function_call":
                function_calls.append(item)

        if not function_calls:
            text = getattr(response, "output_text", None)
            if text:
                return text

            # fallback
            try:
                return json.dumps(response.model_dump(), ensure_ascii=False, indent=2)
            except Exception:
                return "(no response)"

        tool_outputs = []
        for fc in function_calls:
            tool_name = fc.name
            args = json.loads(fc.arguments or "{}")
            result = dispatch_tool(
                tool_name,
                args,
                allow_execute_skill=allow_execute_skill,
                allow_web_search=allow_web_search
            )
            tool_outputs.append({
                "type": "function_call_output",
                "call_id": fc.call_id,
                "output": result
            })

        response = client.responses.create(
            model=model,
            previous_response_id=response.id,
            input=tool_outputs,
            tools=tools or [],
            reasoning={"effort": effort} if effort else None,
        )

    return "BLOCKED: 超过最大工具轮数"

# ====================== 目录层级（优先级从高到低） ======================
def get_skill_dirs() -> List[Path]:
    dirs = []

    # lowest precedence
    for extra in config.get("skills", {}).get("load", {}).get("extraDirs", []):
        p = Path(extra)
        if p.exists():
            dirs.append(p)

    bundled = Path(__file__).parent / "bundled_skills"
    if bundled.exists():
        dirs.append(bundled)

    managed = Path.home() / ".openclaw" / "skills"
    if managed.exists():
        dirs.append(managed)

    workspace_skills = Path(WORKSPACE_ENV) / "skills"
    if workspace_skills.exists():
        dirs.append(workspace_skills)

    return dirs

# ====================== 解析 SKILL.md ======================
def parse_skill_md(skill_dir: Path) -> Optional[Dict]:
    md = skill_dir / "SKILL.md"
    if not md.exists():
        return None

    content = md.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return None

    try:
        _, fm_text, body = content.split("---", 2)
        fm = yaml.safe_load(fm_text.strip()) or {}
        metadata = fm.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        return {
            "name": fm.get("name"),
            "description": fm.get("description", ""),
            "metadata": metadata,
            "location": str(skill_dir.resolve()),
            "skill_md_path": str(md.resolve()),
            "content": content,
            "body": body.strip(),
        }
    except Exception as e:
        print(f"解析 SKILL.md 失败: {md} -> {e}")
        return None
    
# ====================== gating 过滤（官方 requires 完整实现） ======================
def is_eligible(skill: Dict) -> bool:
    meta = skill.get("metadata", {}).get("openclaw", {})
    entry = config.get("skills", {}).get("entries", {}).get(skill["name"], {})

    if entry.get("enabled", True) is False:
        return False

    if meta.get("always", False):
        return True

    required_os = meta.get("os")
    if required_os:
        current = platform.system().lower()
        os_map = {"darwin": "darwin", "linux": "linux", "windows": "win32"}
        if os_map.get(current) not in required_os:
            return False

    requires = meta.get("requires", {})

    for b in requires.get("bins", []):
        if shutil.which(b) is None:
            return False

    any_bins = requires.get("anyBins", [])
    if any_bins and not any(shutil.which(b) for b in any_bins):
        return False

    for env_name in requires.get("env", []):
        if env_name not in os.environ and env_name not in entry.get("env", {}):
            return False

    # 简化版 requires.config
    for path in requires.get("config", []):
        value = config
        for k in path.split("."):
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(k)
        if not value:
            return False

    return True

# ====================== 合并 + 去重（高优先级覆盖） ======================
def load_eligible_skills() -> List[Dict]:
    seen = {}
    for root in get_skill_dirs():  # low -> high, later overrides earlier
        for child in root.iterdir():
            if not child.is_dir():
                continue
            skill = parse_skill_md(child)
            if skill and skill.get("name"):
                seen[skill["name"]] = skill
    return [s for s in seen.values() if is_eligible(s)]

def find_skill(skill_name: str) -> Optional[Dict]:
    eligible = load_eligible_skills()
    return next((s for s in eligible if s["name"] == skill_name), None)

def format_skills_for_prompt(skills: List[Dict]) -> str:
    if not skills:
        return ""
    lines = ["<available_skills>"]
    for s in skills:
        name = s["name"]
        desc = s["description"]
        loc = s["location"]
        lines.append("  <skill>")
        lines.append(f"    <name>{name}</name>")
        lines.append(f"    <description>{desc}</description>")
        lines.append(f"    <location>{loc}</location>")
        lines.append("  </skill>")
    lines.append("</available_skills>")
    return "\n".join(lines)

def read_file(path: str) -> str:
    try:
        p = Path(path)
        if not p.exists():
            return f"File not found: {path}"
        return p.read_text(encoding="utf-8")
    except Exception as e:
        return f"Read error: {e}"

def write_file(path: str, content: str) -> str:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"File written: {path}"
    except Exception as e:
        return f"Write error: {e}"
       
def list_dir(path: str) -> str:
    try:
        p = Path(path)
        if not p.exists():
            return f"Path not found: {path}"
        if not p.is_dir():
            return f"Not a directory: {path}"

        items = []
        for x in sorted(p.iterdir(), key=lambda i: (not i.is_dir(), i.name.lower())):
            suffix = "/" if x.is_dir() else ""
            items.append(x.name + suffix)

        return "\n".join(items) if items else "(empty)"
    except Exception as e:
        return f"List dir error: {e}"    
    
import subprocess

def safe_decode(data: bytes) -> str:
    if not data:
        return ""
    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")

def exec_cmd(command: str, cwd: str) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=False,
            timeout=60
        )

        stdout = safe_decode(result.stdout).strip()
        stderr = safe_decode(result.stderr).strip()

        parts = []
        if stdout:
            parts.append(stdout)
        if stderr:
            parts.append("[stderr]\n" + stderr)
        logging.info(f"执行命令: {command}")
        return "\n".join(parts) if parts else "(no output)"
    except Exception as e:
        return f"Execution error: {e}"

def list_skills() -> str:
    skills = load_eligible_skills()
    data = [
        {
            "name": s["name"],
            "description": s["description"],
            "location": s["location"]
        }
        for s in skills
    ]
    return json.dumps(data, ensure_ascii=False, indent=2)

def read_skill_md(skill_name: str) -> str:
    skill = find_skill(skill_name)
    if not skill:
        return f"Skill not found: {skill_name}"
    return read_file(skill["skill_md_path"])

def assistant_message_to_dict(msg) -> Dict[str, Any]:
    data = {
        "role": "assistant",
        "content": msg.content or ""
    }

    if getattr(msg, "tool_calls", None):
        tool_calls = []
        for tc in msg.tool_calls:
            tool_calls.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}"
                }
            })
        data["tool_calls"] = tool_calls

    return data

import re
def extract_json(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("空响应，无法解析 JSON")

    # ```json ... ```
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()

    # 直接解析
    try:
        return json.loads(text)
    except Exception:
        pass

    # 尝试截取最外层 {...}
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        return json.loads(m.group(0))

    raise ValueError(f"无法从文本中提取 JSON: {text[:200]}")

def build_tools(include_execute_skill: bool = True) -> List[Dict]:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "list_skills",
                "description": "列出所有当前可用的 skills",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_skill_md",
                "description": "读取某个 skill 的 SKILL.md 内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {"type": "string"}
                    },
                    "required": ["skill_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读取本地文件内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"}
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "写入本地文件内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["path", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_dir",
                "description": "列出某个目录下的文件和子目录",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"}
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "exec_cmd",
                "description": "执行本地命令",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "cwd": {"type": "string"}
                    },
                    "required": ["command", "cwd"]
                }
            }
        }
    ]

    if include_execute_skill:
        tools.append({
            "type": "function",
            "function": {
                "name": "execute_skill",
                "description": "执行指定 skill 对应的任务。skill 本身不需要 run.py / run.sh，而是由 agent 根据 SKILL.md 调用通用工具完成。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {"type": "string"},
                        "task": {"type": "string"}
                    },
                    "required": ["skill_name", "task"]
                }
            }
        })

    return tools

MAIN_TOOLS = build_tools(include_execute_skill=True)
SKILL_AGENT_TOOLS = build_tools(include_execute_skill=False)

# ====================== 新版：从入口文件执行（推荐方式） ======================
def execute_skill(skill_name: str, tool_args: dict = None):
    # 1. 找到 skill 文件夹
    eligible = load_eligible_skills()
    skill = next((s for s in eligible if s["name"] == skill_name), None)
    if not skill:
        return f"❌ 找不到 skill: {skill_name}"

    skill_dir = Path(skill["location"])

    # 2. 自动查找入口文件（优先级和官方社区一致）
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
        return f"❌ 没有找到执行入口文件！\n请在 {skill_dir} 里放以下任意一个：\n  • run.py\n  • {skill_name}.py\n  • run.sh"

    # 3. 构造命令
    if entrypoint.suffix == ".py":
        cmd_list = ["python", str(entrypoint)]
    elif entrypoint.suffix == ".sh":
        cmd_list = ["bash", str(entrypoint)]
    else:
        cmd_list = [str(entrypoint)]

    # 4. 把 LLM 传来的参数自动转成命令行参数（--key value）
    if tool_args:
        for k, v in tool_args.items():
            cmd_list.extend([f"--{k}", str(v)])

    # 5. 执行（切换目录 + 安全超时）
    try:
        print(f"🚀 执行入口: {entrypoint.name}  (目录: {skill_dir})")
        print(f"   参数: {tool_args}")

        result = subprocess.run(
            cmd_list,
            cwd=skill_dir,
            capture_output=True,
            text=True,
            timeout=60,          # 多步命令可适当调大
            encoding="utf-8"
        )

        output = result.stdout.strip()
        if result.stderr.strip():
            output += "\n[stderr]\n" + result.stderr.strip()

        if result.returncode == 0:
            return f"✅ 执行成功！\n{output or '（无输出）'}"
        else:
            return f"⚠️ 执行失败 (code={result.returncode})\n{output}"

    except subprocess.TimeoutExpired:
        return "❌ 执行超时（超过 60 秒）"
    except Exception as e:
        return f"❌ 执行异常: {str(e)}"

def read_file(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"File not found: {path}"
    return p.read_text(encoding="utf-8")
 
 
baseDir = get_skill_dirs()  # 代表 skill 目录绝对路径，LLM 可用来构造文件路径或命令  
    
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
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task}
    ]

    for _ in range(8):
        resp = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=SKILL_AGENT_TOOLS,
            tool_choice="auto"
        )

        msg = resp.choices[0].message
        messages.append(assistant_message_to_dict(msg))

        if not msg.tool_calls:
            return msg.content or "BLOCKED: skill agent 没有返回内容"

        for tc in msg.tool_calls:
            tool_name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            result = dispatch_tool(tool_name, args, allow_execute_skill=False)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result
            })

    return "BLOCKED: 超过最大工具轮数"

# ====================== Tool Dispatch ======================
def dispatch_tool(
    name: str,
    args: dict,
    allow_execute_skill: bool = True,
    allow_web_search: bool = False
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

    elif name == "execute_skill":
        if not allow_execute_skill:
            return "execute_skill is disabled in this agent context"
        return execute_skill_by_agent(args["skill_name"], args["task"])

    return f"Unknown tool: {name}"

# ====================== Planner ======================
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
7. 如果 web_mode=on，可以在必要时规划“用 web_search 搜索资料/核验事实/整理来源”的步骤。
8. 如果 web_mode=auto，仅当任务涉及最新信息、事实核验、官网/论文/新闻/价格/对比时才规划联网步骤。
9. 如果 deep_think >= 2，请增加必要的验证或回退步骤。
10. 如果 require_citations=true，并且使用了外部资料，请在相关步骤中要求整理来源。
""".strip()

def make_plans(user_input: str, eligible_skills: List[Dict], options: Optional[RunOptions] = None) -> List[Plan]:
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
            plan_id = f"plan_{len(PLAN_STORE) + 1}"
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
            PLAN_STORE[plan.id] = plan
            plans.append(plan)

        if plans:
            return plans

    except Exception as e:
        print(f"[planner JSON解析失败] {e}")
        print(f"[planner原始输出]\n{content}")

    fallback_id = f"plan_{len(PLAN_STORE) + 1}"
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
    PLAN_STORE[fallback.id] = fallback
    return [fallback]

import re

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
        # 取最后一个协议行，避免前面正文里出现类似字符串干扰
        m = matches[-1]
        state = m.group(1).lower()
        detail = m.group(2).strip()

        if state == "done":
            return "done", detail or "执行完成"
        elif state == "blocked":
            return "blocked", detail or "请补充必要信息"
        else:
            return "failed", detail or "执行失败"

    # 没找到协议行，才算失败
    short = text[:300].replace("\n", " ")
    return "failed", f"step agent 未按协议返回结果: {short}"

def build_history_from_plan(plan: Plan) -> List[str]:
    history_lines = []

    # 只拼 current_step_index 之前已经完成/失败的步骤
    for i, step in enumerate(plan.steps):
        if i >= plan.current_step_index:
            break

        if step.status == "done":
            history_lines.append(f"[DONE] {step.title}: {step.output}")
        elif step.status == "failed":
            history_lines.append(f"[FAILED] {step.title}: {step.output}")

    return history_lines

def execute_plan_structured(
    plan_id: str,
    eligible_skills: List[Dict],
    resume_reply: Optional[str] = None,
    options: Optional[RunOptions] = None
) -> PlanExecResult:
    plan = PLAN_STORE.get(plan_id)
    effective_options = normalize_options(options or plan.options)
    plan.options = effective_options
    if not plan:
        return PlanExecResult(
            status="failed",
            message=f"找不到计划: {plan_id}"
        )

    if plan.status == "done":
        return PlanExecResult(
            status="done",
            message=f"计划已完成：{plan.title}"
        )

    history_lines = build_history_from_plan(plan)

    # 已完成步骤历史
    for i, s in enumerate(plan.steps):
        if i >= plan.current_step_index:
            break
        if s.status == "done":
            history_lines.append(f"[DONE] {s.title}: {s.output}")
        elif s.status == "failed":
            history_lines.append(f"[FAILED] {s.title}: {s.output}")

    # 默认从 current_step_index 开始跑
    start_index = plan.current_step_index

    # === 处理 blocked 后的续跑 ===
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

        # 把上次 blocked 信息和用户新回复拼进 history
        if current_step.output:
            history_lines.append(f"[BLOCKED] {current_step.title}: {current_step.output}")
        history_lines.append(f"[USER_REPLY] {resume_reply}")

        plan.awaiting_user_input = False
        plan.pending_question = ""
        plan.status = "running"

    else:
        plan.status = "running"

    # === 正式执行 ===
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

        # failed
        step.status = "failed"
        plan.status = "failed"
        plan.current_step_index = idx

        return PlanExecResult(
            status="failed",
            message=f"计划执行失败：{step.title}\nFAILED: {detail}"
        )

    # 全部跑完
    plan.status = "done"
    plan.awaiting_user_input = False
    plan.pending_question = ""
    plan.current_step_index = len(plan.steps)

    return PlanExecResult(
        status="done",
        message=f"计划执行完成：{plan.title}"
    )

# ====================== Executor ======================
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

def execute_plan(plan_id: str, eligible_skills: List[Dict]) -> str:
    result = execute_plan_structured(plan_id, eligible_skills)

    if result.status == "blocked" and result.need_input:
        return f"{result.message}\nBLOCKED: {result.need_input.question}"

    return result.message

# ====================== UI / CLI ======================
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

def run_direct_agent(user_input: str, eligible_skills: List[Dict], options: Optional[RunOptions] = None) -> str:
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
    )

import shlex

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
    
if __name__ == "__main__":
    eligible = load_eligible_skills()
    print(f"加载到 {len(eligible)} 个合格 Skills")
    for s in eligible:
        print(f"  ✓ {s['name']} @ {s['location']}")

    print("\n可用命令：")
    print("  /skills                查看当前可用 skills")
    print("  /plan 你的任务         生成候选计划")
    print("  /plans                 查看当前内存中的计划")
    print("  /run plan_1            执行指定计划")
    print("  /auto 你的任务         自动生成计划并执行第一个")
    print("  /ask 你的任务          不走 planner，直接让 agent 执行")
    print("  exit / quit            退出")

    while True:
        text = input("\n你：").strip()
        if not text:
            continue

        if text.lower() in ["exit", "quit"]:
            break

        eligible = load_eligible_skills()

        if text == "/skills":
            print(show_skills(eligible))

        elif text == "/plans":
            print(show_plans(list(PLAN_STORE.values())))

        elif text.startswith("/plan "):
            task = text[len("/plan "):].strip()
            plans = make_plans(task, eligible)
            print(show_plans(plans))

        elif text.startswith("/run "):
            plan_id = text[len("/run "):].strip()
            result = execute_plan_structured(plan_id, eligible)
            print(result.message)
            if result.status == "blocked" and result.need_input:
                SESSION.set_pending(result.need_input)
                print(f"BLOCKED: {result.need_input.question}")            
                print(show_plans([PLAN_STORE[plan_id]]) if plan_id in PLAN_STORE else "")
            elif result.status in ("done", "failed"):
                SESSION.clear_pending()
            if plan_id in PLAN_STORE:
                print(show_plans([PLAN_STORE[plan_id]]))                
                
        elif text.startswith("/auto "):
            opts, task = parse_auto_command(text)
            
            if not task:
                print("任务不能为空")
                continue
            print(f"[RUN_OPTIONS] web_mode={opts.web_mode}, deep_think={opts.deep_think}," 
                  f"cite={opts.require_citations}, max_search_rounds={opts.max_search_rounds}")
            
            plans = make_plans(task, eligible, options=opts)
            print(show_plans(plans))
            for p in plans:
                print(f"\n尝试执行 {p.id} ...")
                result = execute_plan_structured(p.id, eligible)
                print(result.message)
                
                if result.status == "blocked" and result.need_input:
                    SESSION.set_pending(result.need_input)
                    print(f"BLOCKED: {result.need_input.question}")
                    print(show_plans([PLAN_STORE[p.id]]))
                    break

                if result.status == "done":
                    SESSION.clear_pending()
                    print(f"\n已成功完成: {p.id}")
                    print(show_plans([PLAN_STORE[p.id]]))
                    break

                if result.status == "failed":
                    SESSION.clear_pending()
                    print(show_plans([PLAN_STORE[p.id]]))
                    
        elif text.startswith("/reply"):
            reply = text[len("/reply "):].strip()
            
            if not SESSION.state.pending:
                print("当前没有待补充的任务")
                continue
            
            pending = SESSION.state.pending
            result = execute_plan_structured(
                pending.plan_id,
                eligible,
                resume_reply=reply
            )
            print(result.message)
        
            if result.status == "blocked" and result.need_input:
                SESSION.set_pending(result.need_input)
                print(f"BLOCKED: {result.need_input.question}")
            else:
                SESSION.clear_pending()
                
            if pending.plan_id in PLAN_STORE:
                print(show_plans(PLAN_STORE[pending.plan_id]))
                
        elif text == "/cancel":
            if not SESSION.state.pending:
                print("当前没有到补充的任务。")
                continue
            
            pending = SESSION.state.pending
            plan = PLAN_STORE.get(pending.plan_id)
            if plan and plan.status ==  "blocked":
                plan.status = "failed"
                plan.awaiting_user_input = False
                plan.pending_question = ""
                
            SESSION.clear_pending()
            print("已取消当前待补充任务")                
                
        elif text.startswith("/ask "):
            task = text[len("/ask "):].strip()
            result = run_direct_agent(task, eligible)
            print(result)

        else:
            if SESSION.state.pending:
                pending = SESSION.state.pending
                print(
                    f"当前有待补充任务: {pending.plan_id} / {pending.step_id} \n"
                    f"问题：{pending.question} \n"
                    f"请使用 /reply 你的补充内容来继续，或 /cancel 取消" 
                )
                continue
            
            plans = make_plans(text, eligible)
            print("已生成候选计划：")
            print(show_plans(plans))
            print("你可以用 /run plan_x 来执行，或者 /auto 直接执行。")