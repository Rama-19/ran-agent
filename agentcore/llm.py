"""
统一 LLM 调用层 —— 支持 OpenAI Responses API 和 Anthropic Messages API。

使用方式:
    from .llm import run_agent
    result = run_agent(system, user, tools, dispatch_fn, model, effort, max_rounds)
"""
import contextvars
import json
from typing import Any, Callable, Dict, List, Optional

# ── Token 用量追踪 ────────────────────────────────────────────────────────────

_usage_ctx: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    "token_usage", default=None
)


def reset_usage() -> None:
    """在每次 agent 调用前重置计数器。"""
    _usage_ctx.set({"input": 0, "output": 0, "provider": "", "model": ""})


def get_usage() -> Dict[str, Any]:
    """返回当前累计用量，{input, output, provider, model}。"""
    return dict(_usage_ctx.get() or {"input": 0, "output": 0, "provider": "", "model": ""})


def _add_usage(input_tokens: int, output_tokens: int) -> None:
    cur = _usage_ctx.get()
    if cur is None:
        _usage_ctx.set({"input": input_tokens, "output": output_tokens, "provider": "", "model": ""})
    else:
        cur["input"] += input_tokens
        cur["output"] += output_tokens


def _set_usage_provider(provider: str, model: str) -> None:
    """记录本次实际使用的 provider 和 model（在 run_agent 入口处调用一次）。"""
    cur = _usage_ctx.get()
    if cur is None:
        _usage_ctx.set({"input": 0, "output": 0, "provider": provider, "model": model})
    else:
        cur["provider"] = provider
        cur["model"] = model


def _is_openai_compat(prov: dict) -> bool:
    """
    判断是否为 OpenAI 兼容代理（路径含 /v1，用 chat/completions 而非原生 API）。
    适用于以 OpenAI 格式代理 Claude 的中转服务。
    """
    base = (prov.get("base_url") or "").rstrip("/")
    return base.endswith("/v1")


def run_agent(
    system_prompt: str,
    user_input: str,
    tools: List[Dict],
    dispatch: Callable[[str, dict], str],
    model: str,
    reasoning_effort: Optional[str] = None,
    max_rounds: int = 8,
    history: Optional[List[Dict]] = None,
) -> str:
    """多轮 agent 循环，根据当前 provider 自动选择实现。"""
    from .config import get_provider_config
    prov = get_provider_config()
    # 在实际调用时记录 provider 和 model，确保与真实使用的一致
    _set_usage_provider(prov["name"], model)

    if prov["name"] == "anthropic":
        if _is_openai_compat(prov):
            # base_url 含 /v1 → OpenAI 兼容代理（chat/completions）
            return _run_chat_completions(
                system_prompt, user_input, tools, dispatch, model,
                reasoning_effort, max_rounds, prov, history
            )
        return _run_anthropic(
            system_prompt, user_input, tools, dispatch, model, max_rounds, prov, history
        )
    else:
        return _run_openai(
            system_prompt, user_input, tools, dispatch, model,
            reasoning_effort, max_rounds, prov, history
        )


# ── OpenAI Responses API ──────────────────────────────────────────────────────


def _run_openai(
    system_prompt, user_input, tools, dispatch,
    model, reasoning_effort, max_rounds, prov, history=None
) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=prov["api_key"], base_url=prov.get("base_url"))

    input_msgs = [{"role": "system", "content": system_prompt}]
    for h in (history or []):
        input_msgs.append({"role": h["role"], "content": h["content"]})
    input_msgs.append({"role": "user", "content": user_input})

    _create_kwargs: Dict[str, Any] = {
        "model": model,
        "input": input_msgs,
        "tools": tools or [],
    }
    if reasoning_effort:
        _create_kwargs["reasoning"] = {"effort": reasoning_effort}

    response = client.responses.create(**_create_kwargs)

    for _ in range(max_rounds):
        if getattr(response, "usage", None):
            _add_usage(
                getattr(response.usage, "input_tokens", 0),
                getattr(response.usage, "output_tokens", 0),
            )

        function_calls = [
            item for item in (getattr(response, "output", []) or [])
            if getattr(item, "type", None) == "function_call"
        ]

        if not function_calls:
            text = getattr(response, "output_text", None)
            if text:
                return text
            try:
                return json.dumps(response.model_dump(), ensure_ascii=False, indent=2)
            except Exception:
                return "(no response)"

        tool_outputs = []
        for fc in function_calls:
            args = json.loads(fc.arguments or "{}")
            result = dispatch(fc.name, args)
            tool_outputs.append({
                "type": "function_call_output",
                "call_id": fc.call_id,
                "output": result,
            })

        _continue_kwargs: Dict[str, Any] = {
            "model": model,
            "previous_response_id": response.id,
            "input": tool_outputs,
            "tools": tools or [],
        }
        if reasoning_effort:
            _continue_kwargs["reasoning"] = {"effort": reasoning_effort}

        response = client.responses.create(**_continue_kwargs)

    return "BLOCKED: 超过最大工具轮数"


# ── OpenAI Chat Completions API（兼容代理）────────────────────────────────────


def _openai_tools_to_chat(tools: List[Dict]) -> List[Dict]:
    """将工具格式转为 Chat Completions 格式（跳过 web_search 等非 function 类型）。"""
    result = []
    for t in tools:
        if t.get("type") == "function":
            result.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                },
            })
    return result


def _run_chat_completions(
    system_prompt, user_input, tools, dispatch,
    model, reasoning_effort, max_rounds, prov, history=None
) -> str:
    """通过 OpenAI Chat Completions API 调用（适用于 OpenAI 兼容代理）。"""
    from openai import OpenAI
    client = OpenAI(api_key=prov["api_key"], base_url=prov.get("base_url"))

    chat_tools = _openai_tools_to_chat(tools or [])

    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for h in (history or []):
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_input})

    for _ in range(max_rounds):
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if chat_tools:
            kwargs["tools"] = chat_tools
            kwargs["tool_choice"] = "auto"

        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as e:
            return f"FAILED: Chat Completions API 错误 — {e}"

        if getattr(response, "usage", None):
            _add_usage(
                getattr(response.usage, "prompt_tokens", 0),
                getattr(response.usage, "completion_tokens", 0),
            )

        msg = response.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []

        if not tool_calls:
            return msg.content or "(no response)"

        messages.append(msg)

        for tc in tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            result = dispatch(tc.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    return "BLOCKED: 超过最大工具轮数"


# ── Anthropic Messages API ────────────────────────────────────────────────────


def _openai_tools_to_anthropic(tools: List[Dict]) -> List[Dict]:
    """将 OpenAI Responses API 工具格式转为 Anthropic 格式。"""
    result = []
    for t in tools:
        if t.get("type") == "function":
            result.append({
                "name": t["name"],
                "description": t.get("description", ""),
                "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
            })
        elif t.get("type") == "web_search":
            result.append({"type": "web_search_20250305"})
    return result


def _run_anthropic(
    system_prompt, user_input, tools, dispatch, model, max_rounds, prov, history=None
) -> str:
    try:
        import anthropic
    except ImportError:
        return "FAILED: 未安装 anthropic SDK，请运行 pip install anthropic"

    client_kwargs = {"api_key": prov["api_key"]}
    if prov.get("base_url"):
        # Anthropic SDK 会自动拼接 /v1/messages，若 base_url 已含 /v1 则去掉尾部的 /v1
        base = prov["base_url"].rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        client_kwargs["base_url"] = base
    client = anthropic.Anthropic(**client_kwargs)
    anthropic_tools = _openai_tools_to_anthropic(tools)
    messages: List[Dict[str, Any]] = []
    for h in (history or []):
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_input})

    for _ in range(max_rounds):
        kwargs: Dict[str, Any] = {
            "model": model,
            "system": system_prompt,
            "messages": messages,
            "max_tokens": 8192,
        }
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        try:
            response = client.messages.create(**kwargs)
        except anthropic.APIStatusError as e:
            return f"FAILED: Anthropic API 错误 {e.status_code} — {e.message}"
        except anthropic.APIConnectionError as e:
            return f"FAILED: 无法连接 Anthropic API — {e}"

        if getattr(response, "usage", None):
            _add_usage(
                getattr(response.usage, "input_tokens", 0),
                getattr(response.usage, "output_tokens", 0),
            )

        tool_uses = [b for b in response.content if b.type == "tool_use"]

        if not tool_uses:
            texts = [b.text for b in response.content if hasattr(b, "text")]
            return "\n".join(texts) if texts else "(no response)"

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for tu in tool_uses:
            result = dispatch(tu.name, tu.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": result,
            })

        messages.append({"role": "user", "content": tool_results})

    return "BLOCKED: 超过最大工具轮数"
