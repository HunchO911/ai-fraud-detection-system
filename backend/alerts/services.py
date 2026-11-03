"""
Alerts: decide who must be told about a risky transaction, and tell them.

    send_alerts(detection)        create + deliver the email / SMS alerts
    retry_failed(max_attempts)    try again for alerts whose delivery failed

Who is told, on which channel, and from which risk level is controlled by the
administrator on the dashboard's Settings page (the DetectionSettings row).
Delivery problems are recorded on the Alert (status, error, attempts), never raised.
"""

import html
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from authentication.models import User
from detection.models import RISK_RANK, DetectionSettings

from .models import Alert
from .sms import get_sms_backend

logger = logging.getLogger(__name__)

CUSTOMER = "customer"
ANALYST = "analyst"


# ---------------------------------------------------------------------------
# Message wording
# ---------------------------------------------------------------------------
def _money(txn) -> str:
    return f"{txn.currency} {txn.amount:,.2f}"


def _when(txn) -> str:
    return timezone.localtime(txn.timestamp).strftime("%d %b %Y, %H:%M")


def _top_reasons(detection, limit: int = 3) -> list[str]:
    """The features that pushed the model's score the most, as short readable lines."""
    ranked = sorted(detection.top_features.items(), key=lambda item: -abs(item[1]))[:limit]
    return [f"{name.replace('_', ' ')} ({value:+.2f})" for name, value in ranked]


def _email_content(audience: str, user, detection) -> tuple[str, str]:
    txn = detection.transaction
    level = detection.risk_level

    if audience == CUSTOMER:
        subject = "Security alert: unusual transaction on your account"
        body = (
            f"Hello {user.first_name or 'there'},\n\n"
            "We noticed an unusual transaction on your account:\n\n"
            f"  Amount:     {_money(txn)}\n"
            f"  Type:       {txn.get_transaction_type_display()} via {txn.get_channel_display()}\n"
            f"  To account: {txn.counterparty_account or 'n/a'}\n"
            f"  When:       {_when(txn)}\n"
            f"  Reference:  {txn.reference}\n\n"
            "If you made this transaction, no action is needed. "
            "If you did not, please contact support immediately.\n"
        )
        return subject, body

    subject = f"[{level.upper()}] Possible fraud: {txn.reference} ({_money(txn)})"
    reasons = "; ".join(_top_reasons(detection)) or "n/a"
    body = (
        f"A transaction was scored as {level.upper()} risk "
        f"({detection.fraud_probability:.0%} fraud probability).\n\n"
        f"  Customer:   {txn.user.email}\n"
        f"  Amount:     {_money(txn)}\n"
        f"  Type:       {txn.get_transaction_type_display()} via {txn.get_channel_display()}\n"
        f"  To account: {txn.counterparty_account or 'n/a'}\n"
        f"  Device:     {txn.device_id or 'n/a'}\n"
        f"  Location:   {', '.join(p for p in (txn.city, txn.country) if p) or 'n/a'}\n"
        f"  When:       {_when(txn)}\n"
        f"  Top signals: {reasons}\n"
        f"  Model:      {detection.model_version}\n\n"
        f"Review it: {settings.FRONTEND_URL.rstrip('/')}/alerts/{detection.id}\n"
    )
    return subject, body


def _sms_content(audience: str, detection) -> str:
    txn = detection.transaction
    if audience == CUSTOMER:
        return (
            f"Security alert: unusual {txn.get_transaction_type_display().lower()} of "
            f"{_money(txn)} on your account (ref {txn.reference}). "
            "Not you? Contact support now."
        )
    return (
        f"FRAUD {detection.risk_level.upper()} {detection.fraud_probability:.0%}: "
        f"{txn.user.email} {txn.currency} {txn.amount:,.0f} ref {txn.reference}"
    )


def _html(text: str) -> str:
    """A minimal HTML version of the plain-text email, so mail clients render line breaks."""
    return (
        '<div style="font-family:Arial,sans-serif;font-size:14px;line-height:1.5;white-space:pre-wrap">'
        + html.escape(text)
        + "</div>"
    )


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------
def deliver(alert: Alert) -> None:
    """Send one alert and record the outcome on it. Never raises."""
    try:
        if alert.channel == Alert.Channel.EMAIL:
            message = EmailMultiAlternatives(
                subject=alert.subject,
                body=alert.message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[alert.destination],
            )
            message.attach_alternative(_html(alert.message), "text/html")
            if message.send(fail_silently=False) == 0:
                raise RuntimeError("The email backend reported that nothing was sent.")
            alert.mark_sent()
        else:
            alert.mark_sent(get_sms_backend().send(alert.destination, alert.message))
    except Exception as exc:  # noqa: BLE001 - anything can go wrong on the network
        logger.warning("Alert %s (%s) failed: %s", alert.pk, alert.channel, exc)
        alert.mark_failed(str(exc))


def _audiences(cfg: DetectionSettings, customer):
    """Yield (user, audience) for everyone who should hear about this transaction, once each."""
    seen = set()
    if cfg.notify_customer:
        seen.add(customer.pk)
        yield customer, CUSTOMER
    if cfg.notify_analysts:
        staff = User.objects.filter(
            role__in=[User.Role.ANALYST, User.Role.ADMIN], is_active=True
        ).exclude(pk__in=seen)
        for user in staff:
            yield user, ANALYST


def _create_if_new(detection, user, channel, destination, subject, message):
    """Create the alert unless this person already got one on this channel for this detection."""
    if Alert.objects.filter(detection_result=detection, recipient=user, channel=channel).exists():
        return None
    return Alert.objects.create(
        detection_result=detection,
        recipient=user,
        channel=channel,
        destination=destination,
        subject=subject,
        message=message,
    )


def send_alerts(detection) -> list[Alert]:
    """Create and deliver every alert this detection calls for. Returns the alerts handled."""
    cfg = DetectionSettings.load()
    rank = RISK_RANK[detection.risk_level]
    wants_email = cfg.email_alerts_enabled and rank >= RISK_RANK[cfg.email_min_risk]
    wants_sms = cfg.sms_alerts_enabled and rank >= RISK_RANK[cfg.sms_min_risk]
    if not (wants_email or wants_sms):
        return []

    handled = []
    for user, audience in _audiences(cfg, detection.transaction.user):
        if wants_email and user.receive_email_alerts and user.email:
            subject, body = _email_content(audience, user, detection)
            alert = _create_if_new(detection, user, Alert.Channel.EMAIL, user.email, subject, body)
            if alert:
                deliver(alert)
                handled.append(alert)
        if wants_sms and user.receive_sms_alerts and user.phone_number:
            alert = _create_if_new(
                detection, user, Alert.Channel.SMS, user.phone_number, "", _sms_content(audience, detection)
            )
            if alert:
                deliver(alert)
                handled.append(alert)
    return handled


def retry_failed(max_attempts: int = 3) -> tuple[int, int]:
    """Re-send failed alerts that have been tried fewer than `max_attempts` times. Returns (sent, still_failed)."""
    sent = failed = 0
    for alert in Alert.objects.filter(status=Alert.Status.FAILED, attempts__lt=max_attempts):
        deliver(alert)
        if alert.status == Alert.Status.SENT:
            sent += 1
        else:
            failed += 1
    return sent, failed
