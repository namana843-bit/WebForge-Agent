from typing import Dict, Any
from browser_runtime.tools.base_tool import BrowserTool

class ClickTool(BrowserTool):
    """Tool wrapper to execute mouse clicks on elements."""

    def __init__(self):
        super().__init__(
            name="click",
            description="Clicks an element matching the given selector.",
            parameters={
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector to click."}
                },
                "required": ["selector"]
            }
        )

    def validate(self, arguments: Dict[str, Any]):
        if "selector" not in arguments:
            raise ValueError("Parameter 'selector' is required.")

    async def execute(self, page, arguments: Dict[str, Any]) -> Dict[str, Any]:
        selector = arguments["selector"]
        await page.click(selector)
        return {"clicked_selector": selector}

    def format_result(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "action": "click",
            "selector": raw_data.get("clicked_selector"),
            "status": "success"
        }
