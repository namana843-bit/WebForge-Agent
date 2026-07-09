from typing import Dict
from browser_runtime.core.browser_manager import BrowserManager
from browser_runtime.core.context_manager import ContextManager
from browser_runtime.config import BrowserConfig
from browser_runtime.exceptions import SessionNotFoundError

class SessionManager:
    """Manages active contexts (sessions) mapped by unique identifiers."""

    def __init__(self, browser_manager: BrowserManager, config: BrowserConfig):
        self.browser_manager = browser_manager
        self.config = config
        self.sessions: Dict[str, ContextManager] = {}

    async def create_session(self, session_id: str) -> ContextManager:
        """Create a new isolated context session."""
        if not self.browser_manager.browser:
            await self.browser_manager.start()
            
        # Create isolated browser context
        context = await self.browser_manager.browser.new_context(
            viewport=self.config.viewport,
            user_agent=self.config.user_agent
        )
        
        ctx_mgr = ContextManager(context, self.config)
        self.sessions[session_id] = ctx_mgr
        return ctx_mgr

    def get_session(self, session_id: str) -> ContextManager:
        """Get an existing session."""
        if session_id not in self.sessions:
            raise SessionNotFoundError(f"Session '{session_id}' not found.")
        return self.sessions[session_id]

    async def close_session(self, session_id: str):
        """Close and remove a specific session."""
        if session_id in self.sessions:
            await self.sessions[session_id].close()
            del self.sessions[session_id]
            
    async def close_all(self):
        """Close all active sessions."""
        for session_id in list(self.sessions.keys()):
            await self.close_session(session_id)
