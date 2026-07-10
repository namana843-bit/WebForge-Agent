import time
import asyncio
from enum import Enum, auto
from typing import Dict, Any, Optional, List

class ActionType(Enum):
    CLICK = auto()
    TYPE = auto()
    SCROLL = auto()
    HOVER = auto()
    PRESS = auto()
    UPLOAD = auto()
    DOWNLOAD = auto()
    NAVIGATE = auto()

class Action:
    """Structured action command metadata container."""
    def __init__(
        self,
        action_type: ActionType,
        selector: Optional[str] = None,
        value: Optional[str] = None,
        args: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        delay: float = 1.0
    ):
        self.action_type = action_type
        self.selector = selector
        self.value = value
        self.args = args or {}
        self.max_retries = max_retries
        self.delay = delay

class ActionResult:
    """Standardized action execution output container."""
    def __init__(self, success: bool, data: Dict[str, Any], error: Optional[str] = None, exec_time: float = 0.0):
        self.success = success
        self.data = data
        self.error = error
        self.execution_time_ms = exec_time

class ActionExecutor:
    """Executes structured Action commands on a Playwright page with retry handling."""

    async def execute(self, page, action: Action) -> ActionResult:
        start_time = time.time()
        retries = 0
        delay = action.delay
        
        while True:
            try:
                res_data = await self._run_action(page, action)
                duration = (time.time() - start_time) * 1000
                return ActionResult(True, res_data, exec_time=duration)
            except Exception as e:
                if retries >= action.max_retries:
                    duration = (time.time() - start_time) * 1000
                    return ActionResult(False, {}, error=str(e), exec_time=duration)
                
                retries += 1
                await asyncio.sleep(delay)
                delay *= 1.5

    async def _run_action(self, page, action: Action) -> Dict[str, Any]:
        """Maps ActionTypes to direct Playwright page actions."""
        if action.action_type == ActionType.NAVIGATE:
            url = action.value or action.args.get("url")
            if not url:
                raise ValueError("Navigation requires a URL value.")
            await page.goto(url, wait_until="domcontentloaded")
            return {"url": url}
            
        elif action.action_type == ActionType.CLICK:
            if not action.selector:
                raise ValueError("Click action requires selector parameter.")
            await page.click(action.selector)
            return {"selector": action.selector}
            
        elif action.action_type == ActionType.TYPE:
            if not action.selector or not action.value:
                raise ValueError("Type action requires selector and text value parameters.")
            await page.fill(action.selector, action.value)
            return {"selector": action.selector, "length": len(action.value)}
            
        elif action.action_type == ActionType.SCROLL:
            x = action.args.get("x", 0)
            y = action.args.get("y", 300)
            await page.mouse.wheel(x, y)
            return {"scrolled_x": x, "scrolled_y": y}
            
        elif action.action_type == ActionType.HOVER:
            if not action.selector:
                raise ValueError("Hover action requires selector parameter.")
            await page.hover(action.selector)
            return {"selector": action.selector}
            
        elif action.action_type == ActionType.PRESS:
            key = action.value or action.args.get("key")
            if not key:
                raise ValueError("Press action requires a key value.")
            await page.keyboard.press(key)
            return {"pressed_key": key}
            
        elif action.action_type == ActionType.UPLOAD:
            if not action.selector or not action.value:
                raise ValueError("Upload action requires selector and file_path value parameters.")
            await page.set_input_files(action.selector, action.value)
            return {"selector": action.selector, "file_path": action.value}
            
        elif action.action_type == ActionType.DOWNLOAD:
            async with page.expect_download() as download_info:
                # Trigger event concurrently (user must initiate download click via action sequence)
                pass
            download = await download_info.value
            save_path = action.args.get("save_path", f"Memory/data/downloads/{download.suggested_filename}")
            await download.save_as(save_path)
            return {"filename": download.suggested_filename, "save_path": save_path}
            
        else:
            raise NotImplementedError(f"Action type '{action.action_type}' is not supported.")
