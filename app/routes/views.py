from datetime import datetime as dt

from flask import Blueprint, current_app, redirect, render_template, session, url_for

from app.services.report_service import get_week_ranges

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
    tz = current_app.config["HARVEST_TIMEZONE"]
    today = dt.now(tz).date()
    (monday_current, sunday_current), (monday_previous, sunday_previous) = get_week_ranges(today)

    return render_template(
        "reports.html",
        is_admin=bool(session.get("admin")),
        current_week_start=monday_current.isoformat(),
        current_week_end=sunday_current.isoformat(),
        previous_week_start=monday_previous.isoformat(),
        previous_week_end=sunday_previous.isoformat(),
    )
