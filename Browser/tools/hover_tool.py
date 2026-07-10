from typing import Dict, Any
from Browser.tools.base_tool import BrowserTool

class HoverTool(BrowserTool):
    """Tool wrapper to hover cursor over page elements."""

    def __init__(self):
        super().__init__(
            name="hover",
            description="Hover the mouse cursor over a selector.",
            parameters={
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector to hover over."}
                },
                "required": ["selector"]
            }
        )

    def validate(self, arguments: Dict[str, Any]):
        if "selector" not in arguments:
            raise ValueError("Parameter 'selector' is required.")

    async def execute(self, page, arguments: Dict[str, Any]) -> Dict[str, Any]:
        selector = arguments["selector"]
        await page.hover(selector)
        return {"selector": selector}

    def format_result(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "action": "hover",
            "selector": raw_data.get("selector"),
            "status": "success"
        }
