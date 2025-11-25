"""Tests for PaidSocialNav MCP server."""

from __future__ import annotations

import pytest

from mcp_server.server import mcp


@pytest.fixture
async def mcp_client():
    """Reusable MCP client fixture."""
    # For Phase 1, we'll use a simpler approach that doesn't require Client
    # since we're testing the server components directly
    yield mcp


async def test_server_initialization(mcp_client):
    """Test server initialization."""
    assert mcp_client.name == "PaidSocialNav"
    assert mcp_client.version == "0.1.0"


async def test_list_tools(mcp_client):
    """Test tool listing."""
    tools = await mcp_client.get_tools()
    tool_names = list(tools.keys())

    assert "meta_sync_insights" in tool_names
    assert "audit_workflow" in tool_names
    assert "get_tenant_config" in tool_names
    assert "load_benchmarks" in tool_names


async def test_list_resources(mcp_client):
    """Test resource listing."""
    templates = await mcp_client.get_resource_templates()
    resources = await mcp_client.get_resources()

    # Verify both templates and static resources are registered
    assert len(templates) + len(resources) > 0

    # Static resources
    resource_uris = list(resources.keys())
    assert "tenants://list" in resource_uris

    # Dynamic templates
    template_uris = list(templates.keys())
    assert "insights://campaigns/{tenant_id}/{window}" in template_uris


async def test_list_prompts(mcp_client):
    """Test prompt listing."""
    prompts = await mcp_client.get_prompts()
    prompt_names = list(prompts.keys())

    assert "analyze_campaign_performance" in prompt_names
    assert "audit_setup_wizard" in prompt_names
    assert "data_sync_planner" in prompt_names


async def test_get_tenant_config_puttery(mcp_client):
    """Test tenant config retrieval for puttery tenant."""
    from mcp_server.tools import get_tenant_config_tool

    result = await get_tenant_config_tool("puttery")

    assert result["success"] is True
    assert result["id"] == "puttery"
    assert "project_id" in result
    assert result["dataset"] == "paid_social"


async def test_get_tenant_config_fleming(mcp_client):
    """Test tenant config retrieval for fleming tenant."""
    from mcp_server.tools import get_tenant_config_tool

    result = await get_tenant_config_tool("fleming")

    assert result["success"] is True
    assert result["id"] == "fleming"
    assert "project_id" in result
    assert result["dataset"] == "paid_social"


async def test_get_tenant_config_nonexistent(mcp_client):
    """Test tenant config retrieval for nonexistent tenant."""
    from mcp_server.tools import get_tenant_config_tool

    result = await get_tenant_config_tool("nonexistent")

    assert result["success"] is False
    assert "not found" in result["message"].lower()


async def test_tenant_list_resource(mcp_client):
    """Test tenant list resource."""
    from mcp_server.resources import get_tenant_list_resource
    import json

    resource_data = get_tenant_list_resource()
    data = json.loads(resource_data)

    assert "tenants" in data
    assert len(data["tenants"]) > 0

    # Verify puttery and fleming are in the list
    tenant_ids = [t["id"] for t in data["tenants"]]
    assert "puttery" in tenant_ids
    assert "fleming" in tenant_ids


@pytest.mark.parametrize(
    "tenant_id,expected_success",
    [("puttery", True), ("fleming", True), ("nonexistent", False)],
)
async def test_get_tenant_config_validation(
    mcp_client, tenant_id: str, expected_success: bool
):
    """Test tenant config validation."""
    from mcp_server.tools import get_tenant_config_tool

    result = await get_tenant_config_tool(tenant_id)

    assert result["success"] == expected_success


async def test_health_check():
    """Test health check endpoint."""
    from mcp_server.server import health_check
    from unittest.mock import Mock

    # Mock the request object
    mock_request = Mock()
    response = health_check(mock_request)

    # Verify response is a JSONResponse
    assert response.status_code == 200

    # Parse JSON body
    import json

    body_data = json.loads(response.body.decode())
    assert body_data["status"] == "healthy"
    assert "PaidSocialNav" in body_data["service"]
