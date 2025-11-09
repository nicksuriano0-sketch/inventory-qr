from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client
import qrcode
import base64
from io import BytesIO
import os

# --- Supabase Config ---
SUPABASE_URL = "https://hwsltnbxalbsjzqrbrwq.supabase.co"
SUPABASE_KEY = "sb_publishable_qoHmkKoKRWqJDVpnuW0qNA_7563V8Zb"

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = "supersecretkey"

# --- Supabase Client ---
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Routes ---

@app.route("/")
def index():
    fittings = supabase.table("fittings").select("*").execute().data
    return render_template("index.html", fittings=fittings)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        try:
            response = supabase.auth.sign_up({"email": email, "password": password})
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
                session["user"] = response.user.id
                flash("Login successful!", "success")
                return redirect(url_for("index"))
            else:
                flash("Invalid credentials.", "danger")
        except Exception as e:
            flash(f"Login failed: {e}", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/add_item", methods=["GET", "POST"])
def add_item():
    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]

        try:
            # Generate QR code that links to the scan route for this item
            qr = qrcode.make(f"{request.host_url}scan/{name}")
            buffer = BytesIO()
            qr.save(buffer, format="PNG")
            qr_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

            # Save to Supabase
            supabase.table("fittings").insert({
                "name": name,
                "category": category,
                "qr_code": qr_b64
            }).execute()

            flash("Item added successfully!", "success")
            return redirect(url_for("index"))

        except Exception as e:
            flash(f"Error adding item: {e}", "danger")
            return redirect(url_for("add_item"))

    return render_template("add_item.html")

@app.route("/scan/<name>", methods=["GET", "POST"])
def scan(name):
    fitting_data = supabase.table("fittings").select("*").eq("name", name).execute().data
    fitting = fitting_data[0] if fitting_data else None

    if not fitting:
        flash("Item not found.", "danger")
        return redirect(url_for("index"))

    quantity = fitting.get("quantity", 0)

    if request.method == "POST":
        action = request.form.get("action")
        if action == "increase":
            quantity += 1
        elif action == "decrease" and quantity > 0:
            quantity -= 1

        # Update the quantity in Supabase
        supabase.table("fittings").update({"quantity": quantity}).eq("name", name).execute()
        flash("Quantity updated!", "success")
        return redirect(url_for("scan", name=name))

    return render_template("scan.html", fitting=fitting, quantity=quantity)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
