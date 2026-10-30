from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from .. import db, csrf
from ..models import Sale, SaleItem, Product, Customer
from ..utils import send_sale_notification_detailed
from decimal import Decimal
from datetime import datetime

sales_bp = Blueprint("sales", __name__, template_folder="templates")

@sales_bp.route("/")
@login_required
def list_sales():
    sales = (
        Sale.query
        .filter_by(user_id=current_user.id)
        .options(joinedload(Sale.items).joinedload(SaleItem.product))
        .order_by(Sale.created_at.desc())
        .limit(50)
        .all()
    )
    return render_template("sales/sales.html", sales=sales)

@sales_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_sale_form():
    # simple form: POST with items[] as product_id:quantity pairs, or a JSON body via fetch
    products = Product.query.filter(
        Product.user_id == current_user.id,
        Product.quantity_in_stock > 0,
    ).order_by(Product.name).all()
    if request.method == "POST":
        # Expecting form fields like items-<product_id>=<quantity> (simple approach)
        items = []
        for p in products:
            qty = int(request.form.get(f"qty_{p.id}", 0) or 0)
            if qty > 0:
                items.append({"product_id": p.id, "quantity": qty})
        customer_name = (request.form.get("customer_name") or "").strip()
        customer_email = (request.form.get("customer_email") or "").strip()
        payload = {"items": items}
        if customer_name or customer_email:
            payload["customer"] = {
                "name": customer_name or "Customer",
                "email": customer_email or None,
            }
        # delegate to internal function
        result = _create_sale(payload, current_user.id)
        if result.get("error"):
            flash(result["error"], "danger")
            return redirect(url_for("sales.create_sale_form"))
        flash(f"Sale recorded (id={result['sale_id']}) total {result['total']}", "success")
        if result.get("email_sent"):
            flash("A receipt has been emailed to the customer.", "info")
        elif customer_email:
            flash(
                "Sale recorded, but the receipt email could not be sent. "
                + (result.get("email_error") or "Check the server log for details."),
                "warning",
            )
        return redirect(url_for("sales.list_sales"))
    return render_template("sales/sale_form.html", products=products)

@sales_bp.route("/<int:sale_id>/resend-receipt", methods=["POST"])
@login_required
def resend_receipt(sale_id):
    """Resend a receipt for a past sale (e.g. after fixing SMTP settings)."""
    sale = Sale.query.filter_by(id=sale_id, user_id=current_user.id).first_or_404()
    customer = sale.customer
    if customer is None or not customer.email:
        flash("This sale has no customer email address on record.", "warning")
    else:
        sent, reason = send_sale_notification_detailed(sale)
        if sent:
            flash(f"Receipt resent to {customer.email}.", "success")
        else:
            flash(
                "Could not send the receipt. "
                + (reason or "Check the server log for details."),
                "danger",
            )
    return redirect(url_for("sales.list_sales"))

def _create_sale(data, user_id=None):
    if not user_id:
        return {"error": "You must be logged in to record a sale"}
    if not data or "items" not in data or len(data["items"]) == 0:
        return {"error": "No items provided"}
    try:
        # create customer if provided
        customer = None
        if data.get("customer"):
            cust = data["customer"]
            customer_email = (cust.get("email") or "").strip() or None
            customer = Customer(
                name=(cust.get("name") or "").strip() or "Customer",
                email=customer_email,
                user_id=user_id,
            )
            db.session.add(customer)
            db.session.flush()  # get id

        sale = Sale(user_id=user_id, customer=customer)
        db.session.add(sale)
        total = Decimal("0.00")
        # use pessimistic approach: check stock and create items
        for it in data["items"]:
            pid = int(it["product_id"])
            qty = int(it["quantity"])
            product = Product.query.filter_by(id=pid, user_id=user_id).first()
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
            # adjust stock and record movement
            product.adjust_stock(-qty, note=f"Sale #{sale.id or 'pending'}")
            total += subtotal
        sale.total_amount = total
        # generate a unique receipt number
        sale.receipt_number = f"R-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}-{user_id or 0}"
        db.session.commit()
        email_sent, email_error = send_sale_notification_detailed(sale)
        return {
            "sale_id": sale.id,
            "total": str(sale.total_amount),
            "email_sent": email_sent,
            "email_error": email_error,
        }
    except Exception as e:
        db.session.rollback()
        return {"error": str(e)}

# JSON API endpoint for external POS or JS UI.
# CSRF is exempt because clients send application/json and must still be
# authenticated; regular browser forms keep full CSRF protection.
@sales_bp.route("/api", methods=["POST"])
@csrf.exempt
@login_required
def create_sale_api():
    data = request.get_json() or {}
    result = _create_sale(data, current_user.id)
    if result.get("error"):
        return jsonify({"error": result["error"]}), 400
    return jsonify(result), 201