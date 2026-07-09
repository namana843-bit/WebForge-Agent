---
name: Browser CLI Control
description: Direct browser control via CLI. Opens Chrome, navigates, clicks, types, takes screenshots. Core skill for all browser automation. Supports local + remote cloud browsers.
---

# Browser CLI Control

This skill enables direct browser control via CLI or MCP-based interfaces, supporting navigation, clicking, typing, screenshots, and integration with local and remote cloud browsers.

## Core Operations

### 1. Launching and Session Management
- Ensure the WebBridge server (running on `http://127.0.0.1:10088` or standard endpoint) is running.
- Use `mcp_server.py` or directly query/interact with the bridge endpoint to control sessions.
- Configure remote cloud browser WebSocket/HTTP endpoints if utilizing remote instances.

### 2. Basic Browser Interaction
- **Navigation**: Command the page to go to a specific URL.
- **Clicking**: Use specific CSS selectors/XPath on elements (via the `click` tool or action).
- **Typing**: Fill inputs by targeting selectors and sending text values (via the `type` tool or action).
- **Hover & Drag**: Target selectors to hover over or drag elements as required by interactive web components.
- **Scrolling**: Scroll active pages to reveal hidden elements.

### 3. Diagnostics & Verification
- Retrieve screenshots to verify correctness of actions.
- Retrieve current page content or page source to analyze structure.
