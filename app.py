import os
import json
import base64
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, redirect, url_for
from flask_cors import CORS
from dotenv import load_dotenv

# Load variables
load_dotenv()

app = Flask(__name__)
# 🔐 Enable CORS so the Dashboard can talk to the Portal
CORS(app)

app.secret_key = os.environ.get("FLASK_SECRET", "chocoberry-portal-2026")

# ── API Key Verification ──
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")

# ── Security ──
PORTAL_SECRET = os.environ.get("PORTAL_SECRET", "chocoberry2026")

# ── Paths ──
BASE_DIR     = Path(__file__).parent
UPLOADS_DIR  = BASE_DIR / "invoice_uploads"
DB_PATH      = BASE_DIR / "invoices.db"
UPLOADS_DIR.mkdir(exist_ok=True)

# ── Suppliers & Categories ──
SUPPLIERS = ["Cr8 Foods", "Freshways", "Bookers", "Brakes", "Sysco", "Fresh Direct", "Bestway", "Muller", "T.Quality", "Other"]
CATEGORIES = ["Food", "Packaging", "Cleaning", "Utilities", "Maintenance", "Other"]

# ── DB Setup ──
def get_db_connection():
    # check_same_thread=False is essential for Gunicorn production servers
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS portal_uploads (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                upload_date   TEXT    NOT NULL,
                staff_name    TEXT,
                supplier      TEXT,
                invoice_date  TEXT,
                total_amount  REAL,
                category      TEXT,
                invoice_number TEXT,
                notes         TEXT,
                image_filename TEXT,
                ai_parsed     INTEGER DEFAULT 0,
                synced_to_main INTEGER DEFAULT 0,
                created_at    TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

init_db()

# ── AI Invoice Parsing via Claude API ──
def ai_parse_invoice(image_b64: str, mime_type: str) -> dict:
    try:
        import urllib.request
        import urllib.error
        if not ANTHROPIC_KEY: return {}

        payload = json.dumps({
            "model": "claude-3-haiku-20240307", # Faster/cheaper for invoices
            "max_tokens": 500,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": image_b64}},
                    {"type": "text", "text": "Extract invoice data. Reply ONLY with valid JSON: \n"
                                           '{"supplier":"","invoice_number":"","invoice_date":"YYYY-MM-DD",'
                                           '"total_amount":0.00}'}
                ],
            }],
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={"Content-Type": "application/json", "x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            raw_text = data["content"][0]["text"].strip()
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(raw_text)
    except Exception:
        return {}

# ── HTML TEMPLATES ──
HTML_INDEX = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <title>Chocoberry — Invoice Upload</title>
    <style>
      *{box-sizing:border-box;margin:0;padding:0}
      body{background:#0a0b0f;color:#e8e9f0;font-family:sans-serif;min-height:100vh}
      .header{background:#12141a;border-bottom:1px solid #252836;padding:16px 20px;text-align:center}
      .logo{font-size:22px;font-weight:800;color:#f5a623}
      .logo span{color:#fff}
      .body{padding:20px;max-width:480px;margin:0 auto}
      .card{background:#12141a;border:1px solid #252836;border-radius:12px;padding:20px;margin-bottom:16px}
      label{display:block;font-size:12px;color:#6b7094;margin-bottom:5px;margin-top:12px}
      input,select,textarea{width:100%;background:#0d0f14;border:1px solid #252836;border-radius:8px;padding:12px;color:#e8e9f0;font-size:15px}
      .submit-btn{width:100%;background:#f5a623;color:#000;border:none;border-radius:10px;padding:16px;font-weight:700;margin-top:20px}
      #preview{width:100%;border-radius:8px;margin-top:12px;display:none}
      .ai-badge{background:rgba(245,166,35,0.1);color:#f5a623;padding:5px 12px;border-radius:20px;font-size:11px;margin-bottom:15px}
    </style>
</head>
<body>
    <div class="header"><div class="logo">Choco<span>berry</span></div></div>
    <div class="body">
        <div class="ai-badge">✨ AI Auto-Reads Photo</div>
        <form id="uploadForm">
            <div class="card">
                <input type="file" id="fileInput" name="invoice_image" accept="image/*" capture="environment" style="display:none">
                <button type="button" onclick="document.getElementById('fileInput').click()" style="width:100%;padding:30px;background:#1a1d26;border:2px dashed #252836;color:#6b7094;border-radius:12px">Tap to take Photo</button>
                <img id="preview">
            </div>
            <div class="card">
                <label>Your Name *</label><input type="text" name="staff_name" required>
                <label>Supplier *</label>
                <select name="supplier" id="supList" required>
                    <option value="">Select...</option>
                    """ + "".join(f'<option value="{s}">{s}</option>' for s in SUPPLIERS) + r"""
                </select>
                <label>Total Amount (£) *</label><input type="number" name="total_amount" step="0.01" required>
            </div>
            <button type="submit" class="submit-btn" id="subBtn">Submit Invoice</button>
        </form>
    </div>
    <script>
        const form = document.getElementById('uploadForm');
        form.onsubmit = async (e) => {
            e.preventDefault();
            document.getElementById('subBtn').disabled = true;
            document.getElementById('subBtn').innerText = 'Uploading...';
            const fd = new FormData(form);
            const res = await fetch('/upload', {method:'POST', body:fd});
            const data = await res.json();
            if(data.success) { alert('Success!'); location.reload(); }
            else { alert('Error: ' + data.error); document.getElementById('subBtn').disabled=false; }
        }
    </script>
</body>
</html>"""

# ── ROUTES ──
@app.route("/")
def index():
    return HTML_INDEX

@app.route("/upload", methods=["POST"])
def upload():
    try:
        f = request.files.get("invoice_image")
        staff = request.form.get("staff_name")
        sup = request.form.get("supplier")
        amt = float(request.form.get("total_amount", 0))

        if not staff or not sup or amt <= 0:
            return jsonify({"success": False, "error": "Missing info"})

        filename = ""
        if f:
            ext = Path(f.filename).suffix or ".jpg"
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
            f.save(UPLOADS_DIR / filename)

        with get_db_connection() as conn:
            conn.execute("INSERT INTO portal_uploads (upload_date, staff_name, supplier, total_amount, image_filename) VALUES (?,?,?,?,?)",
                        (datetime.now().strftime("%Y-%m-%d"), staff, sup, amt, filename))
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/pending")
def api_pending():
    if request.args.get("secret") != PORTAL_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM portal_uploads WHERE synced_to_main = 0").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/mark_synced", methods=["POST"])
def api_mark_synced():
    if request.json.get("secret") != PORTAL_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    ids = request.json.get("ids", [])
    with get_db_connection() as conn:
        for i in ids:
            conn.execute("UPDATE portal_uploads SET synced_to_main=1 WHERE id=?", (i,))
        conn.commit()
    return jsonify({"synced": len(ids)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5050)))
