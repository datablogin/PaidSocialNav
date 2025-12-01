"""Monitoring and metrics for MCP server."""
from paid_social_nav.core.logging_config import get_logger
from datetime import datetime
from typing import Any, Callable, Awaitable
import time
from functools import wraps

logger = get_logger(__name__)


class MetricsCollector:
    """Collect metrics for monitoring."""

    def __init__(self) -> None:
        self.tool_calls: dict[str, dict[str, int]] = {}
        self.errors: dict[str, int] = {}
        self.latencies: dict[str, list[float]] = {}

    def record_tool_call(self, tool_name: str, duration: float, success: bool) -> None:
        """Record tool call metrics."""
        if tool_name not in self.tool_calls:
            self.tool_calls[tool_name] = {"total": 0, "success": 0, "failure": 0}

        self.tool_calls[tool_name]["total"] += 1
        if success:
            self.tool_calls[tool_name]["success"] += 1
        else:
            self.tool_calls[tool_name]["failure"] += 1

        # Record latency
        if tool_name not in self.latencies:
            self.latencies[tool_name] = []
        self.latencies[tool_name].append(duration)

    def record_error(self, error_type: str, tool_name: str) -> None:
        """Record error metrics."""
        key = f"{tool_name}:{error_type}"
        self.errors[key] = self.errors.get(key, 0) + 1

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics snapshot."""
        return {
            "timestamp": datetime.now().isoformat(),
            "tool_calls": self.tool_calls,
            "errors": self.errors,
            "latencies": {
                tool: {
                    "avg": sum(times) / len(times),
                    "max": max(times),
                    "min": min(times),
                    "count": len(times)
                }
                for tool, times in self.latencies.items()
            }
        }


# Global metrics collector
metrics = MetricsCollector()


def track_tool_execution(func: Callable[..., Awaitable[dict[str, Any]]]) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Decorator to track tool execution metrics."""
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        start = time.time()
        success = False

        try:
            result = await func(*args, **kwargs)
            success = result.get("success", False)
            return result
        except Exception:
            logger.exception(f"Tool {func.__name__} failed")
            raise
        finally:
            duration = time.time() - start
            metrics.record_tool_call(func.__name__, duration, success)

    return wrapper
