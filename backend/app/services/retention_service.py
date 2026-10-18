"""Retention service for data retention policies and GDPR deletion."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.extractionlog import ExtractionLog
from app.models.extractionresult import ExtractionResult
from app.models.project import Project
from app.models.template import Template
from app.services.plan_service import PlanService

logger = logging.getLogger(__name__)


class RetentionService:
    """Service for managing data retention and GDPR deletion."""

    def __init__(self, plan_service: Optional[PlanService] = None):
        """Initialize retention service.

        Args:
            plan_service: Plan service instance
        """
        self.plan_service = plan_service or PlanService()

    async def enforce_retention(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        plan_tier: str,
    ) -> Dict[str, int]:
        """Enforce retention policy for a workspace.

        Args:
            session: Database session
            workspace_id: Workspace ID
            plan_tier: Plan tier identifier

        Returns:
            Dict with counts of deleted records
        """
        retention_days = self.plan_service.get_retention_days(plan_tier)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        logger.info(
            "Enforcing retention for workspace %s: retention_days=%d, cutoff_date=%s",
            workspace_id,
            retention_days,
            cutoff_date,
        )

        deleted_counts = {
            "documents": 0,
            "extraction_results": 0,
            "extraction_logs": 0,
        }

        # Delete old documents and related data
        # Note: This uses CASCADE deletes, so extraction_results and logs
        # will be deleted automatically
        result = await session.execute(
            select(Document).where(
                and_(
                    Document.workspace_id == workspace_id,
                    Document.created_at < cutoff_date,
                )
            )
        )
        old_documents = result.scalars().all()

        for doc in old_documents:
            await session.delete(doc)
            deleted_counts["documents"] += 1

        await session.commit()

        logger.info(
            "Retention enforcement complete: workspace=%s, deleted=%s",
            workspace_id,
            deleted_counts,
        )

        return deleted_counts

    async def delete_workspace_data(
        self,
        session: AsyncSession,
        workspace_id: UUID,
    ) -> Dict[str, int]:
        """Delete all data for a workspace (GDPR deletion).

        Args:
            session: Database session
            workspace_id: Workspace ID

        Returns:
            Dict with counts of deleted records
        """
        logger.info("Deleting all data for workspace: %s (GDPR deletion)", workspace_id)

        deleted_counts = {
            "documents": 0,
            "templates": 0,
            "projects": 0,
            "extraction_results": 0,
            "extraction_logs": 0,
        }

        # Delete documents (cascades to extraction_results and logs)
        result = await session.execute(
            select(Document).where(Document.workspace_id == workspace_id)
        )
        documents = result.scalars().all()
        for doc in documents:
            await session.delete(doc)
            deleted_counts["documents"] += 1

        # Delete templates
        result = await session.execute(
            select(Template).where(Template.workspace_id == workspace_id)
        )
        templates = result.scalars().all()
        for template in templates:
            await session.delete(template)
            deleted_counts["templates"] += 1

        # Delete projects
        result = await session.execute(
            select(Project).where(Project.workspace_id == workspace_id)
        )
        projects = result.scalars().all()
        for project in projects:
            await session.delete(project)
            deleted_counts["projects"] += 1

        await session.commit()

        logger.info(
            "GDPR deletion complete: workspace=%s, deleted=%s",
            workspace_id,
            deleted_counts,
        )

        return deleted_counts

    async def cleanup_expired_data(
        self,
        session: AsyncSession,
        batch_size: int = 100,
    ) -> Dict[str, int]:
        """Clean up expired data across all workspaces.

        Args:
            session: Database session
            batch_size: Batch size for processing

        Returns:
            Dict with total counts of deleted records
        """
        logger.info("Starting cleanup of expired data")

        total_deleted = {
            "documents": 0,
            "extraction_results": 0,
            "extraction_logs": 0,
        }

        # Get all workspaces and their plan tiers
        # (In production, you'd query Workspace and Subscription tables)
        # For now, we'll use a default retention period
        default_retention_days = 90
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=default_retention_days)

        # Delete old documents in batches
        offset = 0
        while True:
            result = await session.execute(
                select(Document)
                .where(Document.created_at < cutoff_date)
                .limit(batch_size)
                .offset(offset)
            )
            old_documents = result.scalars().all()

            if not old_documents:
                break

            for doc in old_documents:
                await session.delete(doc)
                total_deleted["documents"] += 1

            await session.commit()
            offset += batch_size

            logger.info(
                "Processed batch: offset=%d, deleted_documents=%d",
                offset,
                total_deleted["documents"],
            )

        logger.info("Cleanup complete: total_deleted=%s", total_deleted)
        return total_deleted

