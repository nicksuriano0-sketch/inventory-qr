from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client
import qrcode
import base64
from io import BytesIO
import os

# --- Environment variables ---
SUPABASE_URL = "https://hwsltnbxalbsjzqrbrwq.supabase.co"
SUPABASE_KEY = "sb_publishable_qoHmkKoKRWqJDVpnuW0qNA_7563V8Zb"
RENDER_URL = "https://your-render-app.onrender.com"  # <- change this to your Render URL

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = "supersecretkey"  # Change to a strong secret

# --- Supabase Client ---
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Routes ---

@app.route("/")
def index():
    fittings = supabase.table("fittings").select("*").execute().data
    return render_template("index.html", fittings=fittings, render_url=RENDER_URL)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        supabase.auth.sign_up({"email": email, "password": password})
        flash("Signup successful! Please log in.")
        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        response = supabase.auth.sign_in({"email": email, "password": password})
        if response.user:
            session["user"] = response.user.id
            return redirect(url_for("index"))
        else:
            flash("Login failed")
    return render_template("login.html")

@app.route("/add_item", methods=["GET", "POST"])
def add_item():
    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]

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

        flash("Item added!")
        return redirect(url_for("index"))
    return render_template("add_item.html")

@app.route("/scan/<item_name>")
def scan(item_name):
    # Example scan handler
    return f"Scanned item: {item_name}"

# --- Run ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
