---
name: writenote
description: 这是一个写笔记、记笔记技能，将用户要求的内容写入笔记
metadata: '{"openclaw": {"always": true}}'
---

# WriteNote
当用户要求写笔记时：
CONTENT 是要写的笔记内容。（MARKDOWN格式）
LINE1 是要写的笔记内容的第一行。
LINE2 是要写的笔记内容的第二行。
。。。
LINEN 是要写的笔记内容的第N行。
TITLE 是要写的笔记标题。

运行命令：
`python write_note.py --title TITLE --content LINE1 LINE2 ... LINEN`

运行示例：
比如要写一个标题为 "学习笔记"，内容为 "这是我学习Python的笔记" 的笔记，命令如下：
`python write_note.py --title "学习笔记" --content "#这是我学习Python的笔记" "```python print("hello world")```"`



