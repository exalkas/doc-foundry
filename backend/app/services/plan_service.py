"""Plan service for managing subscription plans, limits, and feature flags."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Plan

logger = logging.getLogger(__name__)


class PlanTier(str, Enum):
    """Subscription plan tiers."""

    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass
class PlanLimits:
    """Plan limits and quotas."""

    # Pricing
    monthly_base_price: float
    included_pages_per_month: int
    overage_price_per_1000_pages: float

    # File limits
    max_pages_per_document: int
    max_file_size_mb: int
    max_image_dimensions: tuple[int, int]  # (width, height)

    # Usage limits
    max_concurrent_jobs: int
    max_templates: Optional[int]  # None = unlimited
    max_projects: Optional[int]  # None = unlimited

    # Features
    webhooks_enabled: bool
    api_keys_enabled: bool
    max_api_keys: Optional[int]  # None = unlimited
    priority_queue: bool
    integrations_enabled: bool  # Make/Zapier/n8n
    sso_enabled: bool
    custom_branding: bool

    # AI Extraction
    ai_extraction_enabled: bool
    included_ai_pages_per_month: int  # Included AI pages in plan
    ai_page_price: float  # Price per AI page for pay-as-you-go

    # Retention
    retention_days: int

    # Retry limits
    max_retries: int

    # Hard vs soft limits
    hard_limit_enforced: bool  # True = stop at quota, False = allow overage

    # Confidence thresholds for extraction review
    confidence_threshold: float  # Extractions below this require review


# Plan definitions
PLAN_DEFINITIONS: Dict[PlanTier, PlanLimits] = {
    PlanTier.FREE: PlanLimits(
        monthly_base_price=0.0,
        included_pages_per_month=50,
        overage_price_per_1000_pages=0.0,  # No overage allowed
        max_pages_per_document=10,
        max_file_size_mb=5,
        max_image_dimensions=(2000, 2000),
        max_concurrent_jobs=1,
        max_templates=1,
        max_projects=1,
        webhooks_enabled=False,
        api_keys_enabled=False,
        max_api_keys=0,
        priority_queue=False,
        integrations_enabled=False,
        sso_enabled=False,
        custom_branding=False,
        ai_extraction_enabled=False,
        included_ai_pages_per_month=0,
        ai_page_price=0.0,
        retention_days=30,
        max_retries=1,
        hard_limit_enforced=True,
        confidence_threshold=0.7,  # Free plan: lower threshold
    ),
    PlanTier.STARTER: PlanLimits(
        monthly_base_price=29.0,
        included_pages_per_month=500,
        overage_price_per_1000_pages=5.0,
        max_pages_per_document=50,
        max_file_size_mb=25,
        max_image_dimensions=(4000, 4000),
        max_concurrent_jobs=5,
        max_templates=10,
        max_projects=3,
        webhooks_enabled=True,
        api_keys_enabled=True,
        max_api_keys=1,
        priority_queue=False,
        integrations_enabled=False,  # Make/Zapier only in Pro+
        sso_enabled=False,
        custom_branding=False,
        ai_extraction_enabled=True,
        included_ai_pages_per_month=0,  # Pay-as-you-go only
        ai_page_price=0.03,  # $0.03 per AI page
        retention_days=90,
        max_retries=3,
        hard_limit_enforced=False,
        confidence_threshold=0.8,  # Starter plan
    ),
    PlanTier.PRO: PlanLimits(
        monthly_base_price=99.0,
        included_pages_per_month=5000,
        overage_price_per_1000_pages=3.0,
        max_pages_per_document=200,
        max_file_size_mb=100,
        max_image_dimensions=(8000, 8000),
        max_concurrent_jobs=20,
        max_templates=None,  # Unlimited
        max_projects=None,  # Unlimited
        webhooks_enabled=True,
        api_keys_enabled=True,
        max_api_keys=None,  # Unlimited
        priority_queue=True,
        integrations_enabled=True,  # Make.com / Zapier integrations
        sso_enabled=False,
        custom_branding=True,
        ai_extraction_enabled=True,
        included_ai_pages_per_month=500,  # 500 AI pages included
        ai_page_price=0.02,  # $0.02 per additional AI page
        retention_days=365,
        max_retries=5,
        hard_limit_enforced=False,
        confidence_threshold=0.85,  # Pro plan
    ),
    PlanTier.ENTERPRISE: PlanLimits(
        monthly_base_price=0.0,  # Custom pricing
        included_pages_per_month=0,  # Custom quota
        overage_price_per_1000_pages=0.0,  # Custom pricing
        max_pages_per_document=1000,
        max_file_size_mb=500,
        max_image_dimensions=(16000, 16000),
        max_concurrent_jobs=100,
        max_templates=None,  # Unlimited
        max_projects=None,  # Unlimited
        webhooks_enabled=True,
        api_keys_enabled=True,
        max_api_keys=None,  # Unlimited
        priority_queue=True,  # Dedicated extraction queue
        integrations_enabled=True,
        sso_enabled=True,
        custom_branding=True,
        ai_extraction_enabled=True,
        included_ai_pages_per_month=0,  # Custom quota
        ai_page_price=0.0,  # Custom pricing
        retention_days=3650,  # 10 years
        max_retries=10,
        hard_limit_enforced=False,
        confidence_threshold=0.9,  # Enterprise plan: highest threshold
    ),
}


class PlanService:
    """Service for managing subscription plans and limits."""

    @staticmethod
    def get_plan_limits(plan_tier: str) -> PlanLimits:
        """Get plan limits for a given plan tier.

        Args:
            plan_tier: Plan tier identifier (free, starter, pro, enterprise)

        Returns:
            PlanLimits object

        Raises:
            ValueError: If plan tier is invalid
        """
        try:
            tier = PlanTier(plan_tier.lower())
            return PLAN_DEFINITIONS[tier]
        except ValueError:
            raise ValueError(f"Invalid plan tier: {plan_tier}")

    @staticmethod
    def check_feature_enabled(plan_tier: str, feature: str) -> bool:
        """Check if a feature is enabled for a plan.

        Args:
            plan_tier: Plan tier identifier
            feature: Feature name (webhooks, api_keys, priority_queue, etc.)

        Returns:
            True if feature is enabled
        """
        limits = PlanService.get_plan_limits(plan_tier)
        feature_map = {
            "webhooks": limits.webhooks_enabled,
            "api_keys": limits.api_keys_enabled,
            "priority_queue": limits.priority_queue,
            "integrations": limits.integrations_enabled,
            "sso": limits.sso_enabled,
            "custom_branding": limits.custom_branding,
        }
        return feature_map.get(feature, False)

    @staticmethod
    def check_file_size_limit(plan_tier: str, file_size_mb: float) -> tuple[bool, Optional[str]]:
        """Check if file size is within plan limits.

        Args:
            plan_tier: Plan tier identifier
            file_size_mb: File size in megabytes

        Returns:
            Tuple of (is_valid, error_message)
        """
        limits = PlanService.get_plan_limits(plan_tier)
        if file_size_mb > limits.max_file_size_mb:
            return (
                False,
                f"File size {file_size_mb}MB exceeds plan limit of {limits.max_file_size_mb}MB",
            )
        return True, None

    @staticmethod
    def check_pages_limit(plan_tier: str, page_count: int) -> tuple[bool, Optional[str]]:
        """Check if page count is within plan limits.

        Args:
            plan_tier: Plan tier identifier
            page_count: Number of pages

        Returns:
            Tuple of (is_valid, error_message)
        """
        limits = PlanService.get_plan_limits(plan_tier)
        if page_count > limits.max_pages_per_document:
            return (
                False,
                f"Page count {page_count} exceeds plan limit of {limits.max_pages_per_document}",
            )
        return True, None

    @staticmethod
    def check_image_dimensions(
        plan_tier: str, width: int, height: int
    ) -> tuple[bool, Optional[str]]:
        """Check if image dimensions are within plan limits.

        Args:
            plan_tier: Plan tier identifier
            width: Image width in pixels
            height: Image height in pixels

        Returns:
            Tuple of (is_valid, error_message)
        """
        limits = PlanService.get_plan_limits(plan_tier)
        max_width, max_height = limits.max_image_dimensions
        if width > max_width or height > max_height:
            return (
                False,
                f"Image dimensions {width}x{height} exceed plan limit of {max_width}x{max_height}",
            )
        return True, None

    @staticmethod
    def check_usage_limit(
        plan_tier: str,
        current_usage: int,
        limit_type: str = "pages",
    ) -> tuple[bool, Optional[str], bool]:
        """Check if usage is within plan limits.

        Args:
            plan_tier: Plan tier identifier
            current_usage: Current usage (pages or documents)
            limit_type: Type of limit ("pages" or "documents")

        Returns:
            Tuple of (is_within_limit, error_message, is_hard_limit)
        """
        limits = PlanService.get_plan_limits(plan_tier)

        if limit_type == "pages":
            quota = limits.included_pages_per_month
        else:
            # For documents, use a reasonable default based on pages
            quota = limits.included_pages_per_month // 10

        is_within_limit = current_usage < quota
        is_hard_limit = limits.hard_limit_enforced

        if not is_within_limit and is_hard_limit:
            error_msg = (
                f"Usage limit reached: {current_usage} {limit_type} exceeds "
                f"plan quota of {quota} {limit_type} per month"
            )
            return False, error_msg, True
        elif not is_within_limit:
            # Soft limit - allow overage
            return False, None, False

        return True, None, False

    @staticmethod
    def calculate_overage(plan_tier: str, usage_pages: int) -> float:
        """Calculate overage charges for usage above included quota.

        Args:
            plan_tier: Plan tier identifier
            usage_pages: Total pages used in the billing period

        Returns:
            Overage charge amount in dollars
        """
        limits = PlanService.get_plan_limits(plan_tier)

        if limits.hard_limit_enforced:
            # Free plan - no overage allowed
            return 0.0

        overage_pages = max(0, usage_pages - limits.included_pages_per_month)
        if overage_pages == 0:
            return 0.0

        # Calculate charge per 1000 pages
        charge = (overage_pages / 1000.0) * limits.overage_price_per_1000_pages
        return round(charge, 2)

    @staticmethod
    def get_max_retries(plan_tier: str) -> int:
        """Get maximum retry attempts for a plan.

        Args:
            plan_tier: Plan tier identifier

        Returns:
            Maximum number of retries
        """
        limits = PlanService.get_plan_limits(plan_tier)
        return limits.max_retries

    @staticmethod
    def check_template_limit(plan_tier: str, current_template_count: int) -> tuple[bool, Optional[str]]:
        """Check if template count is within plan limits.

        Args:
            plan_tier: Plan tier identifier
            current_template_count: Current number of templates

        Returns:
            Tuple of (is_valid, error_message)
        """
        limits = PlanService.get_plan_limits(plan_tier)
        if limits.max_templates is None:
            return True, None  # Unlimited

        if current_template_count >= limits.max_templates:
            return (
                False,
                f"Template limit reached: {current_template_count} templates exceeds "
                f"plan limit of {limits.max_templates}",
            )
        return True, None

    @staticmethod
    def check_project_limit(plan_tier: str, current_project_count: int) -> tuple[bool, Optional[str]]:
        """Check if project count is within plan limits.

        Args:
            plan_tier: Plan tier identifier
            current_project_count: Current number of projects

        Returns:
            Tuple of (is_valid, error_message)
        """
        limits = PlanService.get_plan_limits(plan_tier)
        if limits.max_projects is None:
            return True, None  # Unlimited

        if current_project_count >= limits.max_projects:
            return (
                False,
                f"Project limit reached: {current_project_count} projects exceeds "
                f"plan limit of {limits.max_projects}",
            )
        return True, None

    @staticmethod
    def get_retention_days(plan_tier: str) -> int:
        """Get data retention period in days for a plan.

        Args:
            plan_tier: Plan tier identifier

        Returns:
            Retention period in days
        """
        limits = PlanService.get_plan_limits(plan_tier)
        return limits.retention_days

    @staticmethod
    def can_downgrade(
        current_tier: str,
        target_tier: str,
        current_usage: Dict[str, int],
        current_resources: Dict[str, int],
    ) -> tuple[bool, List[str]]:
        """Check if workspace can downgrade to target plan.

        Args:
            current_tier: Current plan tier
            target_tier: Target plan tier
            current_usage: Current usage dict (pages, documents, etc.)
            current_resources: Current resources dict (templates, projects, etc.)

        Returns:
            Tuple of (can_downgrade, list_of_warnings)
        """
        warnings: List[str] = []
        target_limits = PlanService.get_plan_limits(target_tier)

        # Check usage limits
        if current_usage.get("pages", 0) > target_limits.included_pages_per_month:
            warnings.append(
                f"Current usage ({current_usage.get('pages', 0)} pages) exceeds "
                f"target plan quota ({target_limits.included_pages_per_month} pages)"
            )

        # Check resource limits
        if target_limits.max_templates and current_resources.get("templates", 0) > target_limits.max_templates:
            warnings.append(
                f"Current templates ({current_resources.get('templates', 0)}) exceeds "
                f"target plan limit ({target_limits.max_templates})"
            )

        if target_limits.max_projects and current_resources.get("projects", 0) > target_limits.max_projects:
            warnings.append(
                f"Current projects ({current_resources.get('projects', 0)}) exceeds "
                f"target plan limit ({target_limits.max_projects})"
            )

        # Check feature loss
        current_limits = PlanService.get_plan_limits(current_tier)
        if current_limits.webhooks_enabled and not target_limits.webhooks_enabled:
            warnings.append("Webhooks will be disabled on downgrade")
        if current_limits.integrations_enabled and not target_limits.integrations_enabled:
            warnings.append("Integrations (Make/Zapier/n8n) will be disabled on downgrade")

        can_downgrade = len(warnings) == 0
        return can_downgrade, warnings

    @staticmethod
    def get_confidence_threshold(plan_tier: str) -> float:
        """Get confidence threshold for extraction review.

        Args:
            plan_tier: Plan tier identifier

        Returns:
            Confidence threshold (0.0-1.0). Extractions below this require review.
        """
        limits = PlanService.get_plan_limits(plan_tier)
        return limits.confidence_threshold

    @staticmethod
    def check_api_key_limit(plan_tier: str, current_api_key_count: int) -> tuple[bool, Optional[str]]:
        """Check if API key count is within plan limits.

        Args:
            plan_tier: Plan tier identifier
            current_api_key_count: Current number of API keys

        Returns:
            Tuple of (is_valid, error_message)
        """
        limits = PlanService.get_plan_limits(plan_tier)
        if limits.max_api_keys is None:
            return True, None  # Unlimited

        if current_api_key_count >= limits.max_api_keys:
            return (
                False,
                f"API key limit reached: {current_api_key_count} API keys exceeds "
                f"plan limit of {limits.max_api_keys}",
            )
        return True, None

    @staticmethod
    def check_ai_extraction_enabled(plan_tier: str) -> bool:
        """Check if AI extraction is enabled for a plan.

        Args:
            plan_tier: Plan tier identifier

        Returns:
            True if AI extraction is enabled
        """
        limits = PlanService.get_plan_limits(plan_tier)
        return limits.ai_extraction_enabled

    @staticmethod
    def calculate_ai_overage(plan_tier: str, ai_pages_used: int) -> float:
        """Calculate AI page overage charges.

        Args:
            plan_tier: Plan tier identifier
            ai_pages_used: Total AI pages used in the billing period

        Returns:
            Overage charge amount in dollars
        """
        limits = PlanService.get_plan_limits(plan_tier)

        if not limits.ai_extraction_enabled:
            return 0.0

        if limits.ai_page_price == 0.0:
            # Enterprise plan with custom pricing
            return 0.0

        # Calculate overage after included AI pages
        overage_pages = max(0, ai_pages_used - limits.included_ai_pages_per_month)
        if overage_pages == 0:
            return 0.0

        # Calculate charge per AI page
        charge = overage_pages * limits.ai_page_price
        return round(charge, 2)

    @staticmethod
    def check_ai_quota(
        plan_tier: str,
        current_ai_usage: int,
    ) -> tuple[bool, Optional[str], bool]:
        """Check if AI page usage is within plan quota.

        Args:
            plan_tier: Plan tier identifier
            current_ai_usage: Current AI pages used in billing period

        Returns:
            Tuple of (is_within_quota, error_message, is_hard_limit)
        """
        limits = PlanService.get_plan_limits(plan_tier)

        if not limits.ai_extraction_enabled:
            return (
                False,
                "AI extraction is not available on your current plan",
                True,
            )

        # For pay-as-you-go plans (Starter), there's no hard limit on AI pages
        # They just get charged per page
        if limits.included_ai_pages_per_month == 0 and limits.ai_page_price > 0:
            # Pay-as-you-go: no quota limit, just billing
            return True, None, False

        # For plans with included AI pages (Pro), check if within quota
        if current_ai_usage < limits.included_ai_pages_per_month:
            return True, None, False

        # Over quota - Pro plan allows overage with additional charges
        return False, None, False  # Soft limit - allow overage with charges

    # Database methods for plan management
    @staticmethod
    async def get_all_plans(db: AsyncSession, active_only: bool = True) -> List[Plan]:
        """Get all plans from database, ordered by display_order.
        
        Args:
            db: Database session
            active_only: If True, only return active plans
            
        Returns:
            List of Plan objects
        """
        query = select(Plan).order_by(Plan.display_order.asc())
        if active_only:
            query = query.where(Plan.is_active == True)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_plan_by_id(db: AsyncSession, plan_id: str) -> Optional[Plan]:
        """Get a plan by its plan_id.
        
        Args:
            db: Database session
            plan_id: Plan identifier (e.g., 'free', 'basic', 'pro', 'enterprise')
            
        Returns:
            Plan object or None if not found
        """
        result = await db.execute(
            select(Plan).where(Plan.plan_id == plan_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_plan_by_stripe_price_id(db: AsyncSession, stripe_price_id: str) -> Optional[Plan]:
        """Get a plan by its Stripe price ID.
        
        Args:
            db: Database session
            stripe_price_id: Stripe price ID (price_...)
            
        Returns:
            Plan object or None if not found
        """
        result = await db.execute(
            select(Plan).where(Plan.stripe_price_id == stripe_price_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def sync_stripe_price_ids(db: AsyncSession) -> None:
        """Sync Stripe price IDs from environment variables to database.
        
        This should be called on startup or when environment variables change.
        """
        import os
        
        # Map plan_id to environment variable names
        price_id_mapping = {
            "basic": "STRIPE_PRICE_ID_BASIC",
            "pro": "STRIPE_PRICE_ID_PRO",
        }
        
        for plan_id, env_var in price_id_mapping.items():
            price_id = os.getenv(env_var, "").strip()
            if price_id:
                plan = await PlanService.get_plan_by_id(db, plan_id)
                if plan and plan.stripe_price_id != price_id:
                    plan.stripe_price_id = price_id
                    await db.commit()
                    logger.info(f"Updated Stripe price ID for plan {plan_id}: {price_id}")

