from django.apps import AppConfig


class DetectionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "detection"
    verbose_name = "Fraud detection"

    def ready(self):
        """Load the trained model in the background when the dev server starts, so the first transaction is fast."""
        import os
        import sys
        import threading

        from django.conf import settings

        # runserver runs the site in a child process flagged RUN_MAIN (or in the
        # only process with --noreload). Other commands (migrate, test...) skip this.
        serving = os.environ.get("RUN_MAIN") == "true" or "--noreload" in sys.argv
        if serving and settings.FRAUD_DETECTION.get("WARMUP", False):
            threading.Thread(target=self._warm_up, name="model-warm-up", daemon=True).start()

    @staticmethod
    def _warm_up():
        import logging

        from .services import ModelNotAvailable, get_predictor

        logger = logging.getLogger(__name__)
        try:
            get_predictor()
            logger.info("Fraud model loaded and ready.")
        except ModelNotAvailable as exc:
            logger.info("Fraud model not loaded yet (%s). Train one with `python -m fraud_engine.train`.", exc)
        except Exception:  # noqa: BLE001
            logger.exception("Could not load the fraud model at start-up.")
