import os
import time
import psycopg2
from functools import wraps
from flask import (Flask, request, jsonify, render_template,
                   send_from_directory, redirect, url_for)
from flask_login import (LoginManager, UserMixin, login_user,
                         logout_user, login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash

API_KEY = os.environ.get("API_KEY", "andres-123")
DATABASE_URL = os.environ.get("DATABASE_URL")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

login_manager = LoginManager(app)
login_manager.login_view = "login"

state = {"value": None, "device_id": None, "ts": None}


def get_db():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(80) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE
        )
    """)
    cur.execute("SELECT id FROM users WHERE is_admin = TRUE LIMIT 1")
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, TRUE)",
            ("admin", generate_password_hash("dation2024"))
        )
        print("Admin creado: usuario=admin  contraseña=dation2024 — cambiala desde el panel!")
    conn.commit()
    cur.close()
    conn.close()


class User(UserMixin):
    def __init__(self, id, username, is_admin):
        self.id = id
        self.username = username
        self.is_admin = is_admin


@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, is_admin FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return User(row[0], row[1], row[2])
    return None


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/about")
def about():
    return render_template("about.html")


@app.get("/health")
def health():
    return "ok", 200


@app.get("/api/latest")
def latest():
    return jsonify(state)


@app.get("/assets/<path:filename>")
def assets(filename):
    return send_from_directory("assets", filename)


@app.post("/ingest")
def ingest():
    data = request.get_json(silent=True) or {}
    if data.get("api_key") != API_KEY:
        return jsonify({"error": "unauthorized"}), 401
    v = data.get("value")
    if v is None:
        return jsonify({"error": "missing value"}), 400
    try:
        state["value"] = float(v)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid value"}), 400
    state["device_id"] = data.get("device_id", "esp32")
    state["ts"] = int(time.time())
    return jsonify({"ok": True}), 200


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, password_hash, is_admin FROM users WHERE username = %s",
            (username,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and check_password_hash(row[2], password):
            login_user(User(row[0], row[1], row[3]))
            return redirect(url_for("home"))
        error = "Usuario o contraseña incorrectos."
    return render_template("login.html", error=error)


@app.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


@app.route("/admin", methods=["GET", "POST"])
@login_required
@admin_required
def admin():
    msg = None
    error = None
    if request.method == "POST":
        action = request.form.get("action")

        if action == "create":
            username = request.form.get("new_username", "").strip()
            password = request.form.get("new_password", "")
            is_admin = request.form.get("is_admin") == "on"
            if not username or not password:
                error = "El usuario y la contraseña son obligatorios."
            else:
                conn = get_db()
                cur = conn.cursor()
                try:
                    cur.execute(
                        "INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, %s)",
                        (username, generate_password_hash(password), is_admin)
                    )
                    conn.commit()
                    msg = f"Usuario '{username}' creado correctamente."
                except psycopg2.IntegrityError:
                    conn.rollback()
                    error = f"El usuario '{username}' ya existe."
                finally:
                    cur.close()
                    conn.close()

        elif action == "change_password":
            user_id = request.form.get("user_id")
            new_password = request.form.get("new_password", "")
            if not new_password:
                error = "La nueva contraseña no puede estar vacía."
            else:
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    "UPDATE users SET password_hash = %s WHERE id = %s",
                    (generate_password_hash(new_password), user_id)
                )
                conn.commit()
                cur.close()
                conn.close()
                msg = "Contraseña actualizada correctamente."

        elif action == "delete":
            user_id = request.form.get("user_id")
            if str(user_id) == str(current_user.id):
                error = "No podés eliminar tu propia cuenta."
            else:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()
                cur.close()
                conn.close()
                msg = "Usuario eliminado."

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, is_admin FROM users ORDER BY id")
    users = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin.html", users=users, msg=msg, error=error)


@app.context_processor
def inject_globals():
    return {"current_year": time.localtime().tm_year}


with app.app_context():
    if DATABASE_URL:
        init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
