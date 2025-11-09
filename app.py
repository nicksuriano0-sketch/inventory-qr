from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client
import qrcode
import base64
from io import BytesIO

# --- Configuration ---
SUPABASE_URL = "https://hwsltnbxalbsjzqrbrwq.supabase.co"
SUPABASE_KEY = "sb_publishable_qoHmkKoKRWqJDVpnuW0qNA_7563V8Zb"
ADMIN_EMAIL = "nicksuriano0@gmail.com"  # 👈 your admin email
RENDER_URL = "https://inventory-qr-aatq.onrender.com"

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = "supersecretkey"  # ⚠️ replace later with a strong secret

# --- Supabase Client ---
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ========== ROUTES ==========

@app.route("/")
def index():
    """Show current user's fittings or all if admin."""
    if "user" not in session:
        return redirect(url_for("login"))

    email = session.get("email")
    if session.get("is_admin"):
        fittings = supabase.table("fittings").select("*").execute().data
    else:
        fittings = (
            supabase.table("user_stock")
            .select("*, fittings(name, category)")
            .eq("user_email", email)
            .execute()
            .data
        )

    return render_template("index.html", fittings=fittings)


# --- AUTH ROUTES ---

@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Register a new user."""
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        try:
            supabase.auth.sign_up({"email": email, "password": password})
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            flash(f"Signup failed: {e}", "danger")
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log in existing users (redirects admin automatically)."""
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        try:
            response = supabase.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            if response.user:
                session["user"] = response.user.id
                session["email"] = email
                session["is_admin"] = email.lower() == ADMIN_EMAIL.lower()
                flash("Login successful!", "success")

                if session["is_admin"]:
                    return redirect(url_for("admin_dashboard"))
                else:
                    return redirect(url_for("index"))
            else:
                flash("Login failed", "danger")
        except Exception as e:
            flash(f"Login error: {e}", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Log out user."""
    session.clear()
    flash("You’ve been logged out.", "info")
    return redirect(url_for("login"))


# --- INVENTORY MANAGEMENT ---

@app.route("/add_item", methods=["GET", "POST"])
def add_item():
    """Admin adds a new fitting type."""
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]

        try:
            # Create QR code
            qr_url = f"{RENDER_URL}/scan/{name}"
            qr_img = qrcode.make(qr_url)
            buffer = BytesIO()
            qr_img.save(buffer, format="PNG")
            qr_base64 = base64.b64encode(buffer.getvalue()).decode()

            supabase.table("fittings").insert(
                {"name": name, "category": category, "qr_code": qr_base64}
            ).execute()

            flash("Item added successfully!", "success")
            return redirect(url_for("index"))
        except Exception as e:
            flash(f"Error adding item: {e}", "danger")

    return render_template("add_item.html")


@app.route("/scan/<item_name>")
def scan(item_name):
    """QR code scan endpoint."""
    email = session.get("email", "Guest")

    # Get fitting
    fitting = (
        supabase.table("fittings").select("*").eq("name", item_name).execute().data
    )
    if not fitting:
        return f"Item '{item_name}' not found."

    # Get or create user stock record
    stock = (
        supabase.table("user_stock")
        .select("*")
        .eq("user_email", email)
        .eq("fitting_name", item_name)
        .execute()
        .data
    )

    if not stock:
        supabase.table("user_stock").insert(
            {"user_email": email, "fitting_name": item_name, "quantity": 0}
        ).execute()
        quantity = 0
    else:
        quantity = stock[0]["quantity"]

    return render_template("scan.html", name=item_name, quantity=quantity)


@app.route("/update_quantity", methods=["POST"])
def update_quantity():
    """Update user stock quantity via scan page."""
    if "user" not in session:
        return redirect(url_for("login"))

    email = session["email"]
    name = request.form["name"]
    action = request.form["action"]

    stock = (
        supabase.table("user_stock")
        .select("*")
        .eq("user_email", email)
        .eq("fitting_name", name)
        .execute()
        .data
    )

    if stock:
        quantity = stock[0]["quantity"]
        new_qty = quantity + 1 if action == "plus" else max(quantity - 1, 0)
        supabase.table("user_stock").update({"quantity": new_qty}).eq(
            "user_email", email
        ).eq("fitting_name", name).execute()
    else:
        new_qty = 1 if action == "plus" else 0
        supabase.table("user_stock").insert(
            {"user_email": email, "fitting_name": name, "quantity": new_qty}
        ).execute()

    return redirect(url_for("scan", item_name=name))


# --- ADMIN DASHBOARD ---

@app.route("/admin")
def admin_dashboard():
    """Admin overview page."""
    if not session.get("is_admin"):
        flash("Access denied.", "danger")
        return redirect(url_for("index"))

    users = supabase.table("users").select("*").execute().data
    return render_template("admin_dashboard.html", users=users)


@app.route("/admin/view_user_stock/<email>")
def view_user_stock(email):
    """Admin view a specific user's inventory."""
    if not session.get("is_admin"):
        return redirect(url_for("index"))

    stock = (
        supabase.table("user_stock")
        .select("*, fittings(name, category)")
        .eq("user_email", email)
        .execute()
        .data
    )

    return render_template("view_user_stock.html", email=email, stock=stock)


import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
