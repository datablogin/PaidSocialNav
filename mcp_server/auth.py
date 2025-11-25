"""Authentication providers for PaidSocialNav MCP server."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def get_auth_provider() -> Any | None:
    """
    Get authentication provider based on environment configuration.

    Supports:
    - Google OAuth (recommended for Cloud Run)
    - JWT verification (for custom auth systems)
    - None (for local development only)

    Returns:
        Authentication provider instance or None for local development

    Raises:
        ValueError: If attempting to use no authentication in production
    """
    auth_type = os.environ.get("MCP_AUTH_TYPE", "none")
    environment = os.environ.get("ENVIRONMENT", "development")

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
        # Require explicit opt-in for no auth - prevent accidental production deployment
        if environment == "production":
            raise ValueError(
                "Cannot use MCP_AUTH_TYPE=none in production environment. "
                "Set MCP_AUTH_TYPE to 'google' or 'jwt' for secure authentication."
            )

        logger.warning(
            "⚠️  Running MCP server with NO AUTHENTICATION - development only. "
            "Never deploy to production without authentication!"
        )
        return None

    else:
        raise ValueError(f"Unknown auth type: {auth_type}")
