from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor
import os

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return(decorated)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")

        db = get_db()
        user = db.execute(
            "SELECT is_admin FROM users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()

        if not user or user["is_admin"] != 1:
            return "Access denied", 403

        return f(*args, **kwargs)
    return decorated


app = Flask(__name__)
app.secret_key = "69736861746F6E6D79646F6F7273746570"
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:root@localhost/postgres')

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.row_factory = RealDictCursor
    return conn

@app.route("/")
def index():
    db = get_db()
    shops = db.execute(
        "SELECT * FROM shops WHERE checked = 1 AND shown = 1"
    ).fetchall()
    return render_template("index.html", shops=shops)

@app.route("/create", methods=["GET", "POST"])
@login_required
def create_shop():
    if request.method == "POST":
        title = request.form["title"]
        username = request.form["username"]
        x = request.form["x"]
        y = request.form["y"]
        image = request.files["image"]

        image_path = os.path.join(app.config["UPLOAD_FOLDER"], image.filename)
        image.save(image_path)

        db = get_db()
        db.execute(
            "INSERT INTO shops (title, username, x, y, image, checked, shown) VALUES (?, ?, ?, ?, ?, 0, 1)",
            (title, username, x, y, image.filename)
        )
        db.commit()
        flash("tienda creada con exito!!!","info")
        return redirect("/")
    return render_template("create_shop.html")

@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    db = get_db()

    if request.method == "POST":
        shop_id = request.form["shop_id"]
        action = request.form["action"]

        if action == "approve":
            db.execute(
                "UPDATE shops SET checked = 1 WHERE id = ?",
                (shop_id,)
            )
            flash("tienda aprobada con exito!!!","info")
        elif action == "reject":
            db.execute(
                "UPDATE shops SET checked = 1, shown = 0 WHERE id = ?",
                (shop_id,)
            )
            flash("tienda rechazada","info")
        db.commit()

    shops = db.execute(
        "SELECT * FROM shops WHERE checked = 0"
    ).fetchall()

    return render_template("admin.html", shops=shops)

@app.route("/admin/rejected", methods=["GET", "POST"])
@admin_required
def admin_rejected():
    db = get_db()

    if request.method == "POST":
        shop_id = request.form["shop_id"]

        db.execute(
            "UPDATE shops SET shown = 1 WHERE id = ?",
            (shop_id,)
        )
        db.commit()
        flash("tienda reaprobada con exito!!!","info")

    shops = db.execute(
        "SELECT * FROM shops WHERE checked = 1 AND shown = 0"
    ).fetchall()

    return render_template("rejected.html", shops=shops)

@app.route("/admin/approved", methods=["GET", "POST"])
@admin_required
def admin_approved():
    db = get_db()

    if request.method == "POST":
        shop_id = request.form["shop_id"]

        db.execute(
            "UPDATE shops SET shown = 0 WHERE id = ?",
            (shop_id,)
        )
        db.commit()
        flash("tienda desaprobada :c","info")

    shops = db.execute(
        "SELECT * FROM shops WHERE shown = 1 AND checked = 1"
    ).fetchall()

    return render_template("approved.html", shops=shops)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        password_hash = generate_password_hash(password)

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash)
            )
            db.commit()
            flash("yay, estas registrado!!!!","success")
        except psycopg2.errors.IntegrityError:
            flash("usuario ya existe :c","error")
        
        return redirect("/login")
    
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["is_admin"] = user["is_admin"]
            flash("disfruta de estas tiendas pochas!!!!!", "success")
            return redirect("/")
        else:
            flash("usuario o contraseña incorrectos","error")
        
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run(debug=False)
