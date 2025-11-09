from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client
import qrcode
import base64
from io import BytesIO
import os

# --- Config ---
SUPABASE_URL = "https://hwsltnbxalbsjzqrbrwq.supabase.co"
SUPABASE_KEY = "sb_publishable_qoHmkKoKRWqJDVpnuW0qNA_7563V8Zb"
RENDER_URL = "https://inventory-qr-aatq.onrender.com"
ADMIN_EMAIL = "nicksuriano0@gmail.com"

app = Flask(__name__)
app.secret_key = "supersecretkey"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# --- Helpers ---
def get_user_id():
    return session.get("user_id")

def is_admin():
    return session.get("user_email") == ADMIN_EMAIL


# --- Routes ---
@app.route("/")
def index():
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for("login"))

    # Fetch all fittings
    fittings = supabase.table("fittings").select("id, name, category").execute().data or []

    # Fetch user's quantities
    user_stock = supabase.table("user_stock").select("fitting_id, quantity").eq("user_id", user_id).execute().data or []
    stock_lookup = {s["fitting_id"]: s["quantity"] for s in user_stock}

    # Merge quantity into fittings
    for f in fittings:
        f["quantity"] = stock_lookup.get(f["id"], 0)

    return render_template("index.html", fittings=fittings)



@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        try:
            result = supabase.auth.sign_up({"email": email, "password": password})
            if result.user:
                flash("Signup successful! Please log in.")
                return redirect(url_for("login"))
        except Exception as e:
            flash(f"Signup failed: {e}")
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        try:
            result = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if result.user:
                session["user_id"] = result.user.id
                session["user_email"] = email
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
    flash("You have been logged out.")
    return redirect(url_for("login"))


@app.route("/add_item", methods=["GET", "POST"])
def add_item():
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]

        qr_url = f"{RENDER_URL}/scan/{name}"
        qr_img = qrcode.make(qr_url)
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        supabase.table("fittings").insert({
            "name": name,
            "category": category,
            "qr_code": qr_base64
        }).execute()

        flash("Item added successfully!")
        return redirect(url_for("index"))

    return render_template("add_item.html")


@app.route("/scan/<name>", methods=["GET", "POST"])
def scan(name):
    user_id = get_user_id()
    if not user_id:
        return redirect(url_for("login"))

    # Find fitting by name
    fitting_data = supabase.table("fittings").select("*").eq("name", name).execute().data
    fitting = fitting_data[0] if fitting_data else None
    if not fitting:
        flash("Item not found.")
        return redirect(url_for("index"))

    # Fetch user's stock
    stock_resp = supabase.table("user_stock").select("*").eq("user_id", user_id).eq("fitting_id", fitting["id"]).execute()
    current_qty = stock_resp.data[0]["quantity"] if stock_resp.data else 0

    if request.method == "POST":
        action = request.form.get("action")
        new_qty = current_qty + 1 if action == "increase" else max(current_qty - 1, 0)

        if stock_resp.data:
            supabase.table("user_stock").update({"quantity": new_qty}) \
                .eq("user_id", user_id).eq("fitting_id", fitting["id"]).execute()
        else:
            supabase.table("user_stock").insert({
                "user_id": user_id,
                "fitting_id": fitting["id"],
                "quantity": new_qty
            }).execute()

        flash("Quantity updated.")
        return redirect(url_for("scan", name=name))

    return render_template("scan.html", fitting=fitting, quantity=current_qty)


@app.route("/admin")
def admin_dashboard():
    if not is_admin():
        flash("Access denied.")
        return redirect(url_for("index"))

    users = supabase.table("users").select("id, email").execute().data
    return render_template("admin_dashboard.html", users=users)


@app.route("/admin/user/<user_id>")
def view_user_stock(user_id):
    if not is_admin():
        flash("Access denied.")
        return redirect(url_for("index"))

    user_info = supabase.table("users").select("email").eq("id", user_id).execute().data
    stock = supabase.table("user_stock").select("quantity, fitting_id").eq("user_id", user_id).execute().data

    fittings = []
    for s in stock:
        fitting_data = supabase.table("fittings").select("name, category").eq("id", s["fitting_id"]).execute().data
        if fitting_data:
            fittings.append({
                "name": fitting_data[0]["name"],
                "category": fitting_data[0]["category"],
                "quantity": s["quantity"]
            })

    return render_template("admin_user_stock.html", user=user_info[0], fittings=fittings)


# --- Run (Render-compatible) ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
