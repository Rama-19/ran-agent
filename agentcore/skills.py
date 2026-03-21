import os
import json
import yaml
import platform
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from .config import config, WORKSPACE_ENV


def get_skill_dirs() -> List[Path]:
    dirs = []

    for extra in config.get("skills", {}).get("load", {}).get("extraDirs", []):
        p = Path(extra)
        if p.exists():
            dirs.append(p)

    bundled = Path(__file__).parent / "bundled_skills"
    if bundled.exists():
        dirs.append(bundled)

    managed = Path.home() / ".openclaw" / "skills"
    if managed.exists():
        dirs.append(managed)

    workspace_skills = Path(WORKSPACE_ENV) / "skills"
    if workspace_skills.exists():
        dirs.append(workspace_skills)

    return dirs


def parse_skill_md(skill_dir: Path) -> Optional[Dict]:
    md = skill_dir / "SKILL.md"
    if not md.exists():
        return None

    content = md.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return None

    try:
        _, fm_text, body = content.split("---", 2)
        fm = yaml.safe_load(fm_text.strip()) or {}
        metadata = fm.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        return {
            "name": fm.get("name"),
            "description": fm.get("description", ""),
            "metadata": metadata,
            "location": str(skill_dir.resolve()),
            "skill_md_path": str(md.resolve()),
            "content": content,
            "body": body.strip(),
        }
    except Exception as e:
        print(f"解析 SKILL.md 失败: {md} -> {e}")
        return None


def is_eligible(skill: Dict) -> bool:
    meta = skill.get("metadata", {}).get("openclaw", {})
    entry = config.get("skills", {}).get("entries", {}).get(skill["name"], {})

    if entry.get("enabled", True) is False:
        return False

    if meta.get("always", False):
        return True

    required_os = meta.get("os")
    if required_os:
        current = platform.system().lower()
        os_map = {"darwin": "darwin", "linux": "linux", "windows": "win32"}
        if os_map.get(current) not in required_os:
            return False

    requires = meta.get("requires", {})

    for b in requires.get("bins", []):
        if shutil.which(b) is None:
            return False

    any_bins = requires.get("anyBins", [])
    if any_bins and not any(shutil.which(b) for b in any_bins):
        return False

    for env_name in requires.get("env", []):
        if env_name not in os.environ and env_name not in entry.get("env", {}):
            return False

    for path in requires.get("config", []):
        value = config
        for k in path.split("."):
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(k)
        if not value:
            return False

    return True


def load_eligible_skills() -> List[Dict]:
    seen = {}
    for root in get_skill_dirs():
        for child in root.iterdir():
            if not child.is_dir():
                continue
            skill = parse_skill_md(child)
            if skill and skill.get("name"):
                seen[skill["name"]] = skill
    return [s for s in seen.values() if is_eligible(s)]


def find_skill(skill_name: str) -> Optional[Dict]:
    eligible = load_eligible_skills()
    return next((s for s in eligible if s["name"] == skill_name), None)


def format_skills_for_prompt(skills: List[Dict]) -> str:
    if not skills:
        return ""
    lines = ["<available_skills>"]
    for s in skills:
        lines.append("  <skill>")
        lines.append(f"    <name>{s['name']}</name>")
        lines.append(f"    <description>{s['description']}</description>")
        lines.append(f"    <location>{s['location']}</location>")
        lines.append("  </skill>")
    lines.append("</available_skills>")
    return "\n".join(lines)
