"""Server configuration for PaidSocialNav MCP server.

Phase 1: Basic configuration stub.
Phase 2: Will add Cloud Run-specific configuration.
"""

from __future__ import annotations

import os


def get_server_config() -> dict[str, str | int]:
    """
    Get server configuration from environment variables.

    Phase 1: Basic configuration for local STDIO server.
    Phase 2: Will add Cloud Run, authentication, and monitoring config.

    Returns:
        Configuration dictionary
    """
    return {
        "transport": os.environ.get("MCP_TRANSPORT", "stdio"),
        "port": int(os.environ.get("PORT", 8080)),
        "host": os.environ.get("HOST", "0.0.0.0"),
    }
