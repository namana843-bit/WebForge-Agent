#!/usr/bin/env python3
"""Plugin interface for Browser Agent plugins."""

from abc import ABC, abstractmethod

class BrowserPlugin(ABC):
    """Abstract base class representing a plugin for the BrowserAgent."""

    @abstractmethod
    def execute(self, action: str, **kwargs):
        """Execute an action with the given arguments."""
        pass
