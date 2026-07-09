#!/usr/bin/env python3
"""WebBridge MCP Server - Exposes browser actions to external LLM clients."""

import sys
import json
import time
import urllib.request
import urllib.error
import urllib.parse
import traceback
from datetime import datetime

BRIDGE_URL = "http://127.0.0.1:10088"
COMMAND_HISTORY = []

def api_call(action, args=None):
    payload = json.dumps({"action": action, "args": args or {}}).encode("utf-8")
    req = urllib.request.Request(
        f"{BRIDGE_URL}/command",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": f"Failed to reach WebBridge server: {e}"}

def handle_initialize(req_id, params):
    response = {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "webbridge-mcp",
                "version": "1.0.0"
            }
        }
    }
    return response

def handle_list_tools(req_id):
    tools = [
        {
            "name": "search",
            "description": "Web search via DuckDuckGo/Google/Bing.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query string."},
                    "engine": {"type": "string", "enum": ["duckduckgo", "google", "bing"], "description": "Search engine to use (default: duckduckgo)."}
                },
                "required": ["query"]
            }
        },
        {
            "name": "navigate",
            "description": "Navigate to target web URL with empty-DOM retry logic.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Web URL to open."}
                },
                "required": ["url"]
            }
        },
        {
            "name": "go_back",
            "description": "Navigate back in browser history.",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "wait",
            "description": "Delay/wait execution for a number of seconds (capped at 30s).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "number", "description": "Seconds to delay."}
                },
                "required": ["seconds"]
            }
        },
        {
            "name": "click_element",
            "description": "Click by element index (ref ID) OR by coordinates.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector or element ref ID (e.g. @e_abc123)."},
                    "x": {"type": "number", "description": "Horizontal coordinate to click."},
                    "y": {"type": "number", "description": "Vertical coordinate to click."}
                }
            }
        },
        {
            "name": "input_text",
            "description": "Type text into target field. Clears by default, append mode available.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector or element ref ID."},
                    "text": {"type": "string", "description": "Text value to input."},
                    "append": {"type": "boolean", "description": "If true, appends text instead of clearing first (default: false)."}
                },
                "required": ["selector", "text"]
            }
        },
        {
            "name": "upload_file",
            "description": "Upload a local file to target file input.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of file input."},
                    "file_path": {"type": "string", "description": "Absolute file path."}
                },
                "required": ["selector", "file_path"]
            }
        },
        {
            "name": "switch_tab",
            "description": "Switch to a specific tab by ID.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tab_id": {"type": "integer", "description": "The ID of the tab to switch to."}
                },
                "required": ["tab_id"]
            }
        },
        {
            "name": "close_tab",
            "description": "Close a specific tab by ID.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tab_id": {"type": "integer", "description": "The ID of the tab to close."}
                },
                "required": ["tab_id"]
            }
        },
        {
            "name": "extract",
            "description": "LLM-powered structured data extraction from page markdown.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "schema": {"type": "object", "description": "Optional JSON schema layout map."},
                    "prompt": {"type": "string", "description": "Optional extraction instructions."}
                }
            }
        },
        {
            "name": "scroll",
            "description": "Scroll up/down (full page, half page, to element).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["up", "down"], "description": "Scroll direction."},
                    "amount": {"type": "string", "enum": ["full", "half"], "description": "Scroll amount (full page or half page)."},
                    "selector": {"type": "string", "description": "Optional CSS selector to scroll into view."},
                    "x": {"type": "integer", "description": "Optional explicit horizontal scroll offset."},
                    "y": {"type": "integer", "description": "Optional explicit vertical scroll offset."}
                }
            }
        },
        {
            "name": "send_keys",
            "description": "Send keyboard shortcuts/button presses (e.g. Enter, Escape).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "keys": {"type": "string", "description": "Key identifier (e.g. Enter, Escape, ArrowDown)."}
                },
                "required": ["keys"]
            }
        },
        {
            "name": "screenshot",
            "description": "Capture screen snapshot.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Output filename."}
                }
            }
        },
        {
            "name": "save_as_pdf",
            "description": "Export active page layout as PDF with header/footer options.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "PDF filename."}
                }
            }
        },
        {
            "name": "get_dropdown_options",
            "description": "Get options from a select element or autocomplete listbox.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector or ref ID of select element."}
                },
                "required": ["selector"]
            }
        },
        {
            "name": "click",
            "description": "Click an element on the active page.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector or XPath of element."}
                },
                "required": ["selector"]
            }
        },
        {
            "name": "type",
            "description": "Type text into a target input element.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of target input."},
                    "text": {"type": "string", "description": "Text value to type."}
                },
                "required": ["selector", "text"]
            }
        },
        {
            "name": "hover",
            "description": "Hover mouse cursor over target selector.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of element to hover over."}
                },
                "required": ["selector"]
            }
        },
        {
            "name": "drag",
            "description": "Initiate drag-start event on selector.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector to drag."}
                },
                "required": ["selector"]
            }
        },
        {
            "name": "drop",
            "description": "Perform drop event on selector.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector to drop onto."}
                },
                "required": ["selector"]
            }
        },
        {
            "name": "download",
            "description": "List files inside the download folder.",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "upload",
            "description": "Upload a local file to target file input.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of file input."},
                    "file_path": {"type": "string", "description": "Absolute file path."}
                },
                "required": ["selector", "file_path"]
            }
        },
        {
            "name": "press",
            "description": "Press a keyboard button.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Key identifier (e.g. Enter, Escape, ArrowDown)."}
                },
                "required": ["key"]
            }
        },
        {
            "name": "pdf",
            "description": "Save active page layout as PDF.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "PDF filename."}
                }
            }
        },
        {
            "name": "history",
            "description": "Get log record history of executed commands in this session.",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        }
    ]
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "tools": tools
        }
    }

def handle_call_tool(req_id, tool_name, arguments):
    # Log to history
    COMMAND_HISTORY.append({
        "timestamp": datetime.now().isoformat(),
        "tool": tool_name,
        "arguments": arguments
    })

    res = None
    if tool_name == "search":
        query = arguments.get("query")
        engine = arguments.get("engine", "duckduckgo")
        if engine == "google":
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        elif engine == "bing":
            url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
        else:
            url = f"https://duckduckgo.com/?q={urllib.parse.quote(query)}"
        res = api_call("navigate", {"url": url})
        
    elif tool_name == "navigate":
        url = arguments.get("url")
        retries = 3
        for attempt in range(retries):
            res = api_call("navigate", {"url": url})
            if "error" in res:
                if attempt == retries - 1:
                    break
                time.sleep(1.0)
                continue
            dom_check = api_call("evaluate", {"code": "document.body ? document.body.innerText.trim().length : 0"})
            if not dom_check.get("error") and dom_check.get("result", 0) > 0:
                break
            if attempt < retries - 1:
                time.sleep(1.0)
                
    elif tool_name == "go_back":
        res = api_call("evaluate", {"code": "window.history.back();"})
        time.sleep(1.0)
        
    elif tool_name == "wait":
        secs = min(float(arguments.get("seconds", 1.0)), 30.0)
        time.sleep(secs)
        res = {"success": True, "waited": secs}
        
    elif tool_name == "click_element":
        selector = arguments.get("selector")
        x = arguments.get("x")
        y = arguments.get("y")
        if x is not None and y is not None:
            js_code = f"""
            (() => {{
                const el = document.elementFromPoint({x}, {y});
                if (!el) return {{ error: "No element at coordinates ({x}, {y})" }};
                el.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true, view: window}}));
                return {{ success: true, element: el.tagName }};
            }})()
            """
            res = api_call("evaluate", {"code": js_code})
        elif selector:
            res = api_call("click", {"selector": selector})
        else:
            res = {"error": "Either selector or both x and y coordinates must be provided."}
            
    elif tool_name == "input_text":
        selector = arguments.get("selector")
        text = arguments.get("text")
        append = arguments.get("append", False)
        
        sel_json = json.dumps(selector)
        text_json = json.dumps(text)
        js_code = f"""
        (() => {{
            const el = document.querySelector({sel_json});
            if (!el) return {{ error: "Element not found" }};
            if ({'false' if append else 'true'}) {{
                el.value = '';
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
            el.focus();
            el.value += {text_json};
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return {{ success: true }};
        }})()
        """
        res = api_call("evaluate", {"code": js_code})
        
    elif tool_name == "upload_file":
        res = api_call("upload", {"selector": arguments.get("selector"), "file": arguments.get("file_path")})
        
    elif tool_name == "switch_tab":
        res = api_call("find_tab", {"tabId": arguments.get("tab_id")})
        
    elif tool_name == "close_tab":
        res = api_call("close_tab", {"tabId": arguments.get("tab_id")})
        
    elif tool_name == "extract":
        schema = arguments.get("schema")
        prompt = arguments.get("prompt")
        js_code = "document.body ? document.body.innerText : ''"
        text_res = api_call("evaluate", {"code": js_code})
        page_text = text_res.get("result", "")
        
        if page_text:
            extract_prompt = f"Extract structured data from the page text. Schema: {schema}. Prompt: {prompt}."
            js_extract = f"""
            (async () => {{
                if (typeof PageAgent === 'undefined') {{
                    const loadScript = () => new Promise((resolve, reject) => {{
                        const s = document.createElement('script');
                        s.src = "https://cdn.jsdelivr.net/npm/page-agent@latest/dist/iife/page-agent.demo.js";
                        s.crossOrigin = "anonymous";
                        s.onload = () => resolve();
                        s.onerror = () => reject(new Error("Failed to load Page-Agent"));
                        document.head.appendChild(s);
                    }});
                    try {{ await loadScript(); }} catch(e) {{ return {{ error: e.message }}; }}
                }}
                if (!window.__pageAgentInstance) {{
                    window.__pageAgentInstance = new PageAgent({{
                        model: "qwen3.5-plus",
                        apiKey: "demo"
                    }});
                }}
                try {{
                    const res = await window.__pageAgentInstance.understand({json.dumps(extract_prompt)});
                    return {{ success: true, result: res }};
                }} catch(e) {{
                    return {{ error: e.message }};
                }}
            }})()
            """
            res = api_call("evaluate", {"code": js_extract})
            if "error" in res or not res.get("success"):
                res = {"success": True, "raw_text_preview": page_text[:2000], "note": "Alibaba Page-Agent fallback"}
        else:
            res = {"error": "Empty page"}
            
    elif tool_name == "scroll":
        direction = arguments.get("direction")
        amount = arguments.get("amount")
        selector = arguments.get("selector")
        x = arguments.get("x")
        y = arguments.get("y")
        
        if selector:
            res = api_call("scroll", {"selector": selector})
        elif direction or amount:
            js_calc = """
            (() => {
                return { height: window.innerHeight, width: window.innerWidth };
            })()
            """
            calc_res = api_call("evaluate", {"code": js_calc})
            dimensions = calc_res.get("result", {"height": 600, "width": 800})
            h = dimensions.get("height", 600)
            
            scroll_y = h if direction == "down" else -h
            if amount == "half":
                scroll_y = (h // 2) if direction == "down" else -(h // 2)
            res = api_call("scroll", {"x": 0, "y": scroll_y})
        else:
            res = api_call("scroll", {"x": x, "y": y})
            
    elif tool_name == "send_keys":
        res = api_call("pressKey", {"key": arguments.get("keys")})
        
    elif tool_name == "screenshot":
        res = api_call("screenshot", {"filename": arguments.get("name")})
        
    elif tool_name == "save_as_pdf":
        res = api_call("save-as-pdf", {"filename": arguments.get("name")})
        
    elif tool_name == "get_dropdown_options":
        sel_json = json.dumps(arguments.get("selector"))
        js_code = f"""
        (() => {{
            const el = document.querySelector({sel_json});
            if (!el) return {{ error: "Element not found" }};
            if (el.tagName.toLowerCase() === 'select') {{
                return {{ options: Array.from(el.options).map(o => ({{ text: o.text, value: o.value }})) }};
            }}
            const options = Array.from(el.querySelectorAll('[role="option"], option')).map(o => ({{
                text: o.innerText.trim(),
                value: o.getAttribute('value') || o.innerText.trim()
            }}));
            return {{ options }};
        }})()
        """
        res = api_call("evaluate", {"code": js_code})
    elif tool_name == "click":
        res = api_call("click", {"selector": arguments.get("selector")})
    elif tool_name == "type":
        res = api_call("fill", {"selector": arguments.get("selector"), "value": arguments.get("text")})
    elif tool_name == "hover":
        sel = json.dumps(arguments.get("selector"))
        js_code = f"""
        (() => {{
            const el = document.querySelector({sel});
            if (!el) return {{ error: "Element not found" }};
            el.dispatchEvent(new MouseEvent('mouseover', {{ bubbles: true }}));
            el.dispatchEvent(new MouseEvent('mouseenter', {{ bubbles: true }}));
            return {{ success: true }};
        }})()
        """
        res = api_call("evaluate", {"code": js_code})
    elif tool_name == "drag":
        sel = json.dumps(arguments.get("selector"))
        js_code = f"""
        (() => {{
            const el = document.querySelector({sel});
            if (!el) return {{ error: "Element not found" }};
            el.dispatchEvent(new DragEvent('dragstart', {{ bubbles: true }}));
            return {{ success: true }};
        }})()
        """
        res = api_call("evaluate", {"code": js_code})
    elif tool_name == "drop":
        sel = json.dumps(arguments.get("selector"))
        js_code = f"""
        (() => {{
            const el = document.querySelector({sel});
            if (!el) return {{ error: "Element not found" }};
            el.dispatchEvent(new DragEvent('dragover', {{ bubbles: true }}));
            el.dispatchEvent(new DragEvent('drop', {{ bubbles: true }}));
            return {{ success: true }};
        }})()
        """
        res = api_call("evaluate", {"code": js_code})
    elif tool_name == "download":
        import os
        from pathlib import Path
        down_dir = Path("data/downloads")
        files = []
        if down_dir.exists():
            files = [f.name for f in down_dir.iterdir() if f.is_file()]
        res = {"success": True, "downloads": files}
    elif tool_name == "upload":
        res = api_call("upload", {"selector": arguments.get("selector"), "file": arguments.get("file_path")})
    elif tool_name == "press":
        res = api_call("pressKey", {"key": arguments.get("key")})
    elif tool_name == "pdf":
        res = api_call("save-as-pdf", {"filename": arguments.get("name")})
    elif tool_name == "history":
        res = {"success": True, "history": COMMAND_HISTORY}
    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}
        }

    is_error = "error" in res
    text_content = json.dumps(res, indent=2) if not is_error else res["error"]
    
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": text_content
                }
            ],
            "isError": is_error
        }
    }

def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            if method == "initialize":
                resp = handle_initialize(req_id, params)
            elif method == "tools/list":
                resp = handle_list_tools(req_id)
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                resp = handle_call_tool(req_id, tool_name, arguments)
            elif method.startswith("notifications/"):
                continue
            else:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": str(e),
                    "data": traceback.format_exc()
                }
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
