# Standard library
from flask import Blueprint, render_template, request, redirect, session, flash, url_for
from werkzeug.utils import secure_filename
import os
import json
from app.models.db import get_db_connection
from psycopg2.extras import RealDictCursor

hotel_bp = Blueprint("hotel", __name__, url_prefix="/hotel")


def hotel_required():
    return "login_id" in session and session.get("role") == "hotel"


@hotel_bp.route("/dashboard")
def dashboard():
    if "login_id" not in session or session.get("role") != "hotel":
        return redirect(url_for("auth.login"))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, hotel_name, status, is_open
        FROM hotels
        WHERE login_id=%s
        """,
        (session["login_id"],),
    )

    hotel = cur.fetchone()

    cur.close()
    conn.close()

    if not hotel:
        return redirect(url_for("auth.login"))

    return render_template("hotel/dashboard.html", hotel=hotel)


@hotel_bp.route("/toggle-status", methods=["POST"])
def toggle_status():
    if "login_id" not in session or session.get("role") != "hotel":
        return redirect(url_for("auth.login"))

    is_open = True if request.form.get("is_open") == "on" else False

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE hotels
        SET is_open=%s, updated_at=NOW()
        WHERE login_id=%s
        """,
        (is_open, session["login_id"]),
    )

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("hotel.dashboard"))


@hotel_bp.route("/feedbacks")
def feedbacks():
    if not hotel_required():
        return redirect(url_for("auth.login"))

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT id FROM hotels WHERE login_id = %s", (session["login_id"],))
        hotel_row = cur.fetchone()
        if not hotel_row:
            flash("Hotel account not found.", "danger")
            return redirect(url_for("auth.login"))

        hotel_id = hotel_row["id"] if isinstance(hotel_row, dict) else hotel_row[0]

        cur.execute(
            """
            SELECT
                f.id,
                f.rating,
                f.feedback_text,
                f.created_at,
                u.user_full_name AS user_name
            FROM feedbacks f
            JOIN users u ON f.user_id = u.id
            WHERE f.hotel_id = %s
            ORDER BY f.created_at DESC
            """,
            (hotel_id,),
        )
        rows = cur.fetchall()

        feedbacks_list = []
        for row in rows:
            feedbacks_list.append(
                {
                    "id": row["id"],
                    "user_name": (
                        row.get("user_name") if isinstance(row, dict) else row[4]
                    ),
                    "rating": row.get("rating") if isinstance(row, dict) else row[1],
                    "feedback_text": (
                        row.get("feedback_text") if isinstance(row, dict) else row[2]
                    ),
                    "created_at": (
                        row.get("created_at").strftime("%b %d, %Y %I:%M %p")
                        if isinstance(row, dict) and row.get("created_at")
                        else "N/A"
                    ),
                }
            )

        return render_template("hotel/feedbacks.html", feedbacks=feedbacks_list)

    finally:
        cur.close()
        conn.close()


# =========================================================
# ===================== MENU SECTION ======================
# =========================================================


@hotel_bp.route("/menu", methods=["GET", "POST"])
def menu():
    if not hotel_required():
        return redirect(url_for("auth.login"))

    conn = get_db_connection()
    cur = conn.cursor()

    # Get hotel_id safely
    cur.execute("SELECT id FROM hotels WHERE login_id=%s", (session["login_id"],))
    hotel = cur.fetchone()

    if not hotel:
        cur.close()
        conn.close()
        return redirect(url_for("auth.login"))

    hotel_id = hotel["id"]

    if request.method == "POST":
        item_name = request.form["item_name"]
        categories = request.form.getlist("category")
        category_str = ",".join(categories)
        price = request.form["price"]
        qty = request.form["available_quantity"]

        image = request.files.get("image")
        filename = None

        if image and image.filename:
            filename = secure_filename(image.filename)
            upload_dir = "app/static/uploads/menu"
            os.makedirs(upload_dir, exist_ok=True)
            image.save(os.path.join(upload_dir, filename))

        cur.execute(
            """
            INSERT INTO menus
            (hotel_id, item_name, category, price, available_quantity, image)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (hotel_id, item_name, category_str, price, qty, filename),
        )
        conn.commit()
        flash("Menu item added successfully")

        return redirect(url_for("hotel.menu"))

    cur.execute(
        "SELECT * FROM menus WHERE hotel_id=%s ORDER BY created_at DESC", (hotel_id,)
    )
    menus = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("hotel/menu.html", menus=menus)


@hotel_bp.route("/menu/update", methods=["POST"])
def update_menu():
    if not hotel_required():
        return redirect(url_for("auth.login"))

    menu_id = request.form["menu_id"]
    item_name = request.form["item_name"]
    categories = request.form.getlist("category")
    category_str = ",".join(categories)
    price = request.form["price"]
    qty = request.form["available_quantity"]
    is_available = request.form["is_available"] == "true"

    image = request.files.get("image")
    filename = None

    if image and image.filename:
        filename = secure_filename(image.filename)
        upload_dir = "app/static/uploads/menu"
        os.makedirs(upload_dir, exist_ok=True)
        image.save(os.path.join(upload_dir, filename))

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        if filename:
            cur.execute(
                """
                UPDATE menus
                SET item_name=%s,
                    category=%s,
                    price=%s,
                    available_quantity=%s,
                    is_available=%s,
                    image=%s
                WHERE id=%s
                """,
                (item_name, category_str, price, qty, is_available, filename, menu_id),
            )
        else:
            cur.execute(
                """
                UPDATE menus
                SET item_name=%s,
                    category=%s,
                    price=%s,
                    available_quantity=%s,
                    is_available=%s
                WHERE id=%s
                """,
                (item_name, category_str, price, qty, is_available, menu_id),
            )

        conn.commit()
        flash("Menu updated successfully", "success")

    except Exception as e:
        conn.rollback()
        print("Menu update error:", e)
        flash("Failed to update menu", "danger")

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("hotel.menu"))


@hotel_bp.route("/menu/delete", methods=["POST"])
def delete_menu():
    if not hotel_required():
        return redirect(url_for("auth.login"))

    menu_id = request.form["menu_id"]

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("DELETE FROM menus WHERE id=%s", (menu_id,))
        conn.commit()
        flash("Menu deleted successfully", "success")

    except Exception as e:
        conn.rollback()
        print("Delete menu error:", e)
        flash("Failed to delete menu", "danger")

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("hotel.menu"))


# =========================================================
# =================== END MENU SECTION ====================
# =========================================================


@hotel_bp.route("/orders", methods=["GET"])
def orders():
    if not hotel_required():
        return redirect(url_for("auth.login"))

    phone = request.args.get("phone", "").strip()

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # 1️⃣ Get hotel ID
        cur.execute("SELECT id FROM hotels WHERE login_id = %s", (session["login_id"],))
        hotel = cur.fetchone()
        if not hotel:
            return redirect(url_for("auth.login"))

        hotel_id = hotel["id"]

        # 2️⃣ Orders query (late_action INCLUDED)
        query = """
            SELECT
                o.id,
                o.total_people,
                o.total_amount,
                o.order_status,
                o.order_time,
                o.qr_code,
                o.items,
                o.payment_mode,
                
                u.id AS user_id,
                u.user_full_name,
                u.user_phone,
                u.is_premium
            FROM orders o
            JOIN users u ON o.user_id = u.id
            WHERE o.hotel_id = %s
              AND o.order_status != 'completed'
        """
        params = [hotel_id]

        if phone:
            query += " AND u.user_phone ILIKE %s"
            params.append(f"%{phone}%")

        query += " ORDER BY o.order_time DESC"

        cur.execute(query, params)
        rows = cur.fetchall()

        orders_list = []

        # 3️⃣ Prepare data for template
        for row in rows:
            raw_items = row["items"]

            # JSONB safe handling
            if isinstance(raw_items, list):
                items = raw_items
            elif isinstance(raw_items, str):
                try:
                    items = json.loads(raw_items)
                except Exception:
                    items = []
            else:
                items = []

            orders_list.append(
                {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "full_name": row["user_full_name"],
                    "phone": row["user_phone"],
                    "is_premium": row["is_premium"],
                    "payment_mode": row["payment_mode"],
                    "total_people": row["total_people"],
                    "total_amount": row["total_amount"],
                    "order_status": row["order_status"],
                    "order_time": (
                        row["order_time"].strftime("%d %b %Y %I:%M %p")
                        if row["order_time"]
                        else "N/A"
                    ),
                    "qr_code": row["qr_code"],
                    "order_items": items,
                }
            )

        return render_template(
            "hotel/orders.html", orders=orders_list, search_phone=phone
        )

    finally:
        cur.close()
        conn.close()


# -------------------------------------------------
# COMPLETE ORDER (QR VERIFICATION + TIME OVERRIDE)
# -------------------------------------------------
# -------------------------------------------------
# COMPLETE ORDER (QR OR TIME-BASED OVERRIDE)
# -------------------------------------------------
@hotel_bp.route("/orders/complete", methods=["POST"])
def complete_order():
    if not hotel_required():
        return redirect(url_for("auth.login"))

    order_id = request.form.get("order_id")
    entered_qr = request.form.get("qr_code", "").strip()

    if not order_id:
        flash("Invalid request", "danger")
        return redirect(url_for("hotel.orders"))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # 1️⃣ Fetch order (ownership + not completed)
        cur.execute(
            """
            SELECT
                o.items,
                TRIM(o.qr_code) AS qr_code,
                o.hotel_id,
                o.scheduled_time
            FROM orders o
            JOIN hotels h ON o.hotel_id = h.id
            WHERE o.id = %s
              AND h.login_id = %s
              AND o.order_status != 'completed'
            """,
            (order_id, session["login_id"]),
        )
        order = cur.fetchone()

        if not order:
            flash("Order not found or already completed", "danger")
            return redirect(url_for("hotel.orders"))

        # 2️⃣ TIME CHECK (STRICT)
        from datetime import datetime

        scheduled_time = order["scheduled_time"]
        now = datetime.now()

        # 🔥 CORE LOGIC
        is_late = False
        if scheduled_time and now > scheduled_time:
            is_late = True

        # 3️⃣ QR VALIDATION (ONLY IF NOT LATE)
        if not is_late:
            if not entered_qr:
                flash("QR code required", "danger")
                return redirect(url_for("hotel.orders"))

            if entered_qr != order["qr_code"]:
                flash("QR code does not match", "danger")
                return redirect(url_for("hotel.orders"))

        # 4️⃣ Reduce food quantity
        hotel_id = order["hotel_id"]
        items = order["items"] or []

        for item in items:
            item_name = item.get("name", "").strip().lower()
            qty = int(item.get("qty", 0))

            if not item_name or qty <= 0:
                continue

            cur.execute(
                """
                UPDATE menus
                SET available_quantity = available_quantity - %s
                WHERE hotel_id = %s
                  AND LOWER(TRIM(item_name)) = %s
                  AND available_quantity >= %s
                """,
                (qty, hotel_id, item_name, qty),
            )

        # 5️⃣ Mark order completed + late flag
        cur.execute(
            """
            UPDATE orders
            SET order_status = 'completed',
                is_late = %s
            WHERE id = %s
            """,
            (is_late, order_id),
        )

        conn.commit()

        if is_late:
            flash("Order completed (late order – QR skipped)", "warning")
        else:
            flash("Order completed successfully", "success")

    except Exception as e:
        conn.rollback()
        print("ORDER COMPLETION ERROR:", e)
        flash("Order completion failed", "danger")

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("hotel.orders"))


@hotel_bp.route("/orders/report-user", methods=["POST"])
def report_user():
    if not hotel_required():
        flash("Unauthorized access", "danger")
        return redirect(url_for("auth.login"))

    user_id = request.form.get("user_id")
    order_id = request.form.get("order_id")

    if not user_id or not order_id:
        flash("Invalid request", "danger")
        return redirect(url_for("hotel.orders"))

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # 1️⃣ Get current report count
        cur.execute(
            "SELECT report_count, is_premium FROM users WHERE id = %s", (user_id,)
        )
        user = cur.fetchone()

        if not user:
            flash("User not found", "danger")
            return redirect(url_for("hotel.orders"))

        current_count = user["report_count"] or 0
        new_count = current_count + 1

        # 2️⃣ Apply rule: >= 3 reports → revoke premium
        if new_count >= 3:
            cur.execute(
                """
                UPDATE users
                SET is_premium = false,
                    report_count = 0
                WHERE id = %s
                """,
                (user_id,),
            )
            flash(
                "User reported. Premium access revoked due to repeated abuse.",
                "warning",
            )
        else:
            cur.execute(
                """
                UPDATE users
                SET report_count = %s
                WHERE id = %s
                """,
                (new_count, user_id),
            )
            flash(f"User reported successfully ({new_count}/3 warnings).", "warning")

        # 3️⃣ Mark order as completed so it disappears
        cur.execute(
            "UPDATE orders SET order_status = 'completed' WHERE id = %s", (order_id,)
        )

        conn.commit()

    except Exception as e:
        conn.rollback()
        print("REPORT USER ERROR:", e)
        flash("Failed to report user", "danger")

    finally:
        cur.close()
        conn.close()

    return redirect(url_for("hotel.orders"))


@hotel_bp.route("/profile", methods=["GET", "POST"])
def profile():
    if not hotel_required():
        return redirect(url_for("auth.login"))

    conn = get_db_connection()
    cur = conn.cursor()

    # Fetch hotel by login_id
    cur.execute("SELECT * FROM hotels WHERE login_id=%s", (session["login_id"],))
    hotel = cur.fetchone()

    if not hotel:
        cur.close()
        conn.close()
        return redirect(url_for("auth.login"))

    # Update profile
    if request.method == "POST":
        hotel_name = request.form["hotel_name"]
        owner_name = request.form["owner_name"]
        phone = request.form["phone"]
        email = request.form["email"]
        address = request.form["address"]
        location = request.form["location"]

        profile_image = request.files.get("profile_image")
        image_filename = hotel.get("profile_image")

        if profile_image and profile_image.filename:
            image_filename = secure_filename(profile_image.filename)
            upload_dir = "app/static/uploads/hotel_profiles"
            os.makedirs(upload_dir, exist_ok=True)
            profile_image.save(os.path.join(upload_dir, image_filename))

        cur.execute(
            """
            UPDATE hotels
            SET hotel_name=%s,
                owner_name=%s,
                phone=%s,
                email=%s,
                address=%s,
                location=%s,
                profile_image=%s,
                updated_at=NOW()
            WHERE login_id=%s
            """,
            (
                hotel_name,
                owner_name,
                phone,
                email,
                address,
                location,
                image_filename,
                session["login_id"],
            ),
        )

        conn.commit()
        flash("Profile updated successfully", "success")
        return redirect(url_for("hotel.profile"))

    cur.close()
    conn.close()

    return render_template("hotel/profile.html", hotel=hotel)
