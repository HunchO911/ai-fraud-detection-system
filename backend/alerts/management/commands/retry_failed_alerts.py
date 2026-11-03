from django.core.management.base import BaseCommand

from alerts.services import retry_failed


class Command(BaseCommand):
    help = "Try again to send the email / SMS alerts whose delivery failed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-attempts", type=int, default=3, help="give up on an alert after this many tries (default 3)"
        )

    def handle(self, *args, **options):
        sent, still_failed = retry_failed(options["max_attempts"])
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} alert(s)."))
        if still_failed:
            self.stdout.write(self.style.WARNING(f"{still_failed} still failing; see the Alert rows in the admin."))
