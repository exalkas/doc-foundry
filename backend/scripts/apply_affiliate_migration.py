#!/usr/bin/env python3
"""Apply affiliate tables migration directly."""

import asyncio
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import engine

async def apply_migration():
    """Apply the affiliate tables migration."""
    import re
    migration_file = Path(__file__).parent.parent / "migrations" / "010_create_affiliate_tables.sql"
    sql_content = migration_file.read_text(encoding="utf-8")
    
    # Split SQL into DO blocks (each DO $$ ... END $$; is a single statement)
    # Pattern matches: DO $$ ... END $$;
    do_block_pattern = r'(DO\s+\$\$.*?END\s+\$\$;)'
    statements = re.findall(do_block_pattern, sql_content, re.DOTALL | re.IGNORECASE)
    
    # Reorder: create payouts before commissions (to resolve FK dependency)
    # Find indices of commissions and payouts creation blocks
    commissions_idx = None
    payouts_idx = None
    for i, stmt in enumerate(statements):
        if 'CREATE TABLE commissions' in stmt:
            commissions_idx = i
        if 'CREATE TABLE payouts' in stmt:
            payouts_idx = i
    
    # If both exist, swap them so payouts is created first
    if commissions_idx is not None and payouts_idx is not None and payouts_idx > commissions_idx:
        statements[commissions_idx], statements[payouts_idx] = statements[payouts_idx], statements[commissions_idx]
        print("  Reordered statements: payouts will be created before commissions")
    
    async with engine.begin() as conn:
        # Execute each DO block separately
        for i, stmt in enumerate(statements, 1):
            print(f"  Executing statement {i}/{len(statements)}...")
            try:
                await conn.exec_driver_sql(stmt)
            except Exception as e:
                # If it's a "relation does not exist" error for payouts in commissions, skip and retry later
                if 'payouts' in str(e).lower() and 'commissions' in stmt:
                    print(f"    ⚠ Skipping commissions (payouts not created yet), will retry...")
                    # Store for later
                    commissions_stmt = stmt
                    continue
                raise
    
    # If we skipped commissions, create it now (payouts should exist)
    if 'commissions_stmt' in locals():
        print("  Creating commissions table now (payouts exists)...")
        async with engine.begin() as conn:
            await conn.exec_driver_sql(commissions_stmt)
    
    print("✓ Affiliate tables migration applied successfully!")

if __name__ == "__main__":
    asyncio.run(apply_migration())

