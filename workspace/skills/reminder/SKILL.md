---
name: reminder
description: 这是一个提醒技能，用于设置计时器在指定时间打印内容
metadata: '{"openclaw": {"always": true}}'
---

# Reminder
当用户要求设置提醒时：
TIME 是一个时间参数，格式可以是秒数（例如 `10s`）、分钟数（例如 `5m`）或小时数（例如 `2h`）。MESSAGE 是要在计时器结束时打印的内容。
MESSAGE 是一个字符串参数，表示计时器结束时要打印的内容。
运行命令
`python reminder.py --time TIME --message MESSAGE`

运行示例：
比如要设置一个 10 秒的计时器，结束时打印 "时间到！"，可以运行：
`python reminder.py --time 10 --message "时间到！"`