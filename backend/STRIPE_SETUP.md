# Stripe Setup Guide

## Getting Test API Keys (Free)

Stripe provides **free test API keys** for development and testing. You don't need to provide payment information to get test keys.

### Steps:

1. **Create a Stripe Account** (if you don't have one)

   - Go to https://stripe.com
   - Sign up for a free account (no credit card required for test mode)

2. **Get Your Test API Keys**

   - Go to https://dashboard.stripe.com/test/apikeys
   - You'll see two keys:
     - **Publishable key** (starts with `pk_test_...`) - Used in frontend
     - **Secret key** (starts with `sk_test_...`) - Used in backend

3. **Set Environment Variables**

   Create a `.env` file in the backend directory or set these environment variables:

   ```bash
   STRIPE_SECRET_KEY=replace_with_your_stripe_secret_key
   STRIPE_WEBHOOK_SECRET=replace_with_your_stripe_webhook_secret
   STRIPE_PRICE_ID_BASIC=price_your_basic_price_id  # Optional - create products in Stripe dashboard
   STRIPE_PRICE_ID_PRO=price_your_pro_price_id      # Optional - create products in Stripe dashboard
   ```

4. **Create Products in Stripe Dashboard** (Optional but Recommended)
   - Go to https://dashboard.stripe.com/test/products
   - Create products for "Basic" and "Pro" plans
   - Copy the Price IDs (they start with `price_...`)
   - Set them as `STRIPE_PRICE_ID_BASIC` and `STRIPE_PRICE_ID_PRO`

### Test Card Numbers

Stripe provides test card numbers for testing payments:

- **Success**: `4242 4242 4242 4242`
- **Decline**: `4000 0000 0000 0002`
- **Requires Authentication**: `4000 0025 0000 3155`

Use any future expiry date (e.g., 12/34) and any 3-digit CVC.

### Important Notes

- Test keys are **completely free** and don't charge real money
- Test keys only work in test mode
- Never commit your API keys to version control
- Use `.env` file (which should be in `.gitignore`) for local development
