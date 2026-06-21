#!/usr/bin/env python3
"""Opencode Browser Agent Client - direct scripting and automation."""

import json
import urllib.request
import urllib.error
import time
import os
from pathlib import Path

class BrowserAgent:
    def __init__(self, bridge_url="http://127.0.0.1:10088"):
        self.bridge_url = bridge_url
        self.screenshot_dir = Path("data/screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def _api_call(self, action, args=None):
        payload = json.dumps({"action": action, "args": args or {}}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.bridge_url}/command",
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

    def navigate(self, url):
        """Navigate to a URL."""
        print(f"Navigating to {url}...")
        return self._api_call("navigate", {"url": url})

    def click(self, selector):
        """Click an element using CSS selector, XPath, or snapshot @e reference."""
        print(f"Clicking element: {selector}")
        return self._api_call("click", {"selector": selector})

    def fill(self, selector, value):
        """Fill an input field with a value."""
        print(f"Filling element {selector} with '{value}'...")
        return self._api_call("fill", {"selector": selector, "value": value})

    def get_snapshot(self):
        """Get the page's accessibility tree representation."""
        return self._api_call("snapshot")

    def screenshot(self, name=None):
        """Take a page screenshot and save it to data/screenshots."""
        if not name:
            name = f"screenshot_{int(time.time())}.png"
        if not name.endswith(".png"):
            name += ".png"
        resp = self._api_call("screenshot", {"filename": name})
        if "error" in resp:
            print(f"Screenshot Error: {resp['error']}")
        else:
            print(f"Screenshot saved successfully to {resp.get('path')}")
        return resp

    def scroll(self, selector=None, x=None, y=None):
        """Scroll page or scroll to element."""
        return self._api_call("scroll", {"selector": selector, "x": x, "y": y})

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
            else:
                print(f"Unknown command: {cmd}")
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    interactive_loop()
