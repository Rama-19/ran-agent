import json
import logging
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Any

from .models import RunOptions, normalize_options
from .skills import load_eligible_skills, find_skill
from . import memory as mem
from .memory import get_user_memory
from .config import _current_user_id


def _get_mem():
    """返回当前用户的记忆对象，无用户时回退到全局记忆。"""
    user_id = _current_user_id.get()
    return get_user_memory(user_id) if user_id else mem


def safe_decode(data: bytes) -> str:
    if not data:
        return ""
    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")


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
        {"name": s["name"], "description": s["description"], "location": s["location"]}
        for s in skills
    ]
    return json.dumps(data, ensure_ascii=False, indent=2)


def read_skill_md(skill_name: str) -> str:
    skill = find_skill(skill_name)
    if not skill:
        return f"Skill not found: {skill_name}"
    return read_file(skill["skill_md_path"])


# ── HTTP 请求工具 ──────────────────────────────────────────────────────────────


def http_request(method: str, url: str, headers: str = "{}", body: str = "") -> str:
    """发起 HTTP 请求，类似 curl。headers 为 JSON 字符串，body 为请求体字符串。"""
    try:
        h = json.loads(headers) if headers.strip() else {}
        req = urllib.request.Request(url, method=method.upper())
        for k, v in h.items():
            req.add_header(k, str(v))
        data = body.encode("utf-8") if body else None
        with urllib.request.urlopen(req, data=data, timeout=30) as resp:
            status = resp.status
            content = resp.read().decode("utf-8", errors="replace")
            return f"HTTP {status}\n{content}"
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        return f"HTTP {e.code} {e.reason}\n{body_text}"
    except Exception as e:
        return f"请求失败: {e}"


# ── 记忆工具 ──────────────────────────────────────────────────────────────────


def memory_tool_get(key: str) -> str:
    val = _get_mem().get(key)
    return json.dumps(val, ensure_ascii=False) if val is not None else f"(key '{key}' 不存在)"


def memory_tool_set(key: str, value: str) -> str:
    _get_mem().set_value(key, value)
    return f"已保存 memory[{key!r}]"


def memory_tool_delete(key: str) -> str:
    return f"已删除 memory[{key!r}]" if _get_mem().delete(key) else f"(key '{key}' 不存在)"


def memory_tool_list() -> str:
    entries = _get_mem().all_entries()
    if not entries:
        return "(记忆为空)"
    return json.dumps(entries, ensure_ascii=False, indent=2)


def assistant_message_to_dict(msg) -> Dict[str, Any]:
    data = {"role": "assistant", "content": msg.content or ""}
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


def build_responses_tools(
    include_execute_skill: bool = True,
    include_web_search: bool = False
) -> List[Dict]:
    tools = [
        {
            "type": "function",
            "name": "list_skills",
            "description": "列出所有当前可用的 skills",
            "parameters": {"type": "object", "properties": {}}
        },
        {
            "type": "function",
            "name": "read_skill_md",
            "description": "读取某个 skill 的 SKILL.md 内容",
            "parameters": {
                "type": "object",
                "properties": {"skill_name": {"type": "string"}},
                "required": ["skill_name"]
            }
        },
        {
            "type": "function",
            "name": "read_file",
            "description": "读取本地文件内容",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        },
        {
            "type": "function",
            "name": "write_file",
            "description": "写入本地文件内容",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"]
            }
        },
        {
            "type": "function",
            "name": "list_dir",
            "description": "列出某个目录下的文件和子目录",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        },
        {
            "type": "function",
            "name": "exec_cmd",
            "description": "执行本地命令",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}},
                "required": ["command", "cwd"]
            }
        },
    ]

    # HTTP 请求
    tools.append({
        "type": "function",
        "name": "http_request",
        "description": "发起 HTTP 请求（类似 curl）。headers 为 JSON 字符串，body 为字符串。",
        "parameters": {
            "type": "object",
            "properties": {
                "method": {"type": "string", "description": "GET/POST/PUT/DELETE 等"},
                "url": {"type": "string"},
                "headers": {"type": "string", "description": 'JSON 格式，如 {"Authorization":"Bearer xxx"}'},
                "body": {"type": "string", "description": "请求体（可选）"},
            },
            "required": ["method", "url"]
        }
    })

    # 记忆工具
    tools += [
        {
            "type": "function",
            "name": "memory_get",
            "description": "读取一条 agent 记忆（key-value）",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"]
            }
        },
        {
            "type": "function",
            "name": "memory_set",
            "description": "保存或更新一条 agent 记忆",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string"}, "value": {"type": "string"}},
                "required": ["key", "value"]
            }
        },
        {
            "type": "function",
            "name": "memory_delete",
            "description": "删除一条 agent 记忆",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"]
            }
        },
        {
            "type": "function",
            "name": "memory_list",
            "description": "列出所有 agent 记忆",
            "parameters": {"type": "object", "properties": {}}
        },
    ]

    if include_web_search:
        tools.append({"type": "web_search"})

    if include_execute_skill:
        tools.append({
            "type": "function",
            "name": "execute_skill",
            "description": "执行指定 skill 对应的任务。skill 本身不需要 run.py / run.sh，而是由 agent 根据 SKILL.md 调用通用工具完成。",
            "parameters": {
                "type": "object",
                "properties": {"skill_name": {"type": "string"}, "task": {"type": "string"}},
                "required": ["skill_name", "task"]
            }
        })

    return tools


def build_tools(include_execute_skill: bool = True) -> List[Dict]:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "list_skills",
                "description": "列出所有当前可用的 skills",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_skill_md",
                "description": "读取某个 skill 的 SKILL.md 内容",
                "parameters": {
                    "type": "object",
                    "properties": {"skill_name": {"type": "string"}},
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
                    "properties": {"path": {"type": "string"}},
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
                    "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
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
                    "properties": {"path": {"type": "string"}},
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
                    "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}},
                    "required": ["command", "cwd"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "http_request",
                "description": "发起 HTTP 请求（类似 curl）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "method": {"type": "string"},
                        "url": {"type": "string"},
                        "headers": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["method", "url"]
                }
            }
        },
        {"type": "function", "function": {"name": "memory_get", "description": "读取 agent 记忆", "parameters": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}}},
        {"type": "function", "function": {"name": "memory_set", "description": "保存 agent 记忆", "parameters": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"]}}},
        {"type": "function", "function": {"name": "memory_delete", "description": "删除 agent 记忆", "parameters": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}}},
        {"type": "function", "function": {"name": "memory_list", "description": "列出所有 agent 记忆", "parameters": {"type": "object", "properties": {}}}},
    ]

    if include_execute_skill:
        tools.append({
            "type": "function",
            "function": {
                "name": "execute_skill",
                "description": "执行指定 skill 对应的任务。skill 本身不需要 run.py / run.sh，而是由 agent 根据 SKILL.md 调用通用工具完成。",
                "parameters": {
                    "type": "object",
                    "properties": {"skill_name": {"type": "string"}, "task": {"type": "string"}},
                    "required": ["skill_name", "task"]
                }
            }
        })

    return tools


def get_response_tools(options: Optional[RunOptions] = None, include_execute_skill: bool = True) -> List[Dict]:
    opts = normalize_options(options)
    return build_responses_tools(
        include_execute_skill=include_execute_skill,
        include_web_search=(opts.web_mode != "off")
    )


MAIN_TOOLS = build_tools(include_execute_skill=True)
SKILL_AGENT_TOOLS = build_tools(include_execute_skill=False)
