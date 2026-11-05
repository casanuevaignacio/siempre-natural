import logging
import smtplib
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import send_mail


logger = logging.getLogger(__name__)


def send_configured_email(*, recipient, subject, message):
    if not (
        settings.EMAIL_HOST
        and settings.EMAIL_HOST_USER
        and settings.EMAIL_HOST_PASSWORD
    ):
        logger.warning("Configured email was not sent: SMTP is not fully configured.")
        return False

    try:
        sent_count = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except (OSError, smtplib.SMTPException):
        logger.exception("Could not send configured email.")
        return False

    if sent_count != 1:
        logger.error("Email backend did not send a message.")
        return False
    return True


def account_url(path, **query):
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}{path}?{urlencode(query)}"
