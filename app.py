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
        cursor = get_cursor(db)
        cursor.execute(
            "SELECT is_admin FROM users WHERE id = %s",
            (session["user_id"],)
        )
        user = cursor.fetchone()
        db.close()

        if not user or user["is_admin"] != 1:
            return "Access denied", 403

        return f(*args, **kwargs)
    return decorated


app = Flask(__name__)
app.secret_key = "69736861746F6E6D79646F6F7273746570"
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:root@localhost/postgres')

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def get_cursor(conn):
    return conn.cursor(cursor_factory=RealDictCursor)

@app.route("/")
def index():
    db = get_db()
    cursor = get_cursor(db)
    cursor.execute(
        "SELECT * FROM shops WHERE checked = 1 AND shown = 1"
    )
    shops = cursor.fetchall()
    db.close()
    return render_template("index.html", shops=shops)

@app.route("/create", methods=["GET", "POST"])
@login_required
def create_shop():
    if request.method == "POST":
        try:
            title = request.form["title"]
            username = request.form["username"]
            x = request.form["x"]
            y = request.form["y"]
            image = request.files["image"]

            image_path = os.path.join(app.config["UPLOAD_FOLDER"], image.filename)
            image.save(image_path)

            db = get_db()
            cursor = get_cursor(db)
            cursor.execute(
                "INSERT INTO shops (title, username, x, y, image, checked, shown) VALUES (%s, %s, %s, %s, %s, 0, 1)",
                (title, username, x, y, image.filename)
            )
            db.commit()
            db.close()
            flash("tienda creada con exito!!!","info")
            return redirect("/")
        except Exception as e:
            print(f"Error creating shop: {e}")
            flash("Error creating shop","error")
            return redirect("/create")
    return render_template("create_shop.html")

@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    db = get_db()
    cursor = get_cursor(db)

    if request.method == "POST":
        shop_id = request.form["shop_id"]
        action = request.form["action"]

        if action == "approve":
            cursor.execute(
                "UPDATE shops SET checked = 1 WHERE id = %s",
                (shop_id,)
            )
            flash("tienda aprobada con exito!!!","info")
        elif action == "reject":
            cursor.execute(
                "UPDATE shops SET checked = 1, shown = 0 WHERE id = %s",
                (shop_id,)
            )
            flash("tienda rechazada","info")
        db.commit()

    cursor.execute(
        "SELECT * FROM shops WHERE checked = 0"
    )
    shops = cursor.fetchall()
    db.close()

    return render_template("admin.html", shops=shops)

@app.route("/admin/rejected", methods=["GET", "POST"])
@admin_required
def admin_rejected():
    db = get_db()
    cursor = get_cursor(db)

    if request.method == "POST":
        shop_id = request.form["shop_id"]

        cursor.execute(
            "UPDATE shops SET shown = 1 WHERE id = %s",
            (shop_id,)
        )
        db.commit()
        flash("tienda reaprobada con exito!!!","info")

    cursor.execute(
        "SELECT * FROM shops WHERE checked = 1 AND shown = 0"
    )
    shops = cursor.fetchall()
    db.close()

    return render_template("rejected.html", shops=shops)

@app.route("/admin/approved", methods=["GET", "POST"])
@admin_required
def admin_approved():
    db = get_db()
    cursor = get_cursor(db)

    if request.method == "POST":
        shop_id = request.form["shop_id"]

        cursor.execute(
            "UPDATE shops SET shown = 0 WHERE id = %s",
            (shop_id,)
        )
        db.commit()
        flash("tienda desaprobada :c","info")

    cursor.execute(
        "SELECT * FROM shops WHERE shown = 1 AND checked = 1"
    )
    shops = cursor.fetchall()
    db.close()

    return render_template("approved.html", shops=shops)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        password_hash = generate_password_hash(password)

        db = get_db()
        cursor = get_cursor(db)
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                (username, password_hash)
            )
            db.commit()
            flash("yay, estas registrado!!!!","success")
        except psycopg2.errors.IntegrityError:
            db.rollback()
            flash("usuario ya existe :c","error")
        finally:
            db.close()
        
        return redirect("/login")
    
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        cursor = get_cursor(db)
        cursor.execute(
            "SELECT * FROM users WHERE username = %s",
            (username,)
        )
        user = cursor.fetchone()
        db.close()

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
