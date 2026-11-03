"""
Fast settings for the test suite that need no PostgreSQL server:

    python manage.py test --settings=config.test_settings

Everything else is inherited from the real settings.
"""

import os

os.environ.setdefault("DJANGO_DEBUG", "True")

from .settings import *  # noqa: E402,F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

# Send alerts inside the request so tests can check them straight away.
ALERTS_ASYNC = False

# A fast hasher keeps tests quick. Never use this outside tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
