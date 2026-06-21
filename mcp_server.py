#!/usr/bin/env python3
"""WebBridge MCP Server - Exposes browser actions to external LLM clients."""

import sys
import json
import urllib.request
import urllib.error
import traceback

BRIDGE_URL = "http://127.0.0.1:10088"

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
    # Respond to MCP handshake
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
            "name": "navigate",
            "description": "Open a website/URL in Chrome.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to navigate to."}
                },
                "required": ["url"]
            }
        },
        {
            "name": "click",
            "description": "Click an element on the webpage.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector, XPath, or @e ref of the element to click."}
                },
                "required": ["selector"]
            }
        },
        {
            "name": "fill",
            "description": "Type text into a webpage input field.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector or @e ref of the input field."},
                    "value": {"type": "string", "description": "The text value to input."}
                },
                "required": ["selector", "value"]
            }
        },
        {
            "name": "scroll",
            "description": "Scroll the page or scroll to a specific element.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "Optional CSS selector to scroll to."},
                    "x": {"type": "integer", "description": "Optional horizontal pixel scroll offset."},
                    "y": {"type": "integer", "description": "Optional vertical pixel scroll offset."}
                }
            }
        },
        {
            "name": "auto_scroll",
            "description": "Gradually auto-scroll down the webpage.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "duration": {"type": "number", "description": "Scroll duration in seconds (default: 5)."},
                    "step": {"type": "integer", "description": "Pixels scrolled per step (default: 300)."}
                }
            }
        },
        {
            "name": "screenshot",
            "description": "Take a screenshot of the visible area of the active page.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Optional filename (e.g. page.png)."}
                }
            }
        },
        {
            "name": "get_snapshot",
            "description": "Get the simplified accessibility tree of the current webpage.",
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
    # Route tool execution to corresponding WebBridge API action
    res = None
    if tool_name == "navigate":
        res = api_call("navigate", {"url": arguments.get("url")})
    elif tool_name == "click":
        res = api_call("click", {"selector": arguments.get("selector")})
    elif tool_name == "fill":
        res = api_call("fill", {"selector": arguments.get("selector"), "value": arguments.get("value")})
    elif tool_name == "scroll":
        res = api_call("scroll", {
            "selector": arguments.get("selector"),
            "x": arguments.get("x"),
            "y": arguments.get("y")
        })
    elif tool_name == "auto_scroll":
        res = api_call("auto_scroll", {
            "duration": arguments.get("duration", 5),
            "step": arguments.get("step", 300)
        })
    elif tool_name == "screenshot":
        res = api_call("screenshot", {"filename": arguments.get("name")})
    elif tool_name == "get_snapshot":
        res = api_call("snapshot")
    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}
        }

    # Format result for MCP response
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
    # Loop on stdin to process incoming JSON-RPC requests
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            # Handle requests
            if method == "initialize":
                resp = handle_initialize(req_id, params)
            elif method == "tools/list":
                resp = handle_list_tools(req_id)
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                resp = handle_call_tool(req_id, tool_name, arguments)
            elif method.startswith("notifications/"):
                # Notifications do not require responses
                continue
            else:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }
            
            # Send response to stdout
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        except Exception as e:
            # Handle parsing or execution errors gracefully
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
