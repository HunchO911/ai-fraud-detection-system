"""Tests for the HTTPS email backend and for the demo redirect switches."""

import io
import json
import urllib.error
from unittest import mock

from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import SimpleTestCase, TestCase, override_settings

from .email_backends import API_URL, ResendEmailBackend
from .models import Alert
from .services import send_alerts
from .test_services import make_detection, make_user


def make_message():
    message = EmailMultiAlternatives(
        subject="Alert", body="plain text", from_email="Fraud Alerts <onboarding@resend.dev>", to=["you@zohomail.com"]
    )
    message.attach_alternative("<p>html</p>", "text/html")
    return message


@override_settings(RESEND_API_KEY="re_test_key")
class ResendBackendTests(SimpleTestCase):
    def test_sends_the_documented_request(self):
        with mock.patch("alerts.email_backends.urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = b'{"id": "abc"}'
            sent = ResendEmailBackend().send_messages([make_message()])

        self.assertEqual(sent, 1)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, API_URL)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer re_test_key")
        self.assertEqual(
            json.loads(request.data),
            {
                "from": "Fraud Alerts <onboarding@resend.dev>",
                "to": ["you@zohomail.com"],
                "subject": "Alert",
                "text": "plain text",
                "html": "<p>html</p>",
            },
        )

    def test_a_rejected_email_raises_with_the_reason(self):
        error = urllib.error.HTTPError(API_URL, 403, "Forbidden", {}, io.BytesIO(b'{"message": "not verified"}'))
        with mock.patch("alerts.email_backends.urllib.request.urlopen", side_effect=error):
            with self.assertRaises(RuntimeError) as caught:
                ResendEmailBackend().send_messages([make_message()])
        self.assertIn("403", str(caught.exception))
        self.assertIn("not verified", str(caught.exception))

    def test_unreachable_service_raises(self):
        with mock.patch("alerts.email_backends.urllib.request.urlopen", side_effect=urllib.error.URLError("no route")):
            with self.assertRaisesMessage(RuntimeError, "Could not reach Resend"):
                ResendBackendTests.send()

    @staticmethod
    def send():
        ResendEmailBackend().send_messages([make_message()])

    @override_settings(RESEND_API_KEY="")
    def test_missing_key(self):
        with self.assertRaisesMessage(RuntimeError, "RESEND_API_KEY"):
            ResendEmailBackend().send_messages([make_message()])
        self.assertEqual(ResendEmailBackend(fail_silently=True).send_messages([make_message()]), 0)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SMS_BACKEND="console")
class RedirectTests(TestCase):
    def setUp(self):
        self.customer = make_user("customer@example.com", phone="+2340000000003")
        self.analyst = make_user("analyst@example.com", role="analyst", phone="+2340000000002")

    @override_settings(ALERT_EMAIL_REDIRECT="inbox@zohomail.com")
    def test_every_email_goes_to_the_one_inbox_and_says_who_it_was_for(self):
        send_alerts(make_detection(self.customer, 0.95))
        self.assertEqual(len(mail.outbox), 2)
        self.assertTrue(all(m.to == ["inbox@zohomail.com"] for m in mail.outbox))
        subjects = sorted(m.subject.split("]")[0] for m in mail.outbox)
        self.assertEqual(subjects, ["[for analyst@example.com", "[for customer@example.com"])
        # The dashboard still records who each alert was intended for.
        self.assertEqual(
            set(Alert.objects.filter(channel="email").values_list("destination", flat=True)),
            {"customer@example.com", "analyst@example.com"},
        )

    @override_settings(ALERT_EMAIL_REDIRECT="")
    def test_no_redirect_by_default(self):
        send_alerts(make_detection(self.customer, 0.95))
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["analyst@example.com", "customer@example.com"])
        self.assertFalse(any(m.subject.startswith("[for") for m in mail.outbox))

    @override_settings(ALERT_SMS_REDIRECT="+2349000000000")
    def test_sms_redirect(self):
        with mock.patch("alerts.services.get_sms_backend") as backend:
            backend.return_value.send.return_value = "fake-message-id"  # the real sender returns an id (text)
            send_alerts(make_detection(self.customer, 0.95))
        numbers = [call.args[0] for call in backend.return_value.send.call_args_list]
        self.assertEqual(numbers, ["+2349000000000", "+2349000000000"])
