from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.models.db import get_db_connection

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ----------------- AUTH GUARD -----------------
def admin_required():
    if "login_id" not in session or session.get("role") != "admin":
        return False
    return True


# ----------------- DASHBOARD -----------------
@admin_bp.route("/dashboard")
def dashboard():
    if not admin_required():
        return redirect(url_for("auth.login"))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS total FROM hotels")
    total_hotels = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS total FROM users")
    total_users = cur.fetchone()["total"]

    cur.execute("SELECT COUNT(*) AS total FROM hotels WHERE status='pending'")
    pending_hotels = cur.fetchone()["total"]

    cur.close()
    conn.close()

    return render_template(
        "admin/dashboard.html",
        total_hotels=total_hotels,
        total_users=total_users,
        pending_hotels=pending_hotels,
    )


# ----------------- HOTEL MANAGEMENT -----------------
@admin_bp.route("/hotels")
def hotels():
    if not admin_required():
        return redirect(url_for("auth.login"))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT h.*, l.email
        FROM hotels h
        JOIN logins l ON h.login_id = l.id
        ORDER BY h.created_at DESC
    """
    )
    hotels = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("admin/hotels.html", hotels=hotels)


@admin_bp.route("/hotels/action", methods=["POST"])
def hotel_action():
    if not admin_required():
        return redirect(url_for("auth.login"))

    hotel_id = request.form["hotel_id"]
    action = request.form["action"]
    remark = request.form.get("admin_remark")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE hotels
        SET status=%s, admin_remark=%s
        WHERE id=%s
    """,
        (action, remark, hotel_id),
    )

    conn.commit()
    cur.close()
    conn.close()

    flash("Hotel status updated successfully", "success")
    return redirect(url_for("admin.hotels"))


# ----------------- USERS LIST -----------------
@admin_bp.route("/users")
def users():
    if not admin_required():
        return redirect(url_for("auth.login"))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT u.*, l.email
        FROM users u
        JOIN logins l ON u.login_id = l.id
        ORDER BY u.created_at DESC
    """
    )
    users = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("admin/users.html", users=users)


# ----------------- ORDERS (PLACEHOLDER) -----------------
@admin_bp.route("/orders")
def orders():
    if not admin_required():
        return redirect(url_for("auth.login"))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            o.id,
            o.total_people,
            o.total_amount,
            o.order_status,
            o.order_time,
            u.user_full_name AS user_name,
            h.hotel_name
        FROM orders o
        JOIN users u ON o.user_id = u.id
        JOIN hotels h ON o.hotel_id = h.id
        ORDER BY o.order_time DESC
    """
    )

    orders = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("admin/orders.html", orders=orders)


# ----------------- FEEDBACK (PLACEHOLDER) -----------------
@admin_bp.route("/feedbacks", methods=["GET"])
def feedbacks():
    if not admin_required():
        return redirect(url_for("auth.login"))

    license_no = request.args.get("license_no", "").strip()

    conn = get_db_connection()
    cur = conn.cursor()

    base_query = """
        SELECT
            f.id,
            f.rating,
            f.feedback_text,
            f.created_at,
            u.user_full_name AS user_name,
            h.hotel_name,
            h.license_number,
            h.location,
            h.owner_name
        FROM feedbacks f
        JOIN users u ON f.user_id = u.id
        JOIN hotels h ON f.hotel_id = h.id
    """

    params = []

    if license_no:
        base_query += " WHERE h.license_number ILIKE %s"
        params.append(f"%{license_no}%")

    base_query += " ORDER BY f.created_at DESC"

    cur.execute(base_query, params)
    feedbacks = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "admin/feedbacks.html", feedbacks=feedbacks, license_no=license_no
    )
