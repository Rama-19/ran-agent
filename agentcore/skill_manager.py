"""Skill 管理 —— 创建、更新、删除、配置、生成 README。"""
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import config, CONFIG_PATH, WORKSPACE_ENV
from .skills import get_skill_dirs, parse_skill_md, is_eligible

# 用户可写的 skill 目录（优先 workspace，其次 ~/.openclaw/skills）
WORKSPACE_SKILLS = Path(WORKSPACE_ENV) / "skills"
MANAGED_DIR = Path.home() / ".openclaw" / "skills"


def _default_create_dir() -> Path:
    """返回新建 skill 的默认目录（优先 workspace/skills）。"""
    return WORKSPACE_SKILLS


def get_all_skills() -> List[Dict]:
    """返回所有 skill（含已禁用 / 不满足条件的）。"""
    seen: Dict[str, Dict] = {}
    for root in get_skill_dirs():
        if not root.exists():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            skill = parse_skill_md(child)
            if skill and skill.get("name"):
                seen[skill["name"]] = skill

    entries = config.get("skills", {}).get("entries", {})
    result = []
    for name, skill in seen.items():
        entry = entries.get(name, {})
        enabled = entry.get("enabled", True)
        eligible = is_eligible(skill)
        loc = Path(skill["location"])
        readme_path = loc / "README.md"
        readme_content = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

        # 判断是否可被删除（只有在 workspace 或 managed 目录中的才允许删除）
        deletable = (
            str(WORKSPACE_SKILLS.resolve()) in str(loc.resolve())
            or str(MANAGED_DIR.resolve()) in str(loc.resolve())
        )

        result.append({
            "name": skill["name"],
            "description": skill["description"],
            "location": str(loc),
            "content": skill["content"],
            "body": skill.get("body", ""),
            "metadata": skill.get("metadata", {}),
            "enabled": enabled,
            "eligible": eligible,
            "has_readme": readme_path.exists(),
            "readme": readme_content,
            "deletable": deletable,
        })
    return result


def get_skill_detail(name: str) -> Optional[Dict]:
    for s in get_all_skills():
        if s["name"] == name:
            return s
    return None


def set_skill_enabled(name: str, enabled: bool) -> None:
    """在 openclaw.json 中启用或禁用一个 skill。"""
    skills_cfg = config.setdefault("skills", {})
    entries = skills_cfg.setdefault("entries", {})
    entries.setdefault(name, {})["enabled"] = enabled
    _save_config()


def create_skill(name: str, content: str) -> Dict:
    """在 workspace/skills 目录下创建新 skill。"""
    target_dir = _default_create_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    skill_dir = target_dir / name
    if skill_dir.exists():
        raise ValueError(f"Skill '{name}' 已存在于 {target_dir}")
    skill_dir.mkdir()
    md_path = skill_dir / "SKILL.md"
    md_path.write_text(content, encoding="utf-8")
    skill = parse_skill_md(skill_dir)
    if not skill:
        shutil.rmtree(skill_dir)
        raise ValueError("SKILL.md 解析失败，请检查 YAML frontmatter 格式")
    return skill


def update_skill_content(name: str, content: str) -> None:
    """更新指定 skill 的 SKILL.md 内容。"""
    for root in get_skill_dirs():
        skill_dir = root / name
        md_path = skill_dir / "SKILL.md"
        if md_path.exists():
            md_path.write_text(content, encoding="utf-8")
            return
    raise ValueError(f"Skill '{name}' 未找到")


def delete_skill(name: str) -> None:
    """删除 skill（仅限 workspace/skills 或 managed 目录）。"""
    for base in (WORKSPACE_SKILLS, MANAGED_DIR):
        skill_dir = base / name
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
            return
    raise ValueError(f"Skill '{name}' 不在可删除目录中")


def save_readme(name: str, content: str) -> None:
    """将 README 内容写入 skill 目录。"""
    detail = get_skill_detail(name)
    if not detail:
        raise ValueError(f"Skill '{name}' 未找到")
    readme_path = Path(detail["location"]) / "README.md"
    readme_path.write_text(content, encoding="utf-8")


def generate_skill_md(name: str, description: str, bins: list, env_vars: list, always: bool) -> str:
    """调用 LLM 根据用户输入的基本信息生成完整的 SKILL.md 内容。"""
    from .llm import run_agent
    from .models import select_model

    bins_str = ', '.join(bins) if bins else '无'
    env_str = ', '.join(env_vars) if env_vars else '无'
    always_str = '是' if always else '否'

    system_prompt = (
        "你是一个 AI Agent 技能系统专家。请根据用户提供的信息，生成一份完整、专业的 SKILL.md 文件。\n\n"
        "SKILL.md 格式要求：\n"
        "1. 必须包含 YAML frontmatter（---包裹），字段：name, description, metadata.openclaw.always，可选 requires.bins / requires.env\n"
        "2. frontmatter 之后是 Markdown 正文，包含：概述、详细使用说明、执行步骤、参数说明、示例、注意事项\n"
        "3. 使用说明要详细具体，让 AI Agent 能根据此文档独立完成任务\n"
        "4. 直接输出 SKILL.md 全文，不要包裹在代码块中，不要额外解释"
    )

    user_input = (
        f"请生成以下 skill 的 SKILL.md：\n\n"
        f"- name: {name}\n"
        f"- description: {description}\n"
        f"- 依赖命令（bins）: {bins_str}\n"
        f"- 依赖环境变量（env）: {env_str}\n"
        f"- always 启用: {always_str}\n\n"
        "请生成详细的 SKILL.md，包含完整的使用说明和示例。"
    )

    return run_agent(
        system_prompt=system_prompt,
        user_input=user_input,
        tools=[],
        dispatch=lambda n, a: "",
        model=select_model(),
        reasoning_effort=None,
        max_rounds=1,
    )


def generate_readme(skill_name: str) -> str:
    """调用 LLM 为 skill 生成 README.md，并写入磁盘。"""
    from .skills import find_skill
    from .llm import run_agent
    from .models import select_model

    skill = find_skill(skill_name)
    if not skill:
        raise ValueError(f"Skill '{skill_name}' 未找到")

    system_prompt = (
        "你是一个技术文档写手。根据提供的 SKILL.md 内容，生成一份清晰、实用的 README.md 文档。\n\n"
        "要求：\n"
        "1. 使用 Markdown 格式\n"
        "2. 包含：简介、功能特性、使用前提、使用方法、示例\n"
        "3. 语言与 SKILL.md 保持一致（中文或英文）\n"
        "4. 直接输出 README.md 全文，不要额外解释或包裹代码块"
    )

    readme_content = run_agent(
        system_prompt=system_prompt,
        user_input=f"请为以下 skill 生成 README.md：\n\n{skill['content']}",
        tools=[],
        dispatch=lambda n, a: "",
        model=select_model(),
        reasoning_effort=None,
        max_rounds=1,
    )

    readme_path = Path(skill["location"]) / "README.md"
    readme_path.write_text(readme_content, encoding="utf-8")
    return readme_content


# ── 内部工具 ──────────────────────────────────────────────────────────────────


def _save_config() -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
