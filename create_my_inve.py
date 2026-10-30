#!/usr/bin/env python3
"""
Run this script to create the "My inve" project folder on your Desktop.

Usage:
    python create_my_inve.py

If your Desktop is in a non-standard location on Windows, edit the DESKTOP_DIR variable.
"""
import os
from pathlib import Path

# Adjust this if your Desktop path is different
DESKTOP_DIR = Path.home() / "Desktop"
TARGET_DIR = DESKTOP_DIR / "My inve"

files = {
    "requirements.txt": """Flask>=2.2
Flask-SQLAlchemy
Flask-Migrate
Flask-WTF
Flask-Login
python-dotenv
""",
    "run.py": """from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
""",
    "config.py": """import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(basedir, "instance", "inventory.db"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
""",
    "README.md": """Inventory & Sales Management Starter (Flask)

1. Create virtualenv & install
   python -m venv venv
   source venv/bin/activate    # on Windows: venv\\Scripts\\activate
   pip install -r requirements.txt

2. Initialize DB & migrations
   export FLASK_APP=run.py     # on Windows: set FLASK_APP=run.py
   flask db init
   flask db migrate -m "Initial migrate"
   flask db upgrade

3. Create an admin user (simple method)
   from app import create_app, db
   app = create_app()
   with app.app_context():
       from app.models import User
       u = User(username="admin", is_admin=True)
       u.set_password("password")
       db.session.add(u)
       db.session.commit()

4. Run
   python run.py
   Open http://127.0.0.1:5000/ and login with the account created.

Notes:
- Default DB is sqlite instance/inventory.db. For production, set DATABASE_URL env var to postgres or mysql.
- Add role-based checks, tests, more reports, and a JS POS UI as next steps.
""",
    "app/__init__.py": """from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = "auth.login"

def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)
    if config_object:
        app.config.from_object(config_object)
    else:
        from config import Config
        app.config.from_object(Config)

    # ensure instance folder exists
    try:
        import os
        os.makedirs(app.instance_path, exist_ok=True)
    except Exception:
        pass

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)

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

    return app
""",
    "app/models.py": """from . import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text)

    products = db.relationship("Product", back_populates="category")

class Supplier(db.Model):
    __tablename__ = "suppliers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    contact = db.Column(db.String(200))
    email = db.Column(db.String(200))

    products = db.relationship("Product", back_populates="supplier")

class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(64), unique=True, nullable=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10,2), nullable=False)
    cost = db.Column(db.Numeric(10,2), nullable=True)
    quantity_in_stock = db.Column(db.Integer, default=0)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)

    category = db.relationship("Category", back_populates="products")
    supplier = db.relationship("Supplier", back_populates="products")

    def adjust_stock(self, delta, note=""):
        self.quantity_in_stock = (self.quantity_in_stock or 0) + delta
        movement = StockMovement(
            product=self,
            change=delta,
            note=note
        )
        db.session.add(movement)

class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    address = db.Column(db.Text)

    sales = db.relationship("Sale", back_populates="customer")

class Sale(db.Model):
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    total_amount = db.Column(db.Numeric(12,2), default=Decimal("0.00"))
    receipt_number = db.Column(db.String(64), unique=True, nullable=True)

    items = db.relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    customer = db.relationship("Customer", back_populates="sales")
    user = db.relationship("User")

    def compute_total(self):
        total = sum((item.subtotal for item in self.items), Decimal("0.00"))
        self.total_amount = total
        return total

class SaleItem(db.Model):
    __tablename__ = "sale_items"
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"))
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"))
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10,2), nullable=False)
    subtotal = db.Column(db.Numeric(12,2), nullable=False)

    sale = db.relationship("Sale", back_populates="items")
    product = db.relationship("Product")

class StockMovement(db.Model):
    __tablename__ = "stock_movements"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    change = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(255))

    product = db.relationship("Product")
""",
    "app/forms.py": """from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, DecimalField, IntegerField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Length, Optional, NumberRange

class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    submit = SubmitField("Register")

class ProductForm(FlaskForm):
    sku = StringField("SKU", validators=[Optional(), Length(max=64)])
    name = StringField("Name", validators=[DataRequired()])
    description = TextAreaField("Description", validators=[Optional()])
    price = DecimalField("Price", validators=[DataRequired(), NumberRange(min=0)])
    cost = DecimalField("Cost", validators=[Optional(), NumberRange(min=0)])
    quantity_in_stock = IntegerField("Quantity", validators=[Optional()])
    category_id = SelectField("Category", coerce=int, validators=[Optional()])
    supplier_id = SelectField("Supplier", coerce=int, validators=[Optional()])
    submit = SubmitField("Save")
""",
    "app/routes/auth.py": """from flask import Blueprint, render_template, redirect, url_for, flash, request
from .. import db, login
from ..models import User
from ..forms import LoginForm, RegisterForm
from flask_login import login_user, logout_user, login_required

auth_bp = Blueprint("auth", __name__, template_folder="templates")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash("Username already taken", "warning")
            return redirect(url_for("auth.register"))
        u = User(username=form.username.data)
        u.set_password(form.password.data)
        db.session.add(u)
        db.session.commit()
        flash("Account created. Please login.", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html", form=form)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        u = User.query.filter_by(username=form.username.data).first()
        if u and u.check_password(form.password.data):
            login_user(u)
            flash("Logged in", "success")
            next_page = request.args.get("next") or url_for("main.dashboard")
            return redirect(next_page)
        flash("Invalid credentials", "danger")
    return render_template("login.html", form=form)

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out", "info")
    return redirect(url_for("auth.login"))

@login.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
""",
    "app/routes/main.py": """from flask import Blueprint, render_template
from flask_login import login_required
from ..models import Product, Sale

main_bp = Blueprint("main", __name__, template_folder="templates")

@main_bp.route("/")
@login_required
def dashboard():
    total_products = Product.query.count()
    recent_sales = Sale.query.order_by(Sale.created_at.desc()).limit(10).all()
    return render_template("dashboard.html", total_products=total_products, recent_sales=recent_sales)
""",
    "app/routes/products.py": """from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ..models import Product, Category, Supplier
from .. import db
from ..forms import ProductForm

products_bp = Blueprint("products", __name__, template_folder="templates")

@products_bp.route("/")
@login_required
def list_products():
    products = Product.query.order_by(Product.name).all()
    return render_template("products.html", products=products)

@products_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_product():
    form = ProductForm()
    form.category_id.choices = [(0, "-")] + [(c.id, c.name) for c in Category.query.order_by(Category.name)]
    form.supplier_id.choices = [(0, "-")] + [(s.id, s.name) for s in Supplier.query.order_by(Supplier.name)]
    if form.validate_on_submit():
        p = Product(
            sku=form.sku.data or None,
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            cost=form.cost.data,
            quantity_in_stock=form.quantity_in_stock.data or 0,
            category_id=form.category_id.data or None,
            supplier_id=form.supplier_id.data or None
        )
        db.session.add(p)
        db.session.commit()
        flash("Product created", "success")
        return redirect(url_for("products.list_products"))
    return render_template("product_form.html", form=form)

@products_bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    p = Product.query.get_or_404(product_id)
    form = ProductForm(obj=p)
    form.category_id.choices = [(0, "-")] + [(c.id, c.name) for c in Category.query.order_by(Category.name)]
    form.supplier_id.choices = [(0, "-")] + [(s.id, s.name) for s in Supplier.query.order_by(Supplier.name)]
    if form.validate_on_submit():
        p.sku = form.sku.data or None
        p.name = form.name.data
        p.description = form.description.data
        p.price = form.price.data
        p.cost = form.cost.data
        p.quantity_in_stock = form.quantity_in_stock.data or 0
        p.category_id = form.category_id.data or None
        p.supplier_id = form.supplier_id.data or None
        db.session.commit()
        flash("Product updated", "success")
        return redirect(url_for("products.list_products"))
    if p.category_id is None:
        form.category_id.data = 0
    if p.supplier_id is None:
        form.supplier_id.data = 0
    return render_template("product_form.html", form=form, product=p)
""",
    "app/routes/sales.py": """from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from .. import db
from ..models import Sale, SaleItem, Product, Customer
from decimal import Decimal
from datetime import datetime

sales_bp = Blueprint("sales", __name__, template_folder="templates")

@sales_bp.route("/")
@login_required
def list_sales():
    sales = Sale.query.order_by(Sale.created_at.desc()).limit(50).all()
    return render_template("sales.html", sales=sales)

@sales_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_sale_form():
    products = Product.query.filter(Product.quantity_in_stock > 0).order_by(Product.name).all()
    if request.method == "POST":
        items = []
        for p in products:
            qty = int(request.form.get(f"qty_{p.id}", 0) or 0)
            if qty > 0:
                items.append({"product_id": p.id, "quantity": qty})
        customer_name = request.form.get("customer_name")
        customer_email = request.form.get("customer_email")
        payload = {"items": items}
        if customer_name:
            payload["customer"] = {"name": customer_name, "email": customer_email}
        result = _create_sale(payload, current_user.id)
        if result.get("error"):
            flash(result["error"], "danger")
            return redirect(url_for("sales.create_sale_form"))
        flash(f"Sale recorded (id={result['sale_id']}) total {result['total']}", "success")
        return redirect(url_for("sales.list_sales"))
    return render_template("sale_form.html", products=products)

def _create_sale(data, user_id=None):
    if not data or "items" not in data or len(data["items"]) == 0:
        return {"error": "No items provided"}
    try:
        customer = None
        if data.get("customer"):
            cust = data["customer"]
            customer = Customer(name=cust.get("name"), email=cust.get("email"))
            db.session.add(customer)
            db.session.flush()

        sale = Sale(user_id=user_id, customer=customer)
        db.session.add(sale)
        total = Decimal("0.00")
        for it in data["items"]:
            pid = int(it["product_id"])
            qty = int(it["quantity"])
            product = Product.query.get(pid)
            if not product:
                db.session.rollback()
                return {"error": f"Product {pid} not found"}
            if (product.quantity_in_stock or 0) < qty:
                db.session.rollback()
                return {"error": f"Not enough stock for {product.name}"}
            unit_price = product.price
            subtotal = (Decimal(unit_price) * qty).quantize(Decimal("0.01"))
            sale_item = SaleItem(sale=sale, product=product, quantity=qty, unit_price=unit_price, subtotal=subtotal)
            db.session.add(sale_item)
            product.adjust_stock(-qty, note=f"Sale #{sale.id or 'pending'}")
            total += subtotal
        sale.total_amount = total
        sale.receipt_number = f"R-{int(datetime.utcnow().timestamp())}-{user_id or 0}"
        db.session.commit()
        return {"sale_id": sale.id, "total": str(sale.total_amount)}
    except Exception as e:
        db.session.rollback()
        return {"error": str(e)}

@sales_bp.route("/api", methods=["POST"])
def create_sale_api():
    data = request.get_json()
    result = _create_sale(data)
    if result.get("error"):
        return jsonify({"error": result["error"]}), 400
    return jsonify(result), 201
""",
    "app/routes/reports.py": """from flask import Blueprint, render_template
from flask_login import login_required
from ..models import Sale
from sqlalchemy import func
from datetime import datetime, timedelta

reports_bp = Blueprint("reports", __name__, template_folder="templates")

@reports_bp.route("/daily")
@login_required
def daily_report():
    today = datetime.utcnow().date()
    tomorrow = today + timedelta(days=1)
    total = Sale.query.with_entities(func.coalesce(func.sum(Sale.total_amount), 0)).filter(Sale.created_at >= today, Sale.created_at < tomorrow).scalar()
    sales = Sale.query.filter(Sale.created_at >= today, Sale.created_at < tomorrow).all()
    return render_template("report_daily.html", date=today, total=total, sales=sales)
""",
    "app/templates/base.html": """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{% block title %}Inventory System{% endblock %}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css">
</head>
<body>
<section class="section">
  <div class="container">
    <nav class="navbar">
      <div class="navbar-brand">
        <a class="navbar-item" href="{{ url_for('main.dashboard') }}">Inventory</a>
      </div>
      <div class="navbar-menu">
        <div class="navbar-start">
          <a class="navbar-item" href="{{ url_for('products.list_products') }}">Products</a>
          <a class="navbar-item" href="{{ url_for('sales.list_sales') }}">Sales</a>
          <a class="navbar-item" href="{{ url_for('reports.daily_report') }}">Reports</a>
        </div>
        <div class="navbar-end">
          {% if current_user.is_authenticated %}
            <div class="navbar-item">Hi {{ current_user.username }}</div>
            <a class="navbar-item" href="{{ url_for('auth.logout') }}">Logout</a>
          {% else %}
            <a class="navbar-item" href="{{ url_for('auth.login') }}">Login</a>
          {% endif %}
        </div>
      </div>
    </nav>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, msg in messages %}
          <div class="notification is-{{ 'info' if category == 'info' else category }}">{{ msg }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    {% block content %}{% endblock %}

  </div>
</section>
</body>
</html>
""",
    "app/templates/login.html": """{% extends "base.html" %}
{% block title %}Login{% endblock %}
{% block content %}
  <h1 class="title">Login</h1>
  <form method="post">
    {{ form.hidden_tag() }}
    <div class="field"><label class="label">Username</label><div class="control">{{ form.username(class="input") }}</div></div>
    <div class="field"><label class="label">Password</label><div class="control">{{ form.password(class="input") }}</div></div>
    <div class="field"><div class="control">{{ form.submit(class="button is-primary") }}</div></div>
  </form>
  <p>Don't have an account? <a href="{{ url_for('auth.register') }}">Register</a></p>
{% endblock %}
""",
    "app/templates/register.html": """{% extends "base.html" %}
{% block title %}Register{% endblock %}
{% block content %}
  <h1 class="title">Register</h1>
  <form method="post">
    {{ form.hidden_tag() }}
    <div class="field"><label class="label">Username</label><div class="control">{{ form.username(class="input") }}</div></div>
    <div class="field"><label class="label">Password</label><div class="control">{{ form.password(class="input") }}</div></div>
    <div class="field"><div class="control">{{ form.submit(class="button is-primary") }}</div></div>
  </form>
{% endblock %}
""",
    "app/templates/dashboard.html": """{% extends "base.html" %}
{% block title %}Dashboard{% endblock %}
{% block content %}
  <h1 class="title">Dashboard</h1>
  <div class="box">
    <p>Total products: {{ total_products }}</p>
  </div>

  <h2 class="subtitle">Recent Sales</h2>
  <table class="table is-fullwidth">
    <thead><tr><th>Receipt</th><th>Date</th><th>Total</th></tr></thead>
    <tbody>
      {% for s in recent_sales %}
        <tr><td>{{ s.receipt_number }}</td><td>{{ s.created_at }}</td><td>{{ s.total_amount }}</td></tr>
      {% endfor %}
    </tbody>
  </table>
{% endblock %}
""",
    "app/templates/products.html": """{% extends "base.html" %}
{% block title %}Products{% endblock %}
{% block content %}
  <h1 class="title">Products</h1>
  <a class="button is-primary" href="{{ url_for('products.create_product') }}">New product</a>
  <table class="table is-fullwidth">
    <thead><tr><th>SKU</th><th>Name</th><th>Price</th><th>Qty</th><th></th></tr></thead>
    <tbody>
      {% for p in products %}
      <tr>
        <td>{{ p.sku }}</td>
        <td>{{ p.name }}</td>
        <td>{{ p.price }}</td>
        <td>{{ p.quantity_in_stock }}</td>
        <td><a href="{{ url_for('products.edit_product', product_id=p.id) }}">Edit</a></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
{% endblock %}
""",
    "app/templates/product_form.html": """{% extends "base.html" %}
{% block title %}Product Form{% endblock %}
{% block content %}
  <h1 class="title">{{ 'Edit' if product else 'New' }} Product</h1>
  <form method="post">
    {{ form.hidden_tag() }}
    <div class="field"><label class="label">SKU</label><div class="control">{{ form.sku(class="input") }}</div></div>
    <div class="field"><label class="label">Name</label><div class="control">{{ form.name(class="input") }}</div></div>
    <div class="field"><label class="label">Price</label><div class="control">{{ form.price(class="input") }}</div></div>
    <div class="field"><label class="label">Cost</label><div class="control">{{ form.cost(class="input") }}</div></div>
    <div class="field"><label class="label">Quantity</label><div class="control">{{ form.quantity_in_stock(class="input") }}</div></div>
    <div class="field"><label class="label">Category</label><div class="control">{{ form.category_id(class="select") }}</div></div>
    <div class="field"><label class="label">Supplier</label><div class="control">{{ form.supplier_id(class="select") }}</div></div>
    <div class="field"><div class="control">{{ form.submit(class="button is-primary") }}</div></div>
  </form>
{% endblock %}
""",
    "app/templates/sales.html": """{% extends "base.html" %}
{% block title %}Sales{% endblock %}
{% block content %}
  <h1 class="title">Sales</h1>
  <a class="button is-primary" href="{{ url_for('sales.create_sale_form') }}">New Sale</a>
  <table class="table is-fullwidth">
    <thead><tr><th>Receipt</th><th>Date</th><th>Customer</th><th>Total</th></tr></thead>
    <tbody>
      {% for s in sales %}
      <tr>
        <td>{{ s.receipt_number }}</td>
        <td>{{ s.created_at }}</td>
        <td>{{ s.customer.name if s.customer else '' }}</td>
        <td>{{ s.total_amount }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
{% endblock %}
""",
    "app/templates/sale_form.html": """{% extends "base.html" %}
{% block title %}Create Sale{% endblock %}
{% block content %}
  <h1 class="title">Create Sale</h1>
  <form method="post">
    <h2 class="subtitle">Customer (optional)</h2>
    <div class="field"><label class="label">Name</label><div class="control"><input class="input" name="customer_name"></div></div>
    <div class="field"><label class="label">Email</label><div class="control"><input class="input" name="customer_email"></div></div>

    <h2 class="subtitle">Items</h2>
    <table class="table">
      <thead><tr><th>Product</th><th>Price</th><th>Available</th><th>Quantity</th></tr></thead>
      <tbody>
        {% for p in products %}
        <tr>
          <td>{{ p.name }}</td>
          <td>{{ p.price }}</td>
          <td>{{ p.quantity_in_stock }}</td>
          <td><input class="input" name="qty_{{ p.id }}" type="number" min="0" value="0" style="width:80px"></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>

    <div class="field"><div class="control"><button class="button is-primary" type="submit">Record Sale</button></div></div>
  </form>
{% endblock %}
""",
    "app/templates/report_daily.html": """{% extends "base.html" %}
{% block title %}Daily Report{% endblock %}
{% block content %}
  <h1 class="title">Daily Report - {{ date }}</h1>
  <div class="box">Total sales: {{ total }}</div>

  <table class="table is-fullwidth">
    <thead><tr><th>Receipt</th><th>Date</th><th>Customer</th><th>Total</th></tr></thead>
    <tbody>
      {% for s in sales %}
      <tr><td>{{ s.receipt_number }}</td><td>{{ s.created_at }}</td><td>{{ s.customer.name if s.customer else '' }}</td><td>{{ s.total_amount }}</td></tr>
      {% endfor %}
    </tbody>
  </table>
{% endblock %}
""",
    "app/utils.py": """from functools import wraps
from flask import abort
from flask_login import current_user

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not (current_user.is_authenticated and current_user.is_admin):
            abort(403)
        return f(*args, **kwargs)
    return decorated
"""
}

def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Created: {path}")

def main():
    print(f"Creating project at: {TARGET_DIR}")
    for rel_path, content in files.items():
        target_path = TARGET_DIR / rel_path
        write_file(target_path, content)
    # create instance folder
    instance_dir = TARGET_DIR / "instance"
    instance_dir.mkdir(parents=True, exist_ok=True)
    print("Created instance directory.")
    print("\nDone. Next steps:")
    print(f"  1) Open a terminal and cd to: '{TARGET_DIR}'")
    print("  2) Create & activate a virtualenv, then install requirements:")
    print("       python -m venv venv")
    print("       source venv/bin/activate   # or venv\\Scripts\\activate on Windows")
    print("       pip install -r requirements.txt")
    print("  3) Initialize DB & migrations:")
    print("       export FLASK_APP=run.py    # on Windows: set FLASK_APP=run.py")
    print("       flask db init")
    print("       flask db migrate -m \"Initial migrate\"")
    print("       flask db upgrade")
    print("  4) Create an admin user (see README.md) and then run:")
    print("       python run.py")
    print("  5) Visit http://127.0.0.1:5000/")

if __name__ == "__main__":
    main()