import streamlit as st
import os, json, re, hashlib, requests, smtplib, unicodedata, io, base64
import pandas as pd, random, string, time, zipfile
import xml.etree.ElementTree as ET, urllib3
from datetime import datetime, date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formataddr
from PIL import Image
from fpdf import FPDF
import qrcode, psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

urllib3.disable_warnings()

# -- CONFIG --
try:
    admin_pass_init = st.secrets["ADMIN_INIT_PASS"]
    email_pass      = st.secrets.get("EMAIL_PASSWORD", "")
    db_url          = st.secrets["DATABASE_URL"]
except Exception:
    admin_pass_init = os.getenv("ADMIN_INIT_PASS")
    email_pass      = os.getenv("EMAIL_PASSWORD", "")
    db_url          = os.getenv("DATABASE_URL")

if not admin_pass_init or not db_url:
    st.error("⛔ Chybí ADMIN_INIT_PASS nebo DATABASE_URL!")
    st.stop()

SYSTEM_EMAIL = {"enabled": True, "server": "smtp.seznam.cz", "port": 465,
                "email": "jsem@michalkochtik.cz", "password": email_pass, "display_name": "MojeFakturace"}
FONT_FILE = 'arial.ttf'

# -- PAGE CONFIG --
st.set_page_config(page_title="MojeFaktury", page_icon="💎", layout="centered")

# -- CSS --
def inject_css(css_str):
    import base64 as _b64
    encoded = _b64.b64encode(css_str.encode("utf-8")).decode("utf-8")
    st.markdown(
        f'<link rel="stylesheet" href="data:text/css;charset=utf-8;base64,{encoded}">',
        unsafe_allow_html=True,
    )

st.markdown(
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800'
    '&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap"'
    ' rel="stylesheet">',
    unsafe_allow_html=True,
)

_BASE_CSS = r"""*,*::before,*::after{box-sizing:border-box}
.stApp{background:#07090f!important;font-family:'DM Sans',system-ui,sans-serif!important}
.stApp::before{content:'';position:fixed;inset:0;
  background:radial-gradient(ellipse 70% 45% at 15% 5%,rgba(251,191,36,.05) 0%,transparent 65%),
             radial-gradient(ellipse 55% 40% at 85% 90%,rgba(99,102,241,.04) 0%,transparent 55%);
  pointer-events:none;z-index:0}
h1,h2,h3,h4,h5,h6{font-family:'Syne',sans-serif!important;color:#f1f5f9!important;letter-spacing:-.025em;line-height:1.2}
h1{font-size:2rem!important;font-weight:800!important}
h2{font-size:1.45rem!important;font-weight:700!important}
h3{font-size:1.15rem!important;font-weight:600!important}
.stMarkdown p,.stMarkdown li{color:#94a3b8!important;font-family:'DM Sans',sans-serif!important;font-size:.9rem;line-height:1.6}
.stMarkdown strong,.stMarkdown b{color:#e2e8f0!important}
.stMarkdown a{color:#fbbf24!important;text-decoration:none}
label{color:#94a3b8!important;font-size:.82rem!important;font-weight:500!important}
.stTextInput input,.stNumberInput input,.stTextArea textarea,.stDateInput input{
  background:rgba(255,255,255,.04)!important;border:1px solid rgba(255,255,255,.1)!important;
  border-radius:10px!important;color:#f1f5f9!important;font-family:'DM Sans',sans-serif!important;
  font-size:.88rem!important;padding:11px 15px!important;transition:border .2s,box-shadow .2s!important}
.stTextInput input:focus,.stNumberInput input:focus,.stTextArea textarea:focus{
  border-color:rgba(251,191,36,.5)!important;box-shadow:0 0 0 3px rgba(251,191,36,.1)!important;
  background:rgba(255,255,255,.06)!important}
.stSelectbox div[data-baseweb="select"]>div{
  background:rgba(255,255,255,.04)!important;border:1px solid rgba(255,255,255,.1)!important;border-radius:10px!important}
.stSelectbox div[data-baseweb="select"] span{color:#f1f5f9!important}
.stSelectbox svg{fill:#64748b!important}
ul[data-baseweb="menu"]{background:#111827!important;border:1px solid rgba(255,255,255,.1)!important;
  border-radius:12px!important;padding:5px!important;box-shadow:0 20px 60px rgba(0,0,0,.55)!important}
li[data-baseweb="option"]{border-radius:8px!important;padding:9px 13px!important;transition:background .15s!important}
li[data-baseweb="option"]:hover{background:rgba(251,191,36,.12)!important}
li[data-baseweb="option"][aria-selected="true"]{background:rgba(251,191,36,.16)!important}
li[data-baseweb="option"] div{color:#cbd5e1!important}
li[data-baseweb="option"]:hover div,li[data-baseweb="option"][aria-selected="true"] div{color:#fbbf24!important;font-weight:600!important}
::placeholder{color:#334155!important}
.stButton>button{background:rgba(255,255,255,.05)!important;color:#cbd5e1!important;
  border:1px solid rgba(255,255,255,.11)!important;border-radius:10px!important;height:44px!important;
  font-family:'DM Sans',sans-serif!important;font-size:.85rem!important;font-weight:500!important;
  width:100%!important;transition:all .2s ease!important;white-space:nowrap!important}
.stButton>button:hover{background:rgba(251,191,36,.09)!important;border-color:rgba(251,191,36,.38)!important;
  color:#fbbf24!important;transform:translateY(-1px)!important;box-shadow:0 4px 18px rgba(251,191,36,.14)!important}
div[data-testid="stForm"] button[kind="primary"]{
  background:linear-gradient(135deg,#fbbf24,#d97706)!important;color:#0b0f1a!important;
  border:none!important;font-weight:700!important;box-shadow:0 4px 18px rgba(251,191,36,.28)!important}
div[data-testid="stForm"] button[kind="primary"]:hover{transform:translateY(-2px)!important;box-shadow:0 8px 28px rgba(251,191,36,.38)!important}
div[data-testid="stForm"] button[kind="primary"] p{color:#0b0f1a!important;font-weight:700!important}
[data-testid="stDownloadButton"]>button{background:rgba(255,255,255,.05)!important;color:#64748b!important;
  border:1px solid rgba(255,255,255,.09)!important;border-radius:10px!important;height:44px!important;
  font-family:'DM Sans',sans-serif!important;width:100%!important;transition:all .2s!important}
[data-testid="stDownloadButton"]>button:hover{border-color:rgba(52,211,153,.4)!important;
  color:#34d399!important;background:rgba(52,211,153,.07)!important}
section[data-testid="stSidebar"]{background:rgba(7,9,15,.97)!important;border-right:1px solid rgba(255,255,255,.055)!important}
section[data-testid="stSidebar"] .stRadio label{
  background:rgba(255,255,255,.025)!important;border:1px solid rgba(255,255,255,.055)!important;
  border-radius:10px!important;padding:11px 15px!important;margin-bottom:4px!important;
  width:100%!important;cursor:pointer!important;transition:all .18s!important}
section[data-testid="stSidebar"] .stRadio label:hover{background:rgba(251,191,36,.06)!important;border-color:rgba(251,191,36,.2)!important}
section[data-testid="stSidebar"] .stRadio label[data-checked="true"]{
  background:linear-gradient(135deg,rgba(251,191,36,.14),rgba(217,119,6,.09))!important;border-color:rgba(251,191,36,.33)!important}
section[data-testid="stSidebar"] .stRadio label[data-checked="true"] p{color:#fbbf24!important;font-weight:600!important}
div[data-testid="stExpander"]{background:rgba(255,255,255,.022)!important;border:1px solid rgba(255,255,255,.075)!important;
  border-radius:14px!important;overflow:hidden!important;transition:border-color .2s!important;margin-bottom:10px!important}
div[data-testid="stExpander"]:hover{border-color:rgba(251,191,36,.18)!important}
div[data-baseweb="calendar"]{background:#111827!important;border:1px solid rgba(255,255,255,.1)!important;border-radius:12px!important}
div[data-baseweb="calendar"] button{color:#f1f5f9!important}
button[data-baseweb="tab"]{background:transparent!important}
button[data-baseweb="tab"] div p{color:#475569!important;font-family:'DM Sans',sans-serif!important}
button[data-baseweb="tab"][aria-selected="true"] div p{color:#fbbf24!important;font-weight:600!important}
hr{border-color:rgba(255,255,255,.055)!important;margin:1.4rem 0!important}
[data-testid="stMetricValue"]{font-family:'Syne',sans-serif!important;font-weight:700!important;color:#f1f5f9!important}
[data-testid="stMetricLabel"]{font-family:'DM Sans',sans-serif!important;color:#475569!important;font-size:.75rem!important;text-transform:uppercase!important;letter-spacing:.08em!important}
[data-testid="stDataFrame"],[data-testid="stDataEditor"]{border:1px solid rgba(255,255,255,.07)!important;border-radius:12px!important;overflow:hidden!important}
[data-testid="stAlert"]{border-radius:12px!important}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:rgba(255,255,255,.02)}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,.09);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:rgba(251,191,36,.28)}
#MainMenu,footer,header{visibility:hidden!important}

.brand-wrap{padding:40px 0 20px;text-align:center}
.brand-logo{font-size:58px;display:block;margin-bottom:6px;animation:bobble 3.2s ease-in-out infinite}
@keyframes bobble{0%,100%{transform:translateY(0)}50%{transform:translateY(-9px)}}
.brand-title{font-family:'Syne',sans-serif;font-size:2.9rem;font-weight:800;
  background:linear-gradient(120deg,#fbbf24 0%,#fde68a 45%,#f59e0b 100%);background-size:200% auto;
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
  animation:shine 3.5s linear infinite;letter-spacing:-.03em;
  word-break:keep-all;overflow-wrap:normal;white-space:nowrap}
@keyframes shine{to{background-position:200% center}}
.brand-sub{color:#475569;font-size:1rem;margin:8px 0 28px;line-height:1.6}
.feat-grid{background:rgba(255,255,255,.022);border:1px solid rgba(255,255,255,.07);border-radius:16px;padding:22px 24px;margin-bottom:24px}
.feat-row{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:.87rem;color:#64748b}
.feat-row:last-child{border-bottom:none}
.feat-row b{color:#e2e8f0}
.sb-card{background:rgba(251,191,36,.055);border:1px solid rgba(251,191,36,.14);border-radius:13px;padding:15px;margin-bottom:14px}
.sb-name{font-family:'Syne',sans-serif;font-size:.98rem;font-weight:700;color:#f1f5f9;margin-bottom:3px}
.sb-meta{font-size:.76rem;color:#475569;margin-bottom:9px}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.7rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase}
.badge-pro{background:linear-gradient(135deg,#fbbf24,#d97706);color:#0b0f1a}
.badge-free{background:rgba(71,85,105,.25);border:1px solid rgba(71,85,105,.4);color:#64748b}
.stats-row{display:grid;grid-template-columns:repeat(3,1fr);gap:11px;margin:14px 0 22px}
.sc{background:rgba(255,255,255,.028);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:15px 14px;text-align:center;position:relative;overflow:hidden;transition:transform .2s,border-color .2s}
.sc:hover{transform:translateY(-2px);border-color:rgba(255,255,255,.13)}
.sc::before{content:'';position:absolute;top:0;left:0;right:0;height:2px}
.sc.g::before{background:linear-gradient(90deg,#34d399,#10b981)}
.sc.a::before{background:linear-gradient(90deg,#fbbf24,#f59e0b)}
.sc.r::before{background:linear-gradient(90deg,#f87171,#ef4444)}
.sc-lbl{font-size:.65rem;color:#475569;text-transform:uppercase;letter-spacing:.09em;font-weight:600;margin-bottom:5px}
.sc-val{font-family:'Syne',sans-serif;font-size:1.3rem;font-weight:800;line-height:1}
.sc-val.g{color:#34d399}.sc-val.a{color:#fbbf24}.sc-val.r{color:#f87171}
.sc-sub{font-size:.68rem;color:#1e293b;margin-top:3px}
.sec-hdr{display:flex;align-items:center;gap:11px;margin-bottom:20px;padding-bottom:14px;border-bottom:1px solid rgba(255,255,255,.055)}
.sec-ico{width:34px;height:34px;background:rgba(251,191,36,.09);border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:.95rem;flex-shrink:0}
.sec-title{font-family:'Syne',sans-serif;font-size:1.25rem;font-weight:700;color:#f1f5f9}
.callout{background:rgba(251,191,36,.055);border:1px solid rgba(251,191,36,.18);border-radius:9px;padding:11px 15px;margin:7px 0;font-size:.84rem;color:#94a3b8}
.callout span{color:#fbbf24;font-weight:600}
.total-ln{display:flex;justify-content:space-between;align-items:center;background:rgba(251,191,36,.055);border:1px solid rgba(251,191,36,.16);border-radius:10px;padding:13px 17px;margin:11px 0}
.total-lbl{font-size:.84rem;color:#64748b}
.total-amt{font-family:'Syne',sans-serif;font-size:1.18rem;font-weight:800;color:#fbbf24}
.tag-paid{display:inline-block;padding:2px 9px;background:rgba(52,211,153,.1);border:1px solid rgba(52,211,153,.22);border-radius:20px;font-size:.69rem;font-weight:600;color:#34d399;letter-spacing:.04em}
.tag-due{display:inline-block;padding:2px 9px;background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.22);border-radius:20px;font-size:.69rem;font-weight:600;color:#fbbf24;letter-spacing:.04em}
.tag-overdue{display:inline-block;padding:2px 9px;background:rgba(248,113,113,.1);border:1px solid rgba(248,113,113,.25);border-radius:20px;font-size:.69rem;font-weight:600;color:#f87171;letter-spacing:.04em}
.overdue-panel{background:rgba(248,113,113,.07);border:1px solid rgba(248,113,113,.25);border-radius:14px;padding:18px 20px;margin-bottom:18px}
.overdue-header{display:flex;align-items:center;gap:10px;margin-bottom:14px}
.overdue-title{font-family:'Syne',sans-serif;font-size:1rem;font-weight:700;color:#f87171}
.overdue-count{background:rgba(248,113,113,.2);border:1px solid rgba(248,113,113,.3);border-radius:20px;padding:2px 9px;font-size:.72rem;font-weight:700;color:#f87171}
.overdue-row{display:flex;justify-content:space-between;align-items:center;padding:9px 0;border-bottom:1px solid rgba(248,113,113,.1)}
.overdue-row:last-child{border-bottom:none}
.overdue-name{font-size:.85rem;color:#e2e8f0;font-weight:500}
.overdue-detail{font-size:.75rem;color:#64748b;margin-top:2px}
.overdue-amount{font-family:'Syne',sans-serif;font-size:.95rem;font-weight:700;color:#f87171;text-align:right}
.overdue-days{font-size:.72rem;color:#f87171;opacity:.8;text-align:right}
.mini-row{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:11px 0}
.mini-sc{background:rgba(255,255,255,.022);border:1px solid rgba(255,255,255,.065);border-radius:10px;padding:11px;text-align:center}
.mini-lbl{font-size:.63rem;color:#334155;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px}
.mini-val{font-family:'Syne',sans-serif;font-size:1rem;font-weight:700;color:#f1f5f9}
.mini-val.g{color:#34d399}.mini-val.r{color:#f87171}
.tax-c{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.075);border-radius:15px;padding:22px;text-align:center;transition:all .22s}
.tax-c:hover{border-color:rgba(251,191,36,.22)}
.tax-title{font-size:.72rem;text-transform:uppercase;letter-spacing:.1em;color:#475569;margin-bottom:10px}
.tax-meta{font-size:.78rem;color:#334155;margin-bottom:8px}
.tax-amt{font-family:'Syne',sans-serif;font-size:1.9rem;font-weight:800;color:#fbbf24;margin:6px 0}
.tax-sub{font-size:.72rem;color:#334155}
.pro-card{background:linear-gradient(135deg,rgba(251,191,36,.07),rgba(217,119,6,.04));border:1px solid rgba(251,191,36,.18);border-radius:15px;padding:22px;margin-bottom:18px}
.pro-card h3{font-family:'Syne',sans-serif!important;color:#fbbf24!important;margin-bottom:10px}
.pro-feat-row{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:14px}
.pro-feat{font-size:.8rem;color:#64748b}
.pro-price{color:#fbbf24;font-weight:600;font-size:.88rem}
.adm-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:22px}
.adm-card{background:rgba(255,255,255,.022);border:1px solid rgba(255,255,255,.07);border-radius:13px;padding:17px 14px;text-align:center}
.adm-val{font-family:'Syne',sans-serif;font-size:1.45rem;font-weight:800;color:#f1f5f9;margin-bottom:4px}
.adm-lbl{font-size:.69rem;color:#475569;text-transform:uppercase;letter-spacing:.08em}

@media (max-width: 640px) {
  .block-container{padding-left:12px!important;padding-right:12px!important;padding-top:16px!important}
  .brand-wrap{padding:24px 0 14px}
  .brand-logo{font-size:44px}
  .brand-title{font-size:2rem!important;white-space:normal!important;word-break:break-word!important;overflow-wrap:break-word!important;line-height:1.15!important}
  .brand-sub{font-size:.88rem;margin:6px 0 18px}
  .feat-grid{padding:14px 16px}
  .feat-row{font-size:.8rem;gap:7px}
  h1{font-size:1.5rem!important}
  h2{font-size:1.2rem!important}
  h3{font-size:1rem!important}
  .sec-title{font-size:1rem!important}
  .stats-row{grid-template-columns:repeat(3,1fr)!important;gap:7px!important}
  .sc{padding:11px 8px!important}
  .sc-val{font-size:1.05rem!important}
  .sc-lbl{font-size:.58rem!important}
  .mini-row{grid-template-columns:repeat(3,1fr)!important;gap:6px!important}
  .mini-sc{padding:9px 6px!important}
  .mini-val{font-size:.88rem!important}
  .adm-grid{grid-template-columns:repeat(2,1fr)!important}
  .cf-grid{grid-template-columns:1fr!important;gap:8px!important}
  .overdue-header{flex-wrap:wrap;gap:6px}
  .overdue-row{flex-direction:column;align-items:flex-start;gap:4px}
  .overdue-amount,.overdue-days{text-align:left!important}
  .total-ln{padding:11px 13px}
  .total-amt{font-size:1rem!important}
  .tax-c{padding:16px!important}
  .tax-amt{font-size:1.5rem!important}
  .pro-feat-row{grid-template-columns:1fr!important}
  .recur-card{flex-direction:column!important;align-items:flex-start!important;gap:10px!important}
  .quote-header{flex-direction:column!important;align-items:flex-start!important;gap:6px!important}
  .quote-amt{text-align:left!important}
  .cf-row{flex-direction:column!important;align-items:flex-start!important;gap:3px!important}
  .cf-row-amt{text-align:left!important}
  .stButton>button{height:48px!important;font-size:.82rem!important}
  div[data-testid="stForm"] button[kind="primary"]{height:48px!important}
  .stTextInput input,.stNumberInput input,.stTextArea textarea,.stDateInput input{font-size:16px!important;padding:12px 13px!important}
  section[data-testid="stSidebar"]{padding:8px!important}
  section[data-testid="stSidebar"] .stRadio label{padding:10px 12px!important}
  div[data-testid="stExpander"]{margin-bottom:7px!important}
  .timer-display{font-size:2.6rem!important}
  .timer-card{padding:16px!important}
  .sec-hdr{margin-bottom:14px!important;padding-bottom:10px!important}
  .sec-ico{width:28px!important;height:28px!important;font-size:.8rem!important}
  .callout{font-size:.8rem!important;padding:9px 12px!important}
  .tpl-grid{gap:6px}
  .tpl-chip{padding:6px 10px!important;font-size:.75rem!important}
}"""
inject_css(_BASE_CSS)

# ==============================================
# DB
# ==============================================
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
        print(f"Query: {e}"); return None
    finally: p.putconn(conn)

def run_command(sql, params=()):
    sql = sql.replace("?", "%s")
    is_ins = sql.strip().upper().startswith("INSERT")
    if is_ins and "RETURNING id" not in sql and "ON CONFLICT" not in sql: sql += " RETURNING id"
    p = get_pool(); conn = p.getconn()
    try:
        with conn.cursor() as c:
            c.execute(sql, params); conn.commit()
            if is_ins and "RETURNING id" in sql:
                try: return c.fetchone()[0]
                except: return None
        return None
    except Exception as e:
        print(f"Cmd: {e}"); return None
    finally: p.putconn(conn)

def init_db():
    p = get_pool(); conn = p.getconn()
    try:
        with conn.cursor() as c:
            c.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, full_name TEXT, email TEXT, phone TEXT, license_key TEXT, license_valid_until TEXT, role TEXT DEFAULT 'user', created_at TEXT, last_active TEXT, force_password_change INTEGER DEFAULT 0)")
            c.execute("CREATE TABLE IF NOT EXISTS nastaveni (id SERIAL PRIMARY KEY, user_id INTEGER, nazev TEXT, adresa TEXT, ico TEXT, dic TEXT, ucet TEXT, banka TEXT, email TEXT, telefon TEXT, iban TEXT, smtp_server TEXT, smtp_port INTEGER, smtp_email TEXT, smtp_password TEXT, notify_email TEXT, notify_days INTEGER, notify_active INTEGER, faktura_sablona INTEGER DEFAULT 1)")
            c.execute("CREATE TABLE IF NOT EXISTS klienti (id SERIAL PRIMARY KEY, user_id INTEGER, jmeno TEXT, adresa TEXT, ico TEXT, dic TEXT, email TEXT, poznamka TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS kategorie (id SERIAL PRIMARY KEY, user_id INTEGER, nazev TEXT, barva TEXT, prefix TEXT, aktualni_cislo INTEGER DEFAULT 1, logo_blob BYTEA)")
            c.execute("CREATE TABLE IF NOT EXISTS faktury (id SERIAL PRIMARY KEY, user_id INTEGER, cislo INTEGER, cislo_full TEXT, klient_id INTEGER, kategorie_id INTEGER, datum_vystaveni TEXT, datum_duzp TEXT, datum_splatnosti TEXT, castka_celkem REAL, zpusob_uhrady TEXT, variabilni_symbol TEXT, cislo_objednavky TEXT, uvodni_text TEXT, uhrazeno INTEGER DEFAULT 0, muj_popis TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS faktura_polozky (id SERIAL PRIMARY KEY, faktura_id INTEGER, nazev TEXT, cena REAL)")
            c.execute("CREATE TABLE IF NOT EXISTS licencni_klice (id SERIAL PRIMARY KEY, kod TEXT UNIQUE, dny_platnosti INTEGER, vygenerovano TEXT, pouzito_uzivatelem_id INTEGER, poznamka TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS email_templates (id SERIAL PRIMARY KEY, name TEXT UNIQUE, subject TEXT, body TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS vydaje (id SERIAL PRIMARY KEY, user_id INTEGER, datum TEXT, popis TEXT, castka REAL, kategorie TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS casovac (id SERIAL PRIMARY KEY, user_id INTEGER, projekt TEXT, klient_id INTEGER, start_ts TEXT, end_ts TEXT, trvani_min REAL, sazba REAL DEFAULT 500, fakturovano INTEGER DEFAULT 0, poznamka TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS opakujici (id SERIAL PRIMARY KEY, user_id INTEGER, nazev TEXT, klient_id INTEGER, kategorie_id INTEGER, interval_typ TEXT DEFAULT 'mesicne', posledni_vytvoreni TEXT, aktivni INTEGER DEFAULT 1, uvodni_text TEXT, polozky_json TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS item_sablony (id SERIAL PRIMARY KEY, user_id INTEGER, nazev TEXT, cena REAL)")
            c.execute("CREATE TABLE IF NOT EXISTS nabidky (id SERIAL PRIMARY KEY, user_id INTEGER, cislo_full TEXT, klient_id INTEGER, kategorie_id INTEGER, datum_vystaveni TEXT, datum_platnosti TEXT, castka_celkem REAL, uvodni_text TEXT, stav TEXT DEFAULT 'otevrena', faktura_id INTEGER, poznamka TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS nabidka_polozky (id SERIAL PRIMARY KEY, nabidka_id INTEGER, nazev TEXT, cena REAL)")
        conn.commit()
        try:
            with conn.cursor() as c: c.execute("ALTER TABLE users ADD COLUMN force_password_change INTEGER DEFAULT 0")
            conn.commit()
        except: conn.rollback()
        try:
            with conn.cursor() as c: c.execute("ALTER TABLE nastaveni ADD COLUMN faktura_sablona INTEGER DEFAULT 1")
            conn.commit()
        except: conn.rollback()
        with conn.cursor() as c:
            try: c.execute("INSERT INTO email_templates (name,subject,body) VALUES ('welcome','Vitejte','Dobry den {name},\n\nVas ucet byl vytvofen.\n\nTym MojeFakturace') ON CONFLICT (name) DO NOTHING")
            except: pass
            try:
                ah = hashlib.sha256(admin_pass_init.encode()).hexdigest()
                c.execute("INSERT INTO users (username,password_hash,role,full_name,email,phone,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (username) DO NOTHING",
                          ("admin",ah,"admin","Super Admin","admin@system.cz","000000000",datetime.now().isoformat()))
                c.execute("UPDATE users SET password_hash=%s WHERE username='admin'",(ah,))
            except Exception as e: print(f"Admin: {e}")
        conn.commit()
    finally: p.putconn(conn)

if 'db_inited' not in st.session_state:
    init_db(); st.session_state.db_inited = True

# ==============================================
# HELPERS
# ==============================================
def hp(pw): return hashlib.sha256(pw.encode()).hexdigest()
def rm_acc(s): return "".join(c for c in unicodedata.normalize('NFKD',str(s)) if not unicodedata.combining(c)) if s else ""
def fmt_d(d):
    try: return datetime.strptime(str(d)[:10],'%Y-%m-%d').strftime('%d.%m.%Y') if isinstance(d,str) else d.strftime('%d.%m.%Y')
    except: return ""
def gen_pw(n=8): return ''.join(random.choice(string.ascii_letters+string.digits) for _ in range(n))
def gen_lic(): return '-'.join(''.join(random.choices(string.ascii_uppercase+string.digits,k=4)) for _ in range(4))
def fmt_min(m):
    h=int(m)//60; mm=int(m)%60
    return f"{h}h {mm:02d}m" if h else f"{mm}m"

def check_lic(uid):
    res = run_query("SELECT license_valid_until FROM users WHERE id=?", (uid,), single=True)
    if not res or not res['license_valid_until']: return False,"Zadna"
    try:
        exp = datetime.strptime(str(res['license_valid_until'])[:10],'%Y-%m-%d').date()
        return (True,exp) if exp>=date.today() else (False,exp)
    except: return False,"Chyba"

def next_num(kat_id,uid):
    r = run_query("SELECT prefix,aktualni_cislo FROM kategorie WHERE id=? AND user_id=?",(kat_id,uid),single=True)
    if r: return r['aktualni_cislo'],f"{r['prefix']}{r['aktualni_cislo']}",r['prefix']
    return 1,"1",""

@st.cache_data(ttl=86400)
def get_ares(ico):
    if not ico: return None
    ico = "".join(filter(str.isdigit,str(ico))).zfill(8)
    try:
        r = requests.get(f"https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}",
                         headers={"accept":"application/json","User-Agent":"Mozilla/5.0"},verify=False,timeout=5)
        if r.status_code==200:
            d=r.json(); s=d.get('sidlo',{})
            ul=s.get('nazevUlice',''); cd=s.get('cisloDomovni'); co=s.get('cisloOrientacni')
            ob=s.get('nazevObce',''); psc=s.get('psc','')
            ct=str(cd) if cd else ""
            if co: ct+=f"/{co}"
            pts=[]
            if ul: pts.append(f"{ul} {ct}".strip())
            elif ct and ob: pts.append(f"{ob} {ct}")
            if psc and ob: pts.append(f"{psc} {ob}")
            adr=", ".join(pts) or s.get('textovaAdresa','')
            return {"jmeno":d.get('obchodniJmeno',''),"adresa":adr,"ico":ico,"dic":d.get('dic','') or d.get('dicId','')}
    except Exception as e: print(f"ARES:{e}")
    return None

def proc_logo(f):
    if not f: return None
    try:
        img=Image.open(f)
        if img.mode in("RGBA","P"): img=img.convert("RGB")
        b=io.BytesIO(); img.save(b,format='PNG'); return b.getvalue()
    except: return None

def send_mail(to,sub,body,att=None,fname="zaloha.json"):
    if not SYSTEM_EMAIL["enabled"] or not SYSTEM_EMAIL["password"]: return False
    try:
        msg=MIMEMultipart(); msg['From']=formataddr((SYSTEM_EMAIL["display_name"],SYSTEM_EMAIL["email"]))
        msg['To']=to; msg['Subject']=sub; msg.attach(MIMEText(body,'plain'))
        if att:
            part=MIMEApplication(att,Name=fname); part['Content-Disposition']=f'attachment; filename="{fname}"'; msg.attach(part)
        s=smtplib.SMTP_SSL(SYSTEM_EMAIL["server"],SYSTEM_EMAIL["port"])
        s.login(SYSTEM_EMAIL["email"],SYSTEM_EMAIL["password"]); s.sendmail(SYSTEM_EMAIL["email"],to,msg.as_string()); s.quit()
        return True
    except: return False

def export_data(uid):
    out={}; p=get_pool(); conn=p.getconn()
    try:
        for t in ['nastaveni','klienti','kategorie','faktury','vydaje','item_sablony','opakujici']:
            df=pd.read_sql(f"SELECT * FROM {t} WHERE user_id=%s",conn,params=(uid,))
            if 'logo_blob' in df.columns: df['logo_blob']=df['logo_blob'].apply(lambda x:base64.b64encode(x).decode() if x else None)
            out[t]=df.to_dict(orient='records')
        df_p=pd.read_sql("SELECT fp.* FROM faktura_polozky fp JOIN faktury f ON fp.faktura_id=f.id WHERE f.user_id=%s",conn,params=(uid,))
        out['faktura_polozky']=df_p.to_dict(orient='records')
    except Exception as e: print(f"Export:{e}"); return "{}"
    finally: p.putconn(conn)
    return json.dumps(out,default=str)

@st.cache_data(ttl=300)
def get_nastaveni(uid):
    r = run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1",(uid,),single=True)
    return dict(r) if r else {}

def _draw_footer(pdf,fn,moje,tx,sc,accent_line,hrule,PAGE_H,ML,MW,C_LIGHT,C_RULE,ar,ag,ab):
    foot_y=PAGE_H-13
    accent_line(foot_y-3,thick=0.7)
    foot_parts=[]
    if moje.get('nazev'):   foot_parts.append(tx(moje['nazev']))
    if moje.get('ico'):     foot_parts.append(tx(f"IC: {moje['ico']}"))
    if moje.get('email'):   foot_parts.append(tx(moje.get('email','')))
    sc(C_LIGHT); pdf.set_font(fn,'',6.5)
    pdf.set_xy(ML,foot_y); pdf.cell(MW-20,5,"   |   ".join(foot_parts),0,0,'C')
    pdf.set_xy(210-18-20,foot_y); pdf.cell(20,5,f"str. {pdf.page_no()}",0,0,'R')

# ==============================================
# PDF GENERÁTOR — šablona iDoklad
# Levý barevný pruh se štítky sekcí, logo, platební panel s QR
# ==============================================
def generate_pdf(fid, uid, is_pro):
    use_font = os.path.exists(FONT_FILE)

    def tx(t): return rm_acc(str(t)) if t else ""
    def fp(v):
        try: return f"{float(v):,.2f}".replace(",", " ").replace(".", ",")
        except: return "0,00"

    ML=18; MR=18; MT=16
    PAGE_W=210; PAGE_H=297
    MW=PAGE_W-ML-MR
    LINE_H=5.0; ROW_H=7.5; HDR_H=8.5
    MAX_Y=PAGE_H-20

    C_BLACK=(15,15,15); C_DARK=(40,40,40); C_MID=(95,95,95)
    C_LIGHT=(155,155,155); C_RULE=(210,210,210)
    C_BG_HEAD=(238,238,238); C_BG_ALT=(250,250,250)
    C_WHITE=(255,255,255)

    try:
        raw=run_query(
            "SELECT f.*,k.jmeno as k_jmeno,k.adresa as k_adresa,k.ico as k_ico,k.dic as k_dic,"
            "kat.barva,kat.logo_blob,kat.prefix FROM faktury f "
            "JOIN klienti k ON f.klient_id=k.id "
            "JOIN kategorie kat ON f.kategorie_id=kat.id "
            "WHERE f.id=%s AND f.user_id=%s",(fid,uid),single=True)
        if not raw: return None
        data=dict(raw)
        pol=[dict(x) for x in (run_query("SELECT * FROM faktura_polozky WHERE faktura_id=%s",(fid,)) or [])]
        moje=get_nastaveni(uid)
        paid=bool(data.get('uhrazeno',0))
        cf=data.get('cislo_full') or f"{data.get('prefix','')}{data.get('cislo','')}"

        ar,ag,ab=70,90,120
        if data.get('barva'):
            try:
                cv=data['barva'].lstrip('#')
                ar,ag,ab=tuple(int(cv[i:i+2],16) for i in (0,2,4))
            except: pass

        class PDF(FPDF):
            def __init__(self):
                super().__init__()
                self.fn='ArialCS' if use_font else 'Arial'
                if use_font:
                    try:
                        self.add_font('ArialCS','',FONT_FILE,uni=True)
                        self.add_font('ArialCS','B',FONT_FILE,uni=True)
                    except: self.fn='Arial'
            def header(self): pass
            def footer(self): pass

        pdf=PDF(); fn=pdf.fn
        pdf.set_margins(ML,MT,MR)
        pdf.set_auto_page_break(False)
        pdf.add_page()

        def sc(rgb): pdf.set_text_color(*rgb)
        def sfc(rgb): pdf.set_fill_color(*rgb)
        def sdc(rgb): pdf.set_draw_color(*rgb)
        def lw(w): pdf.set_line_width(w)

        def hrule(y,thick=0.2,color=C_RULE):
            sdc(color); lw(thick)
            pdf.line(ML,y,PAGE_W-MR,y); lw(0.2)

        def accent_line(y,thick=1.2,x1=None,x2=None):
            sdc((ar,ag,ab)); lw(thick)
            pdf.line(x1 or ML,y,x2 or PAGE_W-MR,y); lw(0.2)

        # Adresní řádky
        dod_lines=[]
        if moje.get('adresa'): dod_lines.append(tx(moje['adresa']))
        if moje.get('ico'):    dod_lines.append(tx(f"IC: {moje['ico']}"))
        if moje.get('dic'):    dod_lines.append(tx(f"DIC: {moje['dic']}"))
        if moje.get('email'):  dod_lines.append(tx(moje.get('email','')))
        if moje.get('telefon'): dod_lines.append(tx(f"Mobil: {moje['telefon']}"))
        odb_lines=[]
        if data.get('k_adresa'): odb_lines.append(tx(data['k_adresa']))
        if data.get('k_ico'):    odb_lines.append(tx(f"IC: {data['k_ico']}"))
        if data.get('k_dic'):    odb_lines.append(tx(f"DIC: {data['k_dic']}"))

        def fmt_d_local(d):
            try: return str(d)[:10].replace('-','.') if d else ''
            except: return str(d)[:10] if d else ''

        # ══════════════════════════════════════════════════════════════
        # LAYOUT KONSTANT
        # ══════════════════════════════════════════════════════════════
        SB_W   = 8
        CONT_X = SB_W + ML
        CONT_W = PAGE_W - SB_W - ML - MR

        # ── Celostránkový barevný pruh vlevo ──────────────────────────
        sfc((ar,ag,ab)); sdc((ar,ag,ab)); lw(0)
        pdf.rect(0, 0, SB_W, PAGE_H, 'F'); lw(0.2)

        # ── Pomocná fn: rotovaný štítek v pruhu ───────────────────────
        def sidebar_label(label_text, y_top, height):
            if height < 8: return
            pdf.set_font(fn, 'B', 5.5); sc(C_WHITE)
            cx = SB_W / 2
            cy = y_top + height / 2
            try:
                pdf.rotate(90, cx, cy)
                tw = max(height - 4, 4)
                pdf.set_xy(cx - tw / 2, cy - SB_W / 2 + 1)
                pdf.cell(tw, SB_W - 2, tx(label_text), 0, 0, 'C')
                pdf.rotate(0)
            except Exception:
                pass

        # ══════════════════════════════════════════════════════════════
        # SEKCE 1 — IDENTIFIKAČNÍ ÚDAJE
        # ══════════════════════════════════════════════════════════════
        y = MT
        sec1_top = y

        # Logo (z kategorie) nebo název firmy
        logo_drawn = False
        logo_h = 0
        if data.get('logo_blob'):
            try:
                lf = f"/tmp/logo_{fid}.png"
                with open(lf, "wb") as f2:
                    f2.write(data['logo_blob'])
                pdf.image(lf, CONT_X, y, h=18)
                logo_h = 18; logo_drawn = True
                try: os.remove(lf)
                except: pass
            except: pass

        if not logo_drawn:
            pdf.set_font(fn, 'B', 11); sc(C_BLACK)
            pdf.set_xy(CONT_X, y + 2)
            pdf.cell(CONT_W / 2, 7, tx(moje.get('nazev',''))[:40], 0, 0, 'L')
            logo_h = 10

        # Číslo faktury vpravo nahoře
        pdf.set_font(fn, '', 8); sc(C_MID)
        pdf.set_xy(CONT_X + CONT_W / 2, y)
        pdf.cell(CONT_W / 2, 5, 'Faktura', 0, 0, 'L')
        pdf.set_font(fn, 'B', 20); sc(C_BLACK)
        pdf.set_xy(CONT_X + CONT_W / 2, y + 5)
        pdf.cell(CONT_W / 2, 10, tx(cf), 0, 0, 'L')

        # Dodavatel — pod logem
        y = max(y + logo_h, y + 22) + 4
        pdf.set_font(fn, 'B', 7.5); sc(C_MID)
        pdf.set_xy(CONT_X, y)
        pdf.cell(CONT_W / 2, 4.5, tx('Dodavatel'), 0, 0, 'L'); y += 4.5
        pdf.set_font(fn, 'B', 9); sc(C_BLACK)
        pdf.set_xy(CONT_X, y)
        pdf.cell(CONT_W / 2, 5.5, tx(moje.get('nazev',''))[:40], 0, 0, 'L'); y += 5.5

        dod_y_start = y
        pdf.set_font(fn, '', 8); sc(C_DARK)
        for dl in dod_lines:
            pdf.set_xy(CONT_X, y)
            pdf.cell(CONT_W / 2 - 2, LINE_H, dl, 0, 0, 'L'); y += LINE_H

        # Odběratel — pravý sloupec
        odb_y = dod_y_start - 5.5
        pdf.set_font(fn, 'B', 7.5); sc(C_MID)
        pdf.set_xy(CONT_X + CONT_W / 2 + 4, odb_y)
        pdf.cell(CONT_W / 2 - 4, 4.5, tx('Odberatel'), 0, 0, 'L'); odb_y += 4.5
        pdf.set_font(fn, 'B', 9); sc(C_BLACK)
        pdf.set_xy(CONT_X + CONT_W / 2 + 4, odb_y)
        pdf.cell(CONT_W / 2 - 4, 5.5, tx(data.get('k_jmeno',''))[:40], 0, 0, 'L'); odb_y += 5.5
        pdf.set_font(fn, '', 8); sc(C_DARK)
        for ol in odb_lines:
            pdf.set_xy(CONT_X + CONT_W / 2 + 4, odb_y)
            pdf.cell(CONT_W / 2 - 4, LINE_H, ol, 0, 0, 'L'); odb_y += LINE_H

        sec1_end = max(y, odb_y) + 4
        sidebar_label("IDENTIFIKACNI UDAJE", sec1_top, sec1_end - sec1_top)

        # Datum vystavení / splatnosti
        hrule(sec1_end, thick=0.25, color=(200,200,200))
        y = sec1_end + 4
        pdf.set_font(fn, '', 8); sc(C_DARK)
        pdf.set_xy(CONT_X, y)
        pdf.cell(CONT_W, LINE_H,
                 tx(f"Datum vystaveni:  {fmt_d_local(data.get('datum_vystaveni',''))}     "
                    f"Datum splatnosti:  {fmt_d_local(data.get('datum_splatnosti',''))}"),
                 0, 0, 'L')
        y += LINE_H + 2

        # ══════════════════════════════════════════════════════════════
        # SEKCE 2 — PLATEBNÍ ÚDAJE
        # ══════════════════════════════════════════════════════════════
        sec2_top = y
        hrule(sec2_top, thick=0.25, color=(200,200,200))
        y += 3

        ucet_str   = f"{moje.get('ucet','')} / {moje.get('banka','')}" if moje.get('ucet') else "-"
        iban_str   = moje.get('iban','')
        vs_str     = str(data.get('variabilni_symbol',''))
        zpusob_str = tx(data.get('zpusob_uhrady','Prevodem'))
        amt        = data.get('castka_celkem', 0)

        col1_x = CONT_X + 2
        col2_x = CONT_X + CONT_W * 0.34
        col3_x = CONT_X + CONT_W * 0.60

        def pay_kv(lbl, val, x, yy, cw=None):
            cw = cw or (CONT_W * 0.25)
            pdf.set_font(fn, '', 6.5); sc(C_LIGHT)
            pdf.set_xy(x, yy); pdf.cell(cw, 3.5, tx(lbl), 0, 0, 'L')
            pdf.set_font(fn, 'B', 7.5); sc(C_DARK)
            pdf.set_xy(x, yy + 3.5); pdf.cell(cw, 4.5, tx(val), 0, 0, 'L')

        pay_row_h = 10

        # Box "K úhradě" — vpravo, přes oba řádky
        box_w = CONT_W * 0.20
        box_x = CONT_X + CONT_W - box_w
        sfc((ar,ag,ab)); sdc((ar,ag,ab)); lw(0)
        pdf.rect(box_x, y, box_w, pay_row_h * 2 + 1, 'F'); lw(0.2)
        pdf.set_font(fn, '', 7); pdf.set_text_color(210,225,245)
        pdf.set_xy(box_x + 2, y + 2)
        pdf.cell(box_w - 4, 4, tx("K uhrade"), 0, 0, 'C')
        pdf.set_font(fn, 'B', 12); sc(C_WHITE)
        pdf.set_xy(box_x + 2, y + 8)
        pdf.cell(box_w - 4, 7, fp(amt) + " Kc", 0, 0, 'C')

        # Řádek 1 platebních info
        pay_kv("Bankovni ucet", ucet_str, col1_x, y)
        pay_kv("Symbol", f"variabilni:  {vs_str}", col2_x, y)
        pay_kv("Zpusob platby:", zpusob_str, col3_x, y)
        y += pay_row_h

        # Řádek 2
        if iban_str:
            pay_kv("IBAN:", iban_str, col1_x, y, cw=CONT_W * 0.32)
        pay_kv("", "konstantni:  0308", col2_x, y)
        if data.get('datum_duzp'):
            pay_kv("Datum DUZP:", fmt_d_local(data['datum_duzp']), col3_x, y)
        y += pay_row_h

        # QR kód
        qr_drawn = False
        if moje.get('iban'):
            try:
                ic  = str(moje['iban']).replace(" ","").upper()
                qr_s = (f"SPD*1.0*ACC:{ic}*AM:{amt}*CC:CZK"
                        f"*X-VS:{vs_str}*MSG:{rm_acc('Faktura ' + cf)}")
                qri = qrcode.QRCode(version=1,
                                    error_correction=qrcode.constants.ERROR_CORRECT_M,
                                    box_size=4, border=0)
                qri.add_data(qr_s); qri.make(fit=True)
                qi  = qri.make_image(fill_color="black", back_color="white")
                qf  = f"/tmp/qr_{fid}.png"; qi.save(qf)
                pdf.image(qf, col1_x, y + 1, 18)
                try: os.remove(qf)
                except: pass
                pdf.set_font(fn, 'B', 6); sc(C_MID)
                pdf.set_xy(col1_x + 20, y + 6)
                pdf.cell(30, 3.5, tx("QR Platba+F"), 0, 0, 'L')
                qr_drawn = True
            except: pass

        y += (20 if qr_drawn else 4) + 3
        sec2_end = y
        sidebar_label("PLATEBNI UDAJE", sec2_top, sec2_end - sec2_top)

        # ══════════════════════════════════════════════════════════════
        # SEKCE 3 — FAKTURUJEME VÁM (tabulka položek)
        # ══════════════════════════════════════════════════════════════
        hrule(sec2_end, thick=0.25, color=(200,200,200))
        y = sec2_end + 3
        sec3_top = y

        # Úvodní text
        if data.get('uvodni_text') and str(data['uvodni_text']).strip():
            pdf.set_font(fn, 'B', 7.5); sc(C_DARK)
            pdf.set_xy(CONT_X, y)
            pdf.multi_cell(CONT_W, LINE_H, tx(data['uvodni_text']))
            y = pdf.get_y() + 2

        # Záhlaví tabulky
        COL_NAME = CONT_W * 0.52
        COL_QTY  = CONT_W * 0.12
        COL_UNIT = CONT_W * 0.18
        COL_TOT  = CONT_W * 0.18

        sfc(C_BG_HEAD); sdc(C_RULE); lw(0.2)
        pdf.rect(CONT_X, y, CONT_W, HDR_H, 'FD')
        pdf.set_font(fn, 'B', 7.5); sc(C_DARK)
        pdf.set_xy(CONT_X + 3, y + 2)
        pdf.cell(COL_NAME - 3, 5, tx("Oznaceni dodavky"), 0, 0, 'L')
        pdf.set_xy(CONT_X + COL_NAME, y + 2)
        pdf.cell(COL_QTY, 5, tx("Pocet"), 0, 0, 'C')
        pdf.set_xy(CONT_X + COL_NAME + COL_QTY, y + 2)
        pdf.cell(COL_UNIT, 5, tx("Cena/mj"), 0, 0, 'R')
        pdf.set_xy(CONT_X + COL_NAME + COL_QTY + COL_UNIT, y + 2)
        pdf.cell(COL_TOT, 5, tx("Celkem"), 0, 0, 'R')
        accent_line(y + HDR_H, thick=0.8,
                    x1=CONT_X, x2=CONT_X + CONT_W)
        y += HDR_H

        for idx, item in enumerate(pol):
            nazev = str(item.get('nazev','')).strip()
            if not nazev: continue
            est = max(1, (len(nazev) + 59) // 60)
            rh  = max(ROW_H, est * LINE_H + 3)

            if y + rh > MAX_Y - 35:
                sidebar_label("FAKTURUJEME VAM", sec3_top, y - sec3_top)
                _draw_footer(pdf, fn, moje, tx, sc, accent_line, hrule,
                             PAGE_H, ML, MW, C_LIGHT, C_RULE, ar, ag, ab)
                pdf.add_page(); y = MT; sec3_top = y
                # Pruh na nové stránce
                sfc((ar,ag,ab)); sdc((ar,ag,ab)); lw(0)
                pdf.rect(0, 0, SB_W, PAGE_H, 'F'); lw(0.2)
                sfc(C_BG_HEAD); sdc(C_RULE); lw(0.2)
                pdf.rect(CONT_X, y, CONT_W, HDR_H, 'FD')
                pdf.set_font(fn, 'B', 7.5); sc(C_DARK)
                pdf.set_xy(CONT_X + 3, y + 2)
                pdf.cell(COL_NAME - 3, 5, tx("Oznaceni dodavky (pokrac.)"), 0, 0, 'L')
                pdf.set_xy(CONT_X + COL_NAME + COL_QTY + COL_UNIT, y + 2)
                pdf.cell(COL_TOT, 5, tx("Celkem"), 0, 0, 'R')
                accent_line(y + HDR_H, thick=0.8,
                            x1=CONT_X, x2=CONT_X + CONT_W)
                y += HDR_H

            if idx % 2 == 1:
                sfc(C_BG_ALT); lw(0)
                pdf.rect(CONT_X, y, CONT_W, rh, 'F'); lw(0.2)

            pdf.set_font(fn, '', 8.5); sc(C_DARK)
            pdf.set_xy(CONT_X + 3, y + 2)
            pdf.multi_cell(COL_NAME - 6, LINE_H, tx(nazev), 0, 'L')

            # Počet: vždy 1,00 (položky ukládáme jako celkovou cenu)
            pdf.set_font(fn, '', 8.5); sc(C_MID)
            pdf.set_xy(CONT_X + COL_NAME, y + (rh - LINE_H) / 2)
            pdf.cell(COL_QTY, LINE_H, "1,00", 0, 0, 'C')

            # Cena za mj = celkem
            pdf.set_xy(CONT_X + COL_NAME + COL_QTY, y + (rh - LINE_H) / 2)
            pdf.cell(COL_UNIT, LINE_H, fp(item.get('cena', 0)), 0, 0, 'R')

            # Celkem
            pdf.set_font(fn, 'B', 8.5); sc(C_DARK)
            pdf.set_xy(CONT_X + COL_NAME + COL_QTY + COL_UNIT,
                       y + (rh - LINE_H) / 2)
            pdf.cell(COL_TOT, LINE_H, fp(item.get('cena', 0)), 0, 0, 'R')

            hrule(y + rh, thick=0.15); y += rh

        sec3_end = y
        sidebar_label("FAKTURUJEME VAM", sec3_top, sec3_end - sec3_top)

        # ══════════════════════════════════════════════════════════════
        # SEKCE 4 — REKAPITULACE
        # ══════════════════════════════════════════════════════════════
        y += 5
        sec4_top = y
        hrule(y, thick=0.25, color=(200,200,200))
        y += 4

        note = ("Dovolujeme si Vas upozornit, ze v pripade nedodrzeni data splatnosti "
                "uvedeneho na fakture Vam muzeme uctovat zakonny urok z prodleni.")
        pdf.set_font(fn, '', 7.5); sc(C_LIGHT)
        pdf.set_xy(CONT_X, y)
        pdf.multi_cell(CONT_W * 0.60, LINE_H - 0.5, tx(note))
        note_end = pdf.get_y()

        # Celkem k úhradě — barevný box vpravo
        tot_w = CONT_W * 0.36
        tot_x = CONT_X + CONT_W - tot_w
        sfc((ar,ag,ab)); sdc((ar,ag,ab)); lw(0)
        pdf.rect(tot_x, y, tot_w, 13, 'F'); lw(0.2)
        pdf.set_font(fn, '', 7); pdf.set_text_color(210,225,245)
        pdf.set_xy(tot_x + 3, y + 2)
        pdf.cell(tot_w - 6, 4, tx("Celkem k uhrade:"), 0, 0, 'L')
        pdf.set_font(fn, 'B', 13); sc(C_WHITE)
        pdf.set_xy(tot_x + 3, y + 7)
        pdf.cell(tot_w - 6, 6, fp(amt) + " Kc", 0, 0, 'R')

        y = max(note_end, y + 15) + 4
        sidebar_label("REKAPITULACE", sec4_top,
                      min(y, PAGE_H - 18) - sec4_top)

        # ══════════════════════════════════════════════════════════════
        # VODOZNAK "ZAPLACENO"
        # ══════════════════════════════════════════════════════════════
        if paid:
            pdf.set_font(fn, 'B', 52)
            pdf.set_text_color(225, 225, 225)
            pdf.set_xy(25, 125)
            try:
                pdf.rotate(30); pdf.cell(0, 0, "ZAPLACENO", 0, 0, 'C'); pdf.rotate(0)
            except: pass

        # ══════════════════════════════════════════════════════════════
        # PATIČKA
        # ══════════════════════════════════════════════════════════════
        foot_y = PAGE_H - 13
        accent_line(foot_y - 3, thick=0.7)
        foot_parts = []
        if moje.get('nazev'):   foot_parts.append(tx(moje['nazev']))
        if moje.get('ico'):     foot_parts.append(tx(f"IC: {moje['ico']}"))
        if moje.get('email'):   foot_parts.append(tx(moje.get('email','')))
        if moje.get('telefon'): foot_parts.append(tx(moje['telefon']))
        pdf.set_font(fn, '', 6.5); sc(C_LIGHT)
        pdf.set_xy(ML, foot_y)
        pdf.cell(MW - 20, 5, "   |   ".join(foot_parts), 0, 0, 'C')
        pdf.set_xy(PAGE_W - MR - 20, foot_y)
        pdf.cell(20, 5, f"str. {pdf.page_no()}", 0, 0, 'R')

        try: out = pdf.output(dest='S')
        except TypeError: out = pdf.output()
        return out.encode('latin-1') if isinstance(out, str) else bytes(out)

    except Exception as e:
        import traceback; traceback.print_exc()
        return str(e)


def generate_isdoc(fid,uid):
    data=run_query("SELECT f.*,k.jmeno,k.ico,k.adresa,m.nazev as m_nazev,m.ico as m_ico FROM faktury f JOIN klienti k ON f.klient_id=k.id JOIN nastaveni m ON f.user_id=m.user_id WHERE f.id=?",(fid,),True)
    if not data: return None
    d=dict(data)
    root=ET.Element("Invoice",xmlns="http://isdoc.cz/namespace/2013",version="6.0.1")
    ET.SubElement(root,"DocumentType").text="1"; ET.SubElement(root,"ID").text=str(d.get('cislo_full',d['id']))
    ET.SubElement(root,"IssueDate").text=str(d['datum_vystaveni']); ET.SubElement(root,"TaxPointDate").text=str(d.get('datum_duzp',''))
    ET.SubElement(root,"LocalCurrencyCode").text="CZK"
    sp=ET.SubElement(root,"AccountingSupplierParty"); p=ET.SubElement(sp,"Party")
    pn=ET.SubElement(p,"PartyName"); ET.SubElement(pn,"Name").text=str(d.get('m_nazev',''))
    pi=ET.SubElement(p,"PartyIdentification"); ET.SubElement(pi,"ID").text=str(d.get('m_ico',''))
    cp=ET.SubElement(root,"AccountingCustomerParty"); pc=ET.SubElement(cp,"Party")
    pnc=ET.SubElement(pc,"PartyName"); ET.SubElement(pnc,"Name").text=str(d.get('jmeno',''))
    pic=ET.SubElement(pc,"PartyIdentification"); ET.SubElement(pic,"ID").text=str(d.get('ico',''))
    amt=ET.SubElement(root,"LegalMonetaryTotal")
    for tag in ["TaxExclusiveAmount","TaxInclusiveAmount","PayableAmount"]:
        ET.SubElement(amt,tag).text=str(d['castka_celkem'])
    return ET.tostring(root,encoding='utf-8')

@st.cache_data(show_spinner=False,max_entries=500)
def cached_pdf(fid,uid,is_pro,rh): return generate_pdf(fid,uid,is_pro)
@st.cache_data(show_spinner=False,max_entries=500)
def cached_isdoc(fid,uid,rh): return generate_isdoc(fid,uid)

# ==============================================
# SESSION
# ==============================================
for k,v in [('user_id',None),('role','user'),('is_pro',False),
            ('items_df',pd.DataFrame(columns=["Popis polozky","Cena"])),
            ('form_reset_id',0),('ares_data',{}),
            ('timer_start',None),('timer_projekt',''),('timer_sazba',500)]:
    if k not in st.session_state: st.session_state[k]=v

def reset_forms():
    st.session_state.form_reset_id+=1; st.session_state.ares_data={}
    st.session_state.items_df=pd.DataFrame(columns=["Popis polozky","Cena"])

# ==============================================
# LOGIN
# ==============================================
if not st.session_state.user_id:
    _,col,_ = st.columns([1,10,1])
    with col:
        st.markdown("""
<div class="brand-wrap">
  <span class="brand-logo">💎</span>
  <div class="brand-title">MojeFaktury</div>
  <p class="brand-sub">Fakturace pro moderni zivnostniky.<br>Rychla, prehledna, vzdy po ruce.</p>
</div>
<div class="feat-grid">
  <div class="feat-row">✦ &nbsp;<b>14 dni PRO zdarma</b> — bez kreditky</div>
  <div class="feat-row">✦ &nbsp;<b>Faktura do 30 sekund</b> — primocirary tok</div>
  <div class="feat-row">✦ &nbsp;<b>Krasne PDF faktury</b> — s logem a QR platbou</div>
  <div class="feat-row">✦ &nbsp;<b>Casovac hodin</b> — trackuj cas → faktura</div>
  <div class="feat-row">✦ &nbsp;<b>Opakovane faktury</b> — automatizace odberatelu</div>
</div>""", unsafe_allow_html=True)
        t1,t2,t3=st.tabs(["  Prihlaseni  ","  Registrace  ","  Zapomenute heslo  "])
        with t1:
            with st.form("log"):
                u=st.text_input("Jmeno nebo Email").strip(); p=st.text_input("Heslo",type="password").strip()
                if st.form_submit_button("Vstoupit →",type="primary",use_container_width=True):
                    r=run_query("SELECT * FROM users WHERE (username=? OR email=?) AND password_hash=?",(u,u,hp(p)),single=True)
                    if r:
                        for k2,v2 in [('user_id',r['id']),('role',r['role']),('username',r['username']),('full_name',r['full_name']),('user_email',r['email'])]:
                            st.session_state[k2]=v2
                        st.session_state.force_pw_change=dict(r).get('force_password_change',0)
                        valid,exp=check_lic(r['id']); st.session_state.is_pro=valid
                        run_command("UPDATE users SET last_active=? WHERE id=?",(datetime.now().isoformat(),r['id'])); st.rerun()
                    else: st.error("Neplatne prihlasovaci udaje.")
        with t2:
            with st.form("reg"):
                f=st.text_input("Jmeno a Prijmeni").strip(); u=st.text_input("Login").strip()
                e=st.text_input("Email").strip(); tel=st.text_input("Telefon").strip(); p=st.text_input("Heslo",type="password").strip()
                if st.form_submit_button("Vytvorit ucet →",use_container_width=True):
                    try:
                        uid_new=run_command("INSERT INTO users (username,password_hash,full_name,email,phone,created_at,force_password_change) VALUES (?,?,?,?,?,?,0)",(u,hp(p),f,e,tel,datetime.now().isoformat()))
                        tk=gen_lic()
                        run_command("INSERT INTO licencni_klice (kod,dny_platnosti,vygenerovano,poznamka,pouzito_uzivatelem_id) VALUES (?,?,?,?,?)",(tk,14,datetime.now().isoformat(),"Auto-Trial",uid_new))
                        run_command("UPDATE users SET license_key=?,license_valid_until=? WHERE id=?",(tk,date.today()+timedelta(14),uid_new))
                        st.success("Ucet vytvoren + 14 dni PRO zdarma. Prihlaste se.")
                    except Exception as ex: st.error(f"Chyba: {ex}")
        with t3:
            with st.form("forgot"):
                fe=st.text_input("Vas Email").strip()
                if st.form_submit_button("Odeslat nove heslo →",use_container_width=True):
                    usr=run_query("SELECT * FROM users WHERE email=?",(fe,),single=True)
                    if usr:
                        np=gen_pw(); run_command("UPDATE users SET password_hash=?,force_password_change=1 WHERE id=?",(hp(np),usr['id']))
                        if send_mail(fe,"Reset hesla – MojeFaktury",f"Nove heslo: {np}\nPo prihlaseni budete vyzvan ke zmene."): st.success("Odeslano.")
                        else: st.error("Chyba odesilani.")
                    else: st.error("Email nenalezen.")
    st.stop()

# ==============================================
# CSS pro přihlášené
# ==============================================
_APP_CSS = r"""
.timer-display{font-family:'Syne',sans-serif;font-size:3.5rem;font-weight:800;text-align:center;
  color:#fbbf24;letter-spacing:.05em;margin:16px 0;
  text-shadow:0 0 40px rgba(251,191,36,.3)}
.timer-card{background:rgba(251,191,36,.06);border:1px solid rgba(251,191,36,.2);
  border-radius:16px;padding:24px;text-align:center;margin-bottom:16px}
.timer-label{font-size:.75rem;color:#64748b;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px}
.recur-card{background:rgba(99,102,241,.06);border:1px solid rgba(99,102,241,.2);
  border-radius:14px;padding:16px 18px;margin-bottom:10px;
  display:flex;justify-content:space-between;align-items:center}
.recur-name{font-family:'Syne',sans-serif;font-size:.95rem;font-weight:700;color:#f1f5f9}
.recur-meta{font-size:.78rem;color:#64748b;margin-top:2px}
.recur-badge{background:rgba(99,102,241,.2);border:1px solid rgba(99,102,241,.35);
  border-radius:20px;padding:3px 10px;font-size:.7rem;font-weight:700;color:#818cf8;letter-spacing:.04em}
.tpl-grid{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.tpl-chip{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);
  border-radius:8px;padding:7px 12px;font-size:.8rem;color:#94a3b8;cursor:pointer;transition:all .15s}
.tpl-chip:hover{background:rgba(251,191,36,.1);border-color:rgba(251,191,36,.3);color:#fbbf24}
.tpl-chip .price{color:#475569;margin-left:6px;font-size:.75rem}
.quote-card{background:rgba(99,102,241,.06);border:1px solid rgba(99,102,241,.18);
  border-radius:14px;padding:16px 18px;margin-bottom:10px}
.quote-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.quote-num{font-family:'Syne',sans-serif;font-size:1rem;font-weight:700;color:#a5b4fc}
.quote-client{font-size:.8rem;color:#64748b;margin-top:2px}
.quote-amt{font-family:'Syne',sans-serif;font-size:1.1rem;font-weight:800;color:#a5b4fc;text-align:right}
.q-tag{display:inline-block;padding:2px 9px;border-radius:20px;font-size:.69rem;font-weight:600;letter-spacing:.04em}
.q-open{background:rgba(99,102,241,.12);border:1px solid rgba(99,102,241,.25);color:#a5b4fc}
.q-accepted{background:rgba(52,211,153,.1);border:1px solid rgba(52,211,153,.22);color:#34d399}
.q-declined{background:rgba(248,113,113,.1);border:1px solid rgba(248,113,113,.22);color:#f87171}
.q-invoiced{background:rgba(251,191,36,.1);border:1px solid rgba(251,191,36,.22);color:#fbbf24}
.cf-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:16px 0}
.cf-card{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:16px;text-align:center}
.cf-card.pos{border-color:rgba(52,211,153,.2);background:rgba(52,211,153,.04)}
.cf-card.neg{border-color:rgba(248,113,113,.2);background:rgba(248,113,113,.04)}
.cf-lbl{font-size:.65rem;color:#334155;text-transform:uppercase;letter-spacing:.09em;font-weight:600;margin-bottom:6px}
.cf-val{font-family:'Syne',sans-serif;font-size:1.25rem;font-weight:800}
.cf-val.pos{color:#34d399}
.cf-val.neg{color:#f87171}
.cf-val.neu{color:#fbbf24}
.cf-sub{font-size:.7rem;color:#1e293b;margin-top:3px}
.cf-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.04)}
.cf-row:last-child{border-bottom:none}
.cf-row-name{font-size:.82rem;color:#94a3b8}
.cf-row-due{font-size:.72rem;color:#475569;margin-top:2px}
.cf-row-amt{font-family:'Syne',sans-serif;font-size:.9rem;font-weight:700;text-align:right}
.cf-section-hdr{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:#334155;padding:10px 0 4px;border-bottom:1px solid rgba(255,255,255,.06)}
.reminder-ok{background:rgba(52,211,153,.07);border:1px solid rgba(52,211,153,.2);border-radius:9px;padding:10px 14px;font-size:.83rem;color:#34d399;margin:6px 0}"""
inject_css(_APP_CSS)

# ==============================================
# APP
# ==============================================
uid=st.session_state.user_id; role=st.session_state.role; is_pro=st.session_state.is_pro
dname=st.session_state.full_name or st.session_state.username
run_command("UPDATE users SET last_active=? WHERE id=?",(datetime.now().isoformat(),uid))

if st.session_state.get('force_pw_change',0)==1:
    st.markdown("## Zmena hesla vyzadovana")
    with st.form("fpc"):
        np1=st.text_input("Nove heslo",type="password").strip(); np2=st.text_input("Potvrzeni",type="password").strip()
        if st.form_submit_button("Zmenint →",type="primary"):
            if np1 and np1==np2:
                run_command("UPDATE users SET password_hash=?,force_password_change=0 WHERE id=?",(hp(np1),uid))
                st.session_state.force_pw_change=0; st.success("Hotovo!"); st.rerun()
            else: st.error("Hesla se neshoduji.")
    st.stop()

bc="badge-pro" if is_pro else "badge-free"; bt="PRO" if is_pro else "FREE"
st.sidebar.markdown(f'<div class="sb-card"><div class="sb-name">{dname}</div><div class="sb-meta">{st.session_state.username}</div><span class="badge {bc}">{bt}</span></div>',unsafe_allow_html=True)
if st.sidebar.button("Odhlasit"): st.session_state.user_id=None; st.rerun()

# ----------------------------------------------
# ADMIN
# ----------------------------------------------
if role=='admin':
    st.markdown('<div class="sec-hdr"><div class="sec-ico">👑</div><div class="sec-title">Admin Dashboard</div></div>',unsafe_allow_html=True)

    uc   = run_query("SELECT COUNT(*) FROM users WHERE role!='admin'",single=True)['count'] or 0
    uc_pro = run_query("SELECT COUNT(*) FROM users WHERE role!='admin' AND license_valid_until >= %s",
                       (date.today().isoformat(),), single=True)['count'] or 0
    fc   = run_query("SELECT COUNT(*) FROM faktury",single=True)['count'] or 0
    fc_p = run_query("SELECT COUNT(*) FROM faktury WHERE uhrazeno=1",single=True)['count'] or 0
    tr   = run_query("SELECT SUM(castka_celkem) FROM faktury",single=True)['sum'] or 0
    tr_p = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE uhrazeno=1",single=True)['sum'] or 0
    tr_u = tr - tr_p
    ov   = run_query("SELECT COUNT(*),COALESCE(SUM(castka_celkem),0) FROM faktury WHERE uhrazeno=0 AND datum_splatnosti < %s",
                     (date.today().isoformat(),), single=True)
    ov_cnt = ov['count'] or 0
    ov_sum = ov['coalesce'] or 0
    new_7  = run_query("SELECT COUNT(*) FROM users WHERE created_at >= %s",
                       ((date.today()-timedelta(7)).isoformat(),), single=True)['count'] or 0
    fakt_30= run_query("SELECT COUNT(*),COALESCE(SUM(castka_celkem),0) FROM faktury WHERE datum_vystaveni >= %s",
                       ((date.today()-timedelta(30)).isoformat(),), single=True)
    f30_cnt= fakt_30['count'] or 0
    f30_sum= fakt_30['coalesce'] or 0

    st.markdown(f"""
<style>
.adm-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}}
.adm-card{{background:linear-gradient(135deg,#1e293b,#0f172a);border:1px solid rgba(99,102,241,.25);
  border-radius:14px;padding:16px 14px;text-align:center}}
.adm-card.green{{background:linear-gradient(135deg,#052e16,#064e3b);border-color:rgba(34,197,94,.3)}}
.adm-card.red{{background:linear-gradient(135deg,#450a0a,#7f1d1d);border-color:rgba(248,113,113,.3)}}
.adm-card.blue{{background:linear-gradient(135deg,#0c1a2e,#1e3a5f);border-color:rgba(96,165,250,.3)}}
.adm-card.amber{{background:linear-gradient(135deg,#1c1003,#451a03);border-color:rgba(251,191,36,.3)}}
.adm-val{{font-family:'Syne',sans-serif;font-size:1.55rem;font-weight:800;color:#f1f5f9;letter-spacing:-.02em}}
.adm-lbl{{font-size:.68rem;color:#64748b;text-transform:uppercase;letter-spacing:.1em;margin-top:4px}}
.adm-sub{{font-size:.75rem;color:#94a3b8;margin-top:2px}}
.adm-trend.up{{color:#4ade80;font-size:.72rem;margin-top:4px}}
.adm-trend.dn{{color:#f87171;font-size:.72rem;margin-top:4px}}
.activity-feed{{background:#0f172a;border:1px solid rgba(99,102,241,.2);border-radius:14px;padding:16px;margin-bottom:16px}}
.activity-item{{display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.05)}}
.activity-item:last-child{{border-bottom:none}}
.activity-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0}}
.activity-dot.new-user{{background:#60a5fa}}
.activity-dot.new-fak{{background:#4ade80}}
.activity-dot.overdue{{background:#f87171}}
.activity-text{{color:#cbd5e1;font-size:.82rem}}
.activity-time{{color:#475569;font-size:.72rem;margin-left:auto;white-space:nowrap}}
.health-bar-wrap{{background:#0f172a;border:1px solid rgba(99,102,241,.2);border-radius:14px;padding:16px;margin-bottom:16px}}
.health-row{{display:flex;align-items:center;gap:12px;margin-bottom:10px}}
.health-label{{color:#94a3b8;font-size:.8rem;width:130px;flex-shrink:0}}
.health-track{{flex:1;height:8px;background:#1e293b;border-radius:4px;overflow:hidden}}
.health-fill{{height:100%;border-radius:4px;transition:width .5s}}
.health-pct{{color:#f1f5f9;font-size:.8rem;font-weight:700;width:40px;text-align:right}}
.top-users{{background:#0f172a;border:1px solid rgba(99,102,241,.2);border-radius:14px;padding:16px;margin-bottom:16px}}
.tu-row{{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.05)}}
.tu-row:last-child{{border-bottom:none}}
.tu-rank{{font-family:'Syne',sans-serif;font-weight:800;font-size:1rem;color:#6366f1;width:24px}}
.tu-name{{flex:1;color:#e2e8f0;font-size:.85rem;font-weight:600}}
.tu-meta{{color:#64748b;font-size:.75rem}}
.tu-amt{{font-family:'Syne',sans-serif;font-weight:700;color:#4ade80;font-size:.9rem}}
</style>
<div class="adm-grid">
  <div class="adm-card blue">
    <div class="adm-val">{uc}</div>
    <div class="adm-lbl">Uzivatelu</div>
    <div class="adm-sub">{uc_pro} PRO | {uc-uc_pro} FREE</div>
    <div class="adm-trend up">+{new_7} za 7 dni</div>
  </div>
  <div class="adm-card green">
    <div class="adm-val">{tr_p:,.0f} Kc</div>
    <div class="adm-lbl">Uhrazeno celkem</div>
    <div class="adm-sub">{fc_p} faktur</div>
    <div class="adm-trend up">{(fc_p/fc*100) if fc else 0:.0f}% uspesnost</div>
  </div>
  <div class="adm-card red">
    <div class="adm-val">{tr_u:,.0f} Kc</div>
    <div class="adm-lbl">Neuhrazeno</div>
    <div class="adm-sub">{fc-fc_p} faktur ceka</div>
    <div class="adm-trend dn">{ov_cnt} po splatnosti</div>
  </div>
  <div class="adm-card amber">
    <div class="adm-val">{f30_sum:,.0f} Kc</div>
    <div class="adm-lbl">Obrat 30 dni</div>
    <div class="adm-sub">{f30_cnt} novych faktur</div>
    <div class="adm-trend up">avg {f30_sum/f30_cnt:,.0f} / fak</div>
  </div>
</div>""".replace("{f30_sum/f30_cnt:,.0f}", f"{f30_sum/f30_cnt:,.0f}" if f30_cnt else "0"), unsafe_allow_html=True)

    top_users = run_query("""
        SELECT u.username, u.full_name, u.email,
               COUNT(f.id) as faktur,
               COALESCE(SUM(f.castka_celkem),0) as obrat,
               COALESCE(SUM(CASE WHEN f.uhrazeno=1 THEN f.castka_celkem ELSE 0 END),0) as uhrazeno
        FROM users u LEFT JOIN faktury f ON u.id=f.user_id
        WHERE u.role!='admin'
        GROUP BY u.id,u.username,u.full_name,u.email
        ORDER BY obrat DESC LIMIT 8
    """)

    col_tl, col_tr = st.columns([1, 1])
    with col_tl:
        st.markdown("**🏆 Top uzivatele dle obratu**")
        if top_users:
            rows_html = ""
            for i, u in enumerate(top_users):
                u = dict(u)
                rows_html += f"""
<div class="tu-row">
  <div class="tu-rank">#{i+1}</div>
  <div>
    <div class="tu-name">{u.get('full_name') or u['username']}</div>
    <div class="tu-meta">{u['faktur']} faktur · {u['email'] or ''}</div>
  </div>
  <div class="tu-amt">{u['obrat']:,.0f} Kc</div>
</div>"""
            st.markdown(f'<div class="top-users">{rows_html}</div>', unsafe_allow_html=True)

    with col_tr:
        st.markdown("**📊 Zdravi systemu**")
        pay_rate = (fc_p/fc*100) if fc else 0
        pro_rate = (uc_pro/uc*100) if uc else 0
        active_rate_q = run_query("SELECT COUNT(*) FROM users WHERE role!='admin' AND last_active >= %s",
                                  ((date.today()-timedelta(30)).isoformat(),), single=True)
        active_30 = (active_rate_q['count'] or 0) if active_rate_q else 0
        active_rate = (active_30/uc*100) if uc else 0
        avg_inv_val = tr/fc if fc else 0
        avg_30 = f30_sum/f30_cnt if f30_cnt else 0
        momentum = min(100, (avg_30/avg_inv_val*100)) if avg_inv_val else 0

        def bar(label, pct, color):
            pct_s = min(100, max(0, pct))
            return f'<div class="health-row"><div class="health-label">{label}</div><div class="health-track"><div class="health-fill" style="width:{pct_s:.0f}%;background:{color}"></div></div><div class="health-pct">{pct_s:.0f}%</div></div>'

        st.markdown(f"""<div class="health-bar-wrap">
{bar("Platebni uspesnost", pay_rate, "#4ade80")}
{bar("PRO konverze", pro_rate, "#818cf8")}
{bar("Aktivni 30d", active_rate, "#60a5fa")}
{bar("Momentum (obrat)", momentum, "#fbbf24")}
</div>""", unsafe_allow_html=True)

    st.markdown("**⚡ Posledni aktivita**")
    recent_users = run_query("SELECT username,full_name,created_at FROM users WHERE role!='admin' ORDER BY id DESC LIMIT 3")
    recent_faks  = run_query("""SELECT f.cislo_full,f.castka_celkem,f.datum_vystaveni,k.jmeno,u.username
        FROM faktury f JOIN klienti k ON f.klient_id=k.id JOIN users u ON f.user_id=u.id
        ORDER BY f.id DESC LIMIT 4""")
    overdue_list = run_query("""SELECT f.cislo_full,f.datum_splatnosti,k.jmeno,u.username,f.castka_celkem
        FROM faktury f JOIN klienti k ON f.klient_id=k.id JOIN users u ON f.user_id=u.id
        WHERE f.uhrazeno=0 AND f.datum_splatnosti < %s ORDER BY f.datum_splatnosti ASC LIMIT 3""",
        (date.today().isoformat(),))

    act_items = ""
    for u in (recent_users or []):
        u=dict(u)
        act_items += f'<div class="activity-item"><div class="activity-dot new-user"></div><div class="activity-text">Novy uzivatel <b>{u.get("full_name") or u["username"]}</b> se registroval</div><div class="activity-time">{fmt_d(u.get("created_at",""))}</div></div>'
    for f in (recent_faks or []):
        f=dict(f)
        act_items += f'<div class="activity-item"><div class="activity-dot new-fak"></div><div class="activity-text">Faktura <b>{f.get("cislo_full","")}</b> ({f.get("jmeno","")}) — {f.get("castka_celkem",0):,.0f} Kc · uziv. <b>{f["username"]}</b></div><div class="activity-time">{fmt_d(f.get("datum_vystaveni",""))}</div></div>'
    for f in (overdue_list or []):
        f=dict(f)
        try: days_ov=(date.today()-datetime.strptime(str(f['datum_splatnosti'])[:10],'%Y-%m-%d').date()).days
        except: days_ov=0
        act_items += f'<div class="activity-item"><div class="activity-dot overdue"></div><div class="activity-text">⚠️ Po splatnosti: <b>{f.get("cislo_full","")}</b> ({f.get("jmeno","")}) — {f.get("castka_celkem",0):,.0f} Kc · {days_ov}d · uziv. {f["username"]}</div><div class="activity-time">{fmt_d(f.get("datum_splatnosti",""))}</div></div>'
    if act_items:
        st.markdown(f'<div class="activity-feed">{act_items}</div>', unsafe_allow_html=True)

    import plotly.graph_objects as go
    monthly = run_query("""
        SELECT SUBSTRING(datum_vystaveni,1,7) as mesic,
               COUNT(*) as faktur,
               COALESCE(SUM(castka_celkem),0) as obrat,
               COALESCE(SUM(CASE WHEN uhrazeno=1 THEN castka_celkem ELSE 0 END),0) as uhrazeno
        FROM faktury
        WHERE datum_vystaveni >= %s
        GROUP BY mesic ORDER BY mesic ASC LIMIT 12
    """, ((date.today()-timedelta(365)).isoformat(),))

    gcol1, gcol2 = st.columns(2)
    with gcol1:
        st.markdown("**📈 Mesicni obrat (12 mesicu)**")
        if monthly:
            df_m = pd.DataFrame([dict(r) for r in monthly])
            fig = go.Figure()
            fig.add_bar(x=df_m['mesic'], y=df_m['uhrazeno'], name='Uhrazeno', marker_color='#4ade80',
                        text=[f"{v:,.0f}" for v in df_m['uhrazeno']], textposition='inside', textfont=dict(size=9,color='white'))
            fig.add_bar(x=df_m['mesic'], y=df_m['obrat']-df_m['uhrazeno'], name='Neuhrazeno', marker_color='rgba(248,113,113,0.6)',
                        text=[f"{v:,.0f}" for v in df_m['obrat']-df_m['uhrazeno']], textposition='inside', textfont=dict(size=9,color='white'))
            fig.update_layout(barmode='stack', plot_bgcolor='#0f172a', paper_bgcolor='#0f172a',
                font=dict(color='#94a3b8',size=10), height=280, margin=dict(l=10,r=10,t=10,b=30),
                showlegend=True, legend=dict(orientation='h',y=1.08,x=0,font=dict(size=9)),
                xaxis=dict(gridcolor='#1e293b',tickfont=dict(size=9)),
                yaxis=dict(gridcolor='#1e293b',tickformat=',.0f'))
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("Zatim zadna data.")

    with gcol2:
        st.markdown("**🥧 Status faktur**")
        pie_paid = run_query("SELECT COUNT(*) FROM faktury WHERE uhrazeno=1",single=True)['count'] or 0
        pie_over = run_query("SELECT COUNT(*) FROM faktury WHERE uhrazeno=0 AND datum_splatnosti < %s",
                             (date.today().isoformat(),),single=True)['count'] or 0
        pie_pend = (fc - pie_paid - pie_over)
        if fc:
            fig2 = go.Figure(go.Pie(
                labels=['Uhrazeno','Ceka na platbu','Po splatnosti'],
                values=[pie_paid, max(0,pie_pend), pie_over],
                marker=dict(colors=['#4ade80','#60a5fa','#f87171']),
                textfont=dict(size=11,color='white'), hole=0.45))
            fig2.update_layout(plot_bgcolor='#0f172a', paper_bgcolor='#0f172a',
                font=dict(color='#94a3b8'), height=280, margin=dict(l=10,r=10,t=10,b=10),
                legend=dict(orientation='h',y=-0.1,font=dict(size=9)))
            st.plotly_chart(fig2, use_container_width=True)

    gcol3, gcol4 = st.columns(2)
    with gcol3:
        st.markdown("**👥 Registrace uzivatelu (12 mesicu)**")
        user_growth = run_query("""
            SELECT SUBSTRING(created_at,1,7) as mesic, COUNT(*) as novi
            FROM users WHERE role!='admin' AND created_at >= %s
            GROUP BY mesic ORDER BY mesic ASC
        """, ((date.today()-timedelta(365)).isoformat(),))
        if user_growth:
            df_ug = pd.DataFrame([dict(r) for r in user_growth])
            fig3 = go.Figure(go.Bar(x=df_ug['mesic'], y=df_ug['novi'],
                marker=dict(color='#818cf8',opacity=0.8),
                text=df_ug['novi'], textposition='outside', textfont=dict(size=10,color='#818cf8')))
            fig3.update_layout(plot_bgcolor='#0f172a', paper_bgcolor='#0f172a',
                font=dict(color='#94a3b8',size=10), height=240, margin=dict(l=10,r=10,t=10,b=30),
                xaxis=dict(gridcolor='#1e293b'), yaxis=dict(gridcolor='#1e293b'))
            st.plotly_chart(fig3, use_container_width=True)

    with gcol4:
        st.markdown("**🏆 Top 5 klientu dle obratu**")
        top_clients = run_query("""
            SELECT k.jmeno, COALESCE(SUM(f.castka_celkem),0) as obrat, COUNT(f.id) as faktur
            FROM klienti k JOIN faktury f ON k.id=f.klient_id
            GROUP BY k.id,k.jmeno ORDER BY obrat DESC LIMIT 5
        """)
        if top_clients:
            df_tc = pd.DataFrame([dict(r) for r in top_clients])
            fig4 = go.Figure(go.Bar(x=df_tc['obrat'], y=df_tc['jmeno'], orientation='h',
                marker=dict(color='#fbbf24',opacity=0.85),
                text=[f"{v:,.0f} Kc" for v in df_tc['obrat']], textposition='outside',
                textfont=dict(size=9,color='#fbbf24')))
            fig4.update_layout(plot_bgcolor='#0f172a', paper_bgcolor='#0f172a',
                font=dict(color='#94a3b8',size=10), height=240, margin=dict(l=10,r=10,t=10,b=10),
                xaxis=dict(gridcolor='#1e293b',tickformat=',.0f'), yaxis=dict(gridcolor='#1e293b'))
            st.plotly_chart(fig4, use_container_width=True)

    st.divider()
    tabs=st.tabs(["👥 Uzivatele","🔑 Klice","📧 Emailing","🛡️ System"])
    with tabs[0]:
        fk=run_query("SELECT * FROM licencni_klice WHERE pouzito_uzivatelem_id IS NULL ORDER BY id DESC")
        kd={f"{k['kod']} ({k['dny_platnosti']} dni)":k for k in fk}
        for u in run_query("SELECT * FROM users WHERE role!='admin' ORDER BY id DESC"):
            ed=u['license_valid_until']; act=False
            if ed:
                try:
                    if datetime.strptime(str(ed)[:10],'%Y-%m-%d').date()>=date.today(): act=True
                except: pass
            with st.expander(f"{'PRO' if act else 'FREE'} {u['username']} — {u['email']}"):
                c1,c2=st.columns(2)
                c1.write(f"**Jmeno:** {u['full_name']}"); c1.write(f"**Tel:** {u['phone']}"); c1.write(f"**Vytvoreno:** {fmt_d(u['created_at'])}")
                cv=date.today()
                if u['license_valid_until']:
                    try: cv=datetime.strptime(str(u['license_valid_until'])[:10],'%Y-%m-%d').date()
                    except: pass
                nv=c2.date_input("Platnost do:",value=cv,key=f"md_{u['id']}")
                if c2.button("Ulozit",key=f"bd_{u['id']}"): run_command("UPDATE users SET license_valid_until=? WHERE id=?",(nv,u['id'])); st.rerun()
                sk=c2.selectbox("Priradit klic",["-- Vyberte --"]+list(kd.keys()),key=f"sk_{u['id']}")
                if c2.button("Aktivovat",key=f"btn_{u['id']}"):
                    if sk!="-- Vyberte --":
                        kdata=kd[sk]; ne=date.today()+timedelta(days=kdata['dny_platnosti'])
                        run_command("UPDATE users SET license_key=?,license_valid_until=? WHERE id=?",(kdata['kod'],ne,u['id']))
                        run_command("UPDATE licencni_klice SET pouzito_uzivatelem_id=? WHERE id=?",(u['id'],kdata['id'])); st.rerun()
                if st.button("Smazat",key=f"del_{u['id']}",type="primary"): run_command("DELETE FROM users WHERE id=?",(u['id'],)); st.rerun()
    with tabs[1]:
        c1,c2=st.columns(2); dv=c1.number_input("Platnost (dny)",value=365,min_value=1); nv=c2.text_input("Poznamka")
        if st.button("Vygenerovat klic"):
            k=gen_lic(); run_command("INSERT INTO licencni_klice (kod,dny_platnosti,vygenerovano,poznamka) VALUES (?,?,?,?)",(k,dv,datetime.now().isoformat(),nv)); st.success(f"`{k}`")
        for k in run_query("SELECT * FROM licencni_klice ORDER BY id DESC"):
            st.code(f"{k['kod']} | {k['dny_platnosti']} dni | {'pouzito' if k['pouzito_uzivatelem_id'] else 'volny'} | {k['poznamka']}")
    with tabs[2]:
        tpl=run_query("SELECT * FROM email_templates WHERE name='welcome'",single=True); td=dict(tpl) if tpl else {}
        with st.form("wm"):
            ws=st.text_input("Predmet",value=td.get('subject','')); wb=st.text_area("Text ({name})",value=td.get('body',''),height=150)
            if st.form_submit_button("Ulozit"):
                run_command("INSERT INTO email_templates (name,subject,body) VALUES ('welcome',?,?) ON CONFLICT (name) DO UPDATE SET subject=EXCLUDED.subject,body=EXCLUDED.body",(ws,wb)); st.success("OK")
        with st.form("mm"):
            ms=st.text_input("Predmet"); mb=st.text_area("Zprava",height=120)
            if st.form_submit_button("Odeslat vsem"):
                cnt=sum(1 for u in run_query("SELECT email FROM users WHERE role!='admin' AND email IS NOT NULL") if send_mail(u['email'],ms,mb))
                st.success(f"Odeslano: {cnt}")
    with tabs[3]:
        st.markdown("**🛡️ System Info**")
        c1, c2 = st.columns(2)
        db_size = run_query("SELECT pg_size_pretty(pg_database_size(current_database())) as size", single=True)
        tbl_counts = {}
        for tbl in ['users','faktury','klienti','kategorie','faktura_polozky','vydaje','casovac','nabidky']:
            r = run_query(f"SELECT COUNT(*) FROM {tbl}", single=True)
            tbl_counts[tbl] = r['count'] if r else 0
        c1.metric("Velikost DB", db_size['size'] if db_size else "N/A")
        c1.metric("Celkem faktur", tbl_counts['faktury'])
        c1.metric("Celkem klientu", tbl_counts['klienti'])
        c1.metric("Polozek faktury", tbl_counts['faktura_polozky'])
        c2.metric("Uzivatelu", tbl_counts['users'])
        c2.metric("Kategorii", tbl_counts['kategorie'])
        c2.metric("Vydaju", tbl_counts['vydaje'])
        c2.metric("Nabidek", tbl_counts['nabidky'])
        st.divider()
        st.markdown("**Nebezpecne operace**")
        st.warning("Nasledujici akce jsou nevratne!")
        if st.button("🗑️ Smazat vsechny PDF cache"):
            cached_pdf.clear(); cached_isdoc.clear(); st.success("Cache vycistena.")
        exp_u = st.text_input("Smazat uzivatele (login)", placeholder="username")
        if st.button("Smazat uzivatele trvale", type="primary"):
            if exp_u and exp_u != 'admin':
                u_del = run_query("SELECT id FROM users WHERE username=?",(exp_u,),True)
                if u_del:
                    run_command("DELETE FROM faktury WHERE user_id=?",(u_del['id'],))
                    run_command("DELETE FROM klienti WHERE user_id=?",(u_del['id'],))
                    run_command("DELETE FROM kategorie WHERE user_id=?",(u_del['id'],))
                    run_command("DELETE FROM nastaveni WHERE user_id=?",(u_del['id'],))
                    run_command("DELETE FROM users WHERE id=?",(u_del['id'],))
                    st.success(f"Uzivatel {exp_u} smazan vcetne vsech dat.")
                else: st.error("Uzivatel nenalezen.")

# ----------------------------------------------
# USER MENU
# ----------------------------------------------
else:
    menu=st.sidebar.radio(" ",["Faktury","Nabidky","Cashflow","Casovac","Opakovane","Dashboard","Dane","Vydaje","Klienti","Kategorie","Nastaveni"])

    # ================================
    # FAKTURY
    # ================================
    if "Faktury" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">📄</div><div class="sec-title">Faktury</div></div>',unsafe_allow_html=True)

        overdue=run_query("SELECT f.id,f.cislo_full,f.datum_splatnosti,f.castka_celkem,k.jmeno FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND f.uhrazeno=0 AND f.datum_splatnosti < ? ORDER BY f.datum_splatnosti ASC",(uid,date.today().isoformat()))
        if overdue:
            tot_ov=sum(r['castka_celkem'] for r in overdue)
            rows=""
            for r in overdue:
                try: dl=(date.today()-datetime.strptime(str(r['datum_splatnosti'])[:10],'%Y-%m-%d').date()).days; dlt=f"{dl} dni po splatnosti"
                except: dlt="po splatnosti"
                rows+=f'<div class="overdue-row"><div><div class="overdue-name">{r["jmeno"]} <span style="color:#334155;font-size:.75rem">{r.get("cislo_full","")}</span></div><div class="overdue-detail">Splatnost: {fmt_d(r["datum_splatnosti"])}</div></div><div><div class="overdue-amount">{r["castka_celkem"]:,.0f} Kc</div><div class="overdue-days">{dlt}</div></div></div>'
            st.markdown(f'<div class="overdue-panel"><div class="overdue-header"><span>⚠️</span><span class="overdue-title">Pohledavky po splatnosti</span><span class="overdue-count">{len(overdue)}</span><span style="margin-left:auto;font-family:Syne,sans-serif;font-weight:800;color:#f87171">{tot_ov:,.0f} Kc</span></div>{rows}</div>',unsafe_allow_html=True)

        years=[r['substring'] for r in run_query("SELECT DISTINCT SUBSTRING(datum_vystaveni,1,4) as substring FROM faktury WHERE user_id=?",(uid,))]
        if str(datetime.now().year) not in years: years.append(str(datetime.now().year))
        sy=st.selectbox("Rok",sorted(list(set(years)),reverse=True),label_visibility="collapsed")
        sc_y=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND SUBSTRING(datum_vystaveni,1,4)=?",(uid,sy),True)['sum'] or 0
        sc_a=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?",(uid,),True)['sum'] or 0
        su_a=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0",(uid,),True)['sum'] or 0
        st.markdown(f'<div class="stats-row"><div class="sc g"><div class="sc-lbl">Obrat {sy}</div><div class="sc-val g">{sc_y:,.0f}</div><div class="sc-sub">Kc</div></div><div class="sc a"><div class="sc-lbl">Celkem</div><div class="sc-val a">{sc_a:,.0f}</div><div class="sc-sub">Kc</div></div><div class="sc r"><div class="sc-lbl">Neuhrazeno</div><div class="sc-val r">{su_a:,.0f}</div><div class="sc-sub">Kc</div></div></div>',unsafe_allow_html=True)

        sablony=run_query("SELECT * FROM item_sablony WHERE user_id=?",(uid,))
        if sablony:
            chips="".join(f'<span class="tpl-chip" title="Kliknete pro pridani"><b>{s["nazev"]}</b><span class="price">{s["cena"]:,.0f} Kc</span></span>' for s in sablony)
            st.markdown(f'<div class="callout">Ulozene sablony polozek: <span>kliknete v editoru nebo pridejte rucne</span></div><div class="tpl-grid">{chips}</div>',unsafe_allow_html=True)

        with st.expander("Nova faktura"):
            pp=get_pool(); conn=pp.getconn()
            try:
                kli=pd.read_sql("SELECT id,jmeno FROM klienti WHERE user_id=%s",conn,params=(uid,))
                kat=pd.read_sql("SELECT id,nazev FROM kategorie WHERE user_id=%s",conn,params=(uid,))
            finally: pp.putconn(conn)
            if kli.empty: st.warning("Nejprve pridejte klienta.")
            elif not is_pro and kat.empty:
                run_command("INSERT INTO kategorie (user_id,nazev,prefix,aktualni_cislo,barva) VALUES (?,'Obecna','FV',1,'#1e3a5f')",(uid,)); cached_pdf.clear(); st.rerun()
            else:
                rid=st.session_state.form_reset_id; c1,c2=st.columns(2)
                sk=c1.selectbox("Klient",kli['jmeno'],key=f"k_{rid}"); sc2=c2.selectbox("Kategorie",kat['nazev'],key=f"c_{rid}")
                if not kli[kli['jmeno']==sk].empty and not kat[kat['nazev']==sc2].empty:
                    kid=int(kli[kli['jmeno']==sk]['id'].values[0]); cid=int(kat[kat['nazev']==sc2]['id'].values[0])
                    _,full,_=next_num(cid,uid)
                    st.markdown(f'<div class="callout">Cislo dokladu: <span>{full}</span></div>',unsafe_allow_html=True)
                    d1,d2=st.columns(2); dv=d1.date_input("Vystaveni",date.today(),key=f"dv_{rid}"); ds=d2.date_input("Splatnost",date.today()+timedelta(14),key=f"ds_{rid}")
                    ut=st.text_input("Uvodni text","Fakturujeme Vam:",key=f"ut_{rid}")
                    ed=st.data_editor(st.session_state.items_df,num_rows="dynamic",use_container_width=True,key=f"ed_{rid}")
                    total=float(pd.to_numeric(ed["Cena"],errors='coerce').fillna(0).sum()) if not ed.empty and "Cena" in ed.columns else 0.0
                    st.markdown(f'<div class="total-ln"><span class="total-lbl">Celkem k uhrade</span><span class="total-amt">{total:,.2f} Kc</span></div>',unsafe_allow_html=True)

                    if st.button("Vystavit fakturu →",type="primary",key=f"vystavit_{rid}"):
                        fid=run_command("INSERT INTO faktury (user_id,cislo_full,klient_id,kategorie_id,datum_vystaveni,datum_splatnosti,castka_celkem,variabilni_symbol,uvodni_text) VALUES (?,?,?,?,?,?,?,?,?)",(uid,full,kid,cid,dv,ds,total,re.sub(r"\D","",full),ut))
                        for _,row in ed.iterrows():
                            if row.get("Popis polozky"): run_command("INSERT INTO faktura_polozky (faktura_id,nazev,cena) VALUES (?,?,?)",(fid,row["Popis polozky"],float(row.get("Cena",0))))
                        run_command("UPDATE kategorie SET aktualni_cislo=aktualni_cislo+1 WHERE id=?",(cid,))
                        reset_forms(); cached_pdf.clear(); cached_isdoc.clear()
                        st.session_state['last_invoice_id'] = fid
                        st.session_state['last_invoice_full'] = full
                        st.rerun()

                if st.session_state.get('last_invoice_id'):
                    last_fid = st.session_state['last_invoice_id']
                    last_full = st.session_state['last_invoice_full']
                    pdf_out = cached_pdf(last_fid, uid, is_pro, f"new_{last_fid}")
                    if isinstance(pdf_out, bytes):
                        st.success(f"Faktura {last_full} byla uspesne vystavena!")
                        st.download_button("Stahnout PDF ihned", pdf_out, f"{last_full}.pdf", "application/pdf")
                    else:
                        st.error(f"Chyba PDF: {pdf_out}")
                    if st.button("Skryt zpravu"):
                        del st.session_state['last_invoice_id']
                        del st.session_state['last_invoice_full']
                        st.rerun()

        st.markdown("<br>",unsafe_allow_html=True)
        fc1,fc2=st.columns(2)
        sel_cli=fc1.selectbox("Klient",["Vsichni"]+[c['jmeno'] for c in run_query("SELECT jmeno FROM klienti WHERE user_id=?",(uid,))])
        db_yrs=[y['substring'] for y in run_query("SELECT DISTINCT SUBSTRING(datum_vystaveni,1,4) as substring FROM faktury WHERE user_id=?",(uid,))]
        sel_yr=fc2.selectbox("Rok",["Vsechny"]+sorted(db_yrs,reverse=True))
        if sel_cli!="Vsichni":
            ca=run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=?",(uid,sel_cli),True)['sum'] or 0
            cd=run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=? AND f.uhrazeno=0",(uid,sel_cli),True)['sum'] or 0
            cy=0
            if sel_yr!="Vsechny": cy=run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=? AND SUBSTRING(f.datum_vystaveni,1,4)=?",(uid,sel_cli,sel_yr),True)['sum'] or 0
            st.markdown(f'<div class="mini-row"><div class="mini-sc"><div class="mini-lbl">Historie</div><div class="mini-val">{ca:,.0f} Kc</div></div><div class="mini-sc"><div class="mini-lbl">Obrat</div><div class="mini-val g">{cy:,.0f} Kc</div></div><div class="mini-sc"><div class="mini-lbl">Dluzi</div><div class="mini-val r">{cd:,.0f} Kc</div></div></div>',unsafe_allow_html=True)

        search_q=st.text_input("Hledat fakturu…",placeholder="cislo, klient, popis",label_visibility="collapsed")
        q="SELECT f.*,k.jmeno FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=%s"; ps=[uid]
        if sel_cli!="Vsichni": q+=" AND k.jmeno=%s"; ps.append(sel_cli)
        if sel_yr!="Vsechny": q+=" AND SUBSTRING(f.datum_vystaveni,1,4)=%s"; ps.append(sel_yr)
        pp=get_pool(); conn=pp.getconn()
        try: df_f=pd.read_sql(q+" ORDER BY f.id DESC LIMIT 30",conn,params=ps)
        finally: pp.putconn(conn)
        if search_q:
            sq=search_q.lower()
            df_f=df_f[df_f['jmeno'].str.lower().str.contains(sq,na=False)|df_f['cislo_full'].str.lower().str.contains(sq,na=False)|df_f['muj_popis'].fillna('').str.lower().str.contains(sq,na=False)]
        if df_f.empty: st.info("Zadne faktury.")

        for row in df_f.to_dict('records'):
            cf=row.get('cislo_full') or f"F{row['id']}"; paid=row['uhrazeno']
            is_ov=False
            try:
                if not paid and datetime.strptime(str(row['datum_splatnosti'])[:10],'%Y-%m-%d').date()<date.today(): is_ov=True
            except: pass
            tag='<span class="tag-paid">Zaplaceno</span>' if paid else ('<span class="tag-overdue">Po splatnosti</span>' if is_ov else '<span class="tag-due">Ceka na platbu</span>')
            with st.expander(f"{'ok' if paid else ('!' if is_ov else '…')}  {cf}  ·  {row['jmeno']}  ·  {row['castka_celkem']:,.0f} Kc"):
                st.markdown(f"<div style='margin-bottom:12px'>{tag} &nbsp; <span style='color:#334155;font-size:.78rem'>Splatnost: {fmt_d(row.get('datum_splatnosti',''))}</span></div>",unsafe_allow_html=True)
                c1,c2,c3=st.columns(3)
                if paid:
                    if c1.button("Zrusit",key=f"u0_{row['id']}"): run_command("UPDATE faktury SET uhrazeno=0 WHERE id=?",(row['id'],)); cached_pdf.clear(); cached_isdoc.clear(); st.rerun()
                else:
                    if c1.button("Zaplaceno",key=f"u1_{row['id']}"): run_command("UPDATE faktury SET uhrazeno=1 WHERE id=?",(row['id'],)); cached_pdf.clear(); cached_isdoc.clear(); st.rerun()

                rh=str(row); pdf_out=cached_pdf(row['id'],uid,is_pro,rh)
                if isinstance(pdf_out, bytes):
                    c2.download_button("Stahnout PDF", pdf_out, f"{cf}.pdf", "application/pdf", key=f"pdf_{row['id']}", type="primary")
                else:
                    c2.error(f"Nelze vygenerovat: {pdf_out}")

                if is_pro:
                    isdoc_b=cached_isdoc(row['id'],uid,rh)
                    if isdoc_b: c2.download_button("ISDOC",isdoc_b,f"{cf}.isdoc","application/xml",key=f"isd_{row['id']}")
                klient_info=run_query("SELECT email,jmeno FROM klienti WHERE id=?",(row['klient_id'],),single=True)
                klient_email=dict(klient_info).get('email','') if klient_info else ''
                if not paid and klient_email:
                    if c2.button("Upominka",key=f"rem_{row['id']}"):
                        body=(f"Dobry den,\n\nDovolujeme si Vas upomenout o neuhradenou fakturu c. {cf}\n"
                              f"Castka: {row['castka_celkem']:,.0f} Kc\nSplatnost: {fmt_d(row['datum_splatnosti'])}\n\nProsime o uhrazeni.")
                        if send_mail(klient_email,f"Upominka platby – Faktura {cf}",body,pdf_out if isinstance(pdf_out,bytes) else None,f"{cf}.pdf"):
                            st.markdown('<div class="reminder-ok">Upominka odeslana na ' + klient_email + '</div>',unsafe_allow_html=True)
                        else:
                            st.warning("Nepodarilo se odeslat — zkontrolujte SMTP v Nastaveni.")
                ekey=f"edit_f_{row['id']}"
                if ekey not in st.session_state: st.session_state[ekey]=False
                if c3.button("Upravit",key=f"be_{row['id']}"): st.session_state[ekey]=True; st.rerun()
                if st.session_state[ekey]:
                    with st.form(f"fe_{row['id']}"):
                        nd=st.date_input("Splatnost",pd.to_datetime(row['datum_splatnosti'])); nm=st.text_input("Popis",row['muj_popis'] or ""); nut=st.text_input("Uvodni text",row['uvodni_text'] or "")
                        pp2=get_pool(); conn2=pp2.getconn()
                        try: ci=pd.read_sql('SELECT nazev as "Popis polozky",cena as "Cena" FROM faktura_polozky WHERE faktura_id=%s',conn2,params=(row['id'],))
                        finally: pp2.putconn(conn2)
                        ned=st.data_editor(ci,num_rows="dynamic",use_container_width=True)
                        if st.form_submit_button("Ulozit zmeny"):
                            nt=float(pd.to_numeric(ned["Cena"],errors='coerce').fillna(0).sum())
                            run_command("UPDATE faktury SET datum_splatnosti=?,muj_popis=?,castka_celkem=?,uvodni_text=? WHERE id=?",(nd,nm,nt,nut,row['id']))
                            run_command("DELETE FROM faktura_polozky WHERE faktura_id=?",(row['id'],))
                            for _,rw in ned.iterrows():
                                if rw.get("Popis polozky"): run_command("INSERT INTO faktura_polozky (faktura_id,nazev,cena) VALUES (?,?,?)",(row['id'],rw["Popis polozky"],float(rw.get("Cena",0))))
                            st.session_state[ekey]=False; cached_pdf.clear(); cached_isdoc.clear(); st.rerun()
                if c3.button("Duplikovat",key=f"dup_{row['id']}"):
                    nn,nf,_=next_num(row['kategorie_id'],uid)
                    nfid=run_command("INSERT INTO faktury (user_id,cislo,cislo_full,klient_id,kategorie_id,datum_vystaveni,datum_splatnosti,castka_celkem,variabilni_symbol,uvodni_text,muj_popis) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(uid,nn,nf,row['klient_id'],row['kategorie_id'],date.today(),date.today()+timedelta(14),row['castka_celkem'],re.sub(r"\D","",nf),row['uvodni_text'],row['muj_popis']))
                    for it in run_query("SELECT * FROM faktura_polozky WHERE faktura_id=?",(row['id'],)): run_command("INSERT INTO faktura_polozky (faktura_id,nazev,cena) VALUES (?,?,?)",(nfid,it['nazev'],it['cena']))
                    run_command("UPDATE kategorie SET aktualni_cislo=aktualni_cislo+1 WHERE id=?",(row['kategorie_id'],)); cached_pdf.clear(); cached_isdoc.clear(); st.success(f"Duplikat {nf} vytvoren!"); st.rerun()
                if st.button("Smazat",key=f"del_f_{row['id']}"): run_command("DELETE FROM faktury WHERE id=?",(row['id'],)); cached_pdf.clear(); cached_isdoc.clear(); st.rerun()

    # ================================
    # NABÍDKY
    # ================================
    elif "Nabidky" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">📋</div><div class="sec-title">Cenove nabidky</div></div>',unsafe_allow_html=True)
        st.markdown("Vytvorte nezavaznou nabidku — klient ji prijme a vy ji jednim kliknutim prevedete na fakturu.")

        with st.expander("Nova cenova nabidka"):
            pp_db=get_pool(); conn_db=pp_db.getconn()
            try:
                kli=pd.read_sql("SELECT id,jmeno FROM klienti WHERE user_id=%s",conn_db,params=(uid,))
                kat=pd.read_sql("SELECT id,nazev FROM kategorie WHERE user_id=%s",conn_db,params=(uid,))
            finally: pp_db.putconn(conn_db)
            if kli.empty: st.warning("Nejprve pridejte klienta.")
            else:
                with st.form("nab_form"):
                    c1,c2=st.columns(2)
                    nab_kl=c1.selectbox("Klient",kli['jmeno'],key="nab_kl")
                    nab_kat="Obecna"
                    if not kat.empty: nab_kat=c2.selectbox("Kategorie",kat['nazev'],key="nab_kat")
                    c3,c4=st.columns(2)
                    nab_dv=c3.date_input("Datum vystaveni",date.today(),key="nab_dv")
                    nab_pl=c4.date_input("Platnost nabidky do",date.today()+timedelta(30),key="nab_pl")
                    nab_txt=st.text_input("Uvodni text","Nabizime Vam nase sluzby za nasledujicich podminek:")
                    nab_poz=st.text_input("Interni poznamka","")
                    nab_items=st.data_editor(pd.DataFrame(columns=["Popis polozky","Cena"]),num_rows="dynamic",use_container_width=True,key="nab_items_ed")
                    if st.form_submit_button("Ulozit nabidku"):
                        if not kli[kli['jmeno']==nab_kl].empty:
                            nkid=int(kli[kli['jmeno']==nab_kl]['id'].values[0])
                            ncid=int(kat[kat['nazev']==nab_kat]['id'].values[0]) if not kat.empty else None
                            _,nfull,_=next_num(ncid,uid) if ncid else (1,"NAB-"+str(date.today().year)+"-"+str(random.randint(100,999)),"")
                            ntotal=float(pd.to_numeric(nab_items["Cena"],errors='coerce').fillna(0).sum()) if not nab_items.empty else 0.0
                            nab_id=run_command("INSERT INTO nabidky (user_id,cislo_full,klient_id,kategorie_id,datum_vystaveni,datum_platnosti,castka_celkem,uvodni_text,poznamka,stav) VALUES (?,?,?,?,?,?,?,?,?,'otevrena')",
                                              (uid,nfull.replace("FV","NAB"),nkid,ncid,nab_dv,nab_pl,ntotal,nab_txt,nab_poz))
                            if not nab_items.empty:
                                for _,r2 in nab_items.iterrows():
                                    if r2.get("Popis polozky"): run_command("INSERT INTO nabidka_polozky (nabidka_id,nazev,cena) VALUES (?,?,?)",(nab_id,r2["Popis polozky"],float(r2.get("Cena",0))))
                            st.success(f"Nabidka {nfull.replace('FV','NAB')} ulozena!"); st.rerun()

        st.divider()
        nabs=run_query("SELECT n.*,k.jmeno FROM nabidky n JOIN klienti k ON n.klient_id=k.id WHERE n.user_id=? ORDER BY n.id DESC",(uid,))
        stav_map={"otevrena":("o","Otevrena","q-open"),"prijata":("ok","Prijata","q-accepted"),"odmitnuta":("x","Odmitnuta","q-declined"),"fakturovana":("f","Fakturovana","q-invoiced")}
        if not nabs:
            st.info("Zatim zadne nabidky.")
        for nb in nabs:
            nb=dict(nb)
            ico_s,lbl_s,cls_s=stav_map.get(nb.get('stav','otevrena'),("o","?","q-open"))
            expired=""
            try:
                if datetime.strptime(str(nb['datum_platnosti'])[:10],'%Y-%m-%d').date()<date.today() and nb.get('stav')=='otevrena':
                    expired=' <span style="color:#f87171;font-size:.7rem">· Vyprsela</span>'
            except: pass
            st.markdown(f"""
<div class="quote-card">
  <div class="quote-header">
    <div>
      <div class="quote-num">{nb.get('cislo_full','')} &nbsp; <span class="q-tag {cls_s}">{lbl_s}</span>{expired}</div>
      <div class="quote-client">{nb['jmeno']} &nbsp;·&nbsp; Platnost do: {fmt_d(nb.get('datum_platnosti',''))}</div>
    </div>
    <div class="quote-amt">{nb.get('castka_celkem',0):,.0f} Kc</div>
  </div>
</div>""",unsafe_allow_html=True)
            with st.expander(f"  Detaily nabidky {nb.get('cislo_full','')}"):
                c1,c2,c3,c4=st.columns(4)
                new_stav=c1.selectbox("Stav",["otevrena","prijata","odmitnuta"],format_func=lambda x:{"otevrena":"Otevrena","prijata":"Prijata","odmitnuta":"Odmitnuta","fakturovana":"Fakturovana"}[x],index=["otevrena","prijata","odmitnuta"].index(nb.get('stav','otevrena')) if nb.get('stav') in ["otevrena","prijata","odmitnuta"] else 0,key=f"nst_{nb['id']}")
                if c2.button("Ulozit stav",key=f"nst_save_{nb['id']}"): run_command("UPDATE nabidky SET stav=? WHERE id=?",(new_stav,nb['id'])); st.rerun()
                if nb.get('stav') in ('otevrena','prijata') and not nb.get('faktura_id'):
                    if c3.button("Prevest na fakturu",key=f"nab2fak_{nb['id']}",type="primary"):
                        kat_all=run_query("SELECT * FROM kategorie WHERE user_id=?",(uid,))
                        ncid_f=nb.get('kategorie_id')
                        if not ncid_f and kat_all: ncid_f=kat_all[0]['id']
                        if ncid_f:
                            _,fnum,_=next_num(ncid_f,uid)
                            n_items=run_query("SELECT * FROM nabidka_polozky WHERE nabidka_id=?",(nb['id'],)) or []
                            n_total=sum(float(it.get('cena',0)) for it in n_items)
                            new_fid=run_command("INSERT INTO faktury (user_id,cislo_full,klient_id,kategorie_id,datum_vystaveni,datum_splatnosti,castka_celkem,variabilni_symbol,uvodni_text) VALUES (?,?,?,?,?,?,?,?,?)",
                                               (uid,fnum,nb['klient_id'],ncid_f,date.today(),date.today()+timedelta(14),n_total,re.sub(r"\D","",fnum),nb.get('uvodni_text','')))
                            for it in n_items: run_command("INSERT INTO faktura_polozky (faktura_id,nazev,cena) VALUES (?,?,?)",(new_fid,it['nazev'],it['cena']))
                            run_command("UPDATE kategorie SET aktualni_cislo=aktualni_cislo+1 WHERE id=?",(ncid_f,))
                            run_command("UPDATE nabidky SET stav='fakturovana',faktura_id=? WHERE id=?",(new_fid,nb['id']))
                            cached_pdf.clear(); st.success(f"Faktura {fnum} vystavena!"); st.rerun()
                elif nb.get('faktura_id'):
                    c3.info(f"Faktura #{nb['faktura_id']}")
                if c4.button("Smazat",key=f"del_nab_{nb['id']}"): run_command("DELETE FROM nabidky WHERE id=?",(nb['id'],)); run_command("DELETE FROM nabidka_polozky WHERE nabidka_id=?",(nb['id'],)); st.rerun()
                nab_its=run_query("SELECT * FROM nabidka_polozky WHERE nabidka_id=?",(nb['id'],)) or []
                if nab_its:
                    for it in nab_its: st.markdown(f"- {it['nazev']} — **{it['cena']:,.0f} Kc**")
                if nb.get('poznamka'): st.caption(f"Poznamka: {nb['poznamka']}")

    # ================================
    # CASHFLOW
    # ================================
    elif "Cashflow" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">💰</div><div class="sec-title">Cashflow & Prognoza</div></div>',unsafe_allow_html=True)
        today = date.today()
        inc_30=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0 AND datum_splatnosti BETWEEN ? AND ?",(uid,today.isoformat(),(today+timedelta(30)).isoformat()),True)['sum'] or 0
        inc_60=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0 AND datum_splatnosti BETWEEN ? AND ?",(uid,(today+timedelta(31)).isoformat(),(today+timedelta(60)).isoformat()),True)['sum'] or 0
        inc_90=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0 AND datum_splatnosti BETWEEN ? AND ?",(uid,(today+timedelta(61)).isoformat(),(today+timedelta(90)).isoformat()),True)['sum'] or 0
        overdue_cf=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0 AND datum_splatnosti < ?",(uid,today.isoformat()),True)['sum'] or 0
        paid_month=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=1 AND SUBSTRING(datum_splatnosti,1,7)=?",(uid,today.strftime('%Y-%m')),True)['sum'] or 0
        st.markdown(f"""
<div class="cf-grid">
  <div class="cf-card neg"><div class="cf-lbl">Po splatnosti</div><div class="cf-val neg">{overdue_cf:,.0f} Kc</div><div class="cf-sub">okamzite splatne</div></div>
  <div class="cf-card pos"><div class="cf-lbl">Zaplaceno tento mesic</div><div class="cf-val pos">{paid_month:,.0f} Kc</div><div class="cf-sub">{today.strftime('%B %Y')}</div></div>
  <div class="cf-card"><div class="cf-lbl">Vyhled 90 dni</div><div class="cf-val neu">{inc_30+inc_60+inc_90:,.0f} Kc</div><div class="cf-sub">ocekavane prijmy</div></div>
</div>""",unsafe_allow_html=True)
        st.divider()
        tab30,tab60,tab90=st.tabs([f"  30 dni  ({inc_30:,.0f} Kc)",f"  31-60 dni  ({inc_60:,.0f} Kc)",f"  61-90 dni  ({inc_90:,.0f} Kc)"])
        def render_cf_tab(d_from, d_to):
            rows=run_query("SELECT f.castka_celkem,f.datum_splatnosti,f.cislo_full,k.jmeno FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND f.uhrazeno=0 AND f.datum_splatnosti BETWEEN ? AND ? ORDER BY f.datum_splatnosti ASC",(uid,d_from.isoformat(),d_to.isoformat()))
            if not rows: st.info("Zadne faktury v tomto obdobi."); return
            for r in rows:
                r=dict(r)
                try: dl=(datetime.strptime(str(r['datum_splatnosti'])[:10],'%Y-%m-%d').date()-today).days; dtxt=f"za {dl} dni"
                except: dtxt=""
                st.markdown(f'<div class="cf-row"><div><div class="cf-row-name">{r["jmeno"]} &nbsp; <span style="color:#334155">{r.get("cislo_full","")}</span></div><div class="cf-row-due">Splatnost: {fmt_d(r["datum_splatnosti"])} ({dtxt})</div></div><div class="cf-row-amt" style="color:#34d399">{r["castka_celkem"]:,.0f} Kc</div></div>',unsafe_allow_html=True)
        with tab30: render_cf_tab(today, today+timedelta(30))
        with tab60: render_cf_tab(today+timedelta(31), today+timedelta(60))
        with tab90: render_cf_tab(today+timedelta(61), today+timedelta(90))
        st.divider()
        st.subheader("Prijmy za poslednich 6 mesicu")
        pp_db=get_pool(); conn_db=pp_db.getconn()
        try:
            df_cf=pd.read_sql("SELECT datum_vystaveni, castka_celkem, uhrazeno FROM faktury WHERE user_id=%s AND datum_vystaveni >= %s",conn_db,params=(uid,(today.replace(day=1)-timedelta(days=150)).isoformat()))
        finally: pp_db.putconn(conn_db)
        if not df_cf.empty:
            df_cf['dt']=pd.to_datetime(df_cf['datum_vystaveni'])
            df_paid=df_cf[df_cf['uhrazeno']==1].groupby(df_cf['dt'].dt.to_period('M'))['castka_celkem'].sum()
            df_issued=df_cf.groupby(df_cf['dt'].dt.to_period('M'))['castka_celkem'].sum()
            chart_df=pd.DataFrame({'Uhrazeno':df_paid,'Vystaveno':df_issued}).fillna(0)
            chart_df.index=chart_df.index.astype(str)
            st.bar_chart(chart_df)
        else: st.info("Zadna data k zobrazeni.")
        st.divider()
        st.subheader("Pridejte planovany vydaj")
        with st.form("cf_vydaj"):
            c1,c2,c3=st.columns(3)
            cv_d=c1.date_input("Datum",today+timedelta(30)); cv_p=c2.text_input("Popis"); cv_a=c3.number_input("Castka",min_value=0.0,step=100.0)
            cv_k=st.selectbox("Kategorie",["Provoz","Material","Sluzby","Ostatni"])
            if st.form_submit_button("Pridat vydaj"):
                run_command("INSERT INTO vydaje (user_id,datum,popis,castka,kategorie) VALUES (?,?,?,?,?)",(uid,cv_d,cv_p,cv_a,cv_k)); st.success("Ulozeno"); st.rerun()

    # ================================
    # ČASOVAČ
    # ================================
    elif "Casovac" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">⏱️</div><div class="sec-title">Casovac hodin</div></div>',unsafe_allow_html=True)
        st.markdown('<div class="timer-card">',unsafe_allow_html=True)
        if st.session_state.timer_start is None:
            c1,c2=st.columns(2)
            proj=c1.text_input("Nazev projektu / popis prace",key="timer_proj_input")
            sazba=c2.number_input("Hodinova sazba (Kc)",min_value=0,value=500,step=50,key="timer_sazba_input")
            if st.button("Spustit mereni",type="primary"):
                if proj:
                    st.session_state.timer_start=datetime.now().isoformat()
                    st.session_state.timer_projekt=proj
                    st.session_state.timer_sazba=sazba
                    st.rerun()
                else: st.warning("Zadejte nazev projektu.")
        else:
            start_dt=datetime.fromisoformat(st.session_state.timer_start)
            elapsed=(datetime.now()-start_dt).total_seconds()
            h=int(elapsed)//3600; m=(int(elapsed)%3600)//60; s=int(elapsed)%60
            st.markdown(f'<div class="timer-label">Meri se: {st.session_state.timer_projekt}</div>',unsafe_allow_html=True)
            st.markdown(f'<div class="timer-display">{h:02d}:{m:02d}:{s:02d}</div>',unsafe_allow_html=True)
            mins=elapsed/60; odh=mins/60*st.session_state.timer_sazba
            st.markdown(f'<div style="color:#64748b;font-size:.85rem;text-align:center">Odhadovana castka: <b style="color:#fbbf24">{odh:,.0f} Kc</b> pri {st.session_state.timer_sazba} Kc/hod</div>',unsafe_allow_html=True)
            c1,c2=st.columns(2)
            if c1.button("Zastavit a ulozit",type="primary"):
                run_command("INSERT INTO casovac (user_id,projekt,start_ts,end_ts,trvani_min,sazba,poznamka) VALUES (?,?,?,?,?,?,?)",(uid,st.session_state.timer_projekt,st.session_state.timer_start,datetime.now().isoformat(),round(mins,2),st.session_state.timer_sazba,""))
                st.session_state.timer_start=None; st.success(f"Ulozeno: {fmt_min(mins)} → {odh:,.0f} Kc"); st.rerun()
            if c2.button("Zahodit"): st.session_state.timer_start=None; st.rerun()
        st.markdown('</div>',unsafe_allow_html=True)
        st.divider()
        st.subheader("Zaznamy")
        pp=get_pool(); conn=pp.getconn()
        try: df_tim=pd.read_sql("SELECT c.*,k.jmeno as klient FROM casovac c LEFT JOIN klienti k ON c.klient_id=k.id WHERE c.user_id=%s ORDER BY c.id DESC LIMIT 50",conn,params=(uid,))
        finally: pp.putconn(conn)
        if not df_tim.empty:
            df_tim['cas']=df_tim['trvani_min'].apply(fmt_min)
            df_tim['castka']=(df_tim['trvani_min']/60*df_tim['sazba']).round(0)
            df_tim['fakturovano']=df_tim['fakturovano'].map({0:'Ne',1:'Ano'})
            st.dataframe(df_tim[['start_ts','projekt','cas','castka','fakturovano']].rename(columns={'start_ts':'Zacatek','projekt':'Projekt','cas':'Cas','castka':'Kc','fakturovano':'Fakturovano'}),hide_index=True,use_container_width=True)
            st.markdown("**Prevest zaznamy do nove faktury:**")
            nefak=df_tim[df_tim['fakturovano']=='Ne']
            if not nefak.empty:
                sel_ids=st.multiselect("Vyberte zaznamy",nefak.apply(lambda x:f"{x['projekt']} – {x['cas']} ({x['castka']:,.0f} Kc)",axis=1).tolist())
                if sel_ids and st.button("Pridat jako polozky faktury"):
                    for s in sel_ids:
                        proj_name=s.split(" – ")[0]; match=nefak[nefak['projekt']==proj_name]
                        if not match.empty:
                            row2=match.iloc[0]; new_row=pd.DataFrame([{"Popis polozky":f"Prace: {row2['projekt']}","Cena":round(row2['castka'],0)}])
                            st.session_state.items_df=pd.concat([st.session_state.items_df,new_row],ignore_index=True)
                    st.success("Polozky pridany! Prejdete do Faktur a vystavte."); st.rerun()
        else: st.info("Zadne zaznamy. Spustte mereni vyse.")
        st.divider()
        st.subheader("Sablony polozek")
        with st.form("sbl_form"):
            sc1,sc2,sc3=st.columns([3,2,1])
            sn=sc1.text_input("Nazev polozky",placeholder="Konzultace, Vyvoj webu…")
            sp=sc2.number_input("Vychozi cena (Kc)",min_value=0.0,step=100.0)
            if sc3.form_submit_button("Pridat"):
                if sn: run_command("INSERT INTO item_sablony (user_id,nazev,cena) VALUES (?,?,?)",(uid,sn,sp)); st.rerun()
        for s in (run_query("SELECT * FROM item_sablony WHERE user_id=?",(uid,)) or []):
            c1,c2=st.columns([4,1])
            c1.markdown(f"**{s['nazev']}** — {s['cena']:,.0f} Kc")
            if c2.button("Smazat",key=f"delsbl_{s['id']}"): run_command("DELETE FROM item_sablony WHERE id=? AND user_id=?",(s['id'],uid)); st.rerun()

    # ================================
    # OPAKOVANÉ
    # ================================
    elif "Opakovane" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">🔄</div><div class="sec-title">Opakovane faktury</div></div>',unsafe_allow_html=True)
        with st.expander("Nove opakovane nastaveni"):
            pp=get_pool(); conn=pp.getconn()
            try:
                kli=pd.read_sql("SELECT id,jmeno FROM klienti WHERE user_id=%s",conn,params=(uid,))
                kat=pd.read_sql("SELECT id,nazev FROM kategorie WHERE user_id=%s",conn,params=(uid,))
            finally: pp.putconn(conn)
            if kli.empty: st.warning("Nejprve pridejte klienta.")
            else:
                with st.form("op_form"):
                    c1,c2=st.columns(2)
                    op_name=c1.text_input("Nazev (interni)",placeholder="Mesicni sprava webu")
                    op_interval=c2.selectbox("Interval",["mesicne","ctvrtletne","pololetne","rocne"],format_func=lambda x:{"mesicne":"Mesicne","ctvrtletne":"Ctvrtletne","pololetne":"Pololetne","rocne":"Rocne"}[x])
                    c3,c4=st.columns(2)
                    op_kl=c3.selectbox("Klient",kli['jmeno'])
                    op_kat="Obecna"
                    if not kat.empty: op_kat=c4.selectbox("Kategorie",kat['nazev'])
                    op_text=st.text_input("Uvodni text faktury","Fakturujeme Vam pravidelnou platbu:")
                    op_items=st.data_editor(pd.DataFrame(columns=["Popis polozky","Cena"]),num_rows="dynamic",use_container_width=True,key="op_items_ed")
                    if st.form_submit_button("Ulozit nastaveni"):
                        if op_name and not kli[kli['jmeno']==op_kl].empty:
                            kid=int(kli[kli['jmeno']==op_kl]['id'].values[0])
                            cid=int(kat[kat['nazev']==op_kat]['id'].values[0]) if not kat.empty else None
                            items_data=op_items.to_dict(orient='records') if not op_items.empty else []
                            run_command("INSERT INTO opakujici (user_id,nazev,klient_id,kategorie_id,interval_typ,posledni_vytvoreni,aktivni,uvodni_text,polozky_json) VALUES (?,?,?,?,?,?,1,?,?)",(uid,op_name,kid,cid,op_interval,None,op_text,json.dumps(items_data,default=str)))
                            st.success("Nastaveni ulozeno!"); st.rerun()
                        else: st.error("Vyplnte nazev a vyberte klienta.")
        st.divider()
        opak=run_query("SELECT o.*,k.jmeno FROM opakujici o JOIN klienti k ON o.klient_id=k.id WHERE o.user_id=? ORDER BY o.id DESC",(uid,))
        if not opak: st.info("Zadna opakovana fakturace.")
        else:
            interval_map={"mesicne":30,"ctvrtletne":91,"pololetne":182,"rocne":365}
            interval_label={"mesicne":"Mesicne","ctvrtletne":"Ctvrtletne","pololetne":"Pololetne","rocne":"Rocne"}
            for op in opak:
                op=dict(op)
                posledni=op.get('posledni_vytvoreni')
                days_int=interval_map.get(op.get('interval_typ','mesicne'),30)
                if posledni:
                    try:
                        last_d=datetime.strptime(str(posledni)[:10],'%Y-%m-%d').date()
                        next_d=last_d+timedelta(days=days_int)
                        days_left=(next_d-date.today()).days
                        due_status="overdue" if days_left<0 else ("soon" if days_left<=5 else "ok")
                    except: days_left=999; due_status="ok"; next_d=date.today()
                else: days_left=0; due_status="overdue"; next_d=date.today()
                status_color={"overdue":"#f87171","soon":"#fbbf24","ok":"#34d399"}[due_status]
                status_text={"overdue":"Ceka na vystaveni!","soon":f"Splatne za {days_left} dni","ok":f"Splatne za {days_left} dni"}[due_status]
                st.markdown(f"""
<div class="recur-card">
  <div>
    <div class="recur-name">{op['nazev']}</div>
    <div class="recur-meta">{op['jmeno']} &nbsp;·&nbsp; {interval_label.get(op.get('interval_typ',''),'?')}</div>
  </div>
  <div style="text-align:right">
    <div style="color:{status_color};font-size:.82rem;font-weight:600;margin-bottom:6px">{status_text}</div>
    <span class="recur-badge">{interval_label.get(op.get('interval_typ',''),'?')}</span>
  </div>
</div>""",unsafe_allow_html=True)
                with st.expander(f"   Detaily: {op['nazev']}"):
                    c1,c2,c3=st.columns(3)
                    if due_status in ("overdue","soon"):
                        if c1.button("Vystavit nyni",key=f"op_vystavit_{op['id']}",type="primary"):
                            kat_all=run_query("SELECT * FROM kategorie WHERE user_id=?",(uid,))
                            cid=op.get('kategorie_id')
                            if not cid and kat_all: cid=kat_all[0]['id']
                            if cid:
                                _,full,_=next_num(cid,uid)
                                total_items=[]
                                try: total_items=json.loads(op.get('polozky_json','[]'))
                                except: pass
                                total=sum(float(it.get('Cena',0)) for it in total_items)
                                fid=run_command("INSERT INTO faktury (user_id,cislo_full,klient_id,kategorie_id,datum_vystaveni,datum_splatnosti,castka_celkem,variabilni_symbol,uvodni_text) VALUES (?,?,?,?,?,?,?,?,?)",(uid,full,op['klient_id'],cid,date.today(),date.today()+timedelta(14),total,re.sub(r"\D","",full),op.get('uvodni_text','')))
                                for it in total_items:
                                    if it.get('Popis polozky'): run_command("INSERT INTO faktura_polozky (faktura_id,nazev,cena) VALUES (?,?,?)",(fid,it['Popis polozky'],float(it.get('Cena',0))))
                                run_command("UPDATE kategorie SET aktualni_cislo=aktualni_cislo+1 WHERE id=?",(cid,))
                                run_command("UPDATE opakujici SET posledni_vytvoreni=? WHERE id=?",(date.today().isoformat(),op['id']))
                                cached_pdf.clear(); st.success(f"Faktura {full} vystavena!"); st.rerun()
                    act_val=bool(op.get('aktivni',1))
                    if c2.button("Pozastavit" if act_val else "Aktivovat",key=f"op_tog_{op['id']}"):
                        run_command("UPDATE opakujici SET aktivni=? WHERE id=?",(0 if act_val else 1,op['id'])); st.rerun()
                    if c3.button("Smazat",key=f"op_del_{op['id']}"): run_command("DELETE FROM opakujici WHERE id=?",(op['id'],)); st.rerun()
                    if op.get('polozky_json'):
                        try:
                            items=json.loads(op['polozky_json'])
                            if items:
                                st.markdown("**Polozky faktury:**")
                                for it in items: st.markdown(f"- {it.get('Popis polozky','')} — {float(it.get('Cena',0)):,.0f} Kc")
                        except: pass

    # ================================
    # DASHBOARD
    # ================================
    elif "Dashboard" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">📊</div><div class="sec-title">Prehled podnikani</div></div>',unsafe_allow_html=True)
        tr=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?",(uid,),True)['sum'] or 0
        tp=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=1",(uid,),True)['sum'] or 0
        td=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0",(uid,),True)['sum'] or 0
        cnt=run_query("SELECT COUNT(*) FROM faktury WHERE user_id=?",(uid,),True)['count'] or 0
        t_hours=run_query("SELECT SUM(trvani_min) FROM casovac WHERE user_id=?",(uid,),True)['sum'] or 0
        c1,c2,c3,c4,c5=st.columns(5)
        c1.metric("Celkovy obrat",f"{tr:,.0f} Kc"); c2.metric("Zaplaceno",f"{tp:,.0f} Kc",delta=f"{int(tp/tr*100) if tr else 0}%")
        c3.metric("Ceka na platbu",f"{td:,.0f} Kc",delta="-",delta_color="inverse"); c4.metric("Faktur celkem",cnt)
        c5.metric("Hodin v casovaci",fmt_min(t_hours))
        st.divider()
        gc1,gc2=st.columns([2,1])
        pp=get_pool(); conn=pp.getconn()
        try:
            with gc1:
                st.subheader("Vyvoj v case")
                df_g=pd.read_sql("SELECT datum_vystaveni,castka_celkem FROM faktury WHERE user_id=%s",conn,params=(uid,))
                if not df_g.empty:
                    df_g['datum']=pd.to_datetime(df_g['datum_vystaveni'])
                    mo=df_g.groupby(df_g['datum'].dt.to_period('M'))['castka_celkem'].sum(); mo.index=mo.index.astype(str)
                    st.bar_chart(mo,color="#fbbf24")
                else: st.info("Zadna data.")
            with gc2:
                st.subheader("TOP 5 klientu")
                df_t=pd.read_sql("SELECT k.jmeno,SUM(f.castka_celkem) as celkem FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=%s GROUP BY k.jmeno ORDER BY celkem DESC LIMIT 5",conn,params=(uid,))
                if not df_t.empty: st.dataframe(df_t.set_index('jmeno').style.format("{:,.0f} Kc"),use_container_width=True)
            st.subheader("Prijmy dle kategorii")
            df_c=pd.read_sql("SELECT k.nazev,SUM(f.castka_celkem) as celkem FROM faktury f JOIN kategorie k ON f.kategorie_id=k.id WHERE f.user_id=%s GROUP BY k.nazev",conn,params=(uid,))
            if not df_c.empty: st.bar_chart(df_c.set_index('nazev'))
        finally: pp.putconn(conn)

    # ================================
    # DANĚ
    # ================================
    elif "Dane" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">🏛️</div><div class="sec-title">Danova kalkulacka</div></div>',unsafe_allow_html=True)
        years=[r['substring'] for r in run_query("SELECT DISTINCT SUBSTRING(datum_vystaveni,1,4) as substring FROM faktury WHERE user_id=?",(uid,))]
        cy=str(date.today().year)
        if cy not in years: years.append(cy)
        c1,c2=st.columns(2)
        sty=c1.selectbox("Rok",sorted(list(set(years)),reverse=True))
        po=c2.selectbox("Typ cinnosti",["80% – Remeslne zivnosti, zemedelstvi","60% – Ostatni zivnosti (nejcastejsi)","40% – Svobodna povolani, autorska prava","30% – Pronajem majetku"],index=1)
        pp_pct=int(po.split("%")[0])/100
        inc=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND SUBSTRING(datum_vystaveni,1,4)=?",(uid,sty),True)['sum'] or 0
        rex=run_query("SELECT SUM(castka) FROM vydaje WHERE user_id=? AND SUBSTRING(datum,1,4)=?",(uid,sty),True)['sum'] or 0
        fex=inc*pp_pct; tbr=max(0,inc-rex); tbf=max(0,inc-fex); taxr=tbr*.15; taxf=tbf*.15; diff=taxf-taxr
        st.markdown(f'<div class="callout">Prijmy za rok {sty}: <span>{inc:,.0f} Kc</span></div>',unsafe_allow_html=True)
        c1,c2=st.columns(2)
        with c1: st.markdown(f'<div class="tax-c"><div class="tax-title">A) Skutecne vydaje</div><div class="tax-meta">Vydaje: {rex:,.0f} Kc · Zaklad: {tbr:,.0f} Kc</div><div class="tax-amt">{taxr:,.0f} Kc</div><div class="tax-sub">Dan 15 %</div></div>',unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="tax-c"><div class="tax-title">B) Pausal {int(pp_pct*100)} %</div><div class="tax-meta">Vydaje: {fex:,.0f} Kc · Zaklad: {tbf:,.0f} Kc</div><div class="tax-amt">{taxf:,.0f} Kc</div><div class="tax-sub">Dan 15 %</div></div>',unsafe_allow_html=True)
        st.divider()
        if taxr<taxf: st.success(f"Vyhodnejsi jsou SKUTECNE vydaje — usetrite {diff:,.0f} Kc.")
        elif taxf<taxr: st.success(f"Vyhodnejsi je PAUSAL — usetrite {abs(diff):,.0f} Kc.")
        else: st.info("Obe varianty vychazi stejne.")

    # ================================
    # VÝDAJE
    # ================================
    elif "Vydaje" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">💸</div><div class="sec-title">Evidence vydaju</div></div>',unsafe_allow_html=True)
        with st.form("exp"):
            c1,c2=st.columns(2); ed=c1.date_input("Datum",date.today()); ep=c2.text_input("Popis")
            c3,c4=st.columns(2); ea=c3.number_input("Castka (Kc)",min_value=0.0,step=100.0); ec=c4.selectbox("Kategorie",["Provoz","Material","Sluzby","Ostatni"])
            if st.form_submit_button("Pridat"):
                run_command("INSERT INTO vydaje (user_id,datum,popis,castka,kategorie) VALUES (?,?,?,?,?)",(uid,ed,ep,ea,ec)); st.success("Ulozeno"); st.rerun()
        pp=get_pool(); conn=pp.getconn()
        try: vy=pd.read_sql("SELECT * FROM vydaje WHERE user_id=%s ORDER BY datum DESC",conn,params=(uid,))
        finally: pp.putconn(conn)
        if not vy.empty:
            st.dataframe(vy[['id','datum','popis','kategorie','castka']],hide_index=True,use_container_width=True)
            cv=vy['castka'].sum(); cp=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?",(uid,),True)['sum'] or 0
            c1,c2,c3=st.columns(3); c1.metric("Prijmy",f"{cp:,.0f} Kc"); c2.metric("Vydaje",f"{cv:,.0f} Kc",delta=-cv); c3.metric("Hruby zisk",f"{cp-cv:,.0f} Kc")
            vl=vy.apply(lambda x:f"ID {x['id']}: {x['datum']} – {x['popis']} ({x['castka']} Kc)",axis=1).tolist()
            sd=st.selectbox("Vyberte ke smazani",vl)
            if st.button("Smazat"):
                did=int(sd.split(":")[0].replace("ID ",""))
                run_command("DELETE FROM vydaje WHERE id=? AND user_id=?",(did,uid)); st.rerun()

    # ================================
    # KLIENTI
    # ================================
    elif "Klienti" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">👥</div><div class="sec-title">Klienti</div></div>',unsafe_allow_html=True)
        rid=st.session_state.form_reset_id
        with st.expander("Pridat klienta"):
            c1,c2=st.columns([3,1]); ico_in=c1.text_input("ICO",key=f"ico_{rid}")
            if c2.button("Nacist ARES",key=f"ares_{rid}"):
                d=get_ares(ico_in)
                if d: st.session_state.ares_data=d; st.success("Nacteno")
                else: st.error("Nenalezeno v ARES")
            ad=st.session_state.ares_data
            with st.form("fc"):
                j=st.text_input("Jmeno / Firma",ad.get('jmeno','')); a=st.text_area("Adresa",ad.get('adresa',''))
                c1,c2=st.columns(2); i=c1.text_input("IC",ad.get('ico','')); d2=c2.text_input("DIC",ad.get('dic',''))
                pz=st.text_area("Poznamka")
                if st.form_submit_button("Ulozit"):
                    run_command("INSERT INTO klienti (user_id,jmeno,adresa,ico,dic,poznamka) VALUES (?,?,?,?,?,?)",(uid,j,a,i,d2,pz))
                    reset_forms(); cached_pdf.clear(); st.rerun()
        for k in run_query("SELECT * FROM klienti WHERE user_id=?",(uid,)):
            with st.expander(f"  {k['jmeno']}"):
                if k['poznamka']: st.info(k['poznamka'])
                ek=f"edit_k_{k['id']}"
                if ek not in st.session_state: st.session_state[ek]=False
                c1,c2=st.columns(2)
                if c1.button("Upravit",key=f"bek_{k['id']}"): st.session_state[ek]=True; st.rerun()
                if c2.button("Smazat",key=f"bdk_{k['id']}"): run_command("DELETE FROM klienti WHERE id=?",(k['id'],)); st.rerun()
                if st.session_state[ek]:
                    with st.form(f"fke_{k['id']}"):
                        nj=st.text_input("Jmeno",k['jmeno']); na=st.text_area("Adresa",k['adresa'])
                        ni=st.text_input("IC",k['ico']); nd=st.text_input("DIC",k['dic']); np=st.text_area("Poznamka",k['poznamka'])
                        if st.form_submit_button("Ulozit"):
                            run_command("UPDATE klienti SET jmeno=?,adresa=?,ico=?,dic=?,poznamka=? WHERE id=?",(nj,na,ni,nd,np,k['id']))
                            st.session_state[ek]=False; cached_pdf.clear(); st.rerun()

    # ================================
    # KATEGORIE
    # ================================
    elif "Kategorie" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">🏷️</div><div class="sec-title">Kategorie</div></div>',unsafe_allow_html=True)
        if not is_pro:
            st.markdown('<div class="pro-card"><h3>Funkce PRO verze</h3><p style="color:#64748b">Aktivujte v Nastaveni.</p></div>',unsafe_allow_html=True)
        else:
            with st.expander("Nova kategorie"):
                with st.form("fcat"):
                    c1,c2=st.columns(2); n=c1.text_input("Nazev"); p=c2.text_input("Prefix")
                    c3,c4=st.columns(2); s=c3.number_input("Start c.",1); c=c4.color_picker("Barva pruhu (na fakture)")
                    l=st.file_uploader("Logo (PNG/JPG)")
                    if st.form_submit_button("Ulozit"):
                        run_command("INSERT INTO kategorie (user_id,nazev,prefix,aktualni_cislo,barva,logo_blob) VALUES (?,?,?,?,?,?)",(uid,n,p,s,c,proc_logo(l))); cached_pdf.clear(); st.rerun()
        for k in run_query("SELECT * FROM kategorie WHERE user_id=?",(uid,)):
            with st.expander(f"  {k['nazev']}  ·  {k['prefix']}"):
                if k['logo_blob']: st.image(bytes(k['logo_blob']),width=80)
                ck=f"edit_cat_{k['id']}"
                if ck not in st.session_state: st.session_state[ck]=False
                c1,c2=st.columns(2)
                if is_pro and c1.button("Upravit",key=f"bec_{k['id']}"): st.session_state[ck]=True; st.rerun()
                if c2.button("Smazat",key=f"bdc_{k['id']}"): run_command("DELETE FROM kategorie WHERE id=?",(k['id'],)); cached_pdf.clear(); st.rerun()
                if st.session_state[ck]:
                    with st.form(f"feck_{k['id']}"):
                        c1,c2=st.columns(2); nn=c1.text_input("Nazev",k['nazev']); np=c2.text_input("Prefix",k['prefix'])
                        c3,c4=st.columns(2); ns=c3.number_input("Cislo",value=k['aktualni_cislo']); nc=c4.color_picker("Barva pruhu",k['barva'])
                        nl=st.file_uploader("Nove logo",key=f"ul_{k['id']}")
                        if st.form_submit_button("Ulozit"):
                            if nl: run_command("UPDATE kategorie SET nazev=?,prefix=?,aktualni_cislo=?,barva=?,logo_blob=? WHERE id=?",(nn,np,ns,nc,proc_logo(nl),k['id']))
                            else:  run_command("UPDATE kategorie SET nazev=?,prefix=?,aktualni_cislo=?,barva=? WHERE id=?",(nn,np,ns,nc,k['id']))
                            st.session_state[ck]=False; cached_pdf.clear(); st.rerun()

    # ================================
    # NASTAVENÍ
    # ================================
    elif "Nastaveni" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">⚙️</div><div class="sec-title">Nastaveni</div></div>',unsafe_allow_html=True)
        res=run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1",(uid,),single=True); c=dict(res) if res else {}

        with st.expander("Licence & Pristup",expanded=True):
            valid,exp=check_lic(uid)
            if not valid:
                st.markdown('<div class="pro-card"><h3>Aktivujte PRO verzi</h3><div class="pro-feat-row"><div class="pro-feat">Vlastni barvy faktury</div><div class="pro-feat">Export ISDOC</div><div class="pro-feat">Logo na fakture</div><div class="pro-feat">Cloud zaloha</div></div><div class="pro-price">990 Kc / rok · jsem@michalkochtik.cz</div></div>',unsafe_allow_html=True)
                kk=st.text_input("Licencni klic")
                if st.button("Aktivovat PRO"):
                    kdb=run_query("SELECT * FROM licencni_klice WHERE kod=? AND pouzito_uzivatelem_id IS NULL",(kk,),True)
                    if kdb:
                        ne=date.today()+timedelta(days=kdb['dny_platnosti'])
                        run_command("UPDATE users SET license_key=?,license_valid_until=? WHERE id=?",(kk,ne,uid))
                        run_command("UPDATE licencni_klice SET pouzito_uzivatelem_id=? WHERE id=?",(uid,kdb['id']))
                        st.session_state.is_pro=True; st.balloons(); st.rerun()
                    else: st.error("Neplatny klic.")
            else:
                st.success(f"PRO aktivni do: **{fmt_d(exp)}**")
                if st.button("Deaktivovat"): run_command("UPDATE users SET license_key=NULL,license_valid_until=NULL WHERE id=?",(uid,)); st.session_state.is_pro=False; st.rerun()
            st.divider()
            st.markdown("**Zmena hesla**")
            pc1,pc2=st.columns(2); p1=pc1.text_input("Stavajici",type="password"); p2=pc2.text_input("Nove",type="password")
            if st.button("Zmenint heslo"):
                ud=run_query("SELECT * FROM users WHERE id=?",(uid,),True)
                if ud['password_hash']==hp(p1): run_command("UPDATE users SET password_hash=? WHERE id=?",(hp(p2),uid)); st.success("Zmeneno.")
                else: st.error("Nespravne stavajici heslo.")

        with st.expander("Moje Firma"):
            with st.form("setf"):
                c1,c2=st.columns(2); n=c1.text_input("Nazev firmy",c.get('nazev',dname)); a=c2.text_area("Adresa",c.get('adresa',''))
                c3,c4=st.columns(2); i=c3.text_input("ICO",c.get('ico','')); d=c4.text_input("DIC",c.get('dic',''))
                c5,c6=st.columns(2); b=c5.text_input("Banka",c.get('banka','')); u=c6.text_input("Cislo uctu",c.get('ucet',''))
                c7,c8=st.columns(2); ib=c7.text_input("IBAN (pro QR platbu)",c.get('iban','')); tel=c8.text_input("Telefon",c.get('telefon',''))
                if st.form_submit_button("Ulozit"):
                    ic=ib.replace(" ","").upper() if ib else ""
                    if c.get('id'): run_command("UPDATE nastaveni SET nazev=?,adresa=?,ico=?,dic=?,banka=?,ucet=?,iban=?,telefon=? WHERE id=?",(n,a,i,d,b,u,ic,tel,c['id']))
                    else: run_command("INSERT INTO nastaveni (user_id,nazev,adresa,ico,dic,banka,ucet,iban,telefon) VALUES (?,?,?,?,?,?,?,?,?)",(uid,n,a,i,d,b,u,ic,tel))
                    get_nastaveni.clear(); cached_pdf.clear(); cached_isdoc.clear(); st.rerun()

        with st.expander(f"Upozorneni {'(PRO)' if not is_pro else ''}"):
            if not is_pro: st.markdown('<div class="pro-card"><p style="color:#64748b">Automaticka upozorneni jsou v PRO verzi.</p></div>',unsafe_allow_html=True)
            else:
                act=st.toggle("Aktivovat",value=bool(c.get('notify_active',0)))
                ca1,ca2=st.columns(2); nd=ca1.number_input("Dni predem",value=c.get('notify_days',3),min_value=1); ne=ca2.text_input("Email",value=c.get('notify_email',''))
                st.markdown("**SMTP**"); preset=st.selectbox("Preset",["-- Vyberte --","Seznam.cz","Gmail","Vlastni"])
                ds=c.get('smtp_server','smtp.seznam.cz'); dp=c.get('smtp_port',465)
                if preset=="Seznam.cz": ds="smtp.seznam.cz"; dp=465
                elif preset=="Gmail": ds="smtp.gmail.com"; dp=465
                ss=st.text_input("Server",value=ds)
                cs1,cs2=st.columns(2); sp=cs1.number_input("Port",value=dp); su=cs2.text_input("Login",value=c.get('smtp_email',''))
                sw=st.text_input("Heslo",value=c.get('smtp_password',''),type="password")
                cx1,cx2=st.columns(2)
                if cx1.button("Ulozit SMTP"): run_command("UPDATE nastaveni SET notify_active=?,notify_days=?,notify_email=?,smtp_server=?,smtp_port=?,smtp_email=?,smtp_password=? WHERE id=?",(int(act),nd,ne,ss,sp,su,sw,c.get('id'))); st.success("OK")
                if cx2.button("Test email"):
                    if send_mail(ne,"Test","Funguje"): st.success("Odeslano")
                    else: st.error("Chyba")

        if is_pro:
            with st.expander("Export ISDOC"):
                cx1,cx2=st.columns(2); ds=cx1.date_input("Od",date.today().replace(day=1)); de=cx2.date_input("Do",date.today())
                if st.button("Pripravit ZIP"):
                    invs=run_query("SELECT id,cislo_full FROM faktury WHERE datum_vystaveni BETWEEN %s AND %s AND user_id=%s",(str(ds),str(de),uid))
                    if invs:
                        buf=io.BytesIO()
                        with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as zf:
                            for inv in invs:
                                isd=generate_isdoc(inv['id'],uid)
                                if isd: zf.writestr(f"{inv['cislo_full']}.isdoc",isd)
                        st.download_button("Stahnout ZIP",buf.getvalue(),"export.zip","application/zip")
                    else: st.warning("Zadne faktury v danem obdobi.")

            with st.expander("Zaloha dat"):
                z1,z2=st.columns(2)
                z1.download_button("Export JSON",export_data(uid),"zaloha.json","application/json")
                if z2.button("Odeslat na email"):
                    if send_mail(c.get('notify_email'),"Zaloha MojeFaktury","Data v priloze.",export_data(uid),"zaloha.json"): st.success("Odeslano")
                    else: st.error("Chyba")
                st.divider()
                upl=st.file_uploader("Import (JSON)",type="json")
                if upl and st.button("Obnovit data"):
                    try:
                        data=json.load(upl); cm={}; km={}
                        for r in data.get('nastaveni',[]):
                            ex=run_query("SELECT id FROM nastaveni WHERE user_id=?",(uid,),True)
                            if ex: run_command("UPDATE nastaveni SET nazev=?,adresa=?,ico=?,dic=?,ucet=?,banka=?,iban=? WHERE id=?",(r.get('nazev'),r.get('adresa'),r.get('ico'),r.get('dic'),r.get('ucet'),r.get('banka'),r.get('iban'),ex['id']))
                            else: run_command("INSERT INTO nastaveni (user_id,nazev,adresa,ico,dic,banka,ucet,iban) VALUES (?,?,?,?,?,?,?,?)",(uid,r.get('nazev'),r.get('adresa'),r.get('ico'),r.get('dic'),r.get('ucet'),r.get('banka'),r.get('iban')))
                        for r in data.get('klienti',[]):
                            ex=run_query("SELECT id FROM klienti WHERE jmeno=? AND user_id=?",(r.get('jmeno'),uid),True)
                            if ex: cm[r['id']]=ex['id']
                            else:
                                nid=run_command("INSERT INTO klienti (user_id,jmeno,adresa,ico,dic,email,poznamka) VALUES (?,?,?,?,?,?,?)",(uid,r.get('jmeno'),r.get('adresa'),r.get('ico'),r.get('dic'),r.get('email'),r.get('poznamka')))
                                if r.get('id'): cm[r['id']]=nid
                        for r in data.get('kategorie',[]):
                            ex=run_query("SELECT id FROM kategorie WHERE nazev=? AND user_id=?",(r.get('nazev'),uid),True)
                            if ex: km[r['id']]=ex['id']
                            else:
                                blob=base64.b64decode(r.get('logo_blob')) if r.get('logo_blob') else None
                                nid=run_command("INSERT INTO kategorie (user_id,nazev,barva,prefix,aktualni_cislo,logo_blob) VALUES (?,?,?,?,?,?)",(uid,r.get('nazev'),r.get('barva'),r.get('prefix'),r.get('aktualni_cislo'),blob))
                                if r.get('id'): km[r['id']]=nid
                        for r in data.get('faktury',[]):
                            cid=cm.get(r.get('klient_id')); kid=km.get(r.get('kategorie_id'))
                            if cid and kid and not run_query("SELECT id FROM faktury WHERE cislo_full=? AND user_id=?",(r.get('cislo_full'),uid),True):
                                nfid=run_command("INSERT INTO faktury (user_id,cislo,cislo_full,klient_id,kategorie_id,datum_vystaveni,datum_duzp,datum_splatnosti,castka_celkem,zpusob_uhrady,variabilni_symbol,cislo_objednavky,uvodni_text,uhrazeno,muj_popis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(uid,r.get('cislo'),r.get('cislo_full'),cid,kid,r.get('datum_vystaveni'),r.get('datum_duzp'),r.get('datum_splatnosti'),r.get('castka_celkem'),r.get('zpusob_uhrady'),r.get('variabilni_symbol'),r.get('cislo_objednavky'),r.get('uvodni_text'),r.get('uhrazeno'),r.get('muj_popis')))
                                for item in data.get('faktura_polozky',[]):
                                    if item.get('faktura_id')==r.get('id'): run_command("INSERT INTO faktura_polozky (faktura_id,nazev,cena) VALUES (?,?,?)",(nfid,item.get('nazev'),item.get('cena')))
                        cached_pdf.clear(); cached_isdoc.clear(); st.success("Import dokoncen!"); st.rerun()
                    except Exception as ex: st.error(f"Chyba: {ex}")
        else:
            with st.expander("Zaloha dat"):
                st.markdown('<div class="pro-card"><p style="color:#64748b">Zaloha je dostupna v PRO verzi.</p></div>',unsafe_allow_html=True)
