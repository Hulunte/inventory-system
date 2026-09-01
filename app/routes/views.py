from flask import Blueprint, render_template

views_bp = Blueprint("views", __name__)


@views_bp.get("/")
def reception_page():
    return render_template("reception.html")


@views_bp.get("/admin")
def admin_page():
    return render_template("admin.html")


@views_bp.get("/history")
def history_page():
    return render_template("history.html")


@views_bp.get("/reports")
def reports_page():
    return render_template("reports.html")
