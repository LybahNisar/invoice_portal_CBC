"""
╔══════════════════════════════════════════════════════════════════╗
║         CHOCOBERRY — STAFF INVOICE UPLOAD PORTAL                ║
║   Phone-friendly web app — replaces WhatsApp invoice uploads    ║
║                                                                  ║
║  HOW TO RUN:                                                     ║
║    python invoice_portal.py                                      ║
║  Then open on any phone on the same WiFi:                        ║
║    http://<your-laptop-ip>:5050                                   ║
║  Find your laptop IP: run  ipconfig  (Windows) or ifconfig (Mac)║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import json
import base64
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, redirect, url_for
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

app.secret_key = "chocoberry-invoice-2026"

# ── API Key Verification ──────────────────────────────────────────
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_KEY:
    print("\n⚠️  WARNING: ANTHROPIC_API_KEY Not Set")
    print("   AI-powered invoice parsing is currently disabled.")
    print("   Staff can still perform manual uploads as usual.\n")
# ── Security ──────────────────────────────────────────────────────
PORTAL_SECRET = os.environ.get("PORTAL_SECRET", "chocoberry2026")


# ── Paths ─────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
UPLOADS_DIR  = BASE_DIR / "invoice_uploads"
DB_PATH      = BASE_DIR / "invoices.db"
UPLOADS_DIR.mkdir(exist_ok=True)

# ── Suppliers list (edit as needed) ───────────────────────────────
SUPPLIERS = [
    "Cr8 Foods", "Freshways", "Bookers", "Brakes", "Sysco",
    "Fresh Direct", "Bestway", "Muller", "T.Quality", "Other",
]

CATEGORIES = ["Food", "Packaging", "Cleaning", "Utilities", "Maintenance", "Other"]

# ── DB Setup ──────────────────────────────────────────────────────
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
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

# ── AI Invoice Parsing via Claude API ─────────────────────────────
def ai_parse_invoice(image_b64: str, mime_type: str) -> dict:
    """
    Sends invoice image to Claude API and extracts structured data.
    Returns dict with supplier, amount, date, invoice_number.
    Falls back to empty dict if API unavailable.
    """
    try:
        import urllib.request
        import urllib.error

        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 500,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract invoice data. Reply ONLY with valid JSON, no other text:\n"
                            '{"supplier":"","invoice_number":"","invoice_date":"YYYY-MM-DD",'
                            '"total_amount":0.00,"currency":"GBP"}'
                        ),
                    },
                ],
            }],
        }).encode()

        if not ANTHROPIC_KEY:
            return {}

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type":      "application/json",
                "x-api-key":         ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data     = json.loads(resp.read())
            raw_text = data["content"][0]["text"].strip()
            # strip markdown fences if present
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()
            return json.loads(raw_text)
    except Exception:
        return {}


@app.route("/guide")
def show_guide():
    """Simple view for the staff upload guide."""
    return r"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Guide — How to Upload</title>
<style>
  body{background:#0a0b0f;color:#e8e9f0;font-family:sans-serif;padding:25px;line-height:1.6;max-width:500px;margin:0 auto}
  h1{color:#f5a623;font-size:22px}
  h2{color:#f5a623;font-size:18px;margin-top:25px}
  .step{background:#12141a;border:1px solid #252836;border-radius:12px;padding:15px;margin-bottom:15px}
  .num{background:#f5a623;color:#0a0b0f;width:24px;height:24px;display:inline-block;text-align:center;border-radius:50%;font-weight:bold;margin-right:8px}
</style></head><body>
<h1>📄 How to Upload Invoices</h1>
<p style="color:#6b7094">Chocoberry Intelligence — Cardiff</p>
<div class="step"><span class="num">1</span><b>Open Portal</b><br>Go to the portal link on shop WiFi.</div>
<div class="step"><span class="num">2</span><b>Photo</b><br>Take a clear photo of the invoice. Ensure Supplier, Date, and Amount are visible.</div>
<div class="step"><span class="num">3</span><b>Check</b><br>AI will read the details. Fix any errors and tap "Submit".</div>
<h2>✅ Success Tips</h2>
<ul>
  <li>One photo per invoice (page with Total).</li>
  <li>No WhatsApp — use this portal!</li>
  <li>Upload as soon as delivery arrives.</li>
</ul>
<br><a href="/" style="color:#f5a623">← Back to Upload</a>
</body></html>"""


# ── Routes ────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Main upload page — phone optimised."""
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<meta name="theme-color" content="#0a0b0f">
<title>Chocoberry — Invoice Upload</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0a0b0f;color:#e8e9f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh}
  .header{background:#12141a;border-bottom:1px solid #252836;padding:16px 20px;display:flex;align-items:center;gap:12px}
  .logo{font-size:20px;font-weight:800;color:#f5a623}
  .logo span{color:#e8e9f0}
  .sub{font-size:11px;color:#6b7094;text-transform:uppercase;letter-spacing:1px}
  .body{padding:20px;max-width:480px;margin:0 auto}
  .card{background:#12141a;border:1px solid #252836;border-radius:12px;padding:20px;margin-bottom:16px}
  .card-title{font-size:13px;font-weight:600;color:#f5a623;text-transform:uppercase;letter-spacing:1px;margin-bottom:14px}
  label{display:block;font-size:12px;color:#6b7094;margin-bottom:5px;margin-top:12px}
  input,select,textarea{width:100%;background:#0d0f14;border:1px solid #252836;border-radius:8px;padding:12px;color:#e8e9f0;font-size:15px;outline:none;-webkit-appearance:none}
  input:focus,select:focus,textarea:focus{border-color:#f5a623}
  select option{background:#12141a}
  .photo-btn{display:block;width:100%;background:#1a1d26;border:2px dashed #252836;border-radius:12px;padding:28px 16px;text-align:center;cursor:pointer;transition:border-color .2s}
  .photo-btn:active{border-color:#f5a623;background:#1e2030}
  .photo-icon{font-size:36px;margin-bottom:8px}
  .photo-label{font-size:14px;color:#6b7094}
  .photo-label b{color:#e8e9f0;display:block;font-size:15px;margin-bottom:4px}
  #preview{width:100%;border-radius:8px;margin-top:12px;display:none;max-height:220px;object-fit:contain}
  .ai-badge{display:inline-flex;align-items:center;gap:6px;background:rgba(245,166,35,.12);border:1px solid rgba(245,166,35,.3);border-radius:20px;padding:4px 12px;font-size:11px;color:#f5a623;margin-bottom:16px}
  .submit-btn{display:block;width:100%;background:#f5a623;color:#0a0b0f;border:none;border-radius:10px;padding:16px;font-size:16px;font-weight:700;cursor:pointer;margin-top:8px;letter-spacing:.3px}
  .submit-btn:active{opacity:.85;transform:scale(.99)}
  .submit-btn:disabled{background:#2a2d38;color:#6b7094}
  .spinner{display:none;text-align:center;padding:20px;color:#6b7094}
  .success{display:none;background:#102a18;border:1px solid #3ecf8e;border-radius:12px;padding:20px;text-align:center;color:#3ecf8e;font-size:15px;font-weight:600}
  .error-msg{color:#e05c5c;font-size:12px;margin-top:4px;display:none}
  .ai-result{background:#0d0f14;border:1px solid #252836;border-radius:8px;padding:10px 14px;margin-top:10px;font-size:12px;color:#6b7094;display:none}
  .ai-result b{color:#f5a623}
  .field-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
</style>
</head>
<body>
<div class="header">
  <div>
    <div class="logo">Choco<span>berry</span></div>
    <div class="sub">Invoice Upload Portal</div>
  </div>
</div>
<div class="body">

  <div class="ai-badge">
    &#10024; AI auto-reads amount &amp; supplier from your photo
  </div>

  <form id="uploadForm" enctype="multipart/form-data">

    <div class="card">
      <div class="card-title">&#128247; Invoice Photo</div>
      <label for="fileInput" class="photo-btn" id="photoBtn">
        <div class="photo-icon">&#128247;</div>
        <div class="photo-label">
          <b>Tap to take photo or choose file</b>
          Works with camera or gallery
        </div>
      </label>
      <input type="file" id="fileInput" name="invoice_image"
             accept="image/*" capture="environment"
             style="display:none" required>
      <img id="preview" alt="Invoice preview">
      <div class="ai-result" id="aiResult"></div>
    </div>

    <div class="card">
      <div class="card-title">&#128100; Your Details</div>
      <label>Your Name *</label>
      <input type="text" name="staff_name" id="staffName"
             placeholder="e.g. Ahmed / Priya" required>
    </div>

    <div class="card">
      <div class="card-title">&#128203; Invoice Details</div>

      <div class="ai-badge" style="font-size:10px;margin-bottom:10px">
        Fields below auto-fill from photo — check and correct if needed
      </div>

      <label>Supplier *</label>
      <select name="supplier" id="supplierField" required>
        <option value="">Select supplier...</option>
        """ + "".join(f'<option value="{s}">{s}</option>' for s in SUPPLIERS) + r"""
      </select>

      <div class="field-row">
        <div>
          <label>Invoice Date</label>
          <input type="date" name="invoice_date" id="invDate">
        </div>
        <div>
          <label>Invoice # (optional)</label>
          <input type="text" name="invoice_number" id="invNumber" placeholder="INV-001">
        </div>
      </div>

      <label>Total Amount (£) *</label>
      <input type="number" name="total_amount" id="invAmount"
             step="0.01" min="0.01" placeholder="0.00" required>

      <label>Category</label>
      <select name="category" id="catField">
        """ + "".join(f'<option value="{c}">{c}</option>' for c in CATEGORIES) + r"""
      </select>

      <label>Notes (optional)</label>
      <textarea name="notes" rows="2"
                placeholder="Any extra info for the accounts team..."></textarea>
    </div>

    <div class="spinner" id="spinner">&#9200; Uploading &amp; reading invoice...</div>
    <div class="error-msg" id="errorMsg"></div>

    <button type="submit" class="submit-btn" id="submitBtn">
      Submit Invoice
    </button>
  </form>

  <div class="success" id="successBox">
    &#10003; Invoice submitted successfully!<br>
    <span style="font-size:13px;color:#6b7094;font-weight:400">
      The accounts team will review it shortly.
    </span>
    <br><br>
    <button onclick="resetForm()"
            style="background:#f5a623;color:#0a0b0f;border:none;border-radius:8px;
                   padding:12px 24px;font-weight:700;cursor:pointer;font-size:14px">
      Submit Another
    </button>
  </div>

</div>

<script>
const fileInput    = document.getElementById('fileInput');
const preview      = document.getElementById('preview');
const aiResult     = document.getElementById('aiResult');
const supplierFld  = document.getElementById('supplierField');
const invDate      = document.getElementById('invDate');
const invNumber    = document.getElementById('invNumber');
const invAmount    = document.getElementById('invAmount');
const submitBtn    = document.getElementById('submitBtn');
const spinner      = document.getElementById('spinner');
const errorMsg     = document.getElementById('errorMsg');
const successBox   = document.getElementById('successBox');
const form         = document.getElementById('uploadForm');

fileInput.addEventListener('change', async function() {
  const file = this.files[0];
  if (!file) return;

  // Show preview
  const reader = new FileReader();
  reader.onload = e => {
    preview.src = e.target.result;
    preview.style.display = 'block';
  };
  reader.readAsDataURL(file);

  // Auto-parse with AI
  aiResult.style.display = 'block';
  aiResult.innerHTML = '&#9200; Reading invoice with AI...';

  const fd = new FormData();
  fd.append('invoice_image', file);

  try {
    const res  = await fetch('/parse', { method: 'POST', body: fd });
    const data = await res.json();

    if (data.total_amount) {
      invAmount.value = parseFloat(data.total_amount).toFixed(2);
    }
    if (data.invoice_date) {
      invDate.value = data.invoice_date;
    }
    if (data.invoice_number) {
      invNumber.value = data.invoice_number;
    }
    if (data.supplier) {
      // Try to match to our supplier list
      const sup = data.supplier.toLowerCase();
      const opts = supplierFld.options;
      for (let i = 0; i < opts.length; i++) {
        if (opts[i].value.toLowerCase().includes(sup) ||
            sup.includes(opts[i].value.toLowerCase())) {
          supplierFld.value = opts[i].value;
          break;
        }
      }
    }

    const hasData = data.total_amount || data.supplier;
    aiResult.innerHTML = hasData
      ? `<b>AI extracted:</b> ${data.supplier || '?'} &nbsp;|&nbsp; &pound;${data.total_amount || '?'} &nbsp;|&nbsp; ${data.invoice_date || '?'}<br><span style="color:#3ecf8e">&#10003; Check fields below and correct if needed</span>`
      : '<span style="color:#6b7094">Could not auto-read — please fill in manually below</span>';
  } catch(e) {
    aiResult.innerHTML = '<span style="color:#6b7094">AI Brain offline — please fill in manually</span>';
  }
});

form.addEventListener('submit', async function(e) {
  e.preventDefault();
  errorMsg.style.display = 'none';
  submitBtn.disabled = true;
  spinner.style.display = 'block';

  try {
    const fd  = new FormData(form);
    const res = await fetch('/upload', { method: 'POST', body: fd });
    const data = await res.json();

    spinner.style.display = 'none';

    if (data.success) {
      form.style.display    = 'none';
      successBox.style.display = 'block';
    } else {
      errorMsg.textContent    = data.error || 'Upload failed. Please try again.';
      errorMsg.style.display  = 'block';
      submitBtn.disabled = false;
    }
  } catch(e) {
    spinner.style.display  = 'none';
    errorMsg.textContent   = 'Network error. Please check your connection.';
    errorMsg.style.display = 'block';
    submitBtn.disabled     = false;
  }
});

function resetForm() {
  form.reset();
  preview.style.display    = 'none';
  aiResult.style.display   = 'none';
  form.style.display       = 'block';
  successBox.style.display = 'none';
  submitBtn.disabled       = false;
}
</script>
</body>
</html>"""


@app.route("/parse", methods=["POST"])
def parse_invoice():
    """AI-parse an uploaded invoice image. Returns extracted fields as JSON."""
    file = request.files.get("invoice_image")
    if not file:
        return jsonify({})
    data = file.read()
    b64  = base64.b64encode(data).decode()
    mime = file.content_type or "image/jpeg"
    result = ai_parse_invoice(b64, mime)
    return jsonify(result)


@app.route("/upload", methods=["POST"])
def upload_invoice():
    """Save invoice data + image to DB and disk."""
    try:
        f          = request.files.get("invoice_image")
        staff_name = request.form.get("staff_name", "").strip()
        supplier   = request.form.get("supplier", "").strip()
        inv_date   = request.form.get("invoice_date", "").strip()
        inv_number = request.form.get("invoice_number", "").strip()
        notes      = request.form.get("notes", "").strip()
        category   = request.form.get("category", "Food").strip()

        try:
            amount = float(request.form.get("total_amount", 0))
        except ValueError:
            amount = 0.0

        if not staff_name or not supplier or amount <= 0:
            return jsonify({"success": False, "error": "Name, supplier and amount are required."})

        # Save image
        filename = ""
        if f and f.filename:
            ext      = Path(f.filename).suffix or ".jpg"
            stamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_sup = "".join(c for c in supplier if c.isalnum())[:12]
            filename = f"{stamp}_{safe_sup}_{int(amount)}{ext}"
            f.seek(0)
            f.save(UPLOADS_DIR / filename)

        # Write to DB
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO portal_uploads
                  (upload_date, staff_name, supplier, invoice_date, total_amount,
                   category, invoice_number, notes, image_filename, ai_parsed)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                datetime.now().strftime("%Y-%m-%d"),
                staff_name, supplier, inv_date or None, amount,
                category, inv_number or None, notes or None,
                filename, 1 if filename else 0,
            ))
            conn.commit()

        return jsonify({"success": True})

    except Exception as ex:
        return jsonify({"success": False, "error": str(ex)})


@app.route("/admin")
def admin_view():
    """Simple admin page to see all uploads and sync status."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT id, upload_date, staff_name, supplier, invoice_date,
                   total_amount, category, invoice_number, synced_to_main
            FROM portal_uploads ORDER BY created_at DESC LIMIT 100
        """).fetchall()

    total_unsynced = sum(1 for r in rows if not r[8])
    total_amount   = sum(r[5] or 0 for r in rows)

    rows_html = ""
    for r in rows:
        synced_badge = (
            '<span style="color:#3ecf8e">&#10003; Synced</span>'
            if r[8] else
            '<span style="color:#f5a623">&#9711; Pending</span>'
        )
        rows_html += f"""
        <tr>
          <td>{r[1]}</td>
          <td>{r[2]}</td>
          <td>{r[3]}</td>
          <td>{r[4] or '—'}</td>
          <td>&pound;{r[5]:.2f}</td>
          <td>{r[6]}</td>
          <td>{r[7] or '—'}</td>
          <td>{synced_badge}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin — Invoice Portal</title>
<style>
  body{{background:#0a0b0f;color:#e8e9f0;font-family:monospace;padding:20px}}
  h1{{color:#f5a623;margin-bottom:4px}}
  .stats{{display:flex;gap:20px;margin:16px 0}}
  .stat{{background:#12141a;border:1px solid #252836;border-radius:8px;padding:12px 18px;text-align:center}}
  .sv{{font-size:22px;font-weight:700;color:#f5a623}}
  .sl{{font-size:11px;color:#6b7094}}
  table{{width:100%;border-collapse:collapse;font-size:12px;margin-top:20px}}
  th{{background:#1a1d26;color:#f5a623;padding:8px;text-align:left;border-bottom:1px solid #252836}}
  td{{padding:8px;border-bottom:1px solid #14161f;color:#e8e9f0}}
  tr:hover td{{background:#12141a}}
  a{{color:#f5a623}}
</style></head><body>
<h1>&#128203; Invoice Portal — Admin View</h1>
<p style="color:#6b7094;font-size:12px">Showing last 100 uploads</p>
<div class="stats">
  <div class="stat"><div class="sv">{len(rows)}</div><div class="sl">Total Uploads</div></div>
  <div class="stat"><div class="sv">{total_unsynced}</div><div class="sl">Pending Sync</div></div>
  <div class="stat"><div class="sv">&pound;{total_amount:,.2f}</div><div class="sl">Total Value</div></div>
</div>
<p style="color:#6b7094;font-size:11px">
  &#128161; To sync into your main dashboard, run:
  <code style="color:#f5a623">python sync_portal_invoices.py</code>
</p>
<table>
  <tr>
    <th>Date</th><th>Staff</th><th>Supplier</th><th>Inv Date</th>
    <th>Amount</th><th>Category</th><th>Inv #</th><th>Status</th>
  </tr>
  {rows_html if rows_html else '<tr><td colspan="8" style="color:#6b7094;text-align:center">No uploads yet</td></tr>'}
</table>
<br>
<a href="/">&#8592; Back to upload form</a>
&nbsp;|&nbsp;
<a href="https://github.com/google/gemini/blob/main/staff_upload_guide.md" target="_blank">📄 Print Staff Guide</a>
</body></html>"""


@app.route("/api/pending")
def api_pending():
    """JSON endpoint — returns all unsynced uploads for the main dashboard to pull."""
    if request.args.get("secret") != PORTAL_SECRET:
        return jsonify({"error": "unauthorized"}), 401

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT id, upload_date, staff_name, supplier, invoice_date,
                   total_amount, category, invoice_number, notes, image_filename
            FROM portal_uploads WHERE synced_to_main = 0
            ORDER BY created_at ASC
        """).fetchall()
    cols = ["id","upload_date","staff_name","supplier","invoice_date",
            "total_amount","category","invoice_number","notes","image_filename"]
    return jsonify([dict(zip(cols, r)) for r in rows])


@app.route("/api/mark_synced", methods=["POST"])
def api_mark_synced():
    """Mark portal uploads as synced once the main dashboard has imported them."""
    if request.json.get("secret") != PORTAL_SECRET:
        return jsonify({"error": "unauthorized"}), 401

    ids = request.json.get("ids", [])
    if ids:
        with sqlite3.connect(DB_PATH) as conn:
            conn.executemany(
                "UPDATE portal_uploads SET synced_to_main=1 WHERE id=?",
                [(i,) for i in ids],
            )
            conn.commit()
    return jsonify({"synced": len(ids)})


if __name__ == "__main__":
    import socket
    # Find local IP so user knows what to give to staff
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "localhost"

    print("\n" + "=" * 60)
    print("  CHOCOBERRY INVOICE PORTAL")
    print("=" * 60)
    print(f"\n  Share this link with your staff (same WiFi required):")
    print(f"\n     http://{local_ip}:5050\n")
    print(f"  Admin view (your laptop only):")
    print(f"     http://localhost:5050/admin\n")
    print("  Staff open the link on their phone, take a photo,")
    print("  and submit — no app install needed.")
    print("=" * 60 + "\n")

    app.run(host="0.0.0.0", port=5050, debug=False)
