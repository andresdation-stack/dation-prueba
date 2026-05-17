import os
import json
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, request, jsonify, render_template, redirect,
                   url_for, flash, send_from_directory, abort)
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras

# ── Config ─────────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
DATABASE_URL = os.environ.get("DATABASE_URL", "")
API_KEY = os.environ.get("API_KEY", "andres-123")

# ── DB helpers ─────────────────────────────────────────────────────────────────

def _conn():
    return psycopg2.connect(DATABASE_URL)

def db_get(sql, params=()):
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()

def db_one(sql, params=()):
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        conn.close()

def db_run(sql, params=()):
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()

def db_run_returning(sql, params=()):
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            result = cur.fetchone()
        conn.commit()
        return result
    finally:
        conn.close()

# ── Flask-Login ────────────────────────────────────────────────────────────────

login_manager = LoginManager(app)
login_manager.login_view = "login_view"
login_manager.login_message = "Iniciá sesión para continuar."

class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]
        self.is_admin = row["is_admin"]
        self.nombre = row.get("nombre") or ""
        self.apellido = row.get("apellido") or ""
        self.empresa_id = row.get("empresa_id")

@login_manager.user_loader
def load_user(user_id):
    row = db_one("SELECT * FROM usuarios WHERE id = %s", (user_id,))
    return User(row) if row else None

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated

# ── DB Init ────────────────────────────────────────────────────────────────────

def init_db():
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS empresas (
                    id SERIAL PRIMARY KEY,
                    nombre VARCHAR(200) NOT NULL,
                    direccion VARCHAR(300),
                    cuit VARCHAR(20),
                    razon_social VARCHAR(200),
                    pais VARCHAR(100) DEFAULT 'Argentina',
                    telefono VARCHAR(50),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS empresa_contactos (
                    id SERIAL PRIMARY KEY,
                    empresa_id INTEGER REFERENCES empresas(id) ON DELETE CASCADE,
                    puesto VARCHAR(100),
                    nombre VARCHAR(200),
                    telefono VARCHAR(50),
                    email VARCHAR(200)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(80) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    is_admin BOOLEAN DEFAULT FALSE,
                    nombre VARCHAR(100),
                    apellido VARCHAR(100),
                    email VARCHAR(200),
                    telefono VARCHAR(50),
                    zona_horaria VARCHAR(50) DEFAULT 'America/Argentina/Buenos_Aires',
                    empresa_id INTEGER REFERENCES empresas(id) ON DELETE SET NULL,
                    comentarios TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS dispositivos (
                    id SERIAL PRIMARY KEY,
                    empresa_id INTEGER REFERENCES empresas(id) ON DELETE SET NULL,
                    nombre VARCHAR(100) NOT NULL,
                    device_id VARCHAR(80) UNIQUE NOT NULL,
                    icon VARCHAR(80) NOT NULL DEFAULT 'fa-microchip',
                    tiene_gps BOOLEAN DEFAULT FALSE,
                    tiene_caudal BOOLEAN DEFAULT FALSE,
                    caudal_factor NUMERIC,
                    tiene_sensor1 BOOLEAN DEFAULT FALSE,
                    sensor1_nombre VARCHAR(100),
                    sensor1_icon VARCHAR(80),
                    sensor1_factor NUMERIC,
                    tiene_sensor2 BOOLEAN DEFAULT FALSE,
                    sensor2_nombre VARCHAR(100),
                    sensor2_icon VARCHAR(80),
                    sensor2_factor NUMERIC,
                    tiene_sensor3 BOOLEAN DEFAULT FALSE,
                    sensor3_nombre VARCHAR(100),
                    sensor3_icon VARCHAR(80),
                    sensor3_factor NUMERIC,
                    tiene_sensor4 BOOLEAN DEFAULT FALSE,
                    sensor4_nombre VARCHAR(100),
                    sensor4_icon VARCHAR(80),
                    sensor4_factor NUMERIC,
                    tiene_sensor5 BOOLEAN DEFAULT FALSE,
                    sensor5_nombre VARCHAR(100),
                    sensor5_icon VARCHAR(80),
                    sensor5_factor NUMERIC,
                    tiene_maquina BOOLEAN DEFAULT FALSE,
                    maquina_ancho NUMERIC,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nodos (
                    id SERIAL PRIMARY KEY,
                    imei VARCHAR(20) UNIQUE NOT NULL,
                    marca VARCHAR(100),
                    modelo VARCHAR(100),
                    firmware VARCHAR(100),
                    fecha_compra DATE,
                    fecha_instalacion DATE,
                    remito_instalacion VARCHAR(200),
                    empresa_id INTEGER REFERENCES empresas(id) ON DELETE SET NULL,
                    dispositivo_id INTEGER REFERENCES dispositivos(id) ON DELETE SET NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS nodo_sims (
                    id SERIAL PRIMARY KEY,
                    nodo_id INTEGER REFERENCES nodos(id) ON DELETE CASCADE,
                    compania VARCHAR(100),
                    imei_sim VARCHAR(20)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuario_dispositivos (
                    usuario_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
                    dispositivo_id INTEGER REFERENCES dispositivos(id) ON DELETE CASCADE,
                    PRIMARY KEY (usuario_id, dispositivo_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS estados (
                    id SERIAL PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL,
                    color VARCHAR(20) NOT NULL DEFAULT '#3498db',
                    es_trabajo BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS configuraciones (
                    id SERIAL PRIMARY KEY,
                    nombre VARCHAR(200) NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS configuracion_estados (
                    id SERIAL PRIMARY KEY,
                    configuracion_id INTEGER REFERENCES configuraciones(id) ON DELETE CASCADE,
                    estado_id INTEGER REFERENCES estados(id) ON DELETE CASCADE,
                    orden INTEGER DEFAULT 0,
                    bandera1 BOOLEAN DEFAULT FALSE,
                    bandera2 BOOLEAN DEFAULT FALSE,
                    bandera3 BOOLEAN DEFAULT FALSE,
                    bandera4 BOOLEAN DEFAULT FALSE,
                    bandera5 BOOLEAN DEFAULT FALSE,
                    bandera6 BOOLEAN DEFAULT FALSE,
                    bandera7 BOOLEAN DEFAULT FALSE,
                    bandera8 BOOLEAN DEFAULT FALSE,
                    velocidad_activa BOOLEAN DEFAULT FALSE,
                    velocidad_min NUMERIC,
                    velocidad_max NUMERIC,
                    sensor1_activa BOOLEAN DEFAULT FALSE,
                    sensor1_min NUMERIC,
                    sensor1_max NUMERIC,
                    sensor2_activa BOOLEAN DEFAULT FALSE,
                    sensor2_min NUMERIC,
                    sensor2_max NUMERIC,
                    sensor3_activa BOOLEAN DEFAULT FALSE,
                    sensor3_min NUMERIC,
                    sensor3_max NUMERIC
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS device_heartbeats (
                    device_id VARCHAR(80) PRIMARY KEY,
                    last_seen TIMESTAMP NOT NULL,
                    last_data JSONB
                )
            """)
            # Admin por defecto
            cur.execute("SELECT id FROM usuarios WHERE is_admin = TRUE LIMIT 1")
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO usuarios (username, password_hash, is_admin) VALUES (%s, %s, TRUE)",
                    ("admin", generate_password_hash("dation2024"))
                )
            conn.commit()
    finally:
        conn.close()

# ── Landing & estáticos ────────────────────────────────────────────────────────

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/about")
def about():
    return render_template("about.html")

@app.get("/health")
def health():
    return "ok", 200

@app.get("/debug")
def debug():
    import sys
    info = {
        "python": sys.version,
        "db_url_set": bool(DATABASE_URL),
        "db_url_prefix": DATABASE_URL[:20] + "..." if DATABASE_URL else None,
    }
    try:
        conn = _conn()
        conn.close()
        info["db_connect"] = "ok"
    except Exception as e:
        info["db_connect"] = str(e)
    try:
        rows = db_get("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        info["tables"] = [r["tablename"] for r in rows]
    except Exception as e:
        info["tables"] = str(e)
    return jsonify(info)

@app.get("/assets/<path:filename>")
def assets(filename):
    return send_from_directory("assets", filename)

# ── Auth ───────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login_view():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        row = db_one("SELECT * FROM usuarios WHERE username = %s", (username,))
        if row and check_password_hash(row["password_hash"], password):
            login_user(User(row))
            return redirect(url_for("dashboard"))
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("login.html")

@app.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login_view"))

# ── Dashboard ──────────────────────────────────────────────────────────────────

@app.get("/dashboard")
@login_required
def dashboard():
    if current_user.is_admin:
        rows = db_get("""
            SELECT d.*, e.nombre AS empresa_nombre, hb.last_seen, hb.last_data
            FROM dispositivos d
            LEFT JOIN empresas e ON e.id = d.empresa_id
            LEFT JOIN device_heartbeats hb ON hb.device_id = d.device_id
            ORDER BY d.nombre
        """)
    else:
        rows = db_get("""
            SELECT d.*, e.nombre AS empresa_nombre, hb.last_seen, hb.last_data
            FROM dispositivos d
            LEFT JOIN empresas e ON e.id = d.empresa_id
            LEFT JOIN device_heartbeats hb ON hb.device_id = d.device_id
            INNER JOIN usuario_dispositivos ud
                ON ud.dispositivo_id = d.id AND ud.usuario_id = %s
            ORDER BY d.nombre
        """, (current_user.id,))

    now = datetime.utcnow()
    dispositivos = []
    for d in (rows or []):
        d = dict(d)
        online = False
        ultima_vez = None
        if d.get("last_seen"):
            ultima_vez = d["last_seen"]
            online = (now - ultima_vez).total_seconds() < 300
        d["online"] = online
        d["ultima_vez"] = ultima_vez
        dispositivos.append(d)

    return render_template("dashboard.html", dispositivos=dispositivos)

# ── Dispositivo detalle ────────────────────────────────────────────────────────

@app.get("/dispositivo/<int:device_id>")
@login_required
def dispositivo_detail(device_id):
    if current_user.is_admin:
        d = db_one("""
            SELECT d.*, e.nombre AS empresa_nombre
            FROM dispositivos d LEFT JOIN empresas e ON e.id = d.empresa_id
            WHERE d.id = %s
        """, (device_id,))
    else:
        d = db_one("""
            SELECT d.*, e.nombre AS empresa_nombre
            FROM dispositivos d
            LEFT JOIN empresas e ON e.id = d.empresa_id
            INNER JOIN usuario_dispositivos ud
                ON ud.dispositivo_id = d.id AND ud.usuario_id = %s
            WHERE d.id = %s
        """, (current_user.id, device_id))

    if not d:
        abort(404)

    hb = db_one("SELECT * FROM device_heartbeats WHERE device_id = %s", (d["device_id"],))
    nodo = db_one("SELECT * FROM nodos WHERE dispositivo_id = %s", (device_id,))
    now = datetime.utcnow()
    online = hb and (now - hb["last_seen"]).total_seconds() < 300

    last_data = {}
    if hb and hb.get("last_data"):
        try:
            last_data = hb["last_data"] if isinstance(hb["last_data"], dict) else json.loads(hb["last_data"])
        except Exception:
            pass

    return render_template("dispositivo.html", d=d, hb=hb, nodo=nodo,
                           online=online, last_data=last_data)

# ── API (ESP32) ────────────────────────────────────────────────────────────────

@app.get("/api/latest")
def latest():
    rows = db_get("SELECT * FROM device_heartbeats ORDER BY last_seen DESC LIMIT 1")
    return jsonify(dict(rows[0]) if rows else {})

@app.post("/ingest")
def ingest():
    data = request.get_json(silent=True) or {}
    if data.get("api_key") != API_KEY:
        return jsonify({"error": "unauthorized"}), 401
    device_id = data.get("device_id")
    if not device_id:
        return jsonify({"error": "missing device_id"}), 400
    payload = {k: v for k, v in data.items() if k not in ("api_key", "device_id")}
    db_run("""
        INSERT INTO device_heartbeats (device_id, last_seen, last_data)
        VALUES (%s, NOW(), %s)
        ON CONFLICT (device_id) DO UPDATE
        SET last_seen = NOW(), last_data = EXCLUDED.last_data
    """, (device_id, json.dumps(payload)))
    return jsonify({"ok": True}), 200

@app.get("/api/device/<device_id>/config")
def device_config_get(device_id):
    key = request.args.get("api_key") or request.headers.get("X-API-Key", "")
    if key != API_KEY:
        return jsonify({"error": "unauthorized"}), 401
    d = db_one("SELECT * FROM dispositivos WHERE device_id = %s", (device_id,))
    if not d:
        return jsonify({"error": "not found"}), 404
    sensores = []
    for i in range(1, 6):
        if d[f"tiene_sensor{i}"]:
            sensores.append({
                "num": i,
                "nombre": d[f"sensor{i}_nombre"],
                "factor": float(d[f"sensor{i}_factor"]) if d[f"sensor{i}_factor"] else 1.0,
            })
    config = {
        "device_id": device_id,
        "nombre": d["nombre"],
        "gps": d["tiene_gps"],
        "caudal": d["tiene_caudal"],
        "caudal_factor": float(d["caudal_factor"]) if d["caudal_factor"] else 1.0,
        "sensores": sensores,
        "maquina": d["tiene_maquina"],
        "maquina_ancho": float(d["maquina_ancho"]) if d["maquina_ancho"] else None,
    }
    return jsonify(config), 200

# ── Admin: redirect ────────────────────────────────────────────────────────────

@app.get("/admin")
@admin_required
def admin_index():
    return redirect(url_for("admin_usuarios"))

# ── Admin: Usuarios ────────────────────────────────────────────────────────────

@app.route("/admin/usuarios", methods=["GET", "POST"])
@admin_required
def admin_usuarios():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "crear":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            if not username or not password:
                flash("Usuario y contraseña son requeridos.", "error")
            else:
                try:
                    db_run("""
                        INSERT INTO usuarios
                            (username, password_hash, nombre, apellido, email, telefono,
                             zona_horaria, empresa_id, is_admin, comentarios)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (
                        username, generate_password_hash(password),
                        request.form.get("nombre", "").strip(),
                        request.form.get("apellido", "").strip(),
                        request.form.get("email", "").strip(),
                        request.form.get("telefono", "").strip(),
                        request.form.get("zona_horaria", "America/Argentina/Buenos_Aires"),
                        request.form.get("empresa_id") or None,
                        "is_admin" in request.form,
                        request.form.get("comentarios", "").strip(),
                    ))
                    flash("Usuario creado.", "success")
                except Exception as e:
                    flash(f"Error al crear usuario: {e}", "error")

        elif action == "editar":
            uid = request.form.get("id")
            new_pw = request.form.get("password", "").strip()
            if new_pw:
                db_run("""
                    UPDATE usuarios SET nombre=%s, apellido=%s, email=%s, telefono=%s,
                        zona_horaria=%s, empresa_id=%s, is_admin=%s, comentarios=%s,
                        password_hash=%s
                    WHERE id=%s
                """, (
                    request.form.get("nombre", "").strip(),
                    request.form.get("apellido", "").strip(),
                    request.form.get("email", "").strip(),
                    request.form.get("telefono", "").strip(),
                    request.form.get("zona_horaria", "America/Argentina/Buenos_Aires"),
                    request.form.get("empresa_id") or None,
                    "is_admin" in request.form,
                    request.form.get("comentarios", "").strip(),
                    generate_password_hash(new_pw), uid,
                ))
            else:
                db_run("""
                    UPDATE usuarios SET nombre=%s, apellido=%s, email=%s, telefono=%s,
                        zona_horaria=%s, empresa_id=%s, is_admin=%s, comentarios=%s
                    WHERE id=%s
                """, (
                    request.form.get("nombre", "").strip(),
                    request.form.get("apellido", "").strip(),
                    request.form.get("email", "").strip(),
                    request.form.get("telefono", "").strip(),
                    request.form.get("zona_horaria", "America/Argentina/Buenos_Aires"),
                    request.form.get("empresa_id") or None,
                    "is_admin" in request.form,
                    request.form.get("comentarios", "").strip(),
                    uid,
                ))
            flash("Usuario actualizado.", "success")

        elif action == "eliminar":
            uid = request.form.get("id")
            if int(uid) == current_user.id:
                flash("No podés eliminarte a vos mismo.", "error")
            else:
                db_run("DELETE FROM usuarios WHERE id=%s", (uid,))
                flash("Usuario eliminado.", "success")

        return redirect(url_for("admin_usuarios"))

    usuarios = db_get("""
        SELECT u.*, e.nombre AS empresa_nombre
        FROM usuarios u LEFT JOIN empresas e ON e.id = u.empresa_id
        ORDER BY u.username
    """)
    empresas = db_get("SELECT id, nombre FROM empresas ORDER BY nombre")
    return render_template("admin/usuarios.html", usuarios=usuarios, empresas=empresas)

# ── Admin: Empresas ────────────────────────────────────────────────────────────

@app.route("/admin/empresas", methods=["GET", "POST"])
@admin_required
def admin_empresas():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "crear":
            nombre = request.form.get("nombre", "").strip()
            if not nombre:
                flash("Nombre requerido.", "error")
            else:
                row = db_run_returning("""
                    INSERT INTO empresas (nombre, direccion, cuit, razon_social, pais, telefono)
                    VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
                """, (
                    nombre,
                    request.form.get("direccion", ""),
                    request.form.get("cuit", ""),
                    request.form.get("razon_social", ""),
                    request.form.get("pais", "Argentina"),
                    request.form.get("telefono", ""),
                ))
                eid = row["id"]
                for i in range(5):
                    puesto = request.form.get(f"cp_{i}", "").strip()
                    cnombre = request.form.get(f"cn_{i}", "").strip()
                    ctel = request.form.get(f"ct_{i}", "").strip()
                    cemail = request.form.get(f"ce_{i}", "").strip()
                    if puesto or cnombre:
                        db_run("""
                            INSERT INTO empresa_contactos (empresa_id, puesto, nombre, telefono, email)
                            VALUES (%s,%s,%s,%s,%s)
                        """, (eid, puesto, cnombre, ctel, cemail))
                flash("Empresa creada.", "success")

        elif action == "editar":
            eid = request.form.get("id")
            db_run("""
                UPDATE empresas SET nombre=%s, direccion=%s, cuit=%s, razon_social=%s, pais=%s, telefono=%s
                WHERE id=%s
            """, (
                request.form.get("nombre", ""),
                request.form.get("direccion", ""),
                request.form.get("cuit", ""),
                request.form.get("razon_social", ""),
                request.form.get("pais", ""),
                request.form.get("telefono", ""),
                eid,
            ))
            db_run("DELETE FROM empresa_contactos WHERE empresa_id=%s", (eid,))
            for i in range(10):
                puesto = request.form.get(f"cp_{i}", "").strip()
                cnombre = request.form.get(f"cn_{i}", "").strip()
                ctel = request.form.get(f"ct_{i}", "").strip()
                cemail = request.form.get(f"ce_{i}", "").strip()
                if puesto or cnombre:
                    db_run("""
                        INSERT INTO empresa_contactos (empresa_id, puesto, nombre, telefono, email)
                        VALUES (%s,%s,%s,%s,%s)
                    """, (eid, puesto, cnombre, ctel, cemail))
            flash("Empresa actualizada.", "success")

        elif action == "eliminar":
            db_run("DELETE FROM empresas WHERE id=%s", (request.form.get("id"),))
            flash("Empresa eliminada.", "success")

        return redirect(url_for("admin_empresas"))

    empresas = db_get("SELECT * FROM empresas ORDER BY nombre")
    contactos_raw = db_get("SELECT * FROM empresa_contactos ORDER BY empresa_id, id")
    contactos = {}
    for c in (contactos_raw or []):
        contactos.setdefault(c["empresa_id"], []).append(c)
    return render_template("admin/empresas.html", empresas=empresas, contactos=contactos)

# ── Admin: Nodos ───────────────────────────────────────────────────────────────

@app.route("/admin/nodos", methods=["GET", "POST"])
@admin_required
def admin_nodos():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "crear":
            imei = request.form.get("imei", "").strip()
            if not imei:
                flash("IMEI requerido.", "error")
            else:
                try:
                    row = db_run_returning("""
                        INSERT INTO nodos (imei, marca, modelo, firmware, fecha_compra,
                            fecha_instalacion, remito_instalacion, empresa_id, dispositivo_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
                    """, (
                        imei,
                        request.form.get("marca", ""),
                        request.form.get("modelo", ""),
                        request.form.get("firmware", ""),
                        request.form.get("fecha_compra") or None,
                        request.form.get("fecha_instalacion") or None,
                        request.form.get("remito_instalacion", ""),
                        request.form.get("empresa_id") or None,
                        request.form.get("dispositivo_id") or None,
                    ))
                    nid = row["id"]
                    for i in range(2):
                        comp = request.form.get(f"sim_comp_{i}", "").strip()
                        simei = request.form.get(f"sim_imei_{i}", "").strip()
                        if comp or simei:
                            db_run("INSERT INTO nodo_sims (nodo_id, compania, imei_sim) VALUES (%s,%s,%s)",
                                   (nid, comp, simei))
                    flash("Nodo creado.", "success")
                except Exception as e:
                    flash(f"Error: {e}", "error")

        elif action == "editar":
            nid = request.form.get("id")
            db_run("""
                UPDATE nodos SET imei=%s, marca=%s, modelo=%s, firmware=%s, fecha_compra=%s,
                    fecha_instalacion=%s, remito_instalacion=%s, empresa_id=%s, dispositivo_id=%s
                WHERE id=%s
            """, (
                request.form.get("imei", ""),
                request.form.get("marca", ""),
                request.form.get("modelo", ""),
                request.form.get("firmware", ""),
                request.form.get("fecha_compra") or None,
                request.form.get("fecha_instalacion") or None,
                request.form.get("remito_instalacion", ""),
                request.form.get("empresa_id") or None,
                request.form.get("dispositivo_id") or None,
                nid,
            ))
            db_run("DELETE FROM nodo_sims WHERE nodo_id=%s", (nid,))
            for i in range(2):
                comp = request.form.get(f"sim_comp_{i}", "").strip()
                simei = request.form.get(f"sim_imei_{i}", "").strip()
                if comp or simei:
                    db_run("INSERT INTO nodo_sims (nodo_id, compania, imei_sim) VALUES (%s,%s,%s)",
                           (nid, comp, simei))
            flash("Nodo actualizado.", "success")

        elif action == "eliminar":
            db_run("DELETE FROM nodos WHERE id=%s", (request.form.get("id"),))
            flash("Nodo eliminado.", "success")

        return redirect(url_for("admin_nodos"))

    nodos = db_get("""
        SELECT n.*, e.nombre AS empresa_nombre, d.nombre AS dispositivo_nombre
        FROM nodos n
        LEFT JOIN empresas e ON e.id = n.empresa_id
        LEFT JOIN dispositivos d ON d.id = n.dispositivo_id
        ORDER BY n.created_at DESC
    """)
    sims_raw = db_get("SELECT * FROM nodo_sims ORDER BY nodo_id, id")
    sims = {}
    for s in (sims_raw or []):
        sims.setdefault(s["nodo_id"], []).append(s)
    empresas = db_get("SELECT id, nombre FROM empresas ORDER BY nombre")
    dispositivos = db_get("SELECT id, nombre, device_id FROM dispositivos ORDER BY nombre")
    return render_template("admin/nodos.html", nodos=nodos, sims=sims,
                           empresas=empresas, dispositivos=dispositivos)

# ── Admin: Dispositivos ────────────────────────────────────────────────────────

def _parse_device_form():
    f = request.form
    return (
        f.get("empresa_id") or None,
        f.get("nombre", "").strip(),
        f.get("device_id", "").strip(),
        f.get("icon", "fa-microchip"),
        "tiene_gps" in f,
        "tiene_caudal" in f, f.get("caudal_factor") or None,
        "tiene_sensor1" in f, f.get("sensor1_nombre",""), f.get("sensor1_icon",""), f.get("sensor1_factor") or None,
        "tiene_sensor2" in f, f.get("sensor2_nombre",""), f.get("sensor2_icon",""), f.get("sensor2_factor") or None,
        "tiene_sensor3" in f, f.get("sensor3_nombre",""), f.get("sensor3_icon",""), f.get("sensor3_factor") or None,
        "tiene_sensor4" in f, f.get("sensor4_nombre",""), f.get("sensor4_icon",""), f.get("sensor4_factor") or None,
        "tiene_sensor5" in f, f.get("sensor5_nombre",""), f.get("sensor5_icon",""), f.get("sensor5_factor") or None,
        "tiene_maquina" in f, f.get("maquina_ancho") or None,
    )

@app.route("/admin/dispositivos", methods=["GET", "POST"])
@admin_required
def admin_dispositivos():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "crear":
            params = _parse_device_form()
            if not params[1] or not params[2]:
                flash("Nombre y Device ID son requeridos.", "error")
            else:
                try:
                    db_run("""
                        INSERT INTO dispositivos
                            (empresa_id, nombre, device_id, icon,
                             tiene_gps, tiene_caudal, caudal_factor,
                             tiene_sensor1, sensor1_nombre, sensor1_icon, sensor1_factor,
                             tiene_sensor2, sensor2_nombre, sensor2_icon, sensor2_factor,
                             tiene_sensor3, sensor3_nombre, sensor3_icon, sensor3_factor,
                             tiene_sensor4, sensor4_nombre, sensor4_icon, sensor4_factor,
                             tiene_sensor5, sensor5_nombre, sensor5_icon, sensor5_factor,
                             tiene_maquina, maquina_ancho)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, params)
                    flash("Dispositivo creado.", "success")
                except Exception as e:
                    flash(f"Error: {e}", "error")

        elif action == "editar":
            did = request.form.get("id")
            params = _parse_device_form()
            db_run("""
                UPDATE dispositivos SET
                    empresa_id=%s, nombre=%s, device_id=%s, icon=%s,
                    tiene_gps=%s, tiene_caudal=%s, caudal_factor=%s,
                    tiene_sensor1=%s, sensor1_nombre=%s, sensor1_icon=%s, sensor1_factor=%s,
                    tiene_sensor2=%s, sensor2_nombre=%s, sensor2_icon=%s, sensor2_factor=%s,
                    tiene_sensor3=%s, sensor3_nombre=%s, sensor3_icon=%s, sensor3_factor=%s,
                    tiene_sensor4=%s, sensor4_nombre=%s, sensor4_icon=%s, sensor4_factor=%s,
                    tiene_sensor5=%s, sensor5_nombre=%s, sensor5_icon=%s, sensor5_factor=%s,
                    tiene_maquina=%s, maquina_ancho=%s
                WHERE id=%s
            """, params + (did,))
            flash("Dispositivo actualizado.", "success")

        elif action == "eliminar":
            db_run("DELETE FROM dispositivos WHERE id=%s", (request.form.get("id"),))
            flash("Dispositivo eliminado.", "success")

        elif action == "permisos":
            uid = request.form.get("usuario_id")
            dids = request.form.getlist("dispositivos")
            db_run("DELETE FROM usuario_dispositivos WHERE usuario_id=%s", (uid,))
            for did in dids:
                db_run("INSERT INTO usuario_dispositivos (usuario_id, dispositivo_id) VALUES (%s,%s)",
                       (uid, did))
            flash("Permisos actualizados.", "success")

        return redirect(url_for("admin_dispositivos"))

    dispositivos = db_get("""
        SELECT d.*, e.nombre AS empresa_nombre
        FROM dispositivos d LEFT JOIN empresas e ON e.id = d.empresa_id
        ORDER BY d.nombre
    """)
    empresas = db_get("SELECT id, nombre FROM empresas ORDER BY nombre")
    usuarios = db_get("""
        SELECT id, username, nombre, apellido FROM usuarios
        WHERE NOT is_admin ORDER BY username
    """)
    permisos_raw = db_get("SELECT * FROM usuario_dispositivos")
    permisos = {}
    for p in (permisos_raw or []):
        permisos.setdefault(p["usuario_id"], []).append(p["dispositivo_id"])
    return render_template("admin/dispositivos.html", dispositivos=dispositivos,
                           empresas=empresas, usuarios=usuarios, permisos=permisos)

# ── Admin: Estados ─────────────────────────────────────────────────────────────

@app.route("/admin/estados", methods=["GET", "POST"])
@admin_required
def admin_estados():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "crear":
            nombre = request.form.get("nombre", "").strip()
            if not nombre:
                flash("Nombre requerido.", "error")
            else:
                db_run("INSERT INTO estados (nombre, color, es_trabajo) VALUES (%s,%s,%s)",
                       (nombre, request.form.get("color", "#3498db"), "es_trabajo" in request.form))
                flash("Estado creado.", "success")
        elif action == "editar":
            db_run("UPDATE estados SET nombre=%s, color=%s, es_trabajo=%s WHERE id=%s",
                   (request.form.get("nombre","").strip(),
                    request.form.get("color","#3498db"),
                    "es_trabajo" in request.form,
                    request.form.get("id")))
            flash("Estado actualizado.", "success")
        elif action == "eliminar":
            db_run("DELETE FROM estados WHERE id=%s", (request.form.get("id"),))
            flash("Estado eliminado.", "success")
        return redirect(url_for("admin_estados"))

    estados = db_get("SELECT * FROM estados ORDER BY nombre")
    return render_template("admin/estados.html", estados=estados)

# ── Admin: Configuraciones ─────────────────────────────────────────────────────

@app.route("/admin/configuraciones", methods=["GET", "POST"])
@admin_required
def admin_configuraciones():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "crear":
            nombre = request.form.get("nombre", "").strip()
            if not nombre:
                flash("Nombre requerido.", "error")
            else:
                db_run("INSERT INTO configuraciones (nombre) VALUES (%s)", (nombre,))
                flash("Configuración creada.", "success")
        elif action == "eliminar":
            db_run("DELETE FROM configuraciones WHERE id=%s", (request.form.get("id"),))
            flash("Configuración eliminada.", "success")
        return redirect(url_for("admin_configuraciones"))

    configs = db_get("""
        SELECT c.*, COUNT(ce.id) AS num_estados
        FROM configuraciones c
        LEFT JOIN configuracion_estados ce ON ce.configuracion_id = c.id
        GROUP BY c.id ORDER BY c.nombre
    """)
    return render_template("admin/configuraciones.html", configs=configs)

@app.route("/admin/configuraciones/<int:cid>/editar", methods=["GET", "POST"])
@admin_required
def admin_configuracion_edit(cid):
    config = db_one("SELECT * FROM configuraciones WHERE id=%s", (cid,))
    if not config:
        abort(404)

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        if nombre:
            db_run("UPDATE configuraciones SET nombre=%s WHERE id=%s", (nombre, cid))

        db_run("DELETE FROM configuracion_estados WHERE configuracion_id=%s", (cid,))
        estado_ids = request.form.getlist("estado_id")
        for idx, eid in enumerate(estado_ids):
            if not eid:
                continue
            db_run("""
                INSERT INTO configuracion_estados (
                    configuracion_id, estado_id, orden,
                    bandera1, bandera2, bandera3, bandera4,
                    bandera5, bandera6, bandera7, bandera8,
                    velocidad_activa, velocidad_min, velocidad_max,
                    sensor1_activa, sensor1_min, sensor1_max,
                    sensor2_activa, sensor2_min, sensor2_max,
                    sensor3_activa, sensor3_min, sensor3_max
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                cid, eid, idx,
                f"b1_{idx}" in request.form, f"b2_{idx}" in request.form,
                f"b3_{idx}" in request.form, f"b4_{idx}" in request.form,
                f"b5_{idx}" in request.form, f"b6_{idx}" in request.form,
                f"b7_{idx}" in request.form, f"b8_{idx}" in request.form,
                f"vel_activa_{idx}" in request.form,
                request.form.get(f"vel_min_{idx}") or None,
                request.form.get(f"vel_max_{idx}") or None,
                f"s1_activa_{idx}" in request.form,
                request.form.get(f"s1_min_{idx}") or None,
                request.form.get(f"s1_max_{idx}") or None,
                f"s2_activa_{idx}" in request.form,
                request.form.get(f"s2_min_{idx}") or None,
                request.form.get(f"s2_max_{idx}") or None,
                f"s3_activa_{idx}" in request.form,
                request.form.get(f"s3_min_{idx}") or None,
                request.form.get(f"s3_max_{idx}") or None,
            ))
        flash("Configuración guardada.", "success")
        return redirect(url_for("admin_configuracion_edit", cid=cid))

    config_estados = db_get("""
        SELECT ce.*, e.nombre AS estado_nombre, e.color
        FROM configuracion_estados ce
        JOIN estados e ON e.id = ce.estado_id
        WHERE ce.configuracion_id = %s
        ORDER BY ce.orden
    """, (cid,))
    estados_disponibles = db_get("SELECT * FROM estados ORDER BY nombre")
    return render_template("admin/configuracion_edit.html",
                           config=config, config_estados=config_estados,
                           estados_disponibles=estados_disponibles)

# ── Context processor ──────────────────────────────────────────────────────────

@app.context_processor
def inject_globals():
    return {"current_year": datetime.now().year}

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, msg="Acceso denegado."), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, msg="Página no encontrada."), 404

@app.errorhandler(500)
def server_error(e):
    import traceback
    tb = traceback.format_exc()
    return f"<pre style='padding:20px;font-size:13px'><b>500 Error:</b> {e}\n\n{tb}</pre>", 500

# ── Startup ────────────────────────────────────────────────────────────────────

with app.app_context():
    if DATABASE_URL:
        try:
            init_db()
        except Exception as e:
            import traceback
            print(f"[WARNING] init_db falló: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
