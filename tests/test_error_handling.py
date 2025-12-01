"""Tests for MCP server error handling."""

import pytest
from mcp_server.error_handling import (
    handle_tool_error,
    MCPError,
    ValidationError,
    ResourceNotFoundError,
    ExternalServiceError,
    AuthenticationError,
)


@pytest.mark.asyncio
async def test_handle_validation_error():
    """Test handling of validation errors."""
    error = ValidationError("Invalid input parameter")
    result = await handle_tool_error(error, "test_tool")

    assert result["success"] is False
    assert result["error_type"] == "validation_error"
    assert result["tool"] == "test_tool"
    assert "Invalid input parameter" in result["message"]


@pytest.mark.asyncio
async def test_handle_resource_not_found_error():
    """Test handling of resource not found errors."""
    error = ResourceNotFoundError("Tenant not found")
    result = await handle_tool_error(error, "test_tool")

    assert result["success"] is False
    assert result["error_type"] == "not_found"
    assert result["tool"] == "test_tool"
    assert "Tenant not found" in result["message"]


@pytest.mark.asyncio
async def test_handle_external_service_error():
    """Test handling of external service errors."""
    error = ExternalServiceError("BigQuery timeout")
    result = await handle_tool_error(error, "test_tool")

    assert result["success"] is False
    assert result["error_type"] == "external_service_error"
    assert result["tool"] == "test_tool"
    # Error message should be sanitized for external service errors
    assert "temporarily unavailable" in result["message"]


@pytest.mark.asyncio
async def test_handle_authentication_error():
    """Test handling of authentication errors."""
    error = AuthenticationError("Invalid credentials")
    result = await handle_tool_error(error, "test_tool")

    assert result["success"] is False
    assert result["error_type"] == "authentication_error"
    assert result["tool"] == "test_tool"
    assert "Authentication failed" in result["message"]


@pytest.mark.asyncio
async def test_handle_generic_error():
    """Test handling of generic/unexpected errors."""
    error = Exception("Unexpected error")
    result = await handle_tool_error(error, "test_tool")

    assert result["success"] is False
    assert result["error_type"] == "internal_error"
    assert result["tool"] == "test_tool"
    # Generic errors should have sanitized message
    assert "unexpected error occurred" in result["message"]


@pytest.mark.asyncio
async def test_error_hierarchy():
    """Test that custom errors inherit from MCPError."""
    assert issubclass(ValidationError, MCPError)
    assert issubclass(ResourceNotFoundError, MCPError)
    assert issubclass(ExternalServiceError, MCPError)
    assert issubclass(AuthenticationError, MCPError)
