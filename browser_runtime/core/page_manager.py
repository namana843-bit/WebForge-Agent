from playwright.async_api import Page, Download
from browser_runtime.exceptions import PageNavigationError, ElementInteractionError

class PageManager:
    """Manages page-level operations (navigation, interaction, events)."""

    def __init__(self, page: Page):
        self.page = page

    async def navigate(self, url: str):
        """Navigate to the target URL."""
        try:
            await self.page.goto(url, wait_until="domcontentloaded")
        except Exception as e:
            raise PageNavigationError(f"Failed to navigate to {url}: {e}")

    async def click(self, selector: str):
        """Click the target selector element."""
        try:
            await self.page.click(selector)
        except Exception as e:
            raise ElementInteractionError(f"Failed to click selector {selector}: {e}")

    async def fill(self, selector: str, value: str):
        """Fill value into input selector."""
        try:
            await self.page.fill(selector, value)
        except Exception as e:
            raise ElementInteractionError(f"Failed to fill selector {selector}: {e}")

    async def upload_files(self, selector: str, file_paths: list):
        """Inject files into file upload input."""
        try:
            await self.page.set_input_files(selector, file_paths)
        except Exception as e:
            raise ElementInteractionError(f"Failed to upload files to {selector}: {e}")

    async def watch_download(self) -> Download:
        """Helper to wait for and capture a download event."""
        async with self.page.expect_download() as download_info:
            # The download event trigger must happen concurrently
            pass
        return await download_info.value

    async def screenshot(self, path: str, full_page: bool = False):
        """Capture page screenshot."""
        await self.page.screenshot(path=path, full_page=full_page)

    async def close(self):
        """Close the page/tab."""
        await self.page.close()
