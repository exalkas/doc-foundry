-- Migration: Migrate from per-workspace billing to per-user billing
-- This migration moves subscriptions and Stripe customers from workspace to user level

-- Step 1: Add user_id column to subscriptions table (nullable initially)
ALTER TABLE subscriptions
ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;

-- Step 2: Add stripe_customer_id column to users table (nullable initially)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255);

-- Step 3: Create index on user_id in subscriptions for performance
CREATE INDEX IF NOT EXISTS ix_subscriptions_user_id ON subscriptions(user_id);

-- Step 4: Create index on stripe_customer_id in users for performance
CREATE INDEX IF NOT EXISTS ix_users_stripe_customer_id ON users(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;

-- Step 5: Migrate subscription data
-- For each subscription, set user_id to the workspace owner's user_id
UPDATE subscriptions s
SET user_id = w.owner_user_id
FROM workspaces w
WHERE s.workspace_id = w.id
  AND s.user_id IS NULL;

-- Step 6: Migrate Stripe customer data
-- For each workspace with a Stripe customer, move it to the owner user
-- If user already has a customer, keep the existing one (workspace customer is ignored)
UPDATE users u
SET stripe_customer_id = w.stripe_customer_id
FROM workspaces w
WHERE w.owner_user_id = u.id
  AND w.stripe_customer_id IS NOT NULL
  AND u.stripe_customer_id IS NULL;

-- Step 7: Make user_id NOT NULL in subscriptions (after data migration)
-- First, handle any subscriptions that couldn't be migrated (shouldn't happen, but safety check)
-- Delete subscriptions without a valid workspace (orphaned subscriptions)
DELETE FROM subscriptions
WHERE user_id IS NULL
  AND workspace_id NOT IN (SELECT id FROM workspaces);

-- Now make user_id NOT NULL
ALTER TABLE subscriptions
ALTER COLUMN user_id SET NOT NULL;

-- Step 8: Update unique constraint on subscriptions
-- Remove old constraint
ALTER TABLE subscriptions
DROP CONSTRAINT IF EXISTS uq_workspace_stripe_subscription;

-- Add new constraint for user_id + stripe_subscription_id
ALTER TABLE subscriptions
ADD CONSTRAINT uq_user_stripe_subscription UNIQUE (user_id, stripe_subscription_id);

-- Step 9: Update foreign key constraint
-- Drop old foreign key
ALTER TABLE subscriptions
DROP CONSTRAINT IF EXISTS subscriptions_workspace_id_fkey;

-- Note: We keep workspace_id column for historical tracking but remove the foreign key
-- This allows us to query historical data if needed, but new subscriptions won't use it

-- Step 10: Add comment to workspace_id column indicating it's deprecated
COMMENT ON COLUMN subscriptions.workspace_id IS 'DEPRECATED: Kept for historical tracking. Use user_id instead.';

-- Step 11: Add comment to stripe_customer_id in workspaces indicating it's deprecated
COMMENT ON COLUMN workspaces.stripe_customer_id IS 'DEPRECATED: Stripe customers are now stored on users table. This column will be removed in a future migration.';

-- Migration complete
-- Note: The workspace_id and workspace.stripe_customer_id columns are kept for now
-- They can be removed in a future migration after verifying everything works correctly

