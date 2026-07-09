#!/usr/bin/env python3
"""Opencode Browser Agent Client - direct scripting and automation with Alibaba Page-Agent."""

import json
import urllib.request
import urllib.error
import time
import os
import re
from pathlib import Path
from plugin_interface import BrowserPlugin
from router import PluginRouter
from reasoning import ReasoningEngine
from desktop_plugin import DesktopPlugin
from form_handler import FormHandlerPlugin
from visual_enhancements import VisualEnhancementsPlugin
from data_exporter import DataExporterPlugin
from crawler import CrawlerPlugin
from accessibility_plugin import AccessibilityPlugin

class BridgePlugin(BrowserPlugin):
    """Plugin to communicate with the low-level Chrome extension bridge."""

    def __init__(self, agent):
        self.agent = agent

    def execute(self, action: str, **kwargs):
        payload = json.dumps({"action": action, "args": kwargs}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.agent.bridge_url}/command",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            return {"error": f"Connection failed: {e.reason}. Is the bridge server running?"}
        except Exception as e:
            return {"error": str(e)}

    def navigate(self, url: str, new_tab: bool = False):
        print(f"Navigating to {url}...")
        return self.execute("navigate", url=url, newTab=new_tab)

    def click(self, selector: str):
        print(f"Clicking element: {selector}")
        return self.execute("click", selector=selector)

    def fill(self, selector: str, value: str):
        print(f"Filling element {selector} with '{value}'...")
        return self.execute("fill", selector=selector, value=value)

    def get_snapshot(self):
        return self.execute("snapshot")

    def screenshot(self, filename: str):
        return self.execute("screenshot", filename=filename)

    def scroll(self, selector=None, x=None, y=None):
        return self.execute("scroll", selector=selector, x=x, y=y)

class BrowserAgent:
    """Orchestrator class coordinating plugins for browser automation and intelligence."""

    def __init__(self, bridge_url="http://127.0.0.1:10088"):
        self.bridge_url = bridge_url
        self.screenshot_dir = Path("data/screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Plugins registration
        self.bridge = BridgePlugin(self)
        
        # Plugin Router
        self.router = PluginRouter()
        self.router.register_plugin("bridge", self.bridge)
        
        # Desktop plugin
        self.desktop = DesktopPlugin(self)
        self.router.register_plugin("desktop", self.desktop)
        
        # Form Handler plugin
        self.form = FormHandlerPlugin(self)
        self.router.register_plugin("form", self.form)
        
        # Visual Enhancements plugin
        self.visual = VisualEnhancementsPlugin(self)
        self.router.register_plugin("visual", self.visual)
        
        # Data Exporter plugin
        self.exporter = DataExporterPlugin(self)
        self.router.register_plugin("exporter", self.exporter)
        
        # Crawler plugin
        self.crawler = CrawlerPlugin(self)
        self.router.register_plugin("crawler", self.crawler)
        
        # Accessibility plugin
        self.accessibility = AccessibilityPlugin(self)
        self.router.register_plugin("accessibility", self.accessibility)
        
        # Reasoning Engine
        self.reasoning = ReasoningEngine(self.router)

    def run_goal(self, goal: str, **kwargs):
        """Invoke the Reasoning Engine to achieve a high-level goal."""
        return self.reasoning.run_goal(goal, **kwargs)

    # --- Backward compatibility delegation to BridgePlugin ---

    def navigate(self, url, new_tab=False):
        """Navigate to a URL."""
        return self.bridge.navigate(url, new_tab)

    def click(self, selector):
        """Click an element using CSS selector, XPath, or snapshot @e reference."""
        return self.bridge.click(selector)

    def fill(self, selector, value):
        """Fill an input field with a value."""
        return self.bridge.fill(selector, value)

    def get_snapshot(self):
        """Get the page's accessibility tree representation."""
        return self.bridge.get_snapshot()

    def screenshot(self, name=None):
        """Take a page screenshot and save it to data/screenshots."""
        if not name:
            name = f"screenshot_{int(time.time())}.png"
        if not name.endswith(".png"):
            name += ".png"
        resp = self.bridge.screenshot(name)
        if "error" in resp:
            print(f"Screenshot Error: {resp['error']}")
        else:
            print(f"Screenshot saved successfully to {resp.get('path')}")
        return resp

    def scroll(self, selector=None, x=None, y=None):
        """Scroll page or scroll to element."""
        return self.bridge.scroll(selector, x, y)

    def scroll_and_screenshot(self, scroll_steps=3, step_size=500, delay=1.0):
        """Scrolls the page incrementally and captures a screenshot at each step."""
        print(f"Starting scroll-and-screenshot sequence ({scroll_steps} steps of {step_size}px)...")
        results = []
        base_name = f"scroll_seq_{int(time.time())}"
        
        for step in range(1, scroll_steps + 1):
            name = f"{base_name}_step_{step}.png"
            print(f"\n--- Step {step}/{scroll_steps} ---")
            
            # Take screenshot of current position
            res_screenshot = self.screenshot(name)
            results.append({"step": step, "type": "screenshot", "response": res_screenshot})
            
            if step < scroll_steps:
                # Scroll down
                print(f"Scrolling down {step_size}px...")
                res_scroll = self.scroll(y=step_size)
                results.append({"step": step, "type": "scroll", "response": res_scroll})
                
                # Wait for page layout/animations to settle
                time.sleep(delay)
                
        print("\nScroll-and-screenshot sequence completed.")
        return results

    def scrape(self, instruction: str, output_file: str = None):
        """Takes a screenshot, extracts target data from the page using Page-Agent, and saves it to a JSON file."""
        print(f"Starting visual scrape for: '{instruction}'...")
        
        # 1. Take a screenshot
        ts = int(time.time())
        screenshot_name = f"scrape_view_{ts}.png"
        screenshot_res = self.screenshot(screenshot_name)
        
        # 2. Query Page-Agent to extract the requested data
        prompt = (
            f"Based on the page layout, extract the data requested: '{instruction}'. "
            "Please return ONLY a valid JSON object containing the extracted data. Do not include markdown code block formatting (like ```json) or any conversational text."
        )
        print("Querying Page-Agent to extract data...")
        understand_res = self.page_agent.understand(prompt)
        
        # Extract the content from the understand response
        extracted_text = ""
        if isinstance(understand_res, dict) and "result" in understand_res:
            extracted_text = understand_res["result"]
        elif isinstance(understand_res, str):
            extracted_text = understand_res
            
        print(f"Extracted response: {extracted_text}")
        
        # Try to parse the JSON
        cleaned_text = extracted_text.strip()
        if cleaned_text.startswith("```"):
            cleaned_text = re.sub(r"^```(?:json)?\n", "", cleaned_text)
            cleaned_text = re.sub(r"\n```$", "", cleaned_text)
            cleaned_text = cleaned_text.strip()
            
        try:
            data = json.loads(cleaned_text)
        except Exception as e:
            print(f"Warning: Failed to parse directly as JSON: {e}. Saving raw string inside JSON wrapper.")
            data = {"raw_extracted_text": extracted_text, "parse_error": str(e)}
            
        # 3. Save to JSON file
        if not output_file:
            output_dir = Path("data/scraped")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"scraped_{ts}.json"
        else:
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        print(f"Scraped data saved successfully to {output_file}")
        return {"success": True, "file": str(output_file), "data": data, "screenshot": screenshot_res}

    def new_tab(self, url: str):
        """Open a new tab with the given URL."""
        if not url.startswith("http"):
            url = "https://" + url
        print(f"Opening new tab with: {url}...")
        return self.bridge.execute("navigate", url=url, newTab=True)

    def switch_tab(self, target: str):
        """Switch to a tab matching tabId or URL."""
        print(f"Switching to tab: {target}...")
        if target.isdigit():
            return self.bridge.execute("find_tab", tabId=int(target))
        else:
            return self.bridge.execute("find_tab", url=target)

    def close_tab(self, tab_id: str = None):
        """Close a tab by ID or close the active tab if none provided."""
        if tab_id:
            print(f"Closing tab: {tab_id}...")
            return self.bridge.execute("close_tab", tabId=int(tab_id))
        else:
            print("Closing active tab...")
            return self.bridge.execute("close_tab")

    def wait_for_tab(self, seconds: float = 2.0):
        """Wait for the tab page load/rendering to settle."""
        print(f"Waiting {seconds}s for tab...")
        time.sleep(seconds)
        return {"success": True, "waited": seconds}


def interactive_loop():
    agent = BrowserAgent()
    print("==================================================")
    print("   Opencode Browser Agent - Interactive Terminal  ")
    print("==================================================")
    print("Commands:")
    print("  goto <url>                 Navigate to website")
    print("  click <selector>           Click element")
    print("  fill <selector> <text>     Type text into input")
    print("  screenshot <name>          Take screenshot")
    print("  scroll-seq [steps] [px]    Scroll page & take screenshots")
    print("  goal <task description>    Let Reasoning Engine execute task")
    print("  new_tab <url>              Open a new browser tab")
    print("  switch_tab <target>        Switch tab by ID or URL")
    print("  close_tab [tabId]          Close tab by ID or active tab")
    print("  wait_for_tab [seconds]     Wait for tab to settle")
    print("  scrape <instruction>       Capture screenshot & extract requested data to JSON")
    print("  smart_fill <json_data>     Autofill forms using json key-values")
    print("  smart_fill_nl <instr>      Natural language form autofilling command")
    print("  voice_control              Start speech command accessibility overlay")
    print("  full_screenshot <name>     Capture full scrolling page screenshot")
    print("  element_screenshot <sel> <name> Capture specific DOM element screenshot")
    print("  visual_diff <img1> <img2>  Calculate pixel diff between two screenshots")
    print("  annotate <img> <anns> <out> Annotate image with bboxes and labels")
    print("  export <format> <data>     Export data to csv, json, excel")
    print("  sched_export <sec> <fmt> <data> Schedule exports periodically")
    print("  crawl <url> [pages] [depth] Domain-specific web crawler agent")
    print("  dclick <x> <y>             Desktop mouse click")
    print("  dwrite <text>              Desktop type text")
    print("  dpress <key>               Desktop press key")
    print("  dmove <x> <y>              Desktop mouse move")
    print("  dscroll <clicks>           Desktop mouse scroll")
    print("  dscreenshot [name]         Desktop screenshot")
    print("  exit                       Exit terminal")
    print("==================================================")

    while True:
        try:
            line = input("agent> ").strip()
            if not line:
                continue
            if line == "exit":
                break
            
            parts = line.split(" ", 1)
            cmd = parts[0]
            args = parts[1] if len(parts) > 1 else ""

            if cmd == "goto":
                if not args.startswith("http"):
                    args = "https://" + args
                res = agent.navigate(args)
                print(json.dumps(res, indent=2))
            elif cmd == "click":
                res = agent.click(args)
                print(json.dumps(res, indent=2))
            elif cmd == "fill":
                sub_parts = args.split(" ", 1)
                if len(sub_parts) < 2:
                    print("Usage: fill <selector> <text>")
                    continue
                res = agent.fill(sub_parts[0], sub_parts[1])
                print(json.dumps(res, indent=2))
            elif cmd == "screenshot":
                agent.screenshot(args)
            elif cmd == "scroll-seq":
                steps = 3
                px = 500
                if args:
                    try:
                        args_parts = args.split()
                        steps = int(args_parts[0])
                        if len(args_parts) > 1:
                            px = int(args_parts[1])
                    except ValueError:
                        print("Invalid arguments. Defaulting to 3 steps of 500px.")
                agent.scroll_and_screenshot(scroll_steps=steps, step_size=px)
            elif cmd == "goal":
                res = agent.run_goal(args)
                print(json.dumps(res, indent=2))

            elif cmd == "scrape":
                res = agent.scrape(args)
                print(json.dumps(res, indent=2))
            elif cmd == "new_tab":
                res = agent.new_tab(args)
                print(json.dumps(res, indent=2))
            elif cmd == "switch_tab":
                res = agent.switch_tab(args)
                print(json.dumps(res, indent=2))
            elif cmd == "close_tab":
                res = agent.close_tab(args if args else None)
                print(json.dumps(res, indent=2))
            elif cmd == "wait_for_tab":
                seconds = float(args) if args else 2.0
                res = agent.wait_for_tab(seconds)
                print(json.dumps(res, indent=2))
            elif cmd == "dclick":
                parts = args.split()
                x = int(parts[0]) if len(parts) > 0 else 0
                y = int(parts[1]) if len(parts) > 1 else 0
                res = agent.router.route("desktop_click", x=x, y=y)
                print(json.dumps(res, indent=2))
            elif cmd == "dwrite":
                res = agent.router.route("desktop_write", text=args)
                print(json.dumps(res, indent=2))
            elif cmd == "dpress":
                res = agent.router.route("desktop_press", key=args)
                print(json.dumps(res, indent=2))
            elif cmd == "dmove":
                parts = args.split()
                x = int(parts[0]) if len(parts) > 0 else 0
                y = int(parts[1]) if len(parts) > 1 else 0
                res = agent.router.route("desktop_move", x=x, y=y)
                print(json.dumps(res, indent=2))
            elif cmd == "dscroll":
                clicks = int(args) if args else -100
                res = agent.router.route("desktop_scroll", clicks=clicks)
                print(json.dumps(res, indent=2))
            elif cmd == "dscreenshot":
                res = agent.router.route("desktop_screenshot", filename=args)
                print(json.dumps(res, indent=2))
            elif cmd == "smart_fill":
                res = agent.router.route("smart_fill", form_data=args)
                print(json.dumps(res, indent=2))
            elif cmd == "full_screenshot":
                res = agent.router.route("full_page_screenshot", filename=args)
                print(json.dumps(res, indent=2))
            elif cmd == "element_screenshot":
                parts = args.split(" ", 1)
                sel = parts[0] if len(parts) > 0 else ""
                name = parts[1] if len(parts) > 1 else ""
                res = agent.router.route("element_screenshot", selector=sel, filename=name)
                print(json.dumps(res, indent=2))
            elif cmd == "visual_diff":
                parts = args.split()
                img1 = parts[0] if len(parts) > 0 else ""
                img2 = parts[1] if len(parts) > 1 else ""
                out = parts[2] if len(parts) > 2 else "diff.png"
                res = agent.router.route("visual_diff", baseline=img1, current=img2, output=out)
                print(json.dumps(res, indent=2))
            elif cmd == "annotate":
                parts = args.split(" ", 2)
                img = parts[0] if len(parts) > 0 else ""
                anns = parts[1] if len(parts) > 1 else ""
                out = parts[2] if len(parts) > 2 else "annotated.png"
                res = agent.router.route("annotate_image", image=img, annotations=anns, output=out)
                print(json.dumps(res, indent=2))
            elif cmd == "export":
                parts = args.split(" ", 1)
                fmt = parts[0] if len(parts) > 0 else "json"
                data = parts[1] if len(parts) > 1 else ""
                res = agent.router.route("export_data", data=data, format=fmt)
                print(json.dumps(res, indent=2))
            elif cmd == "sched_export":
                parts = args.split(" ", 2)
                sec = float(parts[0]) if len(parts) > 0 else 60.0
                fmt = parts[1] if len(parts) > 1 else "json"
                data = parts[2] if len(parts) > 2 else ""
                res = agent.router.route("schedule_export", interval=sec, format=fmt, data=data)
                print(json.dumps(res, indent=2))
            elif cmd == "crawl":
                parts = args.split()
                base_url = parts[0] if len(parts) > 0 else ""
                pages = int(parts[1]) if len(parts) > 1 else 10
                depth = int(parts[2]) if len(parts) > 2 else 2
                res = agent.router.route("crawl", base_url=base_url, max_pages=pages, max_depth=depth)
                print(json.dumps(res, indent=2))
            elif cmd == "smart_fill_nl":
                res = agent.router.route("smart_fill_nl", instruction=args)
                print(json.dumps(res, indent=2))
            elif cmd == "voice_control":
                res = agent.router.route("start_voice_control")
                print(json.dumps(res, indent=2))
            else:
                print(f"Unknown command: {cmd}")
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    interactive_loop()
