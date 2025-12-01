"""Centralized error handling for MCP server."""
from fastmcp import Context
from paid_social_nav.core.logging_config import get_logger

logger = get_logger(__name__)


class MCPError(Exception):
    """Base exception for MCP server errors."""
    pass


class AuthenticationError(MCPError):
    """Authentication failed."""
    pass


class ValidationError(MCPError):
    """Input validation failed."""
    pass


class ResourceNotFoundError(MCPError):
    """Requested resource not found."""
    pass


class ExternalServiceError(MCPError):
    """External service (BigQuery, Meta API) failed."""
    pass


async def handle_tool_error(
    error: Exception,
    tool_name: str,
    ctx: Context | None = None
) -> dict:
    """
    Standardized error handling for MCP tools.

    Args:
        error: The exception that occurred
        tool_name: Name of the tool that failed
        ctx: MCP context for client logging

    Returns:
        Standardized error response dict
    """
    # Log full error server-side
    logger.exception(f"Error in tool '{tool_name}': {str(error)}")

    # Determine error type and client message
    if isinstance(error, ValidationError):
        error_type = "validation_error"
        client_message = str(error)
    elif isinstance(error, ResourceNotFoundError):
        error_type = "not_found"
        client_message = str(error)
    elif isinstance(error, ExternalServiceError):
        error_type = "external_service_error"
        client_message = "External service temporarily unavailable. Please try again."
    elif isinstance(error, AuthenticationError):
        error_type = "authentication_error"
        client_message = "Authentication failed. Check credentials."
    else:
        error_type = "internal_error"
        client_message = "An unexpected error occurred. Please contact support."

    # Send sanitized error to client
    if ctx:
        await ctx.error(f"{tool_name} failed: {client_message}")

    return {
        "success": False,
        "error_type": error_type,
        "message": client_message,
        "tool": tool_name
    }
