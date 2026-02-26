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
    st.error("⛔ CHYBA: Není nastaveno ADMIN_INIT_PASS nebo DATABASE_URL v secrets!")
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

# ─────────────────────────────────────────────
# 1. DESIGN  –  opravené CSS (bez hrubého div-overridu)
# ─────────────────────────────────────────────
st.set_page_config(page_title="MojeFaktury", page_icon="💎", layout="centered")

st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap" rel="stylesheet">

<style>
/* ── BASE ── */
*, *::before, *::after { box-sizing: border-box; }

.stApp {
    background: #07090f !important;
    font-family: 'DM Sans', system-ui, sans-serif !important;
}

/* subtle radial glow – pointer-events off so it never blocks clicks */
.stApp::before {
    content: '';
    position: fixed; inset: 0;
    background:
        radial-gradient(ellipse 70% 45% at 15% 5%,  rgba(251,191,36,.055) 0%, transparent 65%),
        radial-gradient(ellipse 55% 40% at 85% 90%,  rgba(99,102,241,.04)  0%, transparent 55%);
    pointer-events: none;
    z-index: 0;
}

/* ── TYPOGRAPHY – targeted, NOT "div" ── */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Syne', sans-serif !important;
    color: #f1f5f9 !important;
    letter-spacing: -.025em;
    line-height: 1.2;
}
h1 { font-size: 2rem   !important; font-weight: 800 !important; }
h2 { font-size: 1.45rem !important; font-weight: 700 !important; }
h3 { font-size: 1.15rem !important; font-weight: 600 !important; }

/* Streamlit markdown text */
.stMarkdown p, .stMarkdown li, .stMarkdown span {
    color: #94a3b8 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: .9rem;
    line-height: 1.6;
}
.stMarkdown strong, .stMarkdown b { color: #e2e8f0 !important; }
.stMarkdown a  { color: #fbbf24 !important; text-decoration: none; }
.stMarkdown a:hover { text-decoration: underline; }

/* widget labels */
label { color: #94a3b8 !important; font-size: .82rem !important; font-weight: 500 !important; }

/* ── INPUTS ── */
.stTextInput  input,
.stNumberInput input,
.stTextArea   textarea,
.stDateInput  input {
    background  : rgba(255,255,255,.04) !important;
    border      : 1px solid rgba(255,255,255,.1) !important;
    border-radius: 10px !important;
    color       : #f1f5f9 !important;
    font-family : 'DM Sans', sans-serif !important;
    font-size   : .88rem !important;
    padding     : 11px 15px !important;
    transition  : border .2s, box-shadow .2s !important;
}
.stTextInput  input:focus,
.stNumberInput input:focus,
.stTextArea   textarea:focus {
    border-color: rgba(251,191,36,.5) !important;
    box-shadow  : 0 0 0 3px rgba(251,191,36,.1) !important;
    background  : rgba(255,255,255,.06) !important;
}

/* ── SELECT ── */
.stSelectbox div[data-baseweb="select"] > div {
    background   : rgba(255,255,255,.04) !important;
    border       : 1px solid rgba(255,255,255,.1) !important;
    border-radius: 10px !important;
}
/* text inside select box */
.stSelectbox div[data-baseweb="select"] span { color: #f1f5f9 !important; }
.stSelectbox svg { fill: #64748b !important; }

ul[data-baseweb="menu"] {
    background   : #111827 !important;
    border       : 1px solid rgba(255,255,255,.1) !important;
    border-radius: 12px !important;
    padding      : 5px !important;
    box-shadow   : 0 20px 60px rgba(0,0,0,.55) !important;
}
li[data-baseweb="option"] {
    border-radius: 8px !important;
    padding      : 9px 13px !important;
    transition   : background .15s !important;
}
li[data-baseweb="option"]:hover                       { background: rgba(251,191,36,.12) !important; }
li[data-baseweb="option"][aria-selected="true"]       { background: rgba(251,191,36,.16) !important; }
li[data-baseweb="option"] div                         { color: #cbd5e1 !important; }
li[data-baseweb="option"]:hover div,
li[data-baseweb="option"][aria-selected="true"] div   { color: #fbbf24 !important; font-weight: 600 !important; }

::placeholder { color: #334155 !important; }

/* ── BUTTONS ── */
.stButton > button {
    background   : rgba(255,255,255,.05) !important;
    color        : #cbd5e1 !important;
    border       : 1px solid rgba(255,255,255,.11) !important;
    border-radius: 10px !important;
    height       : 44px !important;
    font-family  : 'DM Sans', sans-serif !important;
    font-size    : .85rem !important;
    font-weight  : 500 !important;
    width        : 100% !important;
    transition   : all .2s ease !important;
    white-space  : nowrap !important;
}
.stButton > button:hover {
    background   : rgba(251,191,36,.09) !important;
    border-color : rgba(251,191,36,.38) !important;
    color        : #fbbf24 !important;
    transform    : translateY(-1px) !important;
    box-shadow   : 0 4px 18px rgba(251,191,36,.14) !important;
}
/* primary form button */
div[data-testid="stForm"] button[kind="primary"] {
    background : linear-gradient(135deg, #fbbf24, #d97706) !important;
    color      : #0b0f1a !important;
    border     : none !important;
    font-weight: 700 !important;
    box-shadow : 0 4px 18px rgba(251,191,36,.28) !important;
}
div[data-testid="stForm"] button[kind="primary"]:hover {
    transform : translateY(-2px) !important;
    box-shadow: 0 8px 28px rgba(251,191,36,.38) !important;
}
div[data-testid="stForm"] button[kind="primary"] p { color: #0b0f1a !important; font-weight: 700 !important; }

/* download button */
[data-testid="stDownloadButton"] > button {
    background   : rgba(255,255,255,.05) !important;
    color        : #64748b !important;
    border       : 1px solid rgba(255,255,255,.09) !important;
    border-radius: 10px !important;
    height       : 44px !important;
    font-family  : 'DM Sans', sans-serif !important;
    width        : 100% !important;
    transition   : all .2s !important;
}
[data-testid="stDownloadButton"] > button:hover {
    border-color: rgba(52,211,153,.4) !important;
    color       : #34d399 !important;
    background  : rgba(52,211,153,.07) !important;
}

/* ── SIDEBAR ── */
section[data-testid="stSidebar"] {
    background  : rgba(7,9,15,.97) !important;
    border-right: 1px solid rgba(255,255,255,.055) !important;
}
section[data-testid="stSidebar"] .stRadio label {
    background   : rgba(255,255,255,.025) !important;
    border       : 1px solid rgba(255,255,255,.055) !important;
    border-radius: 10px !important;
    padding      : 11px 15px !important;
    margin-bottom: 4px !important;
    width        : 100% !important;
    cursor       : pointer !important;
    transition   : all .18s !important;
}
section[data-testid="stSidebar"] .stRadio label:hover {
    background  : rgba(251,191,36,.06) !important;
    border-color: rgba(251,191,36,.2) !important;
}
section[data-testid="stSidebar"] .stRadio label[data-checked="true"] {
    background  : linear-gradient(135deg,rgba(251,191,36,.14),rgba(217,119,6,.09)) !important;
    border-color: rgba(251,191,36,.33) !important;
}
section[data-testid="stSidebar"] .stRadio label[data-checked="true"] p { color: #fbbf24 !important; font-weight: 600 !important; }

/* ── EXPANDER ── */
div[data-testid="stExpander"] {
    background   : rgba(255,255,255,.022) !important;
    border       : 1px solid rgba(255,255,255,.075) !important;
    border-radius: 14px !important;
    overflow     : hidden !important;
    transition   : border-color .2s !important;
    margin-bottom: 10px !important;
}
div[data-testid="stExpander"]:hover { border-color: rgba(251,191,36,.18) !important; }

/* ── CALENDAR / DATEPICKER ── */
div[data-baseweb="calendar"] {
    background   : #111827 !important;
    border       : 1px solid rgba(255,255,255,.1) !important;
    border-radius: 12px !important;
}
div[data-baseweb="calendar"] button { color: #f1f5f9 !important; }

/* ── TABS ── */
button[data-baseweb="tab"]                         { background: transparent !important; }
button[data-baseweb="tab"] div p                   { color: #475569 !important; font-family: 'DM Sans', sans-serif !important; }
button[data-baseweb="tab"][aria-selected="true"] div p { color: #fbbf24 !important; font-weight: 600 !important; }

/* ── MISC ── */
hr { border-color: rgba(255,255,255,.055) !important; margin: 1.4rem 0 !important; }

[data-testid="stMetricValue"] { font-family: 'Syne', sans-serif !important; font-weight: 700 !important; color: #f1f5f9 !important; }
[data-testid="stMetricLabel"] { font-family: 'DM Sans', sans-serif !important; color: #475569 !important; font-size: .75rem !important; text-transform: uppercase !important; letter-spacing: .08em !important; }

[data-testid="stDataFrame"]  { border: 1px solid rgba(255,255,255,.07) !important; border-radius: 12px !important; }
[data-testid="stDataEditor"] { border: 1px solid rgba(255,255,255,.07) !important; border-radius: 12px !important; overflow: hidden !important; }
[data-testid="stAlert"]      { border-radius: 12px !important; }

/* scrollbar */
::-webkit-scrollbar               { width: 5px; height: 5px; }
::-webkit-scrollbar-track         { background: rgba(255,255,255,.02); }
::-webkit-scrollbar-thumb         { background: rgba(255,255,255,.09); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover   { background: rgba(251,191,36,.28); }

/* hide branding */
#MainMenu, footer, header { visibility: hidden !important; }

/* ═══════════════════════════════════════════
   CUSTOM COMPONENT STYLES
   ═══════════════════════════════════════════ */

/* ── LANDING ── */
.brand-wrap   { padding: 40px 0 20px; text-align: center; }
.brand-logo   { font-size: 58px; display: block; margin-bottom: 6px; animation: bobble 3.2s ease-in-out infinite; }
@keyframes bobble { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-9px)} }

.brand-title  {
    font-family: 'Syne', sans-serif;
    font-size  : 2.9rem; font-weight: 800;
    background : linear-gradient(120deg, #fbbf24 0%, #fde68a 45%, #f59e0b 100%);
    background-size: 200% auto;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    animation  : shine 3.5s linear infinite;
    letter-spacing: -.03em;
}
@keyframes shine { to { background-position: 200% center; } }

.brand-sub    { color: #475569; font-size: 1rem; margin: 8px 0 28px; line-height: 1.6; }

.feat-grid    { background: rgba(255,255,255,.022); border: 1px solid rgba(255,255,255,.07); border-radius: 16px; padding: 22px 24px; margin-bottom: 24px; }
.feat-row     { display: flex; align-items: center; gap: 10px; padding: 7px 0; border-bottom: 1px solid rgba(255,255,255,.04); font-size: .87rem; color: #64748b; }
.feat-row:last-child { border-bottom: none; }
.feat-row b   { color: #e2e8f0; }

/* ── SIDEBAR USER CARD ── */
.sb-card      { background: rgba(251,191,36,.055); border: 1px solid rgba(251,191,36,.14); border-radius: 13px; padding: 15px; margin-bottom: 14px; }
.sb-name      { font-family: 'Syne', sans-serif; font-size: .98rem; font-weight: 700; color: #f1f5f9; margin-bottom: 3px; }
.sb-meta      { font-size: .76rem; color: #475569; margin-bottom: 9px; }
.badge        { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: .7rem; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; }
.badge-pro    { background: linear-gradient(135deg,#fbbf24,#d97706); color: #0b0f1a; }
.badge-free   { background: rgba(71,85,105,.25); border: 1px solid rgba(71,85,105,.4); color: #64748b; }

/* ── STAT CARDS ── */
.stats-row    { display: grid; grid-template-columns: repeat(3,1fr); gap: 11px; margin: 14px 0 22px; }
.sc           { background: rgba(255,255,255,.028); border: 1px solid rgba(255,255,255,.07); border-radius: 14px; padding: 15px 14px; text-align: center; position: relative; overflow: hidden; transition: transform .2s, border-color .2s; }
.sc:hover     { transform: translateY(-2px); border-color: rgba(255,255,255,.13); }
.sc::before   { content:''; position:absolute; top:0;left:0;right:0; height:2px; }
.sc.g::before { background: linear-gradient(90deg,#34d399,#10b981); }
.sc.a::before { background: linear-gradient(90deg,#fbbf24,#f59e0b); }
.sc.r::before { background: linear-gradient(90deg,#f87171,#ef4444); }
.sc-lbl       { font-size: .65rem; color: #475569; text-transform: uppercase; letter-spacing: .09em; font-weight: 600; margin-bottom: 5px; }
.sc-val       { font-family: 'Syne', sans-serif; font-size: 1.3rem; font-weight: 800; line-height: 1; }
.sc-val.g     { color: #34d399; }
.sc-val.a     { color: #fbbf24; }
.sc-val.r     { color: #f87171; }
.sc-sub       { font-size: .68rem; color: #1e293b; margin-top: 3px; }

/* ── SECTION HEADER ── */
.sec-hdr      { display: flex; align-items: center; gap: 11px; margin-bottom: 20px; padding-bottom: 14px; border-bottom: 1px solid rgba(255,255,255,.055); }
.sec-ico      { width: 34px; height: 34px; background: rgba(251,191,36,.09); border-radius: 9px; display: flex; align-items: center; justify-content: center; font-size: .95rem; flex-shrink: 0; }
.sec-title    { font-family: 'Syne', sans-serif; font-size: 1.25rem; font-weight: 700; color: #f1f5f9; }

/* ── INFO CALLOUT ── */
.callout      { background: rgba(251,191,36,.055); border: 1px solid rgba(251,191,36,.18); border-radius: 9px; padding: 11px 15px; margin: 7px 0; font-size: .84rem; color: #94a3b8; }
.callout span { color: #fbbf24; font-weight: 600; }

/* ── TOTAL LINE ── */
.total-ln     { display: flex; justify-content: space-between; align-items: center; background: rgba(251,191,36,.055); border: 1px solid rgba(251,191,36,.16); border-radius: 10px; padding: 13px 17px; margin: 11px 0; }
.total-lbl    { font-size: .84rem; color: #64748b; }
.total-amt    { font-family: 'Syne', sans-serif; font-size: 1.18rem; font-weight: 800; color: #fbbf24; }

/* ── INVOICE STATUS BADGES ── */
.tag-paid     { display:inline-block; padding:2px 9px; background:rgba(52,211,153,.1); border:1px solid rgba(52,211,153,.22); border-radius:20px; font-size:.69rem; font-weight:600; color:#34d399; letter-spacing:.04em; }
.tag-due      { display:inline-block; padding:2px 9px; background:rgba(251,191,36,.1); border:1px solid rgba(251,191,36,.22); border-radius:20px; font-size:.69rem; font-weight:600; color:#fbbf24; letter-spacing:.04em; }
.tag-overdue  { display:inline-block; padding:2px 9px; background:rgba(248,113,113,.1); border:1px solid rgba(248,113,113,.25); border-radius:20px; font-size:.69rem; font-weight:600; color:#f87171; letter-spacing:.04em; }

/* ── OVERDUE ALERT PANEL ── */
.overdue-panel {
    background   : rgba(248,113,113,.07);
    border       : 1px solid rgba(248,113,113,.25);
    border-radius: 14px;
    padding      : 18px 20px;
    margin-bottom: 18px;
}
.overdue-header {
    display      : flex;
    align-items  : center;
    gap          : 10px;
    margin-bottom: 14px;
}
.overdue-title  { font-family: 'Syne', sans-serif; font-size: 1rem; font-weight: 700; color: #f87171; }
.overdue-count  { background: rgba(248,113,113,.2); border: 1px solid rgba(248,113,113,.3); border-radius: 20px; padding: 2px 9px; font-size: .72rem; font-weight: 700; color: #f87171; }
.overdue-row    { display: flex; justify-content: space-between; align-items: center; padding: 9px 0; border-bottom: 1px solid rgba(248,113,113,.1); }
.overdue-row:last-child { border-bottom: none; }
.overdue-name   { font-size: .85rem; color: #e2e8f0; font-weight: 500; }
.overdue-detail { font-size: .75rem; color: #64748b; margin-top: 2px; }
.overdue-amount { font-family: 'Syne', sans-serif; font-size: .95rem; font-weight: 700; color: #f87171; text-align: right; }
.overdue-days   { font-size: .72rem; color: #f87171; opacity: .8; text-align: right; }

/* ── MINI STATS ── */
.mini-row     { display: grid; grid-template-columns: repeat(3,1fr); gap: 9px; margin: 11px 0; }
.mini-sc      { background: rgba(255,255,255,.022); border: 1px solid rgba(255,255,255,.065); border-radius: 10px; padding: 11px; text-align: center; }
.mini-lbl     { font-size: .63rem; color: #334155; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 4px; }
.mini-val     { font-family: 'Syne', sans-serif; font-size: 1rem; font-weight: 700; color: #f1f5f9; }
.mini-val.g   { color: #34d399; }
.mini-val.r   { color: #f87171; }

/* ── TAX CARDS ── */
.tax-c        { background: rgba(255,255,255,.025); border: 1px solid rgba(255,255,255,.075); border-radius: 15px; padding: 22px; text-align: center; transition: all .22s; }
.tax-c:hover  { border-color: rgba(251,191,36,.22); }
.tax-title    { font-size: .72rem; text-transform: uppercase; letter-spacing: .1em; color: #475569; margin-bottom: 10px; }
.tax-meta     { font-size: .78rem; color: #334155; margin-bottom: 8px; }
.tax-amt      { font-family: 'Syne', sans-serif; font-size: 1.9rem; font-weight: 800; color: #fbbf24; margin: 6px 0; }
.tax-sub      { font-size: .72rem; color: #334155; }

/* ── PRO UPGRADE CARD ── */
.pro-card     { background: linear-gradient(135deg,rgba(251,191,36,.07),rgba(217,119,6,.04)); border: 1px solid rgba(251,191,36,.18); border-radius: 15px; padding: 22px; margin-bottom: 18px; }
.pro-card h3  { font-family: 'Syne', sans-serif !important; color: #fbbf24 !important; margin-bottom: 10px; }
.pro-feat-row { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 14px; }
.pro-feat     { font-size: .8rem; color: #64748b; }
.pro-price    { color: #fbbf24; font-weight: 600; font-size: .88rem; }

/* ── ADMIN CARDS ── */
.adm-grid     { display: grid; grid-template-columns: repeat(4,1fr); gap: 10px; margin-bottom: 22px; }
.adm-card     { background: rgba(255,255,255,.022); border: 1px solid rgba(255,255,255,.07); border-radius: 13px; padding: 17px 14px; text-align: center; }
.adm-val      { font-family: 'Syne', sans-serif; font-size: 1.45rem; font-weight: 800; color: #f1f5f9; margin-bottom: 4px; }
.adm-lbl      { font-size: .69rem; color: #475569; text-transform: uppercase; letter-spacing: .08em; }

/* ── SEARCH BAR ── */
.search-wrap  { position: relative; margin-bottom: 14px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 2. DB – Connection Pool
# ─────────────────────────────────────────────
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
    except Exception as e:
        print(f"Query Error: {e}"); return None
    finally:
        p.putconn(conn)

def run_command(sql, params=()):
    sql = sql.replace("?", "%s")
    is_insert = sql.strip().upper().startswith("INSERT")
    if is_insert and "RETURNING id" not in sql and "ON CONFLICT" not in sql:
        sql += " RETURNING id"
    p = get_pool(); conn = p.getconn()
    try:
        with conn.cursor() as c:
            c.execute(sql, params); conn.commit()
            if is_insert and "RETURNING id" in sql:
                try:
                    return c.fetchone()[0]
                except:
                    return None
        return None
    except Exception as e:
        print(f"Command Error: {e}"); return None
    finally:
        p.putconn(conn)

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
            with conn.cursor() as c:
                c.execute("ALTER TABLE users ADD COLUMN force_password_change INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            conn.rollback()
        with conn.cursor() as c:
            try:
                c.execute("INSERT INTO email_templates (name, subject, body) VALUES ('welcome','Vítejte ve vašem fakturačním systému','Dobrý den {name},\n\nVáš účet byl úspěšně vytvořen.\n\nS pozdravem,\nTým MojeFakturace') ON CONFLICT (name) DO NOTHING")
            except:
                pass
            try:
                adm_hash = hashlib.sha256(admin_pass_init.encode()).hexdigest()
                c.execute("INSERT INTO users (username,password_hash,role,full_name,email,phone,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (username) DO NOTHING",
                          ("admin", adm_hash, "admin", "Super Admin", "admin@system.cz", "000000000", datetime.now().isoformat()))
                c.execute("UPDATE users SET password_hash=%s WHERE username='admin'", (adm_hash,))
            except Exception as e:
                print(f"Chyba admin sync: {e}")
        conn.commit()
    finally:
        p.putconn(conn)

if 'db_inited' not in st.session_state:
    init_db()
    st.session_state.db_inited = True

# ─────────────────────────────────────────────
# 3. POMOCNÉ FUNKCE
# ─────────────────────────────────────────────
def hash_password(pw): return hashlib.sha256(pw.encode()).hexdigest()
def remove_accents(s): return "".join(c for c in unicodedata.normalize('NFKD', str(s)) if not unicodedata.combining(c)) if s else ""
def format_date(d):
    try:
        return datetime.strptime(str(d)[:10], '%Y-%m-%d').strftime('%d.%m.%Y') if isinstance(d, str) else d.strftime('%d.%m.%Y')
    except:
        return ""
def gen_password(n=8): return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(n))
def gen_license(): return '-'.join(''.join(random.choices(string.ascii_uppercase + string.digits, k=4)) for _ in range(4))

def check_license(uid):
    res = run_query("SELECT license_valid_until FROM users WHERE id=?", (uid,), single=True)
    if not res or not res['license_valid_until']: return False, "Žádná"
    try:
        exp = datetime.strptime(str(res['license_valid_until'])[:10], '%Y-%m-%d').date()
        return (True, exp) if exp >= date.today() else (False, exp)
    except:
        return False, "Chyba"

def get_next_num(kat_id, uid):
    res = run_query("SELECT prefix, aktualni_cislo FROM kategorie WHERE id=? AND user_id=?", (kat_id, uid), single=True)
    if res: return res['aktualni_cislo'], f"{res['prefix']}{res['aktualni_cislo']}", res['prefix']
    return 1, "1", ""

@st.cache_data(ttl=86400)
def get_ares(ico):
    if not ico: return None
    ico = "".join(filter(str.isdigit, str(ico))).zfill(8)
    try:
        r = requests.get(f"https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}",
                         headers={"accept": "application/json", "User-Agent": "Mozilla/5.0"},
                         verify=False, timeout=5)
        if r.status_code == 200:
            data = r.json(); s = data.get('sidlo', {})
            ul = s.get('nazevUlice', ''); cd = s.get('cisloDomovni'); co = s.get('cisloOrientacni')
            ob = s.get('nazevObce', ''); psc = s.get('psc', '')
            ct = str(cd) if cd else ""
            if co: ct += f"/{co}"
            parts = []
            if ul: parts.append(f"{ul} {ct}".strip())
            elif ct and ob: parts.append(f"{ob} {ct}")
            if psc and ob: parts.append(f"{psc} {ob}")
            adr = ", ".join(parts) or s.get('textovaAdresa', '')
            dic = data.get('dic', '') or data.get('dicId', '')
            return {"jmeno": data.get('obchodniJmeno', ''), "adresa": adr, "ico": ico, "dic": dic}
    except Exception as e:
        print(f"ARES Error: {e}")
    return None

def process_logo(f):
    if not f: return None
    try:
        img = Image.open(f)
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        b = io.BytesIO(); img.save(b, format='PNG'); return b.getvalue()
    except:
        return None

def send_email(to, sub, body, attachment=None, filename="zaloha.json"):
    if not SYSTEM_EMAIL["enabled"] or not SYSTEM_EMAIL["password"]: return False
    try:
        msg = MIMEMultipart()
        msg['From'] = formataddr((SYSTEM_EMAIL["display_name"], SYSTEM_EMAIL["email"]))
        msg['To'] = to; msg['Subject'] = sub
        msg.attach(MIMEText(body, 'plain'))
        if attachment:
            part = MIMEApplication(attachment, Name=filename)
            part['Content-Disposition'] = f'attachment; filename="{filename}"'
            msg.attach(part)
        s = smtplib.SMTP_SSL(SYSTEM_EMAIL["server"], SYSTEM_EMAIL["port"])
        s.login(SYSTEM_EMAIL["email"], SYSTEM_EMAIL["password"])
        s.sendmail(SYSTEM_EMAIL["email"], to, msg.as_string()); s.quit()
        return True
    except:
        return False

def send_welcome_email(to, name, key=None):
    tpl = run_query("SELECT subject, body FROM email_templates WHERE name='welcome'", single=True)
    d = dict(tpl) if tpl else {}
    sub = d.get('subject', "Vítejte")
    bod = d.get('body', f"Dobrý den {name}").replace("{name}", name)
    if key: bod += f"\n\n🎁 Váš 14denní PRO klíč: {key}\n(Byl automaticky aktivován.)"
    return send_email(to, sub, bod)

def get_export_data(user_id):
    out = {}
    p = get_pool(); conn = p.getconn()
    try:
        for t in ['nastaveni', 'klienti', 'kategorie', 'faktury', 'vydaje']:
            df = pd.read_sql(f"SELECT * FROM {t} WHERE user_id=%s", conn, params=(user_id,))
            if 'logo_blob' in df.columns:
                df['logo_blob'] = df['logo_blob'].apply(lambda x: base64.b64encode(x).decode() if x else None)
            out[t] = df.to_dict(orient='records')
        df_p = pd.read_sql("SELECT fp.* FROM faktura_polozky fp JOIN faktury f ON fp.faktura_id=f.id WHERE f.user_id=%s", conn, params=(user_id,))
        out['faktura_polozky'] = df_p.to_dict(orient='records')
    except Exception as e:
        print(f"Export Error: {e}"); return "{}"
    finally:
        p.putconn(conn)
    return json.dumps(out, default=str)

# ─── PDF / ISDOC ───
def generate_isdoc(fid, uid):
    data = run_query("SELECT f.*,k.jmeno,k.ico,k.adresa,m.nazev as m_nazev,m.ico as m_ico FROM faktury f JOIN klienti k ON f.klient_id=k.id JOIN nastaveni m ON f.user_id=m.user_id WHERE f.id=?", (fid,), True)
    if not data: return None
    d = dict(data)
    root = ET.Element("Invoice", xmlns="http://isdoc.cz/namespace/2013", version="6.0.1")
    ET.SubElement(root, "DocumentType").text = "1"
    ET.SubElement(root, "ID").text = str(d.get('cislo_full', d['id']))
    ET.SubElement(root, "IssueDate").text = str(d['datum_vystaveni'])
    ET.SubElement(root, "TaxPointDate").text = str(d['datum_duzp'])
    ET.SubElement(root, "LocalCurrencyCode").text = "CZK"
    sp = ET.SubElement(root, "AccountingSupplierParty"); p = ET.SubElement(sp, "Party")
    pn = ET.SubElement(p, "PartyName"); ET.SubElement(pn, "Name").text = str(d.get('m_nazev', ''))
    pi = ET.SubElement(p, "PartyIdentification"); ET.SubElement(pi, "ID").text = str(d.get('m_ico', ''))
    cp = ET.SubElement(root, "AccountingCustomerParty"); pc = ET.SubElement(cp, "Party")
    pnc = ET.SubElement(pc, "PartyName"); ET.SubElement(pnc, "Name").text = str(d.get('jmeno', ''))
    pic = ET.SubElement(pc, "PartyIdentification"); ET.SubElement(pic, "ID").text = str(d.get('ico', ''))
    amt = ET.SubElement(root, "LegalMonetaryTotal")
    ET.SubElement(amt, "TaxExclusiveAmount").text = str(d['castka_celkem'])
    ET.SubElement(amt, "TaxInclusiveAmount").text = str(d['castka_celkem'])
    ET.SubElement(amt, "PayableAmount").text = str(d['castka_celkem'])
    return ET.tostring(root, encoding='utf-8')

def generate_pdf(fid, uid, is_pro):
    use_font = os.path.exists(FONT_FILE)
    def tx(t): return remove_accents(str(t)) if t else ""
    def fp(v): return f"{v:,.2f}".replace(",", " ").replace(".", ",")
    class PDF(FPDF):
        def header(self):
            fn = 'ArialCS' if use_font else 'Arial'
            if use_font:
                try: self.add_font('ArialCS', '', FONT_FILE, uni=True); self.add_font('ArialCS', 'B', FONT_FILE, uni=True)
                except: pass
            self.set_font(fn, 'B', 24); self.set_text_color(50, 50, 50)
            self.cell(0, 10, 'FAKTURA', 0, 1, 'R'); self.ln(5)
    try:
        raw = run_query("SELECT f.*,k.jmeno as k_jmeno,k.adresa as k_adresa,k.ico as k_ico,k.dic as k_dic,kat.barva,kat.logo_blob,kat.prefix FROM faktury f JOIN klienti k ON f.klient_id=k.id JOIN kategorie kat ON f.kategorie_id=kat.id WHERE f.id=? AND f.user_id=?", (fid, uid), single=True)
        if not raw: return None
        data = dict(raw)
        pol = [dict(x) for x in run_query("SELECT * FROM faktura_polozky WHERE faktura_id=?", (fid,))]
        moje = dict(run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1", (uid,), single=True) or {})
        pdf = PDF(); pdf.add_page()
        fn = 'ArialCS' if use_font else 'Arial'
        pdf.set_font(fn, '', 10)
        if data.get('logo_blob'):
            try:
                lf = f"l_{fid}.png"; open(lf, "wb").write(data['logo_blob']); pdf.image(lf, 10, 10, 50); os.remove(lf)
            except: pass
        cf = data.get('cislo_full') or f"{data.get('prefix','')}{data.get('cislo','')}"
        r, g, b = 0, 0, 0
        if is_pro and data.get('barva'):
            try: cv = data['barva'].lstrip('#'); r, g, b = tuple(int(cv[i:i+2], 16) for i in (0, 2, 4))
            except: pass
        pdf.set_text_color(100); pdf.set_y(55)
        pdf.cell(95, 5, "DODAVATEL:", 0, 0); pdf.cell(95, 5, "ODBERATEL:", 0, 1)
        pdf.set_text_color(0); y = pdf.get_y()
        pdf.set_font(fn, 'B', 11); pdf.cell(95, 5, tx(moje.get('nazev', '')), 0, 1)
        pdf.set_font(fn, '', 10)
        dod = [tx(moje.get('adresa', ''))] if moje.get('adresa') else []
        if moje.get('ico'): dod.append(tx(f"IC: {moje['ico']}"))
        if moje.get('dic'): dod.append(tx(f"DIC: {moje['dic']}"))
        if moje.get('email'): dod.append(tx(moje['email']))
        pdf.multi_cell(95, 5, "\n".join(dod))
        pdf.set_xy(105, y); pdf.set_font(fn, 'B', 11); pdf.cell(95, 5, tx(data.get('k_jmeno')), 0, 1)
        pdf.set_xy(105, pdf.get_y()); pdf.set_font(fn, '', 10)
        odb = [tx(data.get('k_adresa', ''))] if data.get('k_adresa') else []
        if data.get('k_ico'): odb.append(tx(f"IC: {data['k_ico']}"))
        if data.get('k_dic'): odb.append(tx(f"DIC: {data['k_dic']}"))
        pdf.multi_cell(95, 5, "\n".join(odb))
        pdf.ln(10); pdf.set_fill_color(r, g, b); pdf.rect(10, pdf.get_y(), 190, 2, 'F'); pdf.ln(5)
        pdf.set_font(fn, 'B', 12); pdf.cell(100, 8, tx(f"Faktura c.: {cf}"), 0, 1)
        pdf.set_font(fn, '', 10)
        pdf.cell(50, 6, "Vystaveno:", 0, 0); pdf.cell(50, 6, format_date(data.get('datum_vystaveni')), 0, 1)
        pdf.cell(50, 6, "Splatnost:", 0, 0); pdf.cell(50, 6, format_date(data.get('datum_splatnosti')), 0, 1)
        if moje.get('ucet'): pdf.cell(50, 6, "Ucet:", 0, 0); pdf.cell(50, 6, tx(moje.get('ucet')), 0, 1)
        else: pdf.ln(6)
        pdf.cell(50, 6, "VS:", 0, 0); pdf.cell(50, 6, tx(data.get('variabilni_symbol')), 0, 1)
        if data.get('uvodni_text'): pdf.ln(8); pdf.multi_cell(190, 5, tx(data['uvodni_text']))
        pdf.ln(10); pdf.set_fill_color(240, 240, 240)
        pdf.set_font(fn, 'B', 10)
        pdf.cell(140, 10, tx("POLOZKY"), 0, 0, 'L', True); pdf.cell(50, 10, "CENA", 0, 1, 'R', True)
        pdf.set_font(fn, '', 10); pdf.set_draw_color(200, 200, 200); pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        for pp in pol:
            if not pp.get('nazev'): continue
            pdf.cell(140, 8, tx(pp.get('nazev')), 0, 0, 'L'); pdf.cell(50, 8, f"{fp(pp.get('cena', 0))} Kc", 0, 1, 'R')
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5); pdf.set_font(fn, 'B', 14)
        pdf.cell(190, 10, f"CELKEM: {fp(data.get('castka_celkem', 0))} Kc", 0, 1, 'R')
        if is_pro and moje.get('iban'):
            try:
                ic = str(moje['iban']).replace(" ", "").upper(); vs = str(data.get('variabilni_symbol', ''))
                qr_str = f"SPD*1.0*ACC:{ic}*AM:{data.get('castka_celkem')}*CC:CZK*X-VS:{vs}*MSG:{remove_accents('Faktura '+cf)}"
                q = qrcode.make(qr_str); qf = f"q_{fid}.png"; q.save(qf)
                pdf.image(qf, 10, pdf.get_y()+2, 30); os.remove(qf)
            except: pass
        return pdf.output(dest='S').encode('latin-1')
    except Exception as e:
        return f"CHYBA: {e}"

@st.cache_data(show_spinner=False, max_entries=500)
def cached_pdf(fid, uid, is_pro, rh): return generate_pdf(fid, uid, is_pro)

@st.cache_data(show_spinner=False, max_entries=500)
def cached_isdoc(fid, uid, rh): return generate_isdoc(fid, uid)

# ─────────────────────────────────────────────
# 4. SESSION
# ─────────────────────────────────────────────
for k, v in [('user_id', None), ('role', 'user'), ('is_pro', False),
             ('items_df', pd.DataFrame(columns=["Popis položky", "Cena"])),
             ('form_reset_id', 0), ('ares_data', {})]:
    if k not in st.session_state: st.session_state[k] = v

def reset_forms():
    st.session_state.form_reset_id += 1
    st.session_state.ares_data = {}
    st.session_state.items_df = pd.DataFrame(columns=["Popis položky", "Cena"])

# ─────────────────────────────────────────────
# 5. LOGIN / LANDING
# ─────────────────────────────────────────────
if not st.session_state.user_id:
    _, col, _ = st.columns([1, 10, 1])
    with col:
        st.markdown("""
<div class="brand-wrap">
  <span class="brand-logo">💎</span>
  <div class="brand-title">MojeFaktury</div>
  <p class="brand-sub">Fakturace pro moderní živnostníky.<br>Rychlá, přehledná, vždy po ruce.</p>
</div>
<div class="feat-grid">
  <div class="feat-row">✦ &nbsp;<b>14 dní PRO zdarma</b> — bez kreditky</div>
  <div class="feat-row">✦ &nbsp;<b>Faktura do 30 sekund</b> — přímočarý tok</div>
  <div class="feat-row">✦ &nbsp;<b>ARES integrace</b> — auto-vyplnění firmy</div>
  <div class="feat-row">✦ &nbsp;<b>Přehled po splatnosti</b> — víte, kdo dluží</div>
  <div class="feat-row">✦ &nbsp;<b>Export ISDOC & PDF</b> — pro účetní</div>
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
                        st.session_state.user_id = r['id']; st.session_state.role = r['role']
                        st.session_state.username = r['username']; st.session_state.full_name = r['full_name']
                        st.session_state.user_email = r['email']
                        st.session_state.force_pw_change = dict(r).get('force_password_change', 0)
                        valid, exp = check_license(r['id'])
                        st.session_state.is_pro = valid
                        run_command("UPDATE users SET last_active=? WHERE id=?", (datetime.now().isoformat(), r['id']))
                        st.rerun()
                    else:
                        st.error("Neplatné přihlašovací údaje.")
        with t2:
            with st.form("reg"):
                f = st.text_input("Jméno a Příjmení").strip()
                u = st.text_input("Login (uživatelské jméno)").strip()
                e = st.text_input("Email").strip()
                t_tel = st.text_input("Telefon").strip()
                p = st.text_input("Heslo", type="password").strip()
                if st.form_submit_button("Vytvořit účet →", use_container_width=True):
                    try:
                        uid_new = run_command("INSERT INTO users (username,password_hash,full_name,email,phone,created_at,force_password_change) VALUES (?,?,?,?,?,?,0)",
                                             (u, hash_password(p), f, e, t_tel, datetime.now().isoformat()))
                        trial_key = gen_license()
                        run_command("INSERT INTO licencni_klice (kod,dny_platnosti,vygenerovano,poznamka,pouzito_uzivatelem_id) VALUES (?,?,?,?,?)",
                                   (trial_key, 14, datetime.now().isoformat(), "Auto-Trial 14 dní", uid_new))
                        run_command("UPDATE users SET license_key=?, license_valid_until=? WHERE id=?",
                                   (trial_key, date.today() + timedelta(days=14), uid_new))
                        send_welcome_email(e, f, trial_key)
                        st.success("Hotovo! Účet vytvořen + 14 dní PRO zdarma. Přihlaste se.")
                    except Exception as ex:
                        st.error(f"Chyba: {ex}")
        with t3:
            with st.form("forgot"):
                fe = st.text_input("Váš Email").strip()
                if st.form_submit_button("Odeslat nové heslo →", use_container_width=True):
                    usr = run_query("SELECT * FROM users WHERE email=?", (fe,), single=True)
                    if usr:
                        np = gen_password()
                        run_command("UPDATE users SET password_hash=?, force_password_change=1 WHERE id=?", (hash_password(np), usr['id']))
                        body = f"Dobrý den,\n\nNové heslo: {np}\n\nPo přihlášení budete vyzváni ke změně."
                        if send_email(fe, "Reset hesla – MojeFaktury", body):
                            st.success("Nové heslo odesláno na email.")
                        else:
                            st.error("Chyba odesílání emailu.")
                    else:
                        st.error("Email nenalezen.")
    st.stop()

# ─────────────────────────────────────────────
# 6. APP
# ─────────────────────────────────────────────
uid = st.session_state.user_id
role = st.session_state.role
is_pro = st.session_state.is_pro
display_name = st.session_state.full_name or st.session_state.username
run_command("UPDATE users SET last_active=? WHERE id=?", (datetime.now().isoformat(), uid))

# Force password change
if st.session_state.get('force_pw_change', 0) == 1:
    st.markdown("## ⚠️ Změna hesla vyžadována")
    with st.form("force_chg"):
        np1 = st.text_input("Nové heslo", type="password").strip()
        np2 = st.text_input("Potvrzení", type="password").strip()
        if st.form_submit_button("Změnit a pokračovat →", type="primary"):
            if np1 and np1 == np2:
                run_command("UPDATE users SET password_hash=?, force_password_change=0 WHERE id=?", (hash_password(np1), uid))
                st.session_state.force_pw_change = 0; st.success("Heslo změněno!"); st.rerun()
            else:
                st.error("Hesla se neshodují.")
    st.stop()

# ── SIDEBAR ──
bc = "badge-pro" if is_pro else "badge-free"
bt = "⭐ PRO" if is_pro else "FREE"
st.sidebar.markdown(f"""
<div class="sb-card">
  <div class="sb-name">{display_name}</div>
  <div class="sb-meta">{st.session_state.username}</div>
  <span class="badge {bc}">{bt}</span>
</div>
""", unsafe_allow_html=True)

if st.sidebar.button("← Odhlásit"):
    st.session_state.user_id = None; st.rerun()

# ─────────────────────────────────────────────
# 7. ADMIN
# ─────────────────────────────────────────────
if role == 'admin':
    st.markdown('<div class="sec-hdr"><div class="sec-ico">👑</div><div class="sec-title">Admin Dashboard</div></div>', unsafe_allow_html=True)
    uc = run_query("SELECT COUNT(*) FROM users WHERE role!='admin'", single=True)['count'] or 0
    fc = run_query("SELECT COUNT(*) FROM faktury", single=True)['count'] or 0
    tr = run_query("SELECT SUM(castka_celkem) FROM faktury", single=True)['sum'] or 0
    au = tr / uc if uc else 0
    af = tr / fc if fc else 0
    st.markdown(f"""
<div class="adm-grid">
  <div class="adm-card"><div class="adm-val">{uc}</div><div class="adm-lbl">Uživatelů</div></div>
  <div class="adm-card"><div class="adm-val">{tr:,.0f} Kč</div><div class="adm-lbl">Celk. obrat</div></div>
  <div class="adm-card"><div class="adm-val">{au:,.0f} Kč</div><div class="adm-lbl">/ Uživatel</div></div>
  <div class="adm-card"><div class="adm-val">{af:,.0f} Kč</div><div class="adm-lbl">Prům. fak.</div></div>
</div>""", unsafe_allow_html=True)
    st.divider()
    tabs = st.tabs(["👥 Uživatelé & Licence", "🔑 Generátor klíčů", "📧 E-mailing"])
    with tabs[0]:
        fk = run_query("SELECT * FROM licencni_klice WHERE pouzito_uzivatelem_id IS NULL ORDER BY id DESC")
        key_dict = {f"{k['kod']} ({k['dny_platnosti']} dní)": k for k in fk}
        for u in run_query("SELECT * FROM users WHERE role!='admin' ORDER BY id DESC"):
            exp_d = u['license_valid_until']; act = False
            if exp_d:
                try:
                    if datetime.strptime(str(exp_d)[:10], '%Y-%m-%d').date() >= date.today(): act = True
                except: pass
            with st.expander(f"{'⭐' if act else '○'} {u['username']}  —  {u['email']}"):
                c1, c2 = st.columns(2)
                c1.write(f"**Jméno:** {u['full_name']}"); c1.write(f"**Tel:** {u['phone']}"); c1.write(f"**Vytvořeno:** {format_date(u['created_at'])}")
                cv = date.today()
                if u['license_valid_until']:
                    try: cv = datetime.strptime(str(u['license_valid_until'])[:10], '%Y-%m-%d').date()
                    except: pass
                nv = c2.date_input("Platnost do:", value=cv, key=f"md_{u['id']}")
                if c2.button("💾 Uložit datum", key=f"bd_{u['id']}"): run_command("UPDATE users SET license_valid_until=? WHERE id=?", (nv, u['id'])); st.success("OK"); st.rerun()
                sk = c2.selectbox("Přiřadit klíč", ["-- Vyberte --"] + list(key_dict.keys()), key=f"sk_{u['id']}")
                if c2.button("Aktivovat klíčem", key=f"btn_{u['id']}"):
                    if sk != "-- Vyberte --":
                        kd = key_dict[sk]; ne = date.today() + timedelta(days=kd['dny_platnosti'])
                        run_command("UPDATE users SET license_key=?, license_valid_until=? WHERE id=?", (kd['kod'], ne, u['id']))
                        run_command("UPDATE licencni_klice SET pouzito_uzivatelem_id=? WHERE id=?", (u['id'], kd['id']))
                        st.success("Aktivováno!"); st.rerun()
                if st.button("🗑️ Smazat uživatele", key=f"del_{u['id']}", type="primary"): run_command("DELETE FROM users WHERE id=?", (u['id'],)); st.rerun()
    with tabs[1]:
        c1, c2 = st.columns(2)
        dv = c1.number_input("Platnost (dny)", value=365, min_value=1); nv = c2.text_input("Poznámka")
        if st.button("Vygenerovat nový klíč"):
            k = gen_license(); run_command("INSERT INTO licencni_klice (kod,dny_platnosti,vygenerovano,poznamka) VALUES (?,?,?,?)", (k, dv, datetime.now().isoformat(), nv)); st.success(f"Klíč: `{k}`")
        for k in run_query("SELECT * FROM licencni_klice ORDER BY id DESC"):
            st.code(f"{k['kod']} | {k['dny_platnosti']} dní | {'🔴 Použit' if k['pouzito_uzivatelem_id'] else '🟢 Volný'} | {k['poznamka']}")
    with tabs[2]:
        tpl = run_query("SELECT * FROM email_templates WHERE name='welcome'", single=True); td = dict(tpl) if tpl else {}
        with st.form("wm"):
            ws = st.text_input("Předmět", value=td.get('subject', ''))
            wb = st.text_area("Text (použijte {name})", value=td.get('body', ''), height=180)
            if st.form_submit_button("Uložit šablonu"):
                run_command("INSERT INTO email_templates (name,subject,body) VALUES ('welcome',?,?) ON CONFLICT (name) DO UPDATE SET subject=EXCLUDED.subject, body=EXCLUDED.body", (ws, wb)); st.success("OK")
        st.divider()
        with st.form("mm"):
            ms = st.text_input("Předmět"); mb = st.text_area("Zpráva pro všechny", height=130)
            if st.form_submit_button("Odeslat všem"):
                cnt = sum(1 for u in run_query("SELECT email FROM users WHERE role!='admin' AND email IS NOT NULL") if send_email(u['email'], ms, mb))
                st.success(f"Odesláno na {cnt} emailů.")

# ─────────────────────────────────────────────
# 8. USER
# ─────────────────────────────────────────────
else:
    menu = st.sidebar.radio(" ", ["📄 Faktury", "📊 Dashboard", "🏛️ Daně", "💸 Výdaje", "👥 Klienti", "🏷️ Kategorie", "⚙️ Nastavení"])

    # ══════════════════════════════════
    # FAKTURY
    # ══════════════════════════════════
    if "Faktury" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">📄</div><div class="sec-title">Faktury</div></div>', unsafe_allow_html=True)

        # ── NOVÁ FUNKCE: Pohledávky po splatnosti ──
        overdue = run_query("""
            SELECT f.id, f.cislo_full, f.datum_splatnosti, f.castka_celkem, k.jmeno
            FROM faktury f JOIN klienti k ON f.klient_id=k.id
            WHERE f.user_id=? AND f.uhrazeno=0
              AND f.datum_splatnosti < ?
            ORDER BY f.datum_splatnosti ASC
        """, (uid, date.today().isoformat()))

        if overdue:
            total_overdue = sum(r['castka_celkem'] for r in overdue)
            rows_html = ""
            for r in overdue:
                try:
                    ds = datetime.strptime(str(r['datum_splatnosti'])[:10], '%Y-%m-%d').date()
                    days_late = (date.today() - ds).days
                    days_txt = f"{days_late} dní po splatnosti"
                except:
                    days_txt = "po splatnosti"
                rows_html += f"""
                <div class="overdue-row">
                  <div>
                    <div class="overdue-name">{r['jmeno']} &nbsp; <span style="color:#64748b;font-size:.8rem;">{r.get('cislo_full','')}</span></div>
                    <div class="overdue-detail">Splatnost: {format_date(r['datum_splatnosti'])}</div>
                  </div>
                  <div style="text-align:right">
                    <div class="overdue-amount">{r['castka_celkem']:,.0f} Kč</div>
                    <div class="overdue-days">{days_txt}</div>
                  </div>
                </div>"""
            st.markdown(f"""
<div class="overdue-panel">
  <div class="overdue-header">
    <span style="font-size:1.1rem">⚠️</span>
    <span class="overdue-title">Pohledávky po splatnosti</span>
    <span class="overdue-count">{len(overdue)}</span>
    <span style="margin-left:auto;font-family:'Syne',sans-serif;font-size:1rem;font-weight:700;color:#f87171;">{total_overdue:,.0f} Kč</span>
  </div>
  {rows_html}
</div>""", unsafe_allow_html=True)

        # ── Stats ──
        years = [r['substring'] for r in run_query("SELECT DISTINCT SUBSTRING(datum_vystaveni,1,4) as substring FROM faktury WHERE user_id=?", (uid,))]
        if str(datetime.now().year) not in years: years.append(str(datetime.now().year))
        sy = st.selectbox("Rok (statistiky)", sorted(list(set(years)), reverse=True), label_visibility="collapsed")
        sc_y = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND SUBSTRING(datum_vystaveni,1,4)=?", (uid, sy), True)['sum'] or 0
        sc_a = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?", (uid,), True)['sum'] or 0
        su_a = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0", (uid,), True)['sum'] or 0
        st.markdown(f"""
<div class="stats-row">
  <div class="sc g"><div class="sc-lbl">Obrat {sy}</div><div class="sc-val g">{sc_y:,.0f}</div><div class="sc-sub">Kč</div></div>
  <div class="sc a"><div class="sc-lbl">Celkem</div><div class="sc-val a">{sc_a:,.0f}</div><div class="sc-sub">Kč</div></div>
  <div class="sc r"><div class="sc-lbl">Neuhrazeno</div><div class="sc-val r">{su_a:,.0f}</div><div class="sc-sub">Kč</div></div>
</div>""", unsafe_allow_html=True)

        # ── Nová faktura ──
        with st.expander("➕  Nová faktura"):
            pp = get_pool(); conn = pp.getconn()
            try:
                kli = pd.read_sql("SELECT id, jmeno FROM klienti WHERE user_id=%s", conn, params=(uid,))
                kat = pd.read_sql("SELECT id, nazev FROM kategorie WHERE user_id=%s", conn, params=(uid,))
            finally:
                pp.putconn(conn)

            if kli.empty:
                st.warning("Nejprve přidejte klienta v sekci Klienti.")
            elif not is_pro and kat.empty:
                run_command("INSERT INTO kategorie (user_id,nazev,prefix,aktualni_cislo,barva) VALUES (?,'Obecná','FV',1,'#000000')", (uid,))
                cached_pdf.clear(); st.rerun()
            else:
                rid = st.session_state.form_reset_id
                c1, c2 = st.columns(2)
                sk = c1.selectbox("Klient", kli['jmeno'], key=f"k_{rid}")
                sc = c2.selectbox("Kategorie", kat['nazev'], key=f"c_{rid}")
                if not kli[kli['jmeno'] == sk].empty and not kat[kat['nazev'] == sc].empty:
                    kid = int(kli[kli['jmeno'] == sk]['id'].values[0])
                    cid = int(kat[kat['nazev'] == sc]['id'].values[0])
                    _, full, _ = get_next_num(cid, uid)
                    st.markdown(f'<div class="callout">Číslo dokladu: <span>{full}</span></div>', unsafe_allow_html=True)
                    d1, d2 = st.columns(2)
                    dv = d1.date_input("Datum vystavení", date.today(), key=f"dv_{rid}")
                    ds = d2.date_input("Datum splatnosti", date.today() + timedelta(14), key=f"ds_{rid}")
                    ut = st.text_input("Úvodní text", "Fakturujeme Vám:", key=f"ut_{rid}")
                    ed = st.data_editor(st.session_state.items_df, num_rows="dynamic", use_container_width=True, key=f"ed_{rid}")
                    total = float(pd.to_numeric(ed["Cena"], errors='coerce').fillna(0).sum()) if not ed.empty and "Cena" in ed.columns else 0.0
                    st.markdown(f'<div class="total-ln"><span class="total-lbl">Celkem k úhradě</span><span class="total-amt">{total:,.2f} Kč</span></div>', unsafe_allow_html=True)
                    if st.button("Vystavit fakturu →", type="primary", key=f"vystavit_{rid}"):
                        fid = run_command("INSERT INTO faktury (user_id,cislo_full,klient_id,kategorie_id,datum_vystaveni,datum_splatnosti,castka_celkem,variabilni_symbol,uvodni_text) VALUES (?,?,?,?,?,?,?,?,?)",
                                         (uid, full, kid, cid, dv, ds, total, re.sub(r"\D", "", full), ut))
                        for _, row in ed.iterrows():
                            if row.get("Popis položky"):
                                run_command("INSERT INTO faktura_polozky (faktura_id,nazev,cena) VALUES (?,?,?)", (fid, row["Popis položky"], float(row.get("Cena", 0))))
                        run_command("UPDATE kategorie SET aktualni_cislo=aktualni_cislo+1 WHERE id=?", (cid,))
                        reset_forms(); cached_pdf.clear(); cached_isdoc.clear(); st.success("Faktura vystavena!"); st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Filtry ──
        fc1, fc2 = st.columns(2)
        sel_cli = fc1.selectbox("Filtr klient", ["Všichni"] + [c['jmeno'] for c in run_query("SELECT jmeno FROM klienti WHERE user_id=?", (uid,))])
        db_years = [y['substring'] for y in run_query("SELECT DISTINCT SUBSTRING(datum_vystaveni,1,4) as substring FROM faktury WHERE user_id=?", (uid,))]
        sel_yr = fc2.selectbox("Filtr rok", ["Všechny"] + sorted(db_years, reverse=True))

        if sel_cli != "Všichni":
            ca = run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=?", (uid, sel_cli), True)['sum'] or 0
            cd = run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=? AND f.uhrazeno=0", (uid, sel_cli), True)['sum'] or 0
            cy = 0
            if sel_yr != "Všechny":
                cy = run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=? AND SUBSTRING(f.datum_vystaveni,1,4)=?", (uid, sel_cli, sel_yr), True)['sum'] or 0
            st.markdown(f"""
<div class="mini-row">
  <div class="mini-sc"><div class="mini-lbl">Historie</div><div class="mini-val">{ca:,.0f} Kč</div></div>
  <div class="mini-sc"><div class="mini-lbl">Obrat {sel_yr if sel_yr!='Všechny' else ''}</div><div class="mini-val g">{cy:,.0f} Kč</div></div>
  <div class="mini-sc"><div class="mini-lbl">Dluží</div><div class="mini-val r">{cd:,.0f} Kč</div></div>
</div>""", unsafe_allow_html=True)

        # ── Vyhledávání ──
        search_q = st.text_input("🔍  Hledat fakturu (číslo, klient, popis…)", placeholder="např. FV2024 nebo Novák", label_visibility="collapsed")

        q = "SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=%s"
        params = [uid]
        if sel_cli != "Všichni": q += " AND k.jmeno=%s"; params.append(sel_cli)
        if sel_yr != "Všechny": q += " AND SUBSTRING(f.datum_vystaveni,1,4)=%s"; params.append(sel_yr)

        pp = get_pool(); conn = pp.getconn()
        try:
            df_f = pd.read_sql(q + " ORDER BY f.id DESC LIMIT 30", conn, params=params)
        finally:
            pp.putconn(conn)

        # client-side search filter
        if search_q:
            sq = search_q.lower()
            df_f = df_f[
                df_f['jmeno'].str.lower().str.contains(sq, na=False) |
                df_f['cislo_full'].str.lower().str.contains(sq, na=False) |
                df_f['muj_popis'].fillna('').str.lower().str.contains(sq, na=False)
            ]

        if df_f.empty:
            st.info("Žádné faktury nenalezeny.")

        for row in df_f.to_dict('records'):
            cf = row.get('cislo_full') or f"F{row['id']}"
            paid = row['uhrazeno']
            # determine overdue
            is_overdue = False
            try:
                if not paid:
                    ds_obj = datetime.strptime(str(row['datum_splatnosti'])[:10], '%Y-%m-%d').date()
                    if ds_obj < date.today(): is_overdue = True
            except: pass

            if paid:
                tag = '<span class="tag-paid">Zaplaceno</span>'
            elif is_overdue:
                tag = '<span class="tag-overdue">Po splatnosti</span>'
            else:
                tag = '<span class="tag-due">Čeká na platbu</span>'

            with st.expander(f"{'✅' if paid else ('🔴' if is_overdue else '⏳')}  {cf}  ·  {row['jmeno']}  ·  {row['castka_celkem']:,.0f} Kč"):
                st.markdown(f"<div style='margin-bottom:12px'>{tag} &nbsp; <span style='color:#334155;font-size:.78rem'>Splatnost: {format_date(row.get('datum_splatnosti',''))}</span></div>", unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                if paid:
                    if c1.button("↩ Zrušit úhradu", key=f"u0_{row['id']}"): run_command("UPDATE faktury SET uhrazeno=0 WHERE id=?", (row['id'],)); cached_pdf.clear(); cached_isdoc.clear(); st.rerun()
                else:
                    if c1.button("✓ Zaplaceno", key=f"u1_{row['id']}"): run_command("UPDATE faktury SET uhrazeno=1 WHERE id=?", (row['id'],)); cached_pdf.clear(); cached_isdoc.clear(); st.rerun()

                rh = str(row)
                pdf_out = cached_pdf(row['id'], uid, is_pro, rh)
                if isinstance(pdf_out, bytes): c2.download_button("↓ PDF", pdf_out, f"{cf}.pdf", "application/pdf", key=f"pdf_{row['id']}")
                if is_pro:
                    isdoc_b = cached_isdoc(row['id'], uid, rh)
                    if isdoc_b: c2.download_button("↓ ISDOC", isdoc_b, f"{cf}.isdoc", "application/xml", key=f"isd_{row['id']}")

                ekey = f"edit_f_{row['id']}"
                if ekey not in st.session_state: st.session_state[ekey] = False
                if c3.button("✏️ Upravit", key=f"be_{row['id']}"): st.session_state[ekey] = True; st.rerun()

                if st.session_state[ekey]:
                    with st.form(f"fe_{row['id']}"):
                        nd = st.date_input("Splatnost", pd.to_datetime(row['datum_splatnosti']))
                        nm = st.text_input("Interní popis", row['muj_popis'] or "")
                        nut = st.text_input("Úvodní text", row['uvodni_text'] or "")
                        pp2 = get_pool(); conn2 = pp2.getconn()
                        try:
                            ci = pd.read_sql('SELECT nazev as "Popis položky", cena as "Cena" FROM faktura_polozky WHERE faktura_id=%s', conn2, params=(row['id'],))
                        finally:
                            pp2.putconn(conn2)
                        ned = st.data_editor(ci, num_rows="dynamic", use_container_width=True)
                        if st.form_submit_button("Uložit změny"):
                            nt = float(pd.to_numeric(ned["Cena"], errors='coerce').fillna(0).sum())
                            run_command("UPDATE faktury SET datum_splatnosti=?,muj_popis=?,castka_celkem=?,uvodni_text=? WHERE id=?", (nd, nm, nt, nut, row['id']))
                            run_command("DELETE FROM faktura_polozky WHERE faktura_id=?", (row['id'],))
                            for _, rw in ned.iterrows():
                                if rw.get("Popis položky"):
                                    run_command("INSERT INTO faktura_polozky (faktura_id,nazev,cena) VALUES (?,?,?)", (row['id'], rw["Popis položky"], float(rw.get("Cena", 0))))
                            st.session_state[ekey] = False; cached_pdf.clear(); cached_isdoc.clear(); st.rerun()

                if c3.button("🔄 Duplikovat", key=f"dup_{row['id']}"):
                    nn, nf, _ = get_next_num(row['kategorie_id'], uid)
                    nfid = run_command("INSERT INTO faktury (user_id,cislo,cislo_full,klient_id,kategorie_id,datum_vystaveni,datum_splatnosti,castka_celkem,variabilni_symbol,uvodni_text,muj_popis) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                      (uid, nn, nf, row['klient_id'], row['kategorie_id'], date.today(), date.today()+timedelta(14), row['castka_celkem'], re.sub(r"\D", "", nf), row['uvodni_text'], row['muj_popis']))
                    for it in run_query("SELECT * FROM faktura_polozky WHERE faktura_id=?", (row['id'],)):
                        run_command("INSERT INTO faktura_polozky (faktura_id,nazev,cena) VALUES (?,?,?)", (nfid, it['nazev'], it['cena']))
                    run_command("UPDATE kategorie SET aktualni_cislo=aktualni_cislo+1 WHERE id=?", (row['kategorie_id'],))
                    cached_pdf.clear(); cached_isdoc.clear(); st.success(f"Duplikát {nf} vytvořen!"); st.rerun()

                if st.button("🗑 Smazat", key=f"del_f_{row['id']}"): run_command("DELETE FROM faktury WHERE id=?", (row['id'],)); cached_pdf.clear(); cached_isdoc.clear(); st.rerun()

    # ══════════════════════════════════
    # DASHBOARD
    # ══════════════════════════════════
    elif "Dashboard" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">📊</div><div class="sec-title">Přehled podnikání</div></div>', unsafe_allow_html=True)
        tr  = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?", (uid,), True)['sum'] or 0
        tp  = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=1", (uid,), True)['sum'] or 0
        td  = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0", (uid,), True)['sum'] or 0
        cnt = run_query("SELECT COUNT(*) FROM faktury WHERE user_id=?", (uid,), True)['count'] or 0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Celkový obrat",  f"{tr:,.0f} Kč")
        c2.metric("Zaplaceno",      f"{tp:,.0f} Kč",  delta=f"{int(tp/tr*100) if tr else 0} %")
        c3.metric("Čeká na platbu", f"{td:,.0f} Kč",  delta="-", delta_color="inverse")
        c4.metric("Faktur celkem",  cnt)
        st.divider()
        gc1, gc2 = st.columns([2, 1])
        pp = get_pool(); conn = pp.getconn()
        try:
            with gc1:
                st.subheader("Vývoj v čase")
                df_g = pd.read_sql("SELECT datum_vystaveni, castka_celkem FROM faktury WHERE user_id=%s", conn, params=(uid,))
                if not df_g.empty:
                    df_g['datum'] = pd.to_datetime(df_g['datum_vystaveni'])
                    mo = df_g.groupby(df_g['datum'].dt.to_period('M'))['castka_celkem'].sum()
                    mo.index = mo.index.astype(str)
                    st.bar_chart(mo, color="#fbbf24")
                else:
                    st.info("Zatím žádná data.")
            with gc2:
                st.subheader("TOP 5 klientů")
                df_t = pd.read_sql("SELECT k.jmeno, SUM(f.castka_celkem) as celkem FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=%s GROUP BY k.jmeno ORDER BY celkem DESC LIMIT 5", conn, params=(uid,))
                if not df_t.empty: st.dataframe(df_t.set_index('jmeno').style.format("{:,.0f} Kč"), use_container_width=True)
                else: st.info("Žádní klienti.")
            st.subheader("Příjmy dle kategorií")
            df_c = pd.read_sql("SELECT k.nazev, SUM(f.castka_celkem) as celkem FROM faktury f JOIN kategorie k ON f.kategorie_id=k.id WHERE f.user_id=%s GROUP BY k.nazev", conn, params=(uid,))
            if not df_c.empty: st.bar_chart(df_c.set_index('nazev'))
        finally:
            pp.putconn(conn)

    # ══════════════════════════════════
    # DANĚ
    # ══════════════════════════════════
    elif "Daně" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">🏛️</div><div class="sec-title">Daňová kalkulačka</div></div>', unsafe_allow_html=True)
        years = [r['substring'] for r in run_query("SELECT DISTINCT SUBSTRING(datum_vystaveni,1,4) as substring FROM faktury WHERE user_id=?", (uid,))]
        cy = str(date.today().year)
        if cy not in years: years.append(cy)
        c1, c2 = st.columns(2)
        sty = c1.selectbox("Rok", sorted(list(set(years)), reverse=True))
        po = c2.selectbox("Typ činnosti", ["80% – Řemeslné živnosti, zemědělství", "60% – Ostatní živnosti (nejčastější)", "40% – Svobodná povolání, autorská práva", "30% – Pronájem majetku"], index=1)
        pp_pct = int(po.split("%")[0]) / 100
        inc  = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND SUBSTRING(datum_vystaveni,1,4)=?", (uid, sty), True)['sum'] or 0
        rex  = run_query("SELECT SUM(castka) FROM vydaje WHERE user_id=? AND SUBSTRING(datum,1,4)=?", (uid, sty), True)['sum'] or 0
        fex  = inc * pp_pct
        tbr  = max(0, inc - rex);  tbf = max(0, inc - fex)
        taxr = tbr * .15;          taxf = tbf * .15
        diff = taxf - taxr
        st.markdown(f'<div class="callout">Příjmy za rok {sty}: <span>{inc:,.0f} Kč</span></div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""<div class="tax-c">
              <div class="tax-title">A) Skutečné výdaje</div>
              <div class="tax-meta">Výdaje: {rex:,.0f} Kč &nbsp;·&nbsp; Základ: {tbr:,.0f} Kč</div>
              <div class="tax-amt">{taxr:,.0f} Kč</div>
              <div class="tax-sub">Daň 15 %</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""<div class="tax-c">
              <div class="tax-title">B) Paušál {int(pp_pct*100)} %</div>
              <div class="tax-meta">Výdaje: {fex:,.0f} Kč &nbsp;·&nbsp; Základ: {tbf:,.0f} Kč</div>
              <div class="tax-amt">{taxf:,.0f} Kč</div>
              <div class="tax-sub">Daň 15 %</div>
            </div>""", unsafe_allow_html=True)
        st.divider()
        if taxr < taxf:   st.success(f"🏆 Výhodnější jsou SKUTEČNÉ výdaje — ušetříte {diff:,.0f} Kč.")
        elif taxf < taxr: st.success(f"🏆 Výhodnější je PAUŠÁL — ušetříte {abs(diff):,.0f} Kč.")
        else:              st.info("Obě varianty vychází stejně.")

    # ══════════════════════════════════
    # VÝDAJE
    # ══════════════════════════════════
    elif "Výdaje" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">💸</div><div class="sec-title">Evidence výdajů</div></div>', unsafe_allow_html=True)
        with st.form("exp"):
            c1, c2 = st.columns(2)
            ed = c1.date_input("Datum", date.today()); ep = c2.text_input("Popis")
            c3, c4 = st.columns(2)
            ea = c3.number_input("Částka (Kč)", min_value=0.0, step=100.0)
            ec = c4.selectbox("Kategorie", ["Provoz", "Materiál", "Služby", "Ostatní"])
            if st.form_submit_button("+ Přidat výdaj"):
                run_command("INSERT INTO vydaje (user_id,datum,popis,castka,kategorie) VALUES (?,?,?,?,?)", (uid, ed, ep, ea, ec)); st.success("Uloženo"); st.rerun()
        pp = get_pool(); conn = pp.getconn()
        try:
            vy = pd.read_sql("SELECT * FROM vydaje WHERE user_id=%s ORDER BY datum DESC", conn, params=(uid,))
        finally:
            pp.putconn(conn)
        if not vy.empty:
            st.dataframe(vy[['id', 'datum', 'popis', 'kategorie', 'castka']], hide_index=True, use_container_width=True)
            cv = vy['castka'].sum(); cp = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?", (uid,), True)['sum'] or 0
            c1, c2, c3 = st.columns(3)
            c1.metric("Příjmy",     f"{cp:,.0f} Kč")
            c2.metric("Výdaje",     f"{cv:,.0f} Kč", delta=-cv)
            c3.metric("Hrubý zisk", f"{cp - cv:,.0f} Kč")
            vl = vy.apply(lambda x: f"ID {x['id']}: {x['datum']} – {x['popis']} ({x['castka']} Kč)", axis=1).tolist()
            sd = st.selectbox("Vyberte výdaj ke smazání", vl)
            if st.button("🗑 Smazat označený"):
                did = int(sd.split(":")[0].replace("ID ", ""))
                run_command("DELETE FROM vydaje WHERE id=? AND user_id=?", (did, uid)); st.rerun()

    # ══════════════════════════════════
    # KLIENTI
    # ══════════════════════════════════
    elif "Klienti" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">👥</div><div class="sec-title">Klienti</div></div>', unsafe_allow_html=True)
        rid = st.session_state.form_reset_id
        with st.expander("➕  Přidat klienta"):
            c1, c2 = st.columns([3, 1])
            ico_in = c1.text_input("IČO pro doplnění z ARES", key=f"ico_{rid}")
            if c2.button("Načíst ARES", key=f"ares_{rid}"):
                d = get_ares(ico_in)
                if d: st.session_state.ares_data = d; st.success("Data načtena ✓")
                else: st.error("Firma nenalezena v ARES")
            ad = st.session_state.ares_data
            with st.form("fc"):
                j = st.text_input("Jméno / Název firmy", ad.get('jmeno', ''))
                a = st.text_area("Adresa", ad.get('adresa', ''))
                c1, c2 = st.columns(2)
                i = c1.text_input("IČ", ad.get('ico', ''))
                d2 = c2.text_input("DIČ", ad.get('dic', ''))
                pz = st.text_area("Interní poznámka")
                if st.form_submit_button("Uložit klienta"):
                    run_command("INSERT INTO klienti (user_id,jmeno,adresa,ico,dic,poznamka) VALUES (?,?,?,?,?,?)", (uid, j, a, i, d2, pz))
                    reset_forms(); cached_pdf.clear(); cached_isdoc.clear(); st.rerun()

        for k in run_query("SELECT * FROM klienti WHERE user_id=?", (uid,)):
            with st.expander(f"◆  {k['jmeno']}"):
                if k['poznamka']: st.info(k['poznamka'])
                ek = f"edit_k_{k['id']}"
                if ek not in st.session_state: st.session_state[ek] = False
                c1, c2 = st.columns(2)
                if c1.button("✏️ Upravit", key=f"bek_{k['id']}"): st.session_state[ek] = True; st.rerun()
                if c2.button("🗑 Smazat",  key=f"bdk_{k['id']}"): run_command("DELETE FROM klienti WHERE id=?", (k['id'],)); cached_pdf.clear(); cached_isdoc.clear(); st.rerun()
                if st.session_state[ek]:
                    with st.form(f"fke_{k['id']}"):
                        nj = st.text_input("Jméno",    k['jmeno']); na = st.text_area("Adresa", k['adresa'])
                        ni = st.text_input("IČ",       k['ico']);   nd = st.text_input("DIČ",   k['dic'])
                        np = st.text_area("Poznámka",  k['poznamka'])
                        if st.form_submit_button("Uložit změny"):
                            run_command("UPDATE klienti SET jmeno=?,adresa=?,ico=?,dic=?,poznamka=? WHERE id=?", (nj, na, ni, nd, np, k['id']))
                            st.session_state[ek] = False; cached_pdf.clear(); cached_isdoc.clear(); st.rerun()

    # ══════════════════════════════════
    # KATEGORIE
    # ══════════════════════════════════
    elif "Kategorie" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">🏷️</div><div class="sec-title">Kategorie</div></div>', unsafe_allow_html=True)
        if not is_pro:
            st.markdown('<div class="pro-card"><h3>🔒 Funkce PRO verze</h3><p style="color:#64748b">Kategorie jsou dostupné v PRO verzi. Aktivujte v Nastavení.</p></div>', unsafe_allow_html=True)
        else:
            with st.expander("➕  Nová kategorie"):
                with st.form("fcat"):
                    c1, c2 = st.columns(2)
                    n = c1.text_input("Název");     p = c2.text_input("Prefix (např. FV)")
                    c3, c4 = st.columns(2)
                    s = c3.number_input("Start č.", 1); c = c4.color_picker("Barva akcentu")
                    l = st.file_uploader("Logo (PNG/JPG)")
                    if st.form_submit_button("Uložit kategorii"):
                        run_command("INSERT INTO kategorie (user_id,nazev,prefix,aktualni_cislo,barva,logo_blob) VALUES (?,?,?,?,?,?)",
                                   (uid, n, p, s, c, process_logo(l))); cached_pdf.clear(); st.rerun()

        for k in run_query("SELECT * FROM kategorie WHERE user_id=?", (uid,)):
            with st.expander(f"◆  {k['nazev']}  ·  {k['prefix']}"):
                if k['logo_blob']: st.image(bytes(k['logo_blob']), width=80)
                ck = f"edit_cat_{k['id']}"
                if ck not in st.session_state: st.session_state[ck] = False
                c1, c2 = st.columns(2)
                if is_pro and c1.button("✏️ Upravit", key=f"bec_{k['id']}"): st.session_state[ck] = True; st.rerun()
                if c2.button("🗑 Smazat",  key=f"bdc_{k['id']}"): run_command("DELETE FROM kategorie WHERE id=?", (k['id'],)); cached_pdf.clear(); st.rerun()
                if st.session_state[ck]:
                    with st.form(f"feck_{k['id']}"):
                        c1, c2 = st.columns(2)
                        nn = c1.text_input("Název",  k['nazev']); np = c2.text_input("Prefix", k['prefix'])
                        c3, c4 = st.columns(2)
                        ns = c3.number_input("Číslo", value=k['aktualni_cislo']); nc = c4.color_picker("Barva", k['barva'])
                        nl = st.file_uploader("Nové logo", key=f"ul_{k['id']}")
                        if st.form_submit_button("Uložit změny"):
                            if nl: run_command("UPDATE kategorie SET nazev=?,prefix=?,aktualni_cislo=?,barva=?,logo_blob=? WHERE id=?", (nn, np, ns, nc, process_logo(nl), k['id']))
                            else:  run_command("UPDATE kategorie SET nazev=?,prefix=?,aktualni_cislo=?,barva=? WHERE id=?",            (nn, np, ns, nc, k['id']))
                            st.session_state[ck] = False; cached_pdf.clear(); st.rerun()

    # ══════════════════════════════════
    # NASTAVENÍ
    # ══════════════════════════════════
    elif "Nastavení" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">⚙️</div><div class="sec-title">Nastavení</div></div>', unsafe_allow_html=True)
        res = run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1", (uid,), single=True)
        c = dict(res) if res else {}

        with st.expander("🔑  Licence & Přístup", expanded=True):
            valid, exp = check_license(uid)
            if not valid:
                st.markdown(f"""
<div class="pro-card">
  <h3>🚀 Aktivujte PRO verzi</h3>
  <div class="pro-feat-row">
    <div class="pro-feat">✦ Neomezené faktury</div><div class="pro-feat">✦ Export ISDOC</div>
    <div class="pro-feat">✦ Vlastní logo & barvy</div><div class="pro-feat">✦ Cloud záloha</div>
    <div class="pro-feat">✦ Přehled po splatnosti</div><div class="pro-feat">✦ Hledání faktur</div>
  </div>
  <div class="pro-price">990 Kč / rok &nbsp;·&nbsp; jsem@michalkochtik.cz</div>
</div>""", unsafe_allow_html=True)
                kk = st.text_input("Licenční klíč")
                if st.button("Aktivovat PRO →"):
                    kdb = run_query("SELECT * FROM licencni_klice WHERE kod=? AND pouzito_uzivatelem_id IS NULL", (kk,), True)
                    if kdb:
                        ne = date.today() + timedelta(days=kdb['dny_platnosti'])
                        run_command("UPDATE users SET license_key=?,license_valid_until=? WHERE id=?", (kk, ne, uid))
                        run_command("UPDATE licencni_klice SET pouzito_uzivatelem_id=? WHERE id=?", (uid, kdb['id']))
                        st.session_state.is_pro = True; st.balloons(); st.rerun()
                    else:
                        st.error("Neplatný nebo již použitý klíč.")
            else:
                st.success(f"✅ PRO licence aktivní do: **{format_date(exp)}**")
                if st.button("Deaktivovat licenci"):
                    run_command("UPDATE users SET license_key=NULL,license_valid_until=NULL WHERE id=?", (uid,))
                    st.session_state.is_pro = False; st.rerun()
            st.divider()
            st.markdown("**Změna hesla**")
            pc1, pc2 = st.columns(2)
            p1 = pc1.text_input("Stávající heslo", type="password")
            p2 = pc2.text_input("Nové heslo",      type="password")
            if st.button("Změnit heslo"):
                ud = run_query("SELECT * FROM users WHERE id=?", (uid,), True)
                if ud['password_hash'] == hash_password(p1):
                    run_command("UPDATE users SET password_hash=? WHERE id=?", (hash_password(p2), uid)); st.success("Heslo změněno.")
                else:
                    st.error("Stávající heslo je nesprávné.")

        with st.expander("🏢  Moje Firma"):
            with st.form("setf"):
                c1, c2 = st.columns(2)
                n  = c1.text_input("Název firmy / jméno", c.get('nazev', display_name))
                a  = c2.text_area("Adresa", c.get('adresa', ''))
                c3, c4 = st.columns(2)
                i  = c3.text_input("IČO", c.get('ico', ''))
                d  = c4.text_input("DIČ", c.get('dic', ''))
                c5, c6 = st.columns(2)
                b  = c5.text_input("Banka", c.get('banka', ''))
                u  = c6.text_input("Číslo účtu", c.get('ucet', ''))
                ib = st.text_input("IBAN (pro QR platbu)", c.get('iban', ''))
                if st.form_submit_button("Uložit nastavení"):
                    ic = ib.replace(" ", "").upper() if ib else ""
                    if c.get('id'):
                        run_command("UPDATE nastaveni SET nazev=?,adresa=?,ico=?,dic=?,banka=?,ucet=?,iban=? WHERE id=?", (n, a, i, d, b, u, ic, c['id']))
                    else:
                        run_command("INSERT INTO nastaveni (user_id,nazev,adresa,ico,dic,banka,ucet,iban) VALUES (?,?,?,?,?,?,?,?)", (uid, n, a, i, d, b, u, ic))
                    cached_pdf.clear(); cached_isdoc.clear(); st.rerun()

        with st.expander(f"🔔  Upozornění {'(PRO)' if not is_pro else ''}"):
            if not is_pro:
                st.markdown('<div class="pro-card"><p style="color:#64748b">Automatická upozornění jsou dostupná v PRO verzi.</p></div>', unsafe_allow_html=True)
            else:
                act = st.toggle("Aktivovat odesílání", value=bool(c.get('notify_active', 0)))
                ca1, ca2 = st.columns(2)
                nd = ca1.number_input("Dní předem",        value=c.get('notify_days', 3), min_value=1)
                ne = ca2.text_input("Email pro notifikace", value=c.get('notify_email', ''))
                st.markdown("**SMTP Server**")
                preset = st.selectbox("Rychlé nastavení", ["-- Vyberte --", "Seznam.cz", "Gmail", "Vlastní"])
                ds = c.get('smtp_server', 'smtp.seznam.cz'); dp = c.get('smtp_port', 465)
                if preset == "Seznam.cz": ds = "smtp.seznam.cz"; dp = 465
                elif preset == "Gmail":  ds = "smtp.gmail.com"; dp = 465
                ss = st.text_input("Server", value=ds)
                cs1, cs2 = st.columns(2)
                sp = cs1.number_input("Port",  value=dp)
                su = cs2.text_input("Login",   value=c.get('smtp_email', ''))
                sw = st.text_input("Heslo SMTP", value=c.get('smtp_password', ''), type="password")
                cx1, cx2 = st.columns(2)
                if cx1.button("💾 Uložit"):
                    run_command("UPDATE nastaveni SET notify_active=?,notify_days=?,notify_email=?,smtp_server=?,smtp_port=?,smtp_email=?,smtp_password=? WHERE id=?",
                               (int(act), nd, ne, ss, sp, su, sw, c.get('id'))); st.success("Uloženo")
                if cx2.button("📨 Testovat"):
                    if send_email(ne, "Test MojeFaktury", "Testovací zpráva funguje."): st.success("Email odeslán ✓")
                    else: st.error("Chyba odesílání")

        if is_pro:
            with st.expander("📦  Export ISDOC"):
                cx1, cx2 = st.columns(2)
                ds = cx1.date_input("Od", date.today().replace(day=1))
                de = cx2.date_input("Do", date.today())
                if st.button("Připravit ZIP"):
                    invs = run_query("SELECT id,cislo_full FROM faktury WHERE datum_vystaveni BETWEEN %s AND %s AND user_id=%s",
                                    (str(ds), str(de), uid))
                    if invs:
                        buf = io.BytesIO()
                        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                            for inv in invs:
                                isd = generate_isdoc(inv['id'], uid)
                                if isd: zf.writestr(f"{inv['cislo_full']}.isdoc", isd)
                        st.download_button("↓ Stáhnout export.zip", buf.getvalue(), "export.zip", "application/zip")
                    else:
                        st.warning("V zadaném období nejsou žádné faktury.")

            with st.expander("💾  Záloha dat"):
                z1, z2 = st.columns(2)
                z1.download_button("↓ Stáhnout JSON", get_export_data(uid), "zaloha.json", "application/json")
                if z2.button("Odeslat na email"):
                    if send_email(c.get('notify_email'), "Záloha MojeFaktury", "Data v příloze.", get_export_data(uid), "zaloha.json"):
                        st.success("Odesláno ✓")
                    else:
                        st.error("Chyba odesílání")
                st.divider()
                upl = st.file_uploader("Import ze zálohy (JSON)", type="json")
                if upl and st.button("Obnovit data"):
                    try:
                        data = json.load(upl); cm = {}; km = {}
                        for r in data.get('nastaveni', []):
                            ex = run_query("SELECT id FROM nastaveni WHERE user_id=?", (uid,), True)
                            if ex:
                                run_command("UPDATE nastaveni SET nazev=?,adresa=?,ico=?,dic=?,ucet=?,banka=?,email=?,telefon=?,iban=? WHERE id=?",
                                           (r.get('nazev'), r.get('adresa'), r.get('ico'), r.get('dic'), r.get('ucet'), r.get('banka'), r.get('email'), r.get('telefon'), r.get('iban'), ex['id']))
                            else:
                                run_command("INSERT INTO nastaveni (user_id,nazev,adresa,ico,dic,banka,ucet,iban) VALUES (?,?,?,?,?,?,?,?)",
                                           (uid, r.get('nazev'), r.get('adresa'), r.get('ico'), r.get('dic'), r.get('ucet'), r.get('banka'), r.get('iban')))
                        for r in data.get('klienti', []):
                            ex = run_query("SELECT id FROM klienti WHERE jmeno=? AND user_id=?", (r.get('jmeno'), uid), True)
                            if ex: cm[r['id']] = ex['id']
                            else:
                                nid = run_command("INSERT INTO klienti (user_id,jmeno,adresa,ico,dic,email,poznamka) VALUES (?,?,?,?,?,?,?)",
                                                 (uid, r.get('jmeno'), r.get('adresa'), r.get('ico'), r.get('dic'), r.get('email'), r.get('poznamka')))
                                if r.get('id'): cm[r['id']] = nid
                        for r in data.get('kategorie', []):
                            ex = run_query("SELECT id FROM kategorie WHERE nazev=? AND user_id=?", (r.get('nazev'), uid), True)
                            if ex: km[r['id']] = ex['id']
                            else:
                                blob = base64.b64decode(r.get('logo_blob')) if r.get('logo_blob') else None
                                nid = run_command("INSERT INTO kategorie (user_id,nazev,barva,prefix,aktualni_cislo,logo_blob) VALUES (?,?,?,?,?,?)",
                                                 (uid, r.get('nazev'), r.get('barva'), r.get('prefix'), r.get('aktualni_cislo'), blob))
                                if r.get('id'): km[r['id']] = nid
                        for r in data.get('faktury', []):
                            cid = cm.get(r.get('klient_id')); kid = km.get(r.get('kategorie_id'))
                            if cid and kid and not run_query("SELECT id FROM faktury WHERE cislo_full=? AND user_id=?", (r.get('cislo_full'), uid), True):
                                nfid = run_command("INSERT INTO faktury (user_id,cislo,cislo_full,klient_id,kategorie_id,datum_vystaveni,datum_duzp,datum_splatnosti,castka_celkem,zpusob_uhrady,variabilni_symbol,cislo_objednavky,uvodni_text,uhrazeno,muj_popis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                                  (uid, r.get('cislo'), r.get('cislo_full'), cid, kid, r.get('datum_vystaveni'), r.get('datum_duzp'), r.get('datum_splatnosti'), r.get('castka_celkem'), r.get('zpusob_uhrady'), r.get('variabilni_symbol'), r.get('cislo_objednavky'), r.get('uvodni_text'), r.get('uhrazeno'), r.get('muj_popis')))
                                for item in data.get('faktura_polozky', []):
                                    if item.get('faktura_id') == r.get('id'):
                                        run_command("INSERT INTO faktura_polozky (faktura_id,nazev,cena) VALUES (?,?,?)", (nfid, item.get('nazev'), item.get('cena')))
                        cached_pdf.clear(); cached_isdoc.clear(); st.success("Import dokončen!"); st.rerun()
                    except Exception as ex:
                        st.error(f"Chyba importu: {ex}")
        else:
            with st.expander("💾  Záloha dat"):
                st.markdown('<div class="pro-card"><p style="color:#64748b">Cloud záloha a export jsou dostupné v PRO verzi.</p></div>', unsafe_allow_html=True)
