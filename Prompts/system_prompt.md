# WebBridge System Prompt — Available Tools

Use these JSON action commands to automate browser actions through the WebBridge agent interface.

---

## 1. Browser Navigation & Tab Control
### `navigate`
Navigate to a web page URL.
```json
{"action": "navigate", "args": {"url": "https://www.example.com", "newTab": false}}
```

### `list_tabs`
List all active tabs in the current browser session.
```json
{"action": "list_tabs", "args": {}}
```

### `find_tab`
Find and switch to a tab matching a URL or ID, or open a new one if not found.
```json
{"action": "find_tab", "args": {"url": "https://www.example.com"}}
```

### `close_tab`
Close a tab by ID, or close the currently active tab if no ID is specified.
```json
{"action": "close_tab", "args": {"tabId": 12345}}
```

---

## 2. DOM Page Interaction
### `click`
Execute a mouse click on an element matching a CSS selector.
```json
{"action": "click", "args": {"selector": "button.submit"}}
```

### `fill`
Type a text string into an input selector.
```json
{"action": "fill", "args": {"selector": "input#email", "value": "user@example.com"}}
```

### `pressKey`
Press a single keyboard key (e.g. `Enter`, `Tab`, `ArrowDown`).
```json
{"action": "pressKey", "args": {"key": "Enter"}}
```

### `upload`
Upload a file to a target file input selector.
```json
{"action": "upload", "args": {"selector": "input[type=file]", "filePath": "path/to/file.txt"}}
```

---

## 3. DOM Extraction & Analysis
### `snapshot`
Capture the accessibility tree and layout hierarchy of the page.
```json
{"action": "snapshot", "args": {}}
```

### `highlight`
Visually highlight elements matching a selector (e.g. for debugging or location confirmation).
```json
{"action": "highlight", "args": {"selector": "button", "color": "#22c55e", "duration": 5000, "scrollIntoView": true}}
```

### `clear_highlight`
Clear all active highlights on the page.
```json
{"action": "clear_highlight", "args": {}}
```

---

## 4. Page Scrolling
### `scroll`
Scroll page offset or scroll to target element coordinates.
```json
{"action": "scroll", "args": {"selector": "div.container", "x": 0, "y": 500}}
```

### `auto_scroll`
Triggers continuous smooth auto-scrolling on the active page.
```json
{"action": "auto_scroll", "args": {"duration": 10, "step": 300}}
```

### `scroll_stop`
Stops any running auto-scroll loops.
```json
{"action": "scroll_stop", "args": {}}
```

---

## 5. Runtimes & Script Execution
### `evaluate`
Run a raw Javascript string within the context of the active page.
```json
{"action": "evaluate", "args": {"code": "document.title"}}
```

### `screenshot`
Capture a screenshot of the visible tab area.
```json
{"action": "screenshot", "args": {"format": "png", "quality": 80}}
```
