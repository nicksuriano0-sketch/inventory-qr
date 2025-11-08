#!/usr/bin/env python3
# app.py
from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory
import sqlite3, os, qrcode
from werkzeug.security import generate_password_hash, check_password_hash

# ---------- CONFIG ----------
DB = "fittings.db"
QR_FOLDER = "qrcodes"
SECRET_KEY = "change_this_to_secure_random_value"

# ---------- INIT ----------
app = Flask(__name__)
app.secret_key = SECRET_KEY
if not os.path.exists(QR_FOLDER):
    os.makedirs(QR_FOLDER)

# ---------- DATABASE ----------
def init_db():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            is_admin INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fittings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            category TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_stock (
            user_id INTEGER,
            fitting_id INTEGER,
            quantity INTEGER DEFAULT 0,
            PRIMARY KEY(user_id,fitting_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(fitting_id) REFERENCES fittings(id)
        )
    """)
    con.commit()
    con.close()

# ---------- USERS ----------
def add_user(username,password,is_admin=0):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    hashed = generate_password_hash(password)
    try:
        cur.execute("INSERT INTO users (username,password,is_admin) VALUES (?,?,?)",(username,hashed,is_admin))
        con.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        con.close()

def verify_user(username,password):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT id,password,is_admin FROM users WHERE username=?",(username,))
    row = cur.fetchone()
    con.close()
    if row and check_password_hash(row[1],password):
        return row[0],row[2]
    return None,None

# ---------- FITTINGS ----------
def get_fittings_for_user(user_id,is_admin=False):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    if is_admin:
        cur.execute("""
            SELECT f.id,f.name,f.category,u.username,IFNULL(us.quantity,0)
            FROM fittings f
            LEFT JOIN user_stock us ON f.id = us.fitting_id
            LEFT JOIN users u ON us.user_id = u.id
            ORDER BY f.name,u.username
        """)
    else:
        cur.execute("""
            SELECT f.id,f.name,f.category,IFNULL(us.quantity,0)
            FROM fittings f
            LEFT JOIN user_stock us ON f.id = us.fitting_id AND us.user_id = ?
        """,(user_id,))
    data = cur.fetchall()
    con.close()
    return data

def add_fitting(name,category):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO fittings (name,category) VALUES (?,?)",(name,category))
    con.commit()
    con.close()
    generate_qr(name)

def edit_fitting(fitting_id,new_name,new_category):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT name FROM fittings WHERE id=?",(fitting_id,))
    old_name = cur.fetchone()[0]
    cur.execute("UPDATE fittings SET name=?,category=? WHERE id=?",(new_name,new_category,fitting_id))
    con.commit()
    con.close()
    old_qr = os.path.join(QR_FOLDER,f"{old_name}.png")
    if os.path.exists(old_qr):
        os.remove(old_qr)
    generate_qr(new_name)

def delete_fitting(fitting_id):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT name FROM fittings WHERE id=?",(fitting_id,))
    row = cur.fetchone()
    if row:
        qr_file = os.path.join(QR_FOLDER,f"{row[0]}.png")
        if os.path.exists(qr_file):
            os.remove(qr_file)
    cur.execute("DELETE FROM fittings WHERE id=?",(fitting_id,))
    cur.execute("DELETE FROM user_stock WHERE fitting_id=?",(fitting_id,))
    con.commit()
    con.close()

# ---------- USER STOCK ----------
def update_user_stock(user_id,fitting_id,delta):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT quantity FROM user_stock WHERE user_id=? AND fitting_id=?",(user_id,fitting_id))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE user_stock SET quantity=quantity+? WHERE user_id=? AND fitting_id=?",(delta,user_id,fitting_id))
    else:
        cur.execute("INSERT INTO user_stock (user_id,fitting_id,quantity) VALUES (?,?,?)",(user_id,fitting_id,delta))
    con.commit()
    con.close()

# ---------- QR CODE ----------
def generate_qr(item_name):
    url = f"http://localhost:5000/scan/{item_name}"
    img = qrcode.make(url)
    img.save(os.path.join(QR_FOLDER,f"{item_name}.png"))

# ---------- HTML ----------
HTML = """
<!doctype html>
<html>
<head>
<title>Inventory App</title>
<style>
body {font-family: Arial; max-width:900px; margin:20px auto; background:#f0f2f5; padding:20px; border-radius:10px;}
h2,h3{text-align:center;color:#333;}
table {width:100%;border-collapse:collapse;margin-top:20px;background:#fff;border-radius:10px;overflow:hidden;}
th, td {border:1px solid #ccc;padding:8px;text-align:center;}
th {background-color:#007bff;color:white;}
button {padding:5px 10px;margin:2px;border:none;border-radius:5px;cursor:pointer;background-color:#007bff;color:white;}
button:hover {opacity:0.8;}
input[type=text], input[type=password] {padding:5px;margin:2px;border-radius:5px;border:1px solid #ccc;}
form {margin:5px 0;}
img.qr {width:100px;height:100px;border:1px solid #ccc;border-radius:10px;}
</style>
</head>
<body>
<h2>Welcome {{ session.get('username','Guest') }}</h2>
{% if not session.get('username') %}
<form method="POST" action="/login">
Username: <input name="username" required>
Password: <input type="password" name="password" required>
<input type="submit" value="Login">
</form>
<h3>Or Register</h3>
<form method="POST" action="/register">
Username: <input name="username" required>
Password: <input type="password" name="password" required>
<input type="submit" value="Register">
</form>
{% else %}
<h3>Add new fitting</h3>
<form method="POST" action="/add">
Name: <input name="name" required>
Category: <input name="category" required>
<input type="submit" value="Add">
</form>

<h3>Fittings</h3>
<table>
<tr>
<th>Name</th><th>Category</th>
{% if session.get('is_admin') %}<th>User</th>{% endif %}
<th>Qty</th><th>QR</th><th>Actions</th></tr>

{% for f in fittings %}
<tr>
<td>{{f[1]}}</td>
<td>{{f[2]}}</td>
{% if session.get('is_admin') %}<td>{{f[3]}}</td>{% endif %}
<td>{{f[4]}}</td>
<td><img src="/qrcodes/{{f[1]}}.png" class="qr"></td>
<td>
<form style="display:inline" method="POST" action="/change">
<input type="hidden" name="id" value="{{f[0]}}">
<button name="delta" value="1">+</button>
<button name="delta" value="-1">-</button>
</form>
<form style="display:inline" method="POST" action="/edit">
<input type="hidden" name="id" value="{{f[0]}}">
<input name="name" placeholder="New Name" required>
<input name="category" placeholder="New Category" required>
<button>Save</button>
</form>
<form style="display:inline" method="POST" action="/delete">
<input type="hidden" name="id" value="{{f[0]}}">
<button onclick="return confirm('Are you sure?')">Delete</button>
</form>
</td>
</tr>
{% endfor %}
</table>
<form method="POST" action="/logout"><button>Logout</button></form>
{% endif %}
</body>
</html>
"""

# ---------- ROUTES ----------
@app.route("/", methods=["GET"])
def home():
    if not session.get("username"):
        return render_template_string(HTML)
    fittings = get_fittings_for_user(session["user_id"], session.get("is_admin"))
    return render_template_string(HTML,fittings=fittings)

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]
    user_id,is_admin = verify_user(username,password)
    if user_id:
        session["username"] = username
        session["user_id"] = user_id
        session["is_admin"] = is_admin
    return redirect(url_for("home"))

@app.route("/register", methods=["POST"])
def register():
    username = request.form["username"]
    password = request.form["password"]
    add_user(username,password)
    user_id,is_admin = verify_user(username,password)
    if user_id:
        session["username"] = username
        session["user_id"] = user_id
        session["is_admin"] = is_admin
    return redirect(url_for("home"))

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/add", methods=["POST"])
def add():
    name = request.form["name"]
    category = request.form["category"]
    add_fitting(name,category)
    return redirect(url_for("home"))

@app.route("/change", methods=["POST"])
def change():
    fitting_id = int(request.form["id"])
    delta = int(request.form["delta"])
    update_user_stock(session["user_id"],fitting_id,delta)
    return redirect(url_for("home"))

@app.route("/edit", methods=["POST"])
def edit():
    fitting_id = int(request.form["id"])
    new_name = request.form["name"]
    new_category = request.form["category"]
    edit_fitting(fitting_id,new_name,new_category)
    return redirect(url_for("home"))

@app.route("/delete", methods=["POST"])
def delete():
    fitting_id = int(request.form["id"])
    delete_fitting(fitting_id)
    return redirect(url_for("home"))

@app.route("/qrcodes/<filename>")
def serve_qr(filename):
    return send_from_directory(QR_FOLDER, filename)

@app.route("/scan/<item_name>")
def scan(item_name):
    if session.get("user_id"):
        fid = get_fitting_id_by_name(item_name)
        if fid:
            update_user_stock(session["user_id"],fid,1)
    return f"Scanned {item_name}. Stock updated for user {session.get('username')}."

def get_fitting_id_by_name(name):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT id FROM fittings WHERE name=?",(name,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else None

# ---------- RUN ----------
if __name__ == "__main__":
    if not os.path.exists(DB):
        init_db()
    add_user("admin","admin123",1)
    app.run(host="0.0.0.0", port=5000)
