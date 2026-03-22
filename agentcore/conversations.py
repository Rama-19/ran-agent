"""对话历史持久化 —— 按用户隔离，每个会话存储为独立的 JSON 文件。"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import DATA_DIR

# 全局目录（兼容旧数据，不再写入）
_GLOBAL_CONV_DIR = DATA_DIR / "conversations"


def _conv_dir(user_id: Optional[str]) -> Path:
    if user_id:
        return DATA_DIR / "users" / user_id / "conversations"
    return _GLOBAL_CONV_DIR


def _conv_path(conv_id: str, user_id: Optional[str]) -> Path:
    return _conv_dir(user_id) / f"{conv_id}.json"


def _load_conv(conv_id: str, user_id: Optional[str] = None) -> Optional[dict]:
    p = _conv_path(conv_id, user_id)
    if not p.exists():
        return None
    try:
        content = p.read_text(encoding="utf-8").strip()
        return json.loads(content) if content else None
    except (json.JSONDecodeError, OSError):
        return None


def _save_conv(data: dict, user_id: Optional[str] = None) -> None:
    d = _conv_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{data['id']}.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_conversations(user_id: Optional[str] = None) -> List[dict]:
    """返回指定用户的会话元数据列表，按更新时间倒序。"""
    d = _conv_dir(user_id)
    if not d.exists():
        return []
    convs = []
    for p in d.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            convs.append({
                "id": data["id"],
                "title": data["title"],
                "created_at": data["created_at"],
                "updated_at": data["updated_at"],
                "message_count": len(data.get("messages", [])),
            })
        except Exception:
            pass
    convs.sort(key=lambda x: x["updated_at"], reverse=True)
    return convs


def create_conversation(title: str = "", user_id: Optional[str] = None) -> dict:
    """创建新会话，返回会话元数据（不含消息列表）。"""
    conv_id = uuid.uuid4().hex[:12]
    now = datetime.now().isoformat()
    data = {
        "id": conv_id,
        "title": title or "新会话",
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }
    _save_conv(data, user_id)
    return {k: v for k, v in data.items() if k != "messages"} | {"message_count": 0}


def get_conversation(conv_id: str, user_id: Optional[str] = None) -> Optional[dict]:
    """返回完整会话（含消息列表）。"""
    return _load_conv(conv_id, user_id)


def append_message(conv_id: str, role: str, text: str, user_id: Optional[str] = None) -> Optional[str]:
    """追加一条消息；若首条用户消息则自动更新标题。返回新消息 id，失败返回 None。"""
    data = _load_conv(conv_id, user_id)
    if data is None:
        return None
    msg_id = uuid.uuid4().hex[:8]
    data["messages"].append({
        "id": msg_id,
        "role": role,
        "text": text,
        "timestamp": datetime.now().isoformat(),
    })
    data["updated_at"] = datetime.now().isoformat()
    if role == "user" and data["title"] == "新会话":
        data["title"] = text[:30] + ("…" if len(text) > 30 else "")
    _save_conv(data, user_id)
    return msg_id


def delete_message(conv_id: str, message_id: str, user_id: Optional[str] = None) -> list:
    """删除指定消息及其配对消息（user↔agent）。返回被删除的 id 列表。"""
    data = _load_conv(conv_id, user_id)
    if data is None:
        return []
    messages = data["messages"]
    idx = next((i for i, m in enumerate(messages) if m["id"] == message_id), -1)
    if idx == -1:
        return []
    msg = messages[idx]
    to_delete = {message_id}
    if msg["role"] == "user" and idx + 1 < len(messages) and messages[idx + 1]["role"] in ("agent", "assistant"):
        to_delete.add(messages[idx + 1]["id"])
    elif msg["role"] in ("agent", "assistant") and idx > 0 and messages[idx - 1]["role"] == "user":
        to_delete.add(messages[idx - 1]["id"])
    data["messages"] = [m for m in messages if m["id"] not in to_delete]
    data["updated_at"] = datetime.now().isoformat()
    _save_conv(data, user_id)
    return list(to_delete)


def delete_conversation(conv_id: str, user_id: Optional[str] = None) -> bool:
    p = _conv_path(conv_id, user_id)
    if p.exists():
        p.unlink()
        return True
    return False


def rename_conversation(conv_id: str, title: str, user_id: Optional[str] = None) -> bool:
    data = _load_conv(conv_id, user_id)
    if data is None:
        return False
    data["title"] = title
    data["updated_at"] = datetime.now().isoformat()
    _save_conv(data, user_id)
    return True
