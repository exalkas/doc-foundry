-- Migration: Create plans table for database-driven plan management
-- This migration is idempotent and safe to run multiple times.

DO $$
BEGIN
    -- Check if table already exists
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_name = 'plans'
    ) THEN
        -- Create plans table
        CREATE TABLE plans (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            plan_id VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            price DECIMAL(10, 2) NOT NULL DEFAULT 0,
            interval VARCHAR(20) NOT NULL DEFAULT 'month',
            stripe_price_id VARCHAR(255),
            display_order INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT true,
            features JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        -- Create index on plan_id for fast lookups
        CREATE INDEX idx_plans_plan_id ON plans(plan_id);
        
        -- Create index on stripe_price_id for Stripe sync
        CREATE INDEX idx_plans_stripe_price_id ON plans(stripe_price_id) WHERE stripe_price_id IS NOT NULL;
        
        -- Create index on display_order for ordering
        CREATE INDEX idx_plans_display_order ON plans(display_order);
        
        -- Create index on is_active for filtering active plans
        CREATE INDEX idx_plans_is_active ON plans(is_active) WHERE is_active = true;

        RAISE NOTICE 'Created plans table';
    ELSE
        RAISE NOTICE 'plans table already exists';
    END IF;
END $$;

-- Seed initial plans from existing PLANS dictionary
-- Note: stripe_price_id should be set via environment variables after migration
DO $$
BEGIN
    -- Insert Free plan
    IF NOT EXISTS (SELECT 1 FROM plans WHERE plan_id = 'free') THEN
        INSERT INTO plans (plan_id, name, price, interval, stripe_price_id, display_order, is_active, features)
        VALUES (
            'free',
            'Free',
            0,
            'month',
            NULL,
            1,
            true,
            '["Up to 100 pages per month", "1 team member", "Up to 3 extraction templates", "1 project", "Email support", "API access"]'::jsonb
        );
    END IF;

    -- Insert Basic/Starter plan
    IF NOT EXISTS (SELECT 1 FROM plans WHERE plan_id = 'basic') THEN
        INSERT INTO plans (plan_id, name, price, interval, stripe_price_id, display_order, is_active, features)
        VALUES (
            'basic',
            'Basic',
            29,
            'month',
            NULL, -- Will be set from STRIPE_PRICE_ID_BASIC env var
            2,
            true,
            '["Up to 1,000 pages per month", "1 team member", "Up to 5 extraction templates", "Email support", "API & webhook access"]'::jsonb
        );
    END IF;

    -- Insert Pro plan
    IF NOT EXISTS (SELECT 1 FROM plans WHERE plan_id = 'pro') THEN
        INSERT INTO plans (plan_id, name, price, interval, stripe_price_id, display_order, is_active, features)
        VALUES (
            'pro',
            'Pro',
            99,
            'month',
            NULL, -- Will be set from STRIPE_PRICE_ID_PRO env var
            3,
            true,
            '["Up to 10,000 pages per month", "5 team members", "Unlimited extraction templates", "Priority support", "API & webhook access", "Zapier/Make/n8n integrations"]'::jsonb
        );
    END IF;

    -- Insert Enterprise plan
    IF NOT EXISTS (SELECT 1 FROM plans WHERE plan_id = 'enterprise') THEN
        INSERT INTO plans (plan_id, name, price, interval, stripe_price_id, display_order, is_active, features)
        VALUES (
            'enterprise',
            'Enterprise',
            0, -- Custom pricing
            'month',
            NULL,
            4,
            true,
            '["Unlimited pages", "Unlimited team members", "Unlimited extraction templates", "Unlimited projects", "Dedicated support", "SSO & custom branding", "Custom integrations", "SLA guarantee", "10-year data retention"]'::jsonb
        );
    END IF;

    RAISE NOTICE 'Seeded initial plans';
END $$;

