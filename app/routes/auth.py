from flask import Blueprint, render_template, redirect, url_for, flash, request
from .. import db, login_manager
from ..models import User
from ..forms import LoginForm, RegisterForm, ShopSettingsForm
from flask_login import login_user, logout_user, login_required, current_user

auth_bp = Blueprint("auth", __name__, template_folder="templates")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash("Username already taken", "warning")
            return redirect(url_for("auth.register"))
        u = User(
            username=form.username.data.strip(),
            shop_name=form.shop_name.data.strip(),
        )
        u.set_password(form.password.data)
        db.session.add(u)
        db.session.commit()
        flash("Account created. Please login.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)

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
    return render_template("auth/login.html", form=form)

@auth_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """Let the shop owner set the name used on receipts and notifications."""
    form = ShopSettingsForm(obj=current_user)
    if form.validate_on_submit():
        current_user.shop_name = form.shop_name.data.strip()
        db.session.commit()
        flash("Shop name updated. Receipts will use it from now on.", "success")
        return redirect(url_for("auth.settings"))
    return render_template("auth/settings.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out", "info")
    return redirect(url_for("auth.login"))

# user loader
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))