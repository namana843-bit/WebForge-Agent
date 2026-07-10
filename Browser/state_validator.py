import time
from typing import Dict, Any, Optional

class ValidationResult:
    """Carries the outcome of state validation checks."""
    def __init__(self, success: bool, observation: str, details: Dict[str, Any]):
        self.success = success
        self.observation = observation
        self.details = details

class StateValidator:
    """Verifies page changes, visibility indicators, captcha presence, and generates next observations."""

    async def verify_url_changed(self, page, previous_url: str) -> bool:
        """Checks if page URL changed from previous URL."""
        return page.url != previous_url

    async def verify_element_disappeared(self, page, selector: str) -> bool:
        """Checks if a selector is no longer visible on the page."""
        try:
            return not (await page.locator(selector).is_visible())
        except Exception:
            return True

    async def verify_text_appeared(self, page, text: str) -> bool:
        """Checks if a specific string text appears on the webpage."""
        try:
            return await page.locator(f"text={text}").is_visible()
        except Exception:
            return False

    async def verify_popup_shown(self, page, selector: Optional[str] = None) -> bool:
        """Checks if an alert/modal dialog popup is visible on the page."""
        sel = selector or "div[role='dialog'], div.modal, div.alert"
        try:
            return await page.locator(sel).is_visible()
        except Exception:
            return False

    async def verify_captcha_present(self, page) -> bool:
        """Scans page structures looking for CAPTCHA elements."""
        captcha_indicators = [
            "iframe[src*='recaptcha']",
            "iframe[src*='hcaptcha']",
            "iframe[title*='recaptcha']",
            ".g-recaptcha",
            "#recaptcha",
            "iframe[src*='captcha']"
        ]
        for selector in captcha_indicators:
            try:
                if await page.locator(selector).count() > 0:
                    return True
            except Exception:
                continue
        return False

    async def verify_goal_completed(self, page, goal: str, page_agent) -> bool:
        """Queries the page agent to check if the goal completion is reached."""
        prompt = (
            f"Goal: '{goal}'. Based on the page, is the goal fully completed? "
            "Reply with exactly 'YES' or 'NO' followed by a brief reason."
        )
        res = page_agent.understand(prompt)
        text = ""
        if isinstance(res, dict) and "result" in res:
            text = res["result"].strip().upper()
        elif isinstance(res, str):
            text = res.strip().upper()
        return text.startswith("YES")

    async def generate_next_observation(self, page, previous_state: Dict[str, Any]) -> ValidationResult:
        """Examines the page and generates a structural description of state changes since last cycle."""
        current_url = page.url
        prev_url = previous_state.get("url", "")
        url_changed = current_url != prev_url
        
        captcha_present = await self.verify_captcha_present(page)
        popup_present = await self.verify_popup_shown(page)
        
        details = {
            "current_url": current_url,
            "url_changed": url_changed,
            "captcha_present": captcha_present,
            "popup_present": popup_present
        }
        
        obs_parts = []
        if url_changed:
            obs_parts.append(f"URL changed from '{prev_url}' to '{current_url}'.")
        else:
            obs_parts.append(f"Page remained on URL '{current_url}'.")
            
        if captcha_present:
            obs_parts.append("Warning: A security CAPTCHA check was detected on the page!")
        if popup_present:
            obs_parts.append("Notification: A popup modal/dialog selector is currently visible.")
            
        observation = " ".join(obs_parts)
        return ValidationResult(success=True, observation=observation, details=details)
