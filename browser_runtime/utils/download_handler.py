from playwright.async_api import Download

class DownloadHandler:
    """Utility class to handle file download saves and monitoring."""

    @staticmethod
    async def save_download(download: Download, target_path: str):
        """Save a Playwright Download object to the target file path."""
        await download.save_as(target_path)
        print(f"[DownloadHandler] Saved downloaded file to: {target_path}")
