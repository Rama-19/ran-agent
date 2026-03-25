import contextvars
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv

load_dotenv()

# ── OpenAI ────────────────────────────────────────────────────────────────────
api_key = os.environ.get("OPENAI_API_KEY")
base_url = os.environ.get("OPENAI_BASE_URL")
model_name = os.environ.get("OPENAI_MODEL", "gpt-4o")
deep_model_name = os.environ.get("OPENAI_MODEL_DEEP", "o1")

# ── Anthropic ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_DEEP_MODEL = os.environ.get("ANTHROPIC_DEEP_MODEL", "claude-opus-4-6")

# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")
OLLAMA_DEEP_MODEL = os.environ.get("OLLAMA_DEEP_MODEL", "llama3")

LAST_BLOCKED = None
now = datetime.now().strftime("%Y-%m-%d")

_log_dir = Path(__file__).parent.parent / "log"
_log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename=str(_log_dir / f"{now}.log"),
    filemode="a",
    encoding="utf-8",
)

# 项目根目录 = agentcore 的上级目录
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = DATA_DIR / "openclaw.json"
print(f"使用配置文件: {CONFIG_PATH}")

WORKSPACE_ENV = os.getenv("WORKSPACE") or str(Path.home() / "workspace")
print(f"工作空间路径: {WORKSPACE_ENV}")

WebMode = Literal["auto", "on", "off"]

# ── Per-user config context ────────────────────────────────────────────────────
_current_user_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_user_id", default=None
)


def set_current_user(user_id) -> None:
    """在路由 handler 里调用，让后续 get_provider_config() 自动使用该用户的配置。
    传入 str 设置用户，传入 None 或 Token 均清除。"""
    if isinstance(user_id, str):
        _current_user_id.set(user_id)
    else:
        _current_user_id.set(None)


def _user_config_path(user_id: str) -> Path:
    return DATA_DIR / "users" / user_id / "config.json"


def load_user_config(user_id: str) -> dict:
    p = _user_config_path(user_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_user_config(user_id: str, cfg: dict) -> None:
    p = _user_config_path(user_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"skills": {"load": {"extraDirs": []}, "entries": {}}}


config = load_config()


def _resolve_user_prov(user_prov: dict, name: str) -> dict:
    """从用户 provider 配置（新嵌套或旧扁平格式）中取出指定供应商的配置。"""
    # 新格式：user_prov 含已知供应商子键
    if "openai" in user_prov or "anthropic" in user_prov or "ollama" in user_prov:
        return user_prov.get(name, {})
    # 旧扁平格式：active 供应商与查询匹配时才使用
    old_name = user_prov.get("name", "")
    return user_prov if old_name == name else {}


def get_provider_config(name: str = None) -> dict:
    """返回当前激活的 LLM provider 配置。
    优先级：用户个人配置 > openclaw.json > 环境变量。"""
    # 优先使用当前用户的个人配置
    user_id = _current_user_id.get()
    user_cfg = load_user_config(user_id) if user_id else {}
    user_prov = user_cfg.get("provider", {})

    # 确定激活的供应商名称
    if name is None:
        # 新格式用 active，旧格式用 name，最后回退环境变量
        name = (user_prov.get("active") or user_prov.get("name")
                or config.get("provider", {}).get("name")
                or os.environ.get("PROVIDER", "openai"))

    stored_user = _resolve_user_prov(user_prov, name)
    # 若用户没有该供应商配置，回退到 openclaw.json
    global_prov = config.get("provider", {})
    global_name = global_prov.get("name", "openai")
    stored = stored_user if stored_user else (global_prov if global_name == name else {})

    if name == "anthropic":
        key = stored.get("api_key") or ANTHROPIC_API_KEY
        if not key:
            raise RuntimeError(
                "缺少 ANTHROPIC_API_KEY（请在 .env 或 openclaw.json provider.api_key 中配置）"
            )
        return {
            "name": "anthropic",
            "api_key": key,
            "base_url": stored.get("base_url") or ANTHROPIC_BASE_URL,
            "model": stored.get("model") or ANTHROPIC_MODEL,
            "deep_model": stored.get("deep_model") or ANTHROPIC_DEEP_MODEL,
        }
    elif name == "ollama":
        return {
            "name": "ollama",
            "api_key": stored.get("api_key") or "ollama",  # Ollama 不需要真实 key
            "base_url": stored.get("base_url") or OLLAMA_BASE_URL,
            "model": stored.get("model") or OLLAMA_MODEL,
            "deep_model": stored.get("deep_model") or OLLAMA_DEEP_MODEL,
        }
    else:
        key = stored.get("api_key") or api_key
        if not key:
            raise RuntimeError(
                "缺少 OPENAI_API_KEY（请在 .env 或 openclaw.json provider.api_key 中配置）"
            )
        return {
            "name": "openai",
            "api_key": key,
            "base_url": stored.get("base_url") or base_url,
            "model": stored.get("model") or model_name,
            "deep_model": stored.get("deep_model") or deep_model_name,
        }


def update_provider_config(updates: dict) -> None:
    """更新 provider 配置并写入 openclaw.json（同时更新内存中的 config）。"""
    config.setdefault("provider", {}).update(updates)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_smtp_config() -> dict:
    """读取最新 SMTP 配置（每次从磁盘加载，支持热更新）。
    优先级：openclaw.json > 环境变量（QQ_EMAIL_SENDER / QQ_EMAIL_AUTH_CODE）。"""
    fresh = load_config()
    smtp = fresh.get("smtp", {})
    return {
        "host": smtp.get("host") or os.environ.get("SMTP_HOST", "smtp.qq.com"),
        "port": int(smtp.get("port") or os.environ.get("SMTP_PORT", 465)),
        "username": smtp.get("username") or os.environ.get("QQ_EMAIL_SENDER", ""),
        "password": smtp.get("password") or os.environ.get("QQ_EMAIL_AUTH_CODE", ""),
        "from_name": smtp.get("from_name") or os.environ.get("SMTP_FROM_NAME", "Agent"),
    }


def update_smtp_config(updates: dict) -> None:
    """更新 SMTP 配置并写入 openclaw.json。"""
    config.setdefault("smtp", {
        "host": "smtp.qq.com",
        "port": 465,
        "username": "",
        "password": "",
        "from_name": "Agent",
    }).update(updates)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_auth_config() -> dict:
    """读取 auth 配置（jwt_secret 存储在此）。"""
    return config.get("auth", {})


def update_auth_config(updates: dict) -> None:
    """更新 auth 配置并写入 openclaw.json。"""
    config.setdefault("auth", {}).update(updates)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
