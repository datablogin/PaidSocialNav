"""Authentication providers for PaidSocialNav MCP server."""

from __future__ import annotations

import os
from typing import Any


def get_auth_provider() -> Any | None:
    """
    Get authentication provider based on environment configuration.

    Supports:
    - Google OAuth (recommended for Cloud Run)
    - JWT verification (for custom auth systems)
    - None (for local development only)

    Returns:
        Authentication provider instance or None for local development
    """
    auth_type = os.environ.get("MCP_AUTH_TYPE", "none")

    if auth_type == "google":
        try:
            from fastmcp.server.auth.providers.google import GoogleProvider

            return GoogleProvider(
                client_id=os.environ["GOOGLE_CLIENT_ID"],
                client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
                base_url=os.environ["MCP_BASE_URL"],
            )
        except ImportError as e:
            raise ImportError(
                "Google OAuth authentication requires fastmcp with google support. "
                "Install with: pip install 'fastmcp[google]'"
            ) from e

    elif auth_type == "jwt":
        try:
            from fastmcp.server.auth.providers.jwt import JWTVerifier

            return JWTVerifier(
                jwks_uri=os.environ["JWT_JWKS_URI"],
                issuer=os.environ["JWT_ISSUER"],
                audience=os.environ["JWT_AUDIENCE"],
            )
        except ImportError as e:
            raise ImportError(
                "JWT authentication requires fastmcp with JWT support. "
                "Install with: pip install 'fastmcp[jwt]'"
            ) from e

    elif auth_type == "none":
        # Local development only - NO AUTHENTICATION
        return None

    else:
        raise ValueError(f"Unknown auth type: {auth_type}")
