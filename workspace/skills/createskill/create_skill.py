#!/usr/bin/env python3
"""
create_skill.py — 快速创建 skill 目录结构

用法:
  python create_skill.py --name <skill_name> --description "<描述>" [--script]

参数:
  --name        技能名称（英文小写，无空格）
  --description 技能描述（中文或英文均可）
  --script      同时生成同名 Python 骨架脚本
  --dir         skill 根目录（默认：本脚本所在目录的上级，即 workspace/skills）
"""

import argparse
import sys
from pathlib import Path

SKILL_MD_TEMPLATE = """\
---
name: {name}
description: {description}
metadata: '{{"openclaw": {{"always": true}}}}'
---

# {title}

## 功能说明

{description}

## 参数说明

| 参数 | 说明 | 必填 |
|------|------|------|
| PARAM1 | 参数1说明 | 是 |

## 使用示例

```
# 示例命令
python {name}.py --param1 "值"
```

## 注意事项

- 补充注意事项
"""

PYTHON_TEMPLATE = """\
#!/usr/bin/env python3
\"\"\"
{name}.py — {description}
\"\"\"

import argparse


def main():
    parser = argparse.ArgumentParser(description="{description}")
    parser.add_argument("--param1", required=True, help="参数1")
    args = parser.parse_args()

    # TODO: 实现技能逻辑
    print(f"[{name}] param1={{args.param1}}")


if __name__ == "__main__":
    main()
"""


def create_skill(name: str, description: str, skills_dir: Path, with_script: bool):
    skill_dir = skills_dir / name
    if skill_dir.exists():
        print(f"[警告] 目录已存在: {skill_dir}，将覆盖 SKILL.md", file=sys.stderr)
    skill_dir.mkdir(parents=True, exist_ok=True)

    # 写 SKILL.md
    skill_md = skill_dir / "SKILL.md"
    title = name.capitalize()
    skill_md.write_text(
        SKILL_MD_TEMPLATE.format(name=name, title=title, description=description),
        encoding="utf-8",
    )
    print(f"[OK] 已创建: {skill_md}")

    # 写 Python 骨架（可选）
    if with_script:
        py_file = skill_dir / f"{name}.py"
        py_file.write_text(
            PYTHON_TEMPLATE.format(name=name, description=description),
            encoding="utf-8",
        )
        print(f"[OK] 已创建: {py_file}")

    print(f"\n技能 '{name}' 创建完成 → {skill_dir}")
    print("下一步：编辑 SKILL.md，补充详细的使用说明和参数示例。")


def main():
    # 默认 skills 根目录 = 本脚本所在目录的上级（workspace/skills）
    default_skills_dir = Path(__file__).resolve().parent.parent

    parser = argparse.ArgumentParser(description="创建 skill 目录结构")
    parser.add_argument("--name", required=True, help="技能名称（英文小写）")
    parser.add_argument("--description", required=True, help="技能描述")
    parser.add_argument("--script", action="store_true", help="同时生成 Python 骨架脚本")
    parser.add_argument(
        "--dir",
        default=str(default_skills_dir),
        help=f"skill 根目录（默认：{default_skills_dir}）",
    )
    args = parser.parse_args()

    name = args.name.strip().lower().replace(" ", "_")
    if not name.isidentifier():
        print(f"[错误] 技能名称不合法: {name!r}，请使用英文字母、数字和下划线", file=sys.stderr)
        sys.exit(1)

    create_skill(
        name=name,
        description=args.description.strip(),
        skills_dir=Path(args.dir),
        with_script=args.script,
    )


if __name__ == "__main__":
    main()
