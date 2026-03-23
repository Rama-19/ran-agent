"""每用户 Token 用量追踪与费用计算。

记录格式（JSONL，每行一条）:
  {"ts": "...", "provider": "openai", "model": "gpt-4o",
   "input": 1200, "output": 350, "cost_usd": 0.00655}
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import os

from .config import DATA_DIR

# ── 汇率 ──────────────────────────────────────────────────────────────────────
CNY_RATE: float = float(os.environ.get("USD_TO_CNY", "7.3"))  # 1 USD = N CNY

# ── 定价表：USD / 百万 tokens ─────────────────────────────────────────────────
# 格式: "model-name-关键词": {"input": price, "output": price}
# 使用 _match_price() 做子串匹配，支持模型名包含版本号的情况

_PRICE_TABLE: List[tuple[str, Dict[str, float]]] = [
    # ── OpenAI ────────────────────────────────────────────────────────────────
    ("o3",          {"input": 10.0,  "output": 40.0}),
    ("o1-mini",     {"input": 3.0,   "output": 12.0}),
    ("o1",          {"input": 15.0,  "output": 60.0}),
    ("o3-mini",     {"input": 1.1,   "output": 4.4}),
    ("gpt-4o-mini", {"input": 0.15,  "output": 0.6}),
    ("gpt-4o",      {"input": 2.5,   "output": 10.0}),
    ("gpt-4-turbo", {"input": 10.0,  "output": 30.0}),
    ("gpt-4",       {"input": 30.0,  "output": 60.0}),
    ("gpt-3.5",     {"input": 0.5,   "output": 1.5}),
    # ── Anthropic ─────────────────────────────────────────────────────────────
    ("claude-opus-4",    {"input": 15.0,  "output": 75.0}),
    ("claude-sonnet-4",  {"input": 3.0,   "output": 15.0}),
    ("claude-haiku-4",   {"input": 0.8,   "output": 4.0}),
    ("claude-3-opus",    {"input": 15.0,  "output": 75.0}),
    ("claude-3-5-sonnet",{"input": 3.0,   "output": 15.0}),
    ("claude-3-5-haiku", {"input": 0.8,   "output": 4.0}),
    ("claude-3-sonnet",  {"input": 3.0,   "output": 15.0}),
    ("claude-3-haiku",   {"input": 0.25,  "output": 1.25}),
]

_FALLBACK_PRICE: Dict[str, float] = {"input": 2.0, "output": 8.0}  # 未匹配时的估算值


def _match_price(model: str) -> Dict[str, float]:
    """按模型名子串匹配定价，越靠前越精确。"""
    lower = model.lower()
    for keyword, price in _PRICE_TABLE:
        if keyword in lower:
            return price
    return _FALLBACK_PRICE


def calc_cost(model: str, input_tokens: int, output_tokens: int) -> tuple[float, float]:
    """计算本次调用费用，返回 (cost_usd, cost_cny)。"""
    price = _match_price(model)
    usd = (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000
    usd = round(usd, 8)
    cny = round(usd * CNY_RATE, 6)
    return usd, cny


def get_price(model: str) -> Dict[str, float]:
    """返回模型的定价（USD/M tokens）。"""
    return _match_price(model)


# ── 存储 ──────────────────────────────────────────────────────────────────────

def _usage_file(user_id: str) -> Path:
    return DATA_DIR / "users" / user_id / "usage.jsonl"


def record(
    user_id: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """追加一条用量记录。input/output 为 0 时跳过。"""
    if not input_tokens and not output_tokens:
        return
    cost_usd, cost_cny = calc_cost(model, input_tokens, output_tokens)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model": model,
        "input": input_tokens,
        "output": output_tokens,
        "cost_usd": cost_usd,
        "cost_cny": cost_cny,
    }
    f = _usage_file(user_id)
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _load_records(user_id: str) -> List[Dict[str, Any]]:
    f = _usage_file(user_id)
    if not f.exists():
        return []
    records = []
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except Exception:
                pass
    return records


# ── 统计 ──────────────────────────────────────────────────────────────────────

def get_stats(user_id: str) -> Dict[str, Any]:
    """
    返回该用户的用量统计：
      - total: 全部汇总
      - by_model: 按模型分组
      - recent: 最近 20 条记录
      - pricing: 当前定价表
    """
    records = _load_records(user_id)

    total_input = sum(r["input"] for r in records)
    total_output = sum(r["output"] for r in records)
    total_usd = sum(r["cost_usd"] for r in records)
    total_cny = sum(r.get("cost_cny", r["cost_usd"] * CNY_RATE) for r in records)

    by_model: Dict[str, Dict[str, Any]] = {}
    for r in records:
        key = f"{r['provider']}/{r['model']}"
        if key not in by_model:
            by_model[key] = {"provider": r["provider"], "model": r["model"],
                             "input": 0, "output": 0, "cost_usd": 0.0, "cost_cny": 0.0, "calls": 0}
        by_model[key]["input"] += r["input"]
        by_model[key]["output"] += r["output"]
        by_model[key]["cost_usd"] = round(by_model[key]["cost_usd"] + r["cost_usd"], 8)
        by_model[key]["cost_cny"] = round(by_model[key]["cost_cny"] + r.get("cost_cny", r["cost_usd"] * CNY_RATE), 6)
        by_model[key]["calls"] += 1

    # 定价表（仅列出常用模型）
    pricing = [
        {"keyword": kw, "input_per_m": p["input"], "output_per_m": p["output"]}
        for kw, p in _PRICE_TABLE
    ]

    return {
        "total": {
            "input": total_input,
            "output": total_output,
            "cost_usd": round(total_usd, 6),
            "cost_cny": round(total_cny, 4),
            "calls": len(records),
        },
        "by_model": sorted(by_model.values(), key=lambda x: x["cost_usd"], reverse=True),
        "recent": list(reversed(records[-20:])),
        "pricing": pricing,
    }
