"""
SQLAlchemy models package initialization.

This module exposes the declarative base and all ORM models so that:
- Table creation scripts can discover all models.
- Other parts of the application can import models from a single place.

Example:
    from app.models import User, Workspace, Base
"""

from app.database import Base

from .user import User
from .workspace import Workspace
from .workspacemember import WorkspaceMember
from .subscription import Subscription
from .usagerecord import UsageRecord
from .project import Project
from .template import Template
from .document import Document
from .extractionresult import ExtractionResult
from .extractionlog import ExtractionLog
from .job import Job
from .apikey import ApiKey
from .webhookconfig import WebhookConfig
from .webhookdelivery import WebhookDelivery
from .auditlog import AuditLog
from .notification import Notification
from .plan import Plan
from .template_library import TemplateLibrary
from .commission_plan import CommissionPlan
from .affiliate import Affiliate, AffiliateStatus
from .affiliate_link import AffiliateLink
from .affiliate_click import AffiliateClick
from .affiliate_attribution import AffiliateAttribution, AttributionSource
from .commission import Commission, CommissionStatus, CommissionEventType
from .payout import Payout, PayoutStatus
from .coupon import Coupon, CouponStatus, DiscountType, DurationType
from .coupon_redemption import CouponRedemption

__all__ = [
    "Base",
    "User",
    "Workspace",
    "WorkspaceMember",
    "Subscription",
    "UsageRecord",
    "Project",
    "Template",
    "TemplateLibrary",
    "Document",
    "ExtractionResult",
    "ExtractionLog",
    "Job",
    "ApiKey",
    "WebhookConfig",
    "WebhookDelivery",
    "AuditLog",
    "Notification",
    "Plan",
    "CommissionPlan",
    "Affiliate",
    "AffiliateStatus",
    "AffiliateLink",
    "AffiliateClick",
    "AffiliateAttribution",
    "AttributionSource",
    "Commission",
    "CommissionStatus",
    "CommissionEventType",
    "Payout",
    "PayoutStatus",
    "Coupon",
    "CouponStatus",
    "DiscountType",
    "DurationType",
    "CouponRedemption",
]