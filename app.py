from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client
import qrcode
import base64
from io import BytesIO
import os

# --- Supabase Config ---
SUPABASE_URL = "https://hwsltnbxalbsjzqrbrwq.supabase.co"
SUPABASE_KEY = "sb_publishable_qoHmkKoKRWqJDVpnuW0qNA_7563V8Zb"
ADMIN_EMAIL = "nicksuriano0@gmail.com"

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = "supersecretkey"

# --- Supabase Client ---
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Helpers ---
def get_user():
    return session.get("user_email")

def is_admin():
    return get_user() == ADMIN_EMAIL

# --- Auth-required decorator ---
def login_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_email" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper

# --- Routes ---
@app.route("/")
def home():
    # Always go to login if not logged in
    if "user_email" not in session:
        return redirect(url_for("login"))
    # Redirect admin or user appropriately
    if is_admin():
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("index"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
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
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if response.user:
                session["user_id"] = response.user.id
                session["user_email"] = email
                flash("Login successful!", "success")
                if email == ADMIN_EMAIL:
                    return redirect(url_for("admin_dashboard"))
                return redirect(url_for("index"))
            else:
                flash("Invalid credentials.", "danger")
        except Exception as e:
            flash(f"Login failed: {e}", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))

# --- User Inventory ---
@app.route("/inventory")
@login_required
def index():
    email = get_user()
    try:
        # Filter items per user
        data = supabase.table("user_stock").select("*, fittings(name, category, qr_code)").eq("user_email", email).execute()
        items = data.data
    except Exception as e:
        flash(f"Error loading stock: {e}", "danger")
        items = []
    return render_template("index.html", fittings=items)

# --- Add Item (Admin only) ---
@app.route("/add_item", methods=["GET", "POST"])
@login_required
def add_item():
    if not is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]
        try:
            qr = qrcode.make(f"{request.host_url}scan/{name}")
            buffer = BytesIO()
            qr.save(buffer, format="PNG")
            qr_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            supabase.table("fittings").insert({
                "name": name,
                "category": category,
                "qr_code": qr_b64
            }).execute()
            flash("Fitting added successfully!", "success")
            return redirect(url_for("admin_dashboard"))
        except Exception as e:
            flash(f"Error adding item: {e}", "danger")
    return render_template("add_item.html")

# --- Scan and Adjust ---
@app.route("/scan/<name>", methods=["GET", "POST"])
@login_required
def scan(name):
    email = get_user()

    # Get fitting info
    fitting_data = supabase.table("fittings").select("*").eq("name", name).execute().data
    if not fitting_data:
        flash("Item not found.", "danger")
        return redirect(url_for("index"))
    fitting = fitting_data[0]

    # Get user quantity
    stock_data = supabase.table("user_stock").select("*").eq("user_email", email).eq("fitting_name", name).execute().data
    quantity = stock_data[0]["quantity"] if stock_data else 0

    if request.method == "POST":
        action = request.form.get("action")
        if action == "increase":
            quantity += 1
        elif action == "decrease" and quantity > 0:
            quantity -= 1

        # Upsert (insert or update)
        try:
            supabase.table("user_stock").upsert({
                "user_email": email,
                "fitting_name": name,
                "quantity": quantity
            }).execute()
            flash("Quantity updated!", "success")
            return redirect(url_for("scan", name=name))
        except Exception as e:
            flash(f"Error updating quantity: {e}", "danger")

    return render_template("scan.html", fitting=fitting, quantity=quantity)

# --- Admin Dashboard ---
@app.route("/admin")
@login_required
def admin_dashboard():
    if not is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("index"))
    try:
        users_data = supabase.table("user_stock").select("user_email").execute().data
        users = sorted(set([u["user_email"] for u in users_data]))
    except Exception as e:
        flash(f"Error loading users: {e}", "danger")
        users = []
    return render_template("admin_dashboard.html", users=users)

@app.route("/admin/view/<user_email>")
@login_required
def admin_view_user(user_email):
    if not is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("index"))
    try:
        stock = supabase.table("user_stock").select("*").eq("user_email", user_email).execute().data
    except Exception as e:
        flash(f"Error loading user stock: {e}", "danger")
        stock = []
    return render_template("admin_user_stock.html", user_email=user_email, stock=stock)

# --- Run App ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
