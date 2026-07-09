class BrowserRuntimeException(Exception):
    """Base exception for all browser runtime errors."""
    pass

class BrowserInitializationError(BrowserRuntimeException):
    """Raised when the browser fails to initialize/start."""
    pass

class SessionNotFoundError(BrowserRuntimeException):
    """Raised when a specified session/context is not found."""
    pass

class PageNavigationError(BrowserRuntimeException):
    """Raised when page navigation fails or times out."""
    pass

class ElementInteractionError(BrowserRuntimeException):
    """Raised when interacting with a page element fails."""
    pass
