"""
Send email through Resend's HTTPS API (https://resend.com).

Why: free Render web services block the usual outgoing mail ports (25, 465, 587), so
SMTP providers such as Zoho cannot be used from them. This backend talks over normal
HTTPS (port 443), which is not blocked. It needs no extra library.

Use it by setting, in the environment:
    EMAIL_BACKEND=alerts.email_backends.ResendEmailBackend
    RESEND_API_KEY=re_...
    DEFAULT_FROM_EMAIL=Fraud Alerts <onboarding@resend.dev>
"""

import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

API_URL = "https://api.resend.com/emails"


class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        """Send each message; returns how many were accepted (Django's backend contract)."""
        if not email_messages:
            return 0
        api_key = getattr(settings, "RESEND_API_KEY", "")
        if not api_key:
            if self.fail_silently:
                return 0
            raise RuntimeError("RESEND_API_KEY is not set.")
        sent = 0
        for message in email_messages:
            try:
                self._send_one(message, api_key)
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent

    @staticmethod
    def _send_one(message, api_key):
        payload = {
            "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
            "to": list(message.to),
            "subject": message.subject,
            "text": message.body,
        }
        if message.cc:
            payload["cc"] = list(message.cc)
        for content, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                payload["html"] = content

        request = urllib.request.Request(
            API_URL,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "fraud-detection-alerts/1.0",  # some firewalls refuse the default Python agent
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=getattr(settings, "EMAIL_TIMEOUT", 10)) as response:
                response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"Resend rejected the email ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach Resend: {exc.reason}") from exc
