# WebSocket Message Schema — DOM Highlight Feature

## AI Agent → Extension (Request)

```json
{
  "id": "req_<counter>",
  "action": "highlight",
  "args": {
    "selector": "string (required) — CSS selector to match elements",
    "color": "string (optional) — hex/rgb color, default: #22c55e",
    "duration": "number (optional) — ms before auto-clear, default: 0 (persistent)",
    "scrollIntoView": "boolean (optional) — scroll to first match, default: false",
    "maxElements": "number (optional) — max elements to highlight, default: 20"
  }
}
```

```json
{
  "id": "req_<counter>",
  "action": "clear_highlight",
  "args": {
    "all": "boolean (optional) — clear all tabs, default: false"
  }
}
```

## Extension → AI Agent (Response)

### highlight — Success
```json
{
  "id": "req_1",
  "success": true,
  "action": "highlight",
  "elements": [
    {
      "tag": "button",
      "text": "Submit",
      "rect": { "x": 100, "y": 200, "width": 120, "height": 40 },
      "index": 0,
      "visible": true,
      "selector": "button.btn-primary"
    }
  ],
  "count": 1,
  "highlightColor": "#22c55e"
}
```

### highlight — Error
```json
{
  "id": "req_1",
  "success": false,
  "action": "highlight",
  "error": "No elements found for selector: .nonexistent"
}
```

### clear_highlight — Success
```json
{
  "id": "req_2",
  "success": true,
  "action": "clear_highlight",
  "cleared": 3
}
```
