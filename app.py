from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client
import qrcode
import base64
from io import BytesIO
import os
from collections import defaultdict

# ========= Config (edit these 3 if needed) =========
SUPABASE_URL = "https://hwsltnbxalbsjzqrbrwq.supabase.co"
SUPABASE_KEY = "sb_publishable_qoHmkKoKRWqJDVpnuW0qNA_7563V8Zb"
RENDER_URL    = "https://inventory-qr-aatq.onrender.com"   # public URL used inside QR codes
ADMIN_EMAIL   = "nicksuriano0@gmail.com"                   # admin login email

# ========= Flask / Supabase =========
app = Flask(__name__)
app.secret_key = "supersecretkey_change_me"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ========= Helpers =========
def current_email() -> str | None:
    return session.get("email")

def is_authed() -> bool:
    return "user" in session and "email" in session

def is_admin() -> bool:
    return bool(session.get("is_admin"))


# ========= Pages =========
@app.route("/")
def index():
    # Redirect if not logged in
    if "user" not in session:
        return redirect(url_for("login"))

    user_email = session.get("email")

    # Fetch all fittings
    fittings_response = supabase.table("fittings").select("*").execute()
    fittings = fittings_response.data or []

    # Fetch this user's stock
    user_stock_response = (
        supabase.table("user_stock")
        .select("fitting_id, quantity")
        .eq("user_email", user_email)
        .execute()
    )
    user_stock = {u["fitting_id"]: u["quantity"] for u in user_stock_response.data or []}

    # Merge data — show user quantity or 0
    for f in fittings:
        f["quantity"] = user_stock.get(f["id"], 0)

    return render_template("index.html", fittings=fittings)



# ========= Auth =========
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"].strip()
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
        email = request.form["email"].strip()
        password = request.form["password"]
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if getattr(res, "user", None):
                session["user"] = res.user.id
                session["email"] = email
                session["is_admin"] = (email.lower() == ADMIN_EMAIL.lower())

                # make sure this user exists in public.users (handy in case trigger didn't run locally)
                try:
                    supabase.table("users").upsert(
                        {"id": res.user.id, "email": email},
                        on_conflict="id"
                    ).execute()
                except Exception:
                    pass

                if session["is_admin"]:
                    flash("Welcome, admin!", "success")
                    return redirect(url_for("admin_dashboard"))
                flash("Login successful.", "success")
                return redirect(url_for("index"))
            else:
                flash("Login failed.", "danger")
        except Exception as e:
            flash(f"Login error: {e}", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


# ========= Fittings (catalog) =========
@app.route("/add_item", methods=["GET", "POST"])
def add_item():
    if not is_authed():
        return redirect(url_for("login"))
    if not is_admin():
        flash("Only admin can add items.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        name = request.form["name"].strip()
        category = request.form["category"].strip()

        try:
            # Build QR code pointing to the scan endpoint
            qr_url = f"{RENDER_URL}/scan/{name}"
            img = qrcode.make(qr_url)
            buf = BytesIO()
            img.save(buf, format="PNG")
            qr_b64 = base64.b64encode(buf.getvalue()).decode()

            supabase.table("fittings").insert(
                {"name": name, "category": category, "qr_code": qr_b64}
            ).execute()
            flash("Item added.", "success")
            return redirect(url_for("index"))
        except Exception as e:
            flash(f"Error adding item: {e}", "danger")

    return render_template("add_item.html")


# ========= Scanning / Per-user quantities =========
@app.route("/scan/<name>", methods=["GET", "POST"])
def scan(name):
    user = supabase.auth.get_user()
    if not user or not user.user:
        flash("You must be logged in to adjust stock.", "error")
        return redirect(url_for("login"))

    user_id = user.user.id
    user_email = user.user.email

    fitting = supabase.table("fittings").select("*").eq("name", name).single().execute().data
    if not fitting:
        flash("Item not found.", "error")
        return redirect(url_for("index"))

    # Fetch current stock for this user + fitting
    stock_data = (
        supabase.table("user_stock")
        .select("quantity")
        .eq("user_id", user_id)
        .eq("fitting_id", fitting["id"])
        .execute()
    )

    current_qty = 0
    if stock_data.data:
        current_qty = stock_data.data[0]["quantity"]

    if request.method == "POST":
        action = request.form.get("action")
        new_qty = current_qty + 1 if action == "plus" else max(0, current_qty - 1)

        # Insert or update this user's stock entry
        supabase.table("user_stock").upsert({
            "user_id": user_id,
            "user_email": user_email,
            "fitting_id": fitting["id"],
            "fitting_name": fitting["name"],
            "quantity": new_qty
        }).execute()

        current_qty = new_qty

    return render_template("scan.html", fitting=fitting, quantity=current_qty)


# ========= Admin dashboard =========
@app.route("/admin")
def admin_dashboard():
    if not is_authed() or not is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("index"))

    # fetch all users
    users = supabase.table("users").select("id, email, is_admin").execute().data or []

    # fetch all stock rows and aggregate totals per user_email
    totals = defaultdict(int)
    rows = supabase.table("user_stock").select("user_email, quantity").execute().data or []
    for r in rows:
        totals[r["user_email"]] += int(r.get("quantity", 0))

    # attach total to each user (by matching email)
    for u in users:
        u["total_quantity"] = totals.get(u.get("email", ""), 0)

    # sort: admins first, then by email
    users.sort(key=lambda u: (not u.get("is_admin", False), u.get("email", "")))

    return render_template("admin_dashboard.html", users=users)


@app.route("/admin/user/<email>")
def admin_user_stock(email):
    if not is_authed() or not is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("index"))

    # rows for this user
    rows = (
        supabase.table("user_stock")
        .select("fitting_name, quantity")
        .eq("user_email", email)
        .execute()
        .data
        or []
    )

    # get categories for display
    names = [r["fitting_name"] for r in rows]
    categories = {}
    if names:
        fits = supabase.table("fittings").select("name, category").execute().data or []
        categories = {f["name"]: f.get("category", "") for f in fits}

    stock = [
        {
            "name": r["fitting_name"],
            "category": categories.get(r["fitting_name"], ""),
            "quantity": r["quantity"],
        }
        for r in rows
    ]

    total = sum(int(i["quantity"]) for i in stock)
    return render_template("view_user_stock.html", email=email, stock=stock, total=total)


# ========= Run (Render-friendly) =========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
