-- Migration: Update subscription_plan_enum to include free, starter, pro, enterprise
-- This migration is idempotent and safe to run multiple times.
-- Note: This migration handles the transition from basic/pro to free/starter/pro/enterprise

DO $$
BEGIN
    -- Check if 'free' already exists in the enum
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_enum 
        WHERE enumlabel = 'free' 
        AND enumtypid = (
            SELECT oid 
            FROM pg_type 
            WHERE typname = 'subscription_plan_enum'
        )
    ) THEN
        -- Add 'free' to the enum
        ALTER TYPE subscription_plan_enum ADD VALUE 'free';
        RAISE NOTICE 'Added ''free'' to subscription_plan_enum';
    ELSE
        RAISE NOTICE '''free'' already exists in subscription_plan_enum';
    END IF;

    -- Check if 'starter' already exists in the enum
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_enum 
        WHERE enumlabel = 'starter' 
        AND enumtypid = (
            SELECT oid 
            FROM pg_type 
            WHERE typname = 'subscription_plan_enum'
        )
    ) THEN
        -- Add 'starter' to the enum
        ALTER TYPE subscription_plan_enum ADD VALUE 'starter';
        RAISE NOTICE 'Added ''starter'' to subscription_plan_enum';
    ELSE
        RAISE NOTICE '''starter'' already exists in subscription_plan_enum';
    END IF;

    -- Check if 'enterprise' already exists in the enum
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_enum 
        WHERE enumlabel = 'enterprise' 
        AND enumtypid = (
            SELECT oid 
            FROM pg_type 
            WHERE typname = 'subscription_plan_enum'
        )
    ) THEN
        -- Add 'enterprise' to the enum
        ALTER TYPE subscription_plan_enum ADD VALUE 'enterprise';
        RAISE NOTICE 'Added ''enterprise'' to subscription_plan_enum';
    ELSE
        RAISE NOTICE '''enterprise'' already exists in subscription_plan_enum';
    END IF;

    -- Note: 'pro' should already exist. If you need to migrate from 'basic' to 'starter',
    -- you would need to update existing records first:
    -- UPDATE subscriptions SET plan_id = 'starter' WHERE plan_id = 'basic';
    -- Then you could optionally remove 'basic' from the enum (requires recreating the enum)
END $$;

