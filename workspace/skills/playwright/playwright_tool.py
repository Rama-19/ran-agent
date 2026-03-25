#!/usr/bin/env python3
"""
playwright_tool.py — 基于 Playwright 的全功能网页自动化工具

支持动作：
  screenshot, pdf, click, dblclick, fill, type, clear, select,
  check, uncheck, hover, focus, press, scroll, drag,
  navigate, wait, extract, evaluate,
  cookie_get, cookie_set, cookie_clear,
  storage_get, storage_set,
  upload, intercept, iframe_extract,
  dialog_auto, form_fill, batch, scrape
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _out(data) -> None:
    """统一输出：dict/list → JSON，其余直接打印。"""
    if isinstance(data, (dict, list)):
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(data)


def _abs(path: str) -> str:
    return str(Path(path).expanduser().resolve())


# ── 核心执行器 ────────────────────────────────────────────────────────────────

async def _run(args) -> None:
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("ERROR: Playwright 未安装。请执行：\n  pip install playwright\n  playwright install")
        sys.exit(1)

    async with async_playwright() as pw:
        # ── 浏览器启动 ──
        bt = getattr(pw, args.browser)
        launch_opts: dict = {"headless": not args.no_headless}
        if args.proxy:
            launch_opts["proxy"] = {"server": args.proxy}
        if args.slow_mo:
            launch_opts["slow_mo"] = args.slow_mo

        browser = await bt.launch(**launch_opts)

        # ── 上下文配置 ──
        ctx_opts: dict = {}
        if args.viewport:
            w, h = (int(x) for x in args.viewport.lower().split("x"))
            ctx_opts["viewport"] = {"width": w, "height": h}
        if args.user_agent:
            ctx_opts["user_agent"] = args.user_agent
        if args.locale:
            ctx_opts["locale"] = args.locale
        if args.timezone:
            ctx_opts["timezone_id"] = args.timezone
        if args.http_credentials:
            u, p = args.http_credentials.split(":", 1)
            ctx_opts["http_credentials"] = {"username": u, "password": p}
        if args.storage_state and Path(args.storage_state).exists():
            ctx_opts["storage_state"] = args.storage_state
        if args.ignore_https_errors:
            ctx_opts["ignore_https_errors"] = True

        context = await browser.new_context(**ctx_opts)

        # ── Cookie 预置 ──
        if args.cookies:
            await context.add_cookies(json.loads(args.cookies))

        # ── Dialog 自动处理 ──
        if args.dialog_action in ("accept", "dismiss"):
            def _handle_dialog(dialog):
                asyncio.ensure_future(
                    dialog.accept(args.dialog_input or "") if args.dialog_action == "accept"
                    else dialog.dismiss()
                )
            context.on("dialog", _handle_dialog)

        # ── 网络拦截 ──
        blocked_patterns: list = json.loads(args.block_urls) if args.block_urls else []
        if blocked_patterns:
            async def _route_handler(route, request):
                for pat in blocked_patterns:
                    if pat in request.url:
                        await route.abort()
                        return
                await route.continue_()
            await context.route("**/*", _route_handler)

        page = await context.new_page()

        # ── 页面导航 ──
        if args.url:
            nav_opts = {"timeout": args.timeout}
            if args.wait_until:
                nav_opts["wait_until"] = args.wait_until
            await page.goto(args.url, **nav_opts)

        # ── 等待指定选择器/状态 ──
        if args.wait_for:
            if args.wait_for in ("load", "domcontentloaded", "networkidle"):
                await page.wait_for_load_state(args.wait_for, timeout=args.timeout)
            else:
                await page.wait_for_selector(args.wait_for, timeout=args.timeout)

        # ── 执行动作 ──
        action = args.action
        sel = args.selector
        timeout = args.timeout

        # ---------- 截图 ----------
        if action == "screenshot":
            output = _abs(args.output or "screenshot.png")
            shot_opts = {"path": output, "full_page": args.full_page}
            if sel:
                elem = await page.wait_for_selector(sel, timeout=timeout)
                await elem.screenshot(path=output)
            else:
                if args.clip:
                    x, y, w, h = (int(v) for v in args.clip.split(","))
                    shot_opts["clip"] = {"x": x, "y": y, "width": w, "height": h}
                await page.screenshot(**shot_opts)
            print(f"File written: {output}")

        # ---------- PDF ----------
        elif action == "pdf":
            output = _abs(args.output or "page.pdf")
            pdf_opts: dict = {"path": output}
            if args.pdf_format:
                pdf_opts["format"] = args.pdf_format
            if args.pdf_margin:
                t, r, b, l = args.pdf_margin.split(",")
                pdf_opts["margin"] = {"top": t, "right": r, "bottom": b, "left": l}
            pdf_opts["print_background"] = True
            await page.pdf(**pdf_opts)
            print(f"File written: {output}")

        # ---------- 点击 ----------
        elif action == "click":
            elem = await page.wait_for_selector(sel, timeout=timeout)
            click_opts: dict = {}
            if args.button:
                click_opts["button"] = args.button
            if args.click_count:
                click_opts["click_count"] = args.click_count
            if args.modifiers:
                click_opts["modifiers"] = args.modifiers.split(",")
            await elem.click(**click_opts)
            print(f"OK: clicked {sel}")

        # ---------- 双击 ----------
        elif action == "dblclick":
            elem = await page.wait_for_selector(sel, timeout=timeout)
            await elem.dblclick()
            print(f"OK: double-clicked {sel}")

        # ---------- 填写（快速）----------
        elif action == "fill":
            elem = await page.wait_for_selector(sel, timeout=timeout)
            await elem.fill(args.text or "")
            print(f"OK: filled {sel}")

        # ---------- 逐字输入 ----------
        elif action == "type":
            elem = await page.wait_for_selector(sel, timeout=timeout)
            await elem.type(args.text or "", delay=args.type_delay)
            print(f"OK: typed into {sel}")

        # ---------- 清空 ----------
        elif action == "clear":
            elem = await page.wait_for_selector(sel, timeout=timeout)
            await elem.fill("")
            print(f"OK: cleared {sel}")

        # ---------- 下拉选择 ----------
        elif action == "select":
            elem = await page.wait_for_selector(sel, timeout=timeout)
            values = args.values.split(",") if args.values else []
            if args.select_by == "label":
                selected = await elem.select_option(label=values)
            elif args.select_by == "index":
                selected = await elem.select_option(index=[int(v) for v in values])
            else:
                selected = await elem.select_option(value=values)
            print(f"OK: selected {selected}")

        # ---------- 勾选 ----------
        elif action == "check":
            elem = await page.wait_for_selector(sel, timeout=timeout)
            await elem.check()
            print(f"OK: checked {sel}")

        # ---------- 取消勾选 ----------
        elif action == "uncheck":
            elem = await page.wait_for_selector(sel, timeout=timeout)
            await elem.uncheck()
            print(f"OK: unchecked {sel}")

        # ---------- 悬停 ----------
        elif action == "hover":
            elem = await page.wait_for_selector(sel, timeout=timeout)
            await elem.hover()
            print(f"OK: hovered {sel}")

        # ---------- 聚焦 ----------
        elif action == "focus":
            elem = await page.wait_for_selector(sel, timeout=timeout)
            await elem.focus()
            print(f"OK: focused {sel}")

        # ---------- 键盘按键 ----------
        elif action == "press":
            if sel:
                elem = await page.wait_for_selector(sel, timeout=timeout)
                await elem.press(args.key)
            else:
                await page.keyboard.press(args.key)
            print(f"OK: pressed {args.key}")

        # ---------- 键盘输入序列 ----------
        elif action == "keyboard":
            for key in (args.keys or "").split("+"):
                await page.keyboard.down(key.strip())
            await asyncio.sleep(0.05)
            for key in reversed((args.keys or "").split("+")):
                await page.keyboard.up(key.strip())
            print(f"OK: keyboard {args.keys}")

        # ---------- 滚动 ----------
        elif action == "scroll":
            if sel:
                elem = await page.wait_for_selector(sel, timeout=timeout)
                await elem.scroll_into_view_if_needed()
            else:
                dx = int(args.scroll_x or 0)
                dy = int(args.scroll_y or 0)
                await page.mouse.wheel(dx, dy)
            print("OK: scrolled")

        # ---------- 拖拽 ----------
        elif action == "drag":
            src = await page.wait_for_selector(sel, timeout=timeout)
            dst = await page.wait_for_selector(args.target, timeout=timeout)
            src_box = await src.bounding_box()
            dst_box = await dst.bounding_box()
            await page.mouse.move(
                src_box["x"] + src_box["width"] / 2,
                src_box["y"] + src_box["height"] / 2,
            )
            await page.mouse.down()
            await page.mouse.move(
                dst_box["x"] + dst_box["width"] / 2,
                dst_box["y"] + dst_box["height"] / 2,
                steps=10,
            )
            await page.mouse.up()
            print(f"OK: dragged {sel} → {args.target}")

        # ---------- 导航控制 ----------
        elif action == "navigate":
            nav = args.nav or "goto"
            if nav == "back":
                await page.go_back(timeout=timeout)
            elif nav == "forward":
                await page.go_forward(timeout=timeout)
            elif nav == "reload":
                await page.reload(timeout=timeout)
            else:
                await page.goto(args.url, timeout=timeout)
            print(f"OK: navigate {nav} → {page.url}")

        # ---------- 等待 ----------
        elif action == "wait":
            if args.wait_ms:
                await page.wait_for_timeout(int(args.wait_ms))
                print(f"OK: waited {args.wait_ms}ms")
            elif sel:
                state = args.wait_state or "visible"
                await page.wait_for_selector(sel, state=state, timeout=timeout)
                print(f"OK: waited for {sel} [{state}]")
            elif args.wait_text:
                await page.wait_for_function(
                    f"document.body.innerText.includes({json.dumps(args.wait_text)})",
                    timeout=timeout,
                )
                print(f"OK: waited for text '{args.wait_text}'")
            elif args.wait_url:
                await page.wait_for_url(args.wait_url, timeout=timeout)
                print(f"OK: waited for URL {args.wait_url}")

        # ---------- 数据提取 ----------
        elif action == "extract":
            mode = args.extract_mode or "text"
            if args.all:
                elems = await page.query_selector_all(sel)
                results = []
                for e in elems:
                    if mode == "text":
                        results.append(await e.inner_text())
                    elif mode == "html":
                        results.append(await e.inner_html())
                    elif mode == "attr":
                        results.append(await e.get_attribute(args.attr))
                    elif mode == "value":
                        results.append(await e.input_value())
                _out(results)
            else:
                elem = await page.wait_for_selector(sel, timeout=timeout)
                if mode == "text":
                    _out(await elem.inner_text())
                elif mode == "html":
                    _out(await elem.inner_html())
                elif mode == "outer_html":
                    _out(await elem.evaluate("el => el.outerHTML"))
                elif mode == "attr":
                    _out(await elem.get_attribute(args.attr))
                elif mode == "value":
                    _out(await elem.input_value())
                elif mode == "checked":
                    _out(await elem.is_checked())
                elif mode == "visible":
                    _out(await elem.is_visible())
                elif mode == "bbox":
                    _out(await elem.bounding_box())

        # ---------- JavaScript 执行 ----------
        elif action == "evaluate":
            script = args.script
            if args.script_file:
                script = Path(args.script_file).read_text(encoding="utf-8")
            if sel:
                elem = await page.wait_for_selector(sel, timeout=timeout)
                result = await elem.evaluate(script)
            else:
                result = await page.evaluate(script)
            _out(result)

        # ---------- Cookie 管理 ----------
        elif action == "cookie_get":
            cookies = await context.cookies(args.url or [])
            _out(cookies)

        elif action == "cookie_set":
            new_cookies = json.loads(args.cookies)
            await context.add_cookies(new_cookies)
            print(f"OK: set {len(new_cookies)} cookies")

        elif action == "cookie_clear":
            await context.clear_cookies()
            print("OK: cleared cookies")

        # ---------- Storage 管理 ----------
        elif action == "storage_get":
            store = args.storage_type or "local"
            js = (
                "Object.fromEntries(Object.entries(localStorage))"
                if store == "local"
                else "Object.fromEntries(Object.entries(sessionStorage))"
            )
            result = await page.evaluate(js)
            if args.storage_key:
                _out(result.get(args.storage_key))
            else:
                _out(result)

        elif action == "storage_set":
            store = args.storage_type or "local"
            key = args.storage_key
            val = args.storage_value
            if store == "local":
                await page.evaluate(f"localStorage.setItem({json.dumps(key)}, {json.dumps(val)})")
            else:
                await page.evaluate(f"sessionStorage.setItem({json.dumps(key)}, {json.dumps(val)})")
            print(f"OK: set {store}[{key}]")

        elif action == "storage_save":
            output = _abs(args.output or "storage_state.json")
            await context.storage_state(path=output)
            print(f"File written: {output}")

        # ---------- 文件上传 ----------
        elif action == "upload":
            elem = await page.wait_for_selector(sel, timeout=timeout)
            files = args.files.split(",")
            await elem.set_input_files(files)
            print(f"OK: uploaded {files}")

        # ---------- 文件下载 ----------
        elif action == "download":
            output_dir = _abs(args.output or ".")
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            async with page.expect_download() as dl_info:
                if sel:
                    elem = await page.wait_for_selector(sel, timeout=timeout)
                    await elem.click()
                else:
                    await page.evaluate(f"window.location.href = {json.dumps(args.download_url)}")
            download = await dl_info.value
            save_path = str(Path(output_dir) / download.suggested_filename)
            await download.save_as(save_path)
            print(f"File written: {save_path}")

        # ---------- iframe 操作 ----------
        elif action == "iframe_extract":
            frame_sel = args.frame_selector or "iframe"
            frame_elem = await page.wait_for_selector(frame_sel, timeout=timeout)
            frame = await frame_elem.content_frame()
            if sel:
                elem = await frame.wait_for_selector(sel, timeout=timeout)
                mode = args.extract_mode or "text"
                if mode == "text":
                    _out(await elem.inner_text())
                elif mode == "html":
                    _out(await elem.inner_html())
                elif mode == "attr":
                    _out(await elem.get_attribute(args.attr))
            else:
                _out(await frame.content())

        # ---------- 表单批量填写 ----------
        elif action == "form_fill":
            fields = json.loads(args.form_data)
            for field in fields:
                f_sel = field["selector"]
                f_type = field.get("type", "fill")
                f_val = field.get("value", "")
                elem = await page.wait_for_selector(f_sel, timeout=timeout)
                if f_type == "fill":
                    await elem.fill(str(f_val))
                elif f_type == "select":
                    await elem.select_option(value=str(f_val))
                elif f_type == "check":
                    if f_val:
                        await elem.check()
                    else:
                        await elem.uncheck()
                elif f_type == "click":
                    await elem.click()
                print(f"  filled: {f_sel} = {f_val!r}")
            print("OK: form filled")

        # ---------- 全页抓取 ----------
        elif action == "scrape":
            result = await page.evaluate("""() => {
                const links = [...document.querySelectorAll('a[href]')]
                    .map(a => ({text: a.innerText.trim(), href: a.href}))
                    .filter(l => l.text && l.href);
                const images = [...document.querySelectorAll('img[src]')]
                    .map(img => ({alt: img.alt, src: img.src}));
                const headings = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')]
                    .map(h => ({level: h.tagName, text: h.innerText.trim()}));
                const meta = {};
                document.querySelectorAll('meta[name],meta[property]').forEach(m => {
                    const key = m.getAttribute('name') || m.getAttribute('property');
                    meta[key] = m.getAttribute('content');
                });
                return {
                    title: document.title,
                    url: location.href,
                    text: document.body.innerText.substring(0, 5000),
                    links: links.slice(0, 100),
                    images: images.slice(0, 50),
                    headings,
                    meta,
                };
            }""")
            if args.output:
                output = _abs(args.output)
                Path(output).write_text(
                    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(f"File written: {output}")
            else:
                _out(result)

        # ---------- 批量动作 ----------
        elif action == "batch":
            batch_file = args.batch_file
            if not batch_file:
                print("ERROR: batch 动作需要 --batch_file 参数")
                sys.exit(1)
            steps = json.loads(Path(batch_file).read_text(encoding="utf-8"))
            for i, step in enumerate(steps):
                step_args = argparse.Namespace(**{**vars(args), **step})
                print(f"[{i+1}/{len(steps)}] action={step.get('action')} ...")
                await _run_step(page, context, step_args)
            print(f"OK: batch completed ({len(steps)} steps)")

        # ---------- 获取页面信息 ----------
        elif action == "info":
            info = {
                "url": page.url,
                "title": await page.title(),
                "viewport": page.viewport_size,
            }
            _out(info)

        # ---------- 获取完整 HTML ----------
        elif action == "html":
            content = await page.content()
            if args.output:
                output = _abs(args.output)
                Path(output).write_text(content, encoding="utf-8")
                print(f"File written: {output}")
            else:
                print(content)

        else:
            print(f"ERROR: 未知动作 '{action}'")
            sys.exit(1)

        await context.close()
        await browser.close()


async def _run_step(page, context, args) -> None:
    """批量模式下执行单个步骤（复用主逻辑的简化版）。"""
    sel = getattr(args, "selector", None)
    timeout = getattr(args, "timeout", 30000)

    if args.action == "navigate" and getattr(args, "url", None):
        await page.goto(args.url, timeout=timeout)
    elif args.action == "click" and sel:
        elem = await page.wait_for_selector(sel, timeout=timeout)
        await elem.click()
    elif args.action == "fill" and sel:
        elem = await page.wait_for_selector(sel, timeout=timeout)
        await elem.fill(getattr(args, "text", "") or "")
    elif args.action == "press":
        await page.keyboard.press(getattr(args, "key", ""))
    elif args.action == "wait":
        ms = getattr(args, "wait_ms", None)
        if ms:
            await page.wait_for_timeout(int(ms))
        elif sel:
            await page.wait_for_selector(sel, timeout=timeout)
    elif args.action == "screenshot":
        output = _abs(getattr(args, "output", "screenshot.png"))
        await page.screenshot(path=output, full_page=getattr(args, "full_page", False))
        print(f"File written: {output}")
    elif args.action == "evaluate":
        result = await page.evaluate(getattr(args, "script", ""))
        _out(result)


# ── CLI 参数定义 ──────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(
        description="Playwright 网页自动化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 基本
    p.add_argument("--action", required=True,
                   help="执行动作（screenshot/pdf/click/fill/type/select/check/uncheck/"
                        "hover/focus/press/keyboard/scroll/drag/navigate/wait/extract/"
                        "evaluate/cookie_get/cookie_set/cookie_clear/storage_get/"
                        "storage_set/storage_save/upload/download/iframe_extract/"
                        "form_fill/scrape/batch/info/html）")
    p.add_argument("--url",      help="目标 URL")
    p.add_argument("--selector", help="CSS 选择器或 XPath（xpath=//...）")
    p.add_argument("--output",   help="输出文件路径")

    # 浏览器
    p.add_argument("--browser",  default="chromium",
                   choices=["chromium", "firefox", "webkit"], help="浏览器类型（默认 chromium）")
    p.add_argument("--no_headless", action="store_true", help="显示浏览器窗口（非无头模式）")
    p.add_argument("--viewport", default="1280x800",    help="视口大小，格式 WxH（默认 1280x800）")
    p.add_argument("--user_agent",                      help="自定义 User-Agent")
    p.add_argument("--locale",                          help="语言设置，如 zh-CN")
    p.add_argument("--timezone",                        help="时区，如 Asia/Shanghai")
    p.add_argument("--proxy",                           help="代理服务器，如 http://127.0.0.1:7890")
    p.add_argument("--slow_mo",  type=int,              help="操作延迟（毫秒），便于调试")
    p.add_argument("--ignore_https_errors", action="store_true", help="忽略 HTTPS 证书错误")
    p.add_argument("--http_credentials",                help="HTTP 认证，格式 user:password")
    p.add_argument("--storage_state",                   help="加载存储状态（cookies+storage）JSON 文件路径")

    # 导航
    p.add_argument("--wait_until", default="domcontentloaded",
                   choices=["load", "domcontentloaded", "networkidle", "commit"],
                   help="页面加载等待条件（默认 domcontentloaded）")
    p.add_argument("--wait_for",   help="导航后等待的选择器或加载状态")
    p.add_argument("--timeout",    type=int, default=30000, help="超时（毫秒，默认 30000）")
    p.add_argument("--nav",        choices=["goto", "back", "forward", "reload"],
                   help="navigate 动作的子类型")

    # 等待
    p.add_argument("--wait_ms",    help="等待指定毫秒数")
    p.add_argument("--wait_state", default="visible",
                   choices=["visible", "hidden", "attached", "detached"],
                   help="等待元素状态（默认 visible）")
    p.add_argument("--wait_text",  help="等待页面出现指定文字")
    p.add_argument("--wait_url",   help="等待 URL 匹配（支持 glob）")

    # 输入
    p.add_argument("--text",       help="输入文本（fill/type 动作）")
    p.add_argument("--type_delay", type=int, default=0, help="逐字输入延迟（毫秒）")
    p.add_argument("--key",        help="键盘按键，如 Enter、Tab、Escape、ArrowDown")
    p.add_argument("--keys",       help="组合键，如 Control+A、Shift+Tab")
    p.add_argument("--button",     choices=["left", "right", "middle"], help="鼠标按键")
    p.add_argument("--click_count",type=int, help="点击次数")
    p.add_argument("--modifiers",  help="修饰键，逗号分隔：Shift,Control,Alt,Meta")

    # 下拉选择
    p.add_argument("--values",     help="select 选项值，逗号分隔")
    p.add_argument("--select_by",  default="value",
                   choices=["value", "label", "index"], help="select 匹配方式（默认 value）")

    # 提取
    p.add_argument("--extract_mode", default="text",
                   choices=["text", "html", "outer_html", "attr", "value",
                             "checked", "visible", "bbox"],
                   help="extract 提取模式（默认 text）")
    p.add_argument("--attr",       help="提取的属性名（extract_mode=attr 时使用）")
    p.add_argument("--all",        action="store_true", help="提取所有匹配元素（返回列表）")

    # 滚动
    p.add_argument("--scroll_x",   help="水平滚动像素")
    p.add_argument("--scroll_y",   help="垂直滚动像素")

    # 拖拽
    p.add_argument("--target",     help="拖拽目标选择器（drag 动作）")

    # 截图
    p.add_argument("--full_page",  action="store_true", help="截取完整页面")
    p.add_argument("--clip",       help="截图区域 x,y,w,h")

    # PDF
    p.add_argument("--pdf_format", default="A4",
                   choices=["A4", "A3", "Letter", "Legal", "Tabloid"],
                   help="PDF 纸张格式（默认 A4）")
    p.add_argument("--pdf_margin", help="PDF 边距 top,right,bottom,left，如 20px,20px,20px,20px")

    # Cookie
    p.add_argument("--cookies",    help="Cookie JSON 字符串")

    # Storage
    p.add_argument("--storage_type",  default="local",
                   choices=["local", "session"], help="存储类型（默认 local）")
    p.add_argument("--storage_key",   help="storage 键名")
    p.add_argument("--storage_value", help="storage 值")

    # 文件上传/下载
    p.add_argument("--files",         help="上传文件路径，逗号分隔")
    p.add_argument("--download_url",  help="直接触发下载的 URL")

    # iframe
    p.add_argument("--frame_selector", help="iframe 选择器（默认 iframe）")

    # 表单批量填写
    p.add_argument("--form_data",  help='表单数据 JSON，如 [{"selector":"#name","type":"fill","value":"Alice"}]')

    # JavaScript
    p.add_argument("--script",      help="JavaScript 代码字符串")
    p.add_argument("--script_file", help="JavaScript 文件路径")

    # Dialog
    p.add_argument("--dialog_action", choices=["accept", "dismiss"],
                   help="自动处理弹窗：accept 确认 / dismiss 取消")
    p.add_argument("--dialog_input",  help="accept 弹窗时输入的文字")

    # 网络拦截
    p.add_argument("--block_urls",   help='需要屏蔽的 URL 关键词 JSON 数组，如 ["ads","tracker"]')

    # 批量
    p.add_argument("--batch_file",   help="批量动作 JSON 文件路径")

    args = p.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
