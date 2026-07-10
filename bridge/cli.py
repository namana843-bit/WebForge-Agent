import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent
if project_root.name in ["Brain", "Browser", "Bridge", "bridge", "Memory", "Config"]:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))
for sub in ["Brain", "Browser", "Bridge", "bridge", "Memory", "Config"]:
    sys.path.insert(0, str(project_root / sub))

import argparse
import json
import os
from datetime import datetime

import urllib.request
import urllib.error

BRIDGE_URL = os.environ.get("WEBBRIDGE_URL", "http://127.0.0.1:10088")
SCREENSHOT_DIR = Path("Memory/data/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
PID_FILE = Path(__file__).parent / ".bridge.pid"


def api_call(action, args=None, raw=False):
    """Send command to bridge server."""
    payload = json.dumps({"action": action, "args": args or {}}).encode("utf-8")
    req = urllib.request.Request(
        f"{BRIDGE_URL}/command",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data if not raw else data
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {e.code}: {err}"}
    except urllib.error.URLError as e:
        return {"error": f"Connection failed: {e.reason}. Is the bridge server running?"}
    except Exception as e:
        return {"error": str(e)}


def cmd_status(args):
    try:
        req = urllib.request.Request(f"{BRIDGE_URL}/status")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"Running: {data.get('running', False)}")
            print(f"Extension connected: {data.get('extension_connected', False)}")
            print(f"Port: {data.get('port', '?')}")
    except urllib.error.URLError as e:
        print(f"Bridge: Connection failed ({e.reason})")
    except Exception as e:
        print(f"Bridge: {e}")


def cmd_navigate(args):
    resp = api_call("navigate", {"url": args.url, "newTab": args.new_tab})
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        print(f"OK: navigated to {resp.get('url', args.url)}")


def cmd_snapshot(args):
    resp = api_call("snapshot")
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        tree = resp.get("tree")
        if args.output:
            path = args.output
        else:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = f"snapshot_{ts}.json"
        Path(path).write_text(json.dumps(tree, indent=2, default=str), encoding="utf-8")
        print(f"Snapshot saved to {path}")
        if args.preview:
            _preview_snapshot(tree)


def _preview_snapshot(node, depth=0, max_depth=4):
    if depth > max_depth or not node:
        return
    tag = node.get("tag", "?")
    text = (node.get("text") or node.get("name") or "")[:60]
    ref = node.get("ref", "")
    interactive = node.get("interactive")
    visible = node.get("visible", True)
    prefix = "  " * depth
    marker = " [I]" if interactive else ""
    ref_str = f" @{ref}" if ref else ""
    vis_str = "" if visible else " [hidden]"
    label = f"{prefix}<{tag}>{vis_str}{ref_str} {text}"
    print(label)
    for child in node.get("children") or []:
        _preview_snapshot(child, depth + 1, max_depth)


def cmd_click(args):
    resp = api_call("click", {"selector": args.selector})
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        print(f"Clicked <{resp.get('tag', '?')}>: {resp.get('text', '')[:100]}")


def cmd_fill(args):
    resp = api_call("fill", {"selector": args.selector, "value": args.value})
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        print(f"Filled ({resp.get('mode', '?')})")


def cmd_find(args):
    resp = api_call("find", {"selector": args.selector})
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        els = resp.get("elements", [])
        print(f"Found {len(els)} element(s):")
        for i, el in enumerate(els):
            text = el.get("text", "")[:80]
            tag = el.get("tag", "?")
            vis = el.get("visible", False)
            print(f"  [{i}] <{tag}> visible={vis} \"{text}\"")


def cmd_text(args):
    resp = api_call("text", {"selector": args.selector})
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        for i, t in enumerate(resp.get("texts", [])):
            print(f"[{i}] {t}")


def cmd_screenshot(args):
    name = args.name
    if name and not name.endswith(".png"):
        name += ".png"
    resp = api_call("screenshot", {"filename": name} if name else {})
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        print(f"Screenshot saved to {resp['path']}")


def cmd_evaluate(args):
    code = " ".join(args.code)
    resp = api_call("evaluate", {"code": code})
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        result = resp.get("result")
        if isinstance(result, str):
            print(result)
        else:
            print(json.dumps(result, indent=2, default=str))


def cmd_html(args):
    resp = api_call("html", {"selector": args.selector} if args.selector else {})
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        html = resp.get("html", "")
        print(html[:2000] + ("..." if len(html) > 2000 else ""))


def cmd_attr(args):
    resp = api_call("attr", {"selector": args.selector, "attr": args.attr})
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        for i, v in enumerate(resp.get("values", [])):
            print(f"[{i}] {v}")


def cmd_scroll(args):
    resp = api_call("scroll", {
        "selector": args.selector,
        "x": args.x,
        "y": args.y,
    })
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        moved = resp.get("moved")
        if moved is not None:
            print(f"OK (moved {moved}px)")
        else:
            print("OK")


def cmd_auto_scroll(args):
    resp = api_call("auto_scroll", {
        "duration": args.duration,
        "step": args.step,
        "interval": 0.1,
    })
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        scrolled = resp.get("scrolled", 0)
        ended = resp.get("reachedEnd", False)
        print(f"Auto-scrolled {scrolled}px" + (" (reached end of page)" if ended else ""))


def cmd_url(args):
    resp = api_call("url")
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        print(resp.get("url", ""))


def cmd_title(args):
    resp = api_call("title")
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        print(resp.get("title", ""))


def cmd_find_tab(args):
    resp = api_call("find_tab", {"url": args.url})
    if "error" in resp:
        print(f"Error: {resp['error']}")
    elif resp.get("found"):
        print(f"Found tab: {resp.get('url', '')} (tabId: {resp.get('tabId')})")
    else:
        print(f"Created new tab: {resp.get('url', '')} (tabId: {resp.get('tabId')})")


def cmd_list_tabs(args):
    resp = api_call("list_tabs")
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        tabs = resp.get("tabs", [])
        print(f"Tabs ({len(tabs)}):")
        for t in tabs:
            active = " [ACTIVE]" if t.get("active") else ""
            url = (t.get("url") or "about:blank")[:80]
            print(f"  [{t['id']}]{active} {t.get('title', '')[:60]}")
            print(f"      {url}")


def cmd_close_tab(args):
    kwargs = {}
    if args.tab_id:
        kwargs["tabId"] = int(args.tab_id)
    resp = api_call("close_tab", kwargs)
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        print(f"Closed tab {resp.get('tabId')}")


def cmd_close_session(args):
    resp = api_call("close_session")
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        print(f"Closed {resp.get('closed', 0)} tab(s)")


def cmd_network(args):
    sub = args.subcommand
    if sub == "start":
        resp = api_call("network_start")
        if "error" in resp:
            print(f"Error: {resp['error']}")
        else:
            print("Network capture started")
    elif sub == "stop":
        resp = api_call("network_stop")
        if "error" in resp:
            print(f"Error: {resp['error']}")
        else:
            print(f"Network capture stopped ({resp.get('captured', 0)} requests captured)")
    elif sub == "list":
        resp = api_call("network_list")
        if "error" in resp:
            print(f"Error: {resp['error']}")
        else:
            reqs = resp.get("requests", [])
            active = resp.get("active", False)
            print(f"Network requests ({len(reqs)}):")
            for r in reqs:
                status = r.get("statusCode", "?")
                method = r.get("method", "?")
                url = (r.get("url", "")[:80])
                print(f"  [{r['id']}] {status} {method} {url}")
            if active:
                print("  (capture active)")
    elif sub == "detail":
        if not args.request_id:
            print("Error: --id required for detail")
            return
        resp = api_call("network_detail", {"requestId": args.request_id})
        if "error" in resp:
            print(f"Error: {resp['error']}")
        else:
            r = resp.get("request", {})
            print(json.dumps(r, indent=2, default=str))
    else:
        print(f"Unknown network subcommand: {sub}")


def cmd_upload(args):
    resp = api_call("upload", {
        "selector": args.selector,
        "filePath": args.file,
    })
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        print(f"Uploaded: {resp.get('fileName', '')}")


def cmd_save_as_pdf(args):
    kwargs = {}
    if args.name:
        kwargs["filename"] = args.name
    resp = api_call("save_as_pdf", kwargs)
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        note = resp.get("note", "")
        print(f"Saved to {resp.get('path')}")
        if note:
            print(f"Note: {note}")


def cmd_reload(args):
    resp = api_call("reload_extension")
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        print("Extension reload triggered. Reconnecting...")


def cmd_server(args):
    import subprocess
    sub = args.subcommand
    if sub == "start":
        script = Path(__file__).parent / "server.py"
        proc = subprocess.Popen(
            [sys.executable, str(script), "--log-file", "bridge.log"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        PID_FILE.write_text(str(proc.pid))
        print(f"Server started (PID: {proc.pid})")
    elif sub == "stop":
        stopped = False
        try:
            urllib.request.urlopen(
                urllib.request.Request(f"{BRIDGE_URL}/restart", method="POST"),
                timeout=3,
            )
            stopped = True
        except Exception:
            pass
        if PID_FILE.exists():
            try:
                raw = PID_FILE.read_bytes()
                pid = int(raw.strip())
                subprocess.run(
                    ["taskkill", "/f", "/pid", str(pid)],
                    capture_output=True, timeout=5,
                )
                PID_FILE.unlink(missing_ok=True)
                stopped = True
            except Exception:
                PID_FILE.unlink(missing_ok=True)
        if not stopped:
            print("Warning: could not stop server (may not be running)")
        else:
            print("Server stopped")
    elif sub == "restart":
        try:
            urllib.request.urlopen(
                urllib.request.Request(f"{BRIDGE_URL}/restart", method="POST"),
                timeout=3,
            )
        except Exception:
            pass
        print("Restart requested")
    elif sub == "logs":
        try:
            req = urllib.request.Request(f"{BRIDGE_URL}/logs")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                print(f"Logs: {data.get('note', '')}")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print(f"Unknown server subcommand: {sub}")


def cmd_extract(args):
    """Extract structured data using a JSON schema."""
    try:
        schema = json.loads(args.schema_json)
    except json.JSONDecodeError:
        print("Error: schema must be valid JSON")
        print('Example: {"title":"h1","prices":".price","links":"a::attr(href)"}')
        return

    result = {}
    for key, sel in schema.items():
        if isinstance(sel, str) and "::" in sel:
            parts = sel.split("::", 1)
            sel_base = parts[0]
            directive = parts[1]
            if directive.startswith("attr(") and directive.endswith(")"):
                attr_name = directive[5:-1]
                resp = api_call("attr", {"selector": sel_base, "attr": attr_name})
                result[key] = resp.get("values", [])
            else:
                resp = api_call("text", {"selector": sel_base})
                result[key] = resp.get("texts", [])
        else:
            resp = api_call("text", {"selector": sel})
            result[key] = resp.get("texts", [])

    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_send_whatsapp(args):
    resp = api_call("send_whatsapp", {"contact": args.contact, "message": args.message})
    if "error" in resp:
        print(f"Error: {resp['error']}")
    else:
        print(f"Sent to {resp.get('contact', args.contact)}: {resp.get('message', '')[:60]}")
        if resp.get('status'):
            print(f"Status: {resp['status']}")


def cmd_batch_send(args):
    import csv
    messages = []
    if args.file:
        with open(args.file, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                messages.append({"contact": (row.get("contact") or "").strip(), "message": (row.get("message") or "").strip()})
    if args.contact and args.message:
        messages.append({"contact": args.contact, "message": args.message})
    if not messages:
        print("Error: no messages to send. Provide --contact/--message or --file")
        return
    resp = api_call("batch_send", {"messages": messages}, raw=True)
    if "error" in resp:
        print(f"Error: {resp['error']}")
        return
    results = resp.get("results", [])
    print(f"Batch: {resp.get('sent', 0)}/{resp.get('total', len(messages))} sent")
    for i, r in enumerate(results):
        status = r.get("status", "?")
        contact = r.get("contact", "?")
        msg = r.get("message", "")[:40]
        err = r.get("error", "")
        line = f"  [{i+1}] {contact}: {msg} -> {status}"
        if err:
            line += f" (error: {err})"
        print(line)


def cmd_help(args):
    print("""WebBridge CLI - Browser control for opencode

Commands:
  status                    Check bridge & extension status
  navigate <url>            Navigate to URL
  find-tab <url>            Find existing tab or create new one
  list-tabs                 List all open tabs
  close-tab [--id N]        Close current or specified tab
  close-session             Close all tabs
  snapshot [--output FILE]  Get page accessibility tree
  click <selector>          Click element (CSS/XPath/@e ref)
  fill <selector> <value>   Fill input/textarea
  find <selector>           Find elements on page
  text <selector>           Extract text from elements
  attr <selector> <attr>    Extract attribute from elements
  screenshot [--name NAME]  Take page screenshot
  save-as-pdf [--name NAME] Save page as PDF (screenshot-based)
  evaluate <js-code>        Execute JavaScript in page
  html [selector]           Get page/element HTML
  scroll [selector] [--x X] [--y Y] Scroll page or element
  auto-scroll [--duration 5] [--step 300]  Auto-scroll page gradually
  url                       Get current URL
  title                     Get page title
  extract <json-schema>     Extract structured data
  upload <selector> <file>  Upload file to input element
  send-whatsapp <contact> <message>  Send WhatsApp message to contact
  network <sub> [options]   Network capture (start|stop|list|detail --id N)
  server <sub>              Server management (start|stop|restart|logs)
  help                      Show this help

Examples:
  python cli.py status
  python cli.py navigate https://binance.com
  python cli.py find-tab https://facebook.com
  python cli.py list-tabs
  python cli.py close-tab --id 123
  python cli.py snapshot --preview
  python cli.py click 'button.submit'
  python cli.py text 'h1, h2'
  python cli.py auto-scroll --duration 10
  python cli.py screenshot --name binance_home
  python cli.py evaluate 'document.title'
  python cli.py network start
  python cli.py network list
  python cli.py upload 'input[type=file]' ./photo.jpg
  python cli.py send-whatsapp "Pratik Mumbai" "Hello from WebBridge!"
  python cli.py extract '{"prices":".price","links":"a::attr(href)"}'""")


def main():
    parser = argparse.ArgumentParser(description="WebBridge CLI", add_help=False)
    parser.add_argument("command", nargs="?", default="help",
                        help="Command: status, navigate, find-tab, list-tabs, close-tab, close-session, snapshot, click, fill, find, text, screenshot, save-as-pdf, evaluate, html, attr, scroll, url, title, extract, upload, network, server, help")
    parser.add_argument("args", nargs=argparse.REMAINDER,
                        help="Command arguments")

    args, extra = parser.parse_known_args()
    cmd = args.command
    cmd_args = args.args

    # Map commands
    command_map = {
        "status": cmd_status,
        "navigate": cmd_navigate,
        "find-tab": cmd_find_tab,
        "list-tabs": cmd_list_tabs,
        "close-tab": cmd_close_tab,
        "close-session": cmd_close_session,
        "snapshot": cmd_snapshot,
        "click": cmd_click,
        "fill": cmd_fill,
        "find": cmd_find,
        "text": cmd_text,
        "screenshot": cmd_screenshot,
        "save-as-pdf": cmd_save_as_pdf,
        "evaluate": cmd_evaluate,
        "html": cmd_html,
        "attr": cmd_attr,
        "scroll": cmd_scroll,
        "auto-scroll": cmd_auto_scroll,
        "url": cmd_url,
        "title": cmd_title,
        "extract": cmd_extract,
        "upload": cmd_upload,
        "send-whatsapp": cmd_send_whatsapp,
        "batch-send": cmd_batch_send,
        "network": cmd_network,
        "server": cmd_server,
        "reload": cmd_reload,
        "help": cmd_help,
    }

    if cmd in command_map:
        subparser = argparse.ArgumentParser()
        if cmd == "navigate":
            subparser.add_argument("url")
            subparser.add_argument("--new-tab", action="store_true", default=True)
            subparser.add_argument("--same-tab", dest="new_tab", action="store_false")
        elif cmd == "find-tab":
            subparser.add_argument("url")
        elif cmd == "close-tab":
            subparser.add_argument("--id", dest="tab_id", default=None)
        elif cmd == "snapshot":
            subparser.add_argument("--output", "-o")
            subparser.add_argument("--preview", "-p", action="store_true")
        elif cmd == "auto-scroll":
            subparser.add_argument("--duration", type=float, default=5, help="Scroll duration in seconds")
            subparser.add_argument("--step", type=int, default=300, help="Pixels per scroll step")
        elif cmd in ("click", "find"):
            subparser.add_argument("selector")
        elif cmd == "scroll":
            subparser.add_argument("selector", nargs="?", default=None, help="Selector of the element to scroll to")
            subparser.add_argument("--x", type=int, default=None, help="Horizontal scroll offset (px)")
            subparser.add_argument("--y", type=int, default=None, help="Vertical scroll offset (px)")
        elif cmd == "fill":
            subparser.add_argument("selector")
            subparser.add_argument("value")
        elif cmd == "text":
            subparser.add_argument("selector")
        elif cmd in ("screenshot", "save-as-pdf"):
            subparser.add_argument("--name", "-n")
        elif cmd == "evaluate":
            subparser.add_argument("code", nargs="+")
        elif cmd == "html":
            subparser.add_argument("selector", nargs="?")
        elif cmd == "attr":
            subparser.add_argument("selector")
            subparser.add_argument("attr")
        elif cmd == "extract":
            subparser.add_argument("schema_json")
        elif cmd == "upload":
            subparser.add_argument("selector")
            subparser.add_argument("file")
        elif cmd == "send-whatsapp":
            subparser.add_argument("contact")
            subparser.add_argument("message")
        elif cmd == "batch-send":
            subparser.add_argument("--contact", default=None, help="Single contact to send to")
            subparser.add_argument("--message", default=None, help="Single message to send")
            subparser.add_argument("--file", "-f", default=None, help="CSV file with contact,message columns")
        elif cmd == "network":
            subparser.add_argument("subcommand", choices=["start", "stop", "list", "detail"])
            subparser.add_argument("--id", dest="request_id", default=None)
        elif cmd == "reload":
            pass
        elif cmd == "server":
            subparser.add_argument("subcommand", choices=["start", "stop", "restart", "logs"])
        sub_cfg = subparser.parse_args(cmd_args)
        command_map[cmd](sub_cfg)
    else:
        print(f"Unknown command: {cmd}")
        cmd_help(None)


if __name__ == "__main__":
    main()
