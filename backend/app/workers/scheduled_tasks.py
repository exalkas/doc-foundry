"""Scheduled tasks for daily aggregation, retention, billing checks, etc."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import AsyncSessionLocal
from app.models.subscription import Subscription, SubscriptionStatusEnum
from app.models.workspace import Workspace, WorkspaceStatus
from app.models.user import User
from app.models.workspacemember import WorkspaceMember, WorkspaceMemberRole, WorkspaceMemberStatus
from app.services.notification_service import NotificationService
from app.services.plan_service import PlanService
from app.services.retention_service import RetentionService
from app.services.usage_service import UsageService
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Grace period configuration
PAYMENT_FAILURE_GRACE_PERIOD_DAYS = 7


class ScheduledTasksService:
    """Service for managing scheduled background tasks."""

    def __init__(
        self,
        usage_service: Optional[UsageService] = None,
        plan_service: Optional[PlanService] = None,
        retention_service: Optional[RetentionService] = None,
        notification_service: Optional[NotificationService] = None,
    ):
        """Initialize scheduled tasks service.

        Args:
            usage_service: Usage service instance
            plan_service: Plan service instance
            retention_service: Retention service instance
            notification_service: Notification service instance
        """
        self.usage_service = usage_service or UsageService()
        self.plan_service = plan_service or PlanService()
        self.retention_service = retention_service or RetentionService()
        self.notification_service = notification_service or NotificationService()
        self.scheduler = AsyncIOScheduler()

    async def daily_usage_aggregation(self) -> None:
        """Aggregate daily usage records (runs at end of day)."""
        logger.info("Starting daily usage aggregation")

        async with AsyncSessionLocal() as session:
            try:
                target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()
                count = await self.usage_service.aggregate_daily_usage(session, target_date)
                await session.commit()
                logger.info("Daily usage aggregation complete: workspaces=%d", count)
            except Exception as e:
                logger.exception("Error in daily usage aggregation: %s", e)
                await session.rollback()

    async def check_payment_failures(self) -> None:
        """Check for payment failures and handle grace periods."""
        logger.info("Checking payment failures")

        async with AsyncSessionLocal() as session:
            try:
                # Query subscriptions with PAST_DUE status
                result = await session.execute(
                    select(Subscription).where(
                        Subscription.status == SubscriptionStatusEnum.PAST_DUE
                    )
                )
                past_due_subscriptions = result.scalars().all()
                
                now = datetime.now(timezone.utc)
                grace_period_delta = timedelta(days=PAYMENT_FAILURE_GRACE_PERIOD_DAYS)
                
                for subscription in past_due_subscriptions:
                    # Calculate grace period end (7 days after period end)
                    grace_period_end = subscription.current_period_end + grace_period_delta
                    
                    # Get workspace
                    workspace_result = await session.execute(
                        select(Workspace).where(Workspace.id == subscription.workspace_id)
                    )
                    workspace = workspace_result.scalar_one_or_none()
                    
                    if not workspace:
                        continue
                    
                    # Check if grace period has expired
                    if now >= grace_period_end:
                        # Grace period expired - suspend workspace
                        if workspace.status != WorkspaceStatus.SUSPENDED:
                            workspace.status = WorkspaceStatus.SUSPENDED
                            workspace.updated_at = now
                            
                            # Send suspension notification
                            try:
                                owner_result = await session.execute(
                                    select(WorkspaceMember).where(
                                        WorkspaceMember.workspace_id == workspace.id,
                                        WorkspaceMember.role == WorkspaceMemberRole.OWNER,
                                        WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
                                    ).limit(1)
                                )
                                owner_member = owner_result.scalar_one_or_none()
                                
                                if owner_member:
                                    user_result = await session.execute(
                                        select(User).where(User.id == owner_member.user_id)
                                    )
                                    owner_user = user_result.scalar_one_or_none()
                                    
                                    if owner_user:
                                        await self.notification_service.send_workspace_suspended(
                                            owner_user.email,
                                            workspace.name,
                                            "Payment failure - grace period expired",
                                        )
                            except Exception as e:
                                logger.warning(f"Failed to send suspension notification: {e}")
                            
                            logger.info(
                                "Workspace suspended due to payment failure: workspace_id=%s",
                                workspace.id,
                            )
                    elif now >= subscription.current_period_end:
                        # Within grace period - send warning
                        days_remaining = (grace_period_end - now).days
                        if days_remaining <= 3:  # Send warning if 3 days or less remaining
                            try:
                                owner_result = await session.execute(
                                    select(WorkspaceMember).where(
                                        WorkspaceMember.workspace_id == workspace.id,
                                        WorkspaceMember.role == WorkspaceMemberRole.OWNER,
                                        WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
                                    ).limit(1)
                                )
                                owner_member = owner_result.scalar_one_or_none()
                                
                                if owner_member:
                                    user_result = await session.execute(
                                        select(User).where(User.id == owner_member.user_id)
                                    )
                                    owner_user = user_result.scalar_one_or_none()
                                    
                                    if owner_user:
                                        await self.notification_service.send_payment_failed(
                                            owner_user.email,
                                            workspace.name,
                                            0.0,  # Amount will be in Stripe invoice
                                            "USD",
                                            grace_period_days=days_remaining,
                                        )
                            except Exception as e:
                                logger.warning(f"Failed to send payment warning: {e}")
                
                await session.commit()
                logger.info(
                    "Payment failure check complete: checked %d subscriptions",
                    len(past_due_subscriptions),
                )
            except Exception as e:
                logger.exception("Error checking payment failures: %s", e)
                await session.rollback()

    async def check_trial_expiry(self) -> None:
        """Check for expired trials and handle downgrades."""
        logger.info("Checking trial expiry")

        async with AsyncSessionLocal() as session:
            try:
                # Placeholder implementation
                # In production, query Subscription table for expiring trials
                logger.info("Trial expiry check complete")
            except Exception as e:
                logger.exception("Error checking trial expiry: %s", e)
                await session.rollback()

    async def enforce_retention(self) -> None:
        """Enforce data retention policies."""
        logger.info("Starting retention enforcement")

        async with AsyncSessionLocal() as session:
            try:
                # Get all workspaces and enforce retention
                # In production, query Workspace and Subscription tables
                deleted = await self.retention_service.cleanup_expired_data(session)
                await session.commit()
                logger.info("Retention enforcement complete: deleted=%s", deleted)
            except Exception as e:
                logger.exception("Error enforcing retention: %s", e)
                await session.rollback()

    async def send_quota_warnings(self) -> None:
        """Send quota warnings to workspaces approaching limits."""
        logger.info("Sending quota warnings")

        async with AsyncSessionLocal() as session:
            try:
                # In production, this would:
                # 1. Query all active workspaces
                # 2. Check usage vs quota
                # 3. Send warnings for 80%, 90%, 95% thresholds
                logger.info("Quota warnings sent")
            except Exception as e:
                logger.exception("Error sending quota warnings: %s", e)
                await session.rollback()

    def start(self) -> None:
        """Start the scheduler."""
        logger.info("Starting scheduled tasks scheduler")

        # Daily usage aggregation (runs at 23:59 UTC)
        self.scheduler.add_job(
            self.daily_usage_aggregation,
            trigger=CronTrigger(hour=23, minute=59),
            id="daily_usage_aggregation",
            name="Daily Usage Aggregation",
        )

        # Payment failure checks (runs every 6 hours)
        self.scheduler.add_job(
            self.check_payment_failures,
            trigger=CronTrigger(hour="*/6"),
            id="check_payment_failures",
            name="Check Payment Failures",
        )

        # Trial expiry checks (runs daily at 00:00 UTC)
        self.scheduler.add_job(
            self.check_trial_expiry,
            trigger=CronTrigger(hour=0, minute=0),
            id="check_trial_expiry",
            name="Check Trial Expiry",
        )

        # Retention enforcement (runs daily at 02:00 UTC)
        self.scheduler.add_job(
            self.enforce_retention,
            trigger=CronTrigger(hour=2, minute=0),
            id="enforce_retention",
            name="Enforce Retention",
        )

        # Quota warnings (runs daily at 09:00 UTC)
        self.scheduler.add_job(
            self.send_quota_warnings,
            trigger=CronTrigger(hour=9, minute=0),
            id="send_quota_warnings",
            name="Send Quota Warnings",
        )

        self.scheduler.start()
        logger.info("Scheduled tasks scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        logger.info("Stopping scheduled tasks scheduler")
        self.scheduler.shutdown()
        logger.info("Scheduled tasks scheduler stopped")


# Global scheduler instance
_scheduler_instance: Optional[ScheduledTasksService] = None


def get_scheduler() -> ScheduledTasksService:
    """Get global scheduler instance.

    Returns:
        ScheduledTasksService instance
    """
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = ScheduledTasksService()
    return _scheduler_instance


async def main() -> None:
    """Entry point for running scheduled tasks as a standalone process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    scheduler = get_scheduler()
    scheduler.start()

    try:
        # Keep running
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Scheduler interrupted by user")
        scheduler.stop()


if __name__ == "__main__":
    asyncio.run(main())

