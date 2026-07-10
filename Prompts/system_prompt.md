# WebBridge System Prompt — Available Tools

## DOM Element Highlight
**Commands:** `highlight`, `clear_highlight`

Visually highlight DOM elements matching a CSS selector. Useful for:
- Verifying which elements match a selector before interacting
- Visual feedback during automation
- Debugging element positions and visibility

### Usage:
```json
// Highlight all buttons
{"action": "highlight", "args": {"selector": "button", "color": "#22c55e", "duration": 5000, "scrollIntoView": true}}

// Clear highlights
{"action": "clear_highlight", "args": {}}
```

### Response includes:
- `elements[]` — array of matched elements with tag, text, rect (x/y/width/height)
- `count` — number of highlighted elements
- Each element has `rect` with pixel coordinates for spatial awareness
