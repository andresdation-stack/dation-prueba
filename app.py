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

# Estado en memoria por device_id
states = {}


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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            device_id VARCHAR(80) UNIQUE NOT NULL,
            icon VARCHAR(80) NOT NULL DEFAULT 'fa-microchip',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_devices (
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            device_id INTEGER REFERENCES devices(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, device_id)
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
    device_id = request.args.get("device_id")
    if device_id:
        return jsonify(states.get(device_id, {"value": None, "device_id": device_id, "ts": None}))
    return jsonify(states)


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
        value = float(v)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid value"}), 400
    device_id = data.get("device_id", "esp32")
    states[device_id] = {"value": value, "device_id": device_id, "ts": int(time.time())}
    return jsonify({"ok": True}), 200


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
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
            return redirect(url_for("dashboard"))
        error = "Usuario o contraseña incorrectos."
    return render_template("login.html", error=error)


@app.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


@app.get("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    cur = conn.cursor()
    if current_user.is_admin:
        cur.execute("SELECT id, name, device_id, icon FROM devices ORDER BY name")
    else:
        cur.execute("""
            SELECT d.id, d.name, d.device_id, d.icon
            FROM devices d
            JOIN user_devices ud ON d.id = ud.device_id
            WHERE ud.user_id = %s
            ORDER BY d.name
        """, (current_user.id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    now = int(time.time())
    devices = []
    for row in rows:
        s = states.get(row[2], {})
        last_ts = s.get("ts")
        online = last_ts is not None and (now - last_ts) < 300
        devices.append({
            "id": row[0],
            "name": row[1],
            "device_id": row[2],
            "icon": row[3],
            "online": online,
            "value": s.get("value"),
            "ts": last_ts,
        })
    return render_template("dashboard.html", devices=devices)


@app.route("/admin", methods=["GET", "POST"])
@login_required
@admin_required
def admin():
    msg = None
    error = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "create_user":
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

        elif action == "delete_user":
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

        elif action == "create_device":
            name = request.form.get("device_name", "").strip()
            device_id = request.form.get("device_id_str", "").strip()
            icon = request.form.get("icon", "fa-microchip")
            if not name or not device_id:
                error = "Nombre e ID del dispositivo son obligatorios."
            else:
                conn = get_db()
                cur = conn.cursor()
                try:
                    cur.execute(
                        "INSERT INTO devices (name, device_id, icon) VALUES (%s, %s, %s)",
                        (name, device_id, icon)
                    )
                    conn.commit()
                    msg = f"Dispositivo '{name}' creado correctamente."
                except psycopg2.IntegrityError:
                    conn.rollback()
                    error = f"El ID '{device_id}' ya está en uso."
                finally:
                    cur.close()
                    conn.close()

        elif action == "delete_device":
            dev_id = request.form.get("dev_id")
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM devices WHERE id = %s", (dev_id,))
            conn.commit()
            cur.close()
            conn.close()
            msg = "Dispositivo eliminado."

        elif action == "update_user_devices":
            user_id = request.form.get("user_id")
            selected = request.form.getlist("device_ids")
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM user_devices WHERE user_id = %s", (user_id,))
            for did in selected:
                cur.execute(
                    "INSERT INTO user_devices (user_id, device_id) VALUES (%s, %s)",
                    (user_id, did)
                )
            conn.commit()
            cur.close()
            conn.close()
            msg = "Permisos de dispositivos actualizados."

    # Fetch data for render
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, is_admin FROM users ORDER BY id")
    users = cur.fetchall()
    cur.execute("SELECT id, name, device_id, icon FROM devices ORDER BY name")
    devices = cur.fetchall()
    # For each non-admin user, get their assigned device IDs
    user_device_map = {}
    for u in users:
        cur.execute(
            "SELECT device_id FROM user_devices WHERE user_id = %s", (u[0],)
        )
        user_device_map[u[0]] = {row[0] for row in cur.fetchall()}
    cur.close()
    conn.close()

    return render_template("admin.html",
                           users=users,
                           devices=devices,
                           user_device_map=user_device_map,
                           msg=msg,
                           error=error)


@app.context_processor
def inject_globals():
    return {"current_year": time.localtime().tm_year}


with app.app_context():
    if DATABASE_URL:
        init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
