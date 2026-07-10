import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent
if project_root.name in ["Brain", "Browser", "Bridge", "bridge", "Memory", "Config"]:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))
for sub in ["Brain", "Browser", "Bridge", "bridge", "Memory", "Config"]:
    sys.path.insert(0, str(project_root / sub))

import asyncio
import json
import os
import base64
import re
import argparse
import logging
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse, quote

import websockets
from websockets.asyncio.server import serve

# --- Config ---
WS_PORT = 10087
HTTP_PORT = 10088
SCREENSHOT_DIR = Path("Memory/data/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
MAX_BODY_SIZE = 10 * 1024 * 1024
LOG_FILE: Optional[Path] = None

# --- State ---
extension_ws: Optional[Any] = None
extension_ws_lock = asyncio.Lock()
pending_requests: dict[str, asyncio.Future] = {}
request_id = 0

# --- Logger ---
log = logging.getLogger("webbridge")
log.setLevel(logging.DEBUG)
_ch = logging.StreamHandler()
_ch.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
log.addHandler(_ch)
_file_handler = None


def make_id() -> str:
    global request_id
    request_id += 1
    return str(request_id)


async def wait_for_extension(max_wait: float = 5) -> bool:
    async with extension_ws_lock:
        if extension_ws is not None:
            return True
    for _ in range(int(max_wait * 2)):
        await asyncio.sleep(0.5)
        async with extension_ws_lock:
            if extension_ws is not None:
                return True
    return False


async def send_to_extension(action: str, args: Optional[dict] = None, timeout: float = 30) -> dict:
    global extension_ws
    for attempt in range(5):
        ws: Optional[Any] = None
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
            pending_requests.pop(req_id, None)
            async with extension_ws_lock:
                if extension_ws is ws:
                    extension_ws = None
            if attempt < 4:
                log.warning("Connection lost, retrying (%d/5): %s", attempt + 1, e)
                await asyncio.sleep(1)
                continue
            raise ConnectionError(f"Extension not connected after retry: {e}")
        except asyncio.TimeoutError:
            pending_requests.pop(req_id, None)
            raise TimeoutError("Command timed out")
        except Exception as e:
            pending_requests.pop(req_id, None)
            raise e

    raise ConnectionError("Extension not connected")


# --- WebSocket Handler ---
async def handle_extension(websocket: Any) -> None:
    global extension_ws
    async with extension_ws_lock:
        extension_ws = websocket
    log.info("Extension connected")

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
                    log.warning("Unhandled message from extension: %s", msg.get("action"))
            except json.JSONDecodeError:
                log.error("Invalid JSON from extension: %s", raw[:200])
    except websockets.exceptions.ConnectionClosed:
        log.warning("Extension disconnected")
    finally:
        async with extension_ws_lock:
            if extension_ws is websocket:
                extension_ws = None
        for fid, future in pending_requests.items():
            if not future.done():
                future.set_exception(ConnectionError("Extension disconnected"))
        pending_requests.clear()


# --- HTTP Handler ---
async def handle_http(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    request_data = b""
    while True:
        line = await reader.readline()
        request_data += line
        if line == b"\r\n":
            break

    request_line = request_data.split(b"\r\n")[0].decode("utf-8", errors="replace")
    parts = request_line.split(" ")
    if len(parts) < 2:
        writer.close()
        return

    method = parts[0].upper()
    path = parts[1]

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
                body = await asyncio.wait_for(reader.readexactly(content_length), timeout=30)
            except (asyncio.TimeoutError, asyncio.IncompleteReadError):
                await json_response(writer, {"error": "Incomplete request body"}, 400)
                writer.close()
                return

    parsed = urlparse(path)
    route = parsed.path.rstrip("/")

    try:
        if route == "/command" and method == "POST":
            params = json.loads(body.decode("utf-8"))
            action = params.get("action")
            args = params.get("args", {})
            result = await handle_command(action, args)
            await json_response(writer, result)

        elif route in ("/status", "/health"):
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
            log.warning("Restart requested via API")
            await json_response(writer, {"success": True, "message": "Restarting..."})
            asyncio.get_event_loop().call_later(0.5, lambda: os._exit(0))

        else:
            await json_response(writer, {"error": f"Not found: {method} {route}"}, 404)

    except json.JSONDecodeError:
        await json_response(writer, {"error": "Invalid JSON in request body"}, 400)
    except Exception as e:
        log.error("HTTP error: %s", e)
        await json_response(writer, {"error": str(e)}, 500)

    writer.close()


async def json_response(writer: asyncio.StreamWriter, data: dict, status: int = 200) -> None:
    body = json.dumps(data).encode("utf-8")
    status_text = "OK" if status == 200 else "Error"
    resp = (
        f"HTTP/1.1 {status} {status_text}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Access-Control-Allow-Origin: *\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("utf-8") + body
    writer.write(resp)
    await writer.drain()


# --- Command Handlers ---
async def _extract_result(result: dict, *keys: str) -> dict:
    """Return result dict ensuring extension errors are propagated."""
    if "error" in result:
        return {"error": result["error"]}
    out = {"success": True}
    for k in keys:
        out[k] = result.get(k)
    return out


async def send_whatsapp(args: dict, opts: dict) -> dict:
    contact = args.get("contact", "")
    message = args.get("message", "")
    same_contact = opts.get("same_contact", False)
    index = opts.get("index")
    total = opts.get("total")
    prefix = f"[{index+1}/{total}] " if index is not None else ""

    if not contact or not message:
        return {"error": "contact and message are required"}

    digits = re.sub(r"\D", "", contact)
    if len(digits) >= 10:
        if len(digits) == 10:
            digits = "91" + digits
        phone = digits
    else:
        phone = contact

    tabs_result = await send_to_extension("list_tabs")
    wa_tabs = [t for t in (tabs_result.get("tabs") or []) if (t.get("url") or "").lower().startswith("https://web.whatsapp.com/")]

    if not wa_tabs:
        log.info("%sNo WA tab, creating one", prefix)
        await send_to_extension("navigate", {"url": "https://web.whatsapp.com", "newTab": True})
        await asyncio.sleep(12)
        same_contact = False
    else:
        active = next((t for t in wa_tabs if t.get("active")), wa_tabs[0])
        wid = active.get("id")
        if not active.get("active"):
            await send_to_extension("find_tab", {"url": active.get("url", "web.whatsapp.com")})
        log.info("%sUsing WA tab %s", prefix, wid)

    if same_contact:
        result = await send_to_extension("wa_sendText", {"text": message}, timeout=10)
        if result.get("success"):
            return {"success": True, "status": "sent", "mode": result.get("mode", "?"), "contact": contact, "message": message[:50]}
        log.warning("Fast send failed, switching contact")

    await send_to_extension("wa_startChat", {"phone": phone}, timeout=10)
    await asyncio.sleep(2)

    for _ in range(8):
        r = await send_to_extension("wa_clickResult", timeout=5)
        if r.get("success"):
            break
        await asyncio.sleep(0.5)

    await asyncio.sleep(3)

    result = await send_to_extension("wa_sendText", {"text": message}, timeout=10)
    if result.get("success"):
        return {"success": True, "status": "sent", "mode": result.get("mode", "?"), "contact": contact, "message": message[:50]}

    for i in range(20):
        await asyncio.sleep(0.25)
        r = await send_to_extension("click", {"selector": 'button[aria-label="Send"]'})
        if r.get("success"):
            return {"success": True, "status": "sent", "contact": contact, "message": message[:50]}

    return {"success": True, "status": "navigated_need_send", "note": "Could not send", "contact": contact, "message": message[:50]}


async def handle_command(action: str, args: dict) -> dict:
    log.info("Command: %s %s", action, json.dumps(args)[:100])

    try:
        if action == "navigate":
            result = await send_to_extension("navigate", {"url": args["url"], "newTab": args.get("newTab", True)})
            return await _extract_result(result, "url")

        elif action == "snapshot":
            result = await send_to_extension("snapshot")
            return await _extract_result(result, "tree")

        elif action == "click":
            result = await send_to_extension("click", {"selector": args.get("selector")})
            return await _extract_result(result, "tag", "text")

        elif action == "fill":
            result = await send_to_extension("fill", {"selector": args.get("selector"), "value": args.get("value")})
            return await _extract_result(result, "mode")

        elif action == "screenshot":
            result = await send_to_extension("screenshot", {"format": args.get("format", "png"), "quality": args.get("quality", 80)})
            img_data = result.get("data", "")
            if "error" in result and not img_data:
                return {"error": result["error"]}
            if img_data:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fname = args.get("filename") or f"screenshot_{ts}.png"
                if not fname.lower().endswith((".png", ".jpeg", ".jpg")):
                    fname += ".png"
                fpath = SCREENSHOT_DIR / fname
                fpath.write_bytes(base64.b64decode(img_data))
                return {"success": True, "path": str(fpath)}
            return {"error": "No screenshot data"}

        elif action == "evaluate":
            result = await send_to_extension("evaluate", {"code": args.get("code", "")})
            return await _extract_result(result, "result")

        elif action == "find":
            result = await send_to_extension("find", {"selector": args.get("selector")})
            return await _extract_result(result, "elements")

        elif action == "text":
            result = await send_to_extension("text", {"selector": args.get("selector")})
            return await _extract_result(result, "texts")

        elif action == "html":
            result = await send_to_extension("html", {"selector": args.get("selector")})
            return await _extract_result(result, "html")

        elif action == "scroll":
            result = await send_to_extension("scroll", {
                "selector": args.get("selector"), "x": args.get("x"), "y": args.get("y"),
            })
            return await _extract_result(result, "mode", "top", "moved")

        elif action == "auto_scroll":
            result = await send_to_extension("auto_scroll", {
                "duration": args.get("duration", 5), "step": args.get("step", 300), "interval": args.get("interval", 0.1),
            })
            return await _extract_result(result, "scrolled", "reachedEnd")

        elif action == "attr":
            result = await send_to_extension("attr", {"selector": args.get("selector"), "attr": args.get("attr")})
            return await _extract_result(result, "values")

        elif action == "url":
            result = await send_to_extension("url")
            return await _extract_result(result, "url")

        elif action == "title":
            result = await send_to_extension("title")
            return await _extract_result(result, "title")

        elif action == "find_tab":
            result = await send_to_extension("find_tab", {"url": args.get("url", "")})
            return await _extract_result(result, "found", "tabId", "url")

        elif action == "list_tabs":
            result = await send_to_extension("list_tabs")
            return await _extract_result(result, "tabs", "count")

        elif action == "close_tab":
            result = await send_to_extension("close_tab", {"tabId": args.get("tabId")})
            return await _extract_result(result, "tabId")

        elif action == "close_session":
            result = await send_to_extension("close_session")
            return await _extract_result(result, "closed")

        elif action == "network_start":
            result = await send_to_extension("network_start")
            return await _extract_result(result, "active")

        elif action == "network_stop":
            result = await send_to_extension("network_stop")
            return await _extract_result(result, "captured")

        elif action == "network_list":
            result = await send_to_extension("network_list")
            return await _extract_result(result, "requests", "count", "active")

        elif action == "network_detail":
            result = await send_to_extension("network_detail", {"requestId": args.get("requestId")})
            return await _extract_result(result, "request")

        elif action == "upload":
            result = await send_to_extension("upload", {
                "selector": args.get("selector"), "filePath": args.get("filePath"),
                "fileData": args.get("fileData"), "fileName": args.get("fileName"),
            })
            return await _extract_result(result, "fileName")

        elif action == "highlight":
            result = await send_to_extension("highlight", {"selector": args.get("selector"), "color": args.get("color", "#22c55e"), "duration": args.get("duration", 0), "scrollIntoView": args.get("scrollIntoView", False), "maxElements": args.get("maxElements", 20)})
            return await _extract_result(result, "elements", "count")

        elif action == "clear_highlight":
            result = await send_to_extension("clear_highlight", {})
            return await _extract_result(result, "cleared")

        elif action == "save_as_pdf":
            result = await send_to_extension("save_as_pdf")
            img_data = result.get("data", "")
            if "error" in result and not img_data:
                return {"error": result["error"]}
            if img_data:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fname = args.get("filename") or f"page_{ts}.png"
                if not fname.lower().endswith((".png", ".jpeg", ".jpg")):
                    fname += ".png"
                fpath = SCREENSHOT_DIR / fname
                fpath.write_bytes(base64.b64decode(img_data))
                return {"success": True, "path": str(fpath), "note": "screenshot-based PDF"}
            return {"error": "No data"}

        elif action == "reload_extension":
            result = await send_to_extension("reload_extension")
            return {"success": True, "message": "Extension reload triggered"}

        elif action == "send_whatsapp":
            return await send_whatsapp(args, {})

        elif action == "batch_send":
            messages = args.get("messages", [])
            if not messages:
                return {"error": "messages list is required"}
            results = []
            last_contact = None
            for i, item in enumerate(messages):
                contact = item.get("contact", "")
                message = item.get("message", "")
                if not contact or not message:
                    results.append({"index": i, "error": "contact and message required"})
                    continue
                is_same = contact == last_contact
                r = await send_whatsapp({"contact": contact, "message": message}, {"same_contact": is_same, "index": i, "total": len(messages)})
                results.append(r)
                last_contact = contact
            sent = sum(1 for r in results if r.get("status") in ("sent", "sent_via_enter"))
            return {"success": True, "sent": sent, "total": len(messages), "results": results}

        else:
            return {"error": f"Unknown action: {action}"}

    except Exception as e:
        log.error("Command %s failed: %s", action, e)
        return {"error": str(e)}


# --- Server Runners ---
async def run_http_server() -> None:
    server = await asyncio.start_server(handle_http, "127.0.0.1", HTTP_PORT)
    log.info("HTTP server on http://127.0.0.1:%d", HTTP_PORT)
    async with server:
        await server.serve_forever()


async def main() -> None:
    global LOG_FILE, WS_PORT, HTTP_PORT, _file_handler

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
        _file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
        _file_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
        log.addHandler(_file_handler)

    log.info("Starting WebBridge server...")
    log.info("WS port: %d, HTTP port: %d", WS_PORT, HTTP_PORT)

    ws_server = await serve(handle_extension, "127.0.0.1", WS_PORT)
    log.info("WebSocket server on ws://127.0.0.1:%d", WS_PORT)

    await asyncio.gather(
        ws_server.serve_forever(),
        run_http_server(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutting down")
