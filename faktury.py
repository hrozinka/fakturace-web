import streamlit as st
import os
import json
import re
import hashlib
import requests
import smtplib
import unicodedata
import io
import base64
import pandas as pd
import random
import string
import time
import zipfile
import xml.etree.ElementTree as ET
import urllib3
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.utils import formataddr
from PIL import Image
from fpdf import FPDF
import qrcode
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

urllib3.disable_warnings()

# --- 0. KONFIGURACE ---
try:
    admin_pass_init = st.secrets["ADMIN_INIT_PASS"]
    email_pass = st.secrets.get("EMAIL_PASSWORD", "")
    db_url = st.secrets["DATABASE_URL"]
except Exception:
    admin_pass_init = os.getenv("ADMIN_INIT_PASS")
    email_pass = os.getenv("EMAIL_PASSWORD", "")
    db_url = os.getenv("DATABASE_URL")

if not admin_pass_init or not db_url:
    st.error("⛔ CHYBA BEZPEČNOSTI: Není nastaveno heslo ADMIN_INIT_PASS nebo DATABASE_URL v secrets!")
    st.stop()

SYSTEM_EMAIL = {
    "enabled": True,
    "server": "smtp.seznam.cz",
    "port": 465,
    "email": "jsem@michalkochtik.cz",
    "password": email_pass,
    "display_name": "MojeFakturace"
}

FONT_FILE = 'arial.ttf'

# --- 1. DESIGN (Kompletně přepsáno - Luxury Dark Glass) ---
st.set_page_config(page_title="MojeFaktury v7", page_icon="💎", layout="centered")

st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;1,9..40,300&display=swap" rel="stylesheet">

<style>
/* ===== RESET & BASE ===== */
*, *::before, *::after { box-sizing: border-box; }

.stApp {
    background: #080c14 !important;
    color: #e8edf5 !important;
    font-family: 'DM Sans', sans-serif !important;
}

/* Animated background mesh */
.stApp::before {
    content: '';
    position: fixed;
    top: 0; left: 0;
    width: 100%; height: 100%;
    background:
        radial-gradient(ellipse 80% 50% at 20% 10%, rgba(251,191,36,0.06) 0%, transparent 60%),
        radial-gradient(ellipse 60% 40% at 80% 80%, rgba(99,102,241,0.05) 0%, transparent 50%),
        radial-gradient(ellipse 40% 60% at 50% 50%, rgba(16,24,40,0.8) 0%, transparent 100%);
    pointer-events: none;
    z-index: 0;
}

/* ===== TYPOGRAPHY ===== */
h1, h2, h3, h4 {
    font-family: 'Syne', sans-serif !important;
    color: #f1f5f9 !important;
    letter-spacing: -0.02em;
}

h1 { font-size: 2rem !important; font-weight: 800 !important; }
h2 { font-size: 1.5rem !important; font-weight: 700 !important; }
h3 { font-size: 1.2rem !important; font-weight: 600 !important; }

p, label, span, div, li {
    color: #cbd5e1 !important;
    font-family: 'DM Sans', sans-serif !important;
}

/* ===== INPUTS ===== */
.stTextInput input,
.stNumberInput input,
.stTextArea textarea,
.stDateInput input {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: #f1f5f9 !important;
    border-radius: 10px !important;
    padding: 12px 16px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.9rem !important;
    transition: all 0.2s ease !important;
    backdrop-filter: blur(10px);
}

.stTextInput input:focus,
.stNumberInput input:focus,
.stTextArea textarea:focus {
    border-color: rgba(251,191,36,0.5) !important;
    box-shadow: 0 0 0 3px rgba(251,191,36,0.1) !important;
    background: rgba(255,255,255,0.06) !important;
}

/* ===== SELECT ===== */
.stSelectbox div[data-baseweb="select"] {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: #f1f5f9 !important;
    border-radius: 10px !important;
}

ul[data-baseweb="menu"] {
    background: #111827 !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 12px !important;
    padding: 6px !important;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5) !important;
}

li[data-baseweb="option"] {
    background: transparent !important;
    color: #cbd5e1 !important;
    border-radius: 8px !important;
    padding: 10px 14px !important;
    transition: all 0.15s ease !important;
}

li[data-baseweb="option"]:hover,
li[data-baseweb="option"][aria-selected="true"] {
    background: rgba(251,191,36,0.12) !important;
    color: #fbbf24 !important;
}

li[data-baseweb="option"]:hover div,
li[data-baseweb="option"][aria-selected="true"] div {
    color: #fbbf24 !important;
    font-weight: 500 !important;
}

.stSelectbox svg { fill: #94a3b8 !important; }
::placeholder { color: #475569 !important; }

/* ===== BUTTONS ===== */
.stButton > button {
    background: rgba(255,255,255,0.06) !important;
    color: #cbd5e1 !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 10px !important;
    height: 46px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    width: 100% !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    backdrop-filter: blur(10px) !important;
}

.stButton > button:hover {
    background: rgba(251,191,36,0.1) !important;
    border-color: rgba(251,191,36,0.4) !important;
    color: #fbbf24 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(251,191,36,0.15) !important;
}

[data-testid="stDownloadButton"] > button {
    background: rgba(255,255,255,0.06) !important;
    color: #94a3b8 !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 10px !important;
    height: 46px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    width: 100% !important;
    transition: all 0.2s ease !important;
}

[data-testid="stDownloadButton"] > button:hover {
    border-color: rgba(52,211,153,0.4) !important;
    color: #34d399 !important;
    background: rgba(52,211,153,0.08) !important;
}

div[data-testid="stForm"] button[kind="primary"] {
    background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 50%, #d97706 100%) !important;
    color: #0c1018 !important;
    border: none !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 20px rgba(251,191,36,0.3) !important;
}

div[data-testid="stForm"] button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 30px rgba(251,191,36,0.4) !important;
}

div[data-testid="stForm"] button[kind="primary"] p {
    color: #0c1018 !important;
    font-weight: 700 !important;
}

/* ===== SIDEBAR ===== */
section[data-testid="stSidebar"] {
    background: rgba(8,12,20,0.95) !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
    backdrop-filter: blur(20px) !important;
}

section[data-testid="stSidebar"] .stRadio label {
    background: rgba(255,255,255,0.03) !important;
    padding: 12px 16px !important;
    border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    width: 100% !important;
    margin-bottom: 4px !important;
    transition: all 0.2s ease !important;
    cursor: pointer !important;
}

section[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(251,191,36,0.06) !important;
    border-color: rgba(251,191,36,0.2) !important;
}

section[data-testid="stSidebar"] .stRadio label[data-checked="true"] {
    background: linear-gradient(135deg, rgba(251,191,36,0.15), rgba(217,119,6,0.1)) !important;
    border-color: rgba(251,191,36,0.35) !important;
}

section[data-testid="stSidebar"] .stRadio label[data-checked="true"] p {
    color: #fbbf24 !important;
    font-weight: 600 !important;
}

/* ===== EXPANDER ===== */
div[data-testid="stExpander"] {
    background: rgba(255,255,255,0.025) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 14px !important;
    overflow: hidden !important;
    transition: border-color 0.2s ease !important;
}

div[data-testid="stExpander"]:hover {
    border-color: rgba(251,191,36,0.2) !important;
}

div[data-testid="stExpander"] summary {
    padding: 14px 18px !important;
}

/* ===== CALENDAR ===== */
div[data-baseweb="calendar"] {
    background: #111827 !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 12px !important;
}

div[data-baseweb="calendar"] button { color: #f1f5f9 !important; }

/* ===== TABS ===== */
button[data-baseweb="tab"] { background: transparent !important; }
button[data-baseweb="tab"] div p { color: #64748b !important; font-family: 'DM Sans', sans-serif !important; }
button[data-baseweb="tab"][aria-selected="true"] div p { color: #fbbf24 !important; font-weight: 600 !important; }

/* ===== DIVIDER ===== */
hr { border-color: rgba(255,255,255,0.06) !important; margin: 1.5rem 0 !important; }

/* ===== METRIC ===== */
[data-testid="stMetricValue"] {
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    color: #f1f5f9 !important;
}

[data-testid="stMetricLabel"] {
    font-family: 'DM Sans', sans-serif !important;
    color: #64748b !important;
    font-size: 0.8rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}

/* ===== DATAFRAME ===== */
[data-testid="stDataFrame"] {
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 12px !important;
    overflow: hidden !important;
}

/* ===== TOGGLE ===== */
[data-testid="stCheckbox"] { accent-color: #fbbf24 !important; }

/* ===== ALERTS ===== */
[data-testid="stAlert"] {
    border-radius: 12px !important;
    border-width: 1px !important;
}

/* ===== CUSTOM COMPONENTS ===== */

/* Landing page */
.brand-logo {
    font-size: 56px;
    text-align: center;
    display: block;
    margin-bottom: 8px;
    animation: float 3s ease-in-out infinite;
}

@keyframes float {
    0%, 100% { transform: translateY(0px); }
    50% { transform: translateY(-8px); }
}

.brand-title {
    font-family: 'Syne', sans-serif;
    font-size: 3rem;
    font-weight: 800;
    text-align: center;
    background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 40%, #fde68a 70%, #fbbf24 100%);
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: shimmer 3s linear infinite;
    margin-bottom: 12px;
    letter-spacing: -0.03em;
}

@keyframes shimmer {
    0% { background-position: 0% center; }
    100% { background-position: 200% center; }
}

.brand-desc {
    text-align: center;
    color: #64748b !important;
    font-size: 1.05rem;
    margin-bottom: 32px;
    line-height: 1.6;
}

.feature-grid {
    background: rgba(255,255,255,0.025);
    padding: 24px;
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.08);
    margin-bottom: 24px;
}

.feature-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    font-size: 0.9rem;
    color: #94a3b8 !important;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}

.feature-item:last-child { border-bottom: none; }
.feature-item b { color: #e2e8f0 !important; }

/* Sidebar user card */
.sidebar-card {
    background: rgba(251,191,36,0.06);
    border: 1px solid rgba(251,191,36,0.15);
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 16px;
}

.sidebar-name {
    font-family: 'Syne', sans-serif;
    font-size: 1rem;
    font-weight: 700;
    color: #f1f5f9 !important;
    margin-bottom: 4px;
}

.sidebar-meta {
    font-size: 0.78rem;
    color: #64748b !important;
    margin-bottom: 8px;
}

.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

.badge-pro {
    background: linear-gradient(135deg, #fbbf24, #d97706);
    color: #0c1018 !important;
}

.badge-free {
    background: rgba(100,116,139,0.2);
    border: 1px solid rgba(100,116,139,0.3);
    color: #64748b !important;
}

/* Stats row */
.stats-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin: 16px 0 24px 0;
}

.stat-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 16px;
    text-align: center;
    transition: all 0.25s ease;
    position: relative;
    overflow: hidden;
}

.stat-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    border-radius: 2px 2px 0 0;
}

.stat-card.green::before { background: linear-gradient(90deg, #34d399, #10b981); }
.stat-card.gold::before { background: linear-gradient(90deg, #fbbf24, #f59e0b); }
.stat-card.red::before { background: linear-gradient(90deg, #f87171, #ef4444); }

.stat-card:hover {
    background: rgba(255,255,255,0.05);
    border-color: rgba(255,255,255,0.15);
    transform: translateY(-2px);
}

.stat-label {
    font-size: 0.68rem;
    color: #475569 !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 600;
    margin-bottom: 6px;
}

.stat-value {
    font-family: 'Syne', sans-serif;
    font-size: 1.35rem;
    font-weight: 800;
    line-height: 1;
    margin-bottom: 4px;
}

.stat-value.green { color: #34d399 !important; }
.stat-value.gold { color: #fbbf24 !important; }
.stat-value.red { color: #f87171 !important; }

.stat-sub {
    font-size: 0.7rem;
    color: #334155 !important;
}

/* Invoice row */
.inv-header {
    display: flex;
    align-items: center;
    gap: 8px;
}

.inv-number {
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 0.95rem;
    color: #f1f5f9 !important;
}

.inv-client {
    color: #94a3b8 !important;
    font-size: 0.85rem;
}

.inv-amount {
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    color: #fbbf24 !important;
    font-size: 0.95rem;
}

.status-paid {
    display: inline-block;
    padding: 2px 8px;
    background: rgba(52,211,153,0.12);
    border: 1px solid rgba(52,211,153,0.25);
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
    color: #34d399 !important;
    letter-spacing: 0.05em;
}

.status-unpaid {
    display: inline-block;
    padding: 2px 8px;
    background: rgba(251,191,36,0.1);
    border: 1px solid rgba(251,191,36,0.25);
    border-radius: 20px;
    font-size: 0.7rem;
    font-weight: 600;
    color: #fbbf24 !important;
    letter-spacing: 0.05em;
}

/* Info box */
.info-callout {
    background: rgba(251,191,36,0.06);
    border: 1px solid rgba(251,191,36,0.2);
    border-radius: 10px;
    padding: 12px 16px;
    margin: 8px 0;
    font-size: 0.85rem;
}

.info-callout span { color: #fbbf24 !important; font-weight: 600; }

/* Tax boxes */
.tax-card {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 24px;
    text-align: center;
    transition: all 0.25s ease;
}

.tax-card:hover {
    background: rgba(255,255,255,0.04);
    border-color: rgba(251,191,36,0.25);
}

.tax-card-title {
    font-family: 'Syne', sans-serif;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #475569 !important;
    margin-bottom: 12px;
}

.tax-amount {
    font-family: 'Syne', sans-serif;
    font-size: 2rem;
    font-weight: 800;
    color: #fbbf24 !important;
    margin: 8px 0;
}

.pro-upgrade-card {
    background: linear-gradient(135deg, rgba(251,191,36,0.08) 0%, rgba(217,119,6,0.05) 100%);
    border: 1px solid rgba(251,191,36,0.2);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 20px;
}

.pro-upgrade-card h3 {
    font-family: 'Syne', sans-serif !important;
    color: #fbbf24 !important;
    margin-bottom: 12px;
}

/* Section header */
.section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 20px;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}

.section-icon {
    width: 36px;
    height: 36px;
    background: rgba(251,191,36,0.1);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
}

.section-title {
    font-family: 'Syne', sans-serif;
    font-size: 1.3rem;
    font-weight: 700;
    color: #f1f5f9 !important;
}

/* Total summary line */
.total-line {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(251,191,36,0.06);
    border: 1px solid rgba(251,191,36,0.15);
    border-radius: 10px;
    padding: 14px 18px;
    margin: 12px 0;
}

.total-label {
    font-size: 0.85rem;
    color: #94a3b8 !important;
    font-weight: 500;
}

.total-amount {
    font-family: 'Syne', sans-serif;
    font-size: 1.2rem;
    font-weight: 800;
    color: #fbbf24 !important;
}

/* Admin stats */
.admin-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 24px;
}

.admin-card {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 18px 16px;
    text-align: center;
}

.admin-card-value {
    font-family: 'Syne', sans-serif;
    font-size: 1.5rem;
    font-weight: 800;
    color: #f1f5f9 !important;
    margin-bottom: 4px;
}

.admin-card-label {
    font-size: 0.72rem;
    color: #475569 !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

/* Client mini stats */
.mini-stats-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin: 12px 0;
}

.mini-stat {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px;
    padding: 12px;
    text-align: center;
}

.mini-stat-label {
    font-size: 0.65rem;
    color: #475569 !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 4px;
}

.mini-stat-value {
    font-family: 'Syne', sans-serif;
    font-size: 1.05rem;
    font-weight: 700;
    color: #f1f5f9 !important;
}

.mini-stat-value.green { color: #34d399 !important; }
.mini-stat-value.red { color: #f87171 !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(251,191,36,0.3); }

/* Hide streamlit branding */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }

/* Fix stray color overrides */
.stMarkdown p { color: #94a3b8 !important; }
.stMarkdown strong, .stMarkdown b { color: #e2e8f0 !important; }
.stMarkdown a { color: #fbbf24 !important; text-decoration: none; }
.stMarkdown a:hover { text-decoration: underline; }

/* Data editor */
[data-testid="stDataEditor"] {
    border-radius: 12px !important;
    overflow: hidden !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
}

/* Success/error/warning */
[data-testid="stAlertContainer"] > div {
    border-radius: 12px !important;
    font-family: 'DM Sans', sans-serif !important;
}
</style>
""", unsafe_allow_html=True)


# --- 2. DATABÁZE OPTIMALIZACE (Connection Pool) ---
@st.cache_resource
def get_pool():
    return psycopg2.pool.ThreadedConnectionPool(1, 20, db_url)

def run_query(sql, params=(), single=False):
    sql = sql.replace("?", "%s")
    p = get_pool(); conn = p.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as c:
            c.execute(sql, params)
            return c.fetchone() if single else c.fetchall()
    except Exception as e: print(f"Query Error: {e}"); return None
    finally: p.putconn(conn)

def run_command(sql, params=()):
    sql = sql.replace("?", "%s")
    is_insert = sql.strip().upper().startswith("INSERT")
    if is_insert and "RETURNING id" not in sql and "ON CONFLICT" not in sql: sql += " RETURNING id"
    p = get_pool(); conn = p.getconn()
    try:
        with conn.cursor() as c:
            c.execute(sql, params); conn.commit()
            if is_insert and "RETURNING id" in sql:
                try: return c.fetchone()[0]
                except: return None
            return None
    except Exception as e: print(f"Command Error: {e}"); return None
    finally: p.putconn(conn)

def init_db():
    p = get_pool(); conn = p.getconn()
    try:
        with conn.cursor() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, full_name TEXT, email TEXT, phone TEXT, license_key TEXT, license_valid_until TEXT, role TEXT DEFAULT 'user', created_at TEXT, last_active TEXT, force_password_change INTEGER DEFAULT 0)''')
            c.execute('''CREATE TABLE IF NOT EXISTS nastaveni (id SERIAL PRIMARY KEY, user_id INTEGER, nazev TEXT, adresa TEXT, ico TEXT, dic TEXT, ucet TEXT, banka TEXT, email TEXT, telefon TEXT, iban TEXT, smtp_server TEXT, smtp_port INTEGER, smtp_email TEXT, smtp_password TEXT, notify_email TEXT, notify_days INTEGER, notify_active INTEGER)''')
            c.execute('''CREATE TABLE IF NOT EXISTS klienti (id SERIAL PRIMARY KEY, user_id INTEGER, jmeno TEXT, adresa TEXT, ico TEXT, dic TEXT, email TEXT, poznamka TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS kategorie (id SERIAL PRIMARY KEY, user_id INTEGER, nazev TEXT, barva TEXT, prefix TEXT, aktualni_cislo INTEGER DEFAULT 1, logo_blob BYTEA)''')
            c.execute('''CREATE TABLE IF NOT EXISTS faktury (id SERIAL PRIMARY KEY, user_id INTEGER, cislo INTEGER, cislo_full TEXT, klient_id INTEGER, kategorie_id INTEGER, datum_vystaveni TEXT, datum_duzp TEXT, datum_splatnosti TEXT, castka_celkem REAL, zpusob_uhrady TEXT, variabilni_symbol TEXT, cislo_objednavky TEXT, uvodni_text TEXT, uhrazeno INTEGER DEFAULT 0, muj_popis TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS faktura_polozky (id SERIAL PRIMARY KEY, faktura_id INTEGER, nazev TEXT, cena REAL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS licencni_klice (id SERIAL PRIMARY KEY, kod TEXT UNIQUE, dny_platnosti INTEGER, vygenerovano TEXT, pouzito_uzivatelem_id INTEGER, poznamka TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS email_templates (id SERIAL PRIMARY KEY, name TEXT UNIQUE, subject TEXT, body TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS vydaje (id SERIAL PRIMARY KEY, user_id INTEGER, datum TEXT, popis TEXT, castka REAL, kategorie TEXT)''')
        conn.commit()
        try:
            with conn.cursor() as c: c.execute("ALTER TABLE users ADD COLUMN force_password_change INTEGER DEFAULT 0")
            conn.commit()
        except Exception: conn.rollback()
        with conn.cursor() as c:
            try: c.execute("INSERT INTO email_templates (name, subject, body) VALUES ('welcome', 'Vítejte ve vašem fakturačním systému', 'Dobrý den {name},\n\nVáš účet byl úspěšně vytvořen.\n\nS pozdravem,\nTým MojeFakturace') ON CONFLICT (name) DO NOTHING")
            except: pass
            try:
                adm_hash = hashlib.sha256(str.encode(admin_pass_init)).hexdigest()
                c.execute("INSERT INTO users (username, password_hash, role, full_name, email, phone, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (username) DO NOTHING", ("admin", adm_hash, "admin", "Super Admin", "admin@system.cz", "000000000", datetime.now().isoformat()))
                c.execute("UPDATE users SET password_hash=%s WHERE username='admin'", (adm_hash,))
            except Exception as e: print(f"Chyba admin sync: {e}")
        conn.commit()
    finally: p.putconn(conn)

if 'db_inited' not in st.session_state:
    init_db()
    st.session_state.db_inited = True

# --- 3. POMOCNÉ FUNKCE ---
def hash_password(password): return hashlib.sha256(str.encode(password)).hexdigest()
def remove_accents(s): return "".join([c for c in unicodedata.normalize('NFKD', str(s)) if not unicodedata.combining(c)]) if s else ""
def format_date(d):
    try: return datetime.strptime(str(d)[:10], '%Y-%m-%d').strftime('%d.%m.%Y') if isinstance(d, str) else d.strftime('%d.%m.%Y')
    except: return ""
def generate_random_password(length=8): return ''.join(random.choice(string.ascii_letters + string.digits) for i in range(length))
def generate_license_key(): return '-'.join([''.join(random.choices(string.ascii_uppercase + string.digits, k=4)) for _ in range(4)])
def check_license_validity(uid):
    res = run_query("SELECT license_valid_until FROM users WHERE id=?", (uid,), single=True)
    if not res or not res['license_valid_until']: return False, "Žádná"
    try:
        exp = datetime.strptime(str(res['license_valid_until'])[:10], '%Y-%m-%d').date()
        return (True, exp) if exp >= date.today() else (False, exp)
    except: return False, "Chyba"

def get_next_invoice_number(kat_id, uid):
    res = run_query("SELECT prefix, aktualni_cislo FROM kategorie WHERE id = ? AND user_id = ?", (kat_id, uid), single=True)
    if res: return (res['aktualni_cislo'], f"{res['prefix']}{res['aktualni_cislo']}", res['prefix'])
    return (1, "1", "")

@st.cache_data(ttl=86400)
def get_ares_data(ico):
    if not ico: return None
    ico = "".join(filter(str.isdigit, str(ico))).zfill(8)
    url = f"https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}"
    headers = {"accept": "application/json", "User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, verify=False, timeout=5)
        if r.status_code == 200:
            data = r.json(); sidlo = data.get('sidlo', {})
            ulice = sidlo.get('nazevUlice', ''); cislo_dom = sidlo.get('cisloDomovni'); cislo_or = sidlo.get('cisloOrientacni'); obec = sidlo.get('nazevObce', ''); psc = sidlo.get('psc', '')
            cislo_txt = str(cislo_dom) if cislo_dom else ""
            if cislo_or: cislo_txt += f"/{cislo_or}"
            adr_parts = []
            if ulice: adr_parts.append(f"{ulice} {cislo_txt}".strip())
            elif cislo_txt and obec: adr_parts.append(f"{obec} {cislo_txt}")
            if psc and obec: adr_parts.append(f"{psc} {obec}")
            plna_adresa = ", ".join(adr_parts)
            if not plna_adresa: plna_adresa = sidlo.get('textovaAdresa', '')
            dic = data.get('dic', '')
            if not dic: dic = data.get('dicId', '')
            return {"jmeno": data.get('obchodniJmeno', ''), "adresa": plna_adresa, "ico": ico, "dic": dic}
    except Exception as e: print(f"ARES Error: {e}")
    return None

def process_logo(uploaded_file):
    if not uploaded_file: return None
    try:
        img = Image.open(uploaded_file)
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        b = io.BytesIO(); img.save(b, format='PNG'); return b.getvalue()
    except: return None

def send_email_custom(to, sub, body, attachment=None, filename="zaloha.json"):
    if not SYSTEM_EMAIL["enabled"] or not SYSTEM_EMAIL["password"]: return False
    try:
        msg = MIMEMultipart(); msg['From'] = formataddr((SYSTEM_EMAIL["display_name"], SYSTEM_EMAIL["email"])); msg['To'] = to; msg['Subject'] = sub
        msg.attach(MIMEText(body, 'plain'))
        if attachment:
            part = MIMEApplication(attachment, Name=filename); part['Content-Disposition'] = f'attachment; filename="{filename}"'; msg.attach(part)
        s = smtplib.SMTP_SSL(SYSTEM_EMAIL["server"], SYSTEM_EMAIL["port"]); s.login(SYSTEM_EMAIL["email"], SYSTEM_EMAIL["password"]); s.sendmail(SYSTEM_EMAIL["email"], to, msg.as_string()); s.quit()
        return True
    except: return False

def send_welcome_email_db(to, name, license_key=None):
    tpl = run_query("SELECT subject, body FROM email_templates WHERE name='welcome'", single=True); tpl_dict = dict(tpl) if tpl else {}
    s = tpl_dict.get('subject', "Vítejte"); b = tpl_dict.get('body', f"Dobrý den {name}").replace("{name}", name)
    if license_key: b += f"\n\n🎁 DÁREK: Získáváte 14 dní verze PRO ZDARMA!\nVáš licenční klíč: {license_key}\n(Byl automaticky aktivován, nemusíte nic dělat)."
    return send_email_custom(to, s, b)

def get_export_data(user_id):
    export_data = {}
    p = get_pool(); conn = p.getconn()
    try:
        for t in ['nastaveni', 'klienti', 'kategorie', 'faktury', 'vydaje']:
            df = pd.read_sql(f"SELECT * FROM {t} WHERE user_id=%s", conn, params=(user_id,))
            if 'logo_blob' in df.columns: df['logo_blob'] = df['logo_blob'].apply(lambda x: base64.b64encode(x).decode('utf-8') if x else None)
            export_data[t] = df.to_dict(orient='records')
        df_pol = pd.read_sql("SELECT fp.* FROM faktura_polozky fp JOIN faktury f ON fp.faktura_id=f.id WHERE f.user_id=%s", conn, params=(user_id,))
        export_data['faktura_polozky'] = df_pol.to_dict(orient='records')
    except Exception as e: print(f"Export Error: {e}"); return "{}"
    finally: p.putconn(conn)
    return json.dumps(export_data, default=str)

# --- ISDOC & PDF ---
def generate_isdoc(faktura_id, uid):
    data = run_query("SELECT f.*, k.jmeno, k.ico, k.adresa, m.nazev as m_nazev, m.ico as m_ico FROM faktury f JOIN klienti k ON f.klient_id=k.id JOIN nastaveni m ON f.user_id=m.user_id WHERE f.id=?", (faktura_id,), True)
    if not data: return None
    d = dict(data)
    root = ET.Element("Invoice", xmlns="http://isdoc.cz/namespace/2013", version="6.0.1")
    ET.SubElement(root, "DocumentType").text = "1"; ET.SubElement(root, "ID").text = str(d.get('cislo_full', d['id']))
    ET.SubElement(root, "IssueDate").text = str(d['datum_vystaveni']); ET.SubElement(root, "TaxPointDate").text = str(d['datum_duzp']); ET.SubElement(root, "LocalCurrencyCode").text = "CZK"
    sp = ET.SubElement(root, "AccountingSupplierParty"); p = ET.SubElement(sp, "Party"); pn = ET.SubElement(p, "PartyName"); ET.SubElement(pn, "Name").text = str(d.get('m_nazev', '')); pi = ET.SubElement(p, "PartyIdentification"); ET.SubElement(pi, "ID").text = str(d.get('m_ico', ''))
    cp = ET.SubElement(root, "AccountingCustomerParty"); pc = ET.SubElement(cp, "Party"); pnc = ET.SubElement(pc, "PartyName"); ET.SubElement(pnc, "Name").text = str(d.get('jmeno', '')); pic = ET.SubElement(pc, "PartyIdentification"); ET.SubElement(pic, "ID").text = str(d.get('ico', ''))
    amt = ET.SubElement(root, "LegalMonetaryTotal"); ET.SubElement(amt, "TaxExclusiveAmount").text = str(d['castka_celkem']); ET.SubElement(amt, "TaxInclusiveAmount").text = str(d['castka_celkem']); ET.SubElement(amt, "PayableAmount").text = str(d['castka_celkem'])
    return ET.tostring(root, encoding='utf-8')

def generate_pdf(faktura_id, uid, is_pro):
    use_font = os.path.exists(FONT_FILE)
    def txt(text): return remove_accents(str(text)) if text else ""
    def fmt_price(val): return f"{val:,.2f}".replace(",", " ").replace(".", ",")
    class PDF(FPDF):
        def header(self):
            if use_font:
                try: self.add_font('ArialCS', '', FONT_FILE, uni=True); self.add_font('ArialCS', 'B', FONT_FILE, uni=True); self.set_font('ArialCS', 'B', 24)
                except: self.set_font('Arial', 'B', 24)
            else: self.set_font('Arial', 'B', 24)
            self.set_text_color(50, 50, 50); self.cell(0, 10, 'FAKTURA', 0, 1, 'R'); self.ln(5)
    try:
        raw_data = run_query("SELECT f.*, k.jmeno as k_jmeno, k.adresa as k_adresa, k.ico as k_ico, k.dic as k_dic, kat.barva, kat.logo_blob, kat.prefix FROM faktury f JOIN klienti k ON f.klient_id=k.id JOIN kategorie kat ON f.kategorie_id=kat.id WHERE f.id=? AND f.user_id=?", (faktura_id, uid), single=True)
        if not raw_data: return None
        data = dict(raw_data)
        polozky = [dict(p) for p in run_query("SELECT * FROM faktura_polozky WHERE faktura_id=?", (faktura_id,))]
        moje = dict(run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1", (uid,), single=True) or {})
        pdf = PDF(); pdf.add_page()
        if use_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)
        if data.get('logo_blob'):
            try:
                fn = f"l_{faktura_id}.png"
                open(fn, "wb").write(data['logo_blob'])
                pdf.image(fn, 10, 10, 50)
                os.remove(fn)
            except: pass
        cislo_f = data.get('cislo_full') or f"{data.get('prefix','')}{data.get('cislo','')}"
        r, g, b = 0, 0, 0
        if is_pro and data.get('barva'):
            try: c = data['barva'].lstrip('#'); r, g, b = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
            except: pass
        pdf.set_text_color(100); pdf.set_y(55)
        pdf.cell(95, 5, "DODAVATEL:", 0, 0); pdf.cell(95, 5, "ODBERATEL:", 0, 1); pdf.set_text_color(0); y = pdf.get_y()
        if use_font: pdf.set_font('ArialCS', 'B', 11)
        else: pdf.set_font('Arial', 'B', 11)
        pdf.cell(95, 5, txt(moje.get('nazev', '')), 0, 1)
        if use_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)
        dod_lines = [txt(moje.get('adresa', ''))] if moje.get('adresa') else []
        if moje.get('ico'): dod_lines.append(txt(f"IC: {moje['ico']}"))
        if moje.get('dic'): dod_lines.append(txt(f"DIC: {moje['dic']}"))
        if moje.get('email'): dod_lines.append(txt(moje['email']))
        pdf.multi_cell(95, 5, "\n".join(dod_lines))
        pdf.set_xy(105, y)
        if use_font: pdf.set_font('ArialCS', 'B', 11)
        else: pdf.set_font('Arial', 'B', 11)
        pdf.cell(95, 5, txt(data.get('k_jmeno')), 0, 1)
        pdf.set_xy(105, pdf.get_y())
        if use_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)
        odb_lines = [txt(data.get('k_adresa', ''))] if data.get('k_adresa') else []
        if data.get('k_ico'): odb_lines.append(txt(f"IC: {data['k_ico']}"))
        if data.get('k_dic'): odb_lines.append(txt(f"DIC: {data['k_dic']}"))
        pdf.multi_cell(95, 5, "\n".join(odb_lines))
        pdf.ln(10); pdf.set_fill_color(r, g, b); pdf.rect(10, pdf.get_y(), 190, 2, 'F'); pdf.ln(5)
        if use_font: pdf.set_font('ArialCS', 'B', 12)
        else: pdf.set_font('Arial', 'B', 12)
        pdf.cell(100, 8, txt(f"Faktura c.: {cislo_f}"), 0, 1)
        if use_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)
        pdf.cell(50, 6, "Vystaveno:", 0, 0); pdf.cell(50, 6, format_date(data.get('datum_vystaveni')), 0, 1)
        pdf.cell(50, 6, "Splatnost:", 0, 0); pdf.cell(50, 6, format_date(data.get('datum_splatnosti')), 0, 1)
        if moje.get('ucet'): pdf.cell(50, 6, "Ucet:", 0, 0); pdf.cell(50, 6, txt(moje.get('ucet')), 0, 1)
        else: pdf.ln(6)
        pdf.cell(50, 6, "VS:", 0, 0); pdf.cell(50, 6, txt(data.get('variabilni_symbol')), 0, 1)
        if data.get('uvodni_text'): pdf.ln(8); pdf.multi_cell(190, 5, txt(data['uvodni_text']))
        pdf.ln(10); pdf.set_fill_color(240, 240, 240)
        if use_font: pdf.set_font('ArialCS', 'B', 10)
        else: pdf.set_font('Arial', 'B', 10)
        pdf.cell(140, 10, txt("POLOZKY"), 0, 0, 'L', True); pdf.cell(50, 10, "CENA", 0, 1, 'R', True)
        if use_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)
        pdf.set_draw_color(200, 200, 200); pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        for p in polozky:
            if not p.get('nazev'): continue
            pdf.cell(140, 8, txt(p.get('nazev')), 0, 0, 'L'); pdf.cell(50, 8, f"{fmt_price(p.get('cena', 0))} {txt('Kc')}", 0, 1, 'R'); pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        if use_font: pdf.set_font('ArialCS', 'B', 14)
        else: pdf.set_font('Arial', 'B', 14)
        pdf.cell(190, 10, f"CELKEM: {fmt_price(data.get('castka_celkem', 0))} {txt('Kc')}", 0, 1, 'R')
        if is_pro and moje.get('iban'):
            try:
                ic = str(moje['iban']).replace(" ", "").upper(); vs = str(data.get('variabilni_symbol', ''))
                qr = f"SPD*1.0*ACC:{ic}*AM:{data.get('castka_celkem')}*CC:CZK*X-VS:{vs}*MSG:{remove_accents('Faktura '+cislo_f)}"
                q = qrcode.make(qr); fn_q = f"q_{faktura_id}.png"; q.save(fn_q)
                pdf.image(fn_q, 10, pdf.get_y()+2, 30); os.remove(fn_q)
            except: pass
        return pdf.output(dest='S').encode('latin-1')
    except Exception as e: return f"CHYBA: {str(e)}"

@st.cache_data(show_spinner=False, max_entries=500)
def get_cached_pdf(faktura_id, uid, is_pro, row_hash): return generate_pdf(faktura_id, uid, is_pro)

@st.cache_data(show_spinner=False, max_entries=500)
def get_cached_isdoc(faktura_id, uid, row_hash): return generate_isdoc(faktura_id, uid)

# --- SESSION ---
if 'user_id' not in st.session_state: st.session_state.user_id = None
if 'role' not in st.session_state: st.session_state.role = 'user'
if 'is_pro' not in st.session_state: st.session_state.is_pro = False
if 'items_df' not in st.session_state: st.session_state.items_df = pd.DataFrame(columns=["Popis položky", "Cena"])
if 'form_reset_id' not in st.session_state: st.session_state.form_reset_id = 0
if 'ares_data' not in st.session_state: st.session_state.ares_data = {}

def reset_forms():
    st.session_state.form_reset_id += 1; st.session_state.ares_data = {}
    st.session_state.items_df = pd.DataFrame(columns=["Popis položky", "Cena"])

# --- LOGIN & LANDING PAGE ---
if not st.session_state.user_id:
    col1, col2, col3 = st.columns([1, 10, 1])
    with col2:
        st.markdown("""
<div style="padding: 40px 0 20px 0;">
    <span class="brand-logo">💎</span>
    <div class="brand-title">MojeFaktury</div>
    <p class="brand-desc">Fakturace pro moderní živnostníky.<br>Rychlá, přehledná a vždy po ruce.</p>
</div>

<div class="feature-grid">
    <div class="feature-item">✦ <b>14 dní PRO zdarma</b> — žádná kreditka</div>
    <div class="feature-item">✦ <b>Faktura do 30 sekund</b> — přímočarý tok</div>
    <div class="feature-item">✦ <b>ARES integrace</b> — auto-vyplnění firmy</div>
    <div class="feature-item">✦ <b>Export ISDOC</b> — pro účetní</div>
    <div class="feature-item">✦ <b>Daňová kalkulačka</b> — paušál vs. skutečné</div>
</div>
""", unsafe_allow_html=True)

        t1, t2, t3 = st.tabs(["  Přihlášení  ", "  Registrace  ", "  Zapomenuté heslo  "])
        with t1:
            with st.form("log"):
                u = st.text_input("Uživatelské jméno nebo Email").strip()
                p = st.text_input("Heslo", type="password").strip()
                if st.form_submit_button("Vstoupit →", type="primary", use_container_width=True):
                    r = run_query("SELECT * FROM users WHERE (username=? OR email=?) AND password_hash=?", (u, u, hash_password(p)), single=True)
                    if r:
                        st.session_state.user_id = r['id']; st.session_state.role = r['role']; st.session_state.username = r['username']; st.session_state.full_name = r['full_name']; st.session_state.user_email = r['email']
                        st.session_state.force_pw_change = dict(r).get('force_password_change', 0)
                        valid, exp = check_license_validity(r['id'])
                        st.session_state.is_pro = valid
                        run_command("UPDATE users SET last_active=? WHERE id=?", (datetime.now().isoformat(), r['id'])); st.rerun()
                    else: st.error("Neplatné údaje. Zkontrolujte, zda jste nezkopírovali heslo s mezerou.")
        with t2:
            with st.form("reg"):
                f = st.text_input("Jméno a Příjmení").strip()
                u = st.text_input("Login").strip()
                e = st.text_input("Email").strip()
                t_tel = st.text_input("Telefon").strip()
                p = st.text_input("Heslo", type="password").strip()
                if st.form_submit_button("Vytvořit účet →", use_container_width=True):
                    try:
                        uid_new = run_command("INSERT INTO users (username,password_hash,full_name,email,phone,created_at,force_password_change) VALUES (?,?,?,?,?,?,0)", (u, hash_password(p), f, e, t_tel, datetime.now().isoformat()))
                        trial_key = generate_license_key()
                        exp_date = date.today() + timedelta(days=14)
                        run_command("INSERT INTO licencni_klice (kod, dny_platnosti, vygenerovano, poznamka, pouzito_uzivatelem_id) VALUES (?,?,?,?,?)", (trial_key, 14, datetime.now().isoformat(), "Auto-Trial 14 dní", uid_new))
                        run_command("UPDATE users SET license_key=?, license_valid_until=? WHERE id=?", (trial_key, exp_date, uid_new))
                        send_welcome_email_db(e, f, trial_key)
                        st.success("Hotovo! Účet vytvořen + 14 dní PRO zdarma. Přihlašte se.")
                    except Exception as ex: st.error(f"Chyba: {ex}")
        with t3:
            with st.form("forgot"):
                fe = st.text_input("Váš Email").strip()
                if st.form_submit_button("Resetovat heslo →", use_container_width=True):
                    usr = run_query("SELECT * FROM users WHERE email=?", (fe,), single=True)
                    if usr:
                        new_pass = generate_random_password()
                        run_command("UPDATE users SET password_hash=?, force_password_change=1 WHERE id=?", (hash_password(new_pass), usr['id']))
                        email_body = f"Dobrý den,\n\nVaše přihlašovací údaje byly obnoveny.\n\nPřihlašovací email: {usr['email']}\nNové heslo: {new_pass}\n\nPo přihlášení budete vyzváni ke změně hesla."
                        if send_email_custom(fe, "Reset hesla - MojeFaktury", email_body):
                            st.success("Nové heslo bylo odesláno do Vaší schránky.")
                        else: st.error("Chyba při odesílání emailu.")
                    else: st.error("Email nenalezen.")
    st.stop()

# --- APP ---
uid = st.session_state.user_id; role = st.session_state.role; is_pro = st.session_state.is_pro
full_name_display = st.session_state.full_name or st.session_state.username
run_command("UPDATE users SET last_active=? WHERE id=?", (datetime.now().isoformat(), uid))

if st.session_state.get('force_pw_change', 0) == 1:
    st.markdown("<h2>⚠️ Změna hesla vyžadována</h2>", unsafe_allow_html=True)
    with st.form("force_change"):
        np1 = st.text_input("Nové heslo", type="password").strip()
        np2 = st.text_input("Potvrzení hesla", type="password").strip()
        if st.form_submit_button("Změnit heslo a pokračovat →", type="primary"):
            if np1 and np1 == np2:
                run_command("UPDATE users SET password_hash=?, force_password_change=0 WHERE id=?", (hash_password(np1), uid)); st.session_state.force_pw_change = 0; st.success("Heslo změněno!"); st.rerun()
            else: st.error("Hesla se neshodují.")
    st.stop()

# SIDEBAR
badge_class = "badge-pro" if is_pro else "badge-free"
badge_text = "⭐ PRO" if is_pro else "FREE"
st.sidebar.markdown(f"""
<div class="sidebar-card">
    <div class="sidebar-name">{full_name_display}</div>
    <div class="sidebar-meta">{st.session_state.username}</div>
    <span class="badge {badge_class}">{badge_text}</span>
</div>
""", unsafe_allow_html=True)

if st.sidebar.button("← Odhlásit"):
    st.session_state.user_id = None; st.rerun()

# --- ADMIN ---
if role == 'admin':
    st.markdown('<div class="section-header"><div class="section-icon">👑</div><div class="section-title">Admin Dashboard</div></div>', unsafe_allow_html=True)
    u_count = run_query("SELECT COUNT(*) FROM users WHERE role!='admin'", single=True)['count'] or 0
    f_count = run_query("SELECT COUNT(*) FROM faktury", single=True)['count'] or 0
    t_rev = run_query("SELECT SUM(castka_celkem) FROM faktury", single=True)['sum'] or 0
    avg_u = t_rev / u_count if u_count > 0 else 0
    avg_f = t_rev / f_count if f_count > 0 else 0
    st.markdown(f"""
    <div class="admin-grid">
        <div class="admin-card"><div class="admin-card-value">{u_count}</div><div class="admin-card-label">Uživatelů</div></div>
        <div class="admin-card"><div class="admin-card-value">{t_rev:,.0f} Kč</div><div class="admin-card-label">Celk. obrat</div></div>
        <div class="admin-card"><div class="admin-card-value">{avg_u:,.0f} Kč</div><div class="admin-card-label">Obrat / User</div></div>
        <div class="admin-card"><div class="admin-card-value">{avg_f:,.0f} Kč</div><div class="admin-card-label">Prům. faktura</div></div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()
    tabs = st.tabs(["👥 Uživatelé & Licence", "🔑 Generátor klíčů", "📧 E-mailing"])
    with tabs[0]:
        st.subheader("Seznam uživatelů")
        fk = run_query("SELECT * FROM licencni_klice WHERE pouzito_uzivatelem_id IS NULL ORDER BY id DESC")
        key_dict = {f"{k['kod']} ({k['dny_platnosti']} dní)": k for k in fk}
        for u in run_query("SELECT * FROM users WHERE role!='admin' ORDER BY id DESC"):
            exp_date = u['license_valid_until']; is_active_lic = False
            if exp_date:
                try:
                    dobj = datetime.strptime(str(exp_date)[:10], '%Y-%m-%d').date()
                    if dobj >= date.today(): is_active_lic = True
                except: pass
            status_badge = "⭐ PRO" if is_active_lic else "FREE"
            with st.expander(f"{'⭐' if is_active_lic else '○'} {u['username']} — {u['email']}"):
                c1, c2 = st.columns(2)
                c1.write(f"**Jméno:** {u['full_name']}")
                c1.write(f"**Tel:** {u['phone']}")
                c1.write(f"**Vytvořeno:** {format_date(u['created_at'])}")
                current_valid = date.today()
                if u['license_valid_until']:
                    try: current_valid = datetime.strptime(str(u['license_valid_until'])[:10], '%Y-%m-%d').date()
                    except: pass
                new_valid = c2.date_input("Platnost do:", value=current_valid, key=f"md_{u['id']}")
                if c2.button("💾 Uložit datum", key=f"bd_{u['id']}"): run_command("UPDATE users SET license_valid_until=? WHERE id=?", (new_valid, u['id'])); st.success("Datum aktualizováno"); st.rerun()
                sel_key = c2.selectbox("Přiřadit klíč", ["-- Vyberte --"] + list(key_dict.keys()), key=f"sk_{u['id']}")
                if c2.button("Aktivovat klíčem", key=f"btn_{u['id']}"):
                    if sel_key != "-- Vyberte --":
                        k_data = key_dict[sel_key]; new_exp = date.today() + timedelta(days=k_data['dny_platnosti'])
                        run_command("UPDATE users SET license_key=?, license_valid_until=? WHERE id=?", (k_data['kod'], new_exp, u['id'])); run_command("UPDATE licencni_klice SET pouzito_uzivatelem_id=? WHERE id=?", (u['id'], k_data['id'])); st.success("Licence aktivována!"); st.rerun()
                if st.button("🗑️ Smazat uživatele", key=f"del_{u['id']}", type="primary"): run_command("DELETE FROM users WHERE id=?", (u['id'],)); st.rerun()
    with tabs[1]:
        days_val = st.number_input("Platnost (dny)", value=365, min_value=1); note_val = st.text_input("Poznámka")
        if st.button("Vygenerovat nový klíč"):
            k = generate_license_key(); run_command("INSERT INTO licencni_klice (kod, dny_platnosti, vygenerovano, poznamka) VALUES (?,?,?,?)", (k, days_val, datetime.now().isoformat(), note_val)); st.success(f"Vytvořeno: `{k}`")
        for k in run_query("SELECT * FROM licencni_klice ORDER BY id DESC"): st.code(f"{k['kod']} | {k['dny_platnosti']} dní | {'🔴 Použit' if k['pouzito_uzivatelem_id'] else '🟢 Volný'} | {k['poznamka']}")
    with tabs[2]:
        st.subheader("Šablona uvítacího emailu")
        tpl = run_query("SELECT * FROM email_templates WHERE name='welcome'", single=True); tpl_dict = dict(tpl) if tpl else {}
        with st.form("wm"):
            ws = st.text_input("Předmět", value=tpl_dict.get('subject', '')); wb = st.text_area("Text (použijte {name} pro jméno)", value=tpl_dict.get('body', ''), height=200)
            if st.form_submit_button("Uložit šablonu"): run_command("INSERT INTO email_templates (name, subject, body) VALUES ('welcome', ?, ?) ON CONFLICT (name) DO UPDATE SET subject = EXCLUDED.subject, body = EXCLUDED.body", (ws, wb)); st.success("Uloženo")
        st.divider()
        st.subheader("Hromadná zpráva")
        with st.form("mm"):
            ms = st.text_input("Předmět"); mb = st.text_area("Zpráva pro všechny uživatele", height=150)
            if st.form_submit_button("Odeslat všem"):
                count = 0
                for u in run_query("SELECT email FROM users WHERE role!='admin' AND email IS NOT NULL"):
                    if send_email_custom(u['email'], ms, mb): count += 1
                st.success(f"Odesláno na {count} emailů.")

# --- USER ---
else:
    menu = st.sidebar.radio(" ", ["📄 Faktury", "📊 Dashboard", "🏛️ Daně", "💸 Výdaje", "👥 Klienti", "🏷️ Kategorie", "⚙️ Nastavení"])

    # ==================== FAKTURY ====================
    if "Faktury" in menu:
        st.markdown('<div class="section-header"><div class="section-icon">📄</div><div class="section-title">Faktury</div></div>', unsafe_allow_html=True)

        # Rok filtr + stats — paralelně načteno
        years = [r['substring'] for r in run_query("SELECT DISTINCT SUBSTRING(datum_vystaveni, 1, 4) as substring FROM faktury WHERE user_id=?", (uid,))]
        if str(datetime.now().year) not in years: years.append(str(datetime.now().year))
        sy = st.selectbox("Rok (statistiky)", sorted(list(set(years)), reverse=True), label_visibility="collapsed")

        # Všechny 3 stats query najednou
        sc_y = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND SUBSTRING(datum_vystaveni, 1, 4)=?", (uid, sy), True)['sum'] or 0
        sc_a = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?", (uid,), True)['sum'] or 0
        su_a = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0", (uid,), True)['sum'] or 0

        st.markdown(f"""
        <div class="stats-row">
            <div class="stat-card green">
                <div class="stat-label">Obrat {sy}</div>
                <div class="stat-value green">{sc_y:,.0f}</div>
                <div class="stat-sub">Kč</div>
            </div>
            <div class="stat-card gold">
                <div class="stat-label">Celkem</div>
                <div class="stat-value gold">{sc_a:,.0f}</div>
                <div class="stat-sub">Kč</div>
            </div>
            <div class="stat-card red">
                <div class="stat-label">Neuhrazeno</div>
                <div class="stat-value red">{su_a:,.0f}</div>
                <div class="stat-sub">Kč</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Nová faktura
        with st.expander("➕  Nová faktura"):
            p_pool = get_pool(); conn = p_pool.getconn()
            try:
                kli = pd.read_sql("SELECT id, jmeno FROM klienti WHERE user_id=%s", conn, params=(uid,))
                kat = pd.read_sql("SELECT id, nazev FROM kategorie WHERE user_id=%s", conn, params=(uid,))
            finally: p_pool.putconn(conn)

            if kli.empty:
                st.warning("Nejprve vytvořte klienta v sekci Klienti.")
            elif not is_pro and kat.empty:
                run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva) VALUES (?, 'Obecná', 'FV', 1, '#000000')", (uid,)); get_cached_pdf.clear(); st.rerun()
            else:
                rid = st.session_state.form_reset_id; c1, c2 = st.columns(2)
                sk = c1.selectbox("Klient", kli['jmeno'], key=f"k_{rid}"); sc = c2.selectbox("Kategorie", kat['nazev'], key=f"c_{rid}")
                if not kli[kli['jmeno'] == sk].empty and not kat[kat['nazev'] == sc].empty:
                    kid = int(kli[kli['jmeno'] == sk]['id'].values[0]); cid = int(kat[kat['nazev'] == sc]['id'].values[0])
                    _, full, _ = get_next_invoice_number(cid, uid)
                    st.markdown(f'<div class="info-callout">Číslo dokladu: <span>{full}</span></div>', unsafe_allow_html=True)
                    d1, d2 = st.columns(2)
                    dv = d1.date_input("Vystavení", date.today(), key=f"d1_{rid}")
                    ds = d2.date_input("Splatnost", date.today() + timedelta(14), key=f"d2_{rid}")
                    ut = st.text_input("Úvodní text", "Fakturujeme Vám:", key=f"ut_{rid}")
                    ed = st.data_editor(st.session_state.items_df, num_rows="dynamic", use_container_width=True, key=f"e_{rid}")
                    total_sum = float(pd.to_numeric(ed["Cena"], errors='coerce').fillna(0).sum()) if not ed.empty and "Cena" in ed.columns else 0.0
                    st.markdown(f"""
                    <div class="total-line">
                        <span class="total-label">Celkem k úhradě</span>
                        <span class="total-amount">{total_sum:,.2f} Kč</span>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Vystavit fakturu →", type="primary", key=f"b_{rid}"):
                        fid = run_command("INSERT INTO faktury (user_id, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_splatnosti, castka_celkem, variabilni_symbol, uvodni_text) VALUES (?,?,?,?,?,?,?,?,?)", (uid, full, kid, cid, dv, ds, total_sum, re.sub(r"\D", "", full), ut))
                        for _, r in ed.iterrows():
                            if r.get("Popis položky"): run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (fid, r["Popis položky"], float(r.get("Cena", 0))))
                        run_command("UPDATE kategorie SET aktualni_cislo = aktualni_cislo + 1 WHERE id = ?", (cid,))
                        reset_forms(); get_cached_pdf.clear(); get_cached_isdoc.clear(); st.success("Faktura vystavena!"); st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # Filtry
        fcol1, fcol2 = st.columns(2)
        sel_cli = fcol1.selectbox("Klient", ["Všichni"] + [c['jmeno'] for c in run_query("SELECT jmeno FROM klienti WHERE user_id=?", (uid,))])
        db_years = [y['substring'] for y in run_query("SELECT DISTINCT SUBSTRING(datum_vystaveni, 1, 4) as substring FROM faktury WHERE user_id=?", (uid,))]
        sel_yf = fcol2.selectbox("Rok", ["Všechny"] + sorted(db_years, reverse=True))

        if sel_cli != "Všichni":
            cl_all = run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=?", (uid, sel_cli), True)['sum'] or 0
            cl_due = run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=? AND f.uhrazeno=0", (uid, sel_cli), True)['sum'] or 0
            cl_yr = 0
            if sel_yf != "Všechny":
                cl_yr = run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=? AND SUBSTRING(f.datum_vystaveni, 1, 4)=?", (uid, sel_cli, sel_yf), True)['sum'] or 0
            st.markdown(f"""
            <div class="mini-stats-row">
                <div class="mini-stat"><div class="mini-stat-label">Historie</div><div class="mini-stat-value">{cl_all:,.0f} Kč</div></div>
                <div class="mini-stat"><div class="mini-stat-label">Obrat {sel_yf if sel_yf != 'Všechny' else ''}</div><div class="mini-stat-value green">{cl_yr:,.0f} Kč</div></div>
                <div class="mini-stat"><div class="mini-stat-label">Dluží</div><div class="mini-stat-value red">{cl_due:,.0f} Kč</div></div>
            </div>
            """, unsafe_allow_html=True)

        q = "SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=%s"; p = [uid]
        if sel_cli != "Všichni": q += " AND k.jmeno=%s"; p.append(sel_cli)
        if sel_yf != "Všechny": q += " AND SUBSTRING(f.datum_vystaveni, 1, 4)=%s"; p.append(sel_yf)

        p_pool = get_pool(); conn = p_pool.getconn()
        try: df_faktury = pd.read_sql(q + " ORDER BY f.id DESC LIMIT 20", conn, params=p)
        finally: p_pool.putconn(conn)

        for row in df_faktury.to_dict('records'):
            cf = row.get('cislo_full') or f"F{row['id']}"
            paid = row['uhrazeno']
            status_html = f'<span class="status-paid">Zaplaceno</span>' if paid else f'<span class="status-unpaid">Čeká na platbu</span>'
            with st.expander(f"{'✅' if paid else '⏳'}  {cf}  ·  {row['jmeno']}  ·  {row['castka_celkem']:,.0f} Kč"):
                st.markdown(f"<div style='margin-bottom:12px;'>{status_html} &nbsp; <small style='color:#475569'>{format_date(row.get('datum_splatnosti', ''))}</small></div>", unsafe_allow_html=True)
                c1, c2, c3 = st.columns([1, 1, 1])
                if paid:
                    if c1.button("↩ Zrušit úhradu", key=f"u0_{row['id']}"): run_command("UPDATE faktury SET uhrazeno=0 WHERE id=?", (row['id'],)); get_cached_pdf.clear(); get_cached_isdoc.clear(); st.rerun()
                else:
                    if c1.button("✓ Zaplaceno", key=f"u1_{row['id']}"): run_command("UPDATE faktury SET uhrazeno=1 WHERE id=?", (row['id'],)); get_cached_pdf.clear(); get_cached_isdoc.clear(); st.rerun()

                row_hash = str(row)
                pdf_output = get_cached_pdf(row['id'], uid, is_pro, row_hash)
                if isinstance(pdf_output, bytes): c2.download_button("↓ PDF", pdf_output, f"{cf}.pdf", "application/pdf", key=f"pd_{row['id']}")

                if is_pro:
                    isdoc_bytes = get_cached_isdoc(row['id'], uid, row_hash)
                    if isdoc_bytes: c2.download_button("↓ ISDOC", isdoc_bytes, f"{cf}.isdoc", "application/xml", key=f"isd_{row['id']}")

                f_edit_key = f"edit_f_{row['id']}"
                if f_edit_key not in st.session_state: st.session_state[f_edit_key] = False
                if c3.button("✏️ Upravit", key=f"be_{row['id']}"): st.session_state[f_edit_key] = True; st.rerun()

                if st.session_state[f_edit_key]:
                    with st.form(f"fe_{row['id']}"):
                        nd = st.date_input("Splatnost", pd.to_datetime(row['datum_splatnosti']))
                        nm = st.text_input("Popis", row['muj_popis'] or ""); nut = st.text_input("Úvodní text", row['uvodni_text'] or "")
                        p_item = get_pool(); conn_item = p_item.getconn()
                        try: cur_i = pd.read_sql("SELECT nazev as \"Popis položky\", cena as \"Cena\" FROM faktura_polozky WHERE faktura_id=%s", conn_item, params=(row['id'],))
                        finally: p_item.putconn(conn_item)
                        ned = st.data_editor(cur_i, num_rows="dynamic", use_container_width=True)
                        if st.form_submit_button("Uložit změny"):
                            ntot = float(pd.to_numeric(ned["Cena"], errors='coerce').fillna(0).sum())
                            run_command("UPDATE faktury SET datum_splatnosti=?, muj_popis=?, castka_celkem=?, uvodni_text=? WHERE id=?", (nd, nm, ntot, nut, row['id']))
                            run_command("DELETE FROM faktura_polozky WHERE faktura_id=?", (row['id'],))
                            for _, rw in ned.iterrows():
                                if rw.get("Popis položky"): run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (row['id'], rw["Popis položky"], float(rw.get("Cena", 0))))
                            st.session_state[f_edit_key] = False; get_cached_pdf.clear(); get_cached_isdoc.clear(); st.rerun()

                if c3.button("🔄 Duplikovat", key=f"dup_{row['id']}"):
                    new_num, new_full, _ = get_next_invoice_number(row['kategorie_id'], uid)
                    new_fid = run_command("""INSERT INTO faktury (user_id, cislo, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_splatnosti, castka_celkem, variabilni_symbol, uvodni_text, muj_popis) VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (uid, new_num, new_full, row['klient_id'], row['kategorie_id'], date.today(), date.today() + timedelta(14), row['castka_celkem'], re.sub(r"\D", "", new_full), row['uvodni_text'], row['muj_popis']))
                    items = run_query("SELECT * FROM faktura_polozky WHERE faktura_id=?", (row['id'],))
                    for it in items: run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (new_fid, it['nazev'], it['cena']))
                    run_command("UPDATE kategorie SET aktualni_cislo = aktualni_cislo + 1 WHERE id = ?", (row['kategorie_id'],))
                    get_cached_pdf.clear(); get_cached_isdoc.clear(); st.success(f"Faktura {new_full} vytvořena!"); st.rerun()

                if st.button("🗑 Smazat", key=f"bd_{row['id']}"): run_command("DELETE FROM faktury WHERE id=?", (row['id'],)); get_cached_pdf.clear(); get_cached_isdoc.clear(); st.rerun()

    # ==================== DASHBOARD ====================
    elif "Dashboard" in menu:
        st.markdown('<div class="section-header"><div class="section-icon">📊</div><div class="section-title">Přehled podnikání</div></div>', unsafe_allow_html=True)
        tot_rev = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?", (uid,), True)['sum'] or 0
        tot_paid = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=1", (uid,), True)['sum'] or 0
        tot_due = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0", (uid,), True)['sum'] or 0
        count_inv = run_query("SELECT COUNT(*) FROM faktury WHERE user_id=?", (uid,), True)['count'] or 0
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Celkový obrat", f"{tot_rev:,.0f} Kč")
        mc2.metric("Zaplaceno", f"{tot_paid:,.0f} Kč", delta=f"{int(tot_paid/tot_rev*100) if tot_rev else 0} %")
        mc3.metric("Čeká na platbu", f"{tot_due:,.0f} Kč", delta="-", delta_color="inverse")
        mc4.metric("Faktur celkem", count_inv)
        st.divider()
        gc1, gc2 = st.columns([2, 1])
        p_graphs = get_pool(); conn_graphs = p_graphs.getconn()
        try:
            with gc1:
                st.subheader("Vývoj v čase")
                df_g = pd.read_sql("SELECT datum_vystaveni, castka_celkem FROM faktury WHERE user_id=%s", conn_graphs, params=(uid,))
                if not df_g.empty:
                    df_g['datum'] = pd.to_datetime(df_g['datum_vystaveni'])
                    monthly = df_g.groupby(df_g['datum'].dt.to_period('M'))['castka_celkem'].sum()
                    monthly.index = monthly.index.astype(str)
                    st.bar_chart(monthly, color="#fbbf24")
                else: st.info("Zatím žádná data.")
            with gc2:
                st.subheader("TOP 5 Klientů")
                df_top = pd.read_sql("SELECT k.jmeno, SUM(f.castka_celkem) as celkem FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=%s GROUP BY k.jmeno ORDER BY celkem DESC LIMIT 5", conn_graphs, params=(uid,))
                if not df_top.empty: st.dataframe(df_top.set_index('jmeno').style.format("{:,.0f} Kč"), use_container_width=True)
                else: st.info("Žádní klienti.")
            st.subheader("Příjmy dle kategorií")
            df_c = pd.read_sql("SELECT k.nazev, SUM(f.castka_celkem) as celkem FROM faktury f JOIN kategorie k ON f.kategorie_id=k.id WHERE f.user_id=%s GROUP BY k.nazev", conn_graphs, params=(uid,))
            if not df_c.empty: st.bar_chart(df_c.set_index('nazev'))
        finally: p_graphs.putconn(conn_graphs)

    # ==================== DANĚ ====================
    elif "Daně" in menu:
        st.markdown('<div class="section-header"><div class="section-icon">🏛️</div><div class="section-title">Daňová kalkulačka</div></div>', unsafe_allow_html=True)
        years = [r['substring'] for r in run_query("SELECT DISTINCT SUBSTRING(datum_vystaveni, 1, 4) as substring FROM faktury WHERE user_id=?", (uid,))]
        current_year = str(date.today().year)
        if current_year not in years: years.append(current_year)
        c_year, c_pausal = st.columns(2)
        sel_tax_year = c_year.selectbox("Vyberte rok", sorted(list(set(years)), reverse=True))
        pausal_opt = c_pausal.selectbox("Typ činnosti", ["80% - Řemeslné živnosti, zemědělství", "60% - Ostatní živnosti (nejčastější)", "40% - Svobodná povolání, autorská práva", "30% - Pronájem majetku"], index=1)
        pausal_pct = int(pausal_opt.split("%")[0]) / 100
        income = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND SUBSTRING(datum_vystaveni, 1, 4)=?", (uid, sel_tax_year), True)['sum'] or 0
        real_expenses = run_query("SELECT SUM(castka) FROM vydaje WHERE user_id=? AND SUBSTRING(datum, 1, 4)=?", (uid, sel_tax_year), True)['sum'] or 0
        flat_expenses = income * pausal_pct
        tax_base_real = max(0, income - real_expenses); tax_base_flat = max(0, income - flat_expenses)
        tax_real = tax_base_real * 0.15; tax_flat = tax_base_flat * 0.15
        diff = tax_flat - tax_real
        st.markdown(f"<div class='info-callout'>Příjmy za rok {sel_tax_year}: <span>{income:,.0f} Kč</span></div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""
            <div class="tax-card">
                <div class="tax-card-title">A) Skutečné výdaje</div>
                <div style="font-size:0.8rem;color:#64748b;margin-bottom:8px;">Výdaje: {real_expenses:,.0f} Kč &nbsp;·&nbsp; Základ: {tax_base_real:,.0f} Kč</div>
                <div class="tax-amount">{tax_real:,.0f} Kč</div>
                <div style="font-size:0.75rem;color:#475569;">Daň 15 %</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="tax-card">
                <div class="tax-card-title">B) Paušál {int(pausal_pct*100)}%</div>
                <div style="font-size:0.8rem;color:#64748b;margin-bottom:8px;">Výdaje: {flat_expenses:,.0f} Kč &nbsp;·&nbsp; Základ: {tax_base_flat:,.0f} Kč</div>
                <div class="tax-amount">{tax_flat:,.0f} Kč</div>
                <div style="font-size:0.75rem;color:#475569;">Daň 15 %</div>
            </div>
            """, unsafe_allow_html=True)
        st.divider()
        if tax_real < tax_flat: st.success(f"🏆 Výhodnější jsou SKUTEČNÉ výdaje! Ušetříte {diff:,.0f} Kč.")
        elif tax_flat < tax_real: st.success(f"🏆 Výhodnější je PAUŠÁL! Ušetříte {abs(diff):,.0f} Kč.")
        else: st.info("Obě varianty vychází stejně.")

    # ==================== VÝDAJE ====================
    elif "Výdaje" in menu:
        st.markdown('<div class="section-header"><div class="section-icon">💸</div><div class="section-title">Evidence výdajů</div></div>', unsafe_allow_html=True)
        with st.form("exp_form"):
            c1, c2 = st.columns(2)
            ex_date = c1.date_input("Datum", date.today()); ex_desc = c2.text_input("Popis (např. Nájem)")
            c3, c4 = st.columns(2)
            ex_amt = c3.number_input("Částka", min_value=0.0, step=100.0); ex_cat = c4.selectbox("Kategorie", ["Provoz", "Materiál", "Služby", "Ostatní"])
            if st.form_submit_button("+ Přidat výdaj"):
                run_command("INSERT INTO vydaje (user_id, datum, popis, castka, kategorie) VALUES (?,?,?,?,?)", (uid, ex_date, ex_desc, ex_amt, ex_cat)); st.success("Uloženo"); st.rerun()

        p_vydaje = get_pool(); conn_vydaje = p_vydaje.getconn()
        try: vydaje = pd.read_sql("SELECT * FROM vydaje WHERE user_id=%s ORDER BY datum DESC", conn_vydaje, params=(uid,))
        finally: p_vydaje.putconn(conn_vydaje)

        if not vydaje.empty:
            st.dataframe(vydaje[['id', 'datum', 'popis', 'kategorie', 'castka']], hide_index=True, use_container_width=True)
            celkem_vydaje = vydaje['castka'].sum(); celkem_prijmy = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?", (uid,), True)['sum'] or 0
            c1, c2, c3 = st.columns(3)
            c1.metric("Příjmy", f"{celkem_prijmy:,.0f} Kč"); c2.metric("Výdaje", f"{celkem_vydaje:,.0f} Kč", delta=-celkem_vydaje); c3.metric("Hrubý zisk", f"{celkem_prijmy - celkem_vydaje:,.0f} Kč")
            vydaj_list = vydaje.apply(lambda x: f"ID {x['id']}: {x['datum']} - {x['popis']} ({x['castka']} Kč)", axis=1).tolist()
            if vydaj_list:
                sel_del = st.selectbox("Vyberte výdaj ke smazání", vydaj_list)
                if st.button("🗑 Smazat označený výdaj"):
                    del_id = int(sel_del.split(":")[0].replace("ID ", ""))
                    run_command("DELETE FROM vydaje WHERE id=? AND user_id=?", (del_id, uid)); st.rerun()

    # ==================== KLIENTI ====================
    elif "Klienti" in menu:
        st.markdown('<div class="section-header"><div class="section-icon">👥</div><div class="section-title">Klienti</div></div>', unsafe_allow_html=True)
        rid = st.session_state.form_reset_id
        with st.expander("➕  Přidat klienta"):
            c1, c2 = st.columns([3, 1])
            ico = c1.text_input("IČO pro načtení z ARES", key=f"a_{rid}")
            if c2.button("Načíst ARES", key=f"b_{rid}"):
                d = get_ares_data(ico)
                if d: st.session_state.ares_data = d; st.success("Data načtena z ARES")
                else: st.error("Firma nenalezena")
            ad = st.session_state.ares_data
            with st.form("fc"):
                j = st.text_input("Jméno firmy / klienta", ad.get('jmeno', ''))
                a = st.text_area("Adresa", ad.get('adresa', ''))
                c1, c2 = st.columns(2)
                i = c1.text_input("IČ", ad.get('ico', '')); d_dic = c2.text_input("DIČ", ad.get('dic', ''))
                p = st.text_area("Poznámka")
                if st.form_submit_button("Uložit klienta"):
                    run_command("INSERT INTO klienti (user_id, jmeno, adresa, ico, dic, poznamka) VALUES (?,?,?,?,?,?)", (uid, j, a, i, d_dic, p)); reset_forms(); get_cached_pdf.clear(); get_cached_isdoc.clear(); st.rerun()

        for k in run_query("SELECT * FROM klienti WHERE user_id=?", (uid,)):
            with st.expander(f"◆  {k['jmeno']}"):
                if k['poznamka']: st.info(k['poznamka'])
                k_edit_key = f"edit_k_{k['id']}"
                if k_edit_key not in st.session_state: st.session_state[k_edit_key] = False
                c1, c2 = st.columns(2)
                if c1.button("✏️ Upravit", key=f"bek_{k['id']}"): st.session_state[k_edit_key] = True; st.rerun()
                if c2.button("🗑 Smazat", key=f"bdk_{k['id']}"): run_command("DELETE FROM klienti WHERE id=?", (k['id'],)); get_cached_pdf.clear(); get_cached_isdoc.clear(); st.rerun()
                if st.session_state[k_edit_key]:
                    with st.form(f"fke_{k['id']}"):
                        nj = st.text_input("Jméno", k['jmeno']); na = st.text_area("Adresa", k['adresa'])
                        ni = st.text_input("IČ", k['ico']); nd = st.text_input("DIČ", k['dic']); np = st.text_area("Poznámka", k['poznamka'])
                        if st.form_submit_button("Uložit změny"):
                            run_command("UPDATE klienti SET jmeno=?, adresa=?, ico=?, dic=?, poznamka=? WHERE id=?", (nj, na, ni, nd, np, k['id']))
                            st.session_state[k_edit_key] = False; get_cached_pdf.clear(); get_cached_isdoc.clear(); st.rerun()

    # ==================== KATEGORIE ====================
    elif "Kategorie" in menu:
        st.markdown('<div class="section-header"><div class="section-icon">🏷️</div><div class="section-title">Kategorie</div></div>', unsafe_allow_html=True)
        if not is_pro:
            st.markdown("""
            <div class="pro-upgrade-card">
                <h3>🔒 Funkce PRO verze</h3>
                <p style="color:#94a3b8;">Správa kategorií je dostupná v PRO verzi. Aktivujte licenci v Nastavení.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            with st.expander("➕  Nová kategorie"):
                with st.form("fcat"):
                    c1, c2 = st.columns(2)
                    n = c1.text_input("Název"); p = c2.text_input("Prefix (např. FV)")
                    c3, c4 = st.columns(2)
                    s = c3.number_input("Startovací číslo", 1); c = c4.color_picker("Barva akcentu")
                    l = st.file_uploader("Logo (PNG/JPG)")
                    if st.form_submit_button("Uložit kategorii"):
                        blob = process_logo(l)
                        run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva, logo_blob) VALUES (?,?,?,?,?,?)", (uid, n, p, s, c, blob)); get_cached_pdf.clear(); st.rerun()

        for k in run_query("SELECT * FROM kategorie WHERE user_id=?", (uid,)):
            with st.expander(f"◆  {k['nazev']}  ·  {k['prefix']}"):
                if k['logo_blob']: st.image(bytes(k['logo_blob']), width=80)
                cat_edit_key = f"edit_cat_{k['id']}"
                if cat_edit_key not in st.session_state: st.session_state[cat_edit_key] = False
                c1, c2 = st.columns(2)
                if is_pro:
                    if c1.button("✏️ Upravit", key=f"bec_{k['id']}"): st.session_state[cat_edit_key] = True; st.rerun()
                if c2.button("🗑 Smazat", key=f"bdc_{k['id']}"): run_command("DELETE FROM kategorie WHERE id=?", (k['id'],)); get_cached_pdf.clear(); st.rerun()
                if st.session_state[cat_edit_key]:
                    with st.form(f"feck_{k['id']}"):
                        c1, c2 = st.columns(2)
                        nn = c1.text_input("Název", k['nazev']); np = c2.text_input("Prefix", k['prefix'])
                        c3, c4 = st.columns(2)
                        ns = c3.number_input("Číslo", value=k['aktualni_cislo']); nc = c4.color_picker("Barva", k['barva'])
                        nl = st.file_uploader("Nové logo", key=f"ul_{k['id']}")
                        if st.form_submit_button("Uložit změny"):
                            if nl:
                                blob = process_logo(nl)
                                run_command("UPDATE kategorie SET nazev=?, prefix=?, aktualni_cislo=?, barva=?, logo_blob=? WHERE id=?", (nn, np, ns, nc, blob, k['id']))
                            else:
                                run_command("UPDATE kategorie SET nazev=?, prefix=?, aktualni_cislo=?, barva=? WHERE id=?", (nn, np, ns, nc, k['id']))
                            st.session_state[cat_edit_key] = False; get_cached_pdf.clear(); st.rerun()

    # ==================== NASTAVENÍ ====================
    elif "Nastavení" in menu:
        st.markdown('<div class="section-header"><div class="section-icon">⚙️</div><div class="section-title">Nastavení</div></div>', unsafe_allow_html=True)
        res = run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1", (uid,), single=True); c = dict(res) if res else {}

        with st.expander("🔑  Licence & Přístup", expanded=True):
            valid, exp = check_license_validity(uid)
            if not valid:
                st.markdown("""
                <div class="pro-upgrade-card">
                    <h3>🚀 Aktivujte PRO verzi</h3>
                    <p style="color:#94a3b8;margin-bottom:12px;">Odemkněte plný potenciál fakturace.</p>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:16px;">
                        <div style="font-size:0.82rem;color:#64748b;">✦ Neomezené faktury</div>
                        <div style="font-size:0.82rem;color:#64748b;">✦ Export ISDOC</div>
                        <div style="font-size:0.82rem;color:#64748b;">✦ Vlastní logo & barvy</div>
                        <div style="font-size:0.82rem;color:#64748b;">✦ Cloud záloha</div>
                    </div>
                    <p style="color:#fbbf24;font-weight:600;font-size:0.9rem;">990 Kč / rok &nbsp;·&nbsp; jsem@michalkochtik.cz</p>
                </div>
                """, unsafe_allow_html=True)
                k = st.text_input("Licenční klíč")
                if st.button("Aktivovat PRO →"):
                    kdb = run_query("SELECT * FROM licencni_klice WHERE kod=? AND pouzito_uzivatelem_id IS NULL", (k,), True)
                    if kdb:
                        ne = date.today() + timedelta(days=kdb['dny_platnosti'])
                        run_command("UPDATE users SET license_key=?, license_valid_until=? WHERE id=?", (k, ne, uid)); run_command("UPDATE licencni_klice SET pouzito_uzivatelem_id=? WHERE id=?", (uid, kdb['id'])); st.session_state.is_pro = True; st.balloons(); st.rerun()
                    else: st.error("Neplatný nebo již použitý klíč")
            else:
                st.success(f"✅ PRO licence aktivní do: **{format_date(exp)}**")
                if st.button("Deaktivovat licenci"): run_command("UPDATE users SET license_key=NULL, license_valid_until=NULL WHERE id=?", (uid,)); st.session_state.is_pro = False; st.rerun()

            st.divider()
            st.markdown("**Změna hesla**")
            p1 = st.text_input("Stávající heslo", type="password"); p2 = st.text_input("Nové heslo", type="password")
            if st.button("Změnit heslo"):
                u_data = run_query("SELECT * FROM users WHERE id=?", (uid,), True)
                if u_data['password_hash'] == hash_password(p1): run_command("UPDATE users SET password_hash=? WHERE id=?", (hash_password(p2), uid)); st.success("Heslo změněno")
                else: st.error("Stávající heslo je nesprávné")

        with st.expander("🏢  Moje Firma"):
            with st.form("setf"):
                c1, c2 = st.columns(2)
                n = c1.text_input("Název firmy / jméno", c.get('nazev', full_name_display))
                a = c2.text_area("Adresa", c.get('adresa', ''))
                c3, c4 = st.columns(2)
                i = c3.text_input("IČO", c.get('ico', '')); d = c4.text_input("DIČ", c.get('dic', ''))
                c5, c6 = st.columns(2)
                b = c5.text_input("Banka", c.get('banka', '')); u = c6.text_input("Číslo účtu", c.get('ucet', ''))
                ib = st.text_input("IBAN (pro QR platbu)", c.get('iban', ''))
                if st.form_submit_button("Uložit nastavení"):
                    ib_cl = ib.replace(" ", "").upper() if ib else ""
                    if c.get('id'): run_command("UPDATE nastaveni SET nazev=?, adresa=?, ico=?, dic=?, banka=?, ucet=?, iban=? WHERE id=?", (n, a, i, d, b, u, ib_cl, c['id']))
                    else: run_command("INSERT INTO nastaveni (user_id, nazev, adresa, ico, dic, banka, ucet, iban) VALUES (?,?,?,?,?,?,?,?)", (uid, n, a, i, d, b, u, ib_cl))
                    get_cached_pdf.clear(); get_cached_isdoc.clear(); st.rerun()

        with st.expander(f"🔔  Upozornění {'(PRO)' if not is_pro else ''}"):
            if not is_pro:
                st.markdown('<div class="pro-upgrade-card"><p style="color:#94a3b8;">Automatická upozornění jsou dostupná v PRO verzi.</p></div>', unsafe_allow_html=True)
            else:
                act = st.toggle("Aktivovat odesílání upozornění", value=bool(c.get('notify_active', 0)))
                col_a, col_b = st.columns(2)
                n_days = col_a.number_input("Dní předem", value=c.get('notify_days', 3), min_value=1); n_email = col_b.text_input("Email pro notifikace", value=c.get('notify_email', ''))
                st.markdown("**SMTP Server**")
                preset = st.selectbox("Rychlé nastavení", ["-- Vyberte --", "Seznam.cz", "Gmail", "Vlastní"])
                d_srv = c.get('smtp_server', 'smtp.seznam.cz'); d_prt = c.get('smtp_port', 465)
                if preset == "Seznam.cz": d_srv = "smtp.seznam.cz"; d_prt = 465
                elif preset == "Gmail": d_srv = "smtp.gmail.com"; d_prt = 465
                s_server = st.text_input("Server", value=d_srv)
                c3, c4 = st.columns(2); s_port = c3.number_input("Port", value=d_prt); s_user = c4.text_input("Login", value=c.get('smtp_email', ''))
                s_pass = st.text_input("Heslo SMTP", value=c.get('smtp_password', ''), type="password")
                c5, c6 = st.columns(2)
                if c5.button("💾 Uložit"): run_command("UPDATE nastaveni SET notify_active=?, notify_days=?, notify_email=?, smtp_server=?, smtp_port=?, smtp_email=?, smtp_password=? WHERE id=?", (int(act), n_days, n_email, s_server, s_port, s_user, s_pass, c.get('id'))); st.success("Uloženo")
                if c6.button("📨 Test"): 
                    if send_email_custom(n_email, "Test MojeFaktury", "Testovací zpráva funguje."): st.success("Email odeslán")
                    else: st.error("Chyba odeslání")

        if is_pro:
            with st.expander("📦  Export ISDOC"):
                c1, c2 = st.columns(2)
                d_start = c1.date_input("Od", date.today().replace(day=1)); d_end = c2.date_input("Do", date.today())
                if st.button("Stáhnout ZIP"):
                    invs = run_query("SELECT id, cislo_full FROM faktury WHERE datum_vystaveni BETWEEN %s AND %s AND user_id=%s", (str(d_start), str(d_end), uid))
                    if invs:
                        buf = io.BytesIO()
                        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                            for i in invs:
                                isd = generate_isdoc(i['id'], uid)
                                if isd: zf.writestr(f"{i['cislo_full']}.isdoc", isd)
                        st.download_button("↓ Stáhnout export.zip", buf.getvalue(), "export.zip", "application/zip")
                    else: st.warning("V zadaném období nejsou žádné faktury")

            with st.expander("💾  Zálohování dat"):
                c1, c2 = st.columns(2)
                c1.download_button("↓ Export JSON", get_export_data(uid), "zaloha.json", "application/json")
                if c2.button("Odeslat na Email"):
                    if send_email_custom(c.get('notify_email'), "Záloha MojeFaktury", "JSON v příloze", get_export_data(uid), "zaloha.json"): st.success("Odesláno")
                    else: st.error("Chyba odeslání")
                st.divider()
                upl = st.file_uploader("Import ze zálohy (JSON)", type="json")
                if upl and st.button("Obnovit data z importu"):
                    try:
                        d = json.load(upl); client_map = {}; cat_map = {}
                        for r in d.get('nastaveni', []):
                            exist = run_query("SELECT id FROM nastaveni WHERE user_id=?", (uid,), True)
                            if exist: run_command("UPDATE nastaveni SET nazev=?, adresa=?, ico=?, dic=?, ucet=?, banka=?, email=?, telefon=?, iban=? WHERE id=?", (r.get('nazev'), r.get('adresa'), r.get('ico'), r.get('dic'), r.get('ucet'), r.get('banka'), r.get('email'), r.get('telefon'), r.get('iban'), exist['id']))
                            else: run_command("INSERT INTO nastaveni (user_id, nazev, adresa, ico, dic, banka, ucet, iban) VALUES (?,?,?,?,?,?,?,?)", (uid, r.get('nazev'), r.get('adresa'), r.get('ico'), r.get('dic'), r.get('ucet'), r.get('banka'), r.get('email'), r.get('telefon'), r.get('iban')))
                        for r in d.get('klienti', []):
                            exist = run_query("SELECT id FROM klienti WHERE jmeno=? AND user_id=?", (r.get('jmeno'), uid), True)
                            if exist: client_map[r['id']] = exist['id']
                            else:
                                nid = run_command("INSERT INTO klienti (user_id, jmeno, adresa, ico, dic, email, poznamka) VALUES (?,?,?,?,?,?,?)", (uid, r.get('jmeno'), r.get('adresa'), r.get('ico'), r.get('dic'), r.get('email'), r.get('poznamka')))
                                if r.get('id'): client_map[r['id']] = nid
                        for r in d.get('kategorie', []):
                            exist = run_query("SELECT id FROM kategorie WHERE nazev=? AND user_id=?", (r.get('nazev'), uid), True)
                            if exist: cat_map[r['id']] = exist['id']
                            else:
                                blob = base64.b64decode(r.get('logo_blob')) if r.get('logo_blob') else None
                                nid = run_command("INSERT INTO kategorie (user_id, nazev, barva, prefix, aktualni_cislo, logo_blob) VALUES (?,?,?,?,?,?)", (uid, r.get('nazev'), r.get('barva'), r.get('prefix'), r.get('aktualni_cislo'), blob))
                                if r.get('id'): cat_map[r['id']] = nid
                        for r in d.get('faktury', []):
                            cid = client_map.get(r.get('klient_id')); kid = cat_map.get(r.get('kategorie_id'))
                            if cid and kid:
                                exist_f = run_query("SELECT id FROM faktury WHERE cislo_full=? AND user_id=?", (r.get('cislo_full'), uid), True)
                                if not exist_f:
                                    new_fid = run_command("INSERT INTO faktury (user_id, cislo, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_duzp, datum_splatnosti, castka_celkem, zpusob_uhrady, variabilni_symbol, cislo_objednavky, uvodni_text, uhrazeno, muj_popis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (uid, r.get('cislo'), r.get('cislo_full'), cid, kid, r.get('datum_vystaveni'), r.get('datum_duzp'), r.get('datum_splatnosti'), r.get('castka_celkem'), r.get('zpusob_uhrady'), r.get('variabilni_symbol'), r.get('cislo_objednavky'), r.get('uvodni_text'), r.get('uhrazeno'), r.get('muj_popis')))
                                    for item in d.get('faktura_polozky', []):
                                        if item.get('faktura_id') == r.get('id'): run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (new_fid, item.get('nazev'), item.get('cena')))
                        get_cached_pdf.clear(); get_cached_isdoc.clear(); st.success("Import dokončen!"); st.rerun()
                    except Exception as ex: st.error(f"Chyba importu: {ex}")
        else:
            with st.expander("💾  Zálohování dat"):
                st.markdown('<div class="pro-upgrade-card"><p style="color:#94a3b8;">Cloud záloha a export jsou dostupné v PRO verzi.</p></div>', unsafe_allow_html=True)
