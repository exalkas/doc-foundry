#!/usr/bin/env python3
"""Apply subscription user_id migration directly."""

import asyncio
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import engine
from sqlalchemy import text

async def apply_migration():
    """Apply the subscription user_id migration."""
    async with engine.begin() as conn:
        # Step 1: Add user_id column (nullable initially)
        print("  Adding user_id column...")
        try:
            await conn.execute(
                text("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE")
            )
        except Exception as e:
            if 'already exists' not in str(e).lower():
                raise
        
        # Step 2: Add stripe_customer_id to users if not exists
        print("  Adding stripe_customer_id to users...")
        try:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255)")
            )
        except Exception as e:
            if 'already exists' not in str(e).lower():
                raise
        
        # Step 3: Create indexes
        print("  Creating indexes...")
        try:
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_subscriptions_user_id ON subscriptions(user_id)")
            )
        except Exception as e:
            if 'already exists' not in str(e).lower():
                raise
        
        try:
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_users_stripe_customer_id ON users(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL")
            )
        except Exception as e:
            if 'already exists' not in str(e).lower():
                raise
        
        # Step 4: Migrate data - set user_id from workspace owner
        print("  Migrating subscription data...")
        await conn.execute(
            text("""
                UPDATE subscriptions s
                SET user_id = w.owner_user_id
                FROM workspaces w
                WHERE s.workspace_id = w.id
                  AND s.user_id IS NULL
            """)
        )
        
        # Step 5: Migrate Stripe customer data
        print("  Migrating Stripe customer data...")
        await conn.execute(
            text("""
                UPDATE users u
                SET stripe_customer_id = w.stripe_customer_id
                FROM workspaces w
                WHERE w.owner_user_id = u.id
                  AND w.stripe_customer_id IS NOT NULL
                  AND u.stripe_customer_id IS NULL
            """)
        )
        
        # Step 6: Delete orphaned subscriptions
        print("  Cleaning up orphaned subscriptions...")
        await conn.execute(
            text("""
                DELETE FROM subscriptions
                WHERE user_id IS NULL
                  AND workspace_id NOT IN (SELECT id FROM workspaces)
            """)
        )
        
        # Step 7: Make user_id NOT NULL (only if all subscriptions have user_id)
        print("  Making user_id NOT NULL...")
        try:
            # Check if any subscriptions still have NULL user_id
            result = await conn.execute(
                text("SELECT COUNT(*) FROM subscriptions WHERE user_id IS NULL")
            )
            null_count = result.scalar()
            
            if null_count == 0:
                await conn.execute(
                    text("ALTER TABLE subscriptions ALTER COLUMN user_id SET NOT NULL")
                )
            else:
                print(f"    ⚠ Warning: {null_count} subscriptions still have NULL user_id, skipping NOT NULL constraint")
        except Exception as e:
            print(f"    ⚠ Warning: Could not set NOT NULL: {e}")
        
        # Step 8: Update constraints
        print("  Updating constraints...")
        try:
            await conn.execute(
                text("ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS uq_workspace_stripe_subscription")
            )
        except Exception:
            pass
        
        try:
            await conn.execute(
                text("ALTER TABLE subscriptions ADD CONSTRAINT uq_user_stripe_subscription UNIQUE (user_id, stripe_subscription_id)")
            )
        except Exception as e:
            if 'already exists' not in str(e).lower():
                print(f"    ⚠ Warning: Could not add unique constraint: {e}")
        
        try:
            await conn.execute(
                text("ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS subscriptions_workspace_id_fkey")
            )
        except Exception:
            pass
    
    print("✓ Subscription migration applied successfully!")

if __name__ == "__main__":
    asyncio.run(apply_migration())

