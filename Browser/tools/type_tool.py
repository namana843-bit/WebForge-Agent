from typing import Dict, Any
from Browser.tools.base_tool import BrowserTool

class TypeTool(BrowserTool):
    """Tool wrapper to execute input typing on text fields."""

    def __init__(self):
        super().__init__(
            name="type",
            description="Type a text string into an input selector.",
            parameters={
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector to target."},
                    "text": {"type": "string", "description": "Value to type."}
                },
                "required": ["selector", "text"]
            }
        )

    def validate(self, arguments: Dict[str, Any]):
        if "selector" not in arguments:
            raise ValueError("Parameter 'selector' is required.")
        if "text" not in arguments:
            raise ValueError("Parameter 'text' is required.")

    async def execute(self, page, arguments: Dict[str, Any]) -> Dict[str, Any]:
        selector = arguments["selector"]
        text = arguments["text"]
        await page.fill(selector, text)
        return {"selector": selector, "typed_length": len(text)}

    def format_result(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "action": "type",
            "selector": raw_data.get("selector"),
            "typed_characters": raw_data.get("typed_length"),
            "status": "success"
        }
