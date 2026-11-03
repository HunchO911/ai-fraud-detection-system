"""
Read a database address such as the one Render provides:

    postgresql://user:password@host:5432/dbname

and turn it into Django's DATABASES entry. Plain Python, so it is easy to test.
"""

from urllib.parse import unquote, urlparse


def parse_database_url(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError(f"Unsupported database address (expected postgres:// or postgresql://): {parsed.scheme}://")
    config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or 5432),
        "CONN_MAX_AGE": 60,
    }
    if parsed.hostname not in {"localhost", "127.0.0.1", ""}:
        config["OPTIONS"] = {"sslmode": "require"}  # hosted databases expect an encrypted connection
    return config
