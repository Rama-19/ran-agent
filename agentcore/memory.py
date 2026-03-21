"""Agent 记忆 —— 持久化键值存储（全局 + 按用户隔离）。"""
import json
from pathlib import Path
from typing import Any, Dict, Optional

from .config import DATA_DIR

MEMORY_FILE = DATA_DIR / "memory.json"

_cache: Dict[str, Any] = {}


def _load() -> None:
    global _cache
    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE, encoding="utf-8") as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}


def _save() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(_cache, f, ensure_ascii=False, indent=2)


_load()  # 模块加载时读取


def get(key: str) -> Optional[Any]:
    return _cache.get(key)


def set_value(key: str, value: str) -> None:
    _cache[key] = value
    _save()


def delete(key: str) -> bool:
    existed = key in _cache
    if existed:
        del _cache[key]
        _save()
    return existed


def all_entries() -> Dict[str, Any]:
    return dict(_cache)


def clear() -> None:
    _cache.clear()
    _save()


def format_for_prompt() -> str:
    """生成可注入 system prompt 的记忆块。"""
    if not _cache:
        return ""
    lines = ["<agent_memory>"]
    for k, v in _cache.items():
        lines.append(f"  <item key={k!r}>{v}</item>")
    lines.append("</agent_memory>")
    return "\n".join(lines)


# ── Per-user memory ───────────────────────────────────────────────────────────

class UserMemory:
    """每个用户独立的持久化键值记忆。"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._file = DATA_DIR / "users" / user_id / "memory.json"
        self._cache: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self._file.exists():
            try:
                self._cache = json.loads(self._file.read_text(encoding="utf-8"))
            except Exception:
                self._cache = {}

    def _save(self) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(
            json.dumps(self._cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get(self, key: str) -> Optional[Any]:
        return self._cache.get(key)

    def set_value(self, key: str, value: str) -> None:
        self._cache[key] = value
        self._save()

    def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            self._save()
            return True
        return False

    def all_entries(self) -> Dict[str, Any]:
        return dict(self._cache)

    def clear(self) -> None:
        self._cache.clear()
        self._save()

    def format_for_prompt(self) -> str:
        if not self._cache:
            return ""
        lines = ["<agent_memory>"]
        for k, v in self._cache.items():
            lines.append(f"  <item key={k!r}>{v}</item>")
        lines.append("</agent_memory>")
        return "\n".join(lines)


_user_memories: Dict[str, UserMemory] = {}


def get_user_memory(user_id: str) -> UserMemory:
    if user_id not in _user_memories:
        _user_memories[user_id] = UserMemory(user_id)
    return _user_memories[user_id]
