from flask import Blueprint, render_template
from flask_login import login_required, current_user
from ..models import Sale, SaleItem
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta

reports_bp = Blueprint("reports", __name__, template_folder="templates")

@reports_bp.route("/daily")
@login_required
def daily_report():
    today = datetime.utcnow().date()
    tomorrow = today + timedelta(days=1)
    total = Sale.query.with_entities(func.coalesce(func.sum(Sale.total_amount), 0)).filter(
        Sale.user_id == current_user.id,
        Sale.created_at >= today,
        Sale.created_at < tomorrow,
    ).scalar()
    sales = (
        Sale.query
        .filter(
            Sale.user_id == current_user.id,
            Sale.created_at >= today,
            Sale.created_at < tomorrow,
        )
        .options(joinedload(Sale.items).joinedload(SaleItem.product))
        .all()
    )
    return render_template("reports/report_daily.html", date=today, total=total, sales=sales)