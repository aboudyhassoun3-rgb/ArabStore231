# -*- coding: utf-8 -*-
"""
ARAB STORE — New Edition (built from zero)
Backend: Flask + SQLite (local) / Postgres (Vercel+Supabase).
Serves the new luxury RTL frontend from ./public + full REST API.
Vercel entrypoint: `app` (see vercel.json).
"""
import os, re, hmac, json, secrets, string, sqlite3, uuid, time
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ---------- env / paths ----------
IS_VERCEL = os.environ.get("VERCEL") == "1"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("ARAB_DATA_DIR") or ("/tmp/arab-store" if IS_VERCEL else BASE_DIR)
os.makedirs(DATA_DIR, exist_ok=True)
DATABASE_URL = (os.environ.get("DATABASE_URL", "").strip()
                or os.environ.get("POSTGRES_URL", "").strip()
                or os.environ.get("POSTGRES_PRISMA_URL", "").strip())
USE_PG = bool(DATABASE_URL)

SECRET_KEY = os.environ.get("ARAB_SECRET_KEY") or None
if not SECRET_KEY:
    # مفتاح مؤقت يعمل فوراً (الجلسات قد تنتهي عند تبدّل النسخ).
    # للإنتاج اضبط ARAB_SECRET_KEY بقيمة ثابتة في Vercel.
    SECRET_KEY = secrets.token_urlsafe(32)
    print("WARNING: ARAB_SECRET_KEY not set — using ephemeral key. Set it in Vercel env for stable sessions.")
ADMIN_PASSWORD = os.environ.get("ARAB_ADMIN_PASSWORD") or "admin564"

PROVIDER_TOKEN = os.environ.get("ARAB_API_TOKEN", "").strip()
PROVIDER_URL = (os.environ.get("ARAB_API_BASE_URL", "") or "").strip().rstrip("/") or "https://api.shams4store.com"
OWNER_EMAILS = {"aboudyhassoun3@gmail.com"}
TOKEN_AGE = 60 * 60 * 24 * 30
WEB_ID_OFFSET = 9_000_000_000_000
ALLOWED_IMG = {"png", "jpg", "jpeg", "webp", "gif"}

app = Flask(__name__, static_folder="public", static_url_path="")
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
user_ser = URLSafeTimedSerializer(SECRET_KEY)
admin_ser = URLSafeTimedSerializer(SECRET_KEY, salt="admin-v2")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

limiter = Limiter(key_func=get_remote_address, app=app,
                  default_limits=["300 per hour", "60 per minute"], storage_uri="memory://")

# ---------- db layer ----------
def _pg_conn():
    import psycopg
    return psycopg.connect(DATABASE_URL)

def _lite_conn():
    p = os.path.join(DATA_DIR, "store.db")
    c = sqlite3.connect(p, check_same_thread=False, timeout=30, isolation_level=None)
    c.row_factory = sqlite3.Row
    try: c.execute("PRAGMA journal_mode=WAL;")
    except Exception: pass
    try: c.execute("PRAGMA busy_timeout=30000;")
    except Exception: pass
    return c

@contextmanager
def get_db():
    if USE_PG:
        conn = _pg_conn()
        try:
            yield PgWrap(conn)
            conn.commit()
        finally:
            conn.close()
    else:
        conn = _lite_conn()
        try:
            yield LiteWrap(conn)
            conn.commit()
        finally:
            conn.close()

class LiteWrap:
    def __init__(self, c): self.c = c
    def cur(self): return self.c.cursor()
    def execute(self, sql, p=()):
        cur = self.c.cursor(); cur.execute(sql, p); return cur

class PgWrap:
    """Accepts ? placeholders, rewrites to %s for psycopg."""
    def __init__(self, c): self.c = c
    def _rw(self, sql):
        out = []; i = 0
        for ch in sql:
            if ch == "?": i += 1; out.append(f"%s")
            else: out.append(ch)
        return "".join(out).replace("AUTOINCREMENT", "GENERATED ALWAYS AS IDENTITY") \
            .replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY") \
            .replace("DATETIME DEFAULT CURRENT_TIMESTAMP", "TIMESTAMP DEFAULT NOW()") \
            .replace("TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "TIMESTAMP DEFAULT NOW()")
    def cur(self): return self.c.cursor()
    def execute(self, sql, p=()):
        cur = self.c.cursor(); cur.execute(self._rw(sql), p); return cur

def _cols(cur, row):
    if row is None: return None
    try: return tuple(row)
    except Exception: return tuple(row)

def save_svg_bytes(svg_text, filename):
    """يحفظ SVG مولّد (صورة منتج بالهوية) في Supabase أو محلياً، ويرجع رابطه."""
    data = svg_text.encode("utf-8") if isinstance(svg_text, str) else svg_text
    name = secure_filename(filename)
    surl, skey = os.environ.get("SUPABASE_URL", "").strip().rstrip("/"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    bucket = os.environ.get("ARAB_STORAGE_BUCKET", "store-assets").strip() or "store-assets"
    if surl and skey:
        try:
            import requests as _rq
            r = _rq.post(f"{surl}/storage/v1/object/{bucket}/{name}",
                         headers={"Authorization": f"Bearer {skey}", "apikey": skey,
                                  "Content-Type": "image/svg+xml", "x-upsert": "true"},
                         data=data, timeout=25)
            r.raise_for_status()
            return f"{surl}/storage/v1/object/public/{bucket}/{name}"
        except Exception:
            pass
    with open(os.path.join(UPLOAD_DIR, name), "wb") as fh:
        fh.write(data)
    return f"/uploads/{name}"

def branded_image_url(product_name):
    """صورة تلقائية للمنتج: تدرّج + إيموجي + الاسم + شريط المتجر. ترجع '' عند الفشل."""
    try:
        from branding import build_product_svg, brand_filename
        try:
            store_name = get_setting("store_name", "ARAB STORE")
        except Exception:
            store_name = "ARAB STORE"
        return save_svg_bytes(build_product_svg(product_name, store_name),
                              brand_filename(product_name))
    except Exception:
        return ""


SCHEMA = """
CREATE TABLE IF NOT EXISTS web_users(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT UNIQUE,
 password_hash TEXT, site_user_id INTEGER UNIQUE, api_key TEXT UNIQUE, allowed_ips TEXT DEFAULT '',
 api_enabled INTEGER DEFAULT 0, preferred_currency TEXT DEFAULT 'USD', country TEXT DEFAULT '', phone TEXT DEFAULT '',
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS balances(user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS sections(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, color TEXT DEFAULT '#7c5cff',
 emoji TEXT DEFAULT '✨', image TEXT DEFAULT '', is_active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS subsections(id INTEGER PRIMARY KEY AUTOINCREMENT, section_id INTEGER, name TEXT,
 emoji TEXT DEFAULT '📦', image TEXT DEFAULT '', is_active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, category TEXT DEFAULT '',
 emoji TEXT DEFAULT '🎮', description TEXT DEFAULT '', image TEXT DEFAULT '', subsection_id INTEGER,
 sort_order INTEGER DEFAULT 0, public_id TEXT);
CREATE TABLE IF NOT EXISTS skus(id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, name TEXT, price REAL DEFAULT 0,
 cost REAL DEFAULT 0, min_qty INTEGER DEFAULT 1, max_qty INTEGER DEFAULT 1, image TEXT DEFAULT '',
 stock_qty INTEGER, requires_id INTEGER DEFAULT 1, public_id TEXT);
CREATE TABLE IF NOT EXISTS deposit_manual(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT DEFAULT '',
 code TEXT DEFAULT '', rate REAL DEFAULT 0, image TEXT DEFAULT '', input_currency TEXT DEFAULT 'usd');
CREATE TABLE IF NOT EXISTS deposit_auto(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT DEFAULT '',
 code TEXT DEFAULT '', rate REAL DEFAULT 0, api_token TEXT DEFAULT '', api_url TEXT DEFAULT '', image TEXT DEFAULT '',
 gateway TEXT DEFAULT 'verify', input_currency TEXT DEFAULT 'usd');
CREATE TABLE IF NOT EXISTS deposit_requests(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, email TEXT DEFAULT '',
 name TEXT DEFAULT '', method TEXT DEFAULT '', amount_usd REAL DEFAULT 0, amount_syp INTEGER DEFAULT 0,
 code TEXT DEFAULT '', status TEXT DEFAULT 'pending', invoice_ref TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT DEFAULT 'shop',
 product TEXT DEFAULT '', sku TEXT DEFAULT '', price_usd REAL DEFAULT 0, price_syp INTEGER DEFAULT 0,
 player TEXT DEFAULT '', qty INTEGER DEFAULT 1, status TEXT DEFAULT 'pending', provider_order TEXT DEFAULT '',
 response TEXT DEFAULT '', order_uuid TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT,
 amount INTEGER DEFAULT 0, note TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT,
 message TEXT DEFAULT '', kind TEXT DEFAULT 'info', is_read INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS banners(id INTEGER PRIMARY KEY AUTOINCREMENT, image TEXT, sort_order INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS web_admins(email TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS tiers(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, percent REAL DEFAULT 0, min_spent REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS user_tier(user_id INTEGER PRIMARY KEY, tier_id INTEGER);
CREATE TABLE IF NOT EXISTS referrals(code TEXT PRIMARY KEY, owner_id INTEGER, uses INTEGER DEFAULT 0);
"""

def init_db():
    with get_db() as db:
        for stmt in [s for s in SCHEMA.split(";") if s.strip()]:
            try: db.execute(stmt)
            except Exception: pass
        # ترحيل أعمدة جديدة لقواعد قديمة
        for mig in ["ALTER TABLE web_users ADD COLUMN blocked INTEGER DEFAULT 0",
                    "ALTER TABLE skus ADD COLUMN unit_qty INTEGER DEFAULT 1",
                    "ALTER TABLE skus ADD COLUMN type TEXT DEFAULT 'fixed'",
                    "ALTER TABLE orders ADD COLUMN cost_usd REAL DEFAULT 0",
                    "ALTER TABLE tiers ADD COLUMN sort_order INTEGER DEFAULT 0",
                    "ALTER TABLE web_admins ADD COLUMN added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"]:
            try: db.execute(mig)
            except Exception: pass
        # settings defaults
        defaults = {"exchange_rate": "13800", "support_username": "aboudy2312",
                    "support_telegram": "https://t.me/aboudy2312", "support_whatsapp": "",
                    "store_name": "ARAB STORE", "welcome_popup_enabled": "false",
                    "welcome_popup_text": "أهلاً بك في ARAB STORE ✨",
                    "welcome_message": "أهلاً بك في ARAB STORE ✨",
                    "logo_image": "", "dev_logo": "", "app_icon": "",
                    "ai_image_api_url": "", "ai_image_api_key": "",
                    "ai_image_prompt_template": "game top-up banner, {product}, neon",
                    "maintenance_enabled": "false", "maintenance_ends_at": ""}
        for k, v in defaults.items():
            try: db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO NOTHING" if USE_PG
                            else "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))
            except Exception: pass
        # seed demo catalog once
        try:
            n = db.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
            if (n or 0) == 0:
                seed(db)
        except Exception: pass

def seed(db):
    secs = [("شحن الألعاب", "#7c5cff", "🎮"), ("بطاقات رقمية", "#f5a623", "💳"), ("خدمات التواصل", "#22c55e", "📱")]
    for i, (n, c, e) in enumerate(secs):
        cur = db.execute("INSERT INTO sections(name,color,emoji,sort_order) VALUES(?,?,?,?) RETURNING id" if USE_PG
                         else "INSERT INTO sections(name,color,emoji,sort_order) VALUES(?,?,?,?)", (n, c, e, i))
        sid = (cur.fetchone()[0] if USE_PG else cur.lastrowid)
        for j, pname in enumerate(["فري فاير 💎", "ببجي موبايل 🔥"] if i == 0 else (["آيتونز", "غوغل بلاي"] if i == 1 else ["متابعين", "لايكات"])):
            cur2 = db.execute("INSERT INTO products(name,category,emoji,description,image,sort_order,public_id) VALUES(?,?,?,?,?,?,?) RETURNING id" if USE_PG
                              else "INSERT INTO products(name,category,emoji,description,image,sort_order,public_id) VALUES(?,?,?,?,?,?,?)",
                              (pname, n, e, "وصف تجريبي — عدّله من لوحة الأدمن", branded_image_url(pname), j, str(10000 + i * 100 + j)))
            pid = (cur2.fetchone()[0] if USE_PG else cur2.lastrowid)
            for k, (sname, price) in enumerate([("باقة صغيرة", 1.5), ("باقة وسط", 5), ("باقة كبيرة", 10)]):
                db.execute("INSERT INTO skus(product_id,name,price,cost,min_qty,max_qty,public_id) VALUES(?,?,?,?,?,?,?)",
                           (pid, sname, price, price * 0.85, 1, 10, str(20000 + pid * 10 + k)))
    db.execute("INSERT INTO deposit_manual(title,description,code) VALUES(?,?,?)",
               ("شام كاش يدوي", "حوّل ثم أرسل كود العملية", "sham"))
    db.execute("INSERT INTO deposit_auto(title,description,code,gateway) VALUES(?,?,?,?)",
                ("تحقق تلقائي", "إيداع فوري عبر كود العملية", "auto", "verify"))

try:
    init_db()
except Exception as e:
    # لا نمنع إقلاع التطبيق (مثلاً DATABASE_URL خاطئ) — تُسجّل المشكلة
    # وتظهر عبر /health، والصفحات الثابتة تستمر بالعمل.
    print(f"WARNING: init_db failed: {e}")

# ---------- helpers ----------
def get_setting(k, d=""):
    with get_db() as db:
        r = db.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone()
        return (r[0] if r else d)

def set_setting(k, v):
    with get_db() as db:
        if USE_PG: db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, v))
        else: db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, v))

def rate(): return float(get_setting("exchange_rate", "13800") or 13800)

def gen_key(): return "ALSH-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(28))

def get_web_by_email(email):
    with get_db() as db:
        return db.execute("SELECT * FROM web_users WHERE email=?", (email.lower().strip(),)).fetchone()

def get_web_by_id(wid):
    with get_db() as db:
        return db.execute("SELECT * FROM web_users WHERE id=?", (wid,)).fetchone()

def row_to_user_public(w):
    import sqlite3 as _s
    uid = w["site_user_id"] if isinstance(w, _s.Row) else w[4]
    try: uid = int(uid)
    except Exception: uid = 0
    bal = balance_of(uid); r = rate()
    disc = tier_of(uid)
    email = w["email"] if isinstance(w, _s.Row) else w[2]
    return {"id": w["id"] if isinstance(w, _s.Row) else w[0],
            "name": w["name"] if isinstance(w, _s.Row) else w[1],
            "email": email, "balance_syp": bal, "balance_usd": round(bal / r, 2) if r else 0,
            "api_enabled": bool(w["api_enabled"] if isinstance(w, _s.Row) else w[7]),
            "preferred_currency": ((w["preferred_currency"] if isinstance(w, _s.Row) else w[8]) or "USD").upper(),
            "country": w["country"] if isinstance(w, _s.Row) else (w[9] if len(w) > 9 else ""),
            "phone": w["phone"] if isinstance(w, _s.Row) else (w[10] if len(w) > 10 else ""),
            "discount_percent": disc[1] if disc else 0, "discount_tier_name": disc[0] if disc else "",
            "is_owner": (email or "").lower() in OWNER_EMAILS, "is_admin": is_admin(email)}

def balance_of(uid):
    with get_db() as db:
        r = db.execute("SELECT balance FROM balances WHERE user_id=?", (uid,)).fetchone()
        return int(r[0]) if r else 0

def add_balance(uid, delta, note=""):
    with get_db() as db:
        if USE_PG:
            db.execute("INSERT INTO balances(user_id,balance) VALUES(?,0) ON CONFLICT(user_id) DO NOTHING", (uid,))
        else:
            db.execute("INSERT OR IGNORE INTO balances(user_id,balance) VALUES(?,0)", (uid,))
        db.execute("UPDATE balances SET balance=balance+? WHERE user_id=?", (int(delta), uid))
        if note: db.execute("INSERT INTO transactions(user_id,type,amount,note) VALUES(?,?,?,?)", (uid, "in" if delta >= 0 else "out", int(delta), note))
    return balance_of(uid)

def tier_of(uid):
    with get_db() as db:
        r = db.execute("SELECT t.name,t.percent FROM user_tier ut JOIN tiers t ON t.id=ut.tier_id WHERE ut.user_id=?", (uid,)).fetchone()
        return (r[0], float(r[1])) if r else None

def is_admin(email):
    e = (email or "").lower()
    if e in OWNER_EMAILS: return True
    with get_db() as db:
        try: return bool(db.execute("SELECT 1 FROM web_admins WHERE email=?", (e,)).fetchone())
        except Exception: return False

def notify(user_id, title, msg="", kind="info"):
    with get_db() as db:
        db.execute("INSERT INTO notifications(user_id,title,message,kind) VALUES(?,?,?,?)", (user_id, title, msg, kind))

# ---------- الجلسات في قاعدة البيانات (تعمل على كل النسخ حتى بدون ARAB_SECRET_KEY) ----------
def issue_token(web_id, admin=False, owner=False):
    tok = secrets.token_urlsafe(32)
    with get_db() as db:
        try: db.execute("DELETE FROM auth_tokens WHERE created_at < datetime('now','-60 days')")
        except Exception: pass
        db.execute("INSERT INTO auth_tokens(token,web_id,is_admin,is_owner) VALUES(?,?,?,?)",
                   (tok, web_id if not admin else None, 1 if admin else 0, 1 if owner else 0))
    return tok

def revoke_token(tok):
    try:
        with get_db() as db: db.execute("DELETE FROM auth_tokens WHERE token=?", (tok,))
    except Exception: pass

def token_to_web(tok):
    """يرجع web_id أو None. يدعم توكنات DB الجديدة والقديمة الموقّعة."""
    if not tok: return None
    try:
        with get_db() as db:
            r = db.execute("SELECT web_id FROM auth_tokens WHERE token=? AND (is_admin=0 OR is_admin IS NULL)", (tok,)).fetchone()
        if r and r[0] is not None: return int(r[0])
    except Exception: pass
    try:
        return int(user_ser.loads(tok, max_age=TOKEN_AGE).get("web_id"))
    except Exception: return None

def token_to_admin(tok):
    """يرجع payload الأدمن أو None."""
    if not tok: return None
    try:
        with get_db() as db:
            r = db.execute("SELECT is_owner FROM auth_tokens WHERE token=? AND is_admin=1", (tok,)).fetchone()
        if r: return {"owner": bool(r[0])}
    except Exception: pass
    try:
        return admin_ser.loads(tok, max_age=90 * 24 * 60 * 60)
    except Exception: return None

def require_auth(f):
    @wraps(f)
    def w(*a, **kw):
        h = request.headers.get("Authorization", "")
        if not h.startswith("Bearer "): return jsonify({"message": "سجّل دخولك أولاً"}), 401
        wid = token_to_web(h[7:])
        if not wid:
            return jsonify({"message": "انتهت الجلسة، سجّل دخولك من جديد"}), 401
        u = get_web_by_id(wid)
        if not u: return jsonify({"message": "الحساب غير موجود"}), 401
        request.wu = u; return f(*a, **kw)
    return w

def optional_user():
    h = request.headers.get("Authorization", "")
    if not h.startswith("Bearer "): return None
    wid = token_to_web(h[7:])
    return get_web_by_id(wid) if wid else None

def require_admin(f):
    @wraps(f)
    def w(*a, **kw):
        h = request.headers.get("Authorization", "")
        token = h[7:] if h.startswith("Bearer ") else (request.args.get("token", "") or "")
        if not token: return jsonify({"message": "دخول غير مصرح"}), 401
        p = token_to_admin(token)
        if not p: return jsonify({"message": "دخول غير مصرح"}), 401
        request.ap = p; return f(*a, **kw)
    return w

def save_upload(fs):
    if not fs or not fs.filename: return ""
    ext = fs.filename.rsplit(".", 1)[-1].lower() if "." in fs.filename else ""
    if ext not in ALLOWED_IMG: return ""
    name = f"{uuid.uuid4().hex}.{ext}"
    # supabase?
    surl, skey = os.environ.get("SUPABASE_URL", "").strip().rstrip("/"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    bucket = os.environ.get("ARAB_STORAGE_BUCKET", "store-assets").strip() or "store-assets"
    if surl and skey:
        try:
            import requests as _rq
            data = fs.read()
            r = _rq.post(f"{surl}/storage/v1/object/{bucket}/{name}",
                         headers={"Authorization": f"Bearer {skey}", "apikey": skey,
                                  "Content-Type": fs.mimetype or "image/png", "x-upsert": "true"},
                         data=data, timeout=25)
            r.raise_for_status()
            return f"{surl}/storage/v1/object/public/{bucket}/{name}"
        except Exception: pass
    fs.stream.seek(0) if hasattr(fs.stream, "seek") else None
    try: fs.save(os.path.join(UPLOAD_DIR, secure_filename(name)))
    except Exception:
        with open(os.path.join(UPLOAD_DIR, secure_filename(name)), "wb") as fh: fh.write(fs.read())
    return f"/uploads/{secure_filename(name)}"

# provider (real attempt + graceful mock)
def provider_buy(sku_row, player, qty, token=None, url=None, product_ref=None):
    tok = (token or PROVIDER_TOKEN or "").strip()
    base = ((url or PROVIDER_URL or "").strip().rstrip("/") or "https://api.shams4store.com")
    if tok:
        try:
            import requests as _rq
            payload = {"token": tok, "api_token": tok, "product_id": product_ref,
                       "player_id": player, "player": player, "qty": qty, "quantity": qty}
            r = _rq.post(f"{base}/api/order", json=payload, timeout=25)
            if r.ok:
                try: d = r.json()
                except Exception: d = {}
                if isinstance(d, dict):
                    oid = d.get("order_id") or d.get("id") or (d.get("data") or {}).get("order_id") if isinstance(d.get("data"), dict) else d.get("order_id")
                    ok = d.get("status") not in ("error", "failed") and (d.get("status", "OK") in ("OK", "success", "accept", "processing", "completed") or oid)
                    if ok: return True, str(oid or f"PV-{uuid.uuid4().hex[:8]}"), r.text[:500]
                    return False, "", str(d.get("message", r.text))[:500]
                return True, f"PV-{uuid.uuid4().hex[:8]}", r.text[:500]
            return False, "", f"provider-http-{r.status_code}"
        except Exception as e: return False, "", f"provider-error: {e}"
    return True, f"LOCAL-{uuid.uuid4().hex[:8]}", "تم التنفيذ محلياً (لا يوجد مزوّد مربوط)"

def sku_provider(sku_id):
    """يرجع (token, url, provider_product) للباقة المرتبطة أو (None,None,None)."""
    try:
        with get_db() as db:
            r = db.execute("SELECT p.token,p.url,l.provider_product FROM category_links l JOIN providers p ON p.id=l.provider_id WHERE l.category_id=?", (sku_id,)).fetchone()
        return (r[0], r[1], r[2]) if r else (None, None, None)
    except Exception:
        return (None, None, None)

def provider_status(porder):
    if not porder or porder.startswith("LOCAL-"): return "completed"
    if PROVIDER_TOKEN:
        try:
            import requests as _rq
            r = _rq.get(f"{PROVIDER_URL}/api/order-status", params={"token": PROVIDER_TOKEN, "order_id": porder}, timeout=15)
            if r.ok: return str(r.json().get("status", "pending"))
        except Exception: pass
    return "completed"

# ---------- maintenance guard ----------
@app.before_request
def _maint():
    if request.path.startswith("/api/") and not (request.path.startswith("/api/auth/") or request.path.startswith("/api/admin/") or request.path == "/api/maintenance-status"):
        if get_setting("maintenance_enabled", "false") == "true":
            return jsonify({"message": "المتجر في صيانة مؤقتة ✨ نعود قريباً", "maintenance": True}), 503

# ================= AUTH =================
@app.post("/api/auth/register")
@limiter.limit("8 per hour")
def register():
    b = request.get_json(force=True, silent=True) or {}
    name, email, pw = (b.get("name") or "").strip(), (b.get("email") or "").strip().lower(), b.get("password") or ""
    country, phone = (b.get("country") or "").strip(), re.sub(r"[^\d+]", "", str(b.get("phone") or ""))
    if not name or not email or len(pw) < 6: return jsonify({"message": "أكمل الاسم والإيميل وكلمة مرور 6+ أحرف"}), 400
    if not country: return jsonify({"message": "اختر البلد"}), 400
    if len(phone) < 6: return jsonify({"message": "رقم هاتف غير صحيح"}), 400
    if get_web_by_email(email): return jsonify({"message": "هذا الإيميل مسجّل مسبقاً"}), 409
    with get_db() as db:
        cur = db.execute("INSERT INTO web_users(name,email,password_hash,country,phone) VALUES(?,?,?,?,?) RETURNING id" if USE_PG
                         else "INSERT INTO web_users(name,email,password_hash,country,phone) VALUES(?,?,?,?,?)",
                         (name, email, generate_password_hash(pw), country, phone))
        wid = cur.fetchone()[0] if USE_PG else cur.lastrowid
        sid = WEB_ID_OFFSET + int(wid)
        db.execute("UPDATE web_users SET site_user_id=? WHERE id=?", (sid, wid))
        if USE_PG: db.execute("INSERT INTO balances(user_id,balance) VALUES(?,0) ON CONFLICT(user_id) DO NOTHING", (sid,))
        else: db.execute("INSERT OR IGNORE INTO balances(user_id,balance) VALUES(?,0)", (sid,))
        try: db.execute("INSERT INTO referrals(code,owner_id) VALUES(?,?)", (f"REF-{wid}-{secrets.token_hex(2).upper()}", sid))
        except Exception: pass
    u = get_web_by_id(wid)
    return jsonify({"token": issue_token(wid), "user": row_to_user_public(u)})

@app.post("/api/auth/logout")
def logout():
    h = request.headers.get("Authorization", "")
    if h.startswith("Bearer "): revoke_token(h[7:])
    return jsonify({"message": "تم تسجيل الخروج"})

@app.post("/api/auth/login")
@limiter.limit("12 per minute")
def login():
    b = request.get_json(force=True, silent=True) or {}
    email, pw = (b.get("email") or "").lower().strip(), b.get("password") or ""
    u = get_web_by_email(email)
    if not u or not check_password_hash(u["password_hash"] if "password_hash" in u.keys() else u[3], pw):
        return jsonify({"message": "الإيميل أو كلمة المرور غير صحيحة"}), 401
    try:
        blocked = u["blocked"] if "blocked" in u.keys() else None
    except Exception:
        blocked = None
    if blocked:
        return jsonify({"message": "تم حظر حسابك — تواصل مع الدعم"}), 403
    return jsonify({"token": issue_token(int(u["id"] if "id" in u.keys() else u[0])), "user": row_to_user_public(u)})

@app.get("/api/auth/me")
@require_auth
def me(): return jsonify({"user": row_to_user_public(request.wu)})

@app.post("/api/auth/update-profile")
@require_auth
def upd_profile():
    b = request.get_json(force=True, silent=True) or {}
    name, email = (b.get("name") or "").strip(), (b.get("email") or "").strip().lower()
    if not name or not email: return jsonify({"message": "الاسم والبريد مطلوبان"}), 400
    wid = int(request.wu["id"] if "id" in request.wu.keys() else request.wu[0])
    ex = get_web_by_email(email)
    if ex and int(ex["id"] if "id" in ex.keys() else ex[0]) != wid:
        return jsonify({"message": "البريد مستخدم بحساب آخر"}), 409
    with get_db() as db: db.execute("UPDATE web_users SET name=?,email=? WHERE id=?", (name, email, wid))
    return jsonify({"message": "تم الحفظ ✅"})

@app.post("/api/auth/currency")
@require_auth
def set_cur():
    c = ((request.get_json(force=True, silent=True) or {}).get("currency") or "").upper()
    if c not in ("USD", "SYP"): return jsonify({"message": "عملة غير مدعومة"}), 400
    wid = int(request.wu["id"] if "id" in request.wu.keys() else request.wu[0])
    with get_db() as db: db.execute("UPDATE web_users SET preferred_currency=? WHERE id=?", (c, wid))
    return jsonify({"message": "تم ✅", "currency": c})

@app.post("/api/auth/change-password")
@require_auth
def ch_pw():
    b = request.get_json(force=True, silent=True) or {}
    old, new = b.get("old_password", ""), b.get("new_password", "")
    if len(new) < 6: return jsonify({"message": "الجديدة 6 أحرف على الأقل"}), 400
    h = request.wu["password_hash"] if "password_hash" in request.wu.keys() else request.wu[3]
    if not check_password_hash(h, old): return jsonify({"message": "الحالية غير صحيحة"}), 401
    wid = int(request.wu["id"] if "id" in request.wu.keys() else request.wu[0])
    with get_db() as db: db.execute("UPDATE web_users SET password_hash=? WHERE id=?", (generate_password_hash(new), wid))
    return jsonify({"message": "تم تغيير كلمة المرور ✅"})

# ================= STORE (public) =================
@app.get("/api/maintenance-status")
def mstat():
    en = get_setting("maintenance_enabled", "false") == "true"
    ends = get_setting("maintenance_ends_at", "")
    left = 0
    if en and ends:
        try: left = max(0, int((datetime.fromisoformat(ends) - datetime.now()).total_seconds()))
        except Exception: left = 0
        if left <= 0: set_setting("maintenance_enabled", "false"); en = False
    return jsonify({"enabled": en, "ends_at": ends or None, "seconds_left": left})

@app.get("/api/store/settings")
def store_settings():
    with get_db() as db:
        try: banners = [r[0] for r in db.execute("SELECT image FROM banners ORDER BY sort_order,id").fetchall()]
        except Exception: banners = []
    _wa_num = re.sub(r"[^\d]", "", get_setting("support_whatsapp_number", "") or "")
    _wa_url = get_setting("support_whatsapp_url", "") or get_setting("support_whatsapp", "") or (f"https://wa.me/{_wa_num}" if _wa_num else "")
    _tg_url = get_setting("support_telegram_url", "") or get_setting("support_telegram", "") or (f"https://t.me/{get_setting('support_username','')}" if get_setting("support_username", "") else "")
    return jsonify({"exchange_rate": rate(), "store_name": get_setting("store_name", "ARAB STORE"),
                    "support_username": get_setting("support_username", "aboudy2312"),
                    "support_telegram": get_setting("support_telegram", "https://t.me/aboudy2312"),
                    "support_whatsapp": get_setting("support_whatsapp", ""),
                    "banner_images": banners, "logo_image": get_setting("logo_image", ""),
                    "welcome_popup_enabled": get_setting("welcome_popup_enabled", "false") == "true",
                    "welcome_popup_text": get_setting("welcome_popup_text", ""),
                    "welcome_message": get_setting("welcome_message", get_setting("welcome_popup_text", "")),
                    "ai_image_api_url": get_setting("ai_image_api_url", ""),
                    "ai_image_api_key": get_setting("ai_image_api_key", ""),
                    "ai_image_prompt_template": get_setting("ai_image_prompt_template", ""),
                    "dev_logo": get_setting("dev_logo", ""),
                    "contact": {"whatsapp_number": get_setting("support_whatsapp_number", ""),
                                "whatsapp_url": _wa_url,
                                "telegram_url": _tg_url,
                                "telegram_channel_url": get_setting("telegram_channel_url", ""),
                                "whatsapp_channel_url": get_setting("whatsapp_channel_url", "")}})

@app.get("/api/store/sections")
def sections():
    with get_db() as db:
        rows = db.execute("SELECT id,name,color,emoji,image FROM sections WHERE is_active=1 ORDER BY sort_order,id").fetchall()
    return jsonify([{"id": r[0], "name": r[1], "color": r[2], "emoji": r[3], "image": r[4] or ""} for r in rows])

@app.get("/api/store/subsections")
def subsections():
    sid = request.args.get("section_id", type=int)
    if not sid: return jsonify({"message": "section_id مطلوب"}), 400
    with get_db() as db:
        rows = db.execute("SELECT id,section_id,name,emoji,image FROM subsections WHERE section_id=? AND is_active=1 ORDER BY sort_order,id", (sid,)).fetchall()
    return jsonify([{"id": r[0], "section_id": r[1], "name": r[2], "emoji": r[3], "image": r[4] or ""} for r in rows])

@app.get("/api/store/products")
def products():
    sub = request.args.get("subsection_id", type=int); sec = request.args.get("section", "")
    with get_db() as db:
        if sub:
            rows = db.execute("SELECT id,name,emoji,image FROM products WHERE subsection_id=? ORDER BY sort_order,id", (sub,)).fetchall()
        elif sec:
            rows = db.execute("SELECT id,name,emoji,image FROM products WHERE category=? AND (subsection_id IS NULL OR subsection_id=0) ORDER BY sort_order,id", (sec,)).fetchall()
        else: return jsonify({"message": "section أو subsection_id مطلوب"}), 400
    q = (request.args.get("q") or "").strip()
    out = [{"id": r[0], "name": r[1], "emoji": r[2], "image": r[3] or ""} for r in rows]
    if q: out = [x for x in out if q.lower() in x["name"].lower()]
    return jsonify(out)

@app.get("/api/store/product/<int:pid>")
def product_one(pid):
    with get_db() as db:
        p = db.execute("SELECT id,name,category,emoji,description,image FROM products WHERE id=?", (pid,)).fetchone()
    if not p: return jsonify({"message": "المنتج غير موجود"}), 404
    return jsonify({"id": p[0], "name": p[1], "category": p[2], "emoji": p[3], "description": p[4] or "", "image": p[5] or ""})

@app.get("/api/store/categories")
def skus():
    pid = request.args.get("product_id", type=int)
    if not pid: return jsonify({"message": "product_id مطلوب"}), 400
    r = rate(); disc = 0
    u = optional_user()
    if u:
        try: uid = int(u["site_user_id"] if "site_user_id" in u.keys() else u[4]); t = tier_of(uid); disc = t[1] if t else 0
        except Exception: pass
    with get_db() as db:
        try: rows = db.execute("SELECT id,name,price,image,stock_qty,requires_id,public_id,min_qty,max_qty,unit_qty,type FROM skus WHERE product_id=?", (pid,)).fetchall()
        except Exception: rows = db.execute("SELECT id,name,price,image,stock_qty,requires_id,public_id,min_qty,max_qty FROM skus WHERE product_id=?", (pid,)).fetchall()
    out = []
    for x in rows:
        base = float(x[2] or 0); final = round(base * (1 - disc / 100), 4) if disc else base
        uq = (x[9] if len(x) > 9 and x[9] else 1) or 1
        out.append({"id": x[0], "name": x[1], "price_usd": final, "price_syp": round(final * r),
                    "image": x[3] or "", "stock_qty": x[4], "available": (x[4] is None or int(x[4]) > 0),
                    "requires_id": bool(x[5] if x[5] is not None else 1), "public_id": x[6] or str(x[0]),
                    "min_qty": x[7] or 1, "max_qty": x[8] or 1, "unit_qty": uq,
                    "type": (x[10] if len(x) > 10 and x[10] else "fixed"),
                    **({"original_price_usd": base, "discount_percent": disc} if disc else {})})
    return jsonify(out)

def _insert_order(db, uid, pname, sname, price_usd, price_syp, player, qty, status, porder, resp, ouuid, cost_usd=0):
    vals = (uid, pname, sname, price_usd, price_syp, player, qty, status, porder, (resp or "")[:500], ouuid, round(float(cost_usd or 0), 4))
    try:
        cur = db.execute("INSERT INTO orders(user_id,product,sku,price_usd,price_syp,player,qty,status,provider_order,response,order_uuid,cost_usd) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id" if USE_PG
                         else "INSERT INTO orders(user_id,product,sku,price_usd,price_syp,player,qty,status,provider_order,response,order_uuid,cost_usd) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", vals)
    except Exception:
        cur = db.execute("INSERT INTO orders(user_id,product,sku,price_usd,price_syp,player,qty,status,provider_order,response,order_uuid) VALUES(?,?,?,?,?,?,?,?,?,?,?) RETURNING id" if USE_PG
                         else "INSERT INTO orders(user_id,product,sku,price_usd,price_syp,player,qty,status,provider_order,response,order_uuid) VALUES(?,?,?,?,?,?,?,?,?,?,?)", vals[:-1])
    return cur.fetchone()[0] if USE_PG else cur.lastrowid

# ================= WALLET / DEPOSIT =================
@app.get("/api/wallet")
@require_auth
def wallet(): return jsonify({"user": row_to_user_public(get_web_by_id(int(request.wu["id"] if "id" in request.wu.keys() else request.wu[0])))})

@app.get("/api/wallet/transactions")
@require_auth
def wtx():
    uid = int(request.wu["site_user_id"] if "site_user_id" in request.wu.keys() else request.wu[4])
    with get_db() as db:
        rows = db.execute("SELECT type,amount,note,created_at FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 100", (uid,)).fetchall()
    return jsonify([{"type": r[0], "amount": r[1], "description": r[2], "date": str(r[3])} for r in rows])

@app.get("/api/wallet/deposit-history")
@require_auth
def dhist():
    uid = int(request.wu["site_user_id"] if "site_user_id" in request.wu.keys() else request.wu[4])
    with get_db() as db:
        rows = db.execute("SELECT method,amount_usd,amount_syp,status,created_at FROM deposit_requests WHERE user_id=? ORDER BY id DESC LIMIT 30", (uid,)).fetchall()
    return jsonify([{"method_title": r[0], "amount_usd": r[1], "amount_syp": r[2], "status": r[3], "date": str(r[4])} for r in rows])

@app.get("/api/wallet/deposit-methods")
def dmethods():
    with get_db() as db:
        try: auto = db.execute("SELECT id,title,description,code,image,gateway,input_currency FROM deposit_auto").fetchall()
        except Exception: auto = []
        try: man = db.execute("SELECT id,title,description,code,image,input_currency FROM deposit_manual").fetchall()
        except Exception: man = []
    return jsonify({"auto": [{"id": m[0], "title": m[1], "description": m[2] or "", "code": m[3] or "", "image": m[4] or "", "gateway_type": m[5] or "verify", "input_currency": m[6] or "usd"} for m in auto],
                    "manual": [{"id": m[0], "title": m[1], "description": m[2] or "", "code": m[3] or "", "image": m[4] or "", "input_currency": m[5] or "usd"} for m in man]})

@app.post("/api/wallet/deposit")
@require_auth
def deposit():
    b = request.get_json(force=True, silent=True) or {}
    mid, kind = b.get("method_id"), b.get("kind")
    amt = float(b.get("amount_usd") or 0); code = (b.get("transaction_code") or "").strip()
    if amt <= 0 or not code or kind not in ("auto", "manual"): return jsonify({"message": "أكمل المبلغ والكود"}), 400
    uid = int(request.wu["site_user_id"] if "site_user_id" in request.wu.keys() else request.wu[4])
    email = request.wu["email"] if "email" in request.wu.keys() else request.wu[2]
    name = request.wu["name"] if "name" in request.wu.keys() else request.wu[1]
    r = rate()
    with get_db() as db:
        if kind == "auto":
            m = db.execute("SELECT id,title,input_currency FROM deposit_auto WHERE id=?", (mid,)).fetchone()
            if not m: return jsonify({"message": "الطريقة غير موجودة"}), 404
            cur = (m[2] or "usd").lower()
            ausd, asyp = (round(amt / r, 4), amt) if cur == "syp" else (amt, amt * r)
            # تحقق بسيط: كود بطول كافٍ + غير مكرر
            dup = db.execute("SELECT 1 FROM deposit_requests WHERE code=?", (code,)).fetchone()
            if dup or len(code) < 4: return jsonify({"message": "الكود غير صالح أو مستخدم مسبقاً"}), 400
            db.execute("INSERT INTO deposit_requests(user_id,email,name,method,amount_usd,amount_syp,code,status) VALUES(?,?,?,?,?,?,?,'accepted')",
                       (uid, email, name, m[1], ausd, int(asyp), code))
            db.execute("INSERT INTO transactions(user_id,type,amount,note) VALUES(?, 'in', ?, ?)", (uid, int(asyp), f"إيداع تلقائي {m[1]}"))
            if USE_PG: db.execute("INSERT INTO balances(user_id,balance) VALUES(?,0) ON CONFLICT(user_id) DO NOTHING", (uid,))
            else: db.execute("INSERT OR IGNORE INTO balances(user_id,balance) VALUES(?,0)", (uid,))
            db.execute("UPDATE balances SET balance=balance+? WHERE user_id=?", (int(asyp), uid))
            notify(uid, "تم الإيداع ✅", f"{ausd}$ عبر {m[1]}", "success")
        else:
            m = db.execute("SELECT id,title,input_currency FROM deposit_manual WHERE id=?", (mid,)).fetchone()
            if not m: return jsonify({"message": "الطريقة غير موجودة"}), 404
            cur = (m[2] or "usd").lower()
            ausd, asyp = (round(amt / r, 4), amt) if cur == "syp" else (amt, amt * r)
            db.execute("INSERT INTO deposit_requests(user_id,email,name,method,amount_usd,amount_syp,code,status) VALUES(?,?,?,?,?,?,?,'pending')",
                       (uid, email, name, m[1], ausd, int(asyp), code))
            notify(0, "طلب إيداع يدوي 💳", f"{name} — {ausd}$ — {m[1]} — كود: {code}", "info")
            return jsonify({"message": "تم إرسال الطلب بانتظار المراجعة ⏳"})
    return jsonify({"message": "تم الإيداع بنجاح ✅", "new_balance_syp": balance_of(uid)})

# ================= ORDERS =================
def _serialize(uid):
    with get_db() as db:
        rows = db.execute("SELECT id,product,sku,price_usd,price_syp,player,qty,status,provider_order,created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 100", (uid,)).fetchall()
    return [{"id": r[0], "product": r[1], "product_name": r[1], "category": r[2], "category_name": r[2],
             "price_usd": r[3], "price_syp": r[4], "player": r[5], "player_id": r[5],
             "qty": r[6], "status": r[7], "raw_status": r[7], "source": "shop",
             "provider_order": r[8], "date": str(r[9]), "created_at": str(r[9])} for r in rows]

@app.get("/api/orders")
@require_auth
def orders_list():
    uid = int(request.wu["site_user_id"] if "site_user_id" in request.wu.keys() else request.wu[4])
    return jsonify(_serialize(uid))

@app.post("/api/orders")
@require_auth
def order_create():
    b = request.get_json(force=True, silent=True) or {}
    sku_id, player, qty = b.get("category_id") or b.get("sku_id"), ((b.get("player_id") or b.get("player") or "").strip()), int(b.get("qty") or 1)
    ouuid = (b.get("order_uuid") or "").strip()
    if not sku_id: return jsonify({"message": "اختر الباقة"}), 400
    uid = int(request.wu["site_user_id"] if "site_user_id" in request.wu.keys() else request.wu[4])
    with get_db() as db:
        if ouuid:
            dup = db.execute("SELECT id FROM orders WHERE order_uuid=?", (ouuid,)).fetchone()
            if dup: return jsonify({"message": "تم استلام طلبك مسبقاً ✅", "order_id": dup[0]})
        try: s = db.execute("SELECT id,product_id,name,price,stock_qty,requires_id,cost FROM skus WHERE id=?", (sku_id,)).fetchone()
        except Exception: s = db.execute("SELECT id,product_id,name,price,stock_qty,requires_id FROM skus WHERE id=?", (sku_id,)).fetchone()
        if not s: return jsonify({"message": "الباقة غير موجودة"}), 404
        if s[5] and not player: return jsonify({"message": "أدخل معرّف اللاعب"}), 400
        if s[4] is not None and int(s[4]) <= 0: return jsonify({"message": "نفد المخزون حالياً"}), 400
        p = db.execute("SELECT name FROM products WHERE id=?", (s[1],)).fetchone()
        pname = p[0] if p else ""
        t = tier_of(uid); disc = t[1] if t else 0
        price_usd = round(float(s[3]) * (1 - disc / 100), 4); r = rate(); price_syp = int(price_usd * r * qty)
        bal = balance_of(uid)
        if bal < price_syp: return jsonify({"message": f"رصيدك غير كافٍ ({bal:,} ل.س). اشحن محفظتك أولاً 💳"}), 402
        _ptok, _purl, _ppid = sku_provider(s[0])
        ok, porder, resp = provider_buy(s, player, qty, _ptok, _purl, _ppid)
        status = "completed" if ok else ("pending" if _ptok else "failed")
        if status == "pending":
            notify(0, "طلب معلّق يحتاج تنفيذ ⏳", f"{pname} — {s[2]} — {player}", "info")
        if s[4] is not None: db.execute("UPDATE skus SET stock_qty=stock_qty-1 WHERE id=?", (s[0],))
        db.execute("UPDATE balances SET balance=balance-? WHERE user_id=?", (price_syp, uid))
        db.execute("INSERT INTO transactions(user_id,type,amount,note) VALUES(?, 'out', ?, ?)", (uid, -price_syp, f"شراء {pname} — {s[2]}"))
        _cost = float(s[6] if len(s) > 6 and s[6] else (s[3] or 0)) * qty
        oid = _insert_order(db, uid, pname, s[2], price_usd * qty, price_syp, player, qty, status, porder, resp, ouuid or f"{uid}-{int(time.time())}", _cost)
        notify(uid, "طلب جديد 🛒", f"{pname} — {s[2]} — {status}", "success" if ok else "error")
    return jsonify({"message": "تم تنفيذ طلبك بنجاح ✅", "order_id": oid, "status": status})

@app.get("/api/orders/<int:oid>/refresh")
@require_auth
def order_refresh(oid):
    uid = int(request.wu["site_user_id"] if "site_user_id" in request.wu.keys() else request.wu[4])
    with get_db() as db:
        o = db.execute("SELECT provider_order FROM orders WHERE id=? AND user_id=?", (oid, uid)).fetchone()
        if not o: return jsonify({"message": "الطلب غير موجود"}), 404
        st = provider_status(o[0])
        db.execute("UPDATE orders SET status=? WHERE id=?", (st, oid))
    return jsonify({"status": st})

@app.get("/api/orders/<int:oid>/detail")
@require_auth
def order_detail(oid):
    uid = int(request.wu["site_user_id"] if "site_user_id" in request.wu.keys() else request.wu[4])
    with get_db() as db:
        o = db.execute("SELECT id,product,sku,price_usd,price_syp,player,qty,status,created_at FROM orders WHERE id=? AND user_id=?", (oid, uid)).fetchone()
    if not o: return jsonify({"message": "الطلب غير موجود"}), 404
    return jsonify({"id": o[0], "product": o[1], "category": o[2], "price_usd": o[3], "price_syp": o[4], "player": o[5], "qty": o[6], "status": o[7], "date": str(o[8])})

@app.get("/api/user/activity")
@require_auth
def activity():
    uid = int(request.wu["site_user_id"] if "site_user_id" in request.wu.keys() else request.wu[4])
    with get_db() as db:
        tx = db.execute("SELECT note,amount,created_at FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 20", (uid,)).fetchall()
        od = db.execute("SELECT product,sku,status,created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 20", (uid,)).fetchall()
    feed = [{"kind": "tx", "text": f"{r[0]} ({r[1]:,} ل.س)", "date": str(r[2])} for r in tx]
    feed += [{"kind": "order", "text": f"{r[0]} — {r[1]} [{r[2]}]", "date": str(r[3])} for r in od]
    return jsonify(sorted(feed, key=lambda x: x["date"], reverse=True)[:30])

@app.get("/api/user/referral")
@require_auth
def referral():
    uid = int(request.wu["site_user_id"] if "site_user_id" in request.wu.keys() else request.wu[4])
    with get_db() as db:
        r = db.execute("SELECT code,uses FROM referrals WHERE owner_id=?", (uid,)).fetchone()
        if not r:
            code = f"REF-{uid}-{secrets.token_hex(2).upper()}"
            db.execute("INSERT INTO referrals(code,owner_id) VALUES(?,?)", (code, uid)); r = (code, 0)
    base = request.url_root.rstrip("/")
    return jsonify({"code": r[0], "link": f"{base}/register.html?ref={r[0]}", "uses": r[1], "earnings_syp": r[1] * 5000})

@app.get("/api/notifications")
@require_auth
def notifs():
    uid = int(request.wu["site_user_id"] if "site_user_id" in request.wu.keys() else request.wu[4])
    with get_db() as db:
        rows = db.execute("SELECT id,title,message,kind,is_read,created_at FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 30", (uid,)).fetchall()
        un = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (uid,)).fetchone()[0]
    return jsonify({"unread": un, "items": [{"id": r[0], "title": r[1], "message": r[2], "kind": r[3], "is_read": bool(r[4]), "created_at": str(r[5])} for r in rows]})

@app.post("/api/notifications/mark-read")
@require_auth
def notifs_read():
    uid = int(request.wu["site_user_id"] if "site_user_id" in request.wu.keys() else request.wu[4])
    with get_db() as db: db.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (uid,))
    return jsonify({"message": "تم ✅"})

# ---- reseller ----
@app.get("/api/user/api")
@require_auth
def mykey():
    u = get_web_by_id(int(request.wu["id"] if "id" in request.wu.keys() else request.wu[0]))
    k = u["api_key"] if "api_key" in u.keys() else u[6]
    if not k:
        k = gen_key()
        with get_db() as db: db.execute("UPDATE web_users SET api_key=?,api_enabled=1 WHERE id=?", (k, int(u["id"] if "id" in u.keys() else u[0])))
    en = u["api_enabled"] if "api_enabled" in u.keys() else u[7]
    ips = u["allowed_ips"] if "allowed_ips" in u.keys() else ""
    return jsonify({"api_key": k, "enabled": bool(en), "allowed_ips": ips or ""})

@app.post("/api/user/api/regenerate")
@require_auth
def regen():
    k = gen_key(); wid = int(request.wu["id"] if "id" in request.wu.keys() else request.wu[0])
    with get_db() as db: db.execute("UPDATE web_users SET api_key=?,api_enabled=1 WHERE id=?", (k, wid))
    return jsonify({"api_key": k})

def _key_user():
    key = request.headers.get("X-Api-Key") or request.args.get("api_key") or ""
    if not key: return None
    with get_db() as db:
        return db.execute("SELECT * FROM web_users WHERE api_key=? AND api_enabled=1", (key,)).fetchone()

@app.get("/api/v1/products")
def v1_products():
    if not _key_user(): return jsonify({"message": "مفتاح API غير صالح"}), 401
    with get_db() as db:
        secs = db.execute("SELECT id,name FROM sections WHERE is_active=1 ORDER BY sort_order").fetchall()
        out = []
        for s in secs:
            prods = db.execute("SELECT id,name,public_id FROM products WHERE category=?", (s[1],)).fetchall()
            plist = []
            for p in prods:
                sk = db.execute("SELECT id,name,price,public_id FROM skus WHERE product_id=?", (p[0],)).fetchall()
                plist.append({"id": p[0], "public_id": p[2] or str(p[0]), "name": p[1],
                              "skus": [{"id": x[0], "public_id": x[3] or str(x[0]), "name": x[1], "price_usd": x[2]} for x in sk]})
            out.append({"id": s[0], "name": s[1], "products": plist})
    return jsonify(out)

@app.post("/api/v1/order")
def v1_order():
    ku = _key_user()
    if not ku: return jsonify({"message": "مفتاح API غير صالح"}), 401
    b = request.get_json(force=True, silent=True) or {}
    sku_id = b.get("category_id") or b.get("sku_id"); player = (b.get("player") or "").strip(); qty = int(b.get("qty") or 1)
    uid = int(ku["site_user_id"] if "site_user_id" in ku.keys() else ku[4])
    with get_db() as db:
        try: s = db.execute("SELECT id,product_id,name,price,cost FROM skus WHERE id=?", (sku_id,)).fetchone()
        except Exception: s = db.execute("SELECT id,product_id,name,price FROM skus WHERE id=?", (sku_id,)).fetchone()
        if not s: return jsonify({"message": "sku غير موجود"}), 404
        cost = float(s[3]) * qty; bal = balance_of(uid)
        if bal < int(cost * rate()): return jsonify({"message": "رصيد غير كافٍ"}), 402
        _ptok, _purl, _ppid = sku_provider(s[0])
        ok, porder, resp = provider_buy(s, player, qty, _ptok, _purl, _ppid)
        _vst = "completed" if ok else ("pending" if _ptok else "failed")
        db.execute("UPDATE balances SET balance=balance-? WHERE user_id=?", (int(cost * rate()), uid))
        _vcost = float(s[4] if len(s) > 4 and s[4] else cost / max(qty, 1)) * qty
        oid = _insert_order(db, uid, "API", s[2], cost, int(cost * rate()), player, qty, _vst, porder, resp, b.get("order_uuid") or "", _vcost)
    return jsonify({"order_id": oid, "status": _vst, "provider_order": porder})

# ================= ADMIN =================
@app.post("/api/admin/login")
@limiter.limit("10 per minute")
def alogin():
    b = request.get_json(force=True, silent=True) or {}
    pw = b.get("password") or ""
    eff = get_setting("admin_password_hash", "")
    ok = check_password_hash(eff, pw) if eff else hmac.compare_digest(pw, ADMIN_PASSWORD)
    if not ok: return jsonify({"message": "كلمة المرور غير صحيحة"}), 401
    return jsonify({"token": issue_token(None, admin=True, owner=True), "owner": True})

@app.get("/api/admin/stats")
@require_admin
def astats():
    r = rate()
    with get_db() as db:
        users = db.execute("SELECT COUNT(*) FROM web_users").fetchone()[0]
        orders = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        try: bal = db.execute("SELECT COALESCE(SUM(balance),0) FROM balances").fetchone()[0] or 0
        except Exception: bal = 0
        try:
            if USE_PG: t = db.execute("SELECT COALESCE(SUM(price_usd),0),COUNT(*),COALESCE(SUM(cost_usd),0) FROM orders WHERE status='completed' AND created_at::date=CURRENT_DATE").fetchone()
            else: t = db.execute("SELECT COALESCE(SUM(price_usd),0),COUNT(*),COALESCE(SUM(cost_usd),0) FROM orders WHERE status='completed' AND date(created_at)=date('now')").fetchone()
        except Exception: t = (0, 0, 0)
        try: pend_dep = db.execute("SELECT COUNT(*) FROM deposit_requests WHERE status='pending'").fetchone()[0]
        except Exception: pend_dep = 0
    sales, cnt, cost = float(t[0] or 0), int(t[1] or 0), float(t[2] or 0)
    profit = sales - cost
    return jsonify({"users": users, "orders": orders, "revenue_syp": int(bal),
                    "pending_deposits": pend_dep, "exchange_rate": r,
                    "total_users": users, "total_orders": orders, "total_balance_syp": int(bal),
                    "today_sales_usd": round(sales, 2), "today_orders": cnt,
                    "today_profit_usd": round(profit, 2),
                    "today_margin_percent": round(profit / sales * 100, 1) if sales else 0})

@app.get("/api/admin/orders")
@require_admin
def aorders():
    with get_db() as db:
        try: rows = db.execute("SELECT id,user_id,product,sku,price_usd,price_syp,player,qty,status,provider_order,created_at,kind FROM orders ORDER BY id DESC LIMIT 200").fetchall()
        except Exception: rows = db.execute("SELECT id,user_id,product,sku,price_usd,price_syp,player,qty,status,provider_order,created_at FROM orders ORDER BY id DESC LIMIT 200").fetchall()
    out = []
    for r in rows:
        kind = r[11] if len(r) > 11 else "shop"
        out.append({"id": r[0], "ref": f"S{r[0]}", "source": kind, "user_id": r[1],
                    "product": r[2], "product_name": r[2], "sku": r[3], "category": r[3], "category_name": r[3],
                    "price_usd": r[4], "price_syp": r[5], "player": r[6], "player_id": r[6],
                    "qty": r[7], "status": r[8], "raw_status": r[8], "provider_order": r[9], "date": str(r[10]), "created_at": str(r[10])})
    return jsonify(out)

@app.post("/api/admin/orders/<string:ref>/status")
@require_admin
def aorder_st(ref):
    b = request.get_json(force=True, silent=True) or {}
    act = b.get("action") or b.get("status") or ""
    if act == "accept": st = "completed"
    elif act == "reject": st = "failed"
    else: st = act if act in ("completed", "failed", "pending", "processing") else "completed"
    oid = ref[1:] if isinstance(ref, str) and ref.startswith("S") and ref[1:].isdigit() else ref
    with get_db() as db:
        try: o = db.execute("SELECT id,user_id,price_syp,product FROM orders WHERE id=?", (oid,)).fetchone()
        except Exception: o = None
        if not o:
            try: o = db.execute("SELECT id,user_id,price_syp,product FROM orders WHERE provider_order=?", (ref,)).fetchone()
            except Exception: o = None
        if not o: return jsonify({"message": "غير موجود"}), 404
        db.execute("UPDATE orders SET status=? WHERE id=?", (st, o[0]))
        if st == "failed":
            add_balance(o[1], int(o[2] or 0), f"استرجاع رفض طلب {o[3]}")
            notify(o[1], "تم رفض الطلب", "تم استرجاع رصيدك", "error")
        else:
            notify(o[1], "تم قبول طلبك ✅", o[3], "success")
    return jsonify({"message": "تم ✅"})

@app.get("/api/admin/deposits")
@require_admin
def adep():
    with get_db() as db:
        rows = db.execute("SELECT id,user_id,name,method,amount_usd,amount_syp,code,status,created_at FROM deposit_requests ORDER BY id DESC LIMIT 200").fetchall()
    return jsonify([{"id": r[0], "user_id": r[1], "name": r[2], "full_name": r[2], "method": r[3], "method_title": r[3],
                     "amount_usd": r[4], "amount_syp": r[5], "code": r[6], "status": r[7], "date": str(r[8])} for r in rows])

@app.post("/api/admin/deposits/<int:did>/<string:act>")
@require_admin
def adep_act(did, act):
    with get_db() as db:
        d = db.execute("SELECT user_id,amount_syp,method FROM deposit_requests WHERE id=?", (did,)).fetchone()
        if not d: return jsonify({"message": "غير موجود"}), 404
        if act == "accept":
            db.execute("UPDATE deposit_requests SET status='accepted' WHERE id=?", (did,))
            if USE_PG: db.execute("INSERT INTO balances(user_id,balance) VALUES(?,0) ON CONFLICT(user_id) DO NOTHING", (d[0],))
            else: db.execute("INSERT OR IGNORE INTO balances(user_id,balance) VALUES(?,0)", (d[0],))
            db.execute("UPDATE balances SET balance=balance+? WHERE user_id=?", (int(d[1]), d[0]))
            db.execute("INSERT INTO transactions(user_id,type,amount,note) VALUES(?, 'in', ?, ?)", (d[0], int(d[1]), f"قبول إيداع {d[2]}"))
            notify(d[0], "تم قبول إيداعك ✅", d[2], "success")
        else:
            db.execute("UPDATE deposit_requests SET status='rejected' WHERE id=?", (did,))
            notify(d[0], "تم رفض الإيداع", d[2], "error")
    return jsonify({"message": "تم ✅"})

@app.get("/api/admin/users")
@require_admin
def ausers():
    with get_db() as db:
        try: rows = db.execute("SELECT id,name,email,site_user_id,api_key,allowed_ips,api_enabled,preferred_currency,country,phone,created_at,blocked FROM web_users ORDER BY id DESC LIMIT 300").fetchall()
        except Exception: rows = db.execute("SELECT id,name,email,site_user_id,api_enabled,country,phone,created_at FROM web_users ORDER BY id DESC LIMIT 300").fetchall()
        out = []
        for r in rows:
            full = len(r) > 8
            uid = r[3]
            t = db.execute("SELECT tier_id FROM user_tier WHERE user_id=?", (uid,)).fetchone() if uid else None
            out.append({"id": r[0], "web_id": r[0], "name": r[1], "email": r[2], "site_user_id": uid,
                        "balance_syp": balance_of(uid or 0),
                        "api_enabled": bool(r[6] if full else r[4]), "api_key": (r[4] if full else "") or "",
                        "country": r[8] if full else r[5], "phone": r[9] if full else r[6],
                        "date": str(r[10] if full else r[7]),
                        "blocked": bool(r[11]) if full and len(r) > 11 and r[11] is not None else False,
                        "discount_tier_id": int(t[0]) if t else 0})
    return jsonify(out)

@app.post("/api/admin/users/<int:wid>/balance")
@require_admin
def abal(wid):
    b = request.get_json(force=True, silent=True) or {}
    act = (b.get("action") or "").lower()
    if act in ("add", "deduct"):
        amt = int(abs(float(b.get("amount") or 0)))
        if act == "deduct": amt = -amt
    else:
        amt = int(b.get("amount_syp") or b.get("amount") or 0)
    u = get_web_by_id(wid)
    if not u: return jsonify({"message": "غير موجود"}), 404
    uid = int(u["site_user_id"] if "site_user_id" in u.keys() else u[4])
    nb = add_balance(uid, amt, "تعديل أدمن")
    notify(uid, "تعديل رصيد 💰", f"{amt:+,} ل.س", "info")
    return jsonify({"message": "تم ✅", "new_balance_syp": nb})

@app.post("/api/admin/users/<int:wid>/api")
@require_admin
def aapi(wid):
    en = bool((request.get_json(force=True, silent=True) or {}).get("enabled", True))
    with get_db() as db:
        if en:
            k = gen_key(); db.execute("UPDATE web_users SET api_key=?,api_enabled=1 WHERE id=?", (k, wid))
            return jsonify({"message": "تم التفعيل ✅", "api_key": k})
        db.execute("UPDATE web_users SET api_enabled=0 WHERE id=?", (wid,))
    return jsonify({"message": "تم التعطيل"})

# catalog CRUD (sections/products/skus/methods/settings/banners)
def _crud_list(q): 
    with get_db() as db: return db.execute(q).fetchall()

@app.get("/api/admin/sections")
@require_admin
def adm_secs():
    rows = _crud_list("SELECT id,name,color,emoji,image,is_active,sort_order FROM sections ORDER BY sort_order,id")
    out = []
    with get_db() as db:
        for r in rows:
            pc = db.execute("SELECT COUNT(*) FROM products WHERE category=?", (r[1],)).fetchone()[0]
            sc = db.execute("SELECT COUNT(*) FROM subsections WHERE section_id=?", (r[0],)).fetchone()[0]
            out.append({"id": r[0], "name": r[1], "color": r[2], "emoji": r[3], "image": r[4] or "",
                        "active": bool(r[5]), "is_active": bool(r[5]), "sort_order": r[6],
                        "products_count": pc, "subsections_count": sc})
    return jsonify(out)

@app.post("/api/admin/sections")
@require_admin
def adm_secs_add():
    b = request.get_json(force=True, silent=True) or {}
    with get_db() as db:
        db.execute("INSERT INTO sections(name,color,emoji,sort_order) VALUES(?,?,?,?)",
                   (b.get("name", "قسم جديد"), b.get("color", "#7c5cff"), b.get("emoji", "✨"), int(b.get("sort_order") or 0)))
    return jsonify({"message": "تمت الإضافة ✅"})

@app.put("/api/admin/sections/<int:sid>")
@require_admin
def adm_secs_ed(sid):
    b = request.get_json(force=True, silent=True) or {}
    with get_db() as db:
        cur = db.execute("SELECT name,color,emoji,image,is_active,sort_order FROM sections WHERE id=?", (sid,)).fetchone()
        if not cur: return jsonify({"message": "غير موجود"}), 404
        act = b.get("active", b.get("is_active", bool(cur[4])))
        db.execute("UPDATE sections SET name=?,color=?,emoji=?,image=?,is_active=?,sort_order=? WHERE id=?",
                   (b.get("name", cur[0]), b.get("color", cur[1]), b.get("emoji", cur[2]),
                    b.get("image", cur[3] or ""), 1 if act else 0,
                    int(b.get("sort_order", cur[5] or 0)), sid))
    return jsonify({"message": "تم الحفظ ✅"})

@app.delete("/api/admin/sections/<int:sid>")
@require_admin
def adm_secs_del(sid):
    with get_db() as db: db.execute("DELETE FROM sections WHERE id=?", (sid,))
    return jsonify({"message": "تم الحذف"})

@app.get("/api/admin/products")
@require_admin
def adm_prods():
    sec = request.args.get("section", "")
    with get_db() as db:
        rows = db.execute("SELECT id,name,category,emoji,image,sort_order,public_id,subsection_id FROM products ORDER BY id DESC LIMIT 300").fetchall() if not sec else \
               db.execute("SELECT id,name,category,emoji,image,sort_order,public_id,subsection_id FROM products WHERE category=? ORDER BY sort_order", (sec,)).fetchall()
        out = []
        for r in rows:
            cc = db.execute("SELECT COUNT(*) FROM skus WHERE product_id=?", (r[0],)).fetchone()[0]
            sub = ""
            if r[7]:
                s = db.execute("SELECT name FROM subsections WHERE id=?", (r[7],)).fetchone()
                sub = s[0] if s else ""
            out.append({"id": r[0], "name": r[1], "category": r[2], "emoji": r[3], "image": r[4] or "",
                        "sort_order": r[5], "public_id": r[6] or "", "subsection_id": r[7],
                        "subsection_name": sub, "categories_count": cc})
    return jsonify(out)

@app.post("/api/admin/products")
@require_admin
def adm_prods_add():
    b = request.get_json(force=True, silent=True) or {}
    with get_db() as db:
        img = (b.get("image") or "").strip() or branded_image_url(b.get("name", "منتج جديد"))
        db.execute("INSERT INTO products(name,category,emoji,description,image,subsection_id,public_id) VALUES(?,?,?,?,?,?,?)",
                   (b.get("name", "منتج جديد"), b.get("category", ""), b.get("emoji", "🎮"), b.get("description", ""),
                    img, b.get("subsection_id"), str(secrets.randbelow(90000) + 10000)))
    return jsonify({"message": "تمت الإضافة ✅"})

@app.put("/api/admin/products/<int:pid>")
@require_admin
def adm_prods_ed(pid):
    b = request.get_json(force=True, silent=True) or {}
    with get_db() as db:
        cur = db.execute("SELECT name,category,emoji,description,image,sort_order FROM products WHERE id=?", (pid,)).fetchone()
        if not cur: return jsonify({"message": "غير موجود"}), 404
        db.execute("UPDATE products SET name=?,category=?,emoji=?,description=?,image=?,sort_order=? WHERE id=?",
                   (b.get("name", cur[0]), b.get("category", cur[1]), b.get("emoji", cur[2]),
                    b.get("description", cur[3] or ""), b.get("image", cur[4] or ""),
                    int(b.get("sort_order", cur[5] or 0)), pid))
    return jsonify({"message": "تم الحفظ ✅"})

@app.delete("/api/admin/products/<int:pid>")
@require_admin
def adm_prods_del(pid):
    with get_db() as db:
        db.execute("DELETE FROM skus WHERE product_id=?", (pid,)); db.execute("DELETE FROM products WHERE id=?", (pid,))
    return jsonify({"message": "تم الحذف"})

@app.get("/api/admin/products/<int:pid>/skus")
@require_admin
def adm_skus(pid):
    with get_db() as db:
        try: rows = db.execute("SELECT id,name,price,cost,stock_qty,requires_id,public_id,image,min_qty,max_qty,unit_qty,type FROM skus WHERE product_id=?", (pid,)).fetchall()
        except Exception: rows = db.execute("SELECT id,name,price,cost,stock_qty,requires_id FROM skus WHERE product_id=?", (pid,)).fetchall()
    out = []
    for r in rows:
        full = len(r) > 6
        out.append({"id": r[0], "name": r[1], "price": r[2], "price_usd": r[2], "cost": r[3] if full else 0,
                    "stock_qty": r[4] if full else None, "requires_id": bool(r[5]) if full else True,
                    "public_id": (r[6] if full else "") or "", "image": (r[7] if full else "") or "",
                    "min_qty": (r[8] if full else 1) or 1, "max_qty": (r[9] if full else 1) or 1,
                    "unit_qty": (r[10] if full else 1) or 1, "type": (r[11] if full else None) or "fixed"})
    return jsonify(out)

@app.post("/api/admin/products/<int:pid>/skus")
@require_admin
def adm_skus_add(pid):
    b = request.get_json(force=True, silent=True) or {}
    price = float(b.get("price") or 0)
    with get_db() as db:
        db.execute("INSERT INTO skus(product_id,name,price,cost,stock_qty,requires_id,public_id,image,min_qty,max_qty,unit_qty,type) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                   (pid, b.get("name", "باقة"), price, float(b.get("cost", price) or 0),
                    b.get("stock_qty"), 1 if b.get("requires_id", True) else 0, str(secrets.randbelow(90000) + 10000),
                    b.get("image", ""), int(b.get("min_qty") or 1), int(b.get("max_qty") or b.get("min_qty") or 1),
                    int(b.get("unit_qty") or 1), b.get("type", "fixed")))
    return jsonify({"message": "تمت الإضافة ✅"})

@app.put("/api/admin/skus/<int:skid>")
@require_admin
def adm_sku_ed(skid):
    b = request.get_json(force=True, silent=True) or {}
    with get_db() as db:
        try: cur = db.execute("SELECT name,price,cost,stock_qty,requires_id,image,min_qty,max_qty,unit_qty,type FROM skus WHERE id=?", (skid,)).fetchone()
        except Exception: cur = db.execute("SELECT name,price,cost,stock_qty,requires_id FROM skus WHERE id=?", (skid,)).fetchone()
        if not cur: return jsonify({"message": "غير موجود"}), 404
        full = len(cur) > 5
        try:
            db.execute("UPDATE skus SET name=?,price=?,cost=?,stock_qty=?,requires_id=?,image=?,min_qty=?,max_qty=?,unit_qty=?,type=? WHERE id=?",
                       (b.get("name", cur[0]), float(b.get("price", cur[1] or 0) or 0), float(b.get("cost", cur[2] or 0) or 0),
                        b.get("stock_qty", cur[3]), 1 if b.get("requires_id", bool(cur[4])) else 0,
                        b.get("image", (cur[5] if full else "") or ""), int(b.get("min_qty", (cur[6] if full else 1) or 1)),
                        int(b.get("max_qty", (cur[7] if full else 1) or 1)), int(b.get("unit_qty", (cur[8] if full else 1) or 1)),
                        b.get("type", (cur[9] if full else None) or "fixed"), skid))
        except Exception:
            db.execute("UPDATE skus SET name=?,price=?,cost=?,stock_qty=?,requires_id=? WHERE id=?",
                       (b.get("name", cur[0]), float(b.get("price", cur[1] or 0) or 0), float(b.get("cost", cur[2] or 0) or 0),
                        b.get("stock_qty", cur[3]), 1 if b.get("requires_id", bool(cur[4])) else 0, skid))
    return jsonify({"message": "تم الحفظ ✅"})

@app.delete("/api/admin/skus/<int:skid>")
@require_admin
def adm_sku_del(skid):
    with get_db() as db: db.execute("DELETE FROM skus WHERE id=?", (skid,))
    return jsonify({"message": "تم الحذف"})

@app.get("/api/admin/settings")
@require_admin
def adm_set_get():
    with get_db() as db:
        rows = db.execute("SELECT key,value FROM settings").fetchall()
        banners = db.execute("SELECT id,image FROM banners ORDER BY sort_order,id").fetchall()
    d = {r[0]: r[1] for r in rows}
    d["banner_images"] = [{"id": b[0], "image": b[1]} for b in banners]
    return jsonify(d)

@app.post("/api/admin/settings")
@require_admin
def adm_set_save():
    b = request.get_json(force=True, silent=True) or {}
    for k, v in b.items(): set_setting(k, str(v))
    return jsonify({"message": "تم الحفظ ✅"})

@app.get("/api/admin/banners")
@require_admin
def adm_ban():
    with get_db() as db:
        rows = db.execute("SELECT id,image FROM banners ORDER BY sort_order,id").fetchall()
    return jsonify([{"id": r[0], "image": r[1]} for r in rows])

@app.post("/api/admin/banners")
@require_admin
def adm_ban_add():
    img = ""
    if "image" in request.files: img = save_upload(request.files["image"]) or ""
    else: img = (request.get_json(force=True, silent=True) or {}).get("image", "")
    if not img: return jsonify({"message": "أرفق صورة"}), 400
    with get_db() as db: db.execute("INSERT INTO banners(image) VALUES(?)", (img,))
    return jsonify({"message": "تمت الإضافة ✅", "image": img})

@app.delete("/api/admin/banners/<int:bid>")
@require_admin
def adm_ban_del(bid):
    with get_db() as db: db.execute("DELETE FROM banners WHERE id=?", (bid,))
    return jsonify({"message": "تم الحذف"})

@app.post("/api/admin/upload")
@require_admin
def adm_up():
    if "file" not in request.files: return jsonify({"message": "لا يوجد ملف"}), 400
    url = save_upload(request.files["file"])
    if not url: return jsonify({"message": "صيغة غير مدعومة (png/jpg/webp/gif)"}), 400
    return jsonify({"url": url})

# ================= ADMIN الموسّع: كل مميزات النسخة الأصلية =================
# --- الأقسام الفرعية ---
@app.get("/api/admin/subsections")
@require_admin
def adm_sub_list():
    sid = request.args.get("section_id", type=int)
    with get_db() as db:
        rows = db.execute("SELECT id,section_id,name,emoji,image,is_active,sort_order FROM subsections ORDER BY sort_order,id").fetchall() if not sid else \
               db.execute("SELECT id,section_id,name,emoji,image,is_active,sort_order FROM subsections WHERE section_id=? ORDER BY sort_order,id", (sid,)).fetchall()
        out = []
        for r in rows:
            pc = db.execute("SELECT COUNT(*) FROM products WHERE subsection_id=?", (r[0],)).fetchone()[0]
            out.append({"id": r[0], "section_id": r[1], "name": r[2], "emoji": r[3], "image": r[4] or "",
                        "active": bool(r[5]), "is_active": bool(r[5]), "sort_order": r[6], "products_count": pc})
    return jsonify(out)

@app.post("/api/admin/subsections")
@require_admin
def adm_sub_add():
    b = request.get_json(force=True, silent=True) or {}
    if not b.get("section_id"): return jsonify({"message": "اختر القسم الرئيسي"}), 400
    with get_db() as db:
        db.execute("INSERT INTO subsections(section_id,name,emoji,image) VALUES(?,?,?,?)",
                   (b.get("section_id"), b.get("name", "قسم فرعي"), b.get("emoji", "📦"), b.get("image", "")))
    return jsonify({"message": "تمت الإضافة ✅"})

@app.put("/api/admin/subsections/<int:subid>")
@require_admin
def adm_sub_ed(subid):
    b = request.get_json(force=True, silent=True) or {}
    with get_db() as db:
        cur = db.execute("SELECT name,emoji,image,is_active,sort_order FROM subsections WHERE id=?", (subid,)).fetchone()
        if not cur: return jsonify({"message": "غير موجود"}), 404
        act = b.get("active", b.get("is_active", bool(cur[3])))
        db.execute("UPDATE subsections SET name=?,emoji=?,image=?,is_active=?,sort_order=? WHERE id=?",
                   (b.get("name", cur[0]), b.get("emoji", cur[1]), b.get("image", cur[2] or ""),
                    1 if act else 0, int(b.get("sort_order", cur[4] or 0)), subid))
    return jsonify({"message": "تم الحفظ ✅"})

@app.delete("/api/admin/subsections/<int:subid>")
@require_admin
def adm_sub_del(subid):
    with get_db() as db: db.execute("DELETE FROM subsections WHERE id=?", (subid,))
    return jsonify({"message": "تم الحذف"})

# --- مستويات الخصم (VIP) ---
@app.get("/api/admin/tiers")
@require_admin
def adm_tiers():
    with get_db() as db:
        try: rows = db.execute("SELECT id,name,percent,min_spent,sort_order FROM tiers ORDER BY sort_order,percent").fetchall()
        except Exception: rows = db.execute("SELECT id,name,percent,min_spent FROM tiers ORDER BY percent").fetchall()
    return jsonify([{"id": r[0], "name": r[1], "percent": r[2], "min_spent": r[3], "sort_order": (r[4] if len(r) > 4 else 0) or 0} for r in rows])

@app.post("/api/admin/tiers")
@require_admin
def adm_tiers_add():
    b = request.get_json(force=True, silent=True) or {}
    with get_db() as db:
        try:
            db.execute("INSERT INTO tiers(name,percent,min_spent,sort_order) VALUES(?,?,?,?)",
                       (b.get("name", "VIP"), float(b.get("percent") or 0), float(b.get("min_spent") or 0), int(b.get("sort_order") or 0)))
        except Exception:
            db.execute("INSERT INTO tiers(name,percent,min_spent) VALUES(?,?,?)",
                       (b.get("name", "VIP"), float(b.get("percent") or 0), float(b.get("min_spent") or 0)))
    return jsonify({"message": "تمت الإضافة ✅"})

@app.put("/api/admin/tiers/<int:tid>")
@require_admin
def adm_tier_ed(tid):
    b = request.get_json(force=True, silent=True) or {}
    with get_db() as db:
        cur = db.execute("SELECT name,percent,min_spent FROM tiers WHERE id=?", (tid,)).fetchone()
        if not cur: return jsonify({"message": "غير موجود"}), 404
        try:
            so = db.execute("SELECT sort_order FROM tiers WHERE id=?", (tid,)).fetchone()[0]
            db.execute("UPDATE tiers SET name=?,percent=?,min_spent=?,sort_order=? WHERE id=?",
                       (b.get("name", cur[0]), float(b.get("percent", cur[1]) or 0), float(b.get("min_spent", cur[2]) or 0), int(b.get("sort_order", so or 0)), tid))
        except Exception:
            db.execute("UPDATE tiers SET name=?,percent=?,min_spent=? WHERE id=?",
                       (b.get("name", cur[0]), float(b.get("percent", cur[1]) or 0), float(b.get("min_spent", cur[2]) or 0), tid))
    return jsonify({"message": "تم الحفظ ✅"})

@app.delete("/api/admin/tiers/<int:tid>")
@require_admin
def adm_tier_del(tid):
    with get_db() as db:
        db.execute("DELETE FROM user_tier WHERE tier_id=?", (tid,)); db.execute("DELETE FROM tiers WHERE id=?", (tid,))
    return jsonify({"message": "تم الحذف"})

@app.post("/api/admin/users/<int:wid>/tier")
@require_admin
def adm_user_tier(wid):
    b = request.get_json(force=True, silent=True) or {}
    tid = b.get("tier_id")
    u = get_web_by_id(wid)
    if not u: return jsonify({"message": "غير موجود"}), 404
    uid = int(u["site_user_id"] if "site_user_id" in u.keys() else u[4])
    with get_db() as db:
        if tid:
            if USE_PG: db.execute("INSERT INTO user_tier(user_id,tier_id) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET tier_id=excluded.tier_id", (uid, tid))
            else: db.execute("INSERT INTO user_tier(user_id,tier_id) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET tier_id=excluded.tier_id", (uid, tid))
            notify(uid, "مستوى خصم جديد 🎖️", "تم تفعيل خصم خاص لحسابك", "success")
        else:
            db.execute("DELETE FROM user_tier WHERE user_id=?", (uid,))
    return jsonify({"message": "تم ✅"})

# --- تفاصيل المستخدم + حظر ---
@app.get("/api/admin/users/<int:wid>/details")
@require_admin
def adm_user_details(wid):
    u = get_web_by_id(wid)
    if not u: return jsonify({"message": "غير موجود"}), 404
    uid = int(u["site_user_id"] if "site_user_id" in u.keys() else u[4])
    email = u["email"] if "email" in u.keys() else u[2]
    name = u["name"] if "name" in u.keys() else u[1]
    r = rate()
    with get_db() as db:
        orders = db.execute("SELECT id,product,qty,price_usd,price_syp,status,created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 20", (uid,)).fetchall()
        spent = db.execute("SELECT COALESCE(SUM(price_usd),0),COUNT(*),COALESCE(SUM(price_usd-cost_usd),0) FROM orders WHERE user_id=? AND status='completed'", (uid,)).fetchone()
    bal = balance_of(uid)
    return jsonify({"name": name, "email": email, "balance_usd": round(bal / r, 2) if r else 0,
                    "total_orders": int(spent[1] or 0), "total_spent_usd": round(float(spent[0] or 0), 2),
                    "total_profit_usd": round(float(spent[2] or 0), 4),
                    "recent_orders": [{"id": x[0], "product_name": x[1], "qty": x[2], "price_usd": x[3],
                                       "price_syp": x[4], "status": x[5], "date": str(x[6])} for x in orders]})

@app.post("/api/admin/users/<int:wid>/block")
@require_admin
def adm_user_block(wid):
    blocked = bool((request.get_json(force=True, silent=True) or {}).get("blocked", True))
    with get_db() as db: db.execute("UPDATE web_users SET blocked=? WHERE id=?", (1 if blocked else 0, wid))
    return jsonify({"message": "تم الحظر 🚫" if blocked else "تم فك الحظر ✅"})

# --- طرق الإيداع CRUD ---
@app.post("/api/admin/deposit-methods/manual")
@require_admin
def adm_dm_add():
    b = request.get_json(force=True, silent=True) or {}
    with get_db() as db:
        db.execute("INSERT INTO deposit_manual(title,description,code,image,input_currency) VALUES(?,?,?,?,?)",
                   (b.get("title", "طريقة جديدة"), b.get("description", ""), b.get("code", ""), b.get("image", ""), b.get("input_currency", "usd")))
    return jsonify({"message": "تمت الإضافة ✅"})

@app.put("/api/admin/deposit-methods/manual/<int:mid>")
@require_admin
def adm_dm_ed(mid):
    b = request.get_json(force=True, silent=True) or {}
    with get_db() as db:
        db.execute("UPDATE deposit_manual SET title=?,description=?,code=?,image=?,input_currency=? WHERE id=?",
                   (b.get("title"), b.get("description", ""), b.get("code", ""), b.get("image", ""), b.get("input_currency", "usd"), mid))
    return jsonify({"message": "تم الحفظ ✅"})

@app.delete("/api/admin/deposit-methods/manual/<int:mid>")
@require_admin
def adm_dm_del(mid):
    with get_db() as db: db.execute("DELETE FROM deposit_manual WHERE id=?", (mid,))
    return jsonify({"message": "تم الحذف"})

@app.post("/api/admin/deposit-methods/auto")
@require_admin
def adm_da_add():
    b = request.get_json(force=True, silent=True) or {}
    with get_db() as db:
        db.execute("INSERT INTO deposit_auto(title,description,code,api_token,api_url,image,gateway,input_currency) VALUES(?,?,?,?,?,?,?,?)",
                   (b.get("title", "طريقة تلقائية"), b.get("description", ""), b.get("code", ""),
                    b.get("api_token", ""), b.get("api_url", ""), b.get("image", ""),
                    b.get("gateway_type") or b.get("gateway", "verify"), b.get("input_currency", "usd")))
    return jsonify({"message": "تمت الإضافة ✅"})

@app.put("/api/admin/deposit-methods/auto/<int:mid>")
@require_admin
def adm_da_ed(mid):
    b = request.get_json(force=True, silent=True) or {}
    with get_db() as db:
        cur = db.execute("SELECT title,description,code,api_token,api_url,image,gateway,input_currency FROM deposit_auto WHERE id=?", (mid,)).fetchone()
        if not cur: return jsonify({"message": "غير موجود"}), 404
        db.execute("UPDATE deposit_auto SET title=?,description=?,code=?,api_token=?,api_url=?,image=?,gateway=?,input_currency=? WHERE id=?",
                   (b.get("title", cur[0]), b.get("description", cur[1] or ""), b.get("code", cur[2] or ""),
                    b.get("api_token", cur[3] or ""), b.get("api_url", cur[4] or ""), b.get("image", cur[5] or ""),
                    b.get("gateway_type") or b.get("gateway", cur[6] or "verify"), b.get("input_currency", cur[7] or "usd"), mid))
    return jsonify({"message": "تم الحفظ ✅"})

@app.delete("/api/admin/deposit-methods/auto/<int:mid>")
@require_admin
def adm_da_del(mid):
    with get_db() as db: db.execute("DELETE FROM deposit_auto WHERE id=?", (mid,))
    return jsonify({"message": "تم الحذف"})

# --- وضع الصيانة ---
@app.get("/api/admin/maintenance")
@require_admin
def adm_maint_get():
    en = get_setting("maintenance_enabled", "false") == "true"
    ends = get_setting("maintenance_ends_at", "") or ""
    left = 0
    if en and ends:
        try: left = max(0, int((datetime.fromisoformat(ends) - datetime.now()).total_seconds()))
        except Exception: left = 0
    return jsonify({"enabled": en, "ends_at": ends or None, "seconds_left": left})

@app.post("/api/admin/maintenance")
@require_admin
def adm_maint_set():
    b = request.get_json(force=True, silent=True) or {}
    en = bool(b.get("enabled"))
    if en:
        ends = datetime.now() + timedelta(hours=float(b.get("hours") or 1))
        set_setting("maintenance_enabled", "true"); set_setting("maintenance_ends_at", ends.isoformat())
    else:
        set_setting("maintenance_enabled", "false")
    return jsonify({"message": "تم الحفظ ✅"})

# --- المشرفون (web_admins) ---
@app.get("/api/admin/web-admins")
@require_admin
def adm_wa_list():
    owner = bool((request.ap or {}).get("owner"))
    with get_db() as db:
        try: rows = db.execute("SELECT email,added_at FROM web_admins").fetchall()
        except Exception: rows = db.execute("SELECT email FROM web_admins").fetchall()
    admins = [{"email": e} for e in OWNER_EMAILS]
    for r in rows:
        if r[0].lower() not in OWNER_EMAILS:
            admins.append({"email": r[0], "owner": False, "added_at": str(r[1]) if len(r) > 1 and r[1] else "",
                           "removable": owner})
    for a in admins:
        a.setdefault("owner", a["email"].lower() in OWNER_EMAILS)
        a.setdefault("added_at", "")
        a.setdefault("removable", False if a["owner"] else owner)
    return jsonify({"is_owner": owner, "admins": admins})

@app.post("/api/admin/web-admins")
@require_admin
def adm_wa_add():
    email = ((request.get_json(force=True, silent=True) or {}).get("email") or "").strip().lower()
    if not email or "@" not in email: return jsonify({"message": "بريد غير صالح"}), 400
    with get_db() as db:
        if USE_PG: db.execute("INSERT INTO web_admins(email) VALUES(?) ON CONFLICT DO NOTHING", (email,))
        else: db.execute("INSERT OR IGNORE INTO web_admins(email) VALUES(?)", (email,))
    return jsonify({"message": "تمت الإضافة ✅"})

@app.delete("/api/admin/web-admins/<string:email>")
@require_admin
def adm_wa_del(email):
    if not (request.ap or {}).get("owner"):
        return jsonify({"message": "هذا الإجراء مسموح للمالك فقط"}), 403
    with get_db() as db: db.execute("DELETE FROM web_admins WHERE email=?", (email.lower(),))
    return jsonify({"message": "تم الحذف"})

# --- الأرباح ---
@app.get("/api/admin/profits")
@require_admin
def adm_profits():
    start = request.args.get("start") or ""
    end = request.args.get("end") or ""
    cond, params = "status='completed'", []
    if start:
        cond += " AND date(created_at)>=date(?)"; params.append(start)
    if end:
        cond += " AND date(created_at)<=date(?)"; params.append(end)
    with get_db() as db:
        try:
            rows = db.execute(f"SELECT id,kind,product,sku,price_usd,cost_usd,created_at FROM orders WHERE {cond} ORDER BY id DESC LIMIT 500", params).fetchall()
            full = True
        except Exception:
            rows = db.execute(f"SELECT id,product,sku,price_usd,created_at FROM orders WHERE {cond} ORDER BY id DESC LIMIT 500", params).fetchall()
            full = False
    items, sales, cost = [], 0.0, 0.0
    for r in rows:
        if full:
            pr, co = float(r[4] or 0), float(r[5] or 0)
            items.append({"id": r[0], "source": r[1] or "shop",
                          "product_name": r[2], "category_name": r[3],
                          "price_usd": round(pr, 4), "cost_usd": round(co, 4),
                          "profit_usd": round(pr - co, 4), "created_at": str(r[6])})
        else:
            pr = float(r[3] or 0)
            items.append({"id": r[0], "source": "shop", "product_name": r[1], "category_name": r[2],
                          "price_usd": round(pr, 4), "cost_usd": 0, "profit_usd": round(pr, 4), "created_at": str(r[4])})
        sales += pr; cost += co if full else 0
    return jsonify({"summary": {"total_orders": len(items), "total_sales_usd": round(sales, 2),
                                "total_cost_usd": round(cost, 2), "total_profit_usd": round(sales - cost, 2)},
                    "orders": items})

@app.get("/api/admin/deposit-methods")
@require_admin
def adm_dm():
    with get_db() as db:
        man = db.execute("SELECT id,title,description,code,rate,image,input_currency FROM deposit_manual").fetchall()
        auto = db.execute("SELECT id,title,description,code,rate,api_token,api_url,image,gateway,input_currency FROM deposit_auto").fetchall()
    return jsonify({"manual": [{"id": r[0], "title": r[1], "description": r[2] or "", "code": r[3] or "", "rate": r[4] or 0, "image": r[5] or "", "input_currency": (r[6] or "usd")} for r in man],
                    "auto": [{"id": r[0], "title": r[1], "description": r[2] or "", "code": r[3] or "", "rate": r[4] or 0,
                              "api_token": r[5] or "", "api_url": r[6] or "", "image": r[7] or "",
                              "gateway_type": r[8] or "verify", "input_currency": (r[9] or "usd")} for r in auto]})

# ================= توافق كامل مع واجهة النسخة الأصلية =================
EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS link_codes(code TEXT PRIMARY KEY, web_user_id INTEGER, expires_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS push_subscriptions(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, endpoint TEXT UNIQUE, p256dh TEXT, auth TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS providers(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, token TEXT DEFAULT '', url TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS category_links(category_id INTEGER PRIMARY KEY, provider_id INTEGER, provider_product TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS import_batches(id TEXT PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, items INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS import_items(batch_id TEXT, kind TEXT, ref_id INTEGER);
CREATE TABLE IF NOT EXISTS bot_admins(user_id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS auth_tokens(token TEXT PRIMARY KEY, web_id INTEGER, is_admin INTEGER DEFAULT 0, is_owner INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY, reason TEXT DEFAULT '', payload TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
"""
def ensure_extra():
    with get_db() as db:
        for stmt in [s for s in EXTRA_SCHEMA.split(";") if s.strip()]:
            try: db.execute(stmt)
            except Exception: pass
try:
    ensure_extra()
except Exception as e:
    print(f"WARNING: ensure_extra failed: {e}")

def _key_user_client():
    key = request.headers.get("api-token") or request.headers.get("X-Api-Key") or request.args.get("api_key") or ""
    if not key: return None
    with get_db() as db:
        return db.execute("SELECT * FROM web_users WHERE api_key=? AND api_enabled=1", (key,)).fetchone()

def _sku_public_rows(product_ids=None):
    with get_db() as db:
        if product_ids:
            ph = ",".join(["?"] * len(product_ids))
            prods = db.execute(f"SELECT id,name,public_id FROM products WHERE public_id IN ({ph}) OR id IN ({ph})", (*product_ids, *product_ids)).fetchall()
        else:
            prods = db.execute("SELECT id,name,public_id FROM products").fetchall()
        out = []
        for p in prods:
            skus = db.execute("SELECT id,name,price,public_id,stock_qty,requires_id,min_qty,max_qty FROM skus WHERE product_id=?", (p[0],)).fetchall()
            for x in skus:
                out.append({"id": x[3] or str(x[0]), "name": x[1], "price": float(x[2] or 0),
                            "params": ["Enter Player ID"] if x[5] else [], "category_name": p[1],
                            "available": (x[4] is None or int(x[4]) > 0),
                            "qty_values": {"min": x[6] or 1, "max": x[7] or 1},
                            "product_type": "amount", "parent_id": p[2] or str(p[0]),
                            "_sku": x[0], "_product": p[0]})
    return out

# --- استعادة كلمة المرور ---
@app.post("/api/auth/forgot-password")
@limiter.limit("6 per hour")
def forgot_pw():
    email = ((request.get_json(force=True, silent=True) or {}).get("email") or "").strip().lower()
    w = get_web_by_email(email)
    if not w: return jsonify({"message": "هذا البريد غير مسجّل"}), 404
    code = "".join(secrets.choice(string.digits) for _ in range(6))
    with get_db() as db:
        exp = (datetime.now() + timedelta(minutes=15)).isoformat()
        if USE_PG: db.execute("INSERT INTO link_codes(code,web_user_id,expires_at) VALUES(?,?,?) ON CONFLICT(code) DO UPDATE SET web_user_id=excluded.web_user_id,expires_at=excluded.expires_at", (code, int(w["id"] if "id" in w.keys() else w[0]), exp))
        else: db.execute("INSERT OR REPLACE INTO link_codes(code,web_user_id,expires_at) VALUES(?,?,?)", (code, int(w["id"] if "id" in w.keys() else w[0]), exp))
    return jsonify({"message": f"كود التحقق الخاص بك: {code} (صالح 15 دقيقة)"})

@app.post("/api/auth/reset-password")
def reset_pw():
    b = request.get_json(force=True, silent=True) or {}
    code, new = (b.get("code") or "").strip(), b.get("new_password") or ""
    if len(new) < 6: return jsonify({"message": "كلمة المرور 6 أحرف على الأقل"}), 400
    with get_db() as db:
        r = db.execute("SELECT web_user_id,expires_at FROM link_codes WHERE code=?", (code,)).fetchone()
        if not r: return jsonify({"message": "الكود غير صحيح"}), 400
        try: valid = datetime.fromisoformat(str(r[1])) > datetime.now()
        except Exception: valid = False
        if not valid:
            db.execute("DELETE FROM link_codes WHERE code=?", (code,))
            return jsonify({"message": "الكود منتهي الصلاحية"}), 400
        db.execute("UPDATE web_users SET password_hash=? WHERE id=?", (generate_password_hash(new), r[0]))
        db.execute("DELETE FROM link_codes WHERE code=?", (code,))
    return jsonify({"message": "تم تعيين كلمة مرور جديدة ✅"})

@app.get("/api/auth/admin-auto-login")
@require_auth
def admin_auto():
    email = request.wu["email"] if "email" in request.wu.keys() else request.wu[2]
    if not is_admin(email): return jsonify({"message": "غير مصرح"}), 403
    return jsonify({"token": issue_token(None, admin=True, owner=(email or "").lower() in OWNER_EMAILS), "owner": (email or "").lower() in OWNER_EMAILS})

# --- إشعارات الأدمن + push ---
@app.get("/api/push/public-key")
def push_key():
    key = os.environ.get("ARAB_VAPID_PUBLIC_KEY", "").strip()
    if not key:
        return jsonify({"enabled": False, "message": "إشعارات الخلفية غير مفعّلة بعد"})
    return jsonify({"enabled": True, "public_key": key})

@app.post("/api/push/subscribe")
@require_auth
def push_sub():
    body = request.get_json(force=True, silent=True) or {}
    ep = str(body.get("endpoint") or "")
    ks = body.get("keys") or {}
    if not ep or not ks.get("p256dh") or not ks.get("auth"):
        return jsonify({"message": "بيانات غير صالحة"}), 400
    uid = int(request.wu["site_user_id"] if "site_user_id" in request.wu.keys() else request.wu[4])
    with get_db() as db:
        if USE_PG: db.execute("INSERT INTO push_subscriptions(user_id,endpoint,p256dh,auth) VALUES(?,?,?,?) ON CONFLICT(endpoint) DO UPDATE SET user_id=excluded.user_id,p256dh=excluded.p256dh,auth=excluded.auth", (uid, ep, ks.get("p256dh"), ks.get("auth")))
        else: db.execute("INSERT OR REPLACE INTO push_subscriptions(user_id,endpoint,p256dh,auth) VALUES(?,?,?,?)", (uid, ep, ks.get("p256dh"), ks.get("auth")))
    return jsonify({"message": "تم تفعيل إشعارات الخلفية"})
@app.post("/api/admin/push/subscribe")
@require_admin
def admin_push():
    body = request.get_json(force=True, silent=True) or {}
    ep = str(body.get("endpoint") or "")
    ks = body.get("keys") or {}
    if not ep: return jsonify({"message": "endpoint مطلوب"}), 400
    with get_db() as db:
        if USE_PG: db.execute("INSERT INTO push_subscriptions(user_id,endpoint,p256dh,auth) VALUES(?,?,?,?) ON CONFLICT(endpoint) DO UPDATE SET p256dh=excluded.p256dh", (0, ep, ks.get("p256dh", ""), ks.get("auth", "")))
        else: db.execute("INSERT OR REPLACE INTO push_subscriptions(user_id,endpoint,p256dh,auth) VALUES(?,?,?,?)", (0, ep, ks.get("p256dh", ""), ks.get("auth", "")))
    return jsonify({"message": "تم ✅"})

@app.get("/api/admin/notifications")
@require_admin
def admin_notifs():
    with get_db() as db:
        rows = db.execute("SELECT id,title,message,kind,is_read,created_at FROM notifications WHERE user_id=0 ORDER BY id DESC LIMIT 50").fetchall()
        un = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=0 AND is_read=0").fetchone()[0]
    return jsonify({"unread": un, "items": [{"id": r[0], "title": r[1], "message": r[2], "kind": r[3], "is_read": bool(r[4]), "created_at": str(r[5])} for r in rows]})

@app.post("/api/admin/notifications/mark-read")
@require_admin
def admin_notifs_read():
    with get_db() as db: db.execute("UPDATE notifications SET is_read=1 WHERE user_id=0")
    return jsonify({"message": "تم ✅"})

@app.get("/api/admin/alerts-count")
@require_admin
def alerts_count():
    with get_db() as db:
        pd = db.execute("SELECT COUNT(*) FROM deposit_requests WHERE status='pending'").fetchone()[0]
        po = db.execute("SELECT COUNT(*) FROM orders WHERE status='pending'").fetchone()[0]
        try: un = db.execute("SELECT COUNT(*) FROM notifications WHERE user_id=0 AND is_read=0").fetchone()[0]
        except Exception: un = 0
    return jsonify({"total": int(pd) + int(po) + int(un), "pending_deposits": pd,
                    "pending_orders": po, "pending_shop_orders": po, "unread": un})

@app.post("/api/admin/settings/notify-test")
@require_admin
def notify_test():
    notify(0, "اختبار 🔔", "زر التنبيه يعمل", "info")
    return jsonify({"message": "تم إرسال تنبيه اختبار داخل اللوحة ✅ (لا يوجد بوت تيليجرام مربوط)"})

# --- فواتير الإيداع ---
@app.post("/api/wallet/deposit/create-invoice")
@require_auth
def create_invoice():
    b = request.get_json(force=True, silent=True) or {}
    mid, amount, currency = b.get("method_id"), float(b.get("amount") or 0), (b.get("currency") or "USD").upper()
    if amount <= 0 or currency not in ("USD", "SYP"): return jsonify({"message": "مبلغ/عملة غير صالحة"}), 400
    with get_db() as db:
        m = db.execute("SELECT id,title,api_token,api_url,gateway FROM deposit_auto WHERE id=?", (mid,)).fetchone()
    if not m: return jsonify({"message": "الطريقة غير موجودة"}), 404
    if (m[4] or "verify") != "invoice": return jsonify({"message": "هذه الطريقة لا تدعم الفواتير"}), 400
    if not (m[3] or ""): return jsonify({"message": "بوابة الفواتير غير مربوطة من الأدمن"}), 502
    uid = int(request.wu["site_user_id"] if "site_user_id" in request.wu.keys() else request.wu[4])
    r = rate()
    ausd = amount if currency == "USD" else round(amount / r, 4)
    ref = f"NZ-{uid}-{int(time.time())}"
    try:
        import requests as _rq
        resp = _rq.post((m[3] or "").rstrip("/") + "/invoice", json={"token": m[2], "amount": amount, "currency": currency, "reference": ref}, timeout=20)
        pay = resp.json().get("payment_url") if resp.ok else None
    except Exception: pay = None
    if not pay: return jsonify({"message": "تعذّر إنشاء الفاتورة لدى المزوّد"}), 502
    with get_db() as db:
        db.execute("INSERT INTO deposit_requests(user_id,email,name,method,amount_usd,amount_syp,code,status,invoice_ref) VALUES(?,?,?,?,?,?,?,'pending',?)",
                   (uid, request.wu["email"] if "email" in request.wu.keys() else request.wu[2],
                    request.wu["name"] if "name" in request.wu.keys() else request.wu[1], m[1], ausd, int(ausd * r), ref, ref))
    return jsonify({"message": "تم إنشاء الفاتورة", "payment_url": pay, "invoice_ref": ref})

@app.post("/api/webhooks/deposit-invoice")
def webhook_invoice():
    b = request.get_json(force=True, silent=True) or {}
    ref, status, token = b.get("reference") or b.get("invoice_ref") or "", (b.get("status") or "").lower(), b.get("token") or request.headers.get("X-Api-Key") or ""
    if not ref: return jsonify({"message": "reference مطلوب"}), 400
    with get_db() as db:
        d = db.execute("SELECT id,user_id,amount_syp,method FROM deposit_requests WHERE invoice_ref=? AND status='pending'", (ref,)).fetchone()
        if not d: return jsonify({"message": "لا يوجد طلب مطابق"}), 404
        m = db.execute("SELECT api_token FROM deposit_auto WHERE title=?", (d[3],)).fetchone()
        if not m or not hmac.compare_digest(str(token), str(m[0] or "")): return jsonify({"message": "توكن غير صحيح"}), 401
        if status in ("paid", "success", "completed"):
            db.execute("UPDATE deposit_requests SET status='accepted' WHERE id=?", (d[0],))
            if USE_PG: db.execute("INSERT INTO balances(user_id,balance) VALUES(?,0) ON CONFLICT(user_id) DO NOTHING", (d[1],))
            else: db.execute("INSERT OR IGNORE INTO balances(user_id,balance) VALUES(?,0)", (d[1],))
            db.execute("UPDATE balances SET balance=balance+? WHERE user_id=?", (int(d[2]), d[1]))
            notify(d[1], "تم تأكيد إيداع الفاتورة ✅", d[3], "success")
        else:
            db.execute("UPDATE deposit_requests SET status='rejected' WHERE id=?", (d[0],))
    return jsonify({"message": "تم"})

# --- reseller إضافي ---
@app.post("/api/user/api/ips")
@require_auth
def save_ips():
    ips = ((request.get_json(force=True, silent=True) or {}).get("allowed_ips") or "").strip()[:500]
    wid = int(request.wu["id"] if "id" in request.wu.keys() else request.wu[0])
    with get_db() as db: db.execute("UPDATE web_users SET allowed_ips=? WHERE id=?", (ips, wid))
    return jsonify({"message": "تم الحفظ ✅"})

@app.get("/api/v1/order/<int:oid>")
def v1_order_status(oid):
    ku = _key_user()
    if not ku: return jsonify({"message": "مفتاح API غير صالح"}), 401
    uid = int(ku["site_user_id"] if "site_user_id" in ku.keys() else ku[4])
    with get_db() as db:
        o = db.execute("SELECT id,product,sku,price_usd,status,created_at FROM orders WHERE id=? AND user_id=?", (oid, uid)).fetchone()
    if not o: return jsonify({"message": "غير موجود"}), 404
    return jsonify({"order_id": o[0], "status": o[4], "product": o[1], "sku": o[2], "price_usd": o[3], "date": str(o[5])})

@app.get("/api/products/catalog")
@require_auth
def products_catalog():
    return jsonify([{k: v for k, v in x.items() if not k.startswith("_")} for x in _sku_public_rows()])

# --- client/api (توافق لوحات外) ---
def _client_auth():
    key = request.headers.get("api-token") or request.headers.get("Api-Token") or ""
    if not key: return None, (jsonify({"status": "error", "code": 120, "message": "رمز API مطلوب!"}), 401)
    with get_db() as db:
        u = db.execute("SELECT * FROM web_users WHERE api_key=? AND api_enabled=1", (key,)).fetchone()
    if not u: return None, (jsonify({"status": "error", "code": 121, "message": "خطأ في الرمز المميز"}), 401)
    return u, None

@app.get("/client/api/profile")
def cl_profile():
    u, err = _client_auth()
    if err: return err
    uid = int(u["site_user_id"] if "site_user_id" in u.keys() else u[4])
    return jsonify({"status": "OK", "balance": str(round(balance_of(uid) / rate(), 3)),
                    "email": u["email"] if "email" in u.keys() else u[2]})

@app.get("/client/api/products")
def cl_products():
    u, err = _client_auth()
    if err: return err
    ids = [x for x in (request.args.get("products_id") or "").split(",") if x.strip()]
    rows = _sku_public_rows(ids or None)
    if request.args.get("base") == "1":
        return jsonify([{"id": x["id"], "name": x["name"]} for x in rows])
    return jsonify([{k: v for k, v in x.items() if not k.startswith("_")} for x in rows])

@app.get("/client/api/content/<string:cid>")
def cl_content(cid):
    u, err = _client_auth()
    if err: return err
    with get_db() as db:
        p = db.execute("SELECT id,name,public_id FROM products WHERE public_id=? OR CAST(id AS TEXT)=?", (cid, cid)).fetchone()
        if not p: return jsonify({"status": "error", "code": 114, "message": "فئة غير معروفة"}), 404
        skus = db.execute("SELECT id,name,price,public_id,stock_qty,requires_id,min_qty,max_qty FROM skus WHERE product_id=?", (p[0],)).fetchall()
    return jsonify({"status": "OK", "categories": [{"id": p[2] or str(p[0]), "name": p[1]}],
                    "products": [{"id": x[3] or str(x[0]), "name": x[1], "price": float(x[2] or 0),
                                  "params": ["Enter Player ID"] if x[5] else [], "available": (x[4] is None or int(x[4]) > 0),
                                  "qty_values": {"min": x[6] or 1, "max": x[7] or 1}} for x in skus]})

def _client_place(pid):
    u, err = _client_auth()
    if err: return err
    src = dict(request.args)
    body = request.get_json(force=True, silent=True) or {}
    src.update(body)
    qty = int(src.get("qty") or 1)
    player = str(src.get("playerId") or src.get("player") or "").strip()
    ouuid = str(src.get("order_uuid") or "").strip()
    uid = int(u["site_user_id"] if "site_user_id" in u.keys() else u[4])
    with get_db() as db:
        if ouuid:
            dup = db.execute("SELECT id,status,price_usd,player FROM orders WHERE order_uuid=? AND user_id=?", (ouuid, uid)).fetchone()
            if dup: return jsonify({"status": "OK", "data": {"order_id": f"ID_{dup[0]}", "status": "processing" if dup[1] == "pending" else ("accept" if dup[1] == "completed" else "failed"), "price": dup[2], "data": {"playerId": dup[3]}, "replay_api": []}})
        try: s = db.execute("SELECT id,product_id,name,price,stock_qty,requires_id,min_qty,max_qty,cost FROM skus WHERE public_id=? OR CAST(id AS TEXT)=?", (pid, pid)).fetchone()
        except Exception: s = db.execute("SELECT id,product_id,name,price,stock_qty,requires_id,min_qty,max_qty FROM skus WHERE public_id=? OR CAST(id AS TEXT)=?", (pid, pid)).fetchone()
        if not s: return jsonify({"status": "error", "code": 114, "message": "منتج غير معروف"}), 404
        if s[4] is not None and int(s[4]) < qty: return jsonify({"status": "error", "code": 105, "message": "الكمية غير متوفرة"}), 400
        if qty < (s[6] or 1): return jsonify({"status": "error", "code": 112, "message": "الكمية صغيرة جداً"}), 400
        if qty > (s[7] or 1): return jsonify({"status": "error", "code": 113, "message": "الكمية كبيرة جداً"}), 400
        if s[5] and not player: return jsonify({"status": "error", "code": 114, "message": "playerId مطلوب"}), 400
        cost = float(s[3] or 0) * qty
        if balance_of(uid) < int(cost * rate()): return jsonify({"status": "error", "code": 100, "message": "رصيد غير كافٍ"}), 400
        p = db.execute("SELECT name FROM products WHERE id=?", (s[1],)).fetchone()
        _ptok, _purl, _ppid = sku_provider(s[0])
        ok, porder, resp = provider_buy(s, player, qty, _ptok, _purl, _ppid)
        _cst = "completed" if ok else ("pending" if _ptok else "failed")
        if s[4] is not None: db.execute("UPDATE skus SET stock_qty=stock_qty-? WHERE id=?", (qty, s[0]))
        db.execute("UPDATE balances SET balance=balance-? WHERE user_id=?", (int(cost * rate()), uid))
        _ccost = float(s[8] if len(s) > 8 and s[8] else cost / max(qty, 1)) * qty
        oid = _insert_order(db, uid, p[0] if p else "", s[2], cost, int(cost * rate()), player, qty, _cst, porder, resp, ouuid or f"c-{uid}-{int(time.time())}", _ccost)
    return jsonify({"status": "OK", "data": {"order_id": f"ID_{oid}", "status": "processing" if ok else ("pending" if _cst == "pending" else "failed"), "price": cost, "data": {"playerId": player}, "replay_api": []}})

@app.route("/client/api/newOrder/<string:pid>", methods=["GET", "POST"])
@app.route("/client/api/newOrder/<string:pid>/params", methods=["GET", "POST"])
def cl_new_order(pid): return _client_place(pid)

@app.get("/client/api/check")
def cl_check():
    u, err = _client_auth()
    if err: return err
    uid = int(u["site_user_id"] if "site_user_id" in u.keys() else u[4])
    raw = request.args.get("orders", "[]")
    try: ids = json.loads(raw)
    except Exception: ids = [x.strip() for x in raw.split(",") if x.strip()]
    is_uuid = request.args.get("uuid") == "1"
    out = []
    with get_db() as db:
        for i in ids:
            str(i)
            if is_uuid: o = db.execute("SELECT id,qty,player,created_at,product,price_usd,status,provider_order FROM orders WHERE order_uuid=? AND user_id=?", (str(i), uid)).fetchone()
            else:
                num = str(i).replace("ID_", "")
                o = db.execute("SELECT id,qty,player,created_at,product,price_usd,status,provider_order FROM orders WHERE id=? AND user_id=?", (num, uid)).fetchone()
            if not o: continue
            out.append({"order_id": f"ID_{o[0]}", "quantity": o[1], "data": {"playerId": o[2]}, "created_at": str(o[3]),
                        "product_name": o[4], "price": str(o[5]), "status": "accept" if o[6] == "completed" else ("failed" if o[6] == "failed" else "processing"),
                        "replay_api": [o[7]] if o[7] else []})
    return jsonify({"status": "OK", "data": out})

# --- طلبات المتجر (قبول/رفض/تنفيذ) ---
@app.get("/api/admin/shop-orders")
@require_admin
def adm_shop():
    with get_db() as db:
        rows = db.execute("SELECT o.id,o.user_id,o.product,o.sku,o.price_usd,o.player,o.qty,o.status,o.created_at,w.email FROM orders o LEFT JOIN web_users w ON w.site_user_id=o.user_id ORDER BY o.id DESC LIMIT 200").fetchall()
    return jsonify([{"id": r[0], "user_id": r[1], "email": r[9] or "", "product": r[2], "sku": r[3], "price_usd": r[4], "player": r[5], "qty": r[6], "status": r[7], "date": str(r[8])} for r in rows])

@app.post("/api/admin/shop-orders/<int:oid>/accept")
@require_admin
def adm_shop_acc(oid):
    with get_db() as db:
        o = db.execute("SELECT user_id,product FROM orders WHERE id=?", (oid,)).fetchone()
        if not o: return jsonify({"message": "غير موجود"}), 404
        db.execute("UPDATE orders SET status='completed' WHERE id=?", (oid,))
        notify(o[0], "تم قبول طلبك ✅", o[1], "success")
    return jsonify({"message": "تم القبول ✅"})

@app.post("/api/admin/shop-orders/<int:oid>/reject")
@require_admin
def adm_shop_rej(oid):
    with get_db() as db:
        o = db.execute("SELECT user_id,price_syp,product FROM orders WHERE id=?", (oid,)).fetchone()
        if not o: return jsonify({"message": "غير موجود"}), 404
        db.execute("UPDATE orders SET status='failed' WHERE id=?", (oid,))
        add_balance(o[0], int(o[1] or 0), f"استرجاع رفض طلب {o[2]}")
        notify(o[0], "تم رفض الطلب", "تم استرجاع رصيدك", "error")
    return jsonify({"message": "تم الرفض واسترجاع الرصيد ✅"})

@app.post("/api/admin/shop-orders/<int:oid>/execute")
@require_admin
def adm_shop_exec(oid):
    b = request.get_json(force=True, silent=True) or {}
    with get_db() as db:
        o = db.execute("SELECT player,qty,sku FROM orders WHERE id=?", (oid,)).fetchone()
        if not o: return jsonify({"message": "غير موجود"}), 404
        ok, porder, resp = provider_buy((0, 0, o[2], 0), o[0], o[1] or 1)
        db.execute("UPDATE orders SET status=?,provider_order=?,response=? WHERE id=?", ("completed" if ok else "failed", porder, (resp or "")[:300], oid))
    return jsonify({"message": "تم التنفيذ ✅" if ok else "فشل التنفيذ", "provider_order": porder})

# --- أسماء بديلة لمسارات الأصلي ---
@app.post("/api/admin/users/<int:wid>/api/enable")
@require_admin
def adm_api_en(wid):
    k = gen_key()
    with get_db() as db: db.execute("UPDATE web_users SET api_key=?,api_enabled=1 WHERE id=?", (k, wid))
    return jsonify({"message": "تم التفعيل ✅", "api_key": k})

@app.post("/api/admin/users/<int:wid>/api/disable")
@require_admin
def adm_api_dis(wid):
    with get_db() as db: db.execute("UPDATE web_users SET api_enabled=0 WHERE id=?", (wid,))
    return jsonify({"message": "تم التعطيل"})

@app.post("/api/admin/users/<int:wid>/api/regenerate")
@require_admin
def adm_api_reg(wid):
    k = gen_key()
    with get_db() as db: db.execute("UPDATE web_users SET api_key=?,api_enabled=1 WHERE id=?", (k, wid))
    return jsonify({"message": "تم ✅", "api_key": k})

@app.post("/api/admin/users/<int:wid>/unblock")
@require_admin
def adm_unblock(wid):
    with get_db() as db: db.execute("UPDATE web_users SET blocked=0 WHERE id=?", (wid,))
    return jsonify({"message": "تم فك الحظر ✅"})

@app.post("/api/admin/users/<int:wid>/discount-tier")
@require_admin
def adm_disc_alias(wid): return adm_user_tier(wid)

@app.get("/api/admin/discount-tiers")
@require_admin
def adm_dt(): return adm_tiers()

@app.post("/api/admin/discount-tiers")
@require_admin
def adm_dt_add(): return adm_tiers_add()

@app.put("/api/admin/discount-tiers/<int:tid>")
@require_admin
def adm_dt_ed(tid): return adm_tier_ed(tid)

@app.delete("/api/admin/discount-tiers/<int:tid>")
@require_admin
def adm_dt_del(tid): return adm_tier_del(tid)

# --- ترتيب + أقسام فرعية متداخلة ---
@app.post("/api/admin/sections/reorder")
@require_admin
def adm_sec_reorder():
    ids = (request.get_json(force=True, silent=True) or {}).get("ids") or []
    with get_db() as db:
        for i, sid in enumerate(ids): db.execute("UPDATE sections SET sort_order=? WHERE id=?", (i, sid))
    return jsonify({"message": "تم ✅"})

@app.get("/api/admin/sections/<int:sid>/subsections")
@require_admin
def adm_sec_subs(sid):
    with get_db() as db:
        rows = db.execute("SELECT id,section_id,name,emoji,image,is_active,sort_order FROM subsections WHERE section_id=? ORDER BY sort_order,id", (sid,)).fetchall()
        out = []
        for r in rows:
            pc = db.execute("SELECT COUNT(*) FROM products WHERE subsection_id=?", (r[0],)).fetchone()[0]
            out.append({"id": r[0], "section_id": r[1], "name": r[2], "emoji": r[3], "image": r[4] or "",
                        "active": bool(r[5]), "is_active": bool(r[5]), "sort_order": r[6], "products_count": pc})
    return jsonify(out)

@app.post("/api/admin/sections/<int:sid>/subsections")
@require_admin
def adm_sec_subs_add(sid):
    b = request.get_json(force=True, silent=True) or {}
    with get_db() as db:
        db.execute("INSERT INTO subsections(section_id,name,emoji) VALUES(?,?,?)", (sid, b.get("name", "قسم فرعي"), b.get("emoji", "📦")))
    return jsonify({"message": "تمت الإضافة ✅"})

@app.post("/api/admin/sections/<int:sid>/subsections/reorder")
@require_admin
def adm_sub_reorder(sid):
    ids = (request.get_json(force=True, silent=True) or {}).get("ids") or []
    with get_db() as db:
        for i, x in enumerate(ids): db.execute("UPDATE subsections SET sort_order=? WHERE id=? AND section_id=?", (i, x, sid))
    return jsonify({"message": "تم ✅"})

# --- فئات (skus) بأسماء الأصلي ---
@app.get("/api/admin/products/<int:pid>/categories")
@require_admin
def adm_prod_cats(pid):
    return adm_skus(pid)

@app.post("/api/admin/products/<int:pid>/categories")
@require_admin
def adm_prod_cats_add(pid): return adm_skus_add(pid)

@app.put("/api/admin/categories/<int:cid>")
@require_admin
def adm_cat_ed(cid): return adm_sku_ed(cid)

@app.delete("/api/admin/categories/<int:cid>")
@require_admin
def adm_cat_del(cid): return adm_sku_del(cid)

@app.get("/api/admin/categories/all-pricing")
@require_admin
def adm_all_pricing():
    with get_db() as db:
        rows = db.execute("SELECT s.id,s.name,s.price,s.cost,p.name FROM skus s LEFT JOIN products p ON p.id=s.product_id ORDER BY s.id").fetchall()
    return jsonify([{"id": r[0], "name": r[1], "price": r[2], "cost": r[3], "product": r[4] or ""} for r in rows])

@app.post("/api/admin/categories/apply-margin")
@require_admin
def adm_margin():
    b = request.get_json(force=True, silent=True) or {}
    m = float(b.get("margin_percent") or 0)
    pid = b.get("product_id")
    with get_db() as db:
        if pid: db.execute("UPDATE skus SET price=cost*(1+?/100.0) WHERE product_id=?", (m, pid))
        else: db.execute("UPDATE skus SET price=cost*(1+?/100.0)", (m,))
    return jsonify({"message": f"تم تطبيق هامش {m}% ✅"})

@app.post("/api/admin/categories/<int:cid>/link")
@require_admin
def adm_link(cid):
    b = request.get_json(force=True, silent=True) or {}
    if not b.get("provider_id"): return jsonify({"message": "اختر المزوّد"}), 400
    with get_db() as db:
        if USE_PG: db.execute("INSERT INTO category_links(category_id,provider_id,provider_product) VALUES(?,?,?) ON CONFLICT(category_id) DO UPDATE SET provider_id=excluded.provider_id,provider_product=excluded.provider_product", (cid, b.get("provider_id"), b.get("provider_product", "")))
        else: db.execute("INSERT OR REPLACE INTO category_links(category_id,provider_id,provider_product) VALUES(?,?,?)", (cid, b.get("provider_id"), b.get("provider_product", "")))
    return jsonify({"message": "تم الربط ✅"})

@app.delete("/api/admin/categories/<int:cid>/link")
@require_admin
def adm_unlink(cid):
    with get_db() as db: db.execute("DELETE FROM category_links WHERE category_id=?", (cid,))
    return jsonify({"message": "تم فك الربط"})

# --- المزوّدون ---
@app.get("/api/admin/providers")
@require_admin
def adm_provs():
    with get_db() as db:
        rows = db.execute("SELECT id,name,url,token FROM providers").fetchall()
        out = []
        for r in rows:
            lc = db.execute("SELECT COUNT(*) FROM category_links WHERE provider_id=?", (r[0],)).fetchone()[0]
            out.append({"id": r[0], "name": r[1], "url": r[2] or "", "api_url": r[2] or "",
                        "has_token": bool(r[3]), "linked_products": lc})
    return jsonify(out)

@app.post("/api/admin/providers")
@require_admin
def adm_provs_add():
    b = request.get_json(force=True, silent=True) or {}
    with get_db() as db:
        db.execute("INSERT INTO providers(name,token,url) VALUES(?,?,?)", (b.get("name", "مزوّد"), b.get("token", ""), b.get("url", "")))
    return jsonify({"message": "تمت الإضافة ✅"})

@app.delete("/api/admin/providers/<int:pid>")
@require_admin
def adm_provs_del(pid):
    with get_db() as db:
        db.execute("DELETE FROM category_links WHERE provider_id=?", (pid,)); db.execute("DELETE FROM providers WHERE id=?", (pid,))
    return jsonify({"message": "تم الحذف"})

def _provider_products(prov):
    try:
        import requests as _rq
        r = _rq.post((prov[2] or "").rstrip("/") + "/products", json={"token": prov[1]}, timeout=20)
        if r.ok:
            d = r.json()
            return d if isinstance(d, list) else d.get("products", [])
    except Exception: pass
    return []

@app.get("/api/admin/providers/<int:pid>/products")
@require_admin
def adm_prov_prods(pid):
    with get_db() as db:
        p = db.execute("SELECT id,token,url FROM providers WHERE id=?", (pid,)).fetchone()
    if not p: return jsonify({"message": "غير موجود"}), 404
    return jsonify([{"id": x.get("id", ""), "name": x.get("name", ""), "price": x.get("price", 0)} for x in _provider_products(p)])

@app.get("/api/admin/categories/<int:cid>/link")
@require_admin
def adm_link_get(cid):
    with get_db() as db:
        r = db.execute("SELECT provider_id,provider_product FROM category_links WHERE category_id=?", (cid,)).fetchone()
    if not r: return jsonify({"linked": False})
    return jsonify({"linked": True, "provider_id": r[0], "api_product_id": r[1]})

@app.post("/api/admin/providers/<int:pid>/import-catalog")
@require_admin
def adm_prov_import(pid):
    b = request.get_json(force=True, silent=True) or {}
    margin = float(b.get("margin_percent") or b.get("margin") or 20)
    with get_db() as db:
        p = db.execute("SELECT id,token,url FROM providers WHERE id=?", (pid,)).fetchone()
    if not p: return jsonify({"message": "غير موجود"}), 404
    items = _provider_products(p)
    if not items: return jsonify({"message": "تعذّر جلب كتالوج المزوّد"}), 502
    n = 0
    with get_db() as db:
        for it in items[:200]:
            name, price = it.get("name", "منتج"), float(it.get("price") or 0)
            cur = db.execute("INSERT INTO products(name,category,emoji,image,public_id) VALUES(?,?,?,?,?) RETURNING id" if USE_PG
                             else "INSERT INTO products(name,category,emoji,image,public_id) VALUES(?,?,?,?,?)",
                             (name, "مستورد", "📦", branded_image_url(name), str(secrets.randbelow(90000) + 10000)))
            newpid = cur.fetchone()[0] if USE_PG else cur.lastrowid
            db.execute("INSERT INTO skus(product_id,name,price,cost,public_id) VALUES(?,?,?,?,?)",
                       (newpid, name, round(price * (1 + margin / 100), 4), price, str(secrets.randbelow(90000) + 10000)))
            n += 1
    return jsonify({"message": f"تم استيراد {n} منتج ✅"})

@app.get("/api/admin/providers/<int:pid>/products/export")
@require_admin
def adm_prov_export(pid):
    import csv as _csv, io as _io
    with get_db() as db:
        rows = db.execute("SELECT s.id,s.name,s.price,p.name FROM skus s LEFT JOIN products p ON p.id=s.product_id").fetchall()
    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["id", "sku", "price", "product"])
    w.writerows(rows)
    return app.response_class("\ufeff" + buf.getvalue(), mimetype="text/csv",
                              headers={"Content-Disposition": "attachment; filename=products-export.csv"})

# --- استيراد CSV + التراجع ---
@app.post("/api/admin/catalog/import-csv")
@require_admin
def adm_csv():
    import csv as _csv, io as _io, re as _re
    if "file" not in request.files: return jsonify({"message": "أرفق ملف CSV"}), 400
    raw = request.files["file"].read()
    if not raw: return jsonify({"message": "الملف فارغ"}), 400
    if len(raw) > 5 * 1024 * 1024: return jsonify({"message": "الملف كبير (الحد 5MB)"}), 413
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp1256", "windows-1256", "windows-1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    if text is None: return jsonify({"message": "تعذّر قراءة الملف"}), 400
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines: return jsonify({"message": "الملف فارغ"}), 400
    head = "\n".join(lines[:5])
    delim = ";" if head.count(";") > head.count(",") else ","
    try: rows = list(_csv.DictReader(_io.StringIO(text), delimiter=delim))
    except Exception: return jsonify({"message": "تعذّر تحليل الملف"}), 400
    if not rows: return jsonify({"message": "لا توجد صفوف في الملف"}), 400

    def norm(h): return (h or "").strip().lower().replace("﹕", "").replace(":", "")
    fmap = {norm(k): k for k in (rows[0].keys() or [])}
    def find(*names):
        for n in names:
            if norm(n) in fmap: return fmap[norm(n)]
        return None
    c_prod = find("product", "name", "product name", "المنتج", "اسم المنتج", "المنتجات")
    c_sku = find("sku", "category", "category name", "الباقة", "الفئة", "اسم الباقة", "الخدمة")
    c_price = find("price", "السعر", "سعر", "سعر الباقة", "السعر $")
    c_cost = find("cost", "التكلفة", "تكلفة", "سعر التكلفة")
    c_stock = find("stock", "stock_qty", "المخزون", "مخزون", "الكمية", "الرصيد")
    c_sec = find("section", "القسم", "قسم", "التصنيف", "التصنيف الرئيسي")
    if not c_prod:
        return jsonify({"message": "لم أجد عمود المنتج — الصيغة: product,sku,price (أو بالعربية: المنتج,الباقة,السعر)"}), 400

    def num(v):
        s = str(v or "").strip()
        try:
            return float(s)
        except Exception:
            pass
        m = _re.search(r"\d+(?:[.,]\d+)?", s.replace(",", ".") if delim == ";" else s)
        try: return float(m.group().replace(",", ".")) if m else 0
        except Exception: return 0

    batch = uuid.uuid4().hex[:10]
    imported, dup, skipped_un = 0, 0, 0
    created = []
    SEED_COLORS = ["#7c5cff", "#f6c453", "#22c55e", "#ff1a3c", "#4f8cff", "#2dd4bf"]
    from classify import classify as _classify, section_color as _scolor
    with get_db() as db:
        secs = db.execute("SELECT id,name FROM sections ORDER BY id").fetchall()
        secname = secs[0][1] if secs else "عام"
        def section_for(name):
            name = (name or "").strip() or secname
            r = db.execute("SELECT id,name FROM sections WHERE name=?", (name,)).fetchone()
            if r: return r[1]
            n = db.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
            db.execute("INSERT INTO sections(name,color,emoji,sort_order) VALUES(?,?,?,?)",
                       (name, SEED_COLORS[n % len(SEED_COLORS)], "📦", n))
            return name
        def section_auto(pname, price):
            sec = _classify(pname, price)
            if not sec: return ""
            r = db.execute("SELECT id,name FROM sections WHERE name=?", (sec,)).fetchone()
            if r: return r[1]
            n = db.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
            emo = sec.split(" ", 1)[0] if " " in sec else "📦"
            db.execute("INSERT INTO sections(name,color,emoji,sort_order) VALUES(?,?,?,?)",
                       (sec, _scolor(sec), emo, n))
            return sec
        for row in rows:
            pname = str(row.get(c_prod) or "").strip()
            if not pname: continue
            sname = str(row.get(c_sku) or "").strip() if c_sku else ""
            sname = sname or pname
            if c_sec and str(row.get(c_sec) or "").strip():
                cat = section_for(row.get(c_sec))
            else:
                price0 = num(row.get(c_price)) if c_price else 0
                cat = section_auto(pname, price0)
                if not cat:
                    skipped_un += 1
                    continue
            p = db.execute("SELECT id FROM products WHERE name=?", (pname,)).fetchone()
            if not p:
                img = branded_image_url(pname)
                cur = db.execute("INSERT INTO products(name,category,emoji,image,public_id) VALUES(?,?,?,?,?) RETURNING id" if USE_PG
                                 else "INSERT INTO products(name,category,emoji,image,public_id) VALUES(?,?,?,?,?)",
                                 (pname, cat, "📦", img, str(secrets.randbelow(90000) + 10000)))
                newpid = cur.fetchone()[0] if USE_PG else cur.lastrowid
                created.append(("product", newpid))
                p = (newpid,)
            if db.execute("SELECT 1 FROM skus WHERE product_id=? AND name=?", (p[0], sname)).fetchone():
                dup += 1
                continue
            price = num(row.get(c_price)) if c_price else 0
            costv = num(row.get(c_cost)) if c_cost else price
            stock = None
            if c_stock and str(row.get(c_stock) or "").strip() != "":
                try: stock = int(num(row.get(c_stock)))
                except Exception: stock = None
            cur = db.execute("INSERT INTO skus(product_id,name,price,cost,stock_qty,public_id) VALUES(?,?,?,?,?,?) RETURNING id" if USE_PG
                             else "INSERT INTO skus(product_id,name,price,cost,stock_qty,public_id) VALUES(?,?,?,?,?,?)",
                             (p[0], sname, price, costv, stock, str(secrets.randbelow(90000) + 10000)))
            skid = cur.fetchone()[0] if USE_PG else cur.lastrowid
            created.append(("sku", skid))
            imported += 1
        db.execute("INSERT INTO import_batches(id,items) VALUES(?,?)", (batch, len(created)))
        for kind, ref in created: db.execute("INSERT INTO import_items(batch_id,kind,ref_id) VALUES(?,?,?)", (batch, kind, ref))
    return jsonify({"message": f"تم استيراد {imported} باقة (تخطّي {skipped_un} غير مصنّف)", "batch_id": batch, "skipped_unknown": skipped_un, "skipped_duplicate": dup})

@app.post("/api/admin/providers/import-file")
@require_admin
def adm_prov_import_file():
    """استيراد كتالوج مزوّد من ملف CSV (id,name,price) مع تصنيف تلقائي للأقسام
    وصور تلقائية وربط كل باقة بالمزوّد. الصفوف غير المفهومة تُتخطّى."""
    import csv as _csv, io as _io
    if "file" not in request.files: return jsonify({"message": "أرفق ملف CSV"}), 400
    pname = (request.form.get("name") or "Shams").strip()
    token = (request.form.get("token") or "").strip()
    url = (request.form.get("url") or "").strip().rstrip("/")
    try: margin = float(request.form.get("margin") or 15)
    except Exception: margin = 15
    raw = request.files["file"].read()
    if not raw: return jsonify({"message": "الملف فارغ"}), 400
    if len(raw) > 10 * 1024 * 1024: return jsonify({"message": "الملف كبير (الحد 10MB)"}), 413
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp1256", "windows-1256", "windows-1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    if text is None: return jsonify({"message": "تعذّر قراءة الملف"}), 400
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines: return jsonify({"message": "الملف فارغ"}), 400
    head = "\n".join(lines[:5])
    delim = ";" if head.count(";") > head.count(",") else ","
    try: rows = list(_csv.DictReader(_io.StringIO(text), delimiter=delim))
    except Exception: return jsonify({"message": "تعذّر تحليل الملف"}), 400
    if not rows: return jsonify({"message": "لا توجد صفوف"}), 400

    def norm(h): return (h or "").strip().lower()
    fmap = {norm(k): k for k in (rows[0].keys() or [])}
    def find(*names):
        for n in names:
            if norm(n) in fmap: return fmap[norm(n)]
        return None
    c_id = find("id", "product_id", "المعرف", "الايدي", "أيدي")
    c_name = find("name", "الاسم", "اسم المنتج", "المنتج")
    c_price = find("price", "السعر", "سعر", "cost", "التكلفة")
    if not c_name or not c_price:
        return jsonify({"message": "الأعمدة المطلوبة: id,name,price"}), 400

    from classify import classify, section_color, extract_game, game_style
    grouping = (request.form.get("grouping") or "sections").strip().lower()
    imported, dup, skipped = 0, 0, 0
    skipped_sample, sections_used = [], set()
    with get_db() as db:
        pr = db.execute("SELECT id FROM providers WHERE name=?", (pname,)).fetchone()
        if pr:
            provid = pr[0]
            db.execute("UPDATE providers SET token=?,url=? WHERE id=?", (token, url, provid))
        else:
            cur = db.execute("INSERT INTO providers(name,token,url) VALUES(?,?,?) RETURNING id" if USE_PG
                             else "INSERT INTO providers(name,token,url) VALUES(?,?,?)", (pname, token, url))
            provid = cur.fetchone()[0] if USE_PG else cur.lastrowid
        for row in rows:
            ext_id = str(row.get(c_id) or "").strip() if c_id else ""
            name = str(row.get(c_name) or "").strip()
            try: cost = float(str(row.get(c_price) or "").strip())
            except Exception: cost = 0
            if not name or not ext_id:
                skipped += 1
                continue
            if db.execute("SELECT 1 FROM category_links WHERE provider_id=? AND provider_product=?", (provid, ext_id)).fetchone():
                dup += 1
                continue
            sec = classify(name, cost)
            if not sec:
                skipped += 1
                if len(skipped_sample) < 30: skipped_sample.append(name)
                continue
            game = extract_game(name) if grouping == "game" else ""
            if game:
                secname, emo, color = game, *game_style(game)
            else:
                secname, emo, color = sec, (sec.split(" ", 1)[0] if " " in sec else "📦"), section_color(sec)
            srow = db.execute("SELECT id,name FROM sections WHERE name=?", (secname,)).fetchone()
            if srow:
                secname = srow[1]
            else:
                n0 = db.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
                db.execute("INSERT INTO sections(name,color,emoji,sort_order) VALUES(?,?,?,?)",
                           (secname, color, emo, n0))
            sections_used.add(secname)
            p = db.execute("SELECT id FROM products WHERE name=?", (name,)).fetchone()
            if not p:
                img = branded_image_url(name)
                cur = db.execute("INSERT INTO products(name,category,emoji,image,public_id) VALUES(?,?,?,?,?) RETURNING id" if USE_PG
                                 else "INSERT INTO products(name,category,emoji,image,public_id) VALUES(?,?,?,?,?)",
                                 (name, secname, emo, img, str(secrets.randbelow(90000) + 10000)))
                newpid = cur.fetchone()[0] if USE_PG else cur.lastrowid
                p = (newpid,)
            sell = cost * (1 + margin / 100)
            sell = round(sell, 2) if sell >= 1 else round(sell, 4)
            if sell <= 0:
                skipped += 1
                continue
            req = 1 if sec in ("🎮 شحن الألعاب", "💬 تطبيقات الدردشة") else 0
            cur = db.execute("INSERT INTO skus(product_id,name,price,cost,requires_id,min_qty,max_qty,public_id) VALUES(?,?,?,?,?,?,?,?) RETURNING id" if USE_PG
                             else "INSERT INTO skus(product_id,name,price,cost,requires_id,min_qty,max_qty,public_id) VALUES(?,?,?,?,?,?,?,?)",
                             (p[0], name, sell, round(cost, 4), req, 1, 1, str(secrets.randbelow(90000) + 10000)))
            skid = cur.fetchone()[0] if USE_PG else cur.lastrowid
            if USE_PG: db.execute("INSERT INTO category_links(category_id,provider_id,provider_product) VALUES(?,?,?) ON CONFLICT(category_id) DO UPDATE SET provider_id=excluded.provider_id,provider_product=excluded.provider_product", (skid, provid, ext_id))
            else: db.execute("INSERT OR REPLACE INTO category_links(category_id,provider_id,provider_product) VALUES(?,?,?)", (skid, provid, ext_id))
            imported += 1
    return jsonify({"message": f"تم استيراد وربط {imported} منتج ✅ (تخطّي {skipped} غير مفهوم، مكرر {dup})",
                    "imported": imported, "skipped": skipped, "duplicates": dup,
                    "skipped_sample": skipped_sample, "sections": sorted(sections_used), "provider_id": provid})

@app.delete("/api/admin/catalog/import/<string:bid>")
@require_admin
def adm_csv_rollback(bid):
    with get_db() as db:
        items = db.execute("SELECT kind,ref_id FROM import_items WHERE batch_id=?", (bid,)).fetchall()
        for kind, ref in items:
            if kind == "sku": db.execute("DELETE FROM skus WHERE id=?", (ref,))
            else:
                db.execute("DELETE FROM skus WHERE product_id=?", (ref,))
                db.execute("DELETE FROM products WHERE id=?", (ref,))
        db.execute("DELETE FROM import_items WHERE batch_id=?", (bid,))
        db.execute("DELETE FROM import_batches WHERE id=?", (bid,))
    return jsonify({"message": f"تم التراجع وحذف {len(items)} عنصر ✅"})

# --- شعارات وملفات الموقع ---
def _save_setting_file(key):
    if "file" not in request.files: return jsonify({"message": "لا يوجد ملف"}), 400
    url = save_upload(request.files["file"])
    if not url: return jsonify({"message": "صيغة غير مدعومة"}), 400
    set_setting(key, url)
    return jsonify({"message": "تم الرفع ✅", "url": url})

@app.post("/api/admin/settings/logo")
@require_admin
def adm_logo(): return _save_setting_file("logo_image")

@app.post("/api/admin/settings/dev-logo")
@require_admin
def adm_devlogo(): return _save_setting_file("dev_logo")

@app.post("/api/admin/settings/app-icon")
@require_admin
def adm_appicon(): return _save_setting_file("app_icon")

@app.post("/api/admin/settings/banner-image")
@require_admin
def adm_banner_file():
    if "file" not in request.files: return jsonify({"message": "لا يوجد ملف"}), 400
    url = save_upload(request.files["file"])
    if not url: return jsonify({"message": "صيغة غير مدعومة"}), 400
    with get_db() as db: db.execute("INSERT INTO banners(image) VALUES(?)", (url,))
    return jsonify({"message": "تمت الإضافة ✅", "image": url})

@app.delete("/api/admin/settings/banner-image/<int:bid>")
@require_admin
def adm_banner_del2(bid):
    with get_db() as db: db.execute("DELETE FROM banners WHERE id=?", (bid,))
    return jsonify({"message": "تم الحذف"})

@app.delete("/api/admin/banners/all")
@require_admin
def adm_banners_clear():
    with get_db() as db: db.execute("DELETE FROM banners")
    return jsonify({"message": "تم حذف كل البنرات ✅"})

@app.post("/api/admin/catalog/clear")
@require_admin
def adm_catalog_clear():
    with get_db() as db:
        db.execute("DELETE FROM category_links")
        db.execute("DELETE FROM skus")
        db.execute("DELETE FROM products")
        db.execute("DELETE FROM import_items")
        db.execute("DELETE FROM import_batches")
    return jsonify({"message": "تم مسح كل المنتجات ✅"})

@app.post("/api/admin/catalog/brand-images")
@require_admin
def adm_brand_images():
    n = 0
    with get_db() as db:
        rows = db.execute("SELECT id,name FROM products WHERE image IS NULL OR image=''").fetchall()
        for pid, pname in rows:
            img = branded_image_url(pname or "منتج")
            if img:
                db.execute("UPDATE products SET image=? WHERE id=?", (img, pid))
                n += 1
    return jsonify({"message": f"تم توليد صور لـ {n} منتج ✅"})

@app.get("/site-icon")
def site_icon():
    icon = get_setting("app_icon", "") or get_setting("logo_image", "")
    if icon.startswith("http"): return redirect(icon)
    if icon.startswith("/uploads/"):
        return send_from_directory(UPLOAD_DIR, icon.split("/")[-1])
    return send_from_directory(os.path.join(BASE_DIR, "public"), "favicon.ico")

# --- صور الكيانات ---
def _entity_image(table, rid):
    if "file" not in request.files: return jsonify({"message": "لا يوجد ملف"}), 400
    url = save_upload(request.files["file"])
    if not url: return jsonify({"message": "صيغة غير مدعومة"}), 400
    with get_db() as db: db.execute(f"UPDATE {table} SET image=? WHERE id=?", (url, rid))
    return jsonify({"message": "تم الرفع ✅", "url": url})

@app.post("/api/admin/sections/<int:rid>/image")
@require_admin
def img_sec(rid): return _entity_image("sections", rid)

@app.post("/api/admin/products/<int:rid>/image")
@require_admin
def img_prod(rid): return _entity_image("products", rid)

@app.post("/api/admin/categories/<int:rid>/image")
@require_admin
def img_cat(rid): return _entity_image("skus", rid)

@app.post("/api/admin/subsections/<int:rid>/image")
@require_admin
def img_sub(rid): return _entity_image("subsections", rid)

@app.post("/api/admin/deposit-methods/manual/<int:rid>/image")
@require_admin
def img_man(rid): return _entity_image("deposit_manual", rid)

@app.post("/api/admin/deposit-methods/auto/<int:rid>/image")
@require_admin
def img_auto(rid): return _entity_image("deposit_auto", rid)

# --- صورة AI ---
@app.post("/api/admin/ai-image/generate")
@require_admin
def ai_gen():
    b = request.get_json(force=True, silent=True) or {}
    name = b.get("name") or b.get("product", "store banner")
    url, key = get_setting("ai_image_api_url", ""), get_setting("ai_image_api_key", "")
    if url and key:
        prompt = (b.get("prompt") or get_setting("ai_image_prompt_template", "")).replace("{product}", name)
        try:
            import requests as _rq
            r = _rq.post(url, json={"prompt": prompt, "key": key}, timeout=60)
            d = r.json() if r.ok else {}
            img = d.get("image_url") or d.get("image") or d.get("url") or ""
            if img: return jsonify({"message": "تم التوليد ✅", "image": img, "url": img})
        except Exception:
            pass
    img = branded_image_url(name)
    if not img: return jsonify({"message": "تعذّر التوليد"}), 502
    return jsonify({"message": "تم التوليد بهوية المتجر ✅", "image": img, "url": img})

@app.post("/api/admin/ai-image/apply")
@require_admin
def ai_apply():
    b = request.get_json(force=True, silent=True) or {}
    img = b.get("image", "") or b.get("url", "")
    pid = b.get("product_id")
    kind, rid = b.get("kind", ""), b.get("id")
    if not img: return jsonify({"message": "لا توجد صورة"}), 400
    table = {"product": "products", "category": "skus", "section": "sections", "subsection": "subsections"}.get(kind)
    with get_db() as db:
        if table and rid:
            db.execute(f"UPDATE {table} SET image=? WHERE id=?", (img, rid))
        elif pid:
            db.execute("UPDATE products SET image=? WHERE id=?", (img, pid))
        else:
            db.execute("INSERT INTO banners(image) VALUES(?)", (img,))
    return jsonify({"message": "تم التطبيق ✅"})

# --- مشرفو البوت ---
@app.get("/api/admin/admins")
@require_admin
def adm_badmins():
    with get_db() as db:
        rows = db.execute("SELECT user_id FROM bot_admins ORDER BY user_id").fetchall()
    ids = [r[0] for r in rows]
    main = min(ids) if ids else None
    return jsonify([{"user_id": x, "main": x == main} for x in ids])

@app.post("/api/admin/admins")
@require_admin
def adm_badmins_add():
    uid = (request.get_json(force=True, silent=True) or {}).get("user_id")
    try: uid = int(uid)
    except Exception: return jsonify({"message": "user_id رقمي مطلوب"}), 400
    with get_db() as db:
        if USE_PG: db.execute("INSERT INTO bot_admins(user_id) VALUES(?) ON CONFLICT DO NOTHING", (uid,))
        else: db.execute("INSERT OR IGNORE INTO bot_admins(user_id) VALUES(?)", (uid,))
    return jsonify({"message": "تمت الإضافة ✅"})

@app.delete("/api/admin/admins/<int:uid>")
@require_admin
def adm_badmins_del(uid):
    with get_db() as db: db.execute("DELETE FROM bot_admins WHERE user_id=?", (uid,))
    return jsonify({"message": "تم الحذف"})

# --- نسخ احتياطي + مسح ---
def _backup_dir():
    d = os.path.join(DATA_DIR, "backups")
    os.makedirs(d, exist_ok=True)
    return d

@app.get("/api/admin/backups")
@require_admin
def adm_backups():
    if USE_PG: return jsonify({"backups": []})
    out = []
    for f in sorted(os.listdir(_backup_dir())):
        fp = os.path.join(_backup_dir(), f)
        try:
            out.append({"name": f, "size_kb": round(os.path.getsize(fp) / 1024, 1),
                        "created_at": datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d %H:%M"),
                        "download_url": f"/admin/backups/{f}/download"})
        except Exception: pass
    return jsonify({"backups": out})

@app.post("/api/admin/backups")
@require_admin
def adm_backup_make():
    if USE_PG: return jsonify({"message": "النسخ اليدوي متاح لـ SQLite فقط"}), 503
    import shutil
    name = f"store-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    shutil.copy(os.path.join(DATA_DIR, "store.db"), os.path.join(_backup_dir(), name))
    return jsonify({"message": "تم إنشاء نسخة ✅", "name": name})

@app.get("/api/admin/backups/<string:name>/download")
@require_admin
def adm_backup_dl(name):
    if "/" in name or USE_PG: return jsonify({"message": "غير متاح"}), 404
    return send_from_directory(_backup_dir(), name, as_attachment=True)

@app.delete("/api/admin/backups/<string:name>")
@require_admin
def adm_backup_del(name):
    if "/" in name: return jsonify({"message": "غير صالح"}), 400
    try: os.remove(os.path.join(_backup_dir(), name))
    except Exception: return jsonify({"message": "غير موجود"}), 404
    return jsonify({"message": "تم الحذف"})

@app.post("/api/admin/restore")
@require_admin
def adm_restore():
    if USE_PG: return jsonify({"message": "غير متاح"}), 400
    if "file" in request.files:
        request.files["file"].save(os.path.join(DATA_DIR, "store.db"))
        ensure_extra()
        return jsonify({"message": "تمت الاستعادة ✅"})
    name = ((request.form.get("name") or "") if request.form else "") or ((request.get_json(force=True, silent=True) or {}).get("name") or "")
    if not name or "/" in name: return jsonify({"message": "حدد النسخة"}), 400
    import shutil
    src = os.path.join(_backup_dir(), name)
    if not os.path.exists(src): return jsonify({"message": "النسخة غير موجودة"}), 404
    shutil.copy(src, os.path.join(DATA_DIR, "store.db"))
    ensure_extra()
    return jsonify({"message": "تمت الاستعادة ✅"})

@app.post("/api/admin/wipe-data")
@require_admin
def adm_wipe():
    b = request.get_json(force=True, silent=True) or {}
    if (b.get("confirm") or "").strip() != "حذف":
        return jsonify({"message": "اكتب كلمة (حذف) للتأكيد"}), 400
    scope = b.get("scope") or "users"
    _auto_snapshot("pre-wipe")
    with get_db() as db:
        if scope == "all":
            for t in ("category_links", "skus", "products", "subsections", "sections",
                      "orders", "deposit_requests", "transactions", "notifications",
                      "banners", "import_items", "import_batches", "referrals",
                      "providers", "web_users", "balances", "user_tier"):
                try: db.execute(f"DELETE FROM {t}")
                except Exception: pass
            return jsonify({"message": "تم مسح كل شيء ✅ (أُخذت نسخة أمان قبل الحذف)"})
        for t in ("orders", "deposit_requests", "transactions", "notifications", "banners", "import_items", "import_batches", "referrals"):
            try: db.execute(f"DELETE FROM {t}")
            except Exception: pass
        try: db.execute("UPDATE balances SET balance=0")
        except Exception: pass
    return jsonify({"message": "تم مسح البيانات التشغيلية ✅ (بقي المستخدمون والكتالوج — وأُخذت نسخة أمان)"})

@app.get("/api/admin/snapshots")
@require_admin
def adm_snaps():
    with get_db() as db:
        try: rows = db.execute("SELECT id,reason,created_at,LENGTH(payload) FROM snapshots ORDER BY created_at DESC").fetchall()
        except Exception: rows = []
    return jsonify([{"id": r[0], "reason": r[1], "created_at": str(r[2]), "size_kb": round((r[3] or 0) / 1024, 1)} for r in rows])

@app.post("/api/admin/snapshots/<string:sid>/restore")
@require_admin
def adm_snap_restore(sid):
    import json as _j
    with get_db() as db:
        r = db.execute("SELECT payload FROM snapshots WHERE id=?", (sid,)).fetchone()
    if not r: return jsonify({"message": "النسخة غير موجودة"}), 404
    _restore_tables(_j.loads(r[0]))
    return jsonify({"message": "تمت الاستعادة ✅"})

@app.delete("/api/admin/snapshots/<string:sid>")
@require_admin
def adm_snap_del(sid):
    with get_db() as db: db.execute("DELETE FROM snapshots WHERE id=?", (sid,))
    return jsonify({"message": "تم الحذف"})

@app.get("/api/admin/backup-json")
@require_admin
def adm_backup_json():
    import json as _j
    payload = _j.dumps({"exported_at": datetime.now().isoformat(), "tables": _dump_tables()}, ensure_ascii=False, default=str)
    name = f"arab-store-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    return app.response_class("\ufeff" + payload, mimetype="application/json",
                              headers={"Content-Disposition": f"attachment; filename={name}"})

@app.post("/api/admin/restore-json")
@require_admin
def adm_restore_json():
    import json as _j
    if "file" not in request.files: return jsonify({"message": "أرفق ملف JSON"}), 400
    try: data = _j.loads(request.files["file"].read().decode("utf-8-sig"))
    except Exception: return jsonify({"message": "ملف غير صالح"}), 400
    tables = data.get("tables", data)
    if not isinstance(tables, dict): return jsonify({"message": "ملف غير صالح"}), 400
    _auto_snapshot("pre-restore")
    _restore_tables(tables)
    return jsonify({"message": "تمت الاستعادة من الملف ✅"})

@app.post("/api/admin/password")
@require_admin
def adm_password():
    b = request.get_json(force=True, silent=True) or {}
    cur, new = b.get("current") or "", b.get("new") or ""
    if len(new) < 8: return jsonify({"message": "الجديدة 8 أحرف على الأقل"}), 400
    eff = get_setting("admin_password_hash", "")
    if eff:
        ok = check_password_hash(eff, cur)
    else:
        ok = hmac.compare_digest(cur, ADMIN_PASSWORD)
    if not ok: return jsonify({"message": "الحالية غير صحيحة"}), 401
    set_setting("admin_password_hash", generate_password_hash(new))
    return jsonify({"message": "تم تغيير كلمة مرور الأدمن ✅ — استخدمها من الآن"})

SNAP_TABLES = ("settings", "sections", "subsections", "products", "skus",
               "web_users", "balances", "user_tier", "tiers",
               "deposit_manual", "deposit_auto", "deposit_requests", "orders",
               "transactions", "notifications", "banners", "web_admins",
               "bot_admins", "providers", "category_links", "referrals")

def _table_cols(db, table):
    try:
        if USE_PG:
            rows = db.execute("SELECT column_name FROM information_schema.columns WHERE table_name=? ORDER BY ordinal_position", (table,)).fetchall()
        else:
            rows = db.execute(f"PRAGMA table_info({table})").fetchall()
            return [r[1] for r in rows]
        return [r[0] for r in rows]
    except Exception:
        return []

def _dump_tables():
    import json as _j
    data = {}
    with get_db() as db:
        for t in SNAP_TABLES:
            try:
                cols = _table_cols(db, t)
                if not cols: continue
                rows = db.execute(f"SELECT * FROM {t}").fetchall()
                data[t] = {"cols": cols, "rows": [[str(v) if isinstance(v, (datetime,)) else v for v in r] for r in rows]}
            except Exception:
                continue
    return data

def _restore_tables(data):
    with get_db() as db:
        for t in SNAP_TABLES:
            blk = (data or {}).get(t)
            if not blk: continue
            cols, rows = blk.get("cols") or [], blk.get("rows") or []
            if not cols: continue
            try: db.execute(f"DELETE FROM {t}")
            except Exception: continue
            ph = ",".join(["?"] * len(cols))
            for r in rows:
                try: db.execute(f"INSERT INTO {t}({','.join(cols)}) VALUES({ph})", tuple(r))
                except Exception: pass

def _auto_snapshot(reason="auto"):
    """نسخة أمان تلقائية قبل العمليات الخطرة."""
    try:
        import json as _j
        dump = _j.dumps(_dump_tables(), ensure_ascii=False, default=str)
        with get_db() as db:
            sid = f"snap-{reason}-{uuid.uuid4().hex[:6]}"
            if USE_PG: db.execute("INSERT INTO snapshots(id,reason,payload) VALUES(?,?,?)", (sid, reason, dump))
            else: db.execute("INSERT INTO snapshots(id,reason,payload) VALUES(?,?,?)", (sid, reason, dump))
            old = db.execute("SELECT id FROM snapshots ORDER BY created_at DESC").fetchall()
            for (oid,) in old[5:]: db.execute("DELETE FROM snapshots WHERE id=?", (oid,))
    except Exception as e:
        print(f"WARNING: auto snapshot failed: {e}")

# ---------- static ----------
@app.get("/uploads/<path:f>")
def upl(f): return send_from_directory(UPLOAD_DIR, f)

@app.get("/manifest.json")
def mani():
    return jsonify({"name": "ARAB STORE", "short_name": "ARAB", "display": "standalone", "dir": "rtl", "lang": "ar",
                    "start_url": "/store.html", "background_color": "#0b1020", "theme_color": "#7c5cff"})

@app.get("/")
def root(): return send_from_directory(app.static_folder, "store.html")

@app.get("/health")
def health():
    info = {"ok": True, "pg": USE_PG, "time": datetime.now().isoformat(),
            "storage": "persistent-postgres" if USE_PG else "ephemeral (set DATABASE_URL or data will be lost)"}
    try:
        with get_db() as db:
            info["sections"] = db.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
        info["db"] = "ok"
    except Exception as e:
        info["db"] = f"error: {e}"
    return jsonify(info)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
