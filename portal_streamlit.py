import streamlit as st
import sqlite3
import pandas as pd
import os
import json
from datetime import datetime
from pathlib import Path
from PIL import Image
import base64

# Shared Database Logic
DB_PATH = "invoices.db"
UPLOADS_DIR = Path("invoice_uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

# --- ADMIN API (FOR DASHBOARD SYNC) ---
# MUST BE AT TOP to exit before rendering UI
if st.query_params.get("api") == "sync":
    secret = st.query_params.get("secret")
    mode = st.query_params.get("mode", "pending") # Default to pending
    
    if secret == os.environ.get("PORTAL_SECRET", "chocoberry2026"):
        try:
            conn = sqlite3.connect(DB_PATH)
            if mode == "history":
                df = pd.read_sql("SELECT * FROM portal_uploads ORDER BY created_at DESC", conn)
            else:
                df = pd.read_sql("SELECT * FROM portal_uploads WHERE synced_to_main = 0", conn)
            conn.close()
            st.text(df.to_json(orient="records"))
        except Exception as e:
            st.text(f"[]")
        st.stop()

# --- SETTINGS ---
st.set_page_config(page_title="Chocoberry Staff Portal", page_icon="🍫", layout="centered")

# CSS for Mobile-Friendly UI
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background: #0a0b0f; color: #e8e9f0; }
    .stButton>button { width: 100%; background: #f5a623; color: #000; font-weight: 700; border: none; border-radius: 10px; padding: 20px; }
    .stTextInput>div>div>input, .stSelectbox>div>div>div { background: #12141a; color: #fff; border: 1px solid #252836; }
    .logo-text { font-size: 32px; font-weight: 800; color: #f5a623; text-align: center; margin-bottom: 2px; }
    .logo-span { color: #fff; }
    .sub-text { font-size: 11px; color: #6b7094; text-align: center; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 30px; }
</style>
""", unsafe_allow_html=True)

# Shared Database Logic
DB_PATH = "invoices.db"
UPLOADS_DIR = Path("invoice_uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portal_uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_date TEXT,
            staff_name TEXT,
            supplier TEXT,
            total_amount REAL,
            image_filename TEXT,
            synced_to_main INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- UI ---
st.markdown('<div class="logo-text">Choco<span class="logo-span">berry</span></div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Staff Invoice Portal</div>', unsafe_allow_html=True)

with st.container():
    st.info("✨ Take a photo of the receipt and fill in the details below.")
    
    staff_name = st.text_input("👤 Your Name", placeholder="e.g. Ahmed")
    
    # Supplier List
    suppliers = ["Cr8 Foods", "Freshways", "Bookers", "Brakes", "Sysco", "Fresh Direct", "Bestway", "Muller", "T.Quality", "Other"]
    supplier = st.selectbox("🏢 Supplier", options=["Select..."] + suppliers)
    
    amount = st.number_input("💰 Total Amount (£)", min_value=0.0, step=0.01, format="%.2f")
    
    # Photo Upload (Camera)
    photo = st.camera_input("📸 Take Photo of Invoice")
    
    if st.button("🚀 SUBMIT INVOICE"):
        if not staff_name or supplier == "Select..." or amount <= 0 or not photo:
            st.error("⚠️ Please fill in all fields and take a photo!")
        else:
            # Save Image
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{staff_name[:5]}.jpg"
            save_path = UPLOADS_DIR / filename
            with open(save_path, "wb") as f:
                f.write(photo.getbuffer())
            
            # Save to DB
            conn = sqlite3.connect(DB_PATH)
            conn.execute("INSERT INTO portal_uploads (upload_date, staff_name, supplier, total_amount, image_filename) VALUES (?,?,?,?,?)",
                        (datetime.now().strftime("%Y-%m-%d"), staff_name, supplier, amount, filename))
            conn.commit()
            conn.close()
            
            st.balloons()
            st.success("✅ Invoice Submitted Successfully! Thank you.")
