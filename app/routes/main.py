from flask import Blueprint, redirect, url_for
from app.models.db import get_db_connection

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    # Always redirect to login page
    return redirect(url_for("auth.login"))


@main_bp.route("/db-test")
def db_test():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1;")
    result = cur.fetchone()
    cur.close()
    conn.close()
    return {"db_status": "connected", "result": result}
