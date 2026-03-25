---
name: playwright
description: 使用 Playwright 控制浏览器，支持截图、PDF、表单操作、数据提取、JavaScript执行、Cookie/Storage管理、文件上传下载、iframe、批量动作等全功能网页自动化
metadata: '{"openclaw": {"always": true}}'
---

# Playwright 网页自动化

## 安装依赖

```bash
pip install playwright
playwright install chromium   # 最小安装
# 或安装全部：playwright install
```

## 基本用法

```
python {baseDir}/playwright_tool.py --action <动作> [选项...]
```

---

## 动作列表

### 📸 screenshot — 截图

截取整页或指定元素。

```bash
# 整页截图
python playwright_tool.py --action screenshot --url https://example.com --output page.png --full_page

# 仅截取指定元素
python playwright_tool.py --action screenshot --url https://example.com --selector "#chart" --output chart.png

# 截取指定区域 x,y,宽,高
python playwright_tool.py --action screenshot --url https://example.com --clip 0,0,800,600 --output crop.png
```

| 参数 | 说明 | 必填 |
|------|------|------|
| --url | 目标网址 | 是 |
| --output | 保存路径（默认 screenshot.png） | 否 |
| --full_page | 截取完整页面（包含滚动区域） | 否 |
| --selector | 仅截取该元素 | 否 |
| --clip | 截取区域 x,y,w,h | 否 |

---

### 📄 pdf — 生成 PDF

```bash
python playwright_tool.py --action pdf --url https://example.com --output report.pdf --pdf_format A4
```

| 参数 | 说明 | 默认 |
|------|------|------|
| --pdf_format | A4 / A3 / Letter / Legal / Tabloid | A4 |
| --pdf_margin | 边距 top,right,bottom,left，如 20px,20px,20px,20px | 无 |

---

### 🖱️ click — 点击元素

```bash
# 普通点击
python playwright_tool.py --action click --url https://example.com --selector "button#submit"

# 右键点击
python playwright_tool.py --action click --url https://example.com --selector ".item" --button right

# Ctrl+点击（新标签打开）
python playwright_tool.py --action click --url https://example.com --selector "a" --modifiers Control
```

---

### ✏️ fill — 快速填写输入框

```bash
python playwright_tool.py --action fill --url https://example.com --selector "#username" --text "admin"
```

---

### ⌨️ type — 逐字符输入（模拟真人打字）

```bash
python playwright_tool.py --action type --url https://example.com --selector "#search" --text "Playwright 教程" --type_delay 50
```

---

### 🔽 select — 下拉框选择

```bash
# 按 value 选择
python playwright_tool.py --action select --url https://example.com --selector "#country" --values "CN"

# 按 label 选择（显示文字）
python playwright_tool.py --action select --url https://example.com --selector "#size" --values "大码" --select_by label

# 多选
python playwright_tool.py --action select --url https://example.com --selector "#tags" --values "python,web,ai"
```

---

### ☑️ check / uncheck — 复选框

```bash
python playwright_tool.py --action check   --url https://example.com --selector "#agree"
python playwright_tool.py --action uncheck --url https://example.com --selector "#newsletter"
```

---

### 🖱️ hover — 悬停元素

```bash
python playwright_tool.py --action hover --url https://example.com --selector ".menu-item"
```

---

### ⌨️ press — 按键

```bash
# 单键
python playwright_tool.py --action press --url https://example.com --selector "#input" --key Enter

# 全局按键（不指定 selector）
python playwright_tool.py --action press --url https://example.com --key Escape

# 常用键：Enter, Tab, Escape, ArrowUp, ArrowDown, ArrowLeft, ArrowRight
#         Backspace, Delete, F1-F12, PageUp, PageDown, Home, End
```

---

### ⌨️ keyboard — 组合键

```bash
# Ctrl+A 全选
python playwright_tool.py --action keyboard --url https://example.com --keys "Control+a"

# Ctrl+C 复制
python playwright_tool.py --action keyboard --url https://example.com --keys "Control+c"
```

---

### 📜 scroll — 滚动

```bash
# 滚动页面（向下 500px）
python playwright_tool.py --action scroll --url https://example.com --scroll_y 500

# 将元素滚动到可见区域
python playwright_tool.py --action scroll --url https://example.com --selector "#footer"
```

---

### 🔀 drag — 拖拽

```bash
python playwright_tool.py --action drag --url https://example.com --selector "#drag-handle" --target "#drop-zone"
```

---

### 🌐 navigate — 导航控制

```bash
# 前进 / 后退 / 刷新
python playwright_tool.py --action navigate --url https://example.com --nav back
python playwright_tool.py --action navigate --url https://example.com --nav forward
python playwright_tool.py --action navigate --url https://example.com --nav reload
```

---

### ⏳ wait — 等待

```bash
# 等待 2 秒
python playwright_tool.py --action wait --url https://example.com --wait_ms 2000

# 等待元素出现
python playwright_tool.py --action wait --url https://example.com --selector "#result" --wait_state visible

# 等待页面出现指定文字
python playwright_tool.py --action wait --url https://example.com --wait_text "加载完成"

# 等待 URL 跳转
python playwright_tool.py --action wait --url https://example.com --wait_url "**/dashboard**"

# 等待状态：visible（可见）| hidden（隐藏）| attached（存在于DOM）| detached（从DOM移除）
```

---

### 📥 extract — 提取数据

```bash
# 提取文字
python playwright_tool.py --action extract --url https://example.com --selector "h1"

# 提取 HTML
python playwright_tool.py --action extract --url https://example.com --selector ".content" --extract_mode html

# 提取属性
python playwright_tool.py --action extract --url https://example.com --selector "img.hero" --extract_mode attr --attr src

# 提取输入框的值
python playwright_tool.py --action extract --url https://example.com --selector "#email" --extract_mode value

# 提取所有匹配元素（返回列表）
python playwright_tool.py --action extract --url https://example.com --selector "li.item" --all

# 获取元素位置和尺寸
python playwright_tool.py --action extract --url https://example.com --selector "#box" --extract_mode bbox
```

| extract_mode | 说明 |
|------|------|
| text | 元素内纯文本（默认） |
| html | 元素内 innerHTML |
| outer_html | 元素完整 outerHTML |
| attr | 指定属性值（需 --attr） |
| value | input/select 的当前值 |
| checked | checkbox 是否勾选 |
| visible | 元素是否可见 |
| bbox | 元素位置 {x,y,width,height} |

---

### 🔧 evaluate — 执行 JavaScript

```bash
# 内联脚本
python playwright_tool.py --action evaluate --url https://example.com \
  --script "document.title"

# 操作 DOM 并返回结果
python playwright_tool.py --action evaluate --url https://example.com \
  --script "[...document.querySelectorAll('a')].map(a=>a.href)"

# 在指定元素上执行
python playwright_tool.py --action evaluate --url https://example.com \
  --selector "#form" --script "el => el.getBoundingClientRect()"

# 从文件加载脚本
python playwright_tool.py --action evaluate --url https://example.com \
  --script_file ./my_script.js
```

---

### 🍪 cookie_get / cookie_set / cookie_clear — Cookie 管理

```bash
# 获取所有 Cookie（JSON 输出）
python playwright_tool.py --action cookie_get --url https://example.com

# 设置 Cookie
python playwright_tool.py --action cookie_set --url https://example.com \
  --cookies '[{"name":"token","value":"abc123","domain":"example.com","path":"/"}]'

# 清空所有 Cookie
python playwright_tool.py --action cookie_clear --url https://example.com
```

---

### 💾 storage_get / storage_set / storage_save — 存储管理

```bash
# 获取全部 localStorage
python playwright_tool.py --action storage_get --url https://example.com

# 获取指定 key
python playwright_tool.py --action storage_get --url https://example.com --storage_key "auth_token"

# 设置 localStorage
python playwright_tool.py --action storage_set --url https://example.com \
  --storage_key "theme" --storage_value "dark"

# sessionStorage
python playwright_tool.py --action storage_get --url https://example.com --storage_type session

# 保存完整状态（cookies + storage）供下次复用
python playwright_tool.py --action storage_save --url https://example.com --output state.json
```

---

### 📤 upload — 文件上传

```bash
python playwright_tool.py --action upload --url https://example.com \
  --selector "input[type=file]" --files "/path/to/file.pdf"

# 多文件
python playwright_tool.py --action upload --url https://example.com \
  --selector "input[type=file]" --files "/path/a.jpg,/path/b.jpg"
```

---

### 📦 download — 文件下载

```bash
# 点击下载按钮触发下载
python playwright_tool.py --action download --url https://example.com \
  --selector "a.download-btn" --output ./downloads/

# 直接下载 URL
python playwright_tool.py --action download --url https://example.com \
  --download_url "https://example.com/file.zip" --output ./downloads/
```

---

### 🖼️ iframe_extract — iframe 内容提取

```bash
# 提取 iframe 内元素文字
python playwright_tool.py --action iframe_extract --url https://example.com \
  --frame_selector "iframe#content" --selector "h1"

# 提取整个 iframe HTML
python playwright_tool.py --action iframe_extract --url https://example.com \
  --frame_selector "iframe"
```

---

### 📝 form_fill — 表单批量填写

一次性填写整个表单（支持 input、select、checkbox）：

```bash
python playwright_tool.py --action form_fill --url https://example.com \
  --form_data '[
    {"selector":"#name",     "type":"fill",   "value":"张三"},
    {"selector":"#email",    "type":"fill",   "value":"zs@example.com"},
    {"selector":"#country",  "type":"select", "value":"CN"},
    {"selector":"#agree",    "type":"check",  "value":true},
    {"selector":"button[type=submit]", "type":"click"}
  ]'
```

| type | 说明 |
|------|------|
| fill | 填写文本 |
| select | 选择下拉选项（按 value） |
| check | 勾选/取消勾选复选框 |
| click | 点击元素 |

---

### 🌐 scrape — 全页内容抓取

提取页面标题、正文、链接、图片、标题层级、Meta 信息：

```bash
python playwright_tool.py --action scrape --url https://example.com

# 保存为 JSON 文件
python playwright_tool.py --action scrape --url https://example.com --output scraped.json
```

---

### ℹ️ info — 页面信息

```bash
python playwright_tool.py --action info --url https://example.com
# 输出：{"url":"...","title":"...","viewport":{...}}
```

---

### 📄 html — 获取页面 HTML

```bash
python playwright_tool.py --action html --url https://example.com --output page.html
```

---

### 🔄 batch — 批量执行动作

从 JSON 文件依次执行多个步骤：

```bash
python playwright_tool.py --action batch --url https://example.com \
  --batch_file ./steps.json
```

`steps.json` 示例：
```json
[
  {"action": "navigate", "url": "https://example.com/login"},
  {"action": "fill",   "selector": "#username", "text": "admin"},
  {"action": "fill",   "selector": "#password", "text": "secret"},
  {"action": "click",  "selector": "button[type=submit]"},
  {"action": "wait",   "wait_ms": "1000"},
  {"action": "screenshot", "output": "after_login.png", "full_page": true}
]
```

---

## 全局选项

| 参数 | 说明 | 默认 |
|------|------|------|
| --browser | chromium / firefox / webkit | chromium |
| --no_headless | 显示浏览器窗口 | 无头模式 |
| --viewport | 视口尺寸 WxH | 1280x800 |
| --timeout | 操作超时（毫秒） | 30000 |
| --user_agent | 自定义 UA | 无 |
| --locale | 语言，如 zh-CN | 无 |
| --timezone | 时区，如 Asia/Shanghai | 无 |
| --proxy | 代理服务器 http://host:port | 无 |
| --slow_mo | 操作间延迟（毫秒），便于调试 | 0 |
| --http_credentials | HTTP 认证 user:password | 无 |
| --ignore_https_errors | 忽略证书错误 | 否 |
| --storage_state | 复用已保存的 cookies+storage 状态 | 无 |
| --wait_for | 导航后等待的选择器或状态 | 无 |
| --wait_until | 页面加载等待条件 | domcontentloaded |
| --dialog_action | 自动处理弹窗 accept/dismiss | 无 |
| --block_urls | 屏蔽 URL 关键词 JSON 数组 | 无 |
| --cookies | 预置 Cookie JSON 字符串 | 无 |

---

## 常见使用场景

### 登录并保存状态
```bash
# 1. 登录并保存 state
python playwright_tool.py --action form_fill \
  --url https://example.com/login --no_headless \
  --form_data '[{"selector":"#user","type":"fill","value":"admin"},
               {"selector":"#pass","type":"fill","value":"secret"},
               {"selector":"button[type=submit]","type":"click"}]'

python playwright_tool.py --action storage_save --url https://example.com/dashboard \
  --output login_state.json

# 2. 下次直接复用登录态
python playwright_tool.py --action screenshot --url https://example.com/dashboard \
  --storage_state login_state.json --output dashboard.png --full_page
```

### 定时监控页面变化
```bash
python playwright_tool.py --action extract \
  --url https://example.com/price \
  --selector ".price" --extract_mode text
```

### 屏蔽广告抓取内容
```bash
python playwright_tool.py --action scrape \
  --url https://example.com \
  --block_urls '["ads","doubleclick","analytics"]' \
  --output clean.json
```

### XPath 选择器
```bash
# 以 xpath= 前缀使用 XPath
python playwright_tool.py --action extract \
  --url https://example.com \
  --selector "xpath=//h1[contains(@class,'title')]"
```

---

## 注意事项

1. **选择器**支持 CSS 选择器（默认）和 XPath（`xpath=//...` 前缀）
2. **输出路径**若包含目录，请确保目录已存在
3. **等待策略**：动态页面建议配合 `--wait_for` 或 `--wait_until networkidle`
4. **无头模式**：默认开启，调试时用 `--no_headless` 显示浏览器
5. **File written**：所有文件输出都会打印 `File written: <路径>` 供 agent 识别
