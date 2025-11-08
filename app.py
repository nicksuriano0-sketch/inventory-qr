from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
import qrcode, base64, os
from io import BytesIO

# --------------------------
# Config (your actual values)
# --------------------------
SUPABASE_URL = "https://hwsltnbxalbsjzqrbrwq.supabase.co"
SUPABASE_KEY = "sb_publishable_qoHmkKoKRWqJDVpnuW0qNA_7563V8Zb"
RENDER_URL   = "https://inventory-qr-aatq.onrender.com"  # your Render URL

# Flask
app = Flask(__name__)
app.secret_key = "change_this_to_a_long_random_secret"

# Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# --------------------------
# Helpers
# --------------------------
def make_qr_base64(url: str) -> str:
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def require_login():
    return "user_id" in session


# --------------------------
# Routes
# --------------------------
@app.route("/")
def index():
    try:
        resp = supabase.table("fittings").select("*").order("name").execute()
        fittings = resp.data or []
    except Exception as e:
        fittings = []
        flash(f"Error loading items: {e}", "danger")
    return render_template("index.html", fittings=fittings)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        try:
            # supabase-py v2 expects a dict, not kwargs
            supabase.auth.sign_up({"email": email, "password": password})
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            flash(f"Signup failed: {e}", "danger")
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        try:
            resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if resp and getattr(resp, "user", None):
                session["user_id"] = resp.user.id
                flash("Logged in!", "success")
                return redirect(url_for("index"))
            flash("Invalid email or password.", "danger")
        except Exception as e:
            flash(f"Login failed: {e}", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("index"))


@app.route("/add_item", methods=["GET", "POST"])
def add_item():
    # (optional) require login:
    # if not require_login():
    #     flash("Please log in to add items.", "warning")
    #     return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()  # Copper / Brass / PVC

        if not name:
            flash("Name is required.", "warning")
            return redirect(url_for("add_item"))

        try:
            # Create QR that points to live /scan/<name>
            qr_url = f"{RENDER_URL}/scan/{name}"
            qr_b64 = make_qr_base64(qr_url)

            # Insert new row
            supabase.table("fittings").insert({
                "name": name,
                "category": category,
                "qr_code": qr_b64
            }).execute()

            flash("Item added!", "success")
            return redirect(url_for("index"))
        except Exception as e:
            flash(f"Error adding item: {e}", "danger")

    return render_template("add_item.html")


@app.route("/edit_item/<name>", methods=["GET", "POST"])
def edit_item(name):
    # if not require_login():
    #     flash("Please log in.", "warning")
    #     return redirect(url_for("login"))

    # Load current
    try:
        resp = supabase.table("fittings").select("*").eq("name", name).limit(1).execute()
        if not resp.data:
            flash("Item not found.", "warning")
            return redirect(url_for("index"))
        item = resp.data[0]
    except Exception as e:
        flash(f"Error loading item: {e}", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        new_name = request.form.get("name", "").strip()
        new_cat  = request.form.get("category", "").strip()

        if not new_name:
            flash("Name is required.", "warning")
            return redirect(url_for("edit_item", name=name))

        try:
            # If name changed, regenerate QR to point to new scan URL
            if new_name != item["name"]:
                new_qr = make_qr_base64(f"{RENDER_URL}/scan/{new_name}")
            else:
                new_qr = item.get("qr_code", "")

            supabase.table("fittings").update({
                "name": new_name,
                "category": new_cat,
                "qr_code": new_qr
            }).eq("id", item["id"]).execute()

            flash("Item updated!", "success")
            return redirect(url_for("index"))
        except Exception as e:
            flash(f"Error updating item: {e}", "danger")

    return render_template("edit_item.html", item=item)


@app.route("/scan/<item_name>")
def scan(item_name):
    try:
        resp = supabase.table("fittings").select("*").eq("name", item_name).limit(1).execute()
        if not resp.data:
            flash(f"Item '{item_name}' not found.", "warning")
            return redirect(url_for("index"))
        return render_template("scan.html", item=resp.data[0])
    except Exception as e:
        flash(f"Error scanning: {e}", "danger")
        return redirect(url_for("index"))


# Render/Prod
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
