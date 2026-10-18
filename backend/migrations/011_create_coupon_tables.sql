-- Migration: Create coupon tables for affiliate marketing
-- This migration is idempotent and safe to run multiple times.

DO $$
BEGIN
    -- Create coupon_status_enum if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'coupon_status_enum') THEN
        CREATE TYPE coupon_status_enum AS ENUM (
            'active',
            'paused',
            'expired'
        );
        RAISE NOTICE 'Created coupon_status_enum type';
    END IF;

    -- Create discount_type_enum if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'discount_type_enum') THEN
        CREATE TYPE discount_type_enum AS ENUM (
            'percentage',
            'fixed'
        );
        RAISE NOTICE 'Created discount_type_enum type';
    END IF;

    -- Create duration_type_enum if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'duration_type_enum') THEN
        CREATE TYPE duration_type_enum AS ENUM (
            'once',
            'first_n_months',
            'until_date'
        );
        RAISE NOTICE 'Created duration_type_enum type';
    END IF;
END $$;

-- Create coupons table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_name = 'coupons'
    ) THEN
        CREATE TABLE coupons (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            code VARCHAR(100) NOT NULL UNIQUE,
            discount_type discount_type_enum NOT NULL,
            discount_value DECIMAL(10, 2) NOT NULL CHECK (discount_value >= 0),
            duration_type duration_type_enum NOT NULL DEFAULT 'once',
            duration_months INTEGER,
            expires_at TIMESTAMPTZ,
            max_redemptions INTEGER CHECK (max_redemptions IS NULL OR max_redemptions > 0),
            max_redemptions_per_customer INTEGER DEFAULT 1 CHECK (max_redemptions_per_customer > 0),
            eligible_plans JSONB NOT NULL DEFAULT '[]'::jsonb,
            affiliate_id UUID REFERENCES affiliates(id) ON DELETE SET NULL,
            status coupon_status_enum NOT NULL DEFAULT 'active',
            stackable BOOLEAN NOT NULL DEFAULT false,
            allow_lifetime_discount BOOLEAN NOT NULL DEFAULT false,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX ix_coupons_code ON coupons(LOWER(code));
        CREATE INDEX ix_coupons_affiliate_id ON coupons(affiliate_id);
        CREATE INDEX ix_coupons_status ON coupons(status);
        CREATE INDEX ix_coupons_expires_at ON coupons(expires_at);
        CREATE UNIQUE INDEX ix_coupons_code_lower_unique ON coupons(LOWER(code));

        RAISE NOTICE 'Created coupons table';
    ELSE
        RAISE NOTICE 'coupons table already exists';
    END IF;
END $$;

-- Create coupon_redemptions table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_name = 'coupon_redemptions'
    ) THEN
        CREATE TABLE coupon_redemptions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            coupon_id UUID NOT NULL REFERENCES coupons(id) ON DELETE CASCADE,
            customer_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,
            used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            discount_applied DECIMAL(10, 2) NOT NULL CHECK (discount_applied >= 0)
        );

        CREATE INDEX ix_coupon_redemptions_coupon_id ON coupon_redemptions(coupon_id);
        CREATE INDEX ix_coupon_redemptions_customer_id ON coupon_redemptions(customer_id);
        CREATE INDEX ix_coupon_redemptions_subscription_id ON coupon_redemptions(subscription_id);
        CREATE INDEX ix_coupon_redemptions_used_at ON coupon_redemptions(used_at);

        RAISE NOTICE 'Created coupon_redemptions table';
    ELSE
        RAISE NOTICE 'coupon_redemptions table already exists';
    END IF;
END $$;

