import os

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))

# Load variables from the project's .env file before reading them below.
# Use an explicit path so the file is found even when the app is started
# from a different working directory (IDE run buttons, systemd, etc.).
# Hosting platforms inject real environment variables, which take precedence.
load_dotenv(os.path.join(basedir, ".env"))

DEFAULT_SECRET_KEY = "dev-secret-key"


def env_bool(name, default=False):
    value = os.environ.get(name, str(default)).strip().lower()
    return value in ("1", "true", "yes", "on")


def env_str(name, default=None):
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


# Vercel sets VERCEL=1 for every deployment. Other hosts can set
# APP_ENV=production. Production mode turns on secure cookies and refuses to
# start with the development secret key.
IS_PRODUCTION = bool(env_str("VERCEL")) or env_str("APP_ENV", "").lower() == "production"


def _database_uri():
    """Return the SQLAlchemy URI, preferring PostgreSQL.

    Deployments must set DATABASE_URL to a PostgreSQL URL, for example:

        postgresql://user:password@host:5432/mysales

    Older providers still hand out ``postgres://`` URLs; SQLAlchemy no longer
    accepts that scheme, so it is rewritten here. When DATABASE_URL is not set
    the app falls back to a local SQLite file, which keeps development simple.
    """
    url = env_str("DATABASE_URL")
    if not url:
        return "sqlite:///" + os.path.join(basedir, "instance", "inventory.db")

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    # PostgreSQL URLs use psycopg 3 in this project. Spelling out the driver
    # avoids SQLAlchemy falling back to psycopg2, which is not installed.
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _engine_options(uri):
    options = {
        "pool_pre_ping": True,  # transparently recover dropped connections
    }
    if uri.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    else:
        # Managed/serverless PostgreSQL closes idle connections; recycle them
        # before that happens so a long-running worker does not see errors.
        options["pool_recycle"] = 280
        options["pool_size"] = 3
        options["max_overflow"] = 2
    return options


class Config:
    SECRET_KEY = env_str("SECRET_KEY", DEFAULT_SECRET_KEY)
    DATABASE_URL = _database_uri()
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options(DATABASE_URL)

    # Never let a production deployment run with the public development key.
    if IS_PRODUCTION and SECRET_KEY == DEFAULT_SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY must be set to a long random value in production. "
            "Add it to the hosting platform's environment variables."
        )

    # Session hardening. Cookies are signed with SECRET_KEY and are only sent
    # over HTTPS in production.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", IS_PRODUCTION)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_SAMESITE = "Lax"
    PREFERRED_URL_SCHEME = "https" if IS_PRODUCTION else "http"

    # Receipts are small; do not accept large request bodies.
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024

    # SMTP settings for sale receipt emails (see README for example values).
    MAIL_SERVER = env_str("MAIL_SERVER")
    MAIL_PORT = int(env_str("MAIL_PORT", "587"))
    MAIL_USE_TLS = env_bool("MAIL_USE_TLS", True)
    MAIL_USE_SSL = env_bool("MAIL_USE_SSL", False)
    MAIL_USERNAME = env_str("MAIL_USERNAME")
    MAIL_PASSWORD = env_str("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = env_str("MAIL_DEFAULT_SENDER") or MAIL_USERNAME
