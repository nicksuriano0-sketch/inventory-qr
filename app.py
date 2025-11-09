from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from supabase import create_client, Client
import qrcode, base64, os
from io import BytesIO

SUPABASE_URL = "https://hwsltnbxalbsjzqrbrwq.supabase.co"
SUPABASE_KEY = "sb_publishable_qoHmkKoKRWqJDVpnuW0qNA_7563V8Zb"
RENDER_URL = "https://inventory-qr-aatq.onrender.com"

app = Flask(__name__)
app.secret_key = "change_this_to_a_long_random_secret"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def make_qr_base64(url: str) -> str:
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


@app.route("/")
def index():
    user_id = session.get("user_id")
    fittings = []

    try:
        if not user_id:
            fittings = supabase.table("fittings").select("*").order("name").execute().data
        else:
            user_resp = supabase.table("user_stock").select("fitting_id, quantity").eq("user_id", user_id).execute()
            user_stock = {row["fitting_id"]: row["quantity"] for row in user_resp.data}

            all_fittings = supabase.table("fittings").select("*").order("name").execute().data
            for f in all_fittings:
                f["quantity"] = user_stock.get(f["id"], 0)
                fittings.append(f)
    except Exception as e:
        flash(f"Error loading stock: {e}", "danger")

    return render_template("index.html", fittings=fittings)


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
            resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if resp and getattr(resp, "user", None):
                session["user_id"] = resp.user.id
                flash("Logged in!", "success")
                return redirect(url_for("index"))
            flash("Invalid login credentials", "danger")
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
    if request.method == "POST":
        name = request.form["name"].strip()
        category = request.form["category"].strip()
        try:
            qr_url = f"{RENDER_URL}/scan/{name}"
            qr_b64 = make_qr_base64(qr_url)
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
    # Load the existing item
    result = supabase.table("fittings").select("*").eq("name", name).execute()
    if not result.data:
        return f"Item {name} not found", 404
    item = result.data[0]

    if request.method == "POST":
        new_name = request.form["name"]
        category = request.form["category"]

        supabase.table("fittings").update({
            "name": new_name,
            "category": category
        }).eq("id", item["id"]).execute()

        flash("Item updated!")
        return redirect(url_for("index"))

    return render_template("edit_item.html", item=item)


@app.route("/scan/<item_name>")
def scan(item_name):
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in to manage stock.", "warning")
        return redirect(url_for("login"))

    try:
        resp = supabase.table("fittings").select("*").eq("name", item_name).limit(1).execute()
        if not resp.data:
            flash("Item not found.", "warning")
            return redirect(url_for("index"))
        item = resp.data[0]

        # Get user-specific quantity
        qresp = supabase.table("user_stock").select("quantity").eq("user_id", user_id).eq("fitting_id", item["id"]).execute()
        item["quantity"] = qresp.data[0]["quantity"] if qresp.data else 0

        return render_template("scan.html", item=item)
    except Exception as e:
        flash(f"Error scanning: {e}", "danger")
        return redirect(url_for("index"))


@app.route("/update_quantity", methods=["POST"])
def update_quantity():
    try:
        data = request.json
        fitting_id = data.get("id")
        change = int(data.get("change", 0))
        user_id = session.get("user_id")

        if not user_id:
            return jsonify({"error": "Not logged in"}), 403

        # Get or create user_stock entry
        resp = supabase.table("user_stock").select("*").eq("user_id", user_id).eq("fitting_id", fitting_id).execute()
        if resp.data:
            current_qty = resp.data[0]["quantity"]
            new_qty = max(0, current_qty + change)
            supabase.table("user_stock").update({"quantity": new_qty}).eq("user_id", user_id).eq("fitting_id", fitting_id).execute()
        else:
            new_qty = max(0, change)
            supabase.table("user_stock").insert({
                "user_id": user_id,
                "fitting_id": fitting_id,
                "quantity": new_qty
            }).execute()

        return jsonify({"success": True, "quantity": new_qty})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Admin Routes ---
@app.route("/admin")
def admin_dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    # Check if current user is admin
    user_info = supabase.auth.get_user(session["user"])
    if not user_info or user_info.user.email != "nicksuriano0@gmail.com":
        flash("Access denied.")
        return redirect(url_for("index"))

    # Get list of users
    users = supabase.table("users").select("id, email").execute().data
    return render_template("admin_dashboard.html", users=users)


@app.route("/admin/user/<user_id>")
def admin_user_stock(user_id):
    if "user" not in session:
        return redirect(url_for("login"))

    user_info = supabase.auth.get_user(session["user"])
    if not user_info or user_info.user.email != "nicksuriano0@gmail.com":
        flash("Access denied.")
        return redirect(url_for("index"))

    # Fetch user’s stock joined with fittings
    stock_data = supabase.rpc("get_user_stock_with_fittings", {"uid": user_id}).execute().data
    return render_template("admin_user_stock.html", stock=stock_data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
