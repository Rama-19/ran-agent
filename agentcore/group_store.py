"""
群组持久化存储

数据路径：data/users/{user_id}/groups.json
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import DATA_DIR
from .multi_agent import AgentDef, AgentGroup, BUILTIN_ROLES

logger = logging.getLogger(__name__)


def _groups_path(user_id: str) -> Path:
    p = DATA_DIR / "users" / user_id / "groups.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_groups(user_id: str) -> List[AgentGroup]:
    p = _groups_path(user_id)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return [AgentGroup.from_dict(g) for g in data]
    except Exception as e:
        logger.error("load_groups error: %s", e)
        return []


def save_groups(user_id: str, groups: List[AgentGroup]) -> None:
    p = _groups_path(user_id)
    p.write_text(
        json.dumps([g.to_dict() for g in groups], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_group(user_id: str, group_id: str) -> Optional[AgentGroup]:
    for g in load_groups(user_id):
        if g.id == group_id:
            return g
    return None


def list_groups(user_id: str) -> List[dict]:
    groups = load_groups(user_id)
    return [
        {
            "id": g.id,
            "name": g.name,
            "description": g.description,
            "agent_count": len(g.agents),
            "agents": [
                {"id": a.id, "role": a.role, "name": a.name, "enabled": a.enabled}
                for a in g.agents
            ],
            "created_at": g.created_at,
            "updated_at": g.updated_at,
        }
        for g in groups
    ]


def create_default_group(user_id: str) -> AgentGroup:
    """创建包含所有内置角色的默认群组"""
    now = datetime.now().isoformat()
    agents = []
    for role in ["coordinator", "researcher", "executor", "reviewer", "summarizer"]:
        agents.append(AgentDef.from_builtin(role, agent_id=f"{role}_{uuid.uuid4().hex[:6]}"))

    group = AgentGroup(
        id=f"group_{uuid.uuid4().hex[:8]}",
        name="默认协作群组",
        description="包含协调者、研究员、执行者、审核者和总结者的标准多 agent 群组",
        agents=agents,
        created_at=now,
        updated_at=now,
    )
    groups = load_groups(user_id)
    groups.append(group)
    save_groups(user_id, groups)
    return group


def create_group(
    user_id: str,
    name: str,
    description: str = "",
    roles: Optional[List[str]] = None,
) -> AgentGroup:
    """
    创建新群组。
    roles: 要包含的角色列表，默认包含所有内置角色。
    """
    now = datetime.now().isoformat()
    if roles is None:
        roles = ["coordinator", "researcher", "executor", "reviewer", "summarizer"]

    # 确保 coordinator 始终存在
    if "coordinator" not in roles:
        roles = ["coordinator"] + list(roles)

    agents = [
        AgentDef.from_builtin(role, agent_id=f"{role}_{uuid.uuid4().hex[:6]}")
        for role in roles
    ]

    group = AgentGroup(
        id=f"group_{uuid.uuid4().hex[:8]}",
        name=name,
        description=description,
        agents=agents,
        created_at=now,
        updated_at=now,
    )

    groups = load_groups(user_id)
    groups.append(group)
    save_groups(user_id, groups)
    return group


def update_group(user_id: str, group_id: str, name: str = None, description: str = None) -> Optional[AgentGroup]:
    groups = load_groups(user_id)
    for g in groups:
        if g.id == group_id:
            if name is not None:
                g.name = name
            if description is not None:
                g.description = description
            g.updated_at = datetime.now().isoformat()
            save_groups(user_id, groups)
            return g
    return None


def delete_group(user_id: str, group_id: str) -> bool:
    groups = load_groups(user_id)
    new_groups = [g for g in groups if g.id != group_id]
    if len(new_groups) == len(groups):
        return False
    save_groups(user_id, new_groups)
    return True


def add_agent(
    user_id: str,
    group_id: str,
    role: str,
    name: str = "",
    description: str = "",
    system_prompt: str = "",
) -> Optional[AgentDef]:
    groups = load_groups(user_id)
    for g in groups:
        if g.id == group_id:
            agent_id = f"{role}_{uuid.uuid4().hex[:6]}"
            template = BUILTIN_ROLES.get(role, BUILTIN_ROLES["custom"])
            agent = AgentDef(
                id=agent_id,
                role=role,
                name=name or template["name"],
                description=description or template["description"],
                system_prompt=system_prompt or template["system_prompt"],
                enabled=True,
            )
            g.agents.append(agent)
            g.updated_at = datetime.now().isoformat()
            save_groups(user_id, groups)
            return agent
    return None


def update_agent(
    user_id: str,
    group_id: str,
    agent_id: str,
    name: str = None,
    description: str = None,
    system_prompt: str = None,
    enabled: bool = None,
) -> Optional[AgentDef]:
    groups = load_groups(user_id)
    for g in groups:
        if g.id == group_id:
            for a in g.agents:
                if a.id == agent_id:
                    if name is not None:
                        a.name = name
                    if description is not None:
                        a.description = description
                    if system_prompt is not None:
                        a.system_prompt = system_prompt
                    if enabled is not None:
                        a.enabled = enabled
                    g.updated_at = datetime.now().isoformat()
                    save_groups(user_id, groups)
                    return a
    return None


def remove_agent(user_id: str, group_id: str, agent_id: str) -> bool:
    groups = load_groups(user_id)
    for g in groups:
        if g.id == group_id:
            orig_len = len(g.agents)
            # 不允许删除协调者
            g.agents = [a for a in g.agents if not (a.id == agent_id and a.role != "coordinator")]
            if len(g.agents) < orig_len:
                g.updated_at = datetime.now().isoformat()
                save_groups(user_id, groups)
                return True
    return False
