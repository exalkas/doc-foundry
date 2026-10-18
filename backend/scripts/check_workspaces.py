#!/usr/bin/env python3
"""Check workspaces and workspace members in the database."""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
backend_dir = Path(__file__).parent.parent
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# Add backend directory to Python path
sys.path.insert(0, str(backend_dir))

from app.database import AsyncSessionLocal
from sqlalchemy import select
from app.models.workspace import Workspace
from app.models.workspacemember import WorkspaceMember
from app.models.user import User


async def check_workspaces():
    """Check all workspaces and memberships."""
    async with AsyncSessionLocal() as session:
        # Get all workspaces
        result = await session.execute(select(Workspace))
        workspaces = result.scalars().all()
        
        print("=" * 60)
        print("All Workspaces in Database")
        print("=" * 60)
        print(f"\nTotal workspaces: {len(workspaces)}\n")
        
        for ws in workspaces:
            print(f"Workspace: {ws.name}")
            print(f"  ID: {ws.id}")
            print(f"  Owner User ID: {ws.owner_user_id}")
            print(f"  Status: {ws.status.value}")
            print(f"  Created: {ws.created_at}")
            
            # Get owner user
            owner_result = await session.execute(
                select(User).where(User.id == ws.owner_user_id)
            )
            owner = owner_result.scalar_one_or_none()
            if owner:
                print(f"  Owner Email: {owner.email}")
            
            # Get all members
            members_result = await session.execute(
                select(WorkspaceMember).where(WorkspaceMember.workspace_id == ws.id)
            )
            members = members_result.scalars().all()
            print(f"  Members ({len(members)}):")
            for member in members:
                user_result = await session.execute(
                    select(User).where(User.id == member.user_id)
                )
                user = user_result.scalar_one_or_none()
                email = user.email if user else "Unknown"
                print(f"    - {email} ({member.role.value}, {member.status.value})")
            print()
        
        # Get all users
        users_result = await session.execute(select(User))
        users = users_result.scalars().all()
        
        print("=" * 60)
        print("All Users in Database")
        print("=" * 60)
        print(f"\nTotal users: {len(users)}\n")
        
        for user in users:
            print(f"User: {user.email}")
            print(f"  ID: {user.id}")
            print(f"  Full Name: {user.full_name}")
            print(f"  Global Role: {user.global_role.value if user.global_role else 'None'}")
            
            # Get workspace memberships
            memberships_result = await session.execute(
                select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
            )
            memberships = memberships_result.scalars().all()
            print(f"  Workspace Memberships ({len(memberships)}):")
            for membership in memberships:
                ws_result = await session.execute(
                    select(Workspace).where(Workspace.id == membership.workspace_id)
                )
                ws = ws_result.scalar_one_or_none()
                ws_name = ws.name if ws else "Unknown"
                print(f"    - {ws_name} ({membership.role.value}, {membership.status.value})")
            print()


if __name__ == "__main__":
    asyncio.run(check_workspaces())

