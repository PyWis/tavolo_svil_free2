#!/usr/bin/env python3
"""
Tavolò - Web App per la gestione del menu di un ristorante.
Al primo avvio viene richiesto di creare l'utente admin da CLI.
"""

import os
import io
import csv
import uuid
import sqlite3
import secrets
import getpass
import functools
from datetime import timedelta, datetime
import qrcode
import qrcode.constants
from PIL import Image, UnidentifiedImageError
from werkzeug.security import generate_password_hash, check_password_hash
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, g, jsonify, send_file, abort
)
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ─── App Setup ───────────────────────────────────────────────────────────────

app = Flask(__name__)


def _load_or_create_secret_key() -> bytes:
    """Persistent secret key so sessions survive restarts and multi-worker setups.

    Priority:
      1. FLASK_SECRET_KEY env var (raccomandato in produzione).
      2. File `.secret_key` accanto all'app (generato al primo avvio, 0600).
    """
    env_key = os.environ.get("FLASK_SECRET_KEY")
    if env_key:
        return env_key.encode("utf-8")
    key_path = os.path.join(os.path.dirname(__file__), ".secret_key")
    if os.path.isfile(key_path):
        with open(key_path, "rb") as f:
            return f.read().strip()
    key = secrets.token_hex(32).encode("utf-8")
    with open(key_path, "wb") as f:
        f.write(key)
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return key


app.secret_key = _load_or_create_secret_key()
app.permanent_session_lifetime = timedelta(hours=8)

# ─── Session / Cookie Hardening ─────────────────────────────────────────────
# SESSION_COOKIE_SECURE richiede HTTPS — attivabile via env per produzione.
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
    WTF_CSRF_TIME_LIMIT=None,  # token valido per tutta la sessione
)

# ─── CSRF Protection ────────────────────────────────────────────────────────
csrf = CSRFProtect(app)


@app.errorhandler(CSRFError)
def _handle_csrf_error(e):
    flash("Sessione scaduta o richiesta non valida. Riprova.", "danger")
    return redirect(request.referrer or url_for("index")), 400


# ─── Rate Limiting ──────────────────────────────────────────────────────────
# In-memory va bene per istanza singola (tipico deploy "free"). Per multi-worker
# impostare RATELIMIT_STORAGE_URI a es. "redis://localhost:6379".
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
)


DB_PATH = os.path.join(os.path.dirname(__file__), "restaurant.db")

# URL base pubblico per i QR code. Se non impostato ricade su request.host_url
# (attenzione: host header poisoning se non dietro reverse proxy fidato).
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

# ─── Upload Configuration ────────────────────────────────────────────────────
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads", "dishes")
ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
PIL_FORMATS_BY_EXT = {
    "png": {"PNG"},
    "jpg": {"JPEG"},
    "jpeg": {"JPEG"},
    "gif": {"GIF"},
    "webp": {"WEBP"},
}
MAX_IMAGE_BYTES = 4 * 1024 * 1024  # 4 MB

ARCHIVE_FOLDER = os.path.join(os.path.dirname(__file__), "archives")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ARCHIVE_FOLDER, exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_BYTES + 1024  # margin for form fields

def _allowed_image(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXT

def _save_dish_image(file_storage):
    """Save an uploaded dish image and return the relative path stored in DB.
    Returns None if no file was uploaded.

    Valida il contenuto reale del file con Pillow: impedisce che un eseguibile
    rinominato `.jpg` venga salvato nella cartella statica.
    """
    if not file_storage or not file_storage.filename:
        return None
    if not _allowed_image(file_storage.filename):
        raise ValueError("Formato immagine non supportato. Usa PNG, JPG, GIF o WEBP.")
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    # Verifica che lo stream sia davvero un'immagine del formato dichiarato
    try:
        file_storage.stream.seek(0)
        with Image.open(file_storage.stream) as img:
            img.verify()
            detected = (img.format or "").upper()
    except UnidentifiedImageError:
        raise ValueError("Il file caricato non è un'immagine valida.")
    except Exception:
        raise ValueError("File immagine non valido.")
    if detected not in PIL_FORMATS_BY_EXT.get(ext, set()):
        raise ValueError("Il contenuto del file non corrisponde all'estensione.")
    file_storage.stream.seek(0)
    fname = f"{uuid.uuid4().hex}.{ext}"
    abs_path = os.path.join(UPLOAD_FOLDER, fname)
    file_storage.save(abs_path)
    # Path relative to /static for use with url_for('static', filename=...)
    return f"uploads/dishes/{fname}"

def _delete_dish_image(rel_path: str | None):
    if not rel_path:
        return
    abs_path = os.path.join(os.path.dirname(__file__), "static", rel_path)
    try:
        if os.path.isfile(abs_path):
            os.remove(abs_path)
    except OSError:
        pass

# ─── Limiti Versione Free ───────────────────────────────────────────────────
MAX_MENU_ITEMS = 50
MAX_CATEGORIES = 5
MAX_USERS = 3
MAX_TABLES = 20

@app.context_processor
def inject_limits():
    return dict(
        MAX_MENU_ITEMS=MAX_MENU_ITEMS,
        MAX_CATEGORIES=MAX_CATEGORIES,
        MAX_USERS=MAX_USERS,
        MAX_TABLES=MAX_TABLES,
    )

# ─── Mappatura stati ordine (IT) ────────────────────────────────────────────
ORDER_STATUS_IT = {
    "pending":   "In attesa",
    "confirmed": "Confermato",
    "preparing": "In preparazione",
    "ready":     "Pronto",
    "completed": "Completato",
    "cancelled": "Annullato",
    "all":       "Tutti",
}

@app.context_processor
def inject_status_labels():
    return dict(ORDER_STATUS_IT=ORDER_STATUS_IT)

@app.template_filter("status_it")
def status_it_filter(value: str) -> str:
    return ORDER_STATUS_IT.get(value, value)

# ─── Database ────────────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            ingredients TEXT,
            description TEXT,
            price REAL NOT NULL,
            visible INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            image_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            number INTEGER UNIQUE NOT NULL CHECK(number >= 1 AND number <= 99),
            name TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (table_id) REFERENCES tables(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            menu_item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (menu_item_id) REFERENCES menu_items(id) ON DELETE CASCADE
        );
    """)
    # Lightweight migration: add image_path column on pre-existing DBs
    cols = {row[1] for row in db.execute("PRAGMA table_info(menu_items)").fetchall()}
    if "image_path" not in cols:
        db.execute("ALTER TABLE menu_items ADD COLUMN image_path TEXT")
    db.commit()
    db.close()

# ─── Security Headers ────────────────────────────────────────────────────────

@app.after_request
def _set_security_headers(resp):
    # X-Frame-Options: blocca il clickjacking sull'admin
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    # CSP compatibile col codice inline presente (Jinja scrive <style> e <script> inline).
    # 'unsafe-inline' è necessario perché base.html ha <style> e <script> inline;
    # se/quando si esterneranno gli asset conviene rimuoverlo.
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    if app.config.get("SESSION_COOKIE_SECURE"):
        resp.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains"
        )
    return resp


# ─── Auth Helpers ────────────────────────────────────────────────────────────

MIN_PASSWORD_LEN = 10


def _password_policy_error(pw: str):
    """Restituisce None se la password rispetta la policy, altrimenti messaggio."""
    if len(pw) < MIN_PASSWORD_LEN:
        return f"La password deve avere almeno {MIN_PASSWORD_LEN} caratteri."
    classes = 0
    if any(c.islower() for c in pw): classes += 1
    if any(c.isupper() for c in pw): classes += 1
    if any(c.isdigit() for c in pw): classes += 1
    if any(not c.isalnum() for c in pw): classes += 1
    if classes < 3:
        return "La password deve contenere almeno 3 tra: minuscole, maiuscole, numeri, simboli."
    return None


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Effettua il login per continuare.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Effettua il login per continuare.", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Accesso riservato all'amministratore.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated

@app.context_processor
def inject_user():
    user = None
    if "user_id" in session:
        user = {"id": session["user_id"], "username": session["username"], "role": session["role"]}
    return dict(current_user=user)

# ─── Public Routes ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Public menu page."""
    db = get_db()
    categories = db.execute(
        "SELECT * FROM categories ORDER BY sort_order, name"
    ).fetchall()
    items_by_cat = {}
    for cat in categories:
        items = db.execute(
            "SELECT * FROM menu_items WHERE category_id = ? AND visible = 1 ORDER BY sort_order, title",
            (cat["id"],)
        ).fetchall()
        if items:
            items_by_cat[cat["id"]] = items
    return render_template("public_menu.html", categories=categories, items_by_cat=items_by_cat)

# ─── Auth Routes ─────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute; 50 per hour", methods=["POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            # Mitiga session fixation: nuovo SID dopo login
            session.clear()
            session.permanent = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash(f"Benvenuto, {user['username']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Credenziali non valide.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logout effettuato.", "info")
    return redirect(url_for("index"))

# ─── Dashboard ───────────────────────────────────────────────────────────────

@app.route("/admin")
@login_required
def dashboard():
    db = get_db()
    cat_count = db.execute("SELECT COUNT(*) c FROM categories").fetchone()["c"]
    item_count = db.execute("SELECT COUNT(*) c FROM menu_items").fetchone()["c"]
    table_count = db.execute("SELECT COUNT(*) c FROM tables WHERE active = 1").fetchone()["c"]
    table_total = db.execute("SELECT COUNT(*) c FROM tables").fetchone()["c"]
    user_count = db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    pending_orders = db.execute("SELECT COUNT(*) c FROM orders WHERE status = 'pending'").fetchone()["c"]
    return render_template("dashboard.html", cat_count=cat_count, item_count=item_count,
                           table_count=table_count, table_total=table_total,
                           user_count=user_count, pending_orders=pending_orders)

# ─── User Management (admin only) ───────────────────────────────────────────

@app.route("/admin/users")
@admin_required
def users_list():
    db = get_db()
    users = db.execute("SELECT * FROM users ORDER BY role DESC, username").fetchall()
    return render_template("users.html", users=users)

@app.route("/admin/users/create", methods=["GET", "POST"])
@admin_required
def user_create():
    db = get_db()
    user_count = db.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    if user_count >= MAX_USERS:
        flash(f"Limite massimo raggiunto: puoi creare al massimo {MAX_USERS} utenti nella versione free.", "danger")
        return redirect(url_for("users_list"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        pw_err = _password_policy_error(password)
        if not username or not password:
            flash("Username e password sono obbligatori.", "danger")
        elif len(username) > 64 or not all(c.isalnum() or c in "._-" for c in username):
            flash("Username non valido (max 64 caratteri, alfanumerici, '.', '_', '-').", "danger")
        elif pw_err:
            flash(pw_err, "danger")
        else:
            try:
                db.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'user')",
                    (username, generate_password_hash(password))
                )
                db.commit()
                flash(f"Utente '{username}' creato con successo.", "success")
                return redirect(url_for("users_list"))
            except sqlite3.IntegrityError:
                flash("Username già esistente.", "danger")
    return render_template("user_form.html", editing=False)

@app.route("/admin/users/<int:uid>/delete", methods=["POST"])
@admin_required
def user_delete(uid):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    if not user:
        flash("Utente non trovato.", "danger")
    elif user["role"] == "admin":
        flash("Non puoi eliminare l'amministratore.", "danger")
    else:
        db.execute("DELETE FROM users WHERE id = ?", (uid,))
        db.commit()
        flash("Utente eliminato.", "success")
    return redirect(url_for("users_list"))

@app.route("/admin/users/<int:uid>/reset-password", methods=["POST"])
@admin_required
def user_reset_password(uid):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    if not user:
        flash("Utente non trovato.", "danger")
        return redirect(url_for("users_list"))
    new_pw = request.form.get("new_password", "")
    pw_err = _password_policy_error(new_pw)
    if pw_err:
        flash(pw_err, "danger")
    else:
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                   (generate_password_hash(new_pw), uid))
        db.commit()
        flash(f"Password di '{user['username']}' reimpostata.", "success")
    return redirect(url_for("users_list"))

# ─── Category CRUD ───────────────────────────────────────────────────────────

@app.route("/admin/categories")
@login_required
def categories_list():
    db = get_db()
    cats = db.execute("SELECT c.*, COUNT(m.id) as item_count FROM categories c LEFT JOIN menu_items m ON m.category_id = c.id GROUP BY c.id ORDER BY c.sort_order, c.name").fetchall()
    return render_template("categories.html", categories=cats)

@app.route("/admin/categories/create", methods=["GET", "POST"])
@login_required
def category_create():
    db = get_db()
    cat_count = db.execute("SELECT COUNT(*) c FROM categories").fetchone()["c"]
    if cat_count >= MAX_CATEGORIES:
        flash(f"Limite massimo raggiunto: puoi creare al massimo {MAX_CATEGORIES} categorie nella versione free.", "danger")
        return redirect(url_for("categories_list"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sort_order = request.form.get("sort_order", 0, type=int)
        if not name:
            flash("Il nome della categoria è obbligatorio.", "danger")
        else:
            try:
                db.execute("INSERT INTO categories (name, sort_order) VALUES (?, ?)", (name, sort_order))
                db.commit()
                flash(f"Categoria '{name}' creata.", "success")
                return redirect(url_for("categories_list"))
            except sqlite3.IntegrityError:
                flash("Categoria già esistente.", "danger")
    return render_template("category_form.html", category=None)

@app.route("/admin/categories/<int:cid>/edit", methods=["GET", "POST"])
@login_required
def category_edit(cid):
    db = get_db()
    cat = db.execute("SELECT * FROM categories WHERE id = ?", (cid,)).fetchone()
    if not cat:
        flash("Categoria non trovata.", "danger")
        return redirect(url_for("categories_list"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sort_order = request.form.get("sort_order", 0, type=int)
        if not name:
            flash("Il nome è obbligatorio.", "danger")
        else:
            try:
                db.execute("UPDATE categories SET name=?, sort_order=? WHERE id=?", (name, sort_order, cid))
                db.commit()
                flash("Categoria aggiornata.", "success")
                return redirect(url_for("categories_list"))
            except sqlite3.IntegrityError:
                flash("Nome categoria già in uso.", "danger")
    return render_template("category_form.html", category=cat)

@app.route("/admin/categories/<int:cid>/delete", methods=["POST"])
@admin_required
def category_delete(cid):
    db = get_db()
    db.execute("DELETE FROM categories WHERE id = ?", (cid,))
    db.commit()
    flash("Categoria eliminata (e tutti i piatti associati).", "success")
    return redirect(url_for("categories_list"))

# ─── Menu Item CRUD ──────────────────────────────────────────────────────────

@app.route("/admin/menu")
@login_required
def menu_list():
    db = get_db()
    items = db.execute("""
        SELECT m.*, c.name as category_name
        FROM menu_items m JOIN categories c ON m.category_id = c.id
        ORDER BY c.sort_order, c.name, m.sort_order, m.title
    """).fetchall()
    return render_template("menu_list.html", items=items)

@app.route("/admin/menu/create", methods=["GET", "POST"])
@login_required
def menu_item_create():
    db = get_db()
    item_count = db.execute("SELECT COUNT(*) c FROM menu_items").fetchone()["c"]
    if item_count >= MAX_MENU_ITEMS:
        flash(f"Limite massimo raggiunto: puoi creare al massimo {MAX_MENU_ITEMS} piatti nella versione free.", "danger")
        return redirect(url_for("menu_list"))
    categories = db.execute("SELECT * FROM categories ORDER BY sort_order, name").fetchall()
    if not categories:
        flash("Crea prima almeno una categoria.", "warning")
        return redirect(url_for("category_create"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        ingredients = request.form.get("ingredients", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", 0, type=float)
        category_id = request.form.get("category_id", 0, type=int)
        visible = 1 if request.form.get("visible") else 0
        sort_order = request.form.get("sort_order", 0, type=int)
        if not title or price < 0 or not category_id:
            flash("Titolo, categoria e prezzo sono obbligatori.", "danger")
        else:
            try:
                image_path = _save_dish_image(request.files.get("image"))
            except ValueError as e:
                flash(str(e), "danger")
                return render_template("menu_form.html", item=None, categories=categories)
            db.execute(
                "INSERT INTO menu_items (category_id, title, ingredients, description, price, visible, sort_order, image_path) VALUES (?,?,?,?,?,?,?,?)",
                (category_id, title, ingredients, description, price, visible, sort_order, image_path)
            )
            db.commit()
            flash(f"Piatto '{title}' aggiunto.", "success")
            return redirect(url_for("menu_list"))
    return render_template("menu_form.html", item=None, categories=categories)

@app.route("/admin/menu/<int:mid>/edit", methods=["GET", "POST"])
@login_required
def menu_item_edit(mid):
    db = get_db()
    item = db.execute("SELECT * FROM menu_items WHERE id = ?", (mid,)).fetchone()
    if not item:
        flash("Piatto non trovato.", "danger")
        return redirect(url_for("menu_list"))
    categories = db.execute("SELECT * FROM categories ORDER BY sort_order, name").fetchall()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        ingredients = request.form.get("ingredients", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", 0, type=float)
        category_id = request.form.get("category_id", 0, type=int)
        visible = 1 if request.form.get("visible") else 0
        sort_order = request.form.get("sort_order", 0, type=int)
        remove_image = bool(request.form.get("remove_image"))
        if not title or price < 0 or not category_id:
            flash("Titolo, categoria e prezzo sono obbligatori.", "danger")
        else:
            current_image = item["image_path"]
            new_image_path = current_image
            try:
                uploaded = _save_dish_image(request.files.get("image"))
            except ValueError as e:
                flash(str(e), "danger")
                return render_template("menu_form.html", item=item, categories=categories)
            if uploaded:
                _delete_dish_image(current_image)
                new_image_path = uploaded
            elif remove_image:
                _delete_dish_image(current_image)
                new_image_path = None
            db.execute(
                "UPDATE menu_items SET category_id=?, title=?, ingredients=?, description=?, price=?, visible=?, sort_order=?, image_path=? WHERE id=?",
                (category_id, title, ingredients, description, price, visible, sort_order, new_image_path, mid)
            )
            db.commit()
            flash("Piatto aggiornato.", "success")
            return redirect(url_for("menu_list"))
    return render_template("menu_form.html", item=item, categories=categories)

@app.route("/admin/menu/<int:mid>/delete", methods=["POST"])
@admin_required
def menu_item_delete(mid):
    db = get_db()
    item = db.execute("SELECT image_path FROM menu_items WHERE id = ?", (mid,)).fetchone()
    db.execute("DELETE FROM menu_items WHERE id = ?", (mid,))
    db.commit()
    if item:
        _delete_dish_image(item["image_path"])
    flash("Piatto eliminato.", "success")
    return redirect(url_for("menu_list"))

@app.route("/admin/menu/<int:mid>/toggle", methods=["POST"])
@login_required
def menu_item_toggle(mid):
    db = get_db()
    db.execute("UPDATE menu_items SET visible = CASE WHEN visible=1 THEN 0 ELSE 1 END WHERE id=?", (mid,))
    db.commit()
    return redirect(url_for("menu_list"))

# ─── Table Management (admin) ───────────────────────────────────────────────

@app.route("/admin/tables")
@login_required
def tables_list():
    db = get_db()
    tables = db.execute("""
        SELECT t.*, COUNT(o.id) as order_count
        FROM tables t
        LEFT JOIN orders o ON o.table_id = t.id AND o.status = 'pending'
        GROUP BY t.id
        ORDER BY t.number
    """).fetchall()
    return render_template("tables.html", tables=tables)

@app.route("/admin/tables/create", methods=["GET", "POST"])
@login_required
def table_create():
    db = get_db()
    table_count = db.execute("SELECT COUNT(*) c FROM tables").fetchone()["c"]
    if table_count >= MAX_TABLES:
        flash(f"Limite massimo raggiunto: puoi creare al massimo {MAX_TABLES} tavoli nella versione free.", "danger")
        return redirect(url_for("tables_list"))
    if request.method == "POST":
        number = request.form.get("number", 0, type=int)
        name = request.form.get("name", "").strip()
        if number < 1 or number > 99:
            flash("Il numero del tavolo deve essere tra 1 e 99.", "danger")
        else:
            try:
                db.execute(
                    "INSERT INTO tables (number, name) VALUES (?, ?)",
                    (number, name or None)
                )
                db.commit()
                flash(f"Tavolo {number} creato.", "success")
                return redirect(url_for("tables_list"))
            except sqlite3.IntegrityError:
                flash(f"Il tavolo {number} esiste già.", "danger")
    return render_template("table_form.html", table=None)

@app.route("/admin/tables/<int:tid>/edit", methods=["GET", "POST"])
@login_required
def table_edit(tid):
    db = get_db()
    table = db.execute("SELECT * FROM tables WHERE id = ?", (tid,)).fetchone()
    if not table:
        flash("Tavolo non trovato.", "danger")
        return redirect(url_for("tables_list"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        active = 1 if request.form.get("active") else 0
        db.execute("UPDATE tables SET name=?, active=? WHERE id=?", (name or None, active, tid))
        db.commit()
        flash("Tavolo aggiornato.", "success")
        return redirect(url_for("tables_list"))
    return render_template("table_form.html", table=table)

@app.route("/admin/tables/<int:tid>/delete", methods=["POST"])
@admin_required
def table_delete(tid):
    db = get_db()
    db.execute("DELETE FROM tables WHERE id = ?", (tid,))
    db.commit()
    flash("Tavolo eliminato.", "success")
    return redirect(url_for("tables_list"))

@app.route("/admin/tables/<int:tid>/toggle", methods=["POST"])
@login_required
def table_toggle(tid):
    db = get_db()
    db.execute("UPDATE tables SET active = CASE WHEN active=1 THEN 0 ELSE 1 END WHERE id=?", (tid,))
    db.commit()
    return redirect(url_for("tables_list"))

# ─── QR Code Generation ────────────────────────────────────────────────────

@app.route("/admin/tables/<int:tid>/qr")
@login_required
def table_qr(tid):
    db = get_db()
    table = db.execute("SELECT * FROM tables WHERE id = ?", (tid,)).fetchone()
    if not table:
        flash("Tavolo non trovato.", "danger")
        return redirect(url_for("tables_list"))
    base_url = PUBLIC_BASE_URL or request.host_url.rstrip("/")
    table_url = f"{base_url}/tavolo/{table['number']}"
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(table_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#e66b1d", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", download_name=f"tavolo_{table['number']}_qr.png")

@app.route("/admin/tables/qr-all")
@login_required
def tables_qr_all():
    """Page to view/print all QR codes at once."""
    db = get_db()
    tables = db.execute("SELECT * FROM tables WHERE active = 1 ORDER BY number").fetchall()
    base_url = PUBLIC_BASE_URL or request.host_url.rstrip("/")
    return render_template("tables_qr_print.html", tables=tables, base_url=base_url)

# ─── Public Table Ordering ──────────────────────────────────────────────────

@app.route("/tavolo/<int:number>")
def table_order(number):
    db = get_db()
    table = db.execute("SELECT * FROM tables WHERE number = ? AND active = 1", (number,)).fetchone()
    if not table:
        flash("Tavolo non disponibile.", "danger")
        return redirect(url_for("index"))
    categories = db.execute("SELECT * FROM categories ORDER BY sort_order, name").fetchall()
    items_by_cat = {}
    for cat in categories:
        items = db.execute(
            "SELECT * FROM menu_items WHERE category_id = ? AND visible = 1 ORDER BY sort_order, title",
            (cat["id"],)
        ).fetchall()
        if items:
            items_by_cat[cat["id"]] = items
    return render_template("table_order.html", table=table, categories=categories, items_by_cat=items_by_cat)

MAX_QTY_PER_ITEM = 20
MAX_ITEMS_PER_ORDER = 50
MAX_ORDER_NOTE_LEN = 500
MAX_ITEM_NOTE_LEN = 200


@app.route("/tavolo/<int:number>/ordina", methods=["POST"])
@limiter.limit("5 per minute; 30 per hour")
def table_submit_order(number):
    db = get_db()
    table = db.execute("SELECT * FROM tables WHERE number = ? AND active = 1", (number,)).fetchone()
    if not table:
        flash("Tavolo non disponibile.", "danger")
        return redirect(url_for("index"))
    # ID dei piatti effettivamente disponibili: filtra ID inesistenti/nascosti
    valid_ids = {
        row["id"] for row in db.execute(
            "SELECT id FROM menu_items WHERE visible = 1"
        ).fetchall()
    }
    order_items = []
    for key, value in request.form.items():
        if not key.startswith("qty_"):
            continue
        try:
            mid = int(key[4:])
            qty = int(value)
        except (TypeError, ValueError):
            continue
        if mid not in valid_ids:
            continue
        if qty <= 0:
            continue
        if qty > MAX_QTY_PER_ITEM:
            qty = MAX_QTY_PER_ITEM
        note = request.form.get(f"note_{mid}", "").strip()[:MAX_ITEM_NOTE_LEN]
        order_items.append((mid, qty, note))
        if len(order_items) >= MAX_ITEMS_PER_ORDER:
            break
    if not order_items:
        flash("Seleziona almeno un piatto.", "warning")
        return redirect(url_for("table_order", number=number))
    notes = request.form.get("order_notes", "").strip()[:MAX_ORDER_NOTE_LEN]
    cursor = db.execute(
        "INSERT INTO orders (table_id, notes) VALUES (?, ?)",
        (table["id"], notes or None)
    )
    order_id = cursor.lastrowid
    for mid, qty, note in order_items:
        db.execute(
            "INSERT INTO order_items (order_id, menu_item_id, quantity, notes) VALUES (?, ?, ?, ?)",
            (order_id, mid, qty, note or None)
        )
    db.commit()
    return render_template("table_order_success.html", table=table, order_id=order_id)

# ─── Orders Management (admin) ─────────────────────────────────────────────

@app.route("/admin/orders")
@login_required
def orders_list():
    db = get_db()
    status_filter = request.args.get("status", "pending")
    if status_filter == "all":
        orders = db.execute("""
            SELECT o.*, t.number as table_number, t.name as table_name
            FROM orders o JOIN tables t ON o.table_id = t.id
            ORDER BY o.created_at DESC
        """).fetchall()
    else:
        orders = db.execute("""
            SELECT o.*, t.number as table_number, t.name as table_name
            FROM orders o JOIN tables t ON o.table_id = t.id
            WHERE o.status = ?
            ORDER BY o.created_at DESC
        """, (status_filter,)).fetchall()
    # Fetch items for each order
    orders_with_items = []
    for order in orders:
        items = db.execute("""
            SELECT oi.*, m.title, m.price
            FROM order_items oi JOIN menu_items m ON oi.menu_item_id = m.id
            WHERE oi.order_id = ?
        """, (order["id"],)).fetchall()
        total = sum(item["price"] * item["quantity"] for item in items)
        orders_with_items.append({"order": order, "order_items": items, "total": total})
    return render_template("orders.html", orders=orders_with_items, current_status=status_filter)

@app.route("/admin/api/pending-count")
@login_required
def api_pending_count():
    """Ritorna il numero di ordini in stato 'pending' (per notifiche UI)."""
    db = get_db()
    row = db.execute("SELECT COUNT(*) c FROM orders WHERE status = 'pending'").fetchone()
    return jsonify(count=row["c"])

@app.route("/admin/orders/<int:oid>/status", methods=["POST"])
@login_required
def order_update_status(oid):
    new_status = request.form.get("status", "")
    if new_status not in ("pending", "confirmed", "preparing", "ready", "completed", "cancelled"):
        flash("Stato non valido.", "danger")
        return redirect(url_for("orders_list"))
    db = get_db()
    db.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, oid))
    db.commit()
    flash(f"Ordine #{oid} aggiornato a '{ORDER_STATUS_IT.get(new_status, new_status)}'.", "success")
    return redirect(url_for("orders_list", status=request.args.get("status", "pending")))

@app.route("/admin/orders/end-of-day", methods=["POST"])
@admin_required
def orders_end_of_day():
    db = get_db()
    deleted = db.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
    db.execute("DELETE FROM orders")
    db.commit()
    flash(f"Fine Giornata: {deleted} ordini cancellati.", "success")
    return redirect(url_for("dashboard"))

@app.route("/admin/orders/archive-daily", methods=["POST"])
@admin_required
def orders_archive_daily():
    db = get_db()
    rows = db.execute("""
        SELECT o.id AS order_id, o.status, o.created_at, o.notes AS order_notes,
               t.number AS table_number, t.name AS table_name,
               oi.quantity, oi.notes AS item_notes,
               m.title AS item_title, m.price AS item_price
        FROM orders o
        JOIN tables t ON o.table_id = t.id
        LEFT JOIN order_items oi ON oi.order_id = o.id
        LEFT JOIN menu_items m ON oi.menu_item_id = m.id
        ORDER BY o.created_at, o.id
    """).fetchall()

    if not rows:
        flash("Nessun ordine da archiviare.", "warning")
        return redirect(url_for("orders_list"))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"orders_{timestamp}.csv"
    abs_path = os.path.join(ARCHIVE_FOLDER, filename)
    with open(abs_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow([
            "order_id", "created_at", "status", "table_number", "table_name",
            "order_notes", "item_title", "quantity", "unit_price", "line_total", "item_notes",
        ])
        for r in rows:
            qty = r["quantity"] or 0
            price = r["item_price"] or 0
            writer.writerow([
                r["order_id"], r["created_at"], r["status"],
                r["table_number"], r["table_name"] or "",
                r["order_notes"] or "",
                r["item_title"] or "",
                qty, f"{price:.2f}", f"{price * qty:.2f}",
                r["item_notes"] or "",
            ])

    deleted = db.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
    db.execute("DELETE FROM orders")
    db.commit()
    flash(f"Archiviazione completata: {deleted} ordini salvati in {filename}.", "success")
    return redirect(url_for("orders_list"))

# ─── CLI First-Run Setup ────────────────────────────────────────────────────

def cli_setup():
    """Create admin user on first run."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    admin = db.execute("SELECT * FROM users WHERE role = 'admin'").fetchone()
    if admin:
        db.close()
        return
    print("\n" + "=" * 55)
    print("  🍽  TAVOLÒ — Primo Avvio")
    print("=" * 55)
    print("\n  Nessun amministratore trovato.")
    print("  Crea il primo utente admin per iniziare.\n")
    while True:
        username = input("  👤 Username admin: ").strip()
        if not username:
            print("  ⚠  Username obbligatorio.\n")
            continue
        if len(username) > 64 or not all(c.isalnum() or c in "._-" for c in username):
            print("  ⚠  Username non valido (max 64, alfanumerici, '.', '_', '-').\n")
            continue
        password = getpass.getpass("  🔑 Password admin: ")
        pw_err = _password_policy_error(password)
        if pw_err:
            print(f"  ⚠  {pw_err}\n")
            continue
        password2 = getpass.getpass("  🔑 Conferma password: ")
        if password != password2:
            print("  ⚠  Le password non coincidono.\n")
            continue
        break
    db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')",
        (username, generate_password_hash(password))
    )
    db.commit()
    db.close()
    print(f"\n  ✅ Admin '{username}' creato con successo!")
    print("=" * 55 + "\n")

# ─── Run ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    cli_setup()
    # Default sicuri: bind locale + debug OFF. Per LAN/produzione usare un WSGI
    # server (gunicorn/uwsgi) dietro reverse proxy TLS e sovrascrivere con env.
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f"  🌐 Server avviato su http://{host}:{port}")
    print(f"  📋 Menu pubblico: http://{host}:{port}/")
    print(f"  🔐 Admin panel:   http://{host}:{port}/login")
    if debug:
        print("  ⚠  ATTENZIONE: modalità DEBUG attiva — NON usare in produzione.")
    print()
    app.run(debug=debug, host=host, port=port)
