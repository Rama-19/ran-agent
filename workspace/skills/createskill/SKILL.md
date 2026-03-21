---
name: createskill
description: 创建一个新的 skill，包含 SKILL.md 和可选的 Python 脚本
metadata: '{"openclaw": {"always": true}}'
---

# CreateSkill

当用户要求创建一个新技能（skill）时，执行以下步骤：

## 参数说明

- SKILL_NAME：技能名称（英文小写，无空格）
- DESCRIPTION：技能的中文描述
- HAS_SCRIPT：是否需要 Python 脚本（yes/no）

## 执行步骤

1. 运行 Python 脚本创建 skill 目录和文件：

```
python create_skill.py --name SKILL_NAME --description "DESCRIPTION" [--script]
```

2. 脚本会：
   - 在 `workspace/skills/SKILL_NAME/` 下创建目录
   - 生成规范的 `SKILL.md`（含 frontmatter）
   - 如指定 `--script`，同时生成 `SKILL_NAME.py` 骨架脚本

3. 脚本创建完成后，根据用户的具体需求**编辑** `SKILL.md` 补充详细的使用说明和示例。

## 示例

创建一个带脚本的翻译技能：
```
python create_skill.py --name translate --description "将文本翻译成指定语言" --script
```

创建一个不带脚本的提示词技能：
```
python create_skill.py --name codereview --description "对代码进行 review 并给出改进建议"
```

## SKILL.md 规范格式

```markdown
---
name: SKILL_NAME
description: 技能描述
metadata: '{"openclaw": {"always": true}}'
---

# SKILL_NAME（标题）

## 功能说明
...

## 参数说明
...

## 使用示例
...
```
