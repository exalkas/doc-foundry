"""Template library service for managing pre-built templates."""

import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template import Template, ExportFormatEnum
from app.models.template_library import TemplateLibrary, TemplateCategoryEnum

logger = logging.getLogger(__name__)


class TemplateLibraryService:
    """Service for managing template library operations."""

    async def get_library_templates(
        self,
        session: AsyncSession,
        category: Optional[TemplateCategoryEnum] = None,
        search: Optional[str] = None,
        is_active: bool = True,
    ) -> List[TemplateLibrary]:
        """Get library templates with optional filtering.

        Args:
            session: Database session
            category: Optional category filter
            search: Optional search term for name/description
            is_active: Filter by active status (default: True)

        Returns:
            List of TemplateLibrary objects
        """
        query = select(TemplateLibrary).where(TemplateLibrary.is_active == is_active)

        if category:
            query = query.where(TemplateLibrary.category == category)

        if search:
            search_filter = or_(
                TemplateLibrary.name.ilike(f"%{search}%"),
                TemplateLibrary.description.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)

        query = query.order_by(TemplateLibrary.name.asc())

        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_library_template_by_id(
        self,
        session: AsyncSession,
        library_template_id: UUID,
    ) -> Optional[TemplateLibrary]:
        """Get a single library template by ID.

        Args:
            session: Database session
            library_template_id: Library template ID

        Returns:
            TemplateLibrary object or None if not found
        """
        result = await session.execute(
            select(TemplateLibrary).where(
                TemplateLibrary.id == library_template_id,
                TemplateLibrary.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_categories(
        self,
        session: AsyncSession,
    ) -> Dict[str, int]:
        """Get category counts.

        Args:
            session: Database session

        Returns:
            Dictionary mapping category names to counts
        """
        result = await session.execute(
            select(
                TemplateLibrary.category,
                func.count(TemplateLibrary.id).label("count"),
            )
            .where(TemplateLibrary.is_active == True)
            .group_by(TemplateLibrary.category)
        )

        return {row.category.value: row.count for row in result.all()}

    async def import_library_template(
        self,
        session: AsyncSession,
        library_template_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        name_override: Optional[str] = None,
        project_id: Optional[UUID] = None,
    ) -> Template:
        """Import a library template into a workspace.

        Args:
            session: Database session
            library_template_id: Library template ID to import
            workspace_id: Target workspace ID
            user_id: User ID importing the template
            name_override: Optional custom name for the imported template
            project_id: Optional project ID to assign the template to

        Returns:
            Created Template object

        Raises:
            ValueError: If library template not found
        """
        # Get library template
        library_template = await self.get_library_template_by_id(
            session, library_template_id
        )
        if not library_template:
            raise ValueError(f"Library template not found: {library_template_id}")

        # Create template from library template
        template = Template(
            workspace_id=workspace_id,
            project_id=project_id,
            name=name_override or library_template.name,
            description=library_template.description,
            document_type=library_template.document_type,
            field_schema=library_template.field_schema.copy(),
            default_export_format=ExportFormatEnum(
                library_template.default_export_format.value
            ),
            created_by_user_id=user_id,
            library_template_id=library_template_id,
        )

        session.add(template)

        # Increment usage count
        library_template.increment_usage_count()

        await session.flush()

        logger.info(
            "Imported library template: library_id=%s, template_id=%s, workspace=%s",
            library_template_id,
            template.id,
            workspace_id,
        )

        return template

