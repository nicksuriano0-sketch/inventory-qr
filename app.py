from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from supabase import create_client, Client
import qrcode, base64, os
from io import BytesIO

# --- Supabase & Flask Config ---
SUPABASE_URL = "https://hwsltnbxalbsjzqrbrwq.supabase.co"
SUPABASE_KEY = "sb_publishable_qoHmkKoKRWqJDVpnuW0qNA_7563V8Zb"
RENDER_URL   = "https://inventory-qr-aatq.onrender.com"

app = Flask(__name__)
app.secret_key = "change_this_to_a_long_random_secret"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# --- Helper Functions ---
def make_qr_base64(url: str) -> str:
    """Generate base64 PNG QR code."""
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# --- Routes ---
@app.route("/")
def index():
    """Homepage showing all fittings and quantities."""
    try:
        fittings = supabase.table("fittings").select("*").order("name").execute().data or []
    except Exception as e:
        fittings = []
        flash(f"Error loading items: {e}", "danger")
    return render_template("index.html", fittings=fittings)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """User sign-up route."""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        try:
            supabase.auth.sign_up({"email": email, "password": password})
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            flash(f"Signup failed: {e}", "danger")
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """User login route."""
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
    """Log user out."""
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("index"))


@app.route("/add_item", methods=["GET", "POST"])
def add_item():
    """Add a new fitting item."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()

        if not name:
            flash("Name is required.", "warning")
            return redirect(url_for("add_item"))

        try:
            qr_url = f"{RENDER_URL}/scan/{name}"
            qr_b64 = make_qr_base64(qr_url)

            supabase.table("fittings").insert({
                "name": name,
                "category": category,
                "quantity": 0,
                "qr_code": qr_b64
            }).execute()

            flash("Item added!", "success")
            return redirect(url_for("index"))
        except Exception as e:
            flash(f"Error adding item: {e}", "danger")

    return render_template("add_item.html")


@app.route("/edit_item/<name>", methods=["GET", "POST"])
def edit_item(name):
    """Edit an existing fitting (name/category)."""
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
        new_cat = request.form.get("category", "").strip()

        if not new_name:
            flash("Name is required.", "warning")
            return redirect(url_for("edit_item", name=name))

        try:
            # regenerate QR if name changed
            new_qr = item["qr_code"]
            if new_name != item["name"]:
                new_qr = make_qr_base64(f"{RENDER_URL}/scan/{new_name}")

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
    """Scan a QR and view or update item quantity."""
    try:
        resp = supabase.table("fittings").select("*").eq("name", item_name).limit(1).execute()
        if not resp.data:
            flash(f"Item '{item_name}' not found.", "warning")
            return redirect(url_for("index"))
        item = resp.data[0]
        return render_template("scan.html", item=item)
    except Exception as e:
        flash(f"Error scanning: {e}", "danger")
        return redirect(url_for("index"))


@app.route("/update_quantity", methods=["POST"])
def update_quantity():
    """Increment or decrement item quantity."""
    try:
        data = request.json
        item_id = data.get("id")
        change = int(data.get("change", 0))

        resp = supabase.table("fittings").select("quantity").eq("id", item_id).limit(1).execute()
        if not resp.data:
            return jsonify({"error": "Item not found"}), 404

        current_qty = resp.data[0].get("quantity", 0)
        new_qty = max(0, current_qty + change)

        supabase.table("fittings").update({"quantity": new_qty}).eq("id", item_id).execute()
        return jsonify({"success": True, "quantity": new_qty})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Run Server ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
