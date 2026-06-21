---
name: browser-webbridge
description: Use when controlling a web browser from opencode — navigating, clicking, extracting text, taking screenshots, filling forms, capturing network requests, or managing browser tabs. Use ONLY within the broweser project directory.
---

# Browser WebBridge

This project provides browser automation through a bridge server + Chrome extension. The bridge lets opencode drive a real Chrome browser programmatically.

## Architecture

```
opencode → bridge/cli.py (CLI) → HTTP localhost:10088 → bridge/server.py → WebSocket localhost:10087 → Chrome Extension → Browser Tab
```

## Quick Start

### 1. Install dependencies

```powershell
pip install -r requirements.txt
playwright install chromium
```

### 2. Load the Chrome extension

1. Open Chrome to `chrome://extensions`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked** and select `bridge/extension/`
4. You should see "Opencode WebBridge" extension installed

### 3. Start the bridge server

```powershell
python bridge/cli.py server start
```

Or manually:

```powershell
python bridge/server.py
```

### 4. Check status

```powershell
python bridge/cli.py status
```

Expected output: `Running: True`, `Extension connected: True`

### 5. Use the browser

```powershell
python bridge/cli.py navigate https://example.com
python bridge/cli.py snapshot --preview
python bridge/cli.py click 'h1'
python bridge/cli.py screenshot --name mypage
```

## CLI Commands

All commands via `python bridge/cli.py <command> [args]`:

| Command | Description |
|---------|-------------|
| `navigate <url>` | Navigate to URL (new tab) |
| `snapshot [--preview]` | Get page accessibility tree |
| `click <selector>` | Click element (CSS, XPath, or @e ref) |
| `fill <selector> <value>` | Fill input/textarea |
| `find <selector>` | Find elements on page |
| `text <selector>` | Extract text |
| `attr <selector> <attr>` | Extract attribute |
| `screenshot [--name NAME]` | Take screenshot |
| `evaluate <js-code>` | Run JS in page |
| `html [selector]` | Get page/element HTML |
| `scroll <selector>` | Scroll element into view |
| `auto-scroll [--duration 5] [--step 300]` | Auto-scroll page gradually over N seconds |
| `url` / `title` | Get current URL/title |
| `extract <json-schema>` | Extract structured data |
| `list-tabs` / `close-tab` | Tab management |
| `network <start\|stop\|list>` | Network request capture |
| `upload <selector> <file>` | Upload file to input |
| `server <start\|stop>` | Server management |
| `status` | Check bridge + extension |

## Using with `browser_agent.py` (standalone)

For simple scripting without the extension:

```powershell
python browser_agent.py
```

This opens an interactive REPL. Commands: `goto`, `find`, `click`, `text`, `attr`, `table`, `extract`, `screenshot`, `el_screenshot`, `html`, `title`, `url`, `fill`, `scroll`, `auto_scroll`, `wait`, `eval`, `close`, `help`.

### Auto-scroll examples

```powershell
# Scroll page for 5 seconds (default)
python bridge/cli.py auto-scroll

# Scroll for 10 seconds, 500px per step
python bridge/cli.py auto-scroll --duration 10 --step 500

# In browser_agent.py REPL
> auto_scroll 8
```

## Example: scraping product data

```powershell
# Navigate and extract structured data
python bridge/cli.py navigate https://example.com/products
python bridge/cli.py extract '{"titles":"h2.product-title","prices":"span.price","links":"a::attr(href)"}'
```

## Example: login flow

```powershell
python bridge/cli.py navigate https://example.com/login
python bridge/cli.py fill 'input[name=email]' user@example.com
python bridge/cli.py fill 'input[name=password]' mypassword
python bridge/cli.py click 'button[type=submit]'
python bridge/cli.py snapshot --preview
```

## Stopping the server

```powershell
python bridge/cli.py server stop
```
