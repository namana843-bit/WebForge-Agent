import os
from typing import Dict, Any, Optional

class BrowserConfig:
    """Configuration class for launching browser instances."""

    def __init__(
        self,
        headless: bool = True,
        browser_type: str = "chromium",  # chromium, firefox, webkit
        viewport_width: int = 1280,
        viewport_height: int = 720,
        timeout: float = 30000.0,  # in ms
        proxy: Optional[Dict[str, str]] = None,
        user_agent: Optional[str] = None
    ):
        self.headless = headless
        self.browser_type = browser_type.lower()
        self.viewport = {"width": viewport_width, "height": viewport_height}
        self.timeout = timeout
        self.proxy = proxy
        self.user_agent = user_agent

    def to_launch_options(self) -> Dict[str, Any]:
        """Convert configurations to Playwright launch options."""
        options = {
            "headless": self.headless,
        }
        if self.proxy:
            options["proxy"] = self.proxy
        return options
