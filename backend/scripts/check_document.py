#!/usr/bin/env python3
"""Check a specific document in the database."""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv
from uuid import UUID

# Load .env file
backend_dir = Path(__file__).parent.parent
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# Add backend directory to Python path
sys.path.insert(0, str(backend_dir))

from app.database import AsyncSessionLocal
from sqlalchemy import select
from app.models.document import Document
from app.models.workspace import Workspace


async def check_document(document_id: str):
    """Check a specific document."""
    async with AsyncSessionLocal() as session:
        doc_uuid = UUID(document_id)
        
        # Get document
        result = await session.execute(
            select(Document).where(Document.id == doc_uuid)
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            print(f"Document {document_id} NOT FOUND in database")
            return
        
        print(f"Document {document_id} found:")
        print(f"  File name: {doc.file_name}")
        print(f"  Workspace ID: {doc.workspace_id}")
        print(f"  Status: {doc.status.value}")
        print(f"  Created at: {doc.created_at}")
        
        # Get workspace
        ws_result = await session.execute(
            select(Workspace).where(Workspace.id == doc.workspace_id)
        )
        ws = ws_result.scalar_one_or_none()
        if ws:
            print(f"  Workspace name: {ws.name}")
        else:
            print(f"  Workspace NOT FOUND (ID: {doc.workspace_id})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_document.py <document_id>")
        sys.exit(1)
    
    document_id = sys.argv[1]
    asyncio.run(check_document(document_id))

