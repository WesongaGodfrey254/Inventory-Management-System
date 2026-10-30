from decimal import Decimal

from flask import Blueprint, current_app, jsonify, render_template
from flask_login import login_required, current_user
from sqlalchemy import func, text
from sqlalchemy.orm import joinedload

from ..models import Product, Sale, SaleItem
from .. import db

main_bp = Blueprint("main", __name__, template_folder="templates")


@main_bp.route("/healthz")
def healthz():
    """Public liveness probe that also checks the database connection."""
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        current_app.logger.exception("Database health check failed")
        return jsonify(status="error", database="unavailable"), 503
    return jsonify(status="ok", database="ok"), 200


def _dashboard_stats(user_id):
    total_products = Product.query.filter_by(user_id=user_id).count()
    total_sales = Sale.query.filter_by(user_id=user_id).count()
    revenue = db.session.query(
        func.coalesce(func.sum(Sale.total_amount), 0)
    ).filter(Sale.user_id == user_id).scalar()
    total_revenue = Decimal(str(revenue or 0)).quantize(Decimal("0.01"))
    return {
        "total_products": total_products,
        "total_sales": total_sales,
        "total_revenue": f"{total_revenue:.2f}",
    }


@main_bp.route("/")
@login_required
def dashboard():
    stats = _dashboard_stats(current_user.id)
    recent_sales = (
        Sale.query
        .filter_by(user_id=current_user.id)
        .options(joinedload(Sale.items).joinedload(SaleItem.product))
        .order_by(Sale.created_at.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "dashboard/dashboard.html",
        recent_sales=recent_sales,
        **stats,
    )


@main_bp.route("/dashboard/stats")
@login_required
def dashboard_stats():
    return jsonify(_dashboard_stats(current_user.id))
