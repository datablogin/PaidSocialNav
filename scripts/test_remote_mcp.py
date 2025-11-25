"""Test remote MCP server deployment."""

from __future__ import annotations

import asyncio
import os

from fastmcp import Client


async def test_remote_server():
    """Test the deployed MCP server."""
    # Use authenticated proxy: gcloud run services proxy paidsocialnav-mcp
    server_url = os.environ.get("MCP_SERVER_URL", "http://localhost:8080/mcp")

    print(f"Connecting to MCP server at {server_url}")

    async with Client(server_url) as client:
        # Test tool listing
        print("\n📋 Testing tool listing...")
        tools = await client.list_tools()
        print(f"Available tools: {[t.name for t in tools]}")

        # Test resource listing
        print("\n📚 Testing resource listing...")
        resources = await client.list_resources()
        print(f"Available resources: {len(resources)} resources")

        # Test tenant config
        print("\n🏢 Testing get_tenant_config...")
        result = await client.call_tool(
            "get_tenant_config", {"tenant_id": "puttery"}
        )
        print(f"Result: {result}")

        # Test tenant list resource
        print("\n👥 Testing tenant list resource...")
        tenant_data = await client.read_resource("tenants://list")
        print(f"Tenants: {tenant_data[0].text[:200]}...")

        print("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_remote_server())
