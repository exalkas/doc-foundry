"""Billing router endpoints for Stripe integration."""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, Header
from pydantic import BaseModel
from sqlalchemy import func, select
from app.models.commission import Commission
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_user,
    get_current_workspace,
    get_current_workspace_member,
    require_workspace_role,
)
from app.database import get_db
from app.models.subscription import Subscription, SubscriptionPlanEnum, SubscriptionStatusEnum
from app.models.template import Template
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceStatus
from app.services.authz_service import AuthzService
from app.services.logging_service import get_logger, set_correlation_id, ErrorCategory
from app.services.notification_service import NotificationService
from app.services.plan_service import PlanService
from app.services.stripe_service import StripeService, ENUM_TO_PLAN_ID_MAPPING
from app.services.usage_service import UsageService
from app.services.coupon_service import CouponService
from app.services.attribution_service import AttributionService

logger = get_logger(__name__)

router = APIRouter()


class PlanResponse(BaseModel):
    id: str
    name: str
    price: float
    interval: str
    features: List[str]


class SubscriptionResponse(BaseModel):
    id: str
    stripe_subscription_id: str
    plan_id: str
    status: str
    current_period_start: str
    current_period_end: str
    cancel_at_period_end: bool
    stripe_data: Dict[str, Any] | None = None


class CheckoutSessionResponse(BaseModel):
    url: str
    session_id: str


class PortalSessionResponse(BaseModel):
    url: str


class PaymentHistoryItem(BaseModel):
    id: str
    amount: float
    currency: str
    status: str
    created: str
    description: str


class PaymentHistoryResponse(BaseModel):
    data: List[PaymentHistoryItem]
    has_more: bool
    total: int
    page: int
    page_size: int


class ValidateCouponRequest(BaseModel):
    code: str
    plan_id: str


class ValidateCouponResponse(BaseModel):
    valid: bool
    error: Optional[str] = None
    discount_info: Optional[Dict[str, Any]] = None


@router.get("/plans", response_model=List[PlanResponse])
async def list_plans(
    db: AsyncSession = Depends(get_db),
) -> List[PlanResponse]:
    """List all available subscription plans."""
    logger.info("Listing available plans")
    plans = await PlanService.get_all_plans(db, active_only=True)
    return [
        PlanResponse(
            id=plan.plan_id,
            name=plan.name,
            price=float(plan.price),
            interval=plan.interval,
            features=plan.features if isinstance(plan.features, list) else [],
        )
        for plan in plans
    ]


@router.get("/subscription", response_model=SubscriptionResponse | None)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionResponse | None:
    """Get the current subscription for the user."""
    logger.info(f"Getting subscription for user: {current_user.id}")
    
    subscription_data = await StripeService.get_subscription(db, current_user)
    
    if not subscription_data:
        return None
    
    return SubscriptionResponse(**subscription_data)


@router.post("/validate-coupon", response_model=ValidateCouponResponse)
async def validate_coupon(
    request: ValidateCouponRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ValidateCouponResponse:
    """Validate a coupon code and return discount information."""
    logger.info(f"Validating coupon code for user {current_user.id}")
    
    is_valid, error_msg, discount_info = await CouponService.validate_coupon(
        db=db,
        code=request.code,
        plan_id=request.plan_id,
        customer_id=current_user.id,
    )
    
    if not is_valid:
        return ValidateCouponResponse(
            valid=False,
            error=error_msg,
            discount_info=None,
        )
    
    return ValidateCouponResponse(
        valid=True,
        error=None,
        discount_info=discount_info,
    )


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: Request,
    plan_id: str = Query(..., description="Plan ID to subscribe to"),
    coupon_code: Optional[str] = Query(None, description="Optional coupon code to apply"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckoutSessionResponse:
    """Create a Stripe checkout session for plan upgrade/downgrade with validation."""
    correlation_id = set_correlation_id()
    logger.info(
        "Creating checkout session",
        extra={
            "plan_id": plan_id,
            "user_id": str(current_user.id),
            "correlation_id": correlation_id,
        },
    )
    
    plan_service = PlanService()
    usage_service = UsageService()
    
    # Get plan from database
    target_plan = await PlanService.get_plan_by_id(db, plan_id)
    if not target_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan ID: {plan_id}",
        )
    
    if not target_plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan '{plan_id}' is not currently available",
        )
    
    # Handle free plan - no checkout needed
    if plan_id == "free":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Free plan is automatically assigned. Please contact support to downgrade.",
        )
    
    # Handle enterprise plan - custom pricing
    if plan_id == "enterprise":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enterprise plan requires custom pricing. Please contact sales.",
        )
    
    # Get current subscription
    subscription_result = await db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == current_user.id,
            Subscription.status.in_([SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING]),
        )
        .order_by(Subscription.created_at.desc())
    )
    current_subscription = subscription_result.scalar_one_or_none()
    
    # Map plan IDs to enum
    from app.services.stripe_service import PLAN_ID_TO_ENUM_MAPPING
    target_plan_enum = PLAN_ID_TO_ENUM_MAPPING.get(plan_id)
    
    if not target_plan_enum:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan ID: {plan_id}",
        )
    
    # Get current plan tier (convert enum to tier string)
    current_plan_tier = "free"
    if current_subscription:
        from app.services.stripe_service import ENUM_TO_PLAN_ID_MAPPING
        current_plan_id_str = ENUM_TO_PLAN_ID_MAPPING.get(current_subscription.plan_id, current_subscription.plan_id.value)
        # Map plan_id to tier for plan_service
        if current_plan_id_str in ["basic", "starter"]:
            current_plan_tier = "starter"
        elif current_plan_id_str == "pro":
            current_plan_tier = "pro"
        elif current_plan_id_str == "enterprise":
            current_plan_tier = "enterprise"
    
    # Map target plan to tier
    if plan_id in ["basic", "starter"]:
        target_plan_tier = "starter"
    elif plan_id == "pro":
        target_plan_tier = "pro"
    elif plan_id == "enterprise":
        target_plan_tier = "enterprise"
    else:
        target_plan_tier = "free"
    
    # If downgrading, validate that user can downgrade
    if current_subscription and current_plan_tier != "free":
        # Get current usage aggregated across all user's workspaces
        period_start = current_subscription.current_period_start
        period_end = current_subscription.current_period_end
        current_usage = await usage_service.get_user_usage(
            db, current_user.id, period_start, period_end
        )
        
        # Get current resources aggregated across all workspaces
        from app.models.workspacemember import WorkspaceMember
        workspace_members_result = await db.execute(
            select(WorkspaceMember.workspace_id).where(
                WorkspaceMember.user_id == current_user.id
            )
        )
        workspace_ids = [row[0] for row in workspace_members_result.all()]
        
        template_count = 0
        project_count = 0
        if workspace_ids:
            template_count_result = await db.execute(
                select(func.count(Template.id)).where(
                    Template.workspace_id.in_(workspace_ids)
                )
            )
            template_count = template_count_result.scalar_one()
            
            project_count_result = await db.execute(
                select(func.count(Project.id)).where(
                    Project.workspace_id.in_(workspace_ids)
                )
            )
            project_count = project_count_result.scalar_one()
        
        current_resources = {
            "templates": template_count,
            "projects": project_count,
        }
        
        can_downgrade, warnings = plan_service.can_downgrade(
            current_plan_tier,
            target_plan_tier,
            current_usage,
            current_resources,
        )
        
        if not can_downgrade:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot downgrade: {', '.join(warnings)}",
            )
    
    # Check for coupon code first (coupon attribution overrides cookie)
    coupon_id = None
    affiliate_id = None
    
    if coupon_code:
        # Validate coupon
        is_valid, error_msg, discount_info = await CouponService.validate_coupon(
            db=db,
            code=coupon_code,
            plan_id=plan_id,
            customer_id=current_user.id,
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg or "Invalid coupon code",
            )
        
        # Get coupon to check affiliate link
        coupon = await CouponService.get_coupon_by_code(db, coupon_code)
        if coupon:
            coupon_id = str(coupon.id)
            if coupon.affiliate_id:
                affiliate_id = str(coupon.affiliate_id)
                # Attribute via coupon (this overrides cookie attribution)
                await AttributionService.attribute_via_coupon(
                    db=db,
                    customer_id=current_user.id,
                    coupon_id=coupon.id,
                )
                logger.info(f"Attributed checkout via coupon {coupon_code} to affiliate {coupon.affiliate_id} for user {current_user.id}")
    
    # Check for affiliate cookie/attribution (only if no coupon)
    if not coupon_code:
        affiliate_slug = request.cookies.get(os.getenv("AFFILIATE_COOKIE_NAME", "aff_id"))
        if affiliate_slug:
            affiliate = await AttributionService.get_affiliate_from_cookie(db, affiliate_slug)
            if affiliate:
                affiliate_id = str(affiliate.id)
                # Create attribution if not exists
                await AttributionService.attribute_customer(
                    db=db,
                    customer_id=current_user.id,
                    affiliate_id=affiliate.id,
                    attribution_source="link",
                )
                logger.info(f"Attributed checkout to affiliate {affiliate.id} for user {current_user.id}")
    
    # Build success and cancel URLs - use frontend URL, not backend URL
    frontend_url = os.getenv("FRONTEND_URL", os.getenv("NEXT_PUBLIC_FRONTEND_URL", "http://localhost:3000"))
    frontend_url = frontend_url.rstrip("/")
    success_url = f"{frontend_url}/app/settings/usage-billing?success=true"
    cancel_url = f"{frontend_url}/app/settings/usage-billing?canceled=true"
    
    try:
        # Prepare metadata for Stripe
        metadata = {}
        if affiliate_id:
            metadata["affiliate_id"] = affiliate_id
        if coupon_code:
            metadata["coupon_code"] = coupon_code
        if coupon_id:
            metadata["coupon_id"] = coupon_id
        
        session_data = await StripeService.create_checkout_session(
            db=db,
            user=current_user,
            plan_id=plan_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
            coupon_code=coupon_code,
        )
        
        return CheckoutSessionResponse(**session_data)
    except ValueError as e:
        # Validation errors (missing price ID, invalid format, etc.)
        logger.warning(
            f"Validation error creating checkout session: {e}",
            error_category=ErrorCategory.USER_ERROR,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Failed to create checkout session: {e}",
            error_category=ErrorCategory.EXTERNAL_ERROR,
            exc_info=e,
        )
        # Return the actual error message if it's informative, otherwise generic
        error_detail = str(e) if str(e) else "Failed to create checkout session"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail,
        )


@router.post("/portal-session", response_model=PortalSessionResponse)
async def create_portal_session(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortalSessionResponse:
    """Create a Stripe customer portal session for managing billing."""
    logger.info(f"Creating portal session for user: {current_user.id}")
    
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a Stripe customer. Please subscribe to a plan first.",
        )
    
    # Use frontend URL, not backend URL
    frontend_url = os.getenv("FRONTEND_URL", os.getenv("NEXT_PUBLIC_FRONTEND_URL", "http://localhost:3000"))
    frontend_url = frontend_url.rstrip("/")
    return_url = f"{frontend_url}/app/settings/usage-billing"
    
    try:
        session_data = await StripeService.create_portal_session(
            db=db,
            user=current_user,
            return_url=return_url,
        )
        
        return PortalSessionResponse(**session_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Failed to create portal session: {e}",
            error_category=ErrorCategory.EXTERNAL_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create portal session",
        )


@router.post("/sync-subscription")
async def sync_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Manually sync subscription from Stripe (useful after checkout before webhook arrives)."""
    logger.info(f"Manually syncing subscription for user: {current_user.id}")
    
    try:
        subscription = await StripeService.sync_user_subscription(
            db=db,
            user=current_user,
        )
        
        if subscription:
            # Convert enum to plan_id string (use "basic" instead of "starter")
            from app.services.stripe_service import ENUM_TO_PLAN_ID_MAPPING
            plan_id_str = ENUM_TO_PLAN_ID_MAPPING.get(subscription.plan_id, subscription.plan_id.value)
            
            return {
                "success": True,
                "message": "Subscription synced successfully",
                "plan_id": plan_id_str,
                "status": subscription.status.value,
            }
        else:
            return {
                "success": False,
                "message": "No active subscription found in Stripe",
            }
    except Exception as e:
        logger.error(
            f"Failed to sync subscription: {e}",
            error_category=ErrorCategory.EXTERNAL_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync subscription: {str(e)}",
        )


@router.get("/payment-history", response_model=PaymentHistoryResponse)
async def get_payment_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    from_date: Optional[datetime] = Query(None, description="Filter payments from this date (ISO format)"),
    to_date: Optional[datetime] = Query(None, description="Filter payments until this date (ISO format)"),
    starting_after: Optional[str] = Query(None, description="Stripe pagination cursor"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentHistoryResponse:
    """Get payment history for the user with pagination and date filtering."""
    logger.info(f"Getting payment history for user: {current_user.id}")
    
    try:
        result = await StripeService.get_payment_history(
            db=db,
            user=current_user,
            limit=page_size,
            starting_after=starting_after,
            from_date=from_date,
            to_date=to_date,
        )
        
        return PaymentHistoryResponse(
            data=[PaymentHistoryItem(**item) for item in result["data"]],
            has_more=result["has_more"],
            total=result["total"],
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        logger.error(
            f"Failed to get payment history: {e}",
            error_category=ErrorCategory.EXTERNAL_ERROR,
            exc_info=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve payment history",
        )


@router.post("/webhook")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Handle Stripe webhook events with payment failure handling."""
    import stripe
    import os
    
    notification_service = NotificationService()
    
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured",
        )
    
    body = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(
            payload=body,
            sig_header=stripe_signature,
            secret=webhook_secret,
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        )
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )
    
    # Handle the event
    event_type = event["type"]
    logger.info(f"Received Stripe webhook event: {event_type}")
    
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        subscription_id = session.get("subscription")
        if subscription_id:
            await StripeService.sync_subscription_from_stripe(db, subscription_id)
            
            # Handle coupon redemption if coupon was used
            try:
                metadata = session.get("metadata", {})
                coupon_code = metadata.get("coupon_code")
                
                if coupon_code:
                    # Get subscription to find user
                    subscription_result = await db.execute(
                        select(Subscription).where(
                            Subscription.stripe_subscription_id == subscription_id
                        )
                    )
                    subscription = subscription_result.scalar_one_or_none()
                    
                    if subscription:
                        # Get plan ID from subscription
                        from app.services.stripe_service import ENUM_TO_PLAN_ID_MAPPING
                        plan_id = ENUM_TO_PLAN_ID_MAPPING.get(subscription.plan_id, subscription.plan_id.value)
                        
                        # Get invoice amount for discount calculation
                        invoice_id = session.get("invoice")
                        invoice_amount = 0.0
                        if invoice_id:
                            try:
                                import stripe
                                invoice = stripe.Invoice.retrieve(invoice_id)
                                invoice_amount = invoice.get("amount_due", 0) / 100.0
                            except Exception as e:
                                logger.warning(f"Failed to retrieve invoice for coupon redemption: {e}")
                        
                        # Apply coupon and create redemption record
                        coupon, redemption, error = await CouponService.apply_coupon(
                            db=db,
                            code=coupon_code,
                            customer_id=subscription.user_id,
                            plan_id=plan_id,
                            subscription_id=subscription.id,
                            subscription_amount=invoice_amount,
                        )
                        
                        if coupon and redemption:
                            logger.info(
                                f"Created coupon redemption {redemption.id} for coupon {coupon_code} "
                                f"on subscription {subscription.id}"
                            )
                            
                            # Attribute via coupon if not already attributed
                            if coupon.affiliate_id:
                                await AttributionService.attribute_via_coupon(
                                    db=db,
                                    customer_id=subscription.user_id,
                                    coupon_id=coupon.id,
                                )
            except Exception as e:
                logger.error(
                    f"Failed to handle coupon redemption in checkout.session.completed: {e}",
                    error_category=ErrorCategory.SYSTEM_ERROR,
                    exc_info=e,
                )
                # Don't fail the webhook if coupon redemption fails
    
    elif event_type in [
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ]:
        subscription_id = event["data"]["object"]["id"]
        await StripeService.sync_subscription_from_stripe(db, subscription_id)
    
    elif event_type == "invoice.payment_succeeded":
        invoice = event["data"]["object"]
        subscription_id = invoice.get("subscription")
        if subscription_id:
            await StripeService.sync_subscription_from_stripe(db, subscription_id)
            
            # Check for affiliate attribution and create commission
            try:
                # Get subscription to find user
                subscription_result = await db.execute(
                    select(Subscription).where(
                        Subscription.stripe_subscription_id == subscription_id
                    )
                )
                subscription = subscription_result.scalar_one_or_none()
                
                if subscription:
                    # Check for affiliate attribution
                    from app.models.affiliate_attribution import AffiliateAttribution
                    from app.services.commission_service import CommissionService
                    from app.models.commission import CommissionEventType
                    
                    attribution_result = await db.execute(
                        select(AffiliateAttribution).where(
                            AffiliateAttribution.customer_id == subscription.user_id
                        )
                    )
                    attribution = attribution_result.scalar_one_or_none()
                    
                    if attribution:
                        # Get invoice amount (in cents, convert to currency units)
                        amount_due = invoice.get("amount_due", 0) / 100.0
                        currency = invoice.get("currency", "eur").upper()
                        
                        # Determine event type (initial vs renewal)
                        # Check if this is the first invoice for this subscription
                        invoice_count_result = await db.execute(
                            select(func.count(Commission.id))
                            .where(
                                Commission.subscription_id == subscription.id,
                                Commission.affiliate_id == attribution.affiliate_id
                            )
                        )
                        existing_commissions = invoice_count_result.scalar() or 0
                        
                        event_type = CommissionEventType.INITIAL if existing_commissions == 0 else CommissionEventType.RENEWAL
                        
                        # Create commission
                        await CommissionService.create_commission(
                            db=db,
                            affiliate_id=attribution.affiliate_id,
                            customer_id=subscription.user_id,
                            subscription_id=subscription.id,
                            subscription_amount=amount_due,
                            currency=currency,
                            event_type=event_type,
                        )
                        logger.info(
                            f"Created {event_type.value} commission for affiliate {attribution.affiliate_id} "
                            f"on subscription {subscription.id}"
                        )
                    
                    # Also handle coupon redemption if coupon was used in checkout
                    try:
                        # Check if subscription metadata has coupon info
                        # (This might be in the checkout session metadata, not subscription metadata)
                        # For now, we handle it in checkout.session.completed above
                        pass
                    except Exception as e:
                        logger.error(
                            f"Failed to handle coupon redemption in invoice.payment_succeeded: {e}",
                            error_category=ErrorCategory.SYSTEM_ERROR,
                            exc_info=e,
                        )
            except Exception as e:
                logger.error(
                    f"Failed to create commission for invoice.payment_succeeded: {e}",
                    error_category=ErrorCategory.SYSTEM_ERROR,
                    exc_info=e,
                )
                # Don't fail the webhook if commission creation fails
    
    elif event_type == "invoice.payment_failed":
        invoice = event["data"]["object"]
        subscription_id = invoice.get("subscription")
        if subscription_id:
            # Get subscription and workspace
            subscription_result = await db.execute(
                select(Subscription).where(
                    Subscription.stripe_subscription_id == subscription_id
                )
            )
            subscription = subscription_result.scalar_one_or_none()
            
            if subscription:
                # Get user
                user_result = await db.execute(
                    select(User).where(User.id == subscription.user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if user:
                    # Send payment failure notification
                    try:
                        await notification_service.send_payment_failed(
                            user.email,
                            user.email,  # Use email as identifier since no workspace name
                            invoice.get("amount_due", 0) / 100.0,  # Convert cents to dollars
                            invoice.get("currency", "usd").upper(),
                            grace_period_days=7,
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to send payment failure notification: {e}",
                            error_category=ErrorCategory.SYSTEM_ERROR,
                            exc_info=e,
                        )
            
            await StripeService.sync_subscription_from_stripe(db, subscription_id)
    
    else:
        logger.info(f"Unhandled event type: {event_type}")
    
    return {"received": True}

