from django.core.management.base import BaseCommand
from django.test import override_settings

from detection.services import score_pending


class Command(BaseCommand):
    help = (
        "Score transactions that were saved while the model was unavailable "
        "(status 'pending'), oldest first, and send any alerts they trigger."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100, help="most transactions to score (default 100)")

    def handle(self, *args, **options):
        # Send alerts before the command exits; a background thread would be cut off.
        with override_settings(ALERTS_ASYNC=False):
            scored, failed = score_pending(options["limit"])
        self.stdout.write(self.style.SUCCESS(f"Scored {scored} transaction(s)."))
        if failed:
            self.stdout.write(
                self.style.WARNING(
                    f"{failed} could not be scored. Is a model trained? "
                    "Run: python -m fraud_engine.train  (details are in the log above)"
                )
            )
