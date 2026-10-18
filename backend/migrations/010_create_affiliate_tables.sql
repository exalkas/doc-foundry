-- Migration: Create affiliate marketing tables
-- This migration is idempotent and safe to run multiple times.

DO $$
BEGIN
    -- Create affiliate_status_enum if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'affiliate_status_enum') THEN
        CREATE TYPE affiliate_status_enum AS ENUM (
            'pending',
            'approved',
            'rejected',
            'blocked'
        );
        RAISE NOTICE 'Created affiliate_status_enum type';
    END IF;

    -- Create commission_status_enum if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'commission_status_enum') THEN
        CREATE TYPE commission_status_enum AS ENUM (
            'pending',
            'cleared',
            'paid',
            'reversed'
        );
        RAISE NOTICE 'Created commission_status_enum type';
    END IF;

    -- Create commission_event_type_enum if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'commission_event_type_enum') THEN
        CREATE TYPE commission_event_type_enum AS ENUM (
            'initial',
            'renewal',
            'upgrade'
        );
        RAISE NOTICE 'Created commission_event_type_enum type';
    END IF;

    -- Create payout_status_enum if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payout_status_enum') THEN
        CREATE TYPE payout_status_enum AS ENUM (
            'requested',
            'approved',
            'paid',
            'rejected'
        );
        RAISE NOTICE 'Created payout_status_enum type';
    END IF;

    -- Create attribution_source_enum if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'attribution_source_enum') THEN
        CREATE TYPE attribution_source_enum AS ENUM (
            'link',
            'coupon'
        );
        RAISE NOTICE 'Created attribution_source_enum type';
    END IF;
END $$;

-- Create commission_plans table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_name = 'commission_plans'
    ) THEN
        CREATE TABLE commission_plans (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL UNIQUE,
            percentage DECIMAL(5, 2) NOT NULL CHECK (percentage >= 0 AND percentage <= 100),
            duration_months INTEGER NOT NULL CHECK (duration_months > 0),
            is_recurring BOOLEAN NOT NULL DEFAULT true,
            allowed_plans JSONB NOT NULL DEFAULT '[]'::jsonb,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX ix_commission_plans_is_active ON commission_plans(is_active);
        CREATE INDEX ix_commission_plans_name ON commission_plans(name);

        RAISE NOTICE 'Created commission_plans table';
    ELSE
        RAISE NOTICE 'commission_plans table already exists';
    END IF;
END $$;

-- Create affiliates table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_name = 'affiliates'
    ) THEN
        CREATE TABLE affiliates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            slug VARCHAR(100) NOT NULL UNIQUE,
            status affiliate_status_enum NOT NULL DEFAULT 'pending',
            commission_plan_id UUID REFERENCES commission_plans(id) ON DELETE SET NULL,
            company_name VARCHAR(255),
            website VARCHAR(512),
            payment_method_type VARCHAR(50),
            payment_details TEXT, -- Encrypted payment info (PayPal email, Wise details, etc.)
            country VARCHAR(100),
            tax_id VARCHAR(100),
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX ix_affiliates_user_id ON affiliates(user_id);
        CREATE INDEX ix_affiliates_slug ON affiliates(slug);
        CREATE INDEX ix_affiliates_status ON affiliates(status);
        CREATE INDEX ix_affiliates_commission_plan_id ON affiliates(commission_plan_id);
        CREATE UNIQUE INDEX ix_affiliates_user_id_unique ON affiliates(user_id);

        RAISE NOTICE 'Created affiliates table';
    ELSE
        RAISE NOTICE 'affiliates table already exists';
    END IF;
END $$;

-- Create affiliate_links table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_name = 'affiliate_links'
    ) THEN
        CREATE TABLE affiliate_links (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            affiliate_id UUID NOT NULL REFERENCES affiliates(id) ON DELETE CASCADE,
            slug VARCHAR(100) NOT NULL,
            destination_url VARCHAR(512) NOT NULL DEFAULT '/',
            campaign_id VARCHAR(100),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX ix_affiliate_links_affiliate_id ON affiliate_links(affiliate_id);
        CREATE INDEX ix_affiliate_links_slug ON affiliate_links(slug);
        CREATE UNIQUE INDEX ix_affiliate_links_slug_unique ON affiliate_links(slug);

        RAISE NOTICE 'Created affiliate_links table';
    ELSE
        RAISE NOTICE 'affiliate_links table already exists';
    END IF;
END $$;

-- Create affiliate_clicks table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_name = 'affiliate_clicks'
    ) THEN
        CREATE TABLE affiliate_clicks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            affiliate_link_id UUID NOT NULL REFERENCES affiliate_links(id) ON DELETE CASCADE,
            ip_hash VARCHAR(64), -- Hashed IP for privacy
            user_agent_hash VARCHAR(64), -- Hashed user agent for privacy
            referrer VARCHAR(512),
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX ix_affiliate_clicks_affiliate_link_id ON affiliate_clicks(affiliate_link_id);
        CREATE INDEX ix_affiliate_clicks_timestamp ON affiliate_clicks(timestamp);

        RAISE NOTICE 'Created affiliate_clicks table';
    ELSE
        RAISE NOTICE 'affiliate_clicks table already exists';
    END IF;
END $$;

-- Create affiliate_attributions table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_name = 'affiliate_attributions'
    ) THEN
        CREATE TABLE affiliate_attributions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            affiliate_id UUID NOT NULL REFERENCES affiliates(id) ON DELETE CASCADE,
            affiliate_link_id UUID REFERENCES affiliate_links(id) ON DELETE SET NULL,
            customer_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            attribution_source attribution_source_enum NOT NULL DEFAULT 'link',
            first_attributed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_attributed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX ix_affiliate_attributions_affiliate_id ON affiliate_attributions(affiliate_id);
        CREATE INDEX ix_affiliate_attributions_customer_id ON affiliate_attributions(customer_id);
        CREATE INDEX ix_affiliate_attributions_affiliate_link_id ON affiliate_attributions(affiliate_link_id);
        CREATE UNIQUE INDEX ix_affiliate_attributions_customer_id_unique ON affiliate_attributions(customer_id);

        RAISE NOTICE 'Created affiliate_attributions table';
    ELSE
        RAISE NOTICE 'affiliate_attributions table already exists';
    END IF;
END $$;

-- Create commissions table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_name = 'commissions'
    ) THEN
        CREATE TABLE commissions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            affiliate_id UUID NOT NULL REFERENCES affiliates(id) ON DELETE CASCADE,
            customer_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,
            event_type commission_event_type_enum NOT NULL,
            amount DECIMAL(10, 2) NOT NULL CHECK (amount >= 0),
            currency VARCHAR(3) NOT NULL DEFAULT 'EUR',
            status commission_status_enum NOT NULL DEFAULT 'pending',
            event_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            cleared_at TIMESTAMPTZ,
            payout_id UUID REFERENCES payouts(id) ON DELETE SET NULL,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX ix_commissions_affiliate_id ON commissions(affiliate_id);
        CREATE INDEX ix_commissions_customer_id ON commissions(customer_id);
        CREATE INDEX ix_commissions_subscription_id ON commissions(subscription_id);
        CREATE INDEX ix_commissions_status ON commissions(status);
        CREATE INDEX ix_commissions_event_date ON commissions(event_date);
        CREATE INDEX ix_commissions_payout_id ON commissions(payout_id);

        RAISE NOTICE 'Created commissions table';
    ELSE
        RAISE NOTICE 'commissions table already exists';
    END IF;
END $$;

-- Create payouts table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_name = 'payouts'
    ) THEN
        CREATE TABLE payouts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            affiliate_id UUID NOT NULL REFERENCES affiliates(id) ON DELETE CASCADE,
            amount DECIMAL(10, 2) NOT NULL CHECK (amount > 0),
            currency VARCHAR(3) NOT NULL DEFAULT 'EUR',
            status payout_status_enum NOT NULL DEFAULT 'requested',
            requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            processed_at TIMESTAMPTZ,
            payment_method VARCHAR(50),
            payment_reference VARCHAR(255),
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX ix_payouts_affiliate_id ON payouts(affiliate_id);
        CREATE INDEX ix_payouts_status ON payouts(status);
        CREATE INDEX ix_payouts_requested_at ON payouts(requested_at);

        RAISE NOTICE 'Created payouts table';
    ELSE
        RAISE NOTICE 'payouts table already exists';
    END IF;
END $$;

-- Add foreign key constraint for commissions.payout_id (circular dependency resolved)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.table_constraints 
        WHERE constraint_name = 'commissions_payout_id_fkey'
    ) THEN
        ALTER TABLE commissions 
        ADD CONSTRAINT commissions_payout_id_fkey 
        FOREIGN KEY (payout_id) REFERENCES payouts(id) ON DELETE SET NULL;
        
        RAISE NOTICE 'Added foreign key constraint for commissions.payout_id';
    END IF;
END $$;

-- Seed default commission plan (25% for 12 months)
DO $$
DECLARE
    plan_id UUID;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM commission_plans WHERE name = 'Standard') THEN
        INSERT INTO commission_plans (name, percentage, duration_months, is_recurring, allowed_plans, is_active)
        VALUES (
            'Standard',
            25.00,
            12,
            true,
            '["basic", "pro", "enterprise"]'::jsonb,
            true
        )
        RETURNING id INTO plan_id;
        
        RAISE NOTICE 'Created default commission plan (Standard: 25%% for 12 months)';
    END IF;
END $$;

