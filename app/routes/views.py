from flask import Blueprint, redirect, render_template, session, url_for

views_bp = Blueprint("views", __name__)


@views_bp.get("/")
def reception_page():
    return render_template("reception.html")


@views_bp.get("/admin/login")
def admin_login_page():
    if session.get("admin"):
        return redirect(url_for("views.admin_page"))
    return render_template("admin_login.html")


@views_bp.get("/admin")
def admin_page():
    if not session.get("admin"):
        return redirect(url_for("views.admin_login_page"))
    return render_template("admin.html")


@views_bp.get("/history")
def history_page():
    return render_template("history.html")


@views_bp.get("/reports")
def reports_page():
    return render_template("reports.html")
