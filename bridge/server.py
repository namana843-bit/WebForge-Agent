import asyncio
import json
import os
import sys
import base64
import argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import websockets
from websockets.asyncio.server import serve

# --- Configuration ---
WS_PORT = 10087
HTTP_PORT = 10088
SCREENSHOT_DIR = Path("data/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = None
MAX_BODY_SIZE = 10 * 1024 * 1024  # 10MB max POST body

# --- State ---
extension_ws = None
extension_ws_lock = asyncio.Lock()
pending_requests = {}
request_id = 0

# --- Helpers ---
def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    if LOG_FILE:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as e:
            print(f"[{ts}] Failed to write log: {e}", flush=True)

def make_id():
    global request_id
    request_id += 1
    return str(request_id)

async def wait_for_extension(max_wait=5):
    async with extension_ws_lock:
        if extension_ws is not None:
            return True
    for _ in range(int(max_wait * 2)):
        await asyncio.sleep(0.5)
        async with extension_ws_lock:
            if extension_ws is not None:
                return True
    return False

async def send_to_extension(action, args=None, timeout=30):
    global extension_ws
    for attempt in range(5):
        ws = None
        async with extension_ws_lock:
            ws = extension_ws

        if ws is None:
            if not await wait_for_extension(5):
                if attempt < 4:
                    await asyncio.sleep(1)
                    continue
                raise ConnectionError("Extension not connected after retry")

        req_id = make_id()
        future = asyncio.get_event_loop().create_future()
        pending_requests[req_id] = future

        try:
            await ws.send(json.dumps({
                "id": req_id,
                "action": action,
                "args": args or {},
            }))
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except (websockets.exceptions.ConnectionClosed) as e:
            if req_id in pending_requests:
                del pending_requests[req_id]
            async with extension_ws_lock:
                if extension_ws is ws:
                    extension_ws = None
            if attempt < 4:
                log(f"Connection lost, retrying ({attempt+1}/5): {e}")
                await asyncio.sleep(1)
                continue
            raise ConnectionError(f"Extension not connected after retry: {e}")
        except asyncio.TimeoutError:
            del pending_requests[req_id]
            raise TimeoutError("Command timed out")
        except Exception as e:
            if req_id in pending_requests:
                del pending_requests[req_id]
            raise e

    raise ConnectionError("Extension not connected")

# --- WebSocket Handler (Extension → Server) ---
async def handle_extension(websocket):
    global extension_ws
    async with extension_ws_lock:
        extension_ws = websocket
    log("Extension connected")

    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
                if msg.get("type") == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))
                    continue
                req_id = msg.get("id")
                if req_id and req_id in pending_requests:
                    pending_requests[req_id].set_result(msg)
                elif msg.get("action"):
                    log(f"Unhandled message from extension: {msg.get('action')}")
            except json.JSONDecodeError:
                log(f"Invalid JSON from extension: {raw[:200]}")
    except websockets.exceptions.ConnectionClosed:
        log("Extension disconnected")
    finally:
        async with extension_ws_lock:
            if extension_ws is websocket:
                extension_ws = None
        for fid, future in pending_requests.items():
            if not future.done():
                future.set_exception(ConnectionError("Extension disconnected"))
        pending_requests.clear()

# --- HTTP Handler (CLI / Opencode) ---
async def handle_http(reader, writer):
    request_data = b""
    while True:
        line = await reader.readline()
        request_data += line
        if line == b"\r\n":
            break

    # Parse request line
    request_line = request_data.split(b"\r\n")[0].decode("utf-8", errors="replace")
    parts = request_line.split(" ")
    if len(parts) < 2:
        writer.close()
        return

    method = parts[0]
    path = parts[1]

    # Read body for POST (with size and timeout limits)
    body = b""
    if method == "POST":
        content_length = 0
        for line in request_data.split(b"\r\n"):
            if line.lower().startswith(b"content-length:"):
                try:
                    content_length = int(line.split(b":")[1].strip())
                except (ValueError, IndexError):
                    content_length = 0
        if content_length > 0:
            if content_length > MAX_BODY_SIZE:
                await json_response(writer, {"error": "Request body too large"}, 413)
                writer.close()
                return
            try:
                body = await asyncio.wait_for(
                    reader.readexactly(content_length),
                    timeout=30,
                )
            except (asyncio.TimeoutError, asyncio.IncompleteReadError):
                await json_response(writer, {"error": "Incomplete request body"}, 400)
                writer.close()
                return

    # Route
    parsed = urlparse(path)
    route = parsed.path.rstrip("/")

    try:
        if route == "/command" and method == "POST":
            params = json.loads(body.decode("utf-8"))
            action = params.get("action")
            args = params.get("args", {})
            result = await handle_command(action, args)
            await json_response(writer, result)

        elif route == "/status" or route == "/health":
            await json_response(writer, {
                "running": True,
                "extension_connected": extension_ws is not None,
                "port": WS_PORT,
                "http_port": HTTP_PORT,
                "screenshot_dir": str(SCREENSHOT_DIR),
            })

        elif route == "/screenshot" and method == "POST":
            params = json.loads(body.decode("utf-8"))
            result = await handle_command("screenshot", params.get("args", {}))
            await json_response(writer, result)

        elif route == "/logs":
            await json_response(writer, {
                "note": "Server logs are written to stdout. Use --log-file to capture to file.",
                "level": "info",
            })

        elif route == "/restart" and method == "POST":
            log("Restart requested via API")
            await json_response(writer, {"success": True, "message": "Restarting..."})
            # Schedule restart in background
            asyncio.get_event_loop().call_later(0.5, lambda: os._exit(0))

        else:
            await json_response(writer, {"error": "Not found"}, 404)
    except Exception as e:
        await json_response(writer, {"error": str(e)}, 500)

    writer.close()

async def json_response(writer, data, status=200):
    body = json.dumps(data).encode("utf-8")
    resp = (
        f"HTTP/1.1 {status} {'OK' if status == 200 else 'Error'}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Access-Control-Allow-Origin: *\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("utf-8") + body
    writer.write(resp)
    await writer.drain()

# --- Commands ---
async def handle_command(action, args):
    log(f"Command: {action} {json.dumps(args)[:100]}")

    if action == "navigate":
        url = args.get("url")
        new_tab = args.get("newTab", True)
        result = await send_to_extension("navigate", {"url": url, "newTab": new_tab})
        return {"success": True, "url": url}

    elif action == "snapshot":
        # Get page snapshot via extension
        result = await send_to_extension("snapshot")
        return {"success": True, "tree": result.get("tree")}

    elif action == "click":
        selector = args.get("selector")
        result = await send_to_extension("click", {"selector": selector})
        return {"success": True, "tag": result.get("tag"), "text": result.get("text")}

    elif action == "fill":
        selector = args.get("selector")
        value = args.get("value")
        result = await send_to_extension("fill", {"selector": selector, "value": value})
        return {"success": True, "mode": result.get("mode")}

    elif action == "screenshot":
        # Send screenshot command to extension
        result = await send_to_extension("screenshot", args or {})
        img_data = result.get("data", "")
        if img_data:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = args.get("filename") or f"screenshot_{ts}.png"
            if not fname.endswith(".png") and not fname.endswith(".jpeg") and not fname.endswith(".jpg"):
                fname += ".png"
            fpath = SCREENSHOT_DIR / fname
            fpath.write_bytes(base64.b64decode(img_data))
            return {"success": True, "path": str(fpath)}
        return {"error": "No screenshot data"}

    elif action == "evaluate":
        code = args.get("code")
        result = await send_to_extension("evaluate", {"code": code})
        return {"success": True, "result": result.get("result")}

    elif action == "find":
        selector = args.get("selector")
        result = await send_to_extension("find", {"selector": selector})
        return {"success": True, "elements": result.get("elements", [])}

    elif action == "text":
        selector = args.get("selector")
        result = await send_to_extension("text", {"selector": selector})
        return {"success": True, "texts": result.get("texts", [])}

    elif action == "html":
        selector = args.get("selector")
        result = await send_to_extension("html", {"selector": selector})
        return {"success": True, "html": result.get("html")}

    elif action == "scroll":
        result = await send_to_extension("scroll", {
            "selector": args.get("selector"),
            "x": args.get("x"),
            "y": args.get("y"),
        })
        return {"success": True, "mode": result.get("mode"), "top": result.get("top"), "moved": result.get("moved")}

    elif action == "auto_scroll":
        result = await send_to_extension("auto_scroll", {
            "duration": args.get("duration", 5),
            "step": args.get("step", 300),
            "interval": args.get("interval", 0.1),
        })
        return {"success": True, "scrolled": result.get("scrolled", 0), "reachedEnd": result.get("reachedEnd", False)}

    elif action == "attr":
        selector = args.get("selector")
        attr = args.get("attr")
        result = await send_to_extension("attr", {"selector": selector, "attr": attr})
        return {"success": True, "values": result.get("values", [])}

    elif action == "url":
        result = await send_to_extension("url")
        return {"success": True, "url": result.get("url")}

    elif action == "title":
        result = await send_to_extension("title")
        return {"success": True, "title": result.get("title")}

    elif action == "find_tab":
        result = await send_to_extension("find_tab", {"url": args.get("url", "")})
        return {"success": True, "found": result.get("found"), "tabId": result.get("tabId"), "url": result.get("url")}

    elif action == "list_tabs":
        result = await send_to_extension("list_tabs")
        return {"success": True, "tabs": result.get("tabs", []), "count": result.get("count", 0)}

    elif action == "close_tab":
        result = await send_to_extension("close_tab", {"tabId": args.get("tabId")})
        return {"success": True, "tabId": result.get("tabId")}

    elif action == "close_session":
        result = await send_to_extension("close_session")
        return {"success": True, "closed": result.get("closed", 0)}

    elif action == "network_start":
        result = await send_to_extension("network_start")
        return {"success": True, "active": result.get("active")}

    elif action == "network_stop":
        result = await send_to_extension("network_stop")
        return {"success": True, "captured": result.get("captured", 0)}

    elif action == "network_list":
        result = await send_to_extension("network_list")
        return {"success": True, "requests": result.get("requests", []), "count": result.get("count", 0), "active": result.get("active")}

    elif action == "network_detail":
        result = await send_to_extension("network_detail", {"requestId": args.get("requestId")})
        return {"success": True, "request": result.get("request")}

    elif action == "upload":
        result = await send_to_extension("upload", {
            "selector": args.get("selector"),
            "filePath": args.get("filePath"),
            "fileData": args.get("fileData"),
            "fileName": args.get("fileName"),
        })
        return {"success": True, "fileName": result.get("fileName")}

    elif action == "save_as_pdf":
        result = await send_to_extension("save_as_pdf")
        img_data = result.get("data", "")
        if img_data:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = args.get("filename") or f"page_{ts}.png"
            if not fname.endswith(".png") and not fname.endswith(".jpeg") and not fname.endswith(".jpg"):
                fname += ".png"
            fpath = SCREENSHOT_DIR / fname
            fpath.write_bytes(base64.b64decode(img_data))
            return {"success": True, "path": str(fpath), "note": "screenshot-based PDF"}
        return {"error": "No data"}

    else:
        return {"error": f"Unknown action: {action}"}

# --- HTTP Server Runner ---
async def run_http_server():
    server = await asyncio.start_server(handle_http, "127.0.0.1", HTTP_PORT)
    log(f"HTTP server on http://127.0.0.1:{HTTP_PORT}")
    async with server:
        await server.serve_forever()

# --- Main ---
async def main():
    global LOG_FILE, WS_PORT, HTTP_PORT
    parser = argparse.ArgumentParser(description="WebBridge Server")
    parser.add_argument("--ws-port", type=int, default=WS_PORT)
    parser.add_argument("--http-port", type=int, default=HTTP_PORT)
    parser.add_argument("--log-file", type=str, default=None, help="File to write logs to")
    args = parser.parse_args()

    WS_PORT = args.ws_port
    HTTP_PORT = args.http_port
    if args.log_file:
        LOG_FILE = Path(args.log_file)
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    log(f"Starting WebBridge server...")
    log(f"WS port: {WS_PORT}, HTTP port: {HTTP_PORT}")

    ws_server = await serve(handle_extension, "127.0.0.1", WS_PORT)
    log(f"WebSocket server on ws://127.0.0.1:{WS_PORT}")

    # Run both servers concurrently
    await asyncio.gather(
        ws_server.serve_forever(),
        run_http_server(),
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("Shutting down")
