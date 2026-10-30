from . import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal

# Roles are simple strings on user for this starter (is_admin boolean)
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    shop_name = db.Column(db.String(200), nullable=True)
    # Werkzeug's scrypt hashes are longer than 128 characters, and PostgreSQL
    # enforces VARCHAR lengths (unlike SQLite), so leave room for them.
    password_hash = db.Column(db.String(255))
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
    __table_args__ = (
        db.UniqueConstraint("user_id", "sku", name="uq_products_user_sku"),
    )
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(64), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10,2), nullable=False)
    cost = db.Column(db.Numeric(10,2), nullable=True)
    quantity_in_stock = db.Column(db.Integer, default=0)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=True)

    user = db.relationship("User")
    category = db.relationship("Category", back_populates="products")
    supplier = db.relationship("Supplier", back_populates="products")

    def adjust_stock(self, delta, note=""):
        self.quantity_in_stock = (self.quantity_in_stock or 0) + delta
        # record stock movement
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
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    user = db.relationship("User")
    sales = db.relationship("Sale", back_populates="customer")

class Sale(db.Model):
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # who created the sale
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
    change = db.Column(db.Integer, nullable=False)  # positive in, negative out
    note = db.Column(db.String(255))

    product = db.relationship("Product")