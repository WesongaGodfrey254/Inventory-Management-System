"""Application smoke tests.

Run with:  python -m pytest -q
"""

import os
import tempfile

import pytest

from app import create_app, db
from app.models import Product, Sale, User
from app.routes.sales import _create_sale
from app.schema import upgrade_schema
from app.utils import _receipt_parts


@pytest.fixture()
def app():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    app = create_app(
        type(
            "TestConfig",
            (),
            {
                "SECRET_KEY": "test-secret-key",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///" + path,
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "SQLALCHEMY_ENGINE_OPTIONS": {"connect_args": {"check_same_thread": False}},
                "TESTING": True,
                "WTF_CSRF_ENABLED": False,
                "MAIL_SERVER": None,
                "MAIL_USERNAME": None,
                "MAIL_PASSWORD": None,
                "MAIL_DEFAULT_SENDER": None,
                "SESSION_COOKIE_SECURE": False,
                "PREFERRED_URL_SCHEME": "http",
                "LOG_TO_FILE": False,
            },
        )
    )
    with app.app_context():
        upgrade_schema()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()
    os.unlink(path)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_client(app, client):
    with app.app_context():
        user = User(username="admin", shop_name="Test Shop", is_admin=True)
        user.set_password("correct-horse-battery")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return client


def test_health_check(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json()["database"] == "ok"


def test_security_headers(client):
    response = client.get("/login")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in response.headers


def test_login_required(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_registration_and_login(client, app):
    response = client.post(
        "/register",
        data={
            "username": "newshop",
            "shop_name": "New Shop",
            "password": "a-secure-password",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(username="newshop").first()
        assert user is not None
        assert user.shop_name == "New Shop"
        assert user.password_hash and len(user.password_hash) > 128

    response = client.post(
        "/login",
        data={"username": "newshop", "password": "a-secure-password"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"New Shop" in response.data


def test_sale_receipt_uses_shop_name(app, auth_client):
    with app.app_context():
        user = User.query.filter_by(username="admin").first()
        product = Product(
            user_id=user.id,
            sku="P-1",
            name="Sugar 1kg",
            price=150,
            quantity_in_stock=10,
        )
        db.session.add(product)
        db.session.commit()
        product_id = product.id

        result = _create_sale(
            {
                "items": [{"product_id": product_id, "quantity": 2}],
                "customer": {"name": "Elijah", "email": "elijah@example.com"},
            },
            user.id,
        )
        assert "error" not in result
        sale = db.session.get(Sale, result["sale_id"])
        assert sale.total_amount == 300
        assert db.session.get(Product, product_id).quantity_in_stock == 8

        shop, body, html_body = _receipt_parts(sale)
        assert shop == "Test Shop"
        assert "Test Shop" in body
        assert "Inventory Management System" not in body
        assert "Test Shop" in html_body


def test_create_sale_requires_stock_and_login(app, auth_client):
    with app.app_context():
        user = User.query.filter_by(username="admin").first()
        product = Product(
            user_id=user.id,
            sku="P-2",
            name="Salt 1kg",
            price=50,
            quantity_in_stock=1,
        )
        db.session.add(product)
        db.session.commit()
        result = _create_sale(
            {"items": [{"product_id": product.id, "quantity": 5}]},
            user.id,
        )
        assert "Not enough stock" in result["error"]
        assert db.session.get(Product, product.id).quantity_in_stock == 1


def test_settings_rejects_post_without_csrf(app):
    """CSRF stays enabled for browser forms even though tests disable it."""
    secure_app = create_app(
        type(
            "CsrfConfig",
            (),
            {
                "SECRET_KEY": "test-secret-key",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "TESTING": True,
                "WTF_CSRF_ENABLED": True,
                "MAIL_SERVER": None,
                "SESSION_COOKIE_SECURE": False,
                "PREFERRED_URL_SCHEME": "http",
                "LOG_TO_FILE": False,
            },
        )
    )
    with secure_app.app_context():
        upgrade_schema()
        user = User(username="csrf-admin", shop_name="Shop")
        user.set_password("a-secure-password")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client = secure_app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    response = client.post("/settings", data={"shop_name": "Hacked"})
    assert response.status_code == 400
