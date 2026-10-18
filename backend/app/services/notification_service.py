"""Notification service for sending emails and alerts."""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

try:
    import resend
except ImportError:
    resend = None

from app.config import settings

logger = logging.getLogger(__name__)


class NotificationError(Exception):
    """Raised when notification sending fails."""

    pass


class NotificationService:
    """Service for sending notifications (email, alerts, etc.)."""

    def __init__(self):
        """Initialize notification service."""
        self.enabled = settings.ENABLE_NOTIFICATIONS
        if resend and settings.RESEND_API_KEY:
            self.resend_client = resend.Resend(api_key=settings.RESEND_API_KEY)
        else:
            self.resend_client = None
            if self.enabled:
                logger.warning("Resend API key not configured, notifications will be logged only")

    async def send_email(
        self,
        to: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """Send an email.

        Args:
            to: Recipient email address
            subject: Email subject
            html_content: HTML email content
            text_content: Optional plain text content

        Returns:
            True if sent successfully
        """
        if not self.enabled:
            logger.info("Notifications disabled, skipping email to %s: %s", to, subject)
            return False

        if not self.resend_client:
            logger.info("Email service not configured, logging email: to=%s, subject=%s", to, subject)
            return False

        try:
            params: Dict[str, Any] = {
                "from": settings.EMAIL_FROM,
                "to": [to],
                "subject": subject,
                "html": html_content,
            }
            if text_content:
                params["text"] = text_content

            response = self.resend_client.emails.send(params)
            logger.info("Email sent successfully: to=%s, subject=%s, id=%s", to, subject, response.get("id"))
            return True
        except Exception as e:
            logger.exception("Failed to send email: %s", e)
            raise NotificationError(f"Failed to send email: {str(e)}") from e

    async def send_quota_warning(
        self,
        to: str,
        workspace_name: str,
        usage_percentage: float,
        pages_used: int,
        quota: int,
        remaining: int,
    ) -> bool:
        """Send quota warning email.

        Args:
            to: Recipient email address
            workspace_name: Workspace name
            usage_percentage: Usage percentage (0.0 to 1.0)
            pages_used: Pages used
            quota: Total quota
            remaining: Remaining pages

        Returns:
            True if sent successfully
        """
        subject = f"Quota Warning: {workspace_name} - {usage_percentage:.0%} Used"

        html_content = f"""
        <html>
        <body>
            <h2>Quota Warning</h2>
            <p>Your workspace <strong>{workspace_name}</strong> has used {usage_percentage:.0%} of its monthly quota.</p>
            <ul>
                <li>Pages used: {pages_used:,} / {quota:,}</li>
                <li>Remaining: {remaining:,} pages</li>
            </ul>
            <p>Consider upgrading your plan to avoid service interruption.</p>
        </body>
        </html>
        """

        return await self.send_email(to, subject, html_content)

    async def send_payment_failed(
        self,
        to: str,
        workspace_name: str,
        amount: float,
        currency: str = "USD",
        grace_period_days: int = 7,
    ) -> bool:
        """Send payment failure notification.

        Args:
            to: Recipient email address
            workspace_name: Workspace name
            amount: Payment amount
            currency: Currency code
            grace_period_days: Grace period in days

        Returns:
            True if sent successfully
        """
        subject = f"Payment Failed: {workspace_name}"

        html_content = f"""
        <html>
        <body>
            <h2>Payment Failed</h2>
            <p>We were unable to process your payment for workspace <strong>{workspace_name}</strong>.</p>
            <ul>
                <li>Amount: {currency} {amount:.2f}</li>
                <li>Grace period: {grace_period_days} days</li>
            </ul>
            <p>Please update your payment method to avoid service interruption.</p>
        </body>
        </html>
        """

        return await self.send_email(to, subject, html_content)

    async def send_webhook_failure(
        self,
        to: str,
        workspace_name: str,
        webhook_url: str,
        failure_count: int,
        max_failures: int = 5,
    ) -> bool:
        """Send webhook failure notification.

        Args:
            to: Recipient email address
            workspace_name: Workspace name
            webhook_url: Webhook URL
            failure_count: Number of consecutive failures
            max_failures: Maximum failures before disabling

        Returns:
            True if sent successfully
        """
        subject = f"Webhook Delivery Failing: {workspace_name}"

        html_content = f"""
        <html>
        <body>
            <h2>Webhook Delivery Failing</h2>
            <p>Your webhook endpoint is experiencing delivery failures.</p>
            <ul>
                <li>Workspace: <strong>{workspace_name}</strong></li>
                <li>Webhook URL: {webhook_url}</li>
                <li>Consecutive failures: {failure_count} / {max_failures}</li>
            </ul>
            <p>Please check your webhook endpoint. It will be disabled after {max_failures} consecutive failures.</p>
        </body>
        </html>
        """

        return await self.send_email(to, subject, html_content)

    async def send_workspace_suspended(
        self,
        to: str,
        workspace_name: str,
        reason: str,
    ) -> bool:
        """Send workspace suspension notification.

        Args:
            to: Recipient email address
            workspace_name: Workspace name
            reason: Suspension reason

        Returns:
            True if sent successfully
        """
        subject = f"Workspace Suspended: {workspace_name}"

        html_content = f"""
        <html>
        <body>
            <h2>Workspace Suspended</h2>
            <p>Your workspace <strong>{workspace_name}</strong> has been suspended.</p>
            <p><strong>Reason:</strong> {reason}</p>
            <p>Please contact support to resolve this issue.</p>
        </body>
        </html>
        """

        return await self.send_email(to, subject, html_content)

    async def send_onboarding_email(
        self,
        to: str,
        workspace_name: str,
        user_name: str,
    ) -> bool:
        """Send onboarding welcome email.

        Args:
            to: Recipient email address
            workspace_name: Workspace name
            user_name: User name

        Returns:
            True if sent successfully
        """
        subject = f"Welcome to {settings.APP_NAME}!"

        html_content = f"""
        <html>
        <body>
            <h2>Welcome, {user_name}!</h2>
            <p>Thank you for joining <strong>{workspace_name}</strong> on {settings.APP_NAME}.</p>
            <p>Get started by:</p>
            <ol>
                <li>Upload your first document</li>
                <li>Create a template to extract data</li>
                <li>View your extraction results</li>
            </ol>
            <p>Need help? Check out our documentation or contact support.</p>
        </body>
        </html>
        """

        return await self.send_email(to, subject, html_content)

