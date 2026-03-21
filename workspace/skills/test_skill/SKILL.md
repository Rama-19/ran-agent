---
name: test_skill
description: 这是一个测试技能，用于验证 Python 加载流程
metadata: '{"openclaw": {"always": true}}'
---

# Test Skill

当用户要求测试 skill 或验证本地 skill 执行链路时：

1. 运行以下命令：
   `python {baseDir}/test_skill.py --message "hello"`
2. 返回脚本 stdout。
3. 如果命令失败，返回 stderr 并简要解释失败原因。
4. 不要编造执行结果，必须基于命令输出。

