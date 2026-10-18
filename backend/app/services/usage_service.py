"""Usage tracking and billing calculation service."""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usagerecord import UsageRecord
from app.services.plan_service import PlanService

logger = logging.getLogger(__name__)


class UsageService:
    """Service for tracking usage and calculating billing."""

    def __init__(self, plan_service: Optional[PlanService] = None):
        """Initialize usage service.

        Args:
            plan_service: Plan service instance. If None, creates default.
        """
        self.plan_service = plan_service or PlanService()

    async def record_usage(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        pages: int,
        documents: int = 1,
        ai_pages: int = 0,
        project_id: Optional[UUID] = None,
        template_id: Optional[UUID] = None,
        source: str = "ui",  # ui, api, zapier, make, n8n
        date_override: Optional[date] = None,
    ) -> UsageRecord:
        """Record usage for a workspace.

        Args:
            session: Database session
            workspace_id: Workspace ID
            pages: Number of pages processed
            documents: Number of documents processed (default: 1)
            ai_pages: Number of AI extraction pages processed (default: 0)
            project_id: Optional project ID for breakdown
            template_id: Optional template ID for breakdown
            source: Source of the usage (ui, api, zapier, make, n8n)
            date_override: Optional date override (defaults to today)

        Returns:
            Created or updated UsageRecord
        """
        usage_date = date_override or datetime.now(timezone.utc).date()

        # Get or create usage record for this date
        result = await session.execute(
            select(UsageRecord).where(
                and_(
                    UsageRecord.workspace_id == workspace_id,
                    UsageRecord.date == usage_date,
                )
            )
        )
        record = result.scalar_one_or_none()

        if record:
            # Update existing record
            record.documents_processed += documents
            record.pages_processed += pages
            record.ai_pages_processed += ai_pages
        else:
            # Create new record
            record = UsageRecord(
                workspace_id=workspace_id,
                date=usage_date,
                documents_processed=documents,
                pages_processed=pages,
                ai_pages_processed=ai_pages,
            )
            session.add(record)

        await session.flush()
        logger.info(
            "Recorded usage: workspace=%s, date=%s, pages=%d, ai_pages=%d, documents=%d",
            workspace_id,
            usage_date,
            pages,
            ai_pages,
            documents,
        )

        return record

    async def get_current_period_usage(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> Dict[str, int]:
        """Get total usage for a billing period.

        Args:
            session: Database session
            workspace_id: Workspace ID
            period_start: Period start datetime
            period_end: Period end datetime

        Returns:
            Dict with total_pages, total_documents, total_ai_pages
        """
        period_start_date = period_start.date()
        period_end_date = period_end.date()

        result = await session.execute(
            select(
                func.sum(UsageRecord.documents_processed).label("total_documents"),
                func.sum(UsageRecord.pages_processed).label("total_pages"),
                func.sum(UsageRecord.ai_pages_processed).label("total_ai_pages"),
            ).where(
                and_(
                    UsageRecord.workspace_id == workspace_id,
                    UsageRecord.date >= period_start_date,
                    UsageRecord.date < period_end_date,
                )
            )
        )
        row = result.first()

        return {
            "total_pages": int(row.total_pages or 0),
            "total_documents": int(row.total_documents or 0),
            "total_ai_pages": int(row.total_ai_pages or 0),
        }

    async def get_user_usage(
        self,
        session: AsyncSession,
        user_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> Dict[str, int]:
        """Get total usage for a user across all their workspaces.

        Args:
            session: Database session
            user_id: User ID
            period_start: Period start datetime
            period_end: Period end datetime

        Returns:
            Dict with total_pages, total_documents, total_ai_pages aggregated across all workspaces
        """
        from app.models.workspacemember import WorkspaceMember
        
        period_start_date = period_start.date()
        period_end_date = period_end.date()

        # Get all workspace IDs the user belongs to
        workspace_members_result = await session.execute(
            select(WorkspaceMember.workspace_id).where(
                WorkspaceMember.user_id == user_id
            )
        )
        workspace_ids = [row[0] for row in workspace_members_result.all()]

        if not workspace_ids:
            return {
                "total_pages": 0,
                "total_documents": 0,
                "total_ai_pages": 0,
            }

        # Aggregate usage across all workspaces
        result = await session.execute(
            select(
                func.sum(UsageRecord.documents_processed).label("total_documents"),
                func.sum(UsageRecord.pages_processed).label("total_pages"),
                func.sum(UsageRecord.ai_pages_processed).label("total_ai_pages"),
            ).where(
                and_(
                    UsageRecord.workspace_id.in_(workspace_ids),
                    UsageRecord.date >= period_start_date,
                    UsageRecord.date < period_end_date,
                )
            )
        )
        row = result.first()

        return {
            "total_pages": int(row.total_pages or 0),
            "total_documents": int(row.total_documents or 0),
            "total_ai_pages": int(row.total_ai_pages or 0),
        }

    async def get_usage_breakdown(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        period_start: datetime,
        period_end: datetime,
        breakdown_type: str = "all",  # all, project, template, source
    ) -> Dict[str, Any]:
        """Get usage breakdown by project, template, or source.

        Args:
            session: Database session
            workspace_id: Workspace ID
            period_start: Period start datetime
            period_end: Period end datetime
            breakdown_type: Type of breakdown (all, project, template, source)

        Returns:
            Dict with breakdown data
        """
        from app.models.document import Document, DocumentStatusEnum
        
        period_start_date = period_start.date()
        period_end_date = period_end.date()

        # Get total usage
        usage = await self.get_current_period_usage(
            session, workspace_id, period_start, period_end
        )
        
        total_pages = usage["total_pages"]
        total_documents = usage["total_documents"]

        # Initialize breakdowns
        by_project: Dict[str, Dict[str, Any]] = {}
        by_template: Dict[str, Dict[str, Any]] = {}
        by_source: Dict[str, Dict[str, Any]] = {}

        # Query documents in the period
        documents_query = select(
            Document.project_id,
            Document.template_id,
            Document.source,
            func.sum(func.coalesce(Document.pages, 1)).label("total_pages"),
            func.count(Document.id).label("total_documents"),
        ).where(
            and_(
                Document.workspace_id == workspace_id,
                Document.created_at >= period_start,
                Document.created_at < period_end,
                Document.status == DocumentStatusEnum.COMPLETED,  # Only count completed extractions
            )
        )

        if breakdown_type in ("all", "project"):
            # Group by project
            project_result = await session.execute(
                documents_query.group_by(Document.project_id)
            )
            for row in project_result.all():
                project_id_str = str(row.project_id) if row.project_id else "none"
                pages = int(row.total_pages or 0)
                docs = int(row.total_documents or 0)
                by_project[project_id_str] = {
                    "project_id": project_id_str,
                    "pages": pages,
                    "documents": docs,
                    "percentage_pages": (pages / total_pages * 100) if total_pages > 0 else 0,
                    "percentage_documents": (docs / total_documents * 100) if total_documents > 0 else 0,
                }

        if breakdown_type in ("all", "template"):
            # Group by template
            template_result = await session.execute(
                documents_query.group_by(Document.template_id)
            )
            for row in template_result.all():
                template_id_str = str(row.template_id) if row.template_id else "none"
                pages = int(row.total_pages or 0)
                docs = int(row.total_documents or 0)
                by_template[template_id_str] = {
                    "template_id": template_id_str,
                    "pages": pages,
                    "documents": docs,
                    "percentage_pages": (pages / total_pages * 100) if total_pages > 0 else 0,
                    "percentage_documents": (docs / total_documents * 100) if total_documents > 0 else 0,
                }

        if breakdown_type in ("all", "source"):
            # Group by source
            source_result = await session.execute(
                documents_query.group_by(Document.source)
            )
            for row in source_result.all():
                source_str = row.source.value if hasattr(row.source, 'value') else str(row.source)
                pages = int(row.total_pages or 0)
                docs = int(row.total_documents or 0)
                by_source[source_str] = {
                    "source": source_str,
                    "pages": pages,
                    "documents": docs,
                    "percentage_pages": (pages / total_pages * 100) if total_pages > 0 else 0,
                    "percentage_documents": (docs / total_documents * 100) if total_documents > 0 else 0,
                }

        return {
            "total": usage,
            "by_project": by_project,
            "by_template": by_template,
            "by_source": by_source,
        }

    async def get_usage_history(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        days: int = 90,
    ) -> List[Dict[str, Any]]:
        """Get daily usage history for a workspace.

        Args:
            session: Database session
            workspace_id: Workspace ID
            days: Number of days to retrieve

        Returns:
            List of daily usage records
        """
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days)

        result = await session.execute(
            select(UsageRecord)
            .where(
                and_(
                    UsageRecord.workspace_id == workspace_id,
                    UsageRecord.date >= start_date,
                    UsageRecord.date <= end_date,
                )
            )
            .order_by(UsageRecord.date.desc())
        )
        records = result.scalars().all()

        return [
            {
                "date": record.date.isoformat(),
                "pages": record.pages_processed,
                "ai_pages": record.ai_pages_processed,
                "documents": record.documents_processed,
            }
            for record in records
        ]

    async def check_quota_exceeded(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        plan_tier: str,
        period_start: datetime,
        period_end: datetime,
    ) -> Tuple[bool, Optional[str], bool]:
        """Check if workspace has exceeded quota.

        Args:
            session: Database session
            workspace_id: Workspace ID
            plan_tier: Plan tier identifier
            period_start: Period start datetime
            period_end: Period end datetime

        Returns:
            Tuple of (is_exceeded, error_message, is_hard_limit)
        """
        usage = await self.get_current_period_usage(
            session, workspace_id, period_start, period_end
        )
        pages_used = usage["total_pages"]

        return self.plan_service.check_usage_limit(plan_tier, pages_used, "pages")

    async def calculate_overage(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        plan_tier: str,
        period_start: datetime,
        period_end: datetime,
    ) -> float:
        """Calculate overage charges for a billing period.

        Args:
            session: Database session
            workspace_id: Workspace ID
            plan_tier: Plan tier identifier
            period_start: Period start datetime
            period_end: Period end datetime

        Returns:
            Overage charge amount in dollars
        """
        usage = await self.get_current_period_usage(
            session, workspace_id, period_start, period_end
        )
        pages_used = usage["total_pages"]

        return self.plan_service.calculate_overage(plan_tier, pages_used)

    async def aggregate_daily_usage(
        self,
        session: AsyncSession,
        target_date: Optional[date] = None,
    ) -> int:
        """Aggregate usage records for a specific date (end-of-day job).

        This is called by scheduled tasks to ensure all usage is properly recorded.

        Args:
            session: Database session
            target_date: Date to aggregate (defaults to yesterday)

        Returns:
            Number of workspaces processed
        """
        if target_date is None:
            # Default to yesterday (end of day aggregation)
            target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

        logger.info("Aggregating daily usage for date: %s", target_date)

        # Get all unique workspaces with usage on this date
        result = await session.execute(
            select(UsageRecord.workspace_id)
            .where(UsageRecord.date == target_date)
            .distinct()
        )
        workspace_ids = [row[0] for row in result.fetchall()]

        # For each workspace, ensure usage is properly aggregated
        # (In a more complex system, you might aggregate from raw events)
        processed_count = len(workspace_ids)

        logger.info(
            "Daily usage aggregation complete: date=%s, workspaces=%d",
            target_date,
            processed_count,
        )

        return processed_count

    async def get_quota_warnings(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        plan_tier: str,
        period_start: datetime,
        period_end: datetime,
        warning_thresholds: List[float] = None,
    ) -> List[Dict[str, Any]]:
        """Get quota warning messages if usage is approaching limits.

        Args:
            session: Database session
            workspace_id: Workspace ID
            plan_tier: Plan tier identifier
            period_start: Period start datetime
            period_end: Period end datetime
            warning_thresholds: List of thresholds (e.g., [0.8, 0.9, 0.95])

        Returns:
            List of warning dicts with threshold and message
        """
        if warning_thresholds is None:
            warning_thresholds = [0.8, 0.9, 0.95]

        usage = await self.get_current_period_usage(
            session, workspace_id, period_start, period_end
        )
        pages_used = usage["total_pages"]

        limits = self.plan_service.get_plan_limits(plan_tier)
        quota = limits.included_pages_per_month

        if quota == 0:
            return []  # Enterprise/unlimited plans

        usage_percentage = pages_used / quota
        warnings = []

        for threshold in warning_thresholds:
            if usage_percentage >= threshold:
                remaining = quota - pages_used
                warnings.append(
                    {
                        "threshold": threshold,
                        "usage_percentage": usage_percentage,
                        "pages_used": pages_used,
                        "quota": quota,
                        "remaining": remaining,
                        "message": (
                            f"You've used {usage_percentage:.0%} of your monthly quota "
                            f"({pages_used:,} / {quota:,} pages). "
                            f"{remaining:,} pages remaining."
                        ),
                    }
                )

        return warnings

    async def get_user_quota_warnings(
        self,
        session: AsyncSession,
        user_id: UUID,
        plan_tier: str,
        period_start: datetime,
        period_end: datetime,
        warning_thresholds: List[float] = None,
    ) -> List[Dict[str, Any]]:
        """Get quota warning messages if user's aggregated usage is approaching limits.

        Args:
            session: Database session
            user_id: User ID
            plan_tier: Plan tier identifier
            period_start: Period start datetime
            period_end: Period end datetime
            warning_thresholds: List of thresholds (e.g., [0.8, 0.9, 0.95])

        Returns:
            List of warning dicts with threshold and message
        """
        if warning_thresholds is None:
            warning_thresholds = [0.8, 0.9, 0.95]

        usage = await self.get_user_usage(
            session, user_id, period_start, period_end
        )
        pages_used = usage["total_pages"]

        limits = self.plan_service.get_plan_limits(plan_tier)
        quota = limits.included_pages_per_month

        if quota == 0:
            return []  # Enterprise/unlimited plans

        usage_percentage = pages_used / quota
        warnings = []

        for threshold in warning_thresholds:
            if usage_percentage >= threshold:
                remaining = quota - pages_used
                warnings.append(
                    {
                        "threshold": threshold,
                        "usage_percentage": usage_percentage,
                        "pages_used": pages_used,
                        "quota": quota,
                        "remaining": remaining,
                        "message": (
                            f"You've used {usage_percentage:.0%} of your monthly quota "
                            f"({pages_used:,} / {quota:,} pages). "
                            f"{remaining:,} pages remaining."
                        ),
                    }
                )

        return warnings

    async def get_ai_usage(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        """Get total AI page usage for a billing period.

        Args:
            session: Database session
            workspace_id: Workspace ID
            period_start: Period start datetime
            period_end: Period end datetime

        Returns:
            Total AI pages used in the period
        """
        period_start_date = period_start.date()
        period_end_date = period_end.date()

        result = await session.execute(
            select(
                func.sum(UsageRecord.ai_pages_processed).label("total_ai_pages"),
            ).where(
                and_(
                    UsageRecord.workspace_id == workspace_id,
                    UsageRecord.date >= period_start_date,
                    UsageRecord.date < period_end_date,
                )
            )
        )
        row = result.first()

        return int(row.total_ai_pages or 0)

    async def calculate_ai_overage(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        plan_tier: str,
        period_start: datetime,
        period_end: datetime,
    ) -> float:
        """Calculate AI page overage charges for a billing period.

        Args:
            session: Database session
            workspace_id: Workspace ID
            plan_tier: Plan tier identifier
            period_start: Period start datetime
            period_end: Period end datetime

        Returns:
            AI overage charge amount in dollars
        """
        ai_pages_used = await self.get_ai_usage(
            session, workspace_id, period_start, period_end
        )

        return self.plan_service.calculate_ai_overage(plan_tier, ai_pages_used)

