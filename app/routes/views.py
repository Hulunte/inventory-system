from flask import Blueprint, render_template

views_bp = Blueprint("views", __name__)


@views_bp.get("/")
def reception_page():
    return render_template("reception.html")
