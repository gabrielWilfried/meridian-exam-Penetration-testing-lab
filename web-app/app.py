#!/usr/bin/env python3
"""
Meridian Health Systems — Patient Portal
CAPSTONE EXAMINATION TARGET (do not distribute to students with comments intact)

This application intentionally contains vulnerabilities across four difficulty
tiers. Each planted vulnerability is marked with a [VULN-xx] tag for the
examiner answer key. Flags are planted to prove exploitation.

Tiers:
  T1 (foothold)      — SQLi login bypass, IDOR, exposed debug endpoint, info disclosure
  T2 (intermediate)  — JWT weak secret, SSRF, path traversal, stored XSS, business logic
  T3 (advanced)      — LLM prompt injection (chatbot service), NoSQLi (api service)
  Internal pivot     — foothold credential leads to the AD domain (see ad-config)
"""
import os, sqlite3, jwt, hashlib, base64, requests, re
from datetime import datetime, timedelta
from flask import (Flask, request, jsonify, render_template_string,
                   make_response, redirect, send_file, Response)

app = Flask(__name__)

# [VULN-01] Weak, guessable JWT secret (T2). Crackable with hashcat/jwt_tool.
JWT_SECRET = "meridian2023"
DB_PATH = "/data/meridian.db"

# ─── Database bootstrap ────────────────────────────────────────────────────────
def init_db():
    os.makedirs("/data", exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, username TEXT, password TEXT,
        role TEXT, email TEXT, full_name TEXT, department TEXT
    );
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY, mrn TEXT, name TEXT, dob TEXT,
        diagnosis TEXT, medication TEXT, ssn TEXT, assigned_doctor TEXT
    );
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY, patient_id INTEGER, doctor TEXT,
        date TEXT, status TEXT, billing_amount REAL
    );
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY, patient_id INTEGER, author TEXT, content TEXT
    );
    """)
    # Seed users only once
    if not c.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        users = [
            # username, password(plain-for-lab), role, email, name, dept
            ("p.watson", "password1", "patient", "p.watson@gmail.com", "Peter Watson", "n/a"),
            ("a.reeves", "Spring2024!", "doctor", "a.reeves@meridianhealth.io", "Dr Alice Reeves", "Cardiology"),
            # [VULN-02] Foothold credential reused on the internal domain (T-internal).
            # This doctor's portal password matches their AD password — the pivot.
            ("m.chen", "MeridianIT#2024", "admin", "m.chen@meridianhealth.io", "Marcus Chen", "IT"),
            ("svc_report", "R3p0rt!ng2023", "service", "svc_report@meridianhealth.io", "Reporting Service", "IT"),
        ]
        c.executemany("INSERT INTO users (username,password,role,email,full_name,department) VALUES (?,?,?,?,?,?)", users)
        patients = [
            ("MRN-1001", "John Doe", "1978-03-12", "Hypertension", "Lisinopril", "489-22-1900", "a.reeves"),
            ("MRN-1002", "Jane Smith", "1990-07-01", "Type 2 Diabetes", "Metformin", "521-88-3300", "a.reeves"),
            # [VULN-03] Sensitive VIP record — IDOR/SQLi target. Contains a flag.
            ("MRN-1003", "R. Harrington (CEO)", "1965-11-20",
             "FLAG{idor_patient_record_exposed}", "Confidential", "999-11-0001", "m.chen"),
        ]
        c.executemany("INSERT INTO patients (mrn,name,dob,diagnosis,medication,ssn,assigned_doctor) VALUES (?,?,?,?,?,?,?)", patients)
        c.executemany("INSERT INTO appointments (patient_id,doctor,date,status,billing_amount) VALUES (?,?,?,?,?)",
                      [(1,"a.reeves","2024-02-01","confirmed",250.0),
                       (2,"a.reeves","2024-02-03","confirmed",180.0)])
        db.commit()
    db.close()

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

# ─── Helpers ────────────────────────────────────────────────────────────────────
def make_token(username, role):
    return jwt.encode({
        "sub": username, "role": role,
        "exp": datetime.utcnow() + timedelta(hours=8)
    }, JWT_SECRET, algorithm="HS256")

def verify_token(token):
    try:
        # [VULN-04] Accepts alg:none if the token is unsigned (T2).
        # jwt library configured permissively for the lab.
        header = jwt.get_unverified_header(token)
        if header.get("alg", "").lower() == "none":
            payload = jwt.decode(token, options={"verify_signature": False})
            return payload
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None

def current_user():
    tok = request.cookies.get("session") or \
          (request.headers.get("Authorization","").replace("Bearer ",""))
    if not tok:
        return None
    return verify_token(tok)

# ─── Public pages ───────────────────────────────────────────────────────────────
PORTAL_HTML = """
<!doctype html><html><head><title>Meridian Health — Patient Portal</title></head>
<body style="font-family:sans-serif;max-width:640px;margin:40px auto">
<h1>Meridian Health Systems</h1>
<p>Secure Patient Portal. Please <a href="/login">log in</a>.</p>
<!-- TODO: remove before go-live. Internal API docs at /api/v1/ -->
<!-- Dev note (m.chen): staging JWT secret is still meridian2023, rotate it -->
</body></html>
"""

@app.route("/")
def index():
    return PORTAL_HTML

# [VULN-05] Information disclosure via robots.txt (T1) — reveals hidden paths.
@app.route("/robots.txt")
def robots():
    return Response(
        "User-agent: *\n"
        "Disallow: /admin\n"
        "Disallow: /api/v1/\n"
        "Disallow: /backup\n"
        "Disallow: /debug\n"
        "Disallow: /export\n",
        mimetype="text/plain")

# [VULN-06] SQL injection login bypass (T1). Classic ' OR '1'='1 style.
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return """<form method=post>
        <input name=username placeholder=username>
        <input name=password type=password placeholder=password>
        <button>Login</button></form>"""
    u = request.form.get("username", "")
    p = request.form.get("password", "")
    db = get_db()
    # VULNERABLE: string-formatted query.
    q = f"SELECT * FROM users WHERE username = '{u}' AND password = '{p}'"
    try:
        row = db.execute(q).fetchone()
    except Exception as e:
        # [VULN-07] Verbose SQL errors aid injection (T1).
        return f"Database error: {e}", 500
    if row:
        resp = make_response(redirect("/dashboard"))
        resp.set_cookie("session", make_token(row["username"], row["role"]))
        return resp
    return "Invalid credentials", 401

@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect("/login")
    return f"<h2>Welcome {user['sub']} ({user['role']})</h2>" \
           f"<p><a href='/patient?id=1'>View patient records</a></p>"

# [VULN-03/08] IDOR — any authenticated user can read any patient by id (T1).
# Also [VULN-09] second-order SQLi via the id parameter (T2 — UNION extractable).
@app.route("/patient")
def patient():
    user = current_user()
    if not user:
        return jsonify({"error": "auth required"}), 401
    pid = request.args.get("id", "1")
    db = get_db()
    # VULNERABLE: id concatenated directly. UNION-based SQLi possible.
    q = f"SELECT id,mrn,name,dob,diagnosis,medication,assigned_doctor FROM patients WHERE id = {pid}"
    try:
        rows = [dict(r) for r in db.execute(q).fetchall()]
    except Exception as e:
        return f"Query error: {e}", 500
    return jsonify(rows)

# [VULN-10] SSRF — "fetch external lab result" feature (T2).
# Reaches internal services and the cloud metadata endpoint (10.10.20.80).
@app.route("/labresult")
def labresult():
    user = current_user()
    if not user:
        return jsonify({"error": "auth required"}), 401
    url = request.args.get("url", "")
    if not url:
        return "Provide ?url= to fetch a lab result", 400
    try:
        r = requests.get(url, timeout=4)
        return Response(r.content, content_type=r.headers.get("content-type", "text/plain"))
    except Exception as e:
        return f"Fetch failed: {e}", 502

# [VULN-11] Path traversal — document viewer (T2). Reads arbitrary files.
@app.route("/document")
def document():
    user = current_user()
    if not user:
        return jsonify({"error": "auth required"}), 401
    name = request.args.get("file", "welcome.txt")
    # VULNERABLE: no sanitisation of ../
    path = os.path.join("/app/documents", name)
    try:
        return send_file(path)
    except Exception as e:
        return f"Cannot read {name}: {e}", 404

# [VULN-12] Stored XSS in clinical notes (T2). Non-HttpOnly cookie = session theft.
@app.route("/note", methods=["GET", "POST"])
def note():
    user = current_user()
    if not user:
        return redirect("/login")
    db = get_db()
    if request.method == "POST":
        content = request.form.get("content", "")  # stored unsanitised
        db.execute("INSERT INTO notes (patient_id,author,content) VALUES (?,?,?)",
                   (request.form.get("patient_id", 1), user["sub"], content))
        db.commit()
        return redirect("/note")
    notes = db.execute("SELECT author,content FROM notes").fetchall()
    # VULNERABLE: rendered without escaping
    body = "".join(f"<div><b>{n['author']}</b>: {n['content']}</div>" for n in notes)
    return f"""<h3>Clinical notes</h3>{body}
    <form method=post><textarea name=content></textarea>
    <input type=hidden name=patient_id value=1><button>Add</button></form>"""

# [VULN-13] Business logic — appointment billing accepts negative amounts (T2).
# A patient can create a negative bill and generate account credit.
@app.route("/appointment/book", methods=["POST"])
def book():
    user = current_user()
    if not user:
        return jsonify({"error": "auth required"}), 401
    data = request.get_json(force=True, silent=True) or {}
    amount = float(data.get("billing_amount", 0))
    # VULNERABLE: no validation that amount > 0
    db = get_db()
    db.execute("INSERT INTO appointments (patient_id,doctor,date,status,billing_amount) VALUES (?,?,?,?,?)",
               (data.get("patient_id", 1), data.get("doctor", "a.reeves"),
                data.get("date", "2024-03-01"), "pending", amount))
    db.commit()
    msg = "Appointment booked."
    if amount < 0:
        msg += " FLAG{business_logic_negative_billing}"
    return jsonify({"message": msg, "billing_amount": amount})

# [VULN-14] Exposed admin/debug endpoint — no auth check (T1).
# Leaks environment including the internal AD hint and cloud role.
@app.route("/debug")
def debug():
    return jsonify({
        "app": "meridian-portal", "version": "1.4.2-staging",
        "db_path": DB_PATH,
        "internal_dc": "10.10.20.60 (meridian.local)",
        "cloud_metadata": "http://10.10.20.80/  (reachable via /labresult SSRF)",
        "note": "FLAG{exposed_debug_endpoint}",
        "hint": "Portal credentials may be valid on the internal domain.",
    })

# [VULN-15] Backup file exposure — source/config disclosure (T1).
@app.route("/backup")
def backup():
    return Response(
        "# meridian-portal .env backup (DO NOT COMMIT)\n"
        "JWT_SECRET=meridian2023\n"
        "DB_PATH=/data/meridian.db\n"
        "REPORTING_SVC_USER=svc_report\n"
        "REPORTING_SVC_PASS=R3p0rt!ng2023\n"
        "# AD read account for the portal directory sync:\n"
        "AD_SYNC_USER=svc_report\n"
        "FLAG{backup_config_disclosure}\n",
        mimetype="text/plain")

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    init_db()
    # Seed a couple of documents for the path-traversal exercise
    os.makedirs("/app/documents", exist_ok=True)
    with open("/app/documents/welcome.txt", "w") as f:
        f.write("Welcome to the Meridian Health document viewer.")
    app.run(host="0.0.0.0", port=80)
