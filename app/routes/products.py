from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ..models import Product, Category, Supplier
from .. import db
from ..forms import ProductForm

products_bp = Blueprint("products", __name__, template_folder="templates")

@products_bp.route("/")
@login_required
def list_products():
    products = Product.query.filter_by(user_id=current_user.id).order_by(Product.name).all()
    return render_template("products/products.html", products=products)

@products_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_product():
    form = ProductForm()
    # populate category and supplier choices
    form.category_id.choices = [(0, "-")] + [(c.id, c.name) for c in Category.query.order_by(Category.name)]
    form.supplier_id.choices = [(0, "-")] + [(s.id, s.name) for s in Supplier.query.order_by(Supplier.name)]
    if form.validate_on_submit():
        p = Product(
            user_id=current_user.id,
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
    return render_template("products/product_form.html", form=form)

@products_bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    p = Product.query.filter_by(id=product_id, user_id=current_user.id).first_or_404()
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
    # set zero to None selection if needed
    if p.category_id is None:
        form.category_id.data = 0
    if p.supplier_id is None:
        form.supplier_id.data = 0
    return render_template("products/product_form.html", form=form, product=p)