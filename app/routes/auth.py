# app/routes/auth.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from app.models.db import get_db_connection
import os
from psycopg2.extras import RealDictCursor

auth_bp = Blueprint("auth", __name__)

# Upload folders
LICENSE_UPLOAD_FOLDER = "app/static/uploads/licenses"
PROFILE_UPLOAD_FOLDER = "app/static/uploads/hotel_profiles"

os.makedirs(LICENSE_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROFILE_UPLOAD_FOLDER, exist_ok=True)


# ---------------- LOGIN ---------------- (unchanged)
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            flash("Email and password are required", "danger")
            return redirect(url_for("auth.login"))

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        try:
            cur.execute(
                """
                SELECT id, password_hash, role
                FROM logins
                WHERE email = %s AND is_active = TRUE
            """,
                (email,),
            )
            login = cur.fetchone()

            if not login or not check_password_hash(login["password_hash"], password):
                flash("Invalid email or password", "danger")
                return redirect(url_for("auth.login"))

            login_id = login["id"]
            role = login["role"]

            # 🔥 NEW: GET USER ID IF ROLE IS USER
            user_id = None
            if role == "user":
                cur.execute("SELECT id FROM users WHERE login_id = %s", (login_id,))
                user = cur.fetchone()
                if not user:
                    flash("User account not found", "danger")
                    return redirect(url_for("auth.login"))
                user_id = user["id"]

            # 🔒 HOTEL APPROVAL CHECK
            if role == "hotel":
                cur.execute(
                    "SELECT status FROM hotels WHERE login_id = %s", (login_id,)
                )
                hotel = cur.fetchone()
                if not hotel or hotel["status"] != "approved":
                    status = hotel["status"] if hotel else "not registered"
                    flash(
                        f"Hotel account not approved yet (status: {status})", "warning"
                    )
                    return redirect(url_for("auth.login"))

            # ✅ SET ALL REQUIRED SESSION VALUES
            session.clear()
            session["login_id"] = login_id
            session["role"] = role
            if user_id:
                session["user_id"] = user_id  # 🔥 THIS FIXES EVERYTHING

            flash("Login successful!", "success")

            if role == "admin":
                return redirect("/admin/dashboard")
            elif role == "user":
                return redirect("/user/dashboard")
            elif role == "hotel":
                return redirect("/hotel/dashboard")

        except Exception as e:
            print("LOGIN ERROR:", e)
            import traceback

            traceback.print_exc()
            flash("An error occurred during login.", "danger")

        finally:
            cur.close()
            conn.close()

    return render_template("auth/login.html")


# ---------------- REGISTER ---------------- (NOW FULLY WORKING)
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        role = request.form.get("role")

        if not email or not password:
            flash("Email and password are required", "danger")
            return redirect(url_for("auth.register"))

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("auth.register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters", "danger")
            return redirect(url_for("auth.register"))

        password_hash = generate_password_hash(password)

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            # Check if email exists
            cur.execute("SELECT id FROM logins WHERE email = %s", (email,))
            if cur.fetchone():
                flash("This email is already registered", "danger")
                return redirect(url_for("auth.register"))

            # Insert login and get ID safely (handles both dict and tuple)
            cur.execute(
                """
                INSERT INTO logins (email, password_hash, role, is_active)
                VALUES (%s, %s, %s, TRUE)
                RETURNING id
                """,
                (email, password_hash, role),
            )
            row = cur.fetchone()
            login_id = (
                row["id"] if isinstance(row, dict) else row[0]
            )  # ← THIS IS THE FIX

            # USER REGISTRATION
            if role == "user":
                full_name = request.form.get("user_full_name", "").strip()
                phone = request.form.get("user_phone", "").strip() or None
                address = request.form.get("user_address", "").strip() or None

                if not full_name:
                    flash("Full name is required", "danger")
                    conn.rollback()
                    return redirect(url_for("auth.register"))

                cur.execute(
                    """
                    INSERT INTO users (login_id, user_full_name, user_phone, user_address)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (login_id, full_name, phone, address),
                )

            # HOTEL REGISTRATION (unchanged – already working)
            elif role == "hotel":
                required_fields = [
                    "hotel_name",
                    "owner_name",
                    "phone",
                    "address",
                    "location",
                    "license_number",
                ]
                missing = [
                    f for f in required_fields if not request.form.get(f, "").strip()
                ]
                if missing:
                    flash("Please fill all required hotel fields", "danger")
                    conn.rollback()
                    return redirect(url_for("auth.register"))

                license_file = request.files.get("license_document")
                if not license_file or not license_file.filename:
                    flash(
                        "License document is required for hotel registration", "danger"
                    )
                    conn.rollback()
                    return redirect(url_for("auth.register"))

                license_filename = secure_filename(license_file.filename)
                license_path = os.path.join(LICENSE_UPLOAD_FOLDER, license_filename)
                license_file.save(license_path)

                profile_file = request.files.get("profile_image")
                profile_filename = None
                if profile_file and profile_file.filename:
                    profile_filename = secure_filename(profile_file.filename)
                    profile_path = os.path.join(PROFILE_UPLOAD_FOLDER, profile_filename)
                    profile_file.save(profile_path)

                cur.execute(
                    """
                    INSERT INTO hotels (
                        login_id, hotel_name, owner_name, phone, email, address, location,
                        license_number, license_document, profile_image, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                    """,
                    (
                        login_id,
                        request.form["hotel_name"].strip(),
                        request.form["owner_name"].strip(),
                        request.form["phone"].strip(),
                        email,
                        request.form["address"].strip(),
                        request.form["location"].strip(),
                        request.form["license_number"].strip(),
                        license_filename,
                        profile_filename,
                    ),
                )

            conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("auth.login"))

        except Exception as e:
            conn.rollback()
            print("\n=== REGISTRATION ERROR ===")
            print("Error:", e)
            print("Role:", role)
            import traceback

            traceback.print_exc()
            flash("Registration failed. Please try again.", "danger")
            return redirect(url_for("auth.register"))

        finally:
            cur.close()
            conn.close()

    return render_template("auth/register.html")


# ---------------- LOGOUT ----------------
@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("auth.login"))
