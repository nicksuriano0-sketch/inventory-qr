from flask import Flask, render_template, request, redirect, url_for, session
from supabase import create_client
import qrcode
import io
import base64
from werkzeug.security import generate_password_hash, check_password_hash

# -----------------------------
# CONFIGURATION
# -----------------------------
SUPABASE_URL = "https://hwsltnbxalbsjzqrbrwq.supabase.co"
SUPABASE_KEY = "sb_publishable_qoHmkKoKRWqJDVpnuW0qNA_7563V8Zb"
RENDER_URL = "https://inventory-qr-ix8f.onrender.com"  # Your deployed URL

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)
app.secret_key = "r9X2v#8kLq!3wPz7tGm$Yb1uHfE5nQx2"

# -----------------------------
# UTILITY FUNCTIONS
# -----------------------------
def generate_qr(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def get_user_stock(user_id):
    res = supabase.table("user_stock").select("*").eq("user_id", user_id).execute()
    return res.data if res.data else []

def get_fittings():
    res = supabase.table("fittings").select("*").execute()
    return res.data if res.data else []

def get_users():
    res = supabase.table("users").select("*").execute()
    return res.data if res.data else []

# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id = session["user_id"]
    is_admin = session.get("is_admin", False)

    fittings = get_fittings()
    if is_admin:
        user_stock = supabase.table("user_stock").select("*").execute().data
    else:
        user_stock = get_user_stock(user_id)

    # Add QR base64
    for f in fittings:
        f["qr_base64"] = generate_qr(f"{RENDER_URL}/scan/{f['id']}")

    return render_template("index.html", fittings=fittings, stock=user_stock, admin=is_admin)

# -----------------------------
# LOGIN / SIGNUP
# -----------------------------
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        res = supabase.table("users").select("*").eq("username", username).execute()
        user = res.data[0] if res.data else None
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["is_admin"] = user.get("is_admin", False)
            return redirect(url_for("index"))
        return "Invalid credentials"
    return render_template("login.html")

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        res = supabase.table("users").insert({"username": username, "password": password, "is_admin": False}).execute()
        return redirect(url_for("login"))
    return render_template("signup.html")

# -----------------------------
# ADD / EDIT / DELETE ITEMS
# -----------------------------
@app.route("/add_item", methods=["GET","POST"])
def add_item():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        name = request.form["name"]
        category = request.form["category"]
        res = supabase.table("fittings").insert({"name": name, "category": category, "qr_code": ""}).execute()
        fitting_id = res.data[0]["id"]
        qr_data = f"{RENDER_URL}/scan/{fitting_id}"
        qr_img = generate_qr(qr_data)
        supabase.table("fittings").update({"qr_code": qr_data}).eq("id", fitting_id).execute()
        return redirect(url_for("index"))
    return render_template("add_item.html")

@app.route("/edit_item/<fitting_id>", methods=["GET","POST"])
def edit_item(fitting_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        name = request.form["name"]
        quantity = int(request.form["quantity"])
        supabase.table("fittings").update({"name": name}).eq("id", fitting_id).execute()
        # Update user stock for current user
        user_id = session["user_id"]
        stock_res = supabase.table("user_stock").select("*").eq("user_id", user_id).eq("fitting_id", fitting_id).execute()
        if stock_res.data:
            supabase.table("user_stock").update({"quantity": quantity}).eq("user_id", user_id).eq("fitting_id", fitting_id).execute()
        else:
            supabase.table("user_stock").insert({"user_id": user_id, "fitting_id": fitting_id, "quantity": quantity}).execute()
        return redirect(url_for("index"))
    # GET
    fitting_res = supabase.table("fittings").select("*").eq("id", fitting_id).execute()
    fitting = fitting_res.data[0] if fitting_res.data else {}
    return render_template("edit_item.html", fitting=fitting)

@app.route("/delete_item/<fitting_id>")
def delete_item(fitting_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    supabase.table("fittings").delete().eq("id", fitting_id).execute()
    supabase.table("user_stock").delete().eq("fitting_id", fitting_id).execute()
    return redirect(url_for("index"))

# -----------------------------
# QR SCAN ENDPOINT
# -----------------------------
@app.route("/scan/<fitting_id>", methods=["GET","POST"])
def scan(fitting_id):
    if "user_id" not in session:
        return "Please login to update stock"
    user_id = session["user_id"]
    stock_res = supabase.table("user_stock").select("*").eq("user_id", user_id).eq("fitting_id", fitting_id).execute()
    if stock_res.data:
        quantity = stock_res.data[0]["quantity"] + 1
        supabase.table("user_stock").update({"quantity": quantity}).eq("user_id", user_id).eq("fitting_id", fitting_id).execute()
    else:
        supabase.table("user_stock").insert({"user_id": user_id, "fitting_id": fitting_id, "quantity": 1}).execute()
    return redirect(url_for("index"))

# -----------------------------
# LOGOUT
# -----------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# -----------------------------
# RUN APP
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
