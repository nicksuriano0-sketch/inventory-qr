from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from supabase import create_client, Client
import qrcode, base64, os
from io import BytesIO

SUPABASE_URL = "https://hwsltnbxalbsjzqrbrwq.supabase.co"
SUPABASE_KEY = "sb_publishable_qoHmkKoKRWqJDVpnuW0qNA_7563V8Zb"
RENDER_URL   = "https://inventory-qr-aatq.onrender.com"

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
    try:
        fittings = supabase.table("fittings").select("*").order("name").execute().data or []
    except Exception as e:
        fittings = []
        flash(f"Error loading items: {e}", "danger")
    return render_template("index.html", fittings=fittings)


@app.route("/add_item", methods=["GET", "POST"])
def add_item():
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


@app.route("/scan/<item_name>")
def scan(item_name):
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
