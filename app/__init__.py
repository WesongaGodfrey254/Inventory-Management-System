import logging
import os
from logging.handlers import RotatingFileHandler

import click
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.engine import make_url
from werkzeug.middleware.proxy_fix import ProxyFix

try:
    from flask_migrate import Migrate
except ImportError:  # migrations are optional for running the app
    Migrate = None

db = SQLAlchemy()
migrate = Migrate() if Migrate else None
csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _configure_logging(app):
    """Log to stdout/stderr, and to a file when the filesystem allows it.

    Serverless platforms such as Vercel run with a read-only project
    directory, so the file handler is optional. Console output is what the
    platform captures.
    """
    app.logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    if not any(
        isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, RotatingFileHandler)
        for handler in app.logger.handlers
    ):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        app.logger.addHandler(stream_handler)

    if not app.config.get("LOG_TO_FILE", _env_bool("LOG_TO_FILE", True)):
        return

    try:
        os.makedirs(app.instance_path, exist_ok=True)
        log_path = os.path.abspath(os.path.join(app.instance_path, "app.log"))
    except OSError as exc:
        app.logger.warning("File logging disabled: %s", exc)
        return

    already_added = any(
        isinstance(handler, RotatingFileHandler)
        and getattr(handler, "baseFilename", None) == log_path
        for handler in app.logger.handlers
    )
    if already_added:
        return

    try:
        handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3)
    except OSError as exc:
        app.logger.warning("File logging disabled: %s", exc)
        return

    handler.setLevel(logging.INFO)
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)


def _security_headers(response):
    """Add conservative security headers to every response."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
    )
    # The dashboard uses a small inline script and the templates use inline
    # styles, so inline code must be allowed. Everything else is restricted.
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data:; "
        "font-src 'self' https://cdn.jsdelivr.net data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'",
    )
    if request.is_secure:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


def _create_or_update_admin(username, password, shop_name=None):
    """Create/refresh an admin account from values supplied at deploy time."""
    if len(password) < 12:
        raise click.ClickException("The admin password must be at least 12 characters.")

    from .models import User

    user = User.query.filter_by(username=username).first()
    if user is None:
        user = User(username=username)
        db.session.add(user)
    user.shop_name = (shop_name or user.shop_name or "My Shop").strip()
    user.is_admin = True
    user.set_password(password)
    db.session.commit()
    return user


def _ensure_admin_from_env():
    """Allow `flask init-db` to seed the admin from environment variables."""
    username = os.environ.get("ADMIN_USERNAME")
    password = os.environ.get("ADMIN_PASSWORD")
    if not username or not password:
        return None
    return _create_or_update_admin(
        username, password, os.environ.get("ADMIN_SHOP_NAME")
    )


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)
    if config_object:
        app.config.from_object(config_object)
    else:
        from config import Config
        app.config.from_object(Config)

    _configure_logging(app)

    # Vercel terminates TLS at its proxy; trust its forwarding headers so
    # redirects and secure cookies see the original HTTPS scheme.
    if os.environ.get("VERCEL") or app.config.get("PREFERRED_URL_SCHEME") == "https":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Log which database is in use without ever printing the password.
    database_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    try:
        safe_uri = make_url(database_uri).render_as_string(hide_password=True)
    except Exception:
        safe_uri = database_uri
    app.logger.info("Using database: %s", safe_uri)

    db.init_app(app)
    if migrate:
        migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)

    app.after_request(_security_headers)

    # Make it obvious in the console whether receipts can be emailed. Settings
    # are read once at startup, so editing .env requires restarting the app.
    if app.config.get("MAIL_SERVER"):
        app.logger.info(
            "Receipt emails enabled via %s:%s",
            app.config.get("MAIL_SERVER"),
            app.config.get("MAIL_PORT"),
        )
    else:
        app.logger.warning(
            "Receipt emails are DISABLED: MAIL_SERVER is not set. "
            "Fill in .env and restart the app."
        )

    # Register blueprints
    from .routes.auth import auth_bp
    from .routes.products import products_bp
    from .routes.sales import sales_bp
    from .routes.main import main_bp
    from .routes.reports import reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp, url_prefix="/products")
    app.register_blueprint(sales_bp, url_prefix="/sales")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(main_bp)

    # Import models for flask shell / migrations
    from . import models  # noqa: F401

    @app.cli.command("init-db")
    def init_db_command():
        """Create missing tables, apply schema upgrades and seed the admin."""
        from .schema import upgrade_schema

        upgrade_schema()
        created = _ensure_admin_from_env()
        if created is not None:
            click.echo(f"Admin user '{created.username}' is ready.")
        click.echo("Database schema is ready.")

    @app.cli.command("create-admin")
    @click.option("--username", envvar="ADMIN_USERNAME", prompt="Admin username")
    @click.option(
        "--password",
        envvar="ADMIN_PASSWORD",
        prompt="Admin password (min 12 characters)",
        hide_input=True,
        confirmation_prompt=True,
    )
    @click.option("--shop-name", envvar="ADMIN_SHOP_NAME", default="My Shop")
    def create_admin_command(username, password, shop_name):
        """Create or update an administrator account."""
        user = _create_or_update_admin(username, password, shop_name)
        click.echo(f"Admin user '{user.username}' is ready.")

    return app
