"""用户认证模块：注册、验证码、登录、JWT。"""
from __future__ import annotations

import json
import os
import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from .config import (
    DATA_DIR, get_auth_config, get_smtp_config,
    update_auth_config, update_smtp_config,
    load_user_config, save_user_config,
)
from .email_sender import send_verification, send_password_reset

# ── Password hashing ──────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

def _verify_password(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode(), hashed.encode())

# ── JWT ───────────────────────────────────────────────────────────────────────
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 天


def _get_jwt_secret() -> str:
    env_secret = os.environ.get("JWT_SECRET")
    if env_secret:
        return env_secret
    auth_cfg = get_auth_config()
    stored = auth_cfg.get("jwt_secret")
    if stored:
        return stored
    new_secret = secrets.token_hex(32)
    update_auth_config({"jwt_secret": new_secret})
    return new_secret


def _create_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, _get_jwt_secret(), algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    return jwt.decode(token, _get_jwt_secret(), algorithms=[ALGORITHM])


# ── Users storage ─────────────────────────────────────────────────────────────
USERS_PATH = DATA_DIR / "users.json"


def _load_users() -> dict:
    if USERS_PATH.exists():
        with open(USERS_PATH, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def _save_users(users: dict) -> None:
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def _get_user_by_email(email: str) -> Optional[dict]:
    for user in _load_users().values():
        if user.get("email") == email:
            return user
    return None


def _create_user(email: str, hashed_password: str) -> dict:
    users = _load_users()
    user_id = secrets.token_hex(4)
    while user_id in users:
        user_id = secrets.token_hex(4)
    user = {
        "id": user_id,
        "email": email,
        "hashed_password": hashed_password,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_active": True,
    }
    users[user_id] = user
    _save_users(users)
    return user


# ── In-memory verification code cache ────────────────────────────────────────
# email -> {code, expires_at, hashed_password}
_pending: dict[str, dict] = {}

# ── FastAPI dependency ────────────────────────────────────────────────────────
_security = HTTPBearer()


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(_security)) -> dict:
    token = creds.credentials
    try:
        payload = _decode_token(token)
        email: Optional[str] = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="无效的 token")
    except JWTError:
        raise HTTPException(status_code=401, detail="无效或过期的 token")
    user = _get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if not user.get("is_active"):
        raise HTTPException(status_code=401, detail="账户未激活")
    return user


# ── Pydantic schemas ──────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: str
    password: str


class VerifyRequest(BaseModel):
    email: str
    code: str


class LoginRequest(BaseModel):
    email: str
    password: str


class SmtpConfigRequest(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    from_name: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str


class UserProviderConfigRequest(BaseModel):
    name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    deep_model: Optional[str] = None


# In-memory reset code cache (separate from _pending)
_reset_pending: dict[str, dict] = {}  # email -> {code, expires_at}


# ── Router ────────────────────────────────────────────────────────────────────
router = APIRouter()


@router.post("/register")
def register(req: RegisterRequest):
    """发送邮箱验证码，注册前调用。"""
    if _get_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="该邮箱已注册")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")

    hashed = _hash_password(req.password)
    code = "".join(random.choices(string.digits, k=6))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    _pending[req.email] = {
        "code": code,
        "expires_at": expires_at,
        "hashed_password": hashed,
    }

    try:
        send_verification(req.email, code)
    except Exception as e:
        _pending.pop(req.email, None)
        raise HTTPException(status_code=500, detail=f"邮件发送失败: {e}")

    return {"message": "验证码已发送，请查收邮箱（5 分钟内有效）"}


@router.post("/verify")
def verify(req: VerifyRequest):
    """校验验证码，建账户，返回 JWT。"""
    entry = _pending.get(req.email)
    if not entry:
        raise HTTPException(status_code=400, detail="未找到注册请求，请重新注册")
    if datetime.now(timezone.utc) > entry["expires_at"]:
        _pending.pop(req.email, None)
        raise HTTPException(status_code=400, detail="验证码已过期，请重新注册")
    if entry["code"] != req.code:
        raise HTTPException(status_code=400, detail="验证码错误")

    user = _create_user(req.email, entry["hashed_password"])
    _pending.pop(req.email, None)

    token = _create_token({"sub": user["email"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user["id"], "email": user["email"]},
    }


@router.post("/login")
def login(req: LoginRequest):
    """邮箱+密码登录，返回 JWT。"""
    user = _get_user_by_email(req.email)
    if not user or not _verify_password(req.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not user.get("is_active"):
        raise HTTPException(status_code=401, detail="账户未激活")

    token = _create_token({"sub": user["email"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user["id"], "email": user["email"]},
    }


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """返回当前用户信息。"""
    return {"id": current_user["id"], "email": current_user["email"]}


@router.get("/smtp-config")
def get_smtp(current_user: dict = Depends(get_current_user)):
    """读取 SMTP 配置（密码脱敏）。"""
    cfg = get_smtp_config()
    result = dict(cfg)
    pwd = result.get("password", "")
    result["password"] = "****" if pwd else ""
    return result


@router.post("/smtp-config")
def update_smtp(req: SmtpConfigRequest, current_user: dict = Depends(get_current_user)):
    """更新 SMTP 配置。"""
    updates: dict = {}
    if req.host is not None:
        updates["host"] = req.host
    if req.port is not None:
        updates["port"] = req.port
    if req.username is not None:
        updates["username"] = req.username
    if req.password is not None and req.password != "****":
        updates["password"] = req.password
    if req.from_name is not None:
        updates["from_name"] = req.from_name
    if updates:
        update_smtp_config(updates)
    return {"message": "SMTP 配置已更新"}


# ── 密码修改 & 重置 ────────────────────────────────────────────────────────────

@router.post("/change-password")
def change_password(req: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    """修改密码（需要当前密码）。"""
    if not _verify_password(req.current_password, current_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="当前密码错误")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")
    users = _load_users()
    users[current_user["id"]]["hashed_password"] = _hash_password(req.new_password)
    _save_users(users)
    return {"message": "密码已修改"}


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    """发送密码重置验证码（无论邮箱是否存在，均返回相同提示，防止枚举）。"""
    user = _get_user_by_email(req.email)
    code = "".join(random.choices(string.digits, k=6))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    _reset_pending[req.email] = {"code": code, "expires_at": expires_at}

    if user:
        try:
            send_password_reset(req.email, code)
        except Exception as e:
            _reset_pending.pop(req.email, None)
            raise HTTPException(status_code=500, detail=f"邮件发送失败: {e}")

    return {"message": "如果该邮箱已注册，重置验证码已发送（5 分钟内有效）"}


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    """验证重置码并设置新密码。"""
    entry = _reset_pending.get(req.email)
    if not entry:
        raise HTTPException(status_code=400, detail="未找到重置请求，请重新申请")
    if datetime.now(timezone.utc) > entry["expires_at"]:
        _reset_pending.pop(req.email, None)
        raise HTTPException(status_code=400, detail="重置码已过期，请重新申请")
    if entry["code"] != req.code:
        raise HTTPException(status_code=400, detail="重置码错误")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")

    user = _get_user_by_email(req.email)
    if not user:
        raise HTTPException(status_code=400, detail="用户不存在")

    users = _load_users()
    users[user["id"]]["hashed_password"] = _hash_password(req.new_password)
    _save_users(users)
    _reset_pending.pop(req.email, None)
    return {"message": "密码已重置，请用新密码登录"}


# ── 用户个人 Provider 配置 ────────────────────────────────────────────────────

def _mask_key(key: str) -> str:
    return f"****{key[-4:]}" if len(key) > 4 else ("****" if key else "")


def _migrate_flat_provider(prov: dict) -> dict:
    """将旧的扁平 provider 结构迁移为嵌套结构（兼容旧数据）。"""
    if "openai" in prov or "anthropic" in prov or "ollama" in prov:
        return prov  # 已是新格式
    name = prov.get("name", "openai")
    nested = {"active": name}
    if any(k in prov for k in ("api_key", "base_url", "model", "deep_model")):
        nested[name] = {k: prov[k] for k in ("api_key", "base_url", "model", "deep_model") if k in prov}
    return nested


@router.get("/user-config")
def get_user_config(current_user: dict = Depends(get_current_user)):
    """读取当前用户的个人 provider 配置（api_key 脱敏）。返回嵌套结构。"""
    cfg = load_user_config(current_user["id"])
    prov = _migrate_flat_provider(dict(cfg.get("provider", {})))

    # 对每个供应商配置脱敏 api_key
    result = {"active": prov.get("active", "openai")}
    for name in ("openai", "anthropic", "ollama"):
        p = dict(prov.get(name, {}))
        p["api_key"] = _mask_key(p.get("api_key", ""))
        result[name] = p
    return {"provider": result}


@router.post("/user-config")
def update_user_config(req: UserProviderConfigRequest, current_user: dict = Depends(get_current_user)):
    """更新当前用户指定供应商的 provider 配置，并设为 active。"""
    cfg = load_user_config(current_user["id"])
    prov = _migrate_flat_provider(cfg.get("provider", {}))

    entry = dict(prov.get(req.name, {}))
    if req.api_key:
        entry["api_key"] = req.api_key.strip()
    if req.base_url is not None:
        entry["base_url"] = req.base_url
    if req.model is not None:
        entry["model"] = req.model
    if req.deep_model is not None:
        entry["deep_model"] = req.deep_model

    prov[req.name] = entry
    prov["active"] = req.name
    cfg["provider"] = prov
    save_user_config(current_user["id"], cfg)
    return {"message": "用户配置已更新"}
