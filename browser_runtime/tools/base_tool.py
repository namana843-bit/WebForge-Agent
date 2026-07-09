import time
import asyncio
from typing import List, Dict, Any, Optional, Type
from abc import ABC, abstractmethod

class RetryPolicy:
    """Configures retry behavior for executing tools."""
    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        retryable_exceptions: Optional[List[Type[Exception]]] = None
    ):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.retryable_exceptions = retryable_exceptions or [Exception]

class ToolResult:
    """Standard container for tool execution results."""
    def __init__(self, success: bool, data: Dict[str, Any], error: Optional[str] = None, exec_time: float = 0.0):
        self.success = success
        self.data = data
        self.error = error
        self.execution_time_ms = exec_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms
        }

class BrowserTool(ABC):
    """Abstract base class that all browser capability tools must inherit from."""

    def __init__(self, name: str, description: str, parameters: Dict[str, Any], retry_policy: Optional[RetryPolicy] = None):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.retry_policy = retry_policy or RetryPolicy()

    @abstractmethod
    def validate(self, arguments: Dict[str, Any]):
        """Validates parameters schema. Raises ValueError if invalid."""
        pass

    @abstractmethod
    async def execute(self, page, arguments: Dict[str, Any]) -> ToolResult:
        """Executes the action on Playwright page context."""
        pass

    @abstractmethod
    def format_result(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes and formats execution output."""
        pass

    async def run(self, page, arguments: Dict[str, Any]) -> ToolResult:
        """Executes tool with retry wrapper logic."""
        start_time = time.time()
        
        try:
            self.validate(arguments)
        except Exception as e:
            return ToolResult(False, {}, error=f"Validation failed: {e}", exec_time=(time.time() - start_time) * 1000)

        retries = 0
        delay = 0.5
        
        while True:
            try:
                result_data = await self.execute(page, arguments)
                duration = (time.time() - start_time) * 1000
                return ToolResult(True, self.format_result(result_data), exec_time=duration)
            except Exception as e:
                # Check if exception is retryable
                is_retryable = any(isinstance(e, ex) for ex in self.retry_policy.retryable_exceptions)
                if not is_retryable or retries >= self.retry_policy.max_retries:
                    duration = (time.time() - start_time) * 1000
                    return ToolResult(False, {}, error=str(e), exec_time=duration)
                
                retries += 1
                await asyncio.sleep(delay)
                delay *= self.retry_policy.backoff_factor
