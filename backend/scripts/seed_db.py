#!/usr/bin/env python3
"""
Seed database with initial data.

This script seeds the database with initial reference data such as:
- Admin user
- Sample workspace (optional)
- Reference data

Usage:
    python scripts/seed_db.py
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import bcrypt

# Load .env file and set up Python path
backend_dir = Path(__file__).parent.parent
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# Add backend directory to Python path so we can import 'app'
sys.path.insert(0, str(backend_dir))

# Import after environment is loaded and path is set
from app.database import AsyncSessionLocal
from app.models.user import User, GlobalUserRole, AuthProvider
from app.models.workspace import Workspace, WorkspaceStatus
from app.models.workspacemember import WorkspaceMember, WorkspaceMemberRole, WorkspaceMemberStatus


async def create_admin_user(session):
    """Create admin user if it doesn't exist."""
    # Check if admin user already exists
    from sqlalchemy import select
    result = await session.execute(
        select(User).where(User.email == "admin@example.com")
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        print("  ⚠ Admin user already exists, skipping...")
        return existing
    
    # Create admin user
    password_hash = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
    
    admin_user = User(
        email="admin@example.com",
        password_hash=password_hash,
        global_role=GlobalUserRole.ADMIN,
        full_name="System Administrator",
        is_email_verified=True,
        auth_provider=AuthProvider.LOCAL,
        is_active=True,
    )
    
    session.add(admin_user)
    await session.flush()
    
    print("  ✓ Created admin user (admin@example.com / admin123)")
    return admin_user


async def create_sample_workspace(session, admin_user):
    """Create a sample workspace if it doesn't exist."""
    from sqlalchemy import select
    
    # Check if workspace already exists
    result = await session.execute(
        select(Workspace).where(Workspace.name == "Sample Workspace")
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        print("  ⚠ Sample workspace already exists, skipping...")
        return existing
    
    # Create workspace
    workspace = Workspace(
        name="Sample Workspace",
        owner_user_id=admin_user.id,
        status=WorkspaceStatus.TRIAL,
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
    )
    
    session.add(workspace)
    await session.flush()
    
    # Create workspace member
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=admin_user.id,
        role=WorkspaceMemberRole.OWNER,
        status=WorkspaceMemberStatus.ACTIVE,
        invited_at=datetime.now(timezone.utc),
        joined_at=datetime.now(timezone.utc),
    )
    
    session.add(member)
    await session.flush()
    
    print("  ✓ Created sample workspace with admin as owner")
    return workspace


async def seed_database():
    """Seed database with initial data."""
    print("Seeding database with initial data...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Create admin user
            admin_user = await create_admin_user(session)
            
            # Create sample workspace
            await create_sample_workspace(session, admin_user)
            
            # Commit all changes
            await session.commit()
            
            print("\n✓ Database seeded successfully!")
            return True
            
        except Exception as e:
            await session.rollback()
            print(f"\n✗ Error seeding database: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """Main entry point."""
    print("=" * 60)
    print("Database Seeding")
    print("=" * 60)
    print()
    
    success = await seed_database()
    
    if success:
        print("\n" + "=" * 60)
        print("✓ Seeding complete!")
        print("=" * 60)
        print("\nDefault credentials:")
        print("  Email: admin@example.com")
        print("  Password: admin123")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("✗ Seeding failed!")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

