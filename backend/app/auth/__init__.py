"""
Authentication package initialization.

This module exposes shared auth utilities such as dependencies and security
helpers so that other parts of the application can import from
`app.auth` instead of individual submodules.
"""

from .dependencies import (
    get_current_user,
    get_current_workspace,
    get_current_workspace_member,
    require_global_admin,
    create_access_token,
    verify_password,
    get_password_hash,
)
from .utils import (
    decode_token,
    get_token_subject,
)
from .schemas import (
    Token,
    LoginRequest,
    RegisterRequest,
    MeResponse,
    SwitchWorkspaceRequest,
)

__all__ = [
    # Dependencies
    "get_current_user",
    "get_current_workspace",
    "get_current_workspace_member",
    "require_global_admin",
    # Security helpers
    "create_access_token",
    "verify_password",
    "get_password_hash",
    "decode_token",
    "get_token_subject",
    # Schemas
    "Token",
    "LoginRequest",
    "RegisterRequest",
    "MeResponse",
    "SwitchWorkspaceRequest",
]