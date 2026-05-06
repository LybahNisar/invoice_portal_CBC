import streamlit as st
import pandas as pd
import os
from datetime import datetime
from pathlib import Path
from supabase import create_client, Client

# --- SUPABASE CONFIG ---
SUPABASE_URL = "https://rrlveynfxghfclgnizpm.supabase.co"
SUPABASE_KEY = "sb_publishable_-fdpwEmIzCmguuGyOU90rg_mZ1d0gFc"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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

# --- UI ---
st.markdown('<div class="logo-text">Choco<span class="logo-span">berry</span></div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Staff Invoice Portal</div>', unsafe_allow_html=True)

with st.container():
    st.info("✨ Take a photo of the receipt and fill in the details below. This data is now permanently saved.")
    
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
            try:
                # 1. Prepare Data
                data = {
                    "staff_name": staff_name,
                    "supplier": supplier,
                    "total_amount": amount,
                    "image_url": "Image captured via camera", # Note: Real image storage can be added later
                    "synced_to_main": False
                }
                
                # 2. Save to Supabase
                response = supabase.table("portal_uploads").insert(data).execute()
                
                st.balloons()
                st.success("✅ Invoice Submitted Successfully! It is now permanently saved in the Cloud.")
                
            except Exception as e:
                st.error(f"❌ Error saving to cloud: {str(e)}")
