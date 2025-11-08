from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
import qrcode
import base64
from io import BytesIO
import os

# --- Environment Variables ---
SUPABASE_URL = "https://hwsltnbxalbsjzqrbrwq.supabase.co"
SUPABASE_KEY = "sb_publishable_qoHmkKoKRWqJDVpnuW0qNA_7563V8Zb"
RENDER_URL = "https://inventory-qr-aatq.onrender.com"  # Your live Render app URL

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = "supersecretkey_123456"  # Change this to something random and long

# --- Supabase Client ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ========================
# ROUTES
# ========================

@app.route("/")
def index():
    try:
        fittings = supabase.table("fittings").select("*").execute().data
    except Exception as e:
        fittings = []
        print("Error fetching fittings:", e)
    return render_template("index.html", fittings=fittings, render_url=RENDER_URL)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        try:
            supabase.auth.sign_up(email=email, password=password)
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
            if response and response.user:
                session["user_id"] = response.user.id
                flash("Login successful!", "success")
                return redirect(url_for("index"))
            else:
                flash("Invalid credentials", "danger")
        except Exception as e:
            flash(f"Login failed: {e}", "danger")
    return render_template("login.html")


@app.route("/add_item", methods=["GET", "POST"])
def add_item():
    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]

        # Create QR code with link to scan page
        qr_url = f"{RENDER_URL}/scan/{name}"
        qr_img = qrcode.make(qr_url)
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        # Insert item into Supabase
        try:
            supabase.table("fittings").insert({
                "name": name,
                "category": category,
                "qr_code": qr_base64
            }).execute()
            flash("Item added successfully!", "success")
            return redirect(url_for("index"))
        except Exception as e:
            flash(f"Error adding item: {e}", "danger")

    return render_template("add_item.html")


@app.route("/scan/<item_name>")
def scan(item_name):
    try:
        fitting = supabase.table("fittings").select("*").eq("name", item_name).execute().data
        if not fitting:
            return f"Item '{item_name}' not found."
        return render_template("scan.html", item=fitting[0])
    except Exception as e:
        return f"Error scanning item: {e}"


# --- Run ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
