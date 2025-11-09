from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client
import qrcode
import base64
from io import BytesIO
import os

# --- Environment variables ---
SUPABASE_URL = "https://hwsltnbxalbsjzqrbrwq.supabase.co"
SUPABASE_KEY = "sb_publishable_qoHmkKoKRWqJDVpnuW0qNA_7563V8Zb"
RENDER_URL = "https://inventory-qr-aatq.onrender.com"  # Change to your Render app URL

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = "supersecretkey"  # Change this to something strong

# --- Supabase Client ---
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Constants ---
ADMIN_EMAIL = "nicksuriano0@gmail.com"  # Your admin email

# ---------------------------------------------------
# Helper functions
# ---------------------------------------------------

def get_user_id():
    """Return the logged-in user's ID from session."""
    return session.get("user")


def get_user_email():
    """Return the logged-in user's email."""
    return session.get("email")


# ---------------------------------------------------
# Routes
# ---------------------------------------------------

@app.route("/")
def index():
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for("login"))

    # Admin sees all fittings, users see their own stock
    if get_user_email() == ADMIN_EMAIL:
        fittings = supabase.table("fittings").select("*").execute().data
    else:
        # Join fittings with user_stock for that user
        stock_data = supabase.table("user_stock").select("fitting_id, quantity").eq("user_id", user_id).execute().data
        fittings = supabase.table("fittings").select("*").execute().data

        # Map quantities for user
        stock_map = {s["fitting_id"]: s["quantity"] for s in stock_data}
        for f in fittings:
            f["quantity"] = stock_map.get(f["id"], 0)

    return render_template("index.html", fittings=fittings)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        try:
            res = supabase.auth.sign_up({"email": email, "password": password})
            if res.user:
                flash("Signup successful! Please log in.")
                return redirect(url_for("login"))
            else:
                flash("Signup failed.")
        except Exception as e:
            flash(f"Signup failed: {e}")
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if res.user:
                session["user"] = res.user.id
                session["email"] = email
                flash("Login successful!")

                # Redirect admin to dashboard
                if email == ADMIN_EMAIL:
                    return redirect(url_for("admin_dashboard"))
                return redirect(url_for("index"))
            else:
                flash("Invalid credentials.")
        except Exception as e:
            flash(f"Login failed: {e}")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for("login"))


@app.route("/add_item", methods=["GET", "POST"])
def add_item():
    user_id = get_user_id()
    if not user_id:
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

            # Insert into Supabase
            supabase.table("fittings").insert({
                "name": name,
                "category": category,
                "qr_code": qr_base64
            }).execute()

            flash("Item added successfully!")
            return redirect(url_for("index"))
        except Exception as e:
            flash(f"Error adding item: {e}")
    return render_template("add_item.html")


@app.route("/scan/<name>", methods=["GET", "POST"])
def scan(name):
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for("login"))

    # Fetch the fitting by name (handles duplicates)
    fitting_data = supabase.table("fittings").select("*").eq("name", name).execute().data
    fitting = fitting_data[0] if


    if not fitting:
        flash("Item not found.")
        return redirect(url_for("index"))

    # Get user's stock quantity
    stock_resp = supabase.table("user_stock").select("*").eq("user_id", user_id).eq("fitting_id", fitting["id"]).execute()
    current_qty = stock_resp.data[0]["quantity"] if stock_resp.data else 0

    if request.method == "POST":
        action = request.form.get("action")
        new_qty = current_qty + 1 if action == "increase" else max(current_qty - 1, 0)

        # Upsert user's stock
        supabase.table("user_stock").upsert({
            "user_id": user_id,
            "fitting_id": fitting["id"],
            "quantity": new_qty
        }).execute()

        flash("Quantity updated.")
        return redirect(url_for("scan", name=name))

    return render_template("scan.html", fitting=fitting, quantity=current_qty)


# ---------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------

@app.route("/admin")
def admin_dashboard():
    user_email = get_user_email()
    if user_email != ADMIN_EMAIL:
        flash("Access denied.")
        return redirect(url_for("index"))

    users = supabase.table("users").select("*").execute().data
    return render_template("admin_dashboard.html", users=users)


@app.route("/admin/user/<user_id>")
def admin_user_stock(user_id):
    user_email = get_user_email()
    if user_email != ADMIN_EMAIL:
        flash("Access denied.")
        return redirect(url_for("index"))

    stock = supabase.table("user_stock").select("*").eq("user_id", user_id).execute().data
    fittings = supabase.table("fittings").select("*").execute().data
    fitting_map = {f["id"]: f["name"] for f in fittings}

    for s in stock:
        s["name"] = fitting_map.get(s["fitting_id"], "Unknown")

    return render_template("admin_user_stock.html", stock=stock)


# ---------------------------------------------------
# Render Port Fix
# ---------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
