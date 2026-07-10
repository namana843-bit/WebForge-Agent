import asyncio
from playwright.async_api import async_playwright, Playwright, Browser
from Config.config import BrowserConfig
from Browser.exceptions import BrowserInitializationError

class BrowserManager:
    """Manages Playwright initialization and Browser instance lifecycles."""

    def __init__(self, config: BrowserConfig):
        self.config = config
        self.playwright: Playwright = None
        self.browser: Browser = None

    async def start(self):
        """Launches the Playwright browser asynchronously."""
        try:
            self.playwright = await async_playwright().start()
            
            # Select target browser type
            if self.config.browser_type == "firefox":
                launcher = self.playwright.firefox
            elif self.config.browser_type == "webkit":
                launcher = self.playwright.webkit
            else:
                launcher = self.playwright.chromium
                
            self.browser = await launcher.launch(**self.config.to_launch_options())
            print(f"[BrowserManager] Launched {self.config.browser_type} successfully.")
        except Exception as e:
            raise BrowserInitializationError(f"Failed to start browser: {e}")

    async def stop(self):
        """Closes browser instances and stops Playwright."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("[BrowserManager] Stopped browser and Playwright.")
