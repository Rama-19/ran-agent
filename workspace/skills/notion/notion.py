#!/usr/bin/env python3
"""
notion.py — 通过 Notion API 管理页面、数据库和内容块

支持操作：
  create-page   在指定父页面或数据库下创建新页面
  append-block  向已有页面追加内容块
  search        在工作区搜索页面/数据库
  get-page      获取页面详情
  list-db       列出数据库中的条目
  create-db-row 在数据库中添加新行

环境变量：
  NOTION_TOKEN      Notion Integration Token（必填）
  NOTION_DB_ID      默认数据库 ID（可选，list-db / create-db-row 时使用）
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def get_token():
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        print("[错误] 未设置环境变量 NOTION_TOKEN", file=sys.stderr)
        print("  请在 .env 或系统环境中设置：export NOTION_TOKEN=secret_xxx", file=sys.stderr)
        sys.exit(1)
    return token


def notion_request(method: str, path: str, body: dict | None = None) -> dict:
    token = get_token()
    url = f"{NOTION_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"[错误] Notion API {e.code}: {err_body}", file=sys.stderr)
        sys.exit(1)


def make_rich_text(text: str) -> list:
    return [{"type": "text", "text": {"content": text}}]


def make_paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": make_rich_text(text)},
    }


def make_heading(text: str, level: int = 1) -> dict:
    h = f"heading_{level}"
    return {
        "object": "block",
        "type": h,
        h: {"rich_text": make_rich_text(text)},
    }


def make_bulleted_item(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": make_rich_text(text)},
    }


def make_todo(text: str, checked: bool = False) -> dict:
    return {
        "object": "block",
        "type": "to_do",
        "to_do": {"rich_text": make_rich_text(text), "checked": checked},
    }


# ── 操作函数 ────────────────────────────────────────────────────────────────

def cmd_create_page(args):
    """在父页面或数据库下创建新页面"""
    parent_id = args.parent_id
    title = args.title
    content = args.content or ""
    parent_type = args.parent_type  # "page" or "database"

    if parent_type == "database":
        parent = {"database_id": parent_id}
        properties = {
            "Name": {"title": make_rich_text(title)}
        }
    else:
        parent = {"page_id": parent_id}
        properties = {
            "title": {"title": make_rich_text(title)}
        }

    blocks = []
    if content:
        for line in content.split("\\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("# "):
                blocks.append(make_heading(line[2:], 1))
            elif line.startswith("## "):
                blocks.append(make_heading(line[3:], 2))
            elif line.startswith("### "):
                blocks.append(make_heading(line[4:], 3))
            elif line.startswith("- "):
                blocks.append(make_bulleted_item(line[2:]))
            elif line.startswith("[ ] "):
                blocks.append(make_todo(line[4:], checked=False))
            elif line.startswith("[x] "):
                blocks.append(make_todo(line[4:], checked=True))
            else:
                blocks.append(make_paragraph(line))

    body = {"parent": parent, "properties": properties}
    if blocks:
        body["children"] = blocks

    result = notion_request("POST", "/pages", body)
    page_id = result.get("id", "")
    page_url = result.get("url", "")
    print(f"[成功] 页面已创建")
    print(f"  ID : {page_id}")
    print(f"  URL: {page_url}")


def cmd_append_block(args):
    """向已有页面追加内容块"""
    page_id = args.page_id
    content = args.content or ""
    block_type = args.block_type or "paragraph"

    blocks = []
    for line in content.split("\\n"):
        line = line.strip()
        if not line:
            continue
        if block_type == "heading1":
            blocks.append(make_heading(line, 1))
        elif block_type == "heading2":
            blocks.append(make_heading(line, 2))
        elif block_type == "bullet":
            blocks.append(make_bulleted_item(line))
        elif block_type == "todo":
            blocks.append(make_todo(line))
        else:
            blocks.append(make_paragraph(line))

    if not blocks:
        print("[警告] 没有内容可追加", file=sys.stderr)
        return

    result = notion_request("PATCH", f"/blocks/{page_id}/children", {"children": blocks})
    count = len(result.get("results", []))
    print(f"[成功] 已追加 {count} 个内容块到页面 {page_id}")


def cmd_search(args):
    """搜索工作区中的页面和数据库"""
    query = args.query
    filter_type = args.filter  # "page" | "database" | None

    body: dict = {"query": query, "page_size": args.limit or 10}
    if filter_type:
        body["filter"] = {"value": filter_type, "property": "object"}

    result = notion_request("POST", "/search", body)
    items = result.get("results", [])

    if not items:
        print(f"[结果] 未找到与 '{query}' 相关的内容")
        return

    print(f"[结果] 找到 {len(items)} 条记录：\n")
    for item in items:
        obj_type = item.get("object", "")
        item_id = item.get("id", "")
        url = item.get("url", "")
        # 获取标题
        if obj_type == "page":
            props = item.get("properties", {})
            title_prop = props.get("title") or props.get("Name") or {}
            title_list = title_prop.get("title", [])
            title = "".join(t.get("plain_text", "") for t in title_list) or "(无标题)"
        else:
            title_list = item.get("title", [])
            title = "".join(t.get("plain_text", "") for t in title_list) or "(无标题)"

        print(f"  [{obj_type}] {title}")
        print(f"    ID : {item_id}")
        print(f"    URL: {url}\n")


def cmd_get_page(args):
    """获取页面详情"""
    page_id = args.page_id
    result = notion_request("GET", f"/pages/{page_id}")

    props = result.get("properties", {})
    url = result.get("url", "")
    created = result.get("created_time", "")
    edited = result.get("last_edited_time", "")

    print(f"[页面详情]")
    print(f"  ID          : {page_id}")
    print(f"  URL         : {url}")
    print(f"  创建时间    : {created}")
    print(f"  最后编辑    : {edited}")
    print(f"  属性：")
    for key, val in props.items():
        val_type = val.get("type", "")
        if val_type == "title":
            text = "".join(t.get("plain_text", "") for t in val.get("title", []))
        elif val_type == "rich_text":
            text = "".join(t.get("plain_text", "") for t in val.get("rich_text", []))
        elif val_type == "select":
            sel = val.get("select") or {}
            text = sel.get("name", "")
        elif val_type == "multi_select":
            text = ", ".join(s.get("name", "") for s in val.get("multi_select", []))
        elif val_type == "checkbox":
            text = str(val.get("checkbox", False))
        elif val_type == "date":
            d = val.get("date") or {}
            text = d.get("start", "")
        elif val_type == "number":
            text = str(val.get("number", ""))
        else:
            text = f"({val_type})"
        print(f"    {key}: {text}")


def cmd_list_db(args):
    """列出数据库中的条目"""
    db_id = args.db_id or os.environ.get("NOTION_DB_ID", "")
    if not db_id:
        print("[错误] 请通过 --db-id 或环境变量 NOTION_DB_ID 指定数据库 ID", file=sys.stderr)
        sys.exit(1)

    body: dict = {"page_size": args.limit or 20}
    if args.filter_prop and args.filter_value:
        body["filter"] = {
            "property": args.filter_prop,
            "rich_text": {"contains": args.filter_value},
        }

    result = notion_request("POST", f"/databases/{db_id}/query", body)
    items = result.get("results", [])

    if not items:
        print("[结果] 数据库为空或无匹配条目")
        return

    print(f"[数据库] 共 {len(items)} 条记录：\n")
    for item in items:
        item_id = item.get("id", "")
        url = item.get("url", "")
        props = item.get("properties", {})
        # 尝试获取 Name/标题列
        title = ""
        for key in ["Name", "名称", "标题", "title", "Title"]:
            if key in props:
                t = props[key]
                title = "".join(x.get("plain_text", "") for x in t.get("title", []))
                break
        print(f"  {title or '(无标题)'}")
        print(f"    ID : {item_id}")
        print(f"    URL: {url}\n")


def cmd_create_db_row(args):
    """在数据库中添加一行"""
    db_id = args.db_id or os.environ.get("NOTION_DB_ID", "")
    if not db_id:
        print("[错误] 请通过 --db-id 或环境变量 NOTION_DB_ID 指定数据库 ID", file=sys.stderr)
        sys.exit(1)

    name = args.name
    properties: dict = {
        "Name": {"title": make_rich_text(name)}
    }

    # 解析额外属性 key=value
    for prop in args.props or []:
        if "=" not in prop:
            continue
        k, v = prop.split("=", 1)
        properties[k.strip()] = {"rich_text": make_rich_text(v.strip())}

    body = {
        "parent": {"database_id": db_id},
        "properties": properties,
    }

    result = notion_request("POST", "/pages", body)
    row_id = result.get("id", "")
    row_url = result.get("url", "")
    print(f"[成功] 数据库新行已创建")
    print(f"  ID : {row_id}")
    print(f"  URL: {row_url}")


# ── CLI 入口 ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="notion.py — Notion API 操作工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # create-page
    p1 = sub.add_parser("create-page", help="创建新页面")
    p1.add_argument("--parent-id", required=True, help="父页面或数据库 ID")
    p1.add_argument("--parent-type", choices=["page", "database"], default="page", help="父对象类型")
    p1.add_argument("--title", required=True, help="页面标题")
    p1.add_argument("--content", default="", help="页面内容（支持 Markdown 子集：#/##/###/-/[ ]/[x]）")

    # append-block
    p2 = sub.add_parser("append-block", help="向页面追加内容块")
    p2.add_argument("--page-id", required=True, help="目标页面 ID")
    p2.add_argument("--content", required=True, help="要追加的文本内容")
    p2.add_argument("--block-type", choices=["paragraph", "heading1", "heading2", "bullet", "todo"],
                    default="paragraph", help="内容块类型")

    # search
    p3 = sub.add_parser("search", help="搜索页面或数据库")
    p3.add_argument("--query", required=True, help="搜索关键词")
    p3.add_argument("--filter", choices=["page", "database"], help="过滤结果类型")
    p3.add_argument("--limit", type=int, default=10, help="最多返回条数")

    # get-page
    p4 = sub.add_parser("get-page", help="获取页面详情")
    p4.add_argument("--page-id", required=True, help="页面 ID")

    # list-db
    p5 = sub.add_parser("list-db", help="列出数据库条目")
    p5.add_argument("--db-id", default="", help="数据库 ID（可用环境变量 NOTION_DB_ID）")
    p5.add_argument("--limit", type=int, default=20, help="最多返回条数")
    p5.add_argument("--filter-prop", default="", help="按属性名过滤")
    p5.add_argument("--filter-value", default="", help="过滤属性值（包含匹配）")

    # create-db-row
    p6 = sub.add_parser("create-db-row", help="在数据库中添加新行")
    p6.add_argument("--db-id", default="", help="数据库 ID（可用环境变量 NOTION_DB_ID）")
    p6.add_argument("--name", required=True, help="行标题（Name 列）")
    p6.add_argument("--props", nargs="*", help="额外属性，格式：属性名=值")

    args = parser.parse_args()

    dispatch = {
        "create-page": cmd_create_page,
        "append-block": cmd_append_block,
        "search": cmd_search,
        "get-page": cmd_get_page,
        "list-db": cmd_list_db,
        "create-db-row": cmd_create_db_row,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
