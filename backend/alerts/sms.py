"""
SMS providers. Choose one with SMS_BACKEND in .env:

    console   (default) prints the message to the terminal; nothing is sent
    termii    sends through Termii (https://termii.com), which suits Nigerian numbers

Adding another provider (Africa's Talking, Twilio...) means writing one more
class with a `send(to, message)` method and listing it in get_sms_backend().
"""

import json
import logging
import urllib.error
import urllib.request
import uuid

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


class SMSError(Exception):
    """The provider refused or could not deliver the message."""


class ConsoleSMSBackend:
    """Development backend: logs the SMS instead of sending it."""

    def send(self, to: str, message: str) -> str:
        logger.info("[SMS console] to %s: %s", to, message)
        return f"console-{uuid.uuid4().hex[:12]}"


class TermiiSMSBackend:
    """Sends SMS through Termii's REST API. Needs TERMII_API_KEY and a registered TERMII_SENDER_ID."""

    TIMEOUT_SECONDS = 10  # a slow provider must not hang the API

    def send(self, to: str, message: str) -> str:
        if not settings.TERMII_API_KEY or not settings.TERMII_SENDER_ID:
            raise SMSError("Set TERMII_API_KEY and TERMII_SENDER_ID in .env to send real SMS.")

        payload = json.dumps(
            {
                "to": to.lstrip("+"),  # Termii wants 2348012345678, without the plus
                "from": settings.TERMII_SENDER_ID,
                "sms": message,
                "type": "plain",
                "channel": settings.TERMII_CHANNEL,
                "api_key": settings.TERMII_API_KEY,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{settings.TERMII_BASE_URL.rstrip('/')}/api/sms/send",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.TIMEOUT_SECONDS) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise SMSError(f"Termii returned HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise SMSError(f"Could not reach Termii: {exc}") from exc

        message_id = body.get("message_id")
        if not message_id:
            raise SMSError(f"Termii did not accept the message: {body}")
        return str(message_id)


def get_sms_backend():
    name = getattr(settings, "SMS_BACKEND", "console").lower()
    if name == "termii":
        return TermiiSMSBackend()
    if name == "console":
        return ConsoleSMSBackend()
    raise ImproperlyConfigured(f"Unknown SMS_BACKEND '{name}'. Use 'console' or 'termii'.")
