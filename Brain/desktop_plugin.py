#!/usr/bin/env python3
"""Desktop automation plugin using PyAutoGUI for full OS-level control."""

import time
import os
from pathlib import Path
from plugin_interface import BrowserPlugin

class DesktopPlugin(BrowserPlugin):
    """Plugin to automate desktop-level operations using PyAutoGUI."""

    def __init__(self, agent):
        self.agent = agent
        try:
            import pyautogui
            self.pyautogui = pyautogui
            # Safety fail-safe: move mouse to corner of screen to abort action
            self.pyautogui.FAILSAFE = True
        except ImportError:
            self.pyautogui = None
            print("[DesktopPlugin] Warning: pyautogui is not installed. Desktop actions will be unavailable.")

    def execute(self, action: str, **kwargs):
        if not self.pyautogui:
            return {"error": "PyAutoGUI not installed or not available on this platform."}

        try:
            if action == "desktop_click":
                x = int(kwargs.get("x", 0))
                y = int(kwargs.get("y", 0))
                clicks = int(kwargs.get("clicks", 1))
                button = kwargs.get("button", "left")
                self.pyautogui.click(x=x, y=y, clicks=clicks, button=button)
                return {"success": True, "action": "click", "x": x, "y": y}

            elif action == "desktop_write":
                text = str(kwargs.get("text", ""))
                interval = float(kwargs.get("interval", 0.05))
                self.pyautogui.write(text, interval=interval)
                return {"success": True, "action": "write", "text_length": len(text)}

            elif action == "desktop_press":
                key = str(kwargs.get("key", ""))
                self.pyautogui.press(key)
                return {"success": True, "action": "press", "key": key}

            elif action == "desktop_move":
                x = int(kwargs.get("x", 0))
                y = int(kwargs.get("y", 0))
                duration = float(kwargs.get("duration", 0.1))
                self.pyautogui.moveTo(x, y, duration=duration)
                return {"success": True, "action": "move", "x": x, "y": y}

            elif action == "desktop_scroll":
                clicks = int(kwargs.get("clicks", 0))
                self.pyautogui.scroll(clicks)
                return {"success": True, "action": "scroll", "clicks": clicks}

            elif action == "desktop_screenshot":
                name = kwargs.get("filename")
                if not name:
                    name = f"desktop_{int(time.time())}.png"
                if not name.endswith(".png"):
                    name += ".png"
                
                output_dir = Path("Memory/data/screenshots")
                output_dir.mkdir(parents=True, exist_ok=True)
                filepath = output_dir / name
                
                im = self.pyautogui.screenshot()
                im.save(filepath)
                return {"success": True, "action": "screenshot", "path": str(filepath)}

            else:
                return {"error": f"Unknown desktop action: {action}"}

        except Exception as e:
            return {"error": f"Desktop automation error: {str(e)}"}
