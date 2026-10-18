"""Authorization service for workspace access and role validation."""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace, WorkspaceStatus
from app.models.workspacemember import WorkspaceMember, WorkspaceMemberRole

logger = logging.getLogger(__name__)


class AuthorizationError(Exception):
    """Raised when authorization fails."""

    pass


class AuthzService:
    """Service for workspace authorization and access control."""

    # Role hierarchy (higher number = more permissions)
    ROLE_HIERARCHY = {
        WorkspaceMemberRole.OWNER: 4,
        WorkspaceMemberRole.MEMBER: 3,  # Using MEMBER as admin equivalent
        WorkspaceMemberRole.READONLY: 1,
    }

    async def assert_workspace_access(
        self,
        session: AsyncSession,
        user_id: UUID,
        workspace_id: UUID,
    ) -> WorkspaceMember:
        """Assert that user has access to workspace and workspace is not suspended.

        Args:
            session: Database session
            user_id: User ID
            workspace_id: Workspace ID

        Returns:
            WorkspaceMember object

        Raises:
            AuthorizationError: If user doesn't have access or workspace is suspended
        """
        # Check workspace status first
        workspace_result = await session.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        workspace = workspace_result.scalar_one_or_none()
        
        if not workspace:
            raise AuthorizationError(f"Workspace {workspace_id} not found")
        
        if workspace.status == WorkspaceStatus.SUSPENDED:
            raise AuthorizationError(
                f"Workspace {workspace_id} is suspended. Please contact support."
            )
        
        result = await session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.workspace_id == workspace_id,
            )
        )
        member = result.scalar_one_or_none()

        if not member:
            raise AuthorizationError(
                f"User {user_id} does not have access to workspace {workspace_id}"
            )

        return member

    async def assert_workspace_role(
        self,
        session: AsyncSession,
        user_id: UUID,
        workspace_id: UUID,
        required_role: WorkspaceMemberRole,
    ) -> WorkspaceMember:
        """Assert that user has required role in workspace.

        Args:
            session: Database session
            user_id: User ID
            workspace_id: Workspace ID
            required_role: Required role

        Returns:
            WorkspaceMember object

        Raises:
            AuthorizationError: If user doesn't have required role
        """
        member = await self.assert_workspace_access(session, user_id, workspace_id)

        user_role_level = self.ROLE_HIERARCHY.get(member.role, 0)
        required_role_level = self.ROLE_HIERARCHY.get(required_role, 0)

        if user_role_level < required_role_level:
            raise AuthorizationError(
                f"User {user_id} has role {member.role.value} but {required_role.value} is required"
            )

        return member

    async def check_workspace_access(
        self,
        session: AsyncSession,
        user_id: UUID,
        workspace_id: UUID,
    ) -> bool:
        """Check if user has access to workspace (non-raising version).

        Args:
            session: Database session
            user_id: User ID
            workspace_id: Workspace ID

        Returns:
            True if user has access
        """
        try:
            await self.assert_workspace_access(session, user_id, workspace_id)
            return True
        except AuthorizationError:
            return False

    async def check_workspace_role(
        self,
        session: AsyncSession,
        user_id: UUID,
        workspace_id: UUID,
        required_role: WorkspaceMemberRole,
    ) -> bool:
        """Check if user has required role (non-raising version).

        Args:
            session: Database session
            user_id: User ID
            workspace_id: Workspace ID
            required_role: Required role

        Returns:
            True if user has required role
        """
        try:
            await self.assert_workspace_role(session, user_id, workspace_id, required_role)
            return True
        except AuthorizationError:
            return False

    async def assert_resource_ownership(
        self,
        session: AsyncSession,
        user_id: UUID,
        workspace_id: UUID,
        resource_workspace_id: UUID,
    ) -> None:
        """Assert that resource belongs to user's workspace (cross-tenant protection).

        Args:
            session: Database session
            user_id: User ID
            workspace_id: User's workspace ID
            resource_workspace_id: Resource's workspace ID

        Raises:
            AuthorizationError: If resource doesn't belong to user's workspace
        """
        if workspace_id != resource_workspace_id:
            raise AuthorizationError(
                f"Resource belongs to workspace {resource_workspace_id} "
                f"but user's workspace is {workspace_id}"
            )

        # Also verify user has access to their workspace
        await self.assert_workspace_access(session, user_id, workspace_id)

    def can_perform_action(
        self,
        user_role: WorkspaceMemberRole,
        action: str,
    ) -> bool:
        """Check if a role can perform an action.

        Args:
            user_role: User's role
            action: Action name (e.g., "create_template", "delete_project", "view_documents")

        Returns:
            True if action is allowed
        """
        # Define action requirements
        action_requirements: dict[str, WorkspaceMemberRole] = {
            # Workspace management
            "manage_workspace": WorkspaceMemberRole.OWNER,
            "invite_members": WorkspaceMemberRole.OWNER,
            "remove_members": WorkspaceMemberRole.OWNER,
            "change_billing": WorkspaceMemberRole.OWNER,
            # Resource management
            "create_project": WorkspaceMemberRole.MEMBER,
            "delete_project": WorkspaceMemberRole.MEMBER,
            "create_template": WorkspaceMemberRole.MEMBER,
            "delete_template": WorkspaceMemberRole.MEMBER,
            "create_api_key": WorkspaceMemberRole.MEMBER,
            "delete_api_key": WorkspaceMemberRole.MEMBER,
            "manage_webhooks": WorkspaceMemberRole.MEMBER,
            # Usage
            "upload_document": WorkspaceMemberRole.MEMBER,
            "delete_document": WorkspaceMemberRole.MEMBER,
            "view_documents": WorkspaceMemberRole.READONLY,
            "view_templates": WorkspaceMemberRole.READONLY,
            "view_usage": WorkspaceMemberRole.MEMBER,
        }

        required_role = action_requirements.get(action)
        if not required_role:
            # Unknown action - deny by default
            logger.warning("Unknown action: %s", action)
            return False

        user_role_level = self.ROLE_HIERARCHY.get(user_role, 0)
        required_role_level = self.ROLE_HIERARCHY.get(required_role, 0)

        return user_role_level >= required_role_level

