from app.models.db import get_db_connection
from flask import (
    Blueprint,
    render_template,
    session,
    redirect,
    url_for,
    flash,
    request,
    jsonify,  # ✅ REQUIRED
)

import json
import os
import qrcode
from psycopg2.extras import RealDictCursor

user_bp = Blueprint("user", __name__, url_prefix="/user")


@user_bp.route("/dashboard")
def dashboard():
    if session.get("role") != "user":
        return redirect(url_for("auth.login"))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT user_full_name
        FROM users
        WHERE login_id = %s
    """,
        (session["login_id"],),
    )

    user = cur.fetchone()

    cur.close()
    conn.close()

    return render_template("user/dashboard.html", user=user)


# ---------------- USER PROFILE ----------------
# ---------------- USER PROFILE (VIEW + UPDATE) ----------------
@user_bp.route("/profile", methods=["GET", "POST"])
def profile():
    if "login_id" not in session or session.get("role") != "user":
        return redirect(url_for("auth.login"))

    login_id = session["login_id"]
    conn = get_db_connection()
    cur = conn.cursor()

    # UPDATE PROFILE
    if request.method == "POST":
        full_name = request.form.get("user_full_name")
        phone = request.form.get("user_phone")
        address = request.form.get("user_address")

        if not full_name:
            flash("Full name is required", "danger")
            return redirect(url_for("user.profile"))

        cur.execute(
            """
            UPDATE users
            SET user_full_name = %s,
                user_phone = %s,
                user_address = %s
            WHERE login_id = %s
            """,
            (full_name, phone, address, login_id),
        )

        conn.commit()
        flash("Profile updated successfully", "success")
        return redirect(url_for("user.profile"))

    # FETCH PROFILE
    cur.execute(
        """
        SELECT user_full_name, user_phone, user_address
        FROM users
        WHERE login_id = %s
        """,
        (login_id,),
    )
    user = cur.fetchone()

    cur.close()
    conn.close()

    return render_template("user/profile.html", user=user)


@user_bp.route("/hotels")
def hotel_list():
    if session.get("role") != "user":
        return redirect(url_for("auth.login"))

    search = request.args.get("search", "").strip()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    query = """
        SELECT id, hotel_name, location, phone, profile_image
        FROM hotels
        WHERE status='approved'
          AND is_active=TRUE
          AND is_open=TRUE
    """
    params = []

    if search:
        query += """
            AND (
                LOWER(hotel_name) LIKE %s
                OR LOWER(location) LIKE %s
            )
        """
        params = [f"%{search.lower()}%", f"%{search.lower()}%"]

    query += " ORDER BY hotel_name"

    cur.execute(query, params)
    hotels = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("user/hotels.html", hotels=hotels, search=search)


@user_bp.route("/menu/<int:hotel_id>")
def menu(hotel_id):
    # 🔒 Hard fail if not logged in as user
    if "user_id" not in session or session.get("role") != "user":
        return redirect(url_for("auth.login"))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ✅ Fetch hotel
    cur.execute(
        """
        SELECT id, hotel_name, location
        FROM hotels
        WHERE id=%s
          AND status='approved'
          AND is_active=TRUE
          AND is_open=TRUE
    """,
        (hotel_id,),
    )
    hotel = cur.fetchone()

    if not hotel:
        cur.close()
        conn.close()
        return redirect(url_for("user.hotel_list"))

    # ✅ Fetch menus
    cur.execute(
        """
        SELECT id, item_name, category, price,
               available_quantity, image
        FROM menus
        WHERE hotel_id=%s
          AND is_available=TRUE
        ORDER BY category, item_name
    """,
        (hotel_id,),
    )
    menus = cur.fetchall()

    # ✅ Fetch premium status
    cur.execute("SELECT is_premium FROM users WHERE id=%s", (session["user_id"],))
    user_row = cur.fetchone()
    is_premium = user_row["is_premium"] if user_row else False

    cur.close()
    conn.close()

    return render_template(
        "user/menu.html", hotel=hotel, menus=menus, is_premium=is_premium
    )


# --------------------------------------------------
# PLACE ORDER (COD + ONLINE)
# --------------------------------------------------
@user_bp.route("/place-order", methods=["POST"])
def place_order():
    if session.get("role") != "user" or "user_id" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400

    payment_mode = data.get("payment_mode")
    if payment_mode not in ("cod", "online"):
        return jsonify({"success": False, "error": "Invalid payment mode"}), 400

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        final_items = []

        for item in data["items"]:
            cur.execute(
                "SELECT item_name, price, available_quantity FROM menus WHERE id=%s",
                (item["menu_id"],),
            )
            menu = cur.fetchone()

            if not menu or menu["available_quantity"] < item["qty"]:
                raise Exception("Item unavailable")

            final_items.append(
                {
                    "menu_id": item["menu_id"],
                    "name": menu["item_name"],
                    "qty": item["qty"],
                    "price": float(menu["price"]),
                }
            )

        order_status = "preparing" if payment_mode == "cod" else "paid"

        cur.execute(
            """
            INSERT INTO orders
            (user_id, hotel_id, total_people, total_amount,
             scheduled_time, items, payment_mode, order_status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (
                session["user_id"],
                data["hotel_id"],
                data["total_people"],
                data["total_amount"],
                data["scheduled_time"],
                json.dumps(final_items),
                payment_mode,
                order_status,
            ),
        )

        order_id = cur.fetchone()["id"]
        conn.commit()

    except Exception as e:
        conn.rollback()
        print("ORDER ERROR:", e)
        return jsonify({"success": False, "error": "Server error"}), 500
    finally:
        cur.close()
        conn.close()

    # COD → confirm immediately
    if payment_mode == "cod":
        process_confirmed_order(order_id)
        return jsonify(
            {
                "success": True,
                "success_url": url_for("user.order_success", order_id=order_id),
            }
        )

    # ONLINE → go to payment page
    return jsonify(
        {
            "success": True,
            "payment_url": url_for("user.online_payment", order_id=order_id),
        }
    )


# --------------------------------------------------
# ONLINE PAYMENT PAGE (SIMULATED)
# --------------------------------------------------
@user_bp.route("/online-payment/<int:order_id>")
def online_payment(order_id):
    if session.get("role") != "user":
        return redirect(url_for("auth.login"))

    return render_template("user/online_payment.html", order_id=order_id)


# --------------------------------------------------
# PAYMENT SUCCESS (ONLINE CONFIRMATION)
# --------------------------------------------------
@user_bp.route("/payment-success/<int:order_id>")
def payment_success(order_id):
    if session.get("role") != "user":
        return redirect(url_for("auth.login"))

    process_confirmed_order(order_id)

    return redirect(url_for("user.order_success", order_id=order_id))


# --------------------------------------------------
# CONFIRMED ORDER PROCESS (COD + ONLINE)
# --------------------------------------------------
def process_confirmed_order(order_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("SELECT items FROM orders WHERE id=%s", (order_id,))
        items = cur.fetchone()["items"]

        for item in items:
            cur.execute(
                "UPDATE menus SET available_quantity = available_quantity - %s WHERE id=%s",
                (item["qty"], item["menu_id"]),
            )

        generate_and_save_qr(order_id, cur)
        conn.commit()

    except Exception as e:
        conn.rollback()
        print("CONFIRM ERROR:", e)
        raise
    finally:
        cur.close()
        conn.close()


# --------------------------------------------------
# QR GENERATION
# --------------------------------------------------
def generate_and_save_qr(order_id, cur):
    qr_value = f"ORDER_ID:{order_id}"

    qr_dir = os.path.join("app", "static", "uploads", "qrcodes")
    os.makedirs(qr_dir, exist_ok=True)

    filename = f"order_{order_id}.png"
    path = os.path.join(qr_dir, filename)

    qrcode.make(qr_value).save(path)

    cur.execute(
        """
        UPDATE orders
        SET qr_code=%s,
            qr_image_url=%s
        WHERE id=%s
        """,
        (qr_value, f"/static/uploads/qrcodes/{filename}", order_id),
    )


# --------------------------------------------------
# COMMON SUCCESS PAGE (COD + ONLINE)
# --------------------------------------------------
@user_bp.route("/order-success/<int:order_id>")
def order_success(order_id):
    if session.get("role") != "user":
        return redirect(url_for("auth.login"))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        "SELECT qr_image_url FROM orders WHERE id=%s",
        (order_id,),
    )
    order = cur.fetchone()

    cur.close()
    conn.close()

    if not order or not order["qr_image_url"]:
        return "QR not available", 404

    return render_template(
        "user/order_success.html",
        order_id=order_id,
        qr_url=order["qr_image_url"],
    )


# ---------------- USER MY ORDERS (VIEW) ----------------
@user_bp.route("/my_orders")
def my_orders():
    if "login_id" not in session or session.get("role") != "user":
        return redirect(url_for("auth.login"))

    login_id = session["login_id"]

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Fetch user
    cur.execute(
        """
        SELECT id, user_full_name
        FROM users
        WHERE login_id = %s
        """,
        (login_id,),
    )
    user = cur.fetchone()

    # Fetch orders (active + completed without feedback)
    cur.execute(
        """
        SELECT 
            o.id,
            o.hotel_id,
            o.order_status,
            o.payment_mode,
            o.scheduled_time,
            o.qr_image_url,
            o.feedback_given,
            h.hotel_name
        FROM orders o
        JOIN hotels h ON h.id = o.hotel_id
        WHERE o.user_id = %s
          AND (
                o.order_status != 'completed'
                OR (o.order_status = 'completed' AND o.feedback_given = false)
              )
        ORDER BY o.created_at DESC
        """,
        (user["id"],),
    )

    orders = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("user/my_orders.html", user=user, orders=orders)


# ---------------- SUBMIT FEEDBACK ----------------
# ---------------- SUBMIT FEEDBACK ----------------
@user_bp.route("/submit-feedback/<int:order_id>", methods=["POST"])
def submit_feedback(order_id):
    if "login_id" not in session or session.get("role") != "user":
        return redirect(url_for("auth.login"))

    rating = request.form.get("rating")
    feedback_text = request.form.get("feedback_text")

    if not rating:
        flash("Rating is required", "danger")
        return redirect(url_for("user.my_orders"))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 🔹 Fetch order details safely
    cur.execute(
        """
        SELECT user_id, hotel_id
        FROM orders
        WHERE id = %s
        """,
        (order_id,),
    )
    order = cur.fetchone()

    if not order:
        cur.close()
        conn.close()
        flash("Invalid order", "danger")
        return redirect(url_for("user.my_orders"))

    # 🔹 Insert feedback (FIXED)
    cur.execute(
        """
        INSERT INTO feedbacks (user_id, hotel_id, rating, feedback_text)
        VALUES (%s, %s, %s, %s)
        """,
        (
            order["user_id"],  # ✅ FIX
            order["hotel_id"],  # ✅ FIX
            rating,
            feedback_text,
        ),
    )

    # 🔹 Mark feedback as given
    cur.execute(
        """
        UPDATE orders
        SET feedback_given = true
        WHERE id = %s
        """,
        (order_id,),
    )

    conn.commit()
    cur.close()
    conn.close()

    flash("Thank you for your feedback!", "success")
    return redirect(url_for("user.my_orders"))
