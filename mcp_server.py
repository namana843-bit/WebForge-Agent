#!/usr/bin/env python3
"""WebBridge MCP Server - Exposes browser actions to external LLM clients."""

import sys
import json
import time
import urllib.request
import urllib.error
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
            "name": "scroll",
            "description": "Scroll the active page.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "Horizontal scroll offset."},
                    "y": {"type": "integer", "description": "Vertical scroll offset."}
                }
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
            "name": "navigate",
            "description": "Navigate to target web URL.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Web URL to open."}
                },
                "required": ["url"]
            }
        },
        {
            "name": "wait",
            "description": "Delay/wait execution for a number of seconds.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "number", "description": "Seconds to delay."}
                },
                "required": ["seconds"]
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
            "name": "extract",
            "description": "Extract data using JSON schema extraction.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "schema": {"type": "object", "description": "JSON schema layout map."}
                },
                "required": ["schema"]
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
    if tool_name == "navigate":
        res = api_call("navigate", {"url": arguments.get("url")})
    elif tool_name == "click":
        res = api_call("click", {"selector": arguments.get("selector")})
    elif tool_name == "type":
        res = api_call("fill", {"selector": arguments.get("selector"), "value": arguments.get("text")})
    elif tool_name == "hover":
        # Dispatch mouse events via JS evaluate
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
    elif tool_name == "scroll":
        res = api_call("scroll", {"x": arguments.get("x"), "y": arguments.get("y")})
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
    elif tool_name == "wait":
        secs = float(arguments.get("seconds", 1.0))
        time.sleep(secs)
        res = {"success": True, "waited": secs}
    elif tool_name == "screenshot":
        res = api_call("screenshot", {"filename": arguments.get("name")})
    elif tool_name == "extract":
        res = api_call("extract", {"schema": arguments.get("schema")})
    elif tool_name == "pdf":
        res = api_call("save-as-pdf", {"filename": arguments.get("name")})
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
