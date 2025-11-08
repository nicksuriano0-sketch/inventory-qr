from flask import Flask, render_template, request, redirect, url_for
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
RENDER_URL = os.getenv("RENDER_URL")# -----------------------------
# 2️⃣ Initialize Flask + Supabase
# -----------------------------
app = Flask(__name__)

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Connected to Supabase successfully!")
except Exception as e:
    print("❌ Error connecting to Supabase:", e)


# -----------------------------
# 3️⃣ Routes
# -----------------------------

@app.route("/")
def index():
    """Show all stock fittings"""
    try:
        data = supabase.table("fittings").select("*").execute()
        fittings = data.data
        return render_template("index.html", fittings=fittings)
    except Exception as e:
        return f"Error loading data: {e}"


@app.route("/add", methods=["POST"])
def add_fitting():
    """Add a new fitting"""
    try:
        name = request.form["name"]
        category = request.form["category"]
        qty = int(request.form["qty"])
        supabase.table("fittings").insert({
            "name": name,
            "category": category,
            "qty": qty
        }).execute()
        return redirect(url_for("index"))
    except Exception as e:
        return f"Error adding fitting: {e}"


@app.route("/edit/<int:id>", methods=["POST"])
def edit_fitting(id):
    """Edit a fitting"""
    try:
        name = request.form["name"]
        category = request.form["category"]
        qty = int(request.form["qty"])
        supabase.table("fittings").update({
            "name": name,
            "category": category,
            "qty": qty
        }).eq("id", id).execute()
        return redirect(url_for("index"))
    except Exception as e:
        return f"Error editing fitting: {e}"


@app.route("/delete/<int:id>")
def delete_fitting(id):
    """Delete a fitting"""
    try:
        supabase.table("fittings").delete().eq("id", id).execute()
        return redirect(url_for("index"))
    except Exception as e:
        return f"Error deleting fitting: {e}"


@app.route("/scan")
def scan_page():
    """QR Scan page"""
    qr_link = f"{RENDER_URL}/scan/{item_id}"
    return render_template("scan.html", qr_link=qr_link)


# -----------------------------
# 4️⃣ Run Flask app
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
