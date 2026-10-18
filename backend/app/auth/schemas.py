"""Pydantic schemas for authentication endpoints."""

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    """JWT token response."""

    token: str


class LoginRequest(BaseModel):
    """Login request payload."""

    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Registration request payload."""

    full_name: Optional[str] = None
    email: EmailStr
    password: str
    workspace_name: str


class UserResponse(BaseModel):
    """User data in API responses."""

    id: str
    email: str
    full_name: Optional[str]
    is_email_verified: bool
    global_role: str

    class Config:
        from_attributes = True


class WorkspaceResponse(BaseModel):
    """Workspace data in API responses."""

    id: str
    name: str
    status: str
    owner_user_id: str

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Login response payload."""

    token: str
    user: UserResponse
    workspaces: List[WorkspaceResponse]
    current_workspace: Optional[WorkspaceResponse]


class RegisterResponse(BaseModel):
    """Registration response payload."""

    token: str
    user: UserResponse
    workspace: WorkspaceResponse


class MeResponse(BaseModel):
    """Current user info response."""

    user: UserResponse
    workspaces: List[WorkspaceResponse]
    current_workspace: Optional[WorkspaceResponse]


class SwitchWorkspaceRequest(BaseModel):
    """Switch workspace request payload."""

    workspace_id: UUID


class SwitchWorkspaceResponse(BaseModel):
    """Switch workspace response payload."""

    current_workspace: WorkspaceResponse

