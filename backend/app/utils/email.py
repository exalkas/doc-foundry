import logging
from typing import Any, Dict, List, Mapping, Optional

import httpx
from pydantic import BaseModel, EmailStr, Field, HttpUrl, ValidationError

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmailRecipient(BaseModel):
    """Represents an email recipient with a validated email address."""

    email: EmailStr
    name: Optional[str] = None


class EmailMessage(BaseModel):
    """
    Internal representation of an email message to be sent via the provider.

    This is intentionally generic so we can swap email providers if needed.
    """

    to: List[EmailRecipient] = Field(..., min_items=1)
    subject: str = Field(..., min_length=1, max_length=255)
    html: str = Field(..., min_length=1)
    from_email: Optional[EmailStr] = None
    from_name: Optional[str] = None
    headers: Optional[Mapping[str, str]] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Mapping[str, Any]] = None


class EmailSendError(Exception):
    """Raised when sending an email fails."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Any] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class EmailClient:
    """
    Thin async wrapper around the configured email provider (Resend).

    Usage:
        client = EmailClient()
        await client.send_email(
            to=["user@example.com"],
            subject="Welcome",
            html="<p>Hello</p>",
        )
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._validate_config()
        self._http_client = httpx.AsyncClient(
            base_url=self.settings.RESEND_API_BASE_URL,
            headers={
                "Authorization": f"Bearer {self.settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=self.settings.HTTP_CLIENT_TIMEOUT,
        )

    def _validate_config(self) -> None:
        """
        Validate that email configuration is usable.

        Raises:
            RuntimeError: If required email configuration is missing.
        """
        if not self.settings.RESEND_API_KEY:
            raise RuntimeError("RESEND_API_KEY is not configured")
        if not self.settings.DEFAULT_FROM_EMAIL:
            raise RuntimeError("DEFAULT_FROM_EMAIL is not configured")

    async def send_email(
        self,
        *,
        to: List[str] | List[EmailRecipient] | str,
        subject: str,
        html: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        headers: Optional[Mapping[str, str]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send an email using the configured provider.

        Args:
            to: Recipient email(s) as string, list of strings, or list of EmailRecipient.
            subject: Email subject.
            html: HTML body.
            from_email: Override default from email address.
            from_name: Optional sender name.
            headers: Optional extra headers.
            tags: Optional tags for categorization.
            metadata: Optional metadata passed through to the provider.

        Returns:
            Parsed JSON response from the provider.

        Raises:
            EmailSendError: If the provider returns an error or the request fails.
        """
        recipients: List[EmailRecipient] = self._normalize_recipients(to)

        try:
            message = EmailMessage(
                to=recipients,
                subject=subject,
                html=html,
                from_email=from_email or self.settings.DEFAULT_FROM_EMAIL,
                from_name=from_name or self.settings.DEFAULT_FROM_NAME,
                headers=headers,
                tags=tags,
                metadata=metadata,
            )
        except ValidationError as exc:
            logger.error("Invalid email message data: %s", exc.json())
            raise EmailSendError("Invalid email message data") from exc

        payload = self._build_resend_payload(message)

        try:
            response = await self._http_client.post("/emails", json=payload)
        except httpx.RequestError as exc:
            logger.exception("Error sending email via Resend: %s", str(exc))
            raise EmailSendError("Error connecting to email provider") from exc

        if response.status_code >= 400:
            try:
                error_body = response.json()
            except ValueError:
                error_body = response.text

            logger.error(
                "Email provider returned error status=%s body=%s",
                response.status_code,
                error_body,
            )
            raise EmailSendError(
                f"Email provider error: {response.status_code}",
                status_code=response.status_code,
                response_body=error_body,
            )

        try:
            data = response.json()
        except ValueError as exc:
            logger.error("Failed to parse email provider response as JSON: %s", response.text)
            raise EmailSendError("Invalid response from email provider") from exc

        logger.info(
            "Email sent successfully via Resend: subject=%s to=%s provider_id=%s",
            subject,
            [r.email for r in recipients],
            data.get("id"),
        )
        return data

    @staticmethod
    def _normalize_recipients(to: List[str] | List[EmailRecipient] | str) -> List[EmailRecipient]:
        """
        Normalize various `to` types into a list of EmailRecipient.

        Args:
            to: String, list of strings, or list of EmailRecipient.

        Returns:
            List of EmailRecipient.

        Raises:
            EmailSendError: If `to` is empty or of an unsupported type.
        """
        recipients: List[EmailRecipient] = []

        if isinstance(to, str):
            recipients.append(EmailRecipient(email=to))
        elif isinstance(to, list):
            if not to:
                raise EmailSendError("At least one recipient is required")
            if isinstance(to[0], EmailRecipient):
                recipients = list(to)  # type: ignore[assignment]
            else:
                # Assume list of strings
                recipients = [EmailRecipient(email=addr) for addr in to]  # type: ignore[arg-type]
        else:
            raise EmailSendError("Unsupported recipient type")

        return recipients

    @staticmethod
    def _build_resend_payload(message: EmailMessage) -> Dict[str, Any]:
        """
        Build the JSON payload expected by Resend API from our EmailMessage.

        Resend docs: https://resend.com/docs/api-reference/emails/send-email
        """
        from_value = str(message.from_email)
        if message.from_name:
            from_value = f"{message.from_name} <{from_value}>"

        to_values = [str(recipient.email) for recipient in message.to]

        payload: Dict[str, Any] = {
            "from": from_value,
            "to": to_values,
            "subject": message.subject,
            "html": message.html,
        }

        if message.headers:
            payload["headers"] = dict(message.headers)
        if message.tags:
            payload["tags"] = message.tags
        if message.metadata:
            payload["metadata"] = dict(message.metadata)

        return payload

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http_client.aclose()


# Convenience functions for common transactional emails

async def send_email_verification(
    *,
    email: str,
    verification_url: HttpUrl,
) -> None:
    """
    Send an email verification email to a new user.

    Args:
        email: Recipient email address.
        verification_url: Unique verification link for the user.
    """
    settings = get_settings()
    client = EmailClient()

    subject = "Verify your email for DocFoundry.app"
    html = f"""
    <p>Hi,</p>
    <p>Thanks for signing up for {settings.PRODUCT_NAME or "DocFoundry.app"}.</p>
    <p>Please verify your email address by clicking the link below:</p>
    <p><a href="{verification_url}">Verify email</a></p>
    <p>If you did not sign up, you can safely ignore this email.</p>
    """

    await client.send_email(
        to=email,
        subject=subject,
        html=html,
        tags=["email_verification"],
        metadata={"event_type": "email_verification"},
    )
    await client.close()


async def send_password_reset_email(
    *,
    email: str,
    reset_url: HttpUrl,
) -> None:
    """
    Send a password reset email.

    Args:
        email: Recipient email address.
        reset_url: Unique password reset link.
    """
    settings = get_settings()
    client = EmailClient()

    subject = "Reset your password for DocFoundry.app"
    html = f"""
    <p>Hi,</p>
    <p>We received a request to reset the password for your {settings.PRODUCT_NAME or "DocFoundry.app"} account.</p>
    <p>You can reset your password by clicking the link below:</p>
    <p><a href="{reset_url}">Reset password</a></p>
    <p>If you did not request this, you can safely ignore this email.</p>
    """

    await client.send_email(
        to=email,
        subject=subject,
        html=html,
        tags=["password_reset"],
        metadata={"event_type": "password_reset"},
    )
    await client.close()


async def send_welcome_email(
    *,
    email: str,
    full_name: Optional[str] = None,
    get_started_url: Optional[HttpUrl] = None,
) -> None:
    """
    Send a simple welcome email to a new user.

    Args:
        email: Recipient email address.
        full_name: Optional name for personalization.
        get_started_url: Optional link to dashboard or onboarding.
    """
    settings = get_settings()
    client = EmailClient()

    name_part = f"{full_name}," if full_name else ""
    subject = "Welcome to DocFoundry.app"

    if not get_started_url:
        # Fall back to marketing or app URL if configured, else '#'
        base_url = settings.FRONTEND_BASE_URL or settings.APP_BASE_URL or "#"
        get_started_url = HttpUrl(base_url, scheme="https")  # type: ignore[arg-type]

    html = f"""
    <p>Hi {name_part}</p>
    <p>Welcome to {settings.PRODUCT_NAME or "DocFoundry.app"} – where you can turn any document into structured, usable data.</p>
    <p>You can get started by visiting your dashboard:</p>
    <p><a href="{get_started_url}">Open dashboard</a></p>
    <p>You'll be able to create a workspace, upload documents, and design extraction templates.</p>
    """

    await client.send_email(
        to=email,
        subject=subject,
        html=html,
        tags=["welcome_new_user"],
        metadata={"event_type": "welcome_new_user"},
    )
    await client.close()