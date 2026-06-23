"""Organization email delivery."""

from urllib.parse import quote
from uuid import UUID

import structlog
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from agentproof_backend.apps.organizations.models import OrganizationInvitation

logger = structlog.get_logger(__name__)


def send_organization_invitation_email(
    *,
    invitation_id: UUID,
    token: str,
) -> None:
    """Send an organization invitation after a transaction commit."""

    try:
        invitation = OrganizationInvitation.objects.select_related("organization", "invited_by").get(id=invitation_id)

        accept_url = f"{settings.APP_BASE_URL.rstrip('/')}/invitations/accept?token={quote(token)}"

        body = render_to_string(
            "emails/organization_invitation.txt",
            {
                "invitation": invitation,
                "accept_url": accept_url,
            },
        )

        send_mail(
            subject=f"You were invited to {invitation.organization.name}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("oganization_invitation_email_failed", invitation_id=str(invitation_id))
