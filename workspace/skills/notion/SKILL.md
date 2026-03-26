---
name: notion
description: 这是一个 Notion 技能，用于通过 Notion API 管理页面、数据库和内容块。当用户要求创建 Notion 页面、向 Notion 写笔记、在 Notion 数据库中添加记录、搜索 Notion 内容、或查看 Notion 页面详情时使用此技能。
metadata: '{"openclaw": {"always": true}}'
---

# Notion

通过 Notion API 与 Notion 工作区交互，支持页面创建、内容追加、数据库管理和全局搜索。

## 前置条件

需要设置环境变量：
- `NOTION_TOKEN`：Notion Integration Token（必填）
  获取方式：https://www.notion.so/my-integrations → 创建 Integration → 复制 Secret
- `NOTION_DB_ID`：默认数据库 ID（可选，`list-db` / `create-db-row` 时使用）

**重要**：使用前需在 Notion 页面/数据库的 "Connections" 中添加你的 Integration。

---

## 支持的操作

### 1. 创建页面 `create-page`

在父页面或数据库下新建一个 Notion 页面。

```bash
python notion.py create-page \
  --parent-id <父页面或数据库ID> \
  --parent-type page \   # 或 database
  --title "页面标题" \
  --content "页面内容（支持 Markdown 子集）"
```

内容支持以下 Markdown 格式（每行一个块）：
- `# 标题一` → Heading 1
- `## 标题二` → Heading 2
- `### 标题三` → Heading 3
- `- 列表项` → Bulleted list
- `[ ] 待办` → Todo（未完成）
- `[x] 待办` → Todo（已完成）
- 普通文本 → Paragraph

示例：
```bash
python notion.py create-page \
  --parent-id abc123def456 \
  --title "会议记录 2026-03-26" \
  --content "# 议题\n- 功能讨论\n- 时间规划\n[ ] 确认需求\n[x] 发送邀请"
```

---

### 2. 追加内容块 `append-block`

向已有页面末尾追加内容。

```bash
python notion.py append-block \
  --page-id <页面ID> \
  --content "要追加的内容" \
  --block-type paragraph   # paragraph / heading1 / heading2 / bullet / todo
```

示例：
```bash
python notion.py append-block \
  --page-id abc123 \
  --content "新的行动项已记录" \
  --block-type bullet
```

---

### 3. 搜索 `search`

在整个工作区搜索页面或数据库。

```bash
python notion.py search \
  --query "关键词" \
  --filter page \   # 可选：page / database
  --limit 10
```

示例：
```bash
python notion.py search --query "产品路线图" --filter page
```

---

### 4. 获取页面详情 `get-page`

查看指定页面的属性和元数据。

```bash
python notion.py get-page --page-id <页面ID>
```

---

### 5. 列出数据库条目 `list-db`

查询数据库中的所有记录，支持按属性过滤。

```bash
python notion.py list-db \
  --db-id <数据库ID> \   # 可省略，使用 NOTION_DB_ID 环境变量
  --limit 20 \
  --filter-prop "状态" \
  --filter-value "进行中"
```

---

### 6. 数据库添加行 `create-db-row`

在数据库中创建新记录。

```bash
python notion.py create-db-row \
  --db-id <数据库ID> \
  --name "记录名称" \
  --props "状态=进行中" "负责人=张三"
```

---

## 如何获取页面/数据库 ID

方法一：从 URL 中提取
打开 Notion 页面，URL 格式为：
```
https://www.notion.so/workspace/页面标题-<32位ID>
```
取最后 32 位字符，格式化为 `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`。

方法二：使用 `search` 命令搜索后，输出中会显示 ID。

---

## 使用流程示例

**场景：记录今天的会议笔记到 Notion**

1. 先搜索找到目标页面 ID：
```bash
python notion.py search --query "会议记录"
```

2. 在找到的父页面下创建今日笔记：
```bash
python notion.py create-page \
  --parent-id <父页面ID> \
  --title "会议记录 2026-03-26" \
  --content "# 参会人\n- 张三\n- 李四\n## 决议\n[ ] 下周完成原型"
```

**场景：向 Notion 数据库添加任务**

```bash
python notion.py create-db-row \
  --name "优化登录流程" \
  --props "状态=待开始" "优先级=高" "负责人=王五"
```
