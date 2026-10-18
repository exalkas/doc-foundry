"""Stripe service for handling billing operations."""

import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

import stripe
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.subscription import Subscription, SubscriptionPlanEnum, SubscriptionStatusEnum
from app.services.plan_service import PlanService

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Validate Stripe configuration
if not stripe.api_key:
    logger.warning(
        "STRIPE_SECRET_KEY not configured. Stripe functionality will not work. "
        "Get test keys from: https://dashboard.stripe.com/test/apikeys"
    )

# Plan ID mapping: Maps plan IDs to SubscriptionPlanEnum
# Note: "basic" and "starter" both map to SubscriptionPlanEnum.STARTER
PLAN_ID_TO_ENUM_MAPPING = {
    "free": SubscriptionPlanEnum.FREE,
    "basic": SubscriptionPlanEnum.STARTER,
    "starter": SubscriptionPlanEnum.STARTER,  # Alias for basic
    "pro": SubscriptionPlanEnum.PRO,
    "enterprise": SubscriptionPlanEnum.ENTERPRISE,
}

# Reverse mapping: SubscriptionPlanEnum to plan_id (prefer "basic" over "starter")
ENUM_TO_PLAN_ID_MAPPING = {
    SubscriptionPlanEnum.FREE: "free",
    SubscriptionPlanEnum.STARTER: "basic",  # Use "basic" as canonical
    SubscriptionPlanEnum.PRO: "pro",
    SubscriptionPlanEnum.ENTERPRISE: "enterprise",
}


class StripeService:
    """Service for interacting with Stripe API."""

    @staticmethod
    async def get_or_create_customer(
        db: AsyncSession, user: User
    ) -> str:
        """Get or create a Stripe customer for the user."""
        if user.stripe_customer_id:
            try:
                customer = stripe.Customer.retrieve(user.stripe_customer_id)
                return customer.id
            except stripe.error.StripeError as e:
                logger.warning(f"Stripe customer not found: {e}, creating new one")
        
        # Validate Stripe API key is configured
        if not stripe.api_key:
            raise ValueError(
                "Stripe API key not configured. Please set STRIPE_SECRET_KEY environment variable. "
                "Get test keys from: https://dashboard.stripe.com/test/apikeys"
            )
        
        # Create new customer
        try:
            customer = stripe.Customer.create(
                email=user.email,
                metadata={"user_id": str(user.id)},
            )
            
            user.stripe_customer_id = customer.id
            await db.commit()
            await db.refresh(user)
            
            logger.info(f"Created Stripe customer {customer.id} for user {user.id}")
            return customer.id
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe customer: {e}")
            raise

    @staticmethod
    async def create_checkout_session(
        db: AsyncSession,
        user: User,
        plan_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, str]] = None,
        coupon_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Stripe checkout session for plan subscription."""
        # Validate Stripe API key is configured
        if not stripe.api_key:
            raise ValueError(
                "Stripe API key not configured. Please set STRIPE_SECRET_KEY environment variable. "
                "Get free test keys from: https://dashboard.stripe.com/test/apikeys"
            )
        
        # Get plan from database
        plan = await PlanService.get_plan_by_id(db, plan_id)
        if not plan:
            raise ValueError(f"Invalid plan ID: {plan_id}")
        
        if not plan.is_active:
            raise ValueError(f"Plan '{plan_id}' is not currently available")
        
        price_id = (plan.stripe_price_id or "").strip()
        
        # Validate price ID
        if not price_id:
            raise ValueError(
                f"Stripe price ID not configured for plan '{plan_id}'. "
                f"Please set STRIPE_PRICE_ID_{plan_id.upper()} environment variable. "
                "Get price IDs from: https://dashboard.stripe.com/products"
            )
        
        # Detect placeholder values
        placeholder_patterns = [
            "price_XXXXXXXXXXXXX",
            "price_XXXX",
            "price_xxx",
            "price_example",
            "price_placeholder",
            "price_your_price_id",
        ]
        if price_id.lower() in [p.lower() for p in placeholder_patterns] or "XXXX" in price_id.upper():
            raise ValueError(
                f"Stripe price ID appears to be a placeholder value for plan '{plan_id}': '{price_id}'. "
                f"Please replace it with your actual Stripe price ID from the dashboard. "
                "Steps to get your price ID:\n"
                "1. Go to https://dashboard.stripe.com/test/products\n"
                "2. Click on your product (Basic or Pro)\n"
                "3. In the 'Pricing' section, find the price and copy its ID (starts with 'price_')\n"
                f"4. Update STRIPE_PRICE_ID_{plan_id.upper()} in your .env file with the actual price ID"
            )
        
        # Ensure it's a price ID, not a product ID
        if not price_id.startswith("price_"):
            raise ValueError(
                f"Invalid Stripe price ID format for plan '{plan_id}': '{price_id}'. "
                "Price IDs must start with 'price_'. "
                "If you have a product ID (starting with 'prod_'), you need to create a price for that product first. "
                "Get price IDs from: https://dashboard.stripe.com/products"
            )
        
        # Basic format validation - Stripe price IDs are typically 24+ characters after "price_"
        if len(price_id) < 30 or not price_id.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                f"Stripe price ID format looks invalid for plan '{plan_id}': '{price_id}'. "
                "Price IDs should be in format 'price_XXXXXXXXXXXXXXXX' (typically 24+ characters). "
                "Please verify you copied the correct price ID from https://dashboard.stripe.com/test/products"
            )
        
        customer_id = await StripeService.get_or_create_customer(db, user)
        
        try:
            # Prepare metadata
            session_metadata = {
                "user_id": str(user.id),
                "plan_id": plan_id,
            }
            if metadata:
                session_metadata.update(metadata)
            
            # Prepare discounts if coupon is provided
            discounts = []
            if coupon_code:
                # Get coupon to calculate discount
                from app.services.coupon_service import CouponService
                coupon = await CouponService.get_coupon_by_code(db, coupon_code)
                
                if coupon:
                    # Calculate discount for Stripe
                    # For percentage discounts, we can use Stripe's discount API
                    # For fixed amount, we need to calculate and apply as a discount
                    # Since Stripe subscriptions work with percentage discounts better,
                    # we'll create a Stripe coupon/promo code or use discounts parameter
                    
                    # Option: Use Stripe's promotion codes (requires creating promo codes in Stripe)
                    # Option: Calculate discount and pass as discounts parameter
                    # For now, we'll use allow_promotion_codes and let Stripe handle it
                    # OR we can create a discount object
                    
                    # For percentage discounts on subscriptions, Stripe supports:
                    # - Coupon objects with percentage_off
                    # - Promotion codes
                    # 
                    # Since we want to manage coupons in our DB, we'll:
                    # 1. Create a Stripe coupon if it doesn't exist (or use existing)
                    # 2. Apply it via discounts parameter
                    
                    # For simplicity, we'll use allow_promotion_codes: true
                    # and create Stripe promo codes manually, OR
                    # we can create discount objects dynamically
                    
                    # Better approach: Create Stripe coupon on-the-fly or use discounts array
                    # For percentage: create a Stripe coupon with percentage_off
                    # For fixed: create a Stripe coupon with amount_off
                    
                    try:
                        # Try to find or create Stripe coupon
                        stripe_coupon_id = None
                        
                        # Check if we have a Stripe coupon ID stored in coupon metadata
                        coupon_metadata = coupon.metadata_json or {}
                        stripe_coupon_id = coupon_metadata.get("stripe_coupon_id")
                        
                        if not stripe_coupon_id:
                            # Create Stripe coupon on-the-fly
                            stripe_coupon_params = {
                                "name": f"Coupon-{coupon.code}",
                            }
                            
                            if coupon.discount_type.value == "percentage":
                                stripe_coupon_params["percent_off"] = float(coupon.discount_value)
                            else:  # fixed
                                # For fixed amount, we need currency
                                # Default to EUR, but ideally get from plan
                                stripe_coupon_params["amount_off"] = int(coupon.discount_value * 100)  # Convert to cents
                                stripe_coupon_params["currency"] = "eur"
                            
                            # Set duration
                            if coupon.duration_type.value == "once":
                                stripe_coupon_params["duration"] = "once"
                            elif coupon.duration_type.value == "first_n_months":
                                stripe_coupon_params["duration"] = "repeating"
                                stripe_coupon_params["duration_in_months"] = coupon.duration_months or 1
                            else:  # until_date
                                # For until_date, we can't directly map to Stripe
                                # Use "once" or "repeating" with max duration
                                stripe_coupon_params["duration"] = "once"
                            
                            # Create Stripe coupon
                            stripe_coupon = stripe.Coupon.create(**stripe_coupon_params)
                            stripe_coupon_id = stripe_coupon.id
                            
                            # Store Stripe coupon ID in coupon metadata for future use
                            coupon_metadata["stripe_coupon_id"] = stripe_coupon_id
                            from app.services.coupon_service import CouponService
                            await CouponService.update_coupon(
                                db=db,
                                coupon_id=coupon.id,
                                metadata_json=coupon_metadata,
                            )
                        
                        if stripe_coupon_id:
                            discounts = [{"coupon": stripe_coupon_id}]
                    except Exception as e:
                        logger.warning(
                            f"Failed to create Stripe coupon for {coupon_code}: {e}. "
                            f"Proceeding without discount in Stripe (will handle in webhook)"
                        )
                        # Continue without Stripe discount - we'll handle it in webhook
            
            session_params = {
                "customer": customer_id,
                "payment_method_types": ["card"],
                "line_items": [
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                "mode": "subscription",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": session_metadata,
            }
            
            if discounts:
                session_params["discounts"] = discounts
            
            session = stripe.checkout.Session.create(**session_params)
            
            logger.info(f"Created checkout session {session.id} for user {user.id}")
            return {"url": session.url, "session_id": session.id}
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create checkout session: {e}")
            raise ValueError(f"Stripe error: {str(e)}") from e

    @staticmethod
    async def create_portal_session(
        db: AsyncSession,
        user: User,
        return_url: str,
    ) -> Dict[str, Any]:
        """Create a Stripe customer portal session."""
        if not user.stripe_customer_id:
            raise ValueError("User does not have a Stripe customer ID")
        
        try:
            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=return_url,
            )
            
            logger.info(f"Created portal session for user {user.id}")
            return {"url": session.url}
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create portal session: {e}")
            raise

    @staticmethod
    async def get_subscription(
        db: AsyncSession, user: User
    ) -> Optional[Dict[str, Any]]:
        """Get the current subscription for a user."""
        result = await db.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user.id,
                Subscription.status.in_([
                    SubscriptionStatusEnum.ACTIVE,
                    SubscriptionStatusEnum.TRIALING,
                ])
            )
            .order_by(Subscription.created_at.desc())
        )
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            return None
        
        try:
            stripe_sub = stripe.Subscription.retrieve(
                subscription.stripe_subscription_id
            )
            
            # Convert enum to plan_id string (use "basic" instead of "starter")
            plan_id_str = ENUM_TO_PLAN_ID_MAPPING.get(subscription.plan_id, subscription.plan_id.value)
            
            return {
                "id": str(subscription.id),
                "stripe_subscription_id": subscription.stripe_subscription_id,
                "plan_id": plan_id_str,
                "status": subscription.status.value,
                "current_period_start": subscription.current_period_start.isoformat(),
                "current_period_end": subscription.current_period_end.isoformat(),
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "stripe_data": {
                    "current_period_start": datetime.fromtimestamp(
                        stripe_sub.current_period_start
                    ).isoformat(),
                    "current_period_end": datetime.fromtimestamp(
                        stripe_sub.current_period_end
                    ).isoformat(),
                },
            }
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve Stripe subscription: {e}")
            # Return local data even if Stripe call fails
            # Convert enum to plan_id string (use "basic" instead of "starter")
            plan_id_str = ENUM_TO_PLAN_ID_MAPPING.get(subscription.plan_id, subscription.plan_id.value)
            
            return {
                "id": str(subscription.id),
                "stripe_subscription_id": subscription.stripe_subscription_id,
                "plan_id": plan_id_str,
                "status": subscription.status.value,
                "current_period_start": subscription.current_period_start.isoformat(),
                "current_period_end": subscription.current_period_end.isoformat(),
                "cancel_at_period_end": subscription.cancel_at_period_end,
            }

    @staticmethod
    async def get_payment_history(
        db: AsyncSession,
        user: User,
        limit: int = 10,
        starting_after: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get payment history for a user with pagination and date filtering.
        
        Returns:
            Dictionary with 'data' (list of charges) and 'has_more' (boolean)
        """
        if not user.stripe_customer_id:
            return {"data": [], "has_more": False, "total": 0}
        
        try:
            # Build Stripe API parameters
            params: Dict[str, Any] = {
                "customer": user.stripe_customer_id,
                "limit": limit,
            }
            
            if starting_after:
                params["starting_after"] = starting_after
            
            # Stripe uses Unix timestamps for date filtering
            if from_date:
                params["created"] = {"gte": int(from_date.timestamp())}
            if to_date:
                if "created" in params:
                    params["created"]["lte"] = int(to_date.timestamp())
                else:
                    params["created"] = {"lte": int(to_date.timestamp())}
            
            charges = stripe.Charge.list(**params)
            
            history = []
            for charge in charges.data:
                history.append({
                    "id": charge.id,
                    "amount": charge.amount / 100,  # Convert from cents
                    "currency": charge.currency,
                    "status": charge.status,
                    "created": datetime.fromtimestamp(charge.created).isoformat(),
                    "description": charge.description or "",
                })
            
            return {
                "data": history,
                "has_more": charges.has_more,
                "total": len(history),  # Approximate, Stripe doesn't provide exact total
            }
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve payment history: {e}")
            return {"data": [], "has_more": False, "total": 0}

    @staticmethod
    async def sync_subscription_from_stripe(
        db: AsyncSession,
        stripe_subscription_id: str,
    ) -> Optional[Subscription]:
        """Sync subscription data from Stripe webhook."""
        try:
            stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
            
            # Find user by customer ID
            customer_id = stripe_sub.customer
            result = await db.execute(
                select(User).where(User.stripe_customer_id == customer_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                logger.warning(f"User not found for Stripe customer {customer_id}")
                return None
            
            # Find or create subscription record
            sub_result = await db.execute(
                select(Subscription).where(
                    Subscription.stripe_subscription_id == stripe_subscription_id
                )
            )
            subscription = sub_result.scalar_one_or_none()
            
            # Determine plan ID from metadata or price
            plan_id = SubscriptionPlanEnum.STARTER
            
            # Convert Stripe object to dict for easier access
            if hasattr(stripe_sub, 'to_dict'):
                sub_dict = stripe_sub.to_dict()
            elif isinstance(stripe_sub, dict):
                sub_dict = stripe_sub
            else:
                # Try to access as object attributes
                sub_dict = {
                    'items': getattr(stripe_sub, 'items', None),
                    'metadata': getattr(stripe_sub, 'metadata', {}),
                }
            
            # First, try to get plan_id from metadata (most reliable, set during checkout)
            metadata = sub_dict.get('metadata', {}) or (getattr(stripe_sub, 'metadata', None) or {})
            if isinstance(metadata, dict) and metadata.get('plan_id'):
                metadata_plan = metadata['plan_id']
                if metadata_plan in PLAN_ID_TO_ENUM_MAPPING:
                    plan_id = PLAN_ID_TO_ENUM_MAPPING[metadata_plan]
                    logger.info(f"Using plan_id from metadata: {metadata_plan} -> {plan_id.value}")
            
            # If not in metadata, try to get from price ID
            if plan_id == SubscriptionPlanEnum.STARTER:  # Only if we haven't set it from metadata
                items_obj = sub_dict.get('items') or getattr(stripe_sub, 'items', None)
                
                # Handle different ways items might be structured
                items_data = None
                if items_obj:
                    if hasattr(items_obj, 'data'):
                        items_data = items_obj.data
                    elif isinstance(items_obj, dict) and 'data' in items_obj:
                        items_data = items_obj['data']
                    elif isinstance(items_obj, list):
                        items_data = items_obj
                
                if items_data and len(items_data) > 0:
                    # Get the first item's price ID
                    first_item = items_data[0]
                    price_id = None
                    
                    if isinstance(first_item, dict):
                        price_obj = first_item.get('price', {})
                        price_id = price_obj.get('id') if isinstance(price_obj, dict) else str(price_obj)
                    elif hasattr(first_item, 'price'):
                        price_obj = first_item.price
                        price_id = price_obj.id if hasattr(price_obj, 'id') else str(price_obj)
                    
                    if price_id:
                        # Match price ID to plan in database
                        db_plan = await PlanService.get_plan_by_stripe_price_id(db, price_id)
                        if db_plan:
                            plan_id = PLAN_ID_TO_ENUM_MAPPING.get(db_plan.plan_id, SubscriptionPlanEnum.STARTER)
                            logger.info(f"Matched price ID {price_id} to plan {db_plan.plan_id} -> {plan_id.value}")
                        else:
                            logger.warning(f"Price ID {price_id} not found in database, defaulting to STARTER")
            
            # Map Stripe status to our enum
            status_map = {
                "active": SubscriptionStatusEnum.ACTIVE,
                "trialing": SubscriptionStatusEnum.TRIALING,
                "past_due": SubscriptionStatusEnum.PAST_DUE,
                "canceled": SubscriptionStatusEnum.CANCELED,
            }
            status = status_map.get(stripe_sub.status, SubscriptionStatusEnum.CANCELED)
            
            if subscription:
                # Update existing
                logger.info(
                    f"Updating existing subscription {subscription.id} for user {user.id}: "
                    f"plan_id={plan_id.value}, status={status.value}"
                )
                subscription.plan_id = plan_id
                subscription.status = status
                subscription.current_period_start = datetime.fromtimestamp(
                    stripe_sub.current_period_start
                )
                subscription.current_period_end = datetime.fromtimestamp(
                    stripe_sub.current_period_end
                )
                subscription.cancel_at_period_end = stripe_sub.cancel_at_period_end
            else:
                # Create new
                logger.info(
                    f"Creating new subscription for user {user.id}: "
                    f"plan_id={plan_id.value}, status={status.value}"
                )
                subscription = Subscription(
                    user_id=user.id,
                    stripe_subscription_id=stripe_subscription_id,
                    plan_id=plan_id,
                    status=status,
                    current_period_start=datetime.fromtimestamp(
                        stripe_sub.current_period_start
                    ),
                    current_period_end=datetime.fromtimestamp(
                        stripe_sub.current_period_end
                    ),
                    cancel_at_period_end=stripe_sub.cancel_at_period_end,
                )
                db.add(subscription)
            
            await db.commit()
            await db.refresh(subscription)
            
            logger.info(
                f"Synced subscription {stripe_subscription_id} for user {user.id}: "
                f"plan_id={subscription.plan_id.value}, status={subscription.status.value}"
            )
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to sync subscription from Stripe: {e}")
            await db.rollback()
            return None

    @staticmethod
    async def sync_user_subscription(
        db: AsyncSession,
        user: User,
    ) -> Optional[Subscription]:
        """Sync subscription for a user by finding active subscriptions from Stripe."""
        if not user.stripe_customer_id:
            logger.info(f"User {user.id} has no Stripe customer ID")
            return None
        
        try:
            # Get subscriptions for this customer using Stripe API
            # stripe.Subscription.list() returns a ListObject with a .data attribute
            result = stripe.Subscription.list(
                customer=user.stripe_customer_id,
                limit=10,
            )
            
            # The result is a ListObject - access .data to get the actual list
            # Handle both cases: if it's already a list or if it has .data attribute
            if hasattr(result, 'data'):
                subscriptions = result.data
            elif isinstance(result, list):
                subscriptions = result
            else:
                # Try to iterate over it
                subscriptions = [item for item in result]
            
            if not subscriptions:
                logger.info(f"No subscriptions found for user {user.id}")
                return None
            
            # Find the most recent active or trialing subscription
            active_subscription = None
            for sub in subscriptions:
                if sub.status in ["active", "trialing"]:
                    active_subscription = sub
                    break
            
            # If no active subscription, get the most recent one
            if not active_subscription:
                active_subscription = subscriptions[0]
            
            if not active_subscription:
                logger.info(f"No valid subscription found for user {user.id}")
                return None
            
            # Sync the found subscription
            return await StripeService.sync_subscription_from_stripe(
                db, active_subscription.id
            )
        except stripe.error.StripeError as e:
            logger.error(f"Failed to sync user subscription from Stripe: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error syncing user subscription: {e}", exc_info=True)
            return None

