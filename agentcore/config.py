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


def get_provider_config(name: str = None) -> dict:
    """返回当前激活的 LLM provider 配置。
    优先级：用户个人配置 > openclaw.json > 环境变量。"""
    # 优先使用当前用户的个人配置
    user_id = _current_user_id.get()
    user_cfg = load_user_config(user_id) if user_id else {}
    user_prov = user_cfg.get("provider", {})

    cfg_prov = user_prov if user_prov.get("api_key") or user_prov.get("name") else config.get("provider", {})
    if name is None:
        name = cfg_prov.get("name") or os.environ.get("PROVIDER", "openai")
    # 仅当查询的 provider 与当前激活的 provider 一致时，才读取 openclaw.json 中的覆盖值
    active_name = cfg_prov.get("name") or os.environ.get("PROVIDER", "openai")
    stored = cfg_prov if name == active_name else {}

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
