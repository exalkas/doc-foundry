"""Onboarding service for creating sample projects, templates, and documents."""

import logging
import uuid
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatusEnum, DocumentSourceEnum
from app.models.project import Project
from app.models.template import Template, ExportFormatEnum

logger = logging.getLogger(__name__)


class OnboardingService:
    """Service for setting up new workspaces with sample data."""

    async def create_sample_project(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        user_id: UUID,
    ) -> Project:
        """Create a sample "Getting Started" project.

        Args:
            session: Database session
            workspace_id: Workspace ID
            user_id: User ID

        Returns:
            Created Project object
        """
        project = Project(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            name="Getting Started",
            description="Sample project to help you get started with document extraction",
            created_by_user_id=user_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        session.add(project)
        await session.flush()

        logger.info("Created sample project: id=%s, workspace=%s", project.id, workspace_id)

        return project

    async def create_sample_templates(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        project_id: UUID,
        user_id: UUID,
    ) -> List[Template]:
        """Create sample templates for onboarding.

        Args:
            session: Database session
            workspace_id: Workspace ID
            project_id: Project ID
            user_id: User ID

        Returns:
            List of created Template objects
        """
        templates = []

        # Invoice template
        invoice_template = Template(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            project_id=project_id,
            name="Invoice (B2B)",
            description="Extract data from B2B invoices",
            document_type="invoice",
            field_schema={
                "fields": [
                    {
                        "name": "Invoice Number",
                        "json_key": "invoice_number",
                        "data_type": "string",
                        "required": True,
                        "strategy": "regex",
                        "pattern": r"Invoice\s*[#:]?\s*([A-Z0-9-]+)",
                    },
                    {
                        "name": "Invoice Date",
                        "json_key": "invoice_date",
                        "data_type": "date",
                        "required": True,
                        "strategy": "regex",
                        "pattern": r"Date\s*[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    },
                    {
                        "name": "Total Amount",
                        "json_key": "total_amount",
                        "data_type": "number",
                        "required": True,
                        "strategy": "anchor",
                        "anchor": "Total",
                    },
                    {
                        "name": "Vendor Name",
                        "json_key": "vendor_name",
                        "data_type": "string",
                        "required": False,
                        "strategy": "name",
                    },
                ]
            },
            default_export_format=ExportFormatEnum.JSON,
            created_by_user_id=user_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        templates.append(invoice_template)

        # Receipt template
        receipt_template = Template(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            project_id=project_id,
            name="Receipt",
            description="Extract data from receipts",
            document_type="receipt",
            field_schema={
                "fields": [
                    {
                        "name": "Merchant Name",
                        "json_key": "merchant_name",
                        "data_type": "string",
                        "required": True,
                        "strategy": "name",
                    },
                    {
                        "name": "Date",
                        "json_key": "date",
                        "data_type": "date",
                        "required": True,
                        "strategy": "regex",
                        "pattern": r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    },
                    {
                        "name": "Total",
                        "json_key": "total",
                        "data_type": "number",
                        "required": True,
                        "strategy": "anchor",
                        "anchor": "Total",
                    },
                ]
            },
            default_export_format=ExportFormatEnum.JSON,
            created_by_user_id=user_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        templates.append(receipt_template)

        # Simple contract template
        contract_template = Template(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            project_id=project_id,
            name="Simple Contract",
            description="Extract key information from contracts",
            document_type="contract",
            field_schema={
                "fields": [
                    {
                        "name": "Contract Date",
                        "json_key": "contract_date",
                        "data_type": "date",
                        "required": True,
                        "strategy": "regex",
                        "pattern": r"Date\s*[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                    },
                    {
                        "name": "Party A",
                        "json_key": "party_a",
                        "data_type": "string",
                        "required": True,
                        "strategy": "anchor",
                        "anchor": "Party A",
                    },
                    {
                        "name": "Party B",
                        "json_key": "party_b",
                        "data_type": "string",
                        "required": True,
                        "strategy": "anchor",
                        "anchor": "Party B",
                    },
                ]
            },
            default_export_format=ExportFormatEnum.JSON,
            created_by_user_id=user_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        templates.append(contract_template)

        for template in templates:
            session.add(template)

        await session.flush()

        logger.info(
            "Created %d sample templates: workspace=%s, project=%s",
            len(templates),
            workspace_id,
            project_id,
        )

        return templates

    async def setup_workspace_onboarding(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        user_id: UUID,
    ) -> Dict[str, any]:
        """Set up complete onboarding for a new workspace.

        Args:
            session: Database session
            workspace_id: Workspace ID
            user_id: User ID

        Returns:
            Dict with created resources
        """
        logger.info("Setting up onboarding for workspace: %s", workspace_id)

        # Create sample project
        project = await self.create_sample_project(session, workspace_id, user_id)

        # Create sample templates
        templates = await self.create_sample_templates(
            session, workspace_id, project.id, user_id
        )

        await session.commit()

        return {
            "project": {
                "id": str(project.id),
                "name": project.name,
            },
            "templates": [
                {
                    "id": str(t.id),
                    "name": t.name,
                    "document_type": t.document_type,
                }
                for t in templates
            ],
        }

