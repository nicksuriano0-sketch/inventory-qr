from flask import Flask, render_template, request, redirect, url_for, session
import base64
from io import BytesIO
import qrcode
from supabase import create_client

# Supabase connection (replace with your keys)
SUPABASE_URL = "https://hwsltnbxalbsjzqrbrwq.supabase.co"
SUPABASE_KEY = "sb_publishable_qoHmkKoKRWqJDVpnuW0qNA_7563V8Zb"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Change this

# ---------- Utility functions ----------

def generate_qr_base64(data):
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def get_current_user():
    return session.get('user')

def get_all_items():
    user = get_current_user()
    if not user:
        return []
    # Admin sees all, regular sees their own
    if user['is_admin']:
        response = supabase.table('fittings').select('*').execute()
    else:
        response = supabase.table('fittings').select('*').eq('user_id', user['id']).execute()
    items = response.data
    # Generate QR for each
    for item in items:
        item['qr_base64'] = generate_qr_base64(f"{item['id']}")
    return items

# ---------- Routes ----------

@app.route("/")
def index():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    fittings = get_all_items()
    return render_template("index.html", fittings=fittings)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        is_admin = False
        # Add user to Supabase
        supabase.table('users').insert({
            'username': username,
            'password': password,
            'is_admin': is_admin
        }).execute()
        return redirect(url_for('login'))
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        response = supabase.table('users').select('*').eq('username', username).eq('password', password).execute()
        data = response.data
        if data:
            session['user'] = data[0]
            return redirect(url_for('index'))
        else:
            return "Invalid credentials"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route("/add_item", methods=["GET", "POST"])
def add_item():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    if request.method == "POST":
        name = request.form['name']
        category = request.form['category']
        qty = int(request.form['qty'])
        # Add item to Supabase
        response = supabase.table('fittings').insert({
            'name': name,
            'category': category,
            'qty': qty,
            'user_id': user['id']
        }).execute()
        return redirect(url_for('index'))
    return render_template("add_item.html")

@app.route("/edit_item/<item_id>", methods=["GET", "POST"])
def edit_item(item_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    response = supabase.table('fittings').select('*').eq('id', item_id).execute()
    item = response.data[0]
    if request.method == "POST":
        supabase.table('fittings').update({
            'name': request.form['name'],
            'category': request.form['category'],
            'qty': int(request.form['qty'])
        }).eq('id', item_id).execute()
        return redirect(url_for('index'))
    return render_template("edit_item.html", item=item)

@app.route("/delete_item/<item_id>")
def delete_item(item_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    supabase.table('fittings').delete().eq('id', item_id).execute()
    return redirect(url_for('index'))

@app.route("/update_qty/<item_id>/<action>")
def update_qty(item_id, action):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    response = supabase.table('fittings').select('*').eq('id', item_id).execute()
    item = response.data[0]
    new_qty = item['qty'] + 1 if action == 'plus' else max(0, item['qty'] - 1)
    supabase.table('fittings').update({'qty': new_qty}).eq('id', item_id).execute()
    return redirect(url_for('index'))

@app.route("/scan/<item_id>")
def scan(item_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    response = supabase.table('fittings').select('*').eq('id', item_id).execute()
    item = response.data[0]
    return render_template("scan.html", item=item)

# ---------- Run ----------

if __name__ == "__main__":
    app.run(debug=True)
