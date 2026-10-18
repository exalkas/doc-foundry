"""Affiliate redirect router for tracking clicks."""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.affiliate import Affiliate, AffiliateStatus
from app.models.affiliate_link import AffiliateLink
from app.services.attribution_service import AttributionService
from app.services.logging_service import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Configuration
AFFILIATE_COOKIE_NAME = os.getenv("AFFILIATE_COOKIE_NAME", "aff_id")
AFFILIATE_ATTRIBUTION_WINDOW_DAYS = int(os.getenv("AFFILIATE_ATTRIBUTION_WINDOW_DAYS", "60"))
FRONTEND_URL = os.getenv("FRONTEND_URL", os.getenv("NEXT_PUBLIC_FRONTEND_URL", "http://localhost:3000"))


@router.get("/r/{slug}")
async def redirect_affiliate_link(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Redirect affiliate link and set tracking cookie."""
    # Find affiliate link by slug
    result = await db.execute(
        select(AffiliateLink)
        .join(Affiliate)
        .where(
            AffiliateLink.slug == slug,
            Affiliate.status == AffiliateStatus.APPROVED,
        )
    )
    affiliate_link = result.scalar_one_or_none()

    if not affiliate_link:
        # If link not found, redirect to homepage
        logger.warning(f"Affiliate link not found: {slug}")
        return RedirectResponse(url=f"{FRONTEND_URL}/", status_code=status.HTTP_302_FOUND)

    # Track click
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    referrer = request.headers.get("referer")

    try:
        await AttributionService.track_click(
            db=db,
            affiliate_link_id=affiliate_link.id,
            ip_address=client_ip,
            user_agent=user_agent,
            referrer=referrer,
        )
    except Exception as e:
        logger.error(f"Failed to track click: {e}")
        # Continue with redirect even if tracking fails

    # Build redirect URL
    destination = affiliate_link.destination_url
    if not destination.startswith(("http://", "https://")):
        # Relative URL - prepend frontend URL
        destination = f"{FRONTEND_URL}{destination}"

    # Create redirect response
    response = RedirectResponse(url=destination, status_code=status.HTTP_302_FOUND)

    # Set affiliate tracking cookie
    # Cookie expires in attribution window days
    from datetime import datetime, timedelta
    expires = datetime.utcnow() + timedelta(days=AFFILIATE_ATTRIBUTION_WINDOW_DAYS)

    response.set_cookie(
        key=AFFILIATE_COOKIE_NAME,
        value=affiliate_link.affiliate.slug,
        max_age=AFFILIATE_ATTRIBUTION_WINDOW_DAYS * 24 * 60 * 60,  # seconds
        httponly=True,
        secure=os.getenv("ENVIRONMENT", "development") == "production",
        samesite="lax",
        path="/",
    )

    logger.info(f"Redirected affiliate link {slug} to {destination}")

    return response

