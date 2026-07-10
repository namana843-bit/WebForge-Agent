import os
from playwright.async_api import Page
from Browser.exceptions import ElementInteractionError

class UploadHandler:
    """Utility class to validate and handle file upload workflows."""

    @staticmethod
    async def upload(page: Page, selector: str, file_path: str):
        """Validates file exists and injects it into file upload selectors."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found for upload: {file_path}")
            
        try:
            await page.set_input_files(selector, file_path)
            print(f"[UploadHandler] Injected file {file_path} into selector {selector}")
        except Exception as e:
            raise ElementInteractionError(f"Upload failed: {e}")
