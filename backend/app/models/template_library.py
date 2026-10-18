from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    ARRAY,
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.types import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from . import Base


class TemplateCategoryEnum(str, Enum):
    """Enum representing template library categories."""

    ACCOUNTING_FINANCE = "accounting_finance"
    LOGISTICS = "logistics"
    ECOMMERCE = "ecommerce"
    HR_LEGAL = "hr_legal"


class ExportFormatEnum(str, Enum):
    """Enum representing supported default export formats for a template."""

    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"


class TemplateLibrary(Base):
    """Template library model for pre-built templates.

    These templates are system-wide and can be imported by any workspace.
    """

    __tablename__ = "template_library"

    id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    # Basic metadata
    name: Mapped[str] = Column(String(255), nullable=False)
    description: Mapped[Optional[str]] = Column(Text, nullable=True)
    category: Mapped[TemplateCategoryEnum] = Column(
        SAEnum(
            TemplateCategoryEnum,
            name="template_category_enum",
            native_enum=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    document_type: Mapped[Optional[str]] = Column(String(128), nullable=True)

    # Schema describing fields, types, validation, etc.
    field_schema: Mapped[Dict[str, Any]] = Column(JSON, nullable=False)

    default_export_format: Mapped[ExportFormatEnum] = Column(
        SAEnum(
            ExportFormatEnum,
            name="export_format_enum",
            native_enum=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ExportFormatEnum.JSON,
    )

    # UI enhancements
    preview_image_url: Mapped[Optional[str]] = Column(String(512), nullable=True)
    tags: Mapped[Optional[List[str]]] = Column(ARRAY(String), nullable=True)

    # Management
    is_active: Mapped[bool] = Column(Boolean, nullable=False, default=True)
    usage_count: Mapped[int] = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    imported_templates: Mapped[List["Template"]] = relationship(
        "Template",
        back_populates="library_template",
        lazy="selectin",
    )

    def increment_usage_count(self) -> None:
        """Increment the usage counter."""
        self.usage_count = (self.usage_count or 0) + 1


# Indexes for common access patterns
Index(
    "ix_template_library_category",
    TemplateLibrary.category,
)
Index(
    "ix_template_library_is_active",
    TemplateLibrary.is_active,
)
Index(
    "ix_template_library_category_active",
    TemplateLibrary.category,
    TemplateLibrary.is_active,
)

