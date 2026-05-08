import streamlit as st
import pandas as pd
import os
import base64
import requests
import json
from datetime import datetime
from pathlib import Path
from supabase import create_client, Client

# --- SUPABASE CONFIG ---
SUPABASE_URL = "https://rrlveynfxghfclgnizpm.supabase.co"
SUPABASE_KEY = "sb_publishable_-fdpwEmIzCmguuGyOU90rg_mZ1d0gFc"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- SETTINGS ---
st.set_page_config(page_title="Chocoberry Pro Invoice Portal", page_icon="🧾", layout="centered")

# --- UI STYLING ---
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background: #0a0b0f; color: #e8e9f0; }
    .stButton>button { width: 100%; background: #f5a623; color: #000; font-weight: 700; border: none; border-radius: 10px; padding: 15px; margin-top: 10px; }
    .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input, .stDateInput>div>div>input { 
        background: #12141a; color: #fff; border: 1px solid #252836; border-radius: 8px;
    }
    .logo-text { font-size: 32px; font-weight: 800; color: #f5a623; text-align: center; }
    .logo-span { color: #fff; }
    .sub-text { font-size: 11px; color: #6b7094; text-align: center; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 20px; }
    .form-section { background: #12141a; padding: 20px; border-radius: 12px; border: 1px solid #252836; margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

# --- UI HEADER ---
st.markdown('<div class="logo-text">Choco<span class="logo-span">berry</span></div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Pro Intelligence Invoice Portal</div>', unsafe_allow_html=True)

# --- INSTRUCTIONS ---
st.info("✨ Take a photo of the receipt and fill in the details below. This data is now permanently saved.")

# --- FORM ---
with st.container():
    st.markdown('<div class="form-section">', unsafe_allow_html=True)
    st.caption("📸 Step 1: Capture Invoice Photo")
    photo = st.camera_input("Take Photo")
    st.markdown('</div>', unsafe_allow_html=True)

    with st.form("invoice_form_pro"):
        st.markdown("### 📝 Invoice Details")
        c1, c2 = st.columns(2)
        with c1:
            inv_date = st.date_input("📅 Invoice Date", value=datetime.now())
            vendor = st.text_input("🏢 Store / Vendor Name", placeholder="e.g. Bookers, Cr8 Foods")
            v_type = st.selectbox("🏬 Store Type", ["Wholesale", "Supermarket", "Local Supplier", "Utility", "Other"])
        with c2:
            location = st.text_input("📍 Location / Branch", placeholder="e.g. Cardiff, London")
            pay_method = st.selectbox("💳 Payment Method", ["Business Card", "Cash", "Bank Transfer", "Direct Debit"])
            staff_name = st.text_input("👤 Staff Name", placeholder="Your Name")

        st.markdown("---")
        st.markdown("### 🛒 Line Item Intelligence")
        st.caption("Enter the primary or most expensive item for forensic tracking.")
        
        item_desc = st.text_input("📦 Item Description", placeholder="e.g. Nutella 3kg Tubs")
        col_qty, col_unit, col_total = st.columns(3)
        with col_qty:
            qty = st.number_input("Qty", min_value=0.0, step=0.1)
        with col_unit:
            unit_price = st.number_input("Unit Price (£)", min_value=0.0, step=0.01)
        with col_total:
            line_total = st.number_input("Line Total (£)", min_value=0.0, step=0.01)
        
        notes = st.text_area("📋 Additional Notes", placeholder="e.g. Delivery issue, price increase noticed")

        submit = st.form_submit_button("🚀 PERMANENTLY RECORD INVOICE")

        if submit:
            if not photo:
                st.error("⚠️ Please take a photo of the receipt first!")
            elif not vendor or not item_desc or line_total <= 0:
                st.error("⚠️ Please fill in Vendor, Item Description, and Total Amount!")
            else:
                    try:
                        # 1. Upload to PRIVATE Storage
                        file_ext = "jpg"
                        file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{vendor.replace(' ','_')}.{file_ext}"
                        bucket_name = "Invoices"
                        
                        img_bytes = photo.getvalue()
                        
                        # Upload
                        supabase.storage.from_(bucket_name).upload(
                            path=file_name,
                            file=img_bytes,
                            file_options={"content-type": "image/jpeg"}
                        )
                        
                        # Use Internal Path for DB (Secure)
                        # We don't use public URL for security.
                        storage_path = f"{bucket_name}/{file_name}"

                        # 2. Prepare Data (Matching User's Request)
                        data = {
                            "upload_date": datetime.now().strftime("%Y-%m-%d"),
                            "invoice_date": inv_date.strftime("%Y-%m-%d"),
                            "staff_name": staff_name,
                            "supplier": vendor,
                            "store_type": v_type,
                            "location": location,
                            "item_description": item_desc,
                            "quantity": qty,
                            "unit_price": unit_price,
                            "total_amount": line_total,
                            "payment_method": pay_method,
                            "notes": notes,
                            "image_url": storage_path,
                            "synced_to_main": False
                        }
                        
                        # 3. Save to Supabase
                        supabase.table("portal_uploads").insert(data).execute()
                        
                        st.balloons()
                        st.success("✅ Forensic Record Saved Successfully!")
                        st.info("🔒 Image stored securely in Private Storage.")
                        
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        st.info("💡 Hint: Ensure you have added the new columns to your Supabase table and created a private bucket named 'invoices'.")

# --- HISTORY VIEW ---
st.markdown("---")
with st.expander("📂 View Recent Uploads"):
    try:
        resp = supabase.table("portal_uploads").select("*").order("created_at", desc=True).limit(5).execute()
        if resp.data:
            df = pd.DataFrame(resp.data)
            st.dataframe(df[["upload_date", "staff_name", "supplier", "store_type", "location", "item_description", "quantity", "unit_price", "total_amount", "payment_method", "notes"]], use_container_width=True)
            
            # Show a signed URL for the latest image for verification
            latest = resp.data[0]
            if "image_url" in latest and latest["image_url"].startswith("Invoices/"):
                path = latest["image_url"].replace("Invoices/", "")
                # Generate a temporary Signed URL (valid for 60s)
                signed_url_resp = supabase.storage.from_("Invoices").create_signed_url(path, 60)
                st.image(signed_url_resp["signedURL"], caption=f"Latest Scan: {latest['supplier']}", width=300)
    except:
        st.write("No records available yet.")
