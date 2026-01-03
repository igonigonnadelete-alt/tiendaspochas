from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()
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

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

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
    user_id = session.get("user_id")
    
    cursor.execute("""
        SELECT s.*, COALESCE(SUM(v.vote_value), 0) as vote_count
        FROM shops s
        LEFT JOIN votes v ON s.id = v.shop_id
        WHERE s.checked = 1 AND s.shown = 1
        GROUP BY s.id
        ORDER BY vote_count DESC
    """)
    shops = cursor.fetchall()
    
    user_votes = {}
    if user_id:
        cursor.execute(
            "SELECT shop_id, vote_value FROM votes WHERE user_id = %s",
            (user_id,)
        )
        for row in cursor.fetchall():
            user_votes[row["shop_id"]] = row["vote_value"]
    
    for shop in shops:
        shop["user_vote"] = user_votes.get(shop["id"], 0)
    
    db.close()
    return render_template("index.html", shops=shops)

@app.route("/vote/<int:shop_id>/<vote_type>", methods=["POST"])
@login_required
def vote(shop_id, vote_type):
    if vote_type not in ["up", "down"]:
        return jsonify({"error": "Invalid vote type"}), 400
    
    vote_value = 1 if vote_type == "up" else -1
    user_id = session["user_id"]
    
    db = get_db()
    cursor = get_cursor(db)
    
    try:
        cursor.execute(
            """
            INSERT INTO votes (user_id, shop_id, vote_value)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, shop_id)
            DO UPDATE SET vote_value = %s
            """,
            (user_id, shop_id, vote_value, vote_value)
        )
        db.commit()
        
        cursor.execute(
            "SELECT COALESCE(SUM(vote_value), 0) as vote_count FROM votes WHERE shop_id = %s",
            (shop_id,)
        )
        result = cursor.fetchone()
        vote_count = result["vote_count"] if result else 0
        
        cursor.execute(
            "SELECT vote_value FROM votes WHERE user_id = %s AND shop_id = %s",
            (user_id, shop_id)
        )
        user_vote_result = cursor.fetchone()
        user_vote = user_vote_result["vote_value"] if user_vote_result else 0
        db.close()
        
        return jsonify({"vote_count": vote_count, "user_vote": user_vote}), 200
    except Exception as e:
        db.close()
        print(f"Error voting: {e}")
        return jsonify({"error": "Error voting"}), 500

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

            result = cloudinary.uploader.upload(image)
            image_url = result["secure_url"]

            db = get_db()
            cursor = get_cursor(db)
            cursor.execute(
                "INSERT INTO shops (title, username, x, y, image, checked, shown) VALUES (%s, %s, %s, %s, %s, 0, 1)",
                (title, username, x, y, image_url)
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
