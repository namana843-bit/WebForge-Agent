from typing import List, Dict, Any
from playwright.async_api import BrowserContext, Page
from browser_runtime.config import BrowserConfig

class ContextManager:
    """Manages tab isolation, proxy rules, cookies, and page contexts."""

    def __init__(self, context: BrowserContext, config: BrowserConfig):
        self.context = context
        self.config = config
        self.pages: List[Page] = []

    async def new_page(self) -> Page:
        """Create a new page/tab in this isolated context."""
        page = await self.context.new_page()
        page.set_default_timeout(self.config.timeout)
        self.pages.append(page)
        return page

    async def get_cookies(self) -> List[Dict[str, Any]]:
        """Retrieve cookies from this context."""
        return await self.context.cookies()

    async def set_cookies(self, cookies: List[Dict[str, Any]]):
        """Set cookies for this isolated context."""
        await self.context.add_cookies(cookies)

    async def close(self):
        """Close the context and all associated pages."""
        await self.context.close()
        self.pages.clear()
