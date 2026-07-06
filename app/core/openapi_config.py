"""OpenAPI 3.0 configuration and metadata."""

from typing import Any

OPENAPI_TAGS_METADATA: list[dict[str, str]] = [
    {
        "name": "auth",
        "description": "User authentication: register, login, refresh tokens, logout.",
    },
    {
        "name": "users",
        "description": "User management: create, read, update, delete users within a library. Requires admin role.",
    },
    {
        "name": "libraries",
        "description": "Library management: get and update library information. Requires admin role.",
    },
]

OPENAPI_CONFIG: dict[str, Any] = {
    "title": "Jinbocho Auth Service",
    "version": "0.1.0",
    "description": "Authentication and library user management service for Jinbocho home library system. "
    "Provides JWT-based auth with refresh token rotation and multi-tenant library isolation.",
    "openapi_tags": OPENAPI_TAGS_METADATA,
    "docs_url": "/docs",
    "redoc_url": "/redoc",
    "openapi_url": "/openapi.json",
}
