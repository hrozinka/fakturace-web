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

# -- CSS (základní – načítá se vždy, i na login stránce) --
def inject_css(css_str):
    import base64 as _b64
    encoded = _b64.b64encode(css_str.encode("utf-8")).decode("utf-8")
    st.markdown(
        f'<link rel="stylesheet" href="data:text/css;charset=utf-8;base64,{encoded}">',
        unsafe_allow_html=True,
    )

# Google Fonts
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

/* CUSTOM COMPONENTS */
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

/* === MOBILNI RESPONZIVITA (max-width: 640px) ===*/
@media (max-width: 640px) {
  /* Hlavni obsah - zmenšit padding */
  .block-container{padding-left:12px!important;padding-right:12px!important;padding-top:16px!important}

  /* Brand / Login */
  .brand-wrap{padding:24px 0 14px}
  .brand-logo{font-size:44px}
  .brand-title{
    font-size:2rem!important;
    white-space:normal!important;
    word-break:break-word!important;
    overflow-wrap:break-word!important;
    line-height:1.15!important
  }
  .brand-sub{font-size:.88rem;margin:6px 0 18px}
  .feat-grid{padding:14px 16px}
  .feat-row{font-size:.8rem;gap:7px}

  /* Nadpisy sekci */
  h1{font-size:1.5rem!important}
  h2{font-size:1.2rem!important}
  h3{font-size:1rem!important}
  .sec-title{font-size:1rem!important}

  /* Stats karty */
  .stats-row{grid-template-columns:repeat(3,1fr)!important;gap:7px!important}
  .sc{padding:11px 8px!important}
  .sc-val{font-size:1.05rem!important}
  .sc-lbl{font-size:.58rem!important}

  /* Mini row */
  .mini-row{grid-template-columns:repeat(3,1fr)!important;gap:6px!important}
  .mini-sc{padding:9px 6px!important}
  .mini-val{font-size:.88rem!important}

  /* Admin grid 2x2 */
  .adm-grid{grid-template-columns:repeat(2,1fr)!important}

  /* Cashflow grid 1 sloupec */
  .cf-grid{grid-template-columns:1fr!important;gap:8px!important}

  /* Overdue panel */
  .overdue-header{flex-wrap:wrap;gap:6px}
  .overdue-row{flex-direction:column;align-items:flex-start;gap:4px}
  .overdue-amount,.overdue-days{text-align:left!important}

  /* Total line */
  .total-ln{padding:11px 13px}
  .total-amt{font-size:1rem!important}

  /* Danove karty */
  .tax-c{padding:16px!important}
  .tax-amt{font-size:1.5rem!important}

  /* Pro card */
  .pro-feat-row{grid-template-columns:1fr!important}

  /* Opakovane karty */
  .recur-card{flex-direction:column!important;align-items:flex-start!important;gap:10px!important}

  /* Quote karta */
  .quote-header{flex-direction:column!important;align-items:flex-start!important;gap:6px!important}
  .quote-amt{text-align:left!important}

  /* Cashflow radky */
  .cf-row{flex-direction:column!important;align-items:flex-start!important;gap:3px!important}
  .cf-row-amt{text-align:left!important}

  /* Tlacitka */
  .stButton>button{height:48px!important;font-size:.82rem!important}
  div[data-testid="stForm"] button[kind="primary"]{height:48px!important}

  /* Inputy - vetsi font pro mobil */
  .stTextInput input,.stNumberInput input,.stTextArea textarea,.stDateInput input{
    font-size:16px!important;padding:12px 13px!important
  }

  /* Sidebar */
  section[data-testid="stSidebar"]{padding:8px!important}
  section[data-testid="stSidebar"] .stRadio label{padding:10px 12px!important}

  /* Expander */
  div[data-testid="stExpander"]{margin-bottom:7px!important}

  /* Timer */
  .timer-display{font-size:2.6rem!important}
  .timer-card{padding:16px!important}

  /* Sec header */
  .sec-hdr{margin-bottom:14px!important;padding-bottom:10px!important}
  .sec-ico{width:28px!important;height:28px!important;font-size:.8rem!important}

  /* Callout */
  .callout{font-size:.8rem!important;padding:9px 12px!important}

  /* Tag chips */
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
            try: c.execute("INSERT INTO email_templates (name,subject,body) VALUES ('welcome','Vítejte','Dobrý den {name},\n\nVáš účet byl vytvořen.\n\nTým MojeFakturace') ON CONFLICT (name) DO NOTHING")
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
    if not res or not res['license_valid_until']: return False,"Žádná"
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

def _pdf_qr(pdf, moje, data, cf, block_y, fn, qr_box_w, total_x):
    if not moje.get('iban'): return
    try:
        ic  = str(moje['iban']).replace(" ","").upper()
        vs  = str(data.get('variabilni_symbol',''))
        qr_str = f"SPD*1.0*ACC:{ic}*AM:{data.get('castka_celkem')}*CC:CZK*X-VS:{vs}*MSG:{rm_acc('Faktura '+cf)}"
        qr_img = qrcode.QRCode(version=1,error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=6,border=2)
        qr_img.add_data(qr_str); qr_img.make(fit=True)
        q = qr_img.make_image(fill_color="black",back_color="white")
        qf = f"q_{data['id']}.png"; q.save(qf)
        qr_x = total_x - qr_box_w - 5
        pdf.set_fill_color(248,249,251); pdf.rect(qr_x,block_y,qr_box_w,24,'F')
        pdf.image(qf,qr_x+2,block_y+2,20); os.remove(qf)
        pdf.set_font(fn,'',6); pdf.set_text_color(100,115,135)
        for i,t in enumerate(["QR Platba","Skenujte","v mobilni","aplikaci"]):
            pdf.set_xy(qr_x+23,block_y+4+i*4); pdf.cell(19,4,t,0,1,'L')
    except: pass

def _pdf_watermark(pdf, fn, paid):
    if not paid: return
    pdf.set_font(fn,'B',52); pdf.set_text_color(180,240,200)
    pdf.set_xy(50,130); pdf.rotate(35)
    pdf.cell(0,0,"ZAPLACENO",0,0,'C'); pdf.rotate(0)
    pdf.set_text_color(0,0,0)

def _pdf_items(pdf, fn, pol, mx, mw, ar, ag, ab, lr, lg, lb, fp_fn, tx_fn):
    COL_DESC = mw - 40; COL_PRICE = 40
    pdf.set_fill_color(ar,ag,ab); pdf.set_text_color(255,255,255)
    pdf.set_font(fn,'B',8.5); pdf.set_x(mx)
    pdf.cell(COL_DESC,8,"POPIS POLOZKY",0,0,'L',True)
    pdf.cell(COL_PRICE,8,"CENA (Kc)",0,1,'R',True)
    alt = False
    for item in pol:
        if not item.get('nazev'): continue
        bg = (lr,lg,lb) if alt else (250,251,253)
        pdf.set_fill_color(*bg); pdf.set_text_color(20,32,52)
        pdf.set_font(fn,'',8.5); pdf.set_x(mx)
        pdf.cell(COL_DESC,7.5,tx_fn(item.get('nazev','')),0,0,'L',True)
        pdf.set_font(fn,'B',8.5)
        pdf.cell(COL_PRICE,7.5,fp_fn(item.get('cena',0)),0,1,'R',True)
        alt = not alt
    return pdf.get_y()

def generate_pdf(fid, uid, is_pro, template=1):
    use_font = os.path.exists(FONT_FILE)
    def tx(t): return rm_acc(str(t)) if t else ""
    def fp(v):
        try: return f"{float(v):,.2f}".replace(","," ").replace(".",",")
        except: return "0,00"
    try:
        raw = run_query(
            "SELECT f.*,k.jmeno as k_jmeno,k.adresa as k_adresa,k.ico as k_ico,k.dic as k_dic,"
            "kat.barva,kat.logo_blob,kat.prefix FROM faktury f "
            "JOIN klienti k ON f.klient_id=k.id "
            "JOIN kategorie kat ON f.kategorie_id=kat.id "
            "WHERE f.id=? AND f.user_id=?", (fid,uid), single=True)
        if not raw: return None
        data = dict(raw)
        pol  = [dict(x) for x in (run_query("SELECT * FROM faktura_polozky WHERE faktura_id=?",(fid,)) or [])]
        moje = get_nastaveni(uid)
        paid = bool(data.get('uhrazeno',0))

        ar,ag,ab = 15,23,42
        if data.get('barva'):
            try:
                cv=data['barva'].lstrip('#')
                ar,ag,ab=tuple(int(cv[i:i+2],16) for i in (0,2,4))
            except: pass
        def lc(c,a=180): return min(c+a,255)
        lr,lg,lb = lc(ar,190),lc(ag,190),lc(ab,190)
        mr,mg,mb = lc(ar,120),lc(ag,120),lc(ab,120)
        cf = data.get('cislo_full') or f"{data.get('prefix','')}{data.get('cislo','')}"

        class PDF(FPDF):
            def __init__(self):
                super().__init__()
                self.fn = 'ArialCS' if use_font else 'Arial'
                if use_font:
                    try:
                        self.add_font('ArialCS','',FONT_FILE,uni=True)
                        self.add_font('ArialCS','B',FONT_FILE,uni=True)
                    except: pass
            def header(self): pass

        pdf = PDF(); fn = pdf.fn
        pdf.set_margins(0,0,0); pdf.add_page()
        PAGE_W = 210

        if template == 1:
            SB = 32
            pdf.set_fill_color(ar,ag,ab); pdf.rect(0,0,SB,297,'F')
            pdf.set_fill_color(lc(ar,30),lc(ag,30),lc(ab,30)); pdf.rect(SB-1,0,1,297,'F')
            logo_placed = False
            if data.get('logo_blob'):
                try:
                    lf=f"l_{fid}.png"; open(lf,"wb").write(data['logo_blob'])
                    pdf.image(lf,4,8,SB-8); os.remove(lf); logo_placed=True
                except: pass
            if not logo_placed:
                pdf.set_fill_color(lc(ar,25),lc(ag,25),lc(ab,25)); pdf.rect(6,8,20,20,'F')
                pdf.set_font(fn,'B',11); pdf.set_text_color(255,255,255)
                co=tx(moje.get('nazev',''))[:2].upper()
                pdf.set_xy(6,12); pdf.cell(20,12,co,0,0,'C')

            pdf.set_fill_color(lc(ar,18),lc(ag,18),lc(ab,18)); pdf.rect(5,34,SB-10,0.5,'F')

            def sb_lbl(y,label,value,vs=8):
                pdf.set_font(fn,'',6.5); pdf.set_text_color(mr,mg,mb)
                pdf.set_xy(4,y); pdf.cell(SB-8,4,label.upper(),0,1,'L')
                pdf.set_font(fn,'B',vs); pdf.set_text_color(255,255,255)
                pdf.set_xy(4,y+4); pdf.cell(SB-8,5,tx(value),0,1,'L')

            sy=38
            sb_lbl(sy,"Cislo",cf,7.5); sy+=13
            sb_lbl(sy,"Vystaveno",fmt_d(data.get('datum_vystaveni')),7.5); sy+=13
            sb_lbl(sy,"Splatnost",fmt_d(data.get('datum_splatnosti')),7.5); sy+=13
            if tx(data.get('variabilni_symbol','')): sb_lbl(sy,"VS",tx(data.get('variabilni_symbol','')),7.5); sy+=13
            if moje.get('ucet') or moje.get('iban'):
                pdf.set_fill_color(lc(ar,15),lc(ag,15),lc(ab,15)); pdf.rect(3,sy+2,SB-6,0.4,'F'); sy+=7
                sb_lbl(sy,"Platba na ucet",tx(moje.get('ucet','')),7); sy+=13
                if moje.get('banka'): sb_lbl(sy,"Banka",tx(moje['banka']),7); sy+=13
            pdf.set_fill_color(lc(ar,15),lc(ag,15),lc(ab,15)); pdf.rect(3,255,SB-6,0.4,'F')
            pdf.set_font(fn,'B',7); pdf.set_text_color(255,255,255)
            pdf.set_xy(4,259); pdf.multi_cell(SB-8,4.5,tx(moje.get('nazev',''))[:22],0,'L')
            if moje.get('ico'):
                pdf.set_font(fn,'',6); pdf.set_text_color(mr,mg,mb)
                pdf.set_xy(4,pdf.get_y()); pdf.cell(SB-8,4,tx(f"IC: {moje['ico']}"),0,1,'L')

            MX=SB+8; MW=PAGE_W-MX-8
            pdf.set_font(fn,'B',36); pdf.set_text_color(ar,ag,ab)
            pdf.set_xy(MX,10); pdf.cell(MW,16,"FAKTURA",0,1,'R')
            pdf.set_draw_color(ar,ag,ab); pdf.set_line_width(0.5)
            pdf.line(MX,28,PAGE_W-8,28); pdf.set_line_width(0.2)

            DOD_W=MW//2-4; ODB_X=MX+DOD_W+8
            pdf.set_font(fn,'B',6.5); pdf.set_text_color(ar,ag,ab)
            pdf.set_xy(MX,32); pdf.cell(DOD_W,4,"DODAVATEL",0,0,'L')
            pdf.set_xy(ODB_X,32); pdf.cell(DOD_W,4,"ODBERATEL",0,1,'L')
            pdf.set_font(fn,'B',10); pdf.set_text_color(10,18,35)
            pdf.set_xy(MX,38); pdf.cell(DOD_W,6,tx(moje.get('nazev',''))[:32],0,0,'L')
            pdf.set_xy(ODB_X,38); pdf.cell(DOD_W,6,tx(data.get('k_jmeno',''))[:32],0,1,'L')
            pdf.set_font(fn,'',8); pdf.set_text_color(80,95,115)
            dod=[tx(moje.get('adresa','')),tx(f"IC: {moje['ico']}") if moje.get('ico') else "",
                 tx(f"DIC: {moje['dic']}") if moje.get('dic') else "",tx(moje.get('email','')),tx(moje.get('telefon',''))]
            dod=[x for x in dod if x]
            odb=[tx(data.get('k_adresa','')),tx(f"IC: {data['k_ico']}") if data.get('k_ico') else "",
                 tx(f"DIC: {data['k_dic']}") if data.get('k_dic') else ""]
            odb=[x for x in odb if x]
            py=46
            for i in range(max(len(dod),len(odb))):
                dl=dod[i] if i<len(dod) else ""; ol=odb[i] if i<len(odb) else ""
                pdf.set_xy(MX,py); pdf.cell(DOD_W,5,dl,0,0,'L')
                pdf.set_xy(ODB_X,py); pdf.cell(DOD_W,5,ol,0,1,'L'); py+=5
            if data.get('uvodni_text'):
                pdf.set_y(py+3); pdf.set_x(MX)
                pdf.set_font(fn,'I',8); pdf.set_text_color(100,115,135)
                pdf.multi_cell(MW,4.5,tx(data['uvodni_text'])); py=pdf.get_y()

            pdf.set_y(max(py+8,90))
            ty=_pdf_items(pdf,fn,pol,MX,MW,ar,ag,ab,lr,lg,lb,fp,tx)
            pdf.set_draw_color(ar,ag,ab); pdf.set_line_width(0.3); pdf.line(MX,ty,PAGE_W-8,ty)

            BY=ty+5; TBW=75
            TX2=PAGE_W-8-TBW
            pdf.set_fill_color(ar,ag,ab); pdf.rect(TX2,BY,TBW,18,'F')
            pdf.set_font(fn,'',7.5); pdf.set_text_color(mr,mg,mb)
            pdf.set_xy(TX2+3,BY+3); pdf.cell(40,5,"CELKEM K UHRADE:",0,0,'L')
            pdf.set_font(fn,'B',16); pdf.set_text_color(255,255,255)
            pdf.set_xy(TX2,BY+7); pdf.cell(TBW-4,10,fp(data.get('castka_celkem',0))+" Kc",0,0,'R')
            _pdf_qr(pdf,moje,data,cf,BY,fn,44,TX2)
            _pdf_watermark(pdf,fn,paid)
            pdf.set_fill_color(ar,ag,ab); pdf.rect(SB,286,PAGE_W-SB,11,'F')
            fparts=[tx(moje.get('nazev','')),tx(f"IC: {moje['ico']}") if moje.get('ico') else "",tx(moje.get('email',''))]
            pdf.set_font(fn,'',6.5); pdf.set_text_color(mr,mg,mb)
            pdf.set_xy(MX,289); pdf.cell(MW,5,"   |   ".join(x for x in fparts if x),0,0,'C')

        elif template == 2:
            MX=14; MW=PAGE_W-MX-14
            pdf.set_fill_color(ar,ag,ab); pdf.rect(0,0,PAGE_W,22,'F')
            logo_placed=False
            if data.get('logo_blob'):
                try:
                    lf=f"l_{fid}.png"; open(lf,"wb").write(data['logo_blob'])
                    pdf.image(lf,MX,3,24); os.remove(lf); logo_placed=True
                except: pass
            if not logo_placed:
                pdf.set_font(fn,'B',13); pdf.set_text_color(255,255,255)
                pdf.set_xy(MX,5); pdf.cell(40,12,tx(moje.get('nazev',''))[:18],0,0,'L')

            pdf.set_font(fn,'B',22); pdf.set_text_color(255,255,255)
            pdf.set_xy(0,4); pdf.cell(PAGE_W-MX,14,"FAKTURA",0,0,'R')
            pdf.set_font(fn,'',8); pdf.set_text_color(lc(ar,160),lc(ag,160),lc(ab,160))
            pdf.set_xy(PAGE_W-MX-65,15); pdf.cell(65,5,tx(f"Cislo: {cf}"),0,0,'R')

            pdf.set_draw_color(ar,ag,ab); pdf.set_line_width(0.8)
            pdf.line(MX,26,PAGE_W-MX,26); pdf.set_line_width(0.2)

            DOD_W=80; ODB_X=MX+DOD_W+10; DTL_X=PAGE_W-MX-55
            pdf.set_font(fn,'B',7); pdf.set_text_color(ar,ag,ab)
            pdf.set_xy(MX,30); pdf.cell(DOD_W,4,"DODAVATEL",0,0,'L')
            pdf.set_xy(ODB_X,30); pdf.cell(DOD_W,4,"ODBERATEL",0,0,'L')
            pdf.set_xy(DTL_X,30); pdf.cell(55,4,"FAKTURA",0,1,'R')

            pdf.set_font(fn,'B',10); pdf.set_text_color(10,18,35)
            pdf.set_xy(MX,36); pdf.cell(DOD_W,6,tx(moje.get('nazev',''))[:28],0,0,'L')
            pdf.set_xy(ODB_X,36); pdf.cell(DOD_W,6,tx(data.get('k_jmeno',''))[:28],0,0,'L')

            pdf.set_fill_color(248,249,252); pdf.rect(DTL_X,34,55,32,'F')
            pdf.set_font(fn,'',7.5); pdf.set_text_color(100,115,135)
            details=[("Vystaveno:",fmt_d(data.get('datum_vystaveni'))),
                     ("Splatnost:",fmt_d(data.get('datum_splatnosti'))),
                     ("Var. symbol:",tx(data.get('variabilni_symbol',''))),
                     ("Ucet:",tx(moje.get('ucet','')))]
            for i,(lbl,val) in enumerate(details):
                y=36+i*7.5
                pdf.set_xy(DTL_X+3,y); pdf.cell(26,6,lbl,0,0,'L')
                pdf.set_font(fn,'B',7.5); pdf.set_text_color(10,18,35)
                pdf.set_xy(DTL_X+30,y); pdf.cell(22,6,val,0,1,'R')
                pdf.set_font(fn,'',7.5); pdf.set_text_color(100,115,135)

            pdf.set_font(fn,'',8); pdf.set_text_color(80,95,115); py=44
            dod=[tx(moje.get('adresa','')),tx(f"IC: {moje['ico']}") if moje.get('ico') else "",
                 tx(f"DIC: {moje['dic']}") if moje.get('dic') else "",tx(moje.get('email',''))]
            dod=[x for x in dod if x]
            odb=[tx(data.get('k_adresa','')),tx(f"IC: {data['k_ico']}") if data.get('k_ico') else "",
                 tx(f"DIC: {data['k_dic']}") if data.get('k_dic') else ""]
            odb=[x for x in odb if x]
            for i in range(max(len(dod),len(odb))):
                dl=dod[i] if i<len(dod) else ""; ol=odb[i] if i<len(odb) else ""
                pdf.set_xy(MX,py); pdf.cell(DOD_W,5,dl,0,0,'L')
                pdf.set_xy(ODB_X,py); pdf.cell(DOD_W,5,ol,0,1,'L'); py+=5
            if data.get('uvodni_text'):
                pdf.set_y(py+3); pdf.set_x(MX)
                pdf.set_font(fn,'I',8); pdf.set_text_color(100,115,135)
                pdf.multi_cell(MW,4.5,tx(data['uvodni_text'])); py=pdf.get_y()

            pdf.set_draw_color(ar,ag,ab); pdf.set_line_width(0.5)
            pdf.line(MX,max(py+6,75),PAGE_W-MX,max(py+6,75)); pdf.set_line_width(0.2)
            pdf.set_y(max(py+8,77))

            ty=_pdf_items(pdf,fn,pol,MX,MW,ar,ag,ab,lr,lg,lb,fp,tx)
            pdf.set_draw_color(ar,ag,ab); pdf.set_line_width(0.5)
            pdf.line(MX,ty,PAGE_W-MX,ty); pdf.line(MX,ty+2,PAGE_W-MX,ty+2)
            pdf.set_line_width(0.2)

            BY=ty+8; TBW=80; TX2=PAGE_W-MX-TBW
            pdf.set_font(fn,'',9); pdf.set_text_color(80,95,115)
            pdf.set_xy(TX2,BY); pdf.cell(TBW//2,8,"CELKEM K UHRADE:",0,0,'L')
            pdf.set_font(fn,'B',18); pdf.set_text_color(ar,ag,ab)
            pdf.set_xy(TX2,BY); pdf.cell(TBW,8,fp(data.get('castka_celkem',0))+" Kc",0,0,'R')
            pdf.set_draw_color(ar,ag,ab); pdf.set_line_width(1.5)
            pdf.line(TX2,BY+9,PAGE_W-MX,BY+9); pdf.set_line_width(0.2)

            _pdf_qr(pdf,moje,data,cf,BY,fn,44,TX2)
            _pdf_watermark(pdf,fn,paid)

            pdf.set_draw_color(200,210,220); pdf.set_line_width(0.3)
            pdf.line(MX,281,PAGE_W-MX,281)
            fparts=[tx(moje.get('nazev','')),tx(f"IC: {moje['ico']}") if moje.get('ico') else "",
                    tx(moje.get('email','')),tx(moje.get('telefon',''))]
            pdf.set_font(fn,'',6.5); pdf.set_text_color(150,160,175)
            pdf.set_xy(MX,284); pdf.cell(MW,5,"   |   ".join(x for x in fparts if x),0,0,'C')

        elif template == 3:
            MX=16; MW=PAGE_W-MX-16
            pdf.set_fill_color(ar,ag,ab); pdf.rect(0,0,PAGE_W,4,'F')
            pdf.set_fill_color(ar,ag,ab); pdf.rect(0,4,3,293,'F')

            logo_placed=False
            if data.get('logo_blob'):
                try:
                    lf=f"l_{fid}.png"; open(lf,"wb").write(data['logo_blob'])
                    pdf.image(lf,MX,10,28); os.remove(lf); logo_placed=True
                except: pass

            pdf.set_font(fn,'B',14); pdf.set_text_color(10,18,35)
            pdf.set_xy(MX,10 if not logo_placed else 42)
            pdf.cell(MW//2,10,tx(moje.get('nazev',''))[:26],0,1,'L')

            pdf.set_font(fn,'B',32); pdf.set_text_color(ar,ag,ab)
            pdf.set_xy(0,8); pdf.cell(PAGE_W-MX,14,"FAKTURA",0,1,'R')

            pdf.set_font(fn,'',8); pdf.set_text_color(150,160,175)
            pdf.set_xy(0,24); pdf.cell(PAGE_W-MX,5,tx(cf),0,1,'R')

            pdf.set_draw_color(230,232,238); pdf.set_line_width(0.4)
            pdf.line(MX,35,PAGE_W-MX,35); pdf.set_line_width(0.2)

            DOD_W=65; ODB_X=MX+DOD_W+8; DTL_X=ODB_X+65+5
            pdf.set_font(fn,'B',6); pdf.set_text_color(ar,ag,ab)
            for lbl,x in [("DODAVATEL",MX),("ODBERATEL",ODB_X),("PLATEBNI UDAJE",DTL_X)]:
                pdf.set_xy(x,39); pdf.cell(60,3.5,lbl,0,1,'L')

            pdf.set_font(fn,'B',9); pdf.set_text_color(10,18,35)
            pdf.set_xy(MX,44); pdf.cell(DOD_W,5,tx(moje.get('nazev',''))[:22],0,0,'L')
            pdf.set_xy(ODB_X,44); pdf.cell(DOD_W,5,tx(data.get('k_jmeno',''))[:22],0,0,'L')
            pdf.set_font(fn,'',7.5); pdf.set_text_color(80,95,115)
            pay_rows=[("Vystaveno",fmt_d(data.get('datum_vystaveni'))),
                      ("Splatnost",fmt_d(data.get('datum_splatnosti'))),
                      ("VS",tx(data.get('variabilni_symbol',''))),
                      ("Ucet",tx(moje.get('ucet','')))]
            for i,(lbl,val) in enumerate(pay_rows):
                py2=44+i*5
                pdf.set_xy(DTL_X,py2); pdf.cell(22,5,lbl+":",0,0,'L')
                pdf.set_font(fn,'B',7.5); pdf.set_text_color(10,18,35)
                pdf.set_xy(DTL_X+24,py2); pdf.cell(30,5,val,0,0,'L')
                pdf.set_font(fn,'',7.5); pdf.set_text_color(80,95,115)

            pdf.set_font(fn,'',8); pdf.set_text_color(80,95,115); py=51
            dod=[tx(moje.get('adresa','')),tx(f"IC: {moje['ico']}") if moje.get('ico') else "",
                 tx(f"DIC: {moje['dic']}") if moje.get('dic') else "",tx(moje.get('email',''))]
            dod=[x for x in dod if x]
            odb=[tx(data.get('k_adresa','')),tx(f"IC: {data['k_ico']}") if data.get('k_ico') else "",
                 tx(f"DIC: {data['k_dic']}") if data.get('k_dic') else ""]
            odb=[x for x in odb if x]
            for i in range(max(len(dod),len(odb))):
                dl=dod[i] if i<len(dod) else ""; ol=odb[i] if i<len(odb) else ""
                pdf.set_xy(MX,py); pdf.cell(DOD_W,5,dl,0,0,'L')
                pdf.set_xy(ODB_X,py); pdf.cell(DOD_W,5,ol,0,1,'L'); py+=5

            if data.get('uvodni_text'):
                pdf.set_y(py+2); pdf.set_x(MX)
                pdf.set_font(fn,'I',8); pdf.set_text_color(130,140,155)
                pdf.multi_cell(MW,4.5,tx(data['uvodni_text'])); py=pdf.get_y()

            pdf.set_draw_color(ar,ag,ab); pdf.set_line_width(0.4)
            tbl_y=max(py+6,85)
            pdf.line(MX,tbl_y,PAGE_W-MX,tbl_y); pdf.set_line_width(0.2)
            pdf.set_y(tbl_y+2)

            COL_DESC=MW-40; COL_PRICE=40
            pdf.set_font(fn,'B',7.5); pdf.set_text_color(ar,ag,ab)
            pdf.set_x(MX); pdf.cell(COL_DESC,7,"POPIS",0,0,'L')
            pdf.cell(COL_PRICE,7,"CENA (Kc)",0,1,'R')
            pdf.set_draw_color(220,225,232); pdf.set_line_width(0.3)
            pdf.line(MX,pdf.get_y(),PAGE_W-MX,pdf.get_y())

            for item in pol:
                if not item.get('nazev'): continue
                pdf.set_font(fn,'',8.5); pdf.set_text_color(20,32,52); pdf.set_x(MX)
                pdf.cell(COL_DESC,7.5,tx(item.get('nazev','')),0,0,'L')
                pdf.set_font(fn,'B',8.5); pdf.cell(COL_PRICE,7.5,fp(item.get('cena',0)),0,1,'R')
                pdf.set_draw_color(238,240,245); pdf.line(MX,pdf.get_y(),PAGE_W-MX,pdf.get_y())

            ty=pdf.get_y()+4
            pdf.set_draw_color(ar,ag,ab); pdf.set_line_width(0.5)
            pdf.line(PAGE_W-MX-85,ty,PAGE_W-MX,ty); pdf.set_line_width(0.2)
            pdf.set_font(fn,'',8); pdf.set_text_color(120,130,145)
            pdf.set_xy(PAGE_W-MX-85,ty+4); pdf.cell(40,7,"CELKEM K UHRADE:",0,0,'L')
            pdf.set_font(fn,'B',20); pdf.set_text_color(ar,ag,ab)
            pdf.set_xy(0,ty+2); pdf.cell(PAGE_W-MX,9,fp(data.get('castka_celkem',0))+" Kc",0,0,'R')

            _pdf_qr(pdf,moje,data,cf,ty+2,fn,40,PAGE_W-MX-85)
            _pdf_watermark(pdf,fn,paid)

            pdf.set_draw_color(ar,ag,ab); pdf.set_line_width(2)
            pdf.line(MX,284,MX+8,284); pdf.set_line_width(0.2)
            fparts=[tx(moje.get('nazev','')),tx(f"IC: {moje['ico']}") if moje.get('ico') else "",
                    tx(moje.get('email',''))]
            pdf.set_font(fn,'',6.5); pdf.set_text_color(160,170,185)
            pdf.set_xy(MX,287); pdf.cell(MW,5," · ".join(x for x in fparts if x),0,0,'L')

        try:
            out = pdf.output(dest='S')
        except TypeError:
            out = pdf.output()
            
        if isinstance(out, str):
            return out.encode('latin-1')
        return bytes(out)
        
    except Exception as e:
        print(f"PDF error: {e}")
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
def cached_pdf(fid,uid,is_pro,template,rh): return generate_pdf(fid,uid,is_pro,template)
@st.cache_data(show_spinner=False,max_entries=500)
def cached_isdoc(fid,uid,rh): return generate_isdoc(fid,uid)

# ==============================================
# SESSION
# ==============================================
for k,v in [('user_id',None),('role','user'),('is_pro',False),
            ('items_df',pd.DataFrame(columns=["Popis položky","Cena"])),
            ('form_reset_id',0),('ares_data',{}),
            ('timer_start',None),('timer_projekt',''),('timer_sazba',500)]:
    if k not in st.session_state: st.session_state[k]=v

def reset_forms():
    st.session_state.form_reset_id+=1; st.session_state.ares_data={}
    st.session_state.items_df=pd.DataFrame(columns=["Popis položky","Cena"])

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
  <p class="brand-sub">Fakturace pro moderní živnostníky.<br>Rychlá, přehledná, vždy po ruce.</p>
</div>
<div class="feat-grid">
  <div class="feat-row">✦ &nbsp;<b>14 dní PRO zdarma</b> — bez kreditky</div>
  <div class="feat-row">✦ &nbsp;<b>Faktura do 30 sekund</b> — přímočarý tok</div>
  <div class="feat-row">✦ &nbsp;<b>Krásné PDF faktury</b> — s logem a QR platbou</div>
  <div class="feat-row">✦ &nbsp;<b>Časovač hodin</b> — trackuj čas → faktura</div>
  <div class="feat-row">✦ &nbsp;<b>Opakované faktury</b> — automatizace odběratelů</div>
</div>""", unsafe_allow_html=True)
        t1,t2,t3=st.tabs(["  Přihlášení  ","  Registrace  ","  Zapomenuté heslo  "])
        with t1:
            with st.form("log"):
                u=st.text_input("Jméno nebo Email").strip(); p=st.text_input("Heslo",type="password").strip()
                if st.form_submit_button("Vstoupit →",type="primary",use_container_width=True):
                    r=run_query("SELECT * FROM users WHERE (username=? OR email=?) AND password_hash=?",(u,u,hp(p)),single=True)
                    if r:
                        for k2,v2 in [('user_id',r['id']),('role',r['role']),('username',r['username']),('full_name',r['full_name']),('user_email',r['email'])]:
                            st.session_state[k2]=v2
                        st.session_state.force_pw_change=dict(r).get('force_password_change',0)
                        valid,exp=check_lic(r['id']); st.session_state.is_pro=valid
                        run_command("UPDATE users SET last_active=? WHERE id=?",(datetime.now().isoformat(),r['id'])); st.rerun()
                    else: st.error("Neplatné přihlašovací údaje.")
        with t2:
            with st.form("reg"):
                f=st.text_input("Jméno a Příjmení").strip(); u=st.text_input("Login").strip()
                e=st.text_input("Email").strip(); tel=st.text_input("Telefon").strip(); p=st.text_input("Heslo",type="password").strip()
                if st.form_submit_button("Vytvořit účet →",use_container_width=True):
                    try:
                        uid_new=run_command("INSERT INTO users (username,password_hash,full_name,email,phone,created_at,force_password_change) VALUES (?,?,?,?,?,?,0)",(u,hp(p),f,e,tel,datetime.now().isoformat()))
                        tk=gen_lic()
                        run_command("INSERT INTO licencni_klice (kod,dny_platnosti,vygenerovano,poznamka,pouzito_uzivatelem_id) VALUES (?,?,?,?,?)",(tk,14,datetime.now().isoformat(),"Auto-Trial",uid_new))
                        run_command("UPDATE users SET license_key=?,license_valid_until=? WHERE id=?",(tk,date.today()+timedelta(14),uid_new))
                        st.success("Účet vytvořen + 14 dní PRO zdarma. Přihlaste se.")
                    except Exception as ex: st.error(f"Chyba: {ex}")
        with t3:
            with st.form("forgot"):
                fe=st.text_input("Váš Email").strip()
                if st.form_submit_button("Odeslat nové heslo →",use_container_width=True):
                    usr=run_query("SELECT * FROM users WHERE email=?",(fe,),single=True)
                    if usr:
                        np=gen_pw(); run_command("UPDATE users SET password_hash=?,force_password_change=1 WHERE id=?",(hp(np),usr['id']))
                        if send_mail(fe,"Reset hesla – MojeFaktury",f"Nové heslo: {np}\nPo přihlášení budete vyzváni ke změně."): st.success("Odesláno.")
                        else: st.error("Chyba odesílání.")
                    else: st.error("Email nenalezen.")
    st.stop()

# ==============================================
# CSS pro přihlášené uživatele
# ==============================================
_APP_CSS = r"""/* TIMER */
.timer-display{font-family:'Syne',sans-serif;font-size:3.5rem;font-weight:800;text-align:center;
  color:#fbbf24;letter-spacing:.05em;margin:16px 0;
  text-shadow:0 0 40px rgba(251,191,36,.3)}
.timer-card{background:rgba(251,191,36,.06);border:1px solid rgba(251,191,36,.2);
  border-radius:16px;padding:24px;text-align:center;margin-bottom:16px}
.timer-label{font-size:.75rem;color:#64748b;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px}

/* RECURRING */
.recur-card{background:rgba(99,102,241,.06);border:1px solid rgba(99,102,241,.2);
  border-radius:14px;padding:16px 18px;margin-bottom:10px;
  display:flex;justify-content:space-between;align-items:center}
.recur-name{font-family:'Syne',sans-serif;font-size:.95rem;font-weight:700;color:#f1f5f9}
.recur-meta{font-size:.78rem;color:#64748b;margin-top:2px}
.recur-badge{background:rgba(99,102,241,.2);border:1px solid rgba(99,102,241,.35);
  border-radius:20px;padding:3px 10px;font-size:.7rem;font-weight:700;color:#818cf8;letter-spacing:.04em}

/* TEMPLATE CHIP */
.tpl-grid{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.tpl-chip{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);
  border-radius:8px;padding:7px 12px;font-size:.8rem;color:#94a3b8;cursor:pointer;
  transition:all .15s}
.tpl-chip:hover{background:rgba(251,191,36,.1);border-color:rgba(251,191,36,.3);color:#fbbf24}
.tpl-chip .price{color:#475569;margin-left:6px;font-size:.75rem}

/* QUOTE */
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

/* CASHFLOW */
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

/* REMINDER SENT */
.reminder-ok{background:rgba(52,211,153,.07);border:1px solid rgba(52,211,153,.2);border-radius:9px;padding:10px 14px;font-size:.83rem;color:#34d399;margin:6px 0}"""
inject_css(_APP_CSS)

# ==============================================
# APP
# ==============================================
uid=st.session_state.user_id; role=st.session_state.role; is_pro=st.session_state.is_pro
dname=st.session_state.full_name or st.session_state.username
run_command("UPDATE users SET last_active=? WHERE id=?",(datetime.now().isoformat(),uid))

if st.session_state.get('force_pw_change',0)==1:
    st.markdown("## ⚠️ Změna hesla vyžadována")
    with st.form("fpc"):
        np1=st.text_input("Nové heslo",type="password").strip(); np2=st.text_input("Potvrzení",type="password").strip()
        if st.form_submit_button("Změnit →",type="primary"):
            if np1 and np1==np2:
                run_command("UPDATE users SET password_hash=?,force_password_change=0 WHERE id=?",(hp(np1),uid))
                st.session_state.force_pw_change=0; st.success("Hotovo!"); st.rerun()
            else: st.error("Hesla se neshodují.")
    st.stop()

# Sidebar
bc="badge-pro" if is_pro else "badge-free"; bt="⭐ PRO" if is_pro else "FREE"
st.sidebar.markdown(f'<div class="sb-card"><div class="sb-name">{dname}</div><div class="sb-meta">{st.session_state.username}</div><span class="badge {bc}">{bt}</span></div>',unsafe_allow_html=True)
if st.sidebar.button("← Odhlásit"): st.session_state.user_id=None; st.rerun()

# ----------------------------------------------
# ADMIN
# ----------------------------------------------
if role=='admin':
    st.markdown('<div class="sec-hdr"><div class="sec-ico">👑</div><div class="sec-title">Admin Dashboard</div></div>',unsafe_allow_html=True)
    uc=run_query("SELECT COUNT(*) FROM users WHERE role!='admin'",single=True)['count'] or 0
    fc=run_query("SELECT COUNT(*) FROM faktury",single=True)['count'] or 0
    tr=run_query("SELECT SUM(castka_celkem) FROM faktury",single=True)['sum'] or 0
    au=tr/uc if uc else 0; af=tr/fc if fc else 0
    st.markdown(f'<div class="adm-grid"><div class="adm-card"><div class="adm-val">{uc}</div><div class="adm-lbl">Uživatelů</div></div><div class="adm-card"><div class="adm-val">{tr:,.0f} Kč</div><div class="adm-lbl">Celk. obrat</div></div><div class="adm-card"><div class="adm-val">{au:,.0f} Kč</div><div class="adm-lbl">/ User</div></div><div class="adm-card"><div class="adm-val">{af:,.0f} Kč</div><div class="adm-lbl">Prům. fak.</div></div></div>',unsafe_allow_html=True)
    st.divider()
    tabs=st.tabs(["👥 Uživatelé","🔑 Klíče","📧 Emailing"])
    with tabs[0]:
        fk=run_query("SELECT * FROM licencni_klice WHERE pouzito_uzivatelem_id IS NULL ORDER BY id DESC")
        kd={f"{k['kod']} ({k['dny_platnosti']} dní)":k for k in fk}
        for u in run_query("SELECT * FROM users WHERE role!='admin' ORDER BY id DESC"):
            ed=u['license_valid_until']; act=False
            if ed:
                try:
                    if datetime.strptime(str(ed)[:10],'%Y-%m-%d').date()>=date.today(): act=True
                except: pass
            with st.expander(f"{'⭐' if act else '○'} {u['username']} — {u['email']}"):
                c1,c2=st.columns(2)
                c1.write(f"**Jméno:** {u['full_name']}"); c1.write(f"**Tel:** {u['phone']}"); c1.write(f"**Vytvořeno:** {fmt_d(u['created_at'])}")
                cv=date.today()
                if u['license_valid_until']:
                    try: cv=datetime.strptime(str(u['license_valid_until'])[:10],'%Y-%m-%d').date()
                    except: pass
                nv=c2.date_input("Platnost do:",value=cv,key=f"md_{u['id']}")
                if c2.button("💾 Uložit",key=f"bd_{u['id']}"): run_command("UPDATE users SET license_valid_until=? WHERE id=?",(nv,u['id'])); st.rerun()
                sk=c2.selectbox("Přiřadit klíč",["-- Vyberte --"]+list(kd.keys()),key=f"sk_{u['id']}")
                if c2.button("Aktivovat",key=f"btn_{u['id']}"):
                    if sk!="-- Vyberte --":
                        kdata=kd[sk]; ne=date.today()+timedelta(days=kdata['dny_platnosti'])
                        run_command("UPDATE users SET license_key=?,license_valid_until=? WHERE id=?",(kdata['kod'],ne,u['id']))
                        run_command("UPDATE licencni_klice SET pouzito_uzivatelem_id=? WHERE id=?",(u['id'],kdata['id'])); st.rerun()
                if st.button("🗑️ Smazat",key=f"del_{u['id']}",type="primary"): run_command("DELETE FROM users WHERE id=?",(u['id'],)); st.rerun()
    with tabs[1]:
        c1,c2=st.columns(2); dv=c1.number_input("Platnost (dny)",value=365,min_value=1); nv=c2.text_input("Poznámka")
        if st.button("Vygenerovat klíč"):
            k=gen_lic(); run_command("INSERT INTO licencni_klice (kod,dny_platnosti,vygenerovano,poznamka) VALUES (?,?,?,?)",(k,dv,datetime.now().isoformat(),nv)); st.success(f"`{k}`")
        for k in run_query("SELECT * FROM licencni_klice ORDER BY id DESC"):
            st.code(f"{k['kod']} | {k['dny_platnosti']} dní | {'🔴' if k['pouzito_uzivatelem_id'] else '🟢'} | {k['poznamka']}")
    with tabs[2]:
        tpl=run_query("SELECT * FROM email_templates WHERE name='welcome'",single=True); td=dict(tpl) if tpl else {}
        with st.form("wm"):
            ws=st.text_input("Předmět",value=td.get('subject','')); wb=st.text_area("Text ({name})",value=td.get('body',''),height=150)
            if st.form_submit_button("Uložit"):
                run_command("INSERT INTO email_templates (name,subject,body) VALUES ('welcome',?,?) ON CONFLICT (name) DO UPDATE SET subject=EXCLUDED.subject,body=EXCLUDED.body",(ws,wb)); st.success("OK")
        with st.form("mm"):
            ms=st.text_input("Předmět"); mb=st.text_area("Zpráva",height=120)
            if st.form_submit_button("Odeslat všem"):
                cnt=sum(1 for u in run_query("SELECT email FROM users WHERE role!='admin' AND email IS NOT NULL") if send_mail(u['email'],ms,mb))
                st.success(f"Odesláno: {cnt}")

# ----------------------------------------------
# USER MENU
# ----------------------------------------------
else:
    menu=st.sidebar.radio(" ",["📄 Faktury","📋 Nabídky","💰 Cashflow","⏱️ Časovač","🔄 Opakované","📊 Dashboard","🏛️ Daně","💸 Výdaje","👥 Klienti","🏷️ Kategorie","⚙️ Nastavení"])

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
                try: dl=(date.today()-datetime.strptime(str(r['datum_splatnosti'])[:10],'%Y-%m-%d').date()).days; dlt=f"{dl} dní po splatnosti"
                except: dlt="po splatnosti"
                rows+=f'<div class="overdue-row"><div><div class="overdue-name">{r["jmeno"]} <span style="color:#334155;font-size:.75rem">{r.get("cislo_full","")}</span></div><div class="overdue-detail">Splatnost: {fmt_d(r["datum_splatnosti"])}</div></div><div><div class="overdue-amount">{r["castka_celkem"]:,.0f} Kč</div><div class="overdue-days">{dlt}</div></div></div>'
            st.markdown(f'<div class="overdue-panel"><div class="overdue-header"><span>⚠️</span><span class="overdue-title">Pohledávky po splatnosti</span><span class="overdue-count">{len(overdue)}</span><span style="margin-left:auto;font-family:Syne,sans-serif;font-weight:800;color:#f87171">{tot_ov:,.0f} Kč</span></div>{rows}</div>',unsafe_allow_html=True)

        years=[r['substring'] for r in run_query("SELECT DISTINCT SUBSTRING(datum_vystaveni,1,4) as substring FROM faktury WHERE user_id=?",(uid,))]
        if str(datetime.now().year) not in years: years.append(str(datetime.now().year))
        sy=st.selectbox("Rok",sorted(list(set(years)),reverse=True),label_visibility="collapsed")
        sc_y=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND SUBSTRING(datum_vystaveni,1,4)=?",(uid,sy),True)['sum'] or 0
        sc_a=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?",(uid,),True)['sum'] or 0
        su_a=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0",(uid,),True)['sum'] or 0
        st.markdown(f'<div class="stats-row"><div class="sc g"><div class="sc-lbl">Obrat {sy}</div><div class="sc-val g">{sc_y:,.0f}</div><div class="sc-sub">Kč</div></div><div class="sc a"><div class="sc-lbl">Celkem</div><div class="sc-val a">{sc_a:,.0f}</div><div class="sc-sub">Kč</div></div><div class="sc r"><div class="sc-lbl">Neuhrazeno</div><div class="sc-val r">{su_a:,.0f}</div><div class="sc-sub">Kč</div></div></div>',unsafe_allow_html=True)

        sablony=run_query("SELECT * FROM item_sablony WHERE user_id=?",(uid,))
        if sablony:
            chips="".join(f'<span class="tpl-chip" title="Klikněte pro přidání"><b>{s["nazev"]}</b><span class="price">{s["cena"]:,.0f} Kč</span></span>' for s in sablony)
            st.markdown(f'<div class="callout">💡 Uložené šablony položek: <span>klikněte v editoru nebo přidejte ručně</span></div><div class="tpl-grid">{chips}</div>',unsafe_allow_html=True)

        with st.expander("➕  Nová faktura"):
            pp=get_pool(); conn=pp.getconn()
            try:
                kli=pd.read_sql("SELECT id,jmeno FROM klienti WHERE user_id=%s",conn,params=(uid,))
                kat=pd.read_sql("SELECT id,nazev FROM kategorie WHERE user_id=%s",conn,params=(uid,))
            finally: pp.putconn(conn)
            if kli.empty: st.warning("Nejprve přidejte klienta.")
            elif not is_pro and kat.empty:
                run_command("INSERT INTO kategorie (user_id,nazev,prefix,aktualni_cislo,barva) VALUES (?,'Obecná','FV',1,'#1e3a5f')",(uid,)); cached_pdf.clear(); st.rerun()
            else:
                rid=st.session_state.form_reset_id; c1,c2=st.columns(2)
                sk=c1.selectbox("Klient",kli['jmeno'],key=f"k_{rid}"); sc=c2.selectbox("Kategorie",kat['nazev'],key=f"c_{rid}")
                if not kli[kli['jmeno']==sk].empty and not kat[kat['nazev']==sc].empty:
                    kid=int(kli[kli['jmeno']==sk]['id'].values[0]); cid=int(kat[kat['nazev']==sc]['id'].values[0])
                    _,full,_=next_num(cid,uid)
                    st.markdown(f'<div class="callout">Číslo dokladu: <span>{full}</span></div>',unsafe_allow_html=True)
                    d1,d2=st.columns(2); dv=d1.date_input("Vystavení",date.today(),key=f"dv_{rid}"); ds=d2.date_input("Splatnost",date.today()+timedelta(14),key=f"ds_{rid}")
                    ut=st.text_input("Úvodní text","Fakturujeme Vám:",key=f"ut_{rid}")
                    ed=st.data_editor(st.session_state.items_df,num_rows="dynamic",use_container_width=True,key=f"ed_{rid}")
                    total=float(pd.to_numeric(ed["Cena"],errors='coerce').fillna(0).sum()) if not ed.empty and "Cena" in ed.columns else 0.0
                    st.markdown(f'<div class="total-ln"><span class="total-lbl">Celkem k úhradě</span><span class="total-amt">{total:,.2f} Kč</span></div>',unsafe_allow_html=True)
                    
                    if st.button("Vystavit fakturu →",type="primary",key=f"vystavit_{rid}"):
                        fid=run_command("INSERT INTO faktury (user_id,cislo_full,klient_id,kategorie_id,datum_vystaveni,datum_splatnosti,castka_celkem,variabilni_symbol,uvodni_text) VALUES (?,?,?,?,?,?,?,?,?)",(uid,full,kid,cid,dv,ds,total,re.sub(r"\D","",full),ut))
                        for _,row in ed.iterrows():
                            if row.get("Popis položky"): run_command("INSERT INTO faktura_polozky (faktura_id,nazev,cena) VALUES (?,?,?)",(fid,row["Popis položky"],float(row.get("Cena",0))))
                        run_command("UPDATE kategorie SET aktualni_cislo=aktualni_cislo+1 WHERE id=?",(cid,))
                        reset_forms(); cached_pdf.clear(); cached_isdoc.clear()
                        st.session_state['last_invoice_id'] = fid
                        st.session_state['last_invoice_full'] = full
                        st.rerun()
                        
                if st.session_state.get('last_invoice_id'):
                    last_fid = st.session_state['last_invoice_id']
                    last_full = st.session_state['last_invoice_full']
                    _tpl = get_nastaveni(uid).get('faktura_sablona',1) or 1
                    pdf_out = cached_pdf(last_fid, uid, is_pro, _tpl, f"new_{last_fid}_{_tpl}")
                    
                    if isinstance(pdf_out, bytes):
                        st.success(f"Faktura {last_full} byla úspěšně vystavena!")
                        st.download_button("↓ Stáhnout PDF ihned", pdf_out, f"{last_full}.pdf", "application/pdf")
                    else:
                        st.error(f"⚠️ Chyba PDF: {pdf_out}")
                        
                    if st.button("✖ Skrýt zprávu"):
                        del st.session_state['last_invoice_id']
                        del st.session_state['last_invoice_full']
                        st.rerun()

        st.markdown("<br>",unsafe_allow_html=True)
        fc1,fc2=st.columns(2)
        sel_cli=fc1.selectbox("Klient",["Všichni"]+[c['jmeno'] for c in run_query("SELECT jmeno FROM klienti WHERE user_id=?",(uid,))])
        db_yrs=[y['substring'] for y in run_query("SELECT DISTINCT SUBSTRING(datum_vystaveni,1,4) as substring FROM faktury WHERE user_id=?",(uid,))]
        sel_yr=fc2.selectbox("Rok",["Všechny"]+sorted(db_yrs,reverse=True))
        if sel_cli!="Všichni":
            ca=run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=?",(uid,sel_cli),True)['sum'] or 0
            cd=run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=? AND f.uhrazeno=0",(uid,sel_cli),True)['sum'] or 0
            cy=0
            if sel_yr!="Všechny": cy=run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=? AND SUBSTRING(f.datum_vystaveni,1,4)=?",(uid,sel_cli,sel_yr),True)['sum'] or 0
            st.markdown(f'<div class="mini-row"><div class="mini-sc"><div class="mini-lbl">Historie</div><div class="mini-val">{ca:,.0f} Kč</div></div><div class="mini-sc"><div class="mini-lbl">Obrat</div><div class="mini-val g">{cy:,.0f} Kč</div></div><div class="mini-sc"><div class="mini-lbl">Dluží</div><div class="mini-val r">{cd:,.0f} Kč</div></div></div>',unsafe_allow_html=True)

        search_q=st.text_input("🔍 Hledat fakturu…",placeholder="číslo, klient, popis",label_visibility="collapsed")
        q="SELECT f.*,k.jmeno FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=%s"; ps=[uid]
        if sel_cli!="Všichni": q+=" AND k.jmeno=%s"; ps.append(sel_cli)
        if sel_yr!="Všechny": q+=" AND SUBSTRING(f.datum_vystaveni,1,4)=%s"; ps.append(sel_yr)
        pp=get_pool(); conn=pp.getconn()
        try: df_f=pd.read_sql(q+" ORDER BY f.id DESC LIMIT 30",conn,params=ps)
        finally: pp.putconn(conn)
        if search_q:
            sq=search_q.lower()
            df_f=df_f[df_f['jmeno'].str.lower().str.contains(sq,na=False)|df_f['cislo_full'].str.lower().str.contains(sq,na=False)|df_f['muj_popis'].fillna('').str.lower().str.contains(sq,na=False)]
        if df_f.empty: st.info("Žádné faktury.")
        
        for row in df_f.to_dict('records'):
            cf=row.get('cislo_full') or f"F{row['id']}"; paid=row['uhrazeno']
            is_ov=False
            try:
                if not paid and datetime.strptime(str(row['datum_splatnosti'])[:10],'%Y-%m-%d').date()<date.today(): is_ov=True
            except: pass
            tag='<span class="tag-paid">Zaplaceno</span>' if paid else ('<span class="tag-overdue">Po splatnosti</span>' if is_ov else '<span class="tag-due">Čeká na platbu</span>')
            with st.expander(f"{'✅' if paid else ('🔴' if is_ov else '⏳')}  {cf}  ·  {row['jmeno']}  ·  {row['castka_celkem']:,.0f} Kč"):
                st.markdown(f"<div style='margin-bottom:12px'>{tag} &nbsp; <span style='color:#334155;font-size:.78rem'>Splatnost: {fmt_d(row.get('datum_splatnosti',''))}</span></div>",unsafe_allow_html=True)
                c1,c2,c3=st.columns(3)
                if paid:
                    if c1.button("↩ Zrušit",key=f"u0_{row['id']}"): run_command("UPDATE faktury SET uhrazeno=0 WHERE id=?",(row['id'],)); cached_pdf.clear(); cached_isdoc.clear(); st.rerun()
                else:
                    if c1.button("✓ Zaplaceno",key=f"u1_{row['id']}"): run_command("UPDATE faktury SET uhrazeno=1 WHERE id=?",(row['id'],)); cached_pdf.clear(); cached_isdoc.clear(); st.rerun()
                
                # ------ Ošetření a vykreslení PDF tlačítka ------
                _tpl=get_nastaveni(uid).get('faktura_sablona',1) or 1
                rh=str(row)+str(_tpl); pdf_out=cached_pdf(row['id'],uid,is_pro,_tpl,rh)
                
                if isinstance(pdf_out, bytes): 
                    c2.download_button("↓ Stáhnout PDF", pdf_out, f"{cf}.pdf", "application/pdf", key=f"pdf_{row['id']}", type="primary")
                else:
                    c2.error(f"⚠️ Nelze vygenerovat: {pdf_out}")
                # ------------------------------------------------
                
                if is_pro:
                    isdoc_b=cached_isdoc(row['id'],uid,rh)
                    if isdoc_b: c2.download_button("↓ ISDOC",isdoc_b,f"{cf}.isdoc","application/xml",key=f"isd_{row['id']}")
                klient_info=run_query("SELECT email,jmeno FROM klienti WHERE id=?",(row['klient_id'],),single=True)
                klient_email=dict(klient_info).get('email','') if klient_info else ''
                if not paid and klient_email:
                    if c2.button("📨 Upomínka",key=f"rem_{row['id']}"):
                        body=(f"Dobry den,\n\nDovolujeme si Vas upomenout o neuhradenou fakturu c. {cf}\n"
                              f"Castka: {row['castka_celkem']:,.0f} Kc\n"
                              f"Splatnost: {fmt_d(row['datum_splatnosti'])}\n\n"
                              f"Prosime o uhrazeni na ucet.")
                        if send_mail(klient_email,f"Upominka platby – Faktura {cf}",body,pdf_out if isinstance(pdf_out,bytes) else None,f"{cf}.pdf"):
                            st.markdown('<div class="reminder-ok">✓ Upomínka odeslána na ' + klient_email + '</div>',unsafe_allow_html=True)
                        else:
                            st.warning("Nepodařilo se odeslat — zkontrolujte SMTP v Nastavení.")
                ekey=f"edit_f_{row['id']}"
                if ekey not in st.session_state: st.session_state[ekey]=False
                if c3.button("✏️ Upravit",key=f"be_{row['id']}"): st.session_state[ekey]=True; st.rerun()
                if st.session_state[ekey]:
                    with st.form(f"fe_{row['id']}"):
                        nd=st.date_input("Splatnost",pd.to_datetime(row['datum_splatnosti'])); nm=st.text_input("Popis",row['muj_popis'] or ""); nut=st.text_input("Úvodní text",row['uvodni_text'] or "")
                        pp2=get_pool(); conn2=pp2.getconn()
                        try: ci=pd.read_sql('SELECT nazev as "Popis položky",cena as "Cena" FROM faktura_polozky WHERE faktura_id=%s',conn2,params=(row['id'],))
                        finally: pp2.putconn(conn2)
                        ned=st.data_editor(ci,num_rows="dynamic",use_container_width=True)
                        if st.form_submit_button("Uložit změny"):
                            nt=float(pd.to_numeric(ned["Cena"],errors='coerce').fillna(0).sum())
                            run_command("UPDATE faktury SET datum_splatnosti=?,muj_popis=?,castka_celkem=?,uvodni_text=? WHERE id=?",(nd,nm,nt,nut,row['id']))
                            run_command("DELETE FROM faktura_polozky WHERE faktura_id=?",(row['id'],))
                            for _,rw in ned.iterrows():
                                if rw.get("Popis položky"): run_command("INSERT INTO faktura_polozky (faktura_id,nazev,cena) VALUES (?,?,?)",(row['id'],rw["Popis položky"],float(rw.get("Cena",0))))
                            st.session_state[ekey]=False; cached_pdf.clear(); cached_isdoc.clear(); st.rerun()
                if c3.button("🔄 Duplikovat",key=f"dup_{row['id']}"):
                    nn,nf,_=next_num(row['kategorie_id'],uid)
                    nfid=run_command("INSERT INTO faktury (user_id,cislo,cislo_full,klient_id,kategorie_id,datum_vystaveni,datum_splatnosti,castka_celkem,variabilni_symbol,uvodni_text,muj_popis) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(uid,nn,nf,row['klient_id'],row['kategorie_id'],date.today(),date.today()+timedelta(14),row['castka_celkem'],re.sub(r"\D","",nf),row['uvodni_text'],row['muj_popis']))
                    for it in run_query("SELECT * FROM faktura_polozky WHERE faktura_id=?",(row['id'],)): run_command("INSERT INTO faktura_polozky (faktura_id,nazev,cena) VALUES (?,?,?)",(nfid,it['nazev'],it['cena']))
                    run_command("UPDATE kategorie SET aktualni_cislo=aktualni_cislo+1 WHERE id=?",(row['kategorie_id'],)); cached_pdf.clear(); cached_isdoc.clear(); st.success(f"Duplikát {nf} vytvořen!"); st.rerun()
                if st.button("🗑 Smazat",key=f"del_f_{row['id']}"): run_command("DELETE FROM faktury WHERE id=?",(row['id'],)); cached_pdf.clear(); cached_isdoc.clear(); st.rerun()

    # ================================
    # NABÍDKY
    # ================================
    elif "Nabídky" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">📋</div><div class="sec-title">Cenové nabídky</div></div>',unsafe_allow_html=True)
        st.markdown("Vytvořte nezávaznou nabídku — klient ji přijme a vy ji jedním kliknutím převedete na fakturu.")

        with st.expander("➕  Nová cenová nabídka"):
            pp_db=get_pool(); conn_db=pp_db.getconn()
            try:
                kli=pd.read_sql("SELECT id,jmeno FROM klienti WHERE user_id=%s",conn_db,params=(uid,))
                kat=pd.read_sql("SELECT id,nazev FROM kategorie WHERE user_id=%s",conn_db,params=(uid,))
            finally: pp_db.putconn(conn_db)
            if kli.empty: st.warning("Nejprve přidejte klienta.")
            else:
                with st.form("nab_form"):
                    c1,c2=st.columns(2)
                    nab_kl=c1.selectbox("Klient",kli['jmeno'],key="nab_kl")
                    nab_kat="Obecná"
                    if not kat.empty: nab_kat=c2.selectbox("Kategorie",kat['nazev'],key="nab_kat")
                    c3,c4=st.columns(2)
                    nab_dv=c3.date_input("Datum vystavení",date.today(),key="nab_dv")
                    nab_pl=c4.date_input("Platnost nabídky do",date.today()+timedelta(30),key="nab_pl")
                    nab_txt=st.text_input("Úvodní text","Nabízíme Vám naše služby za následujících podmínek:")
                    nab_poz=st.text_input("Interní poznámka","")
                    nab_items=st.data_editor(pd.DataFrame(columns=["Popis položky","Cena"]),num_rows="dynamic",use_container_width=True,key="nab_items_ed")
                    if st.form_submit_button("Uložit nabídku"):
                        if not kli[kli['jmeno']==nab_kl].empty:
                            nkid=int(kli[kli['jmeno']==nab_kl]['id'].values[0])
                            ncid=int(kat[kat['nazev']==nab_kat]['id'].values[0]) if not kat.empty else None
                            _,nfull,_=next_num(ncid,uid) if ncid else (1,"NAB-"+str(date.today().year)+"-"+str(random.randint(100,999)),"")
                            ntotal=float(pd.to_numeric(nab_items["Cena"],errors='coerce').fillna(0).sum()) if not nab_items.empty else 0.0
                            nab_id=run_command("INSERT INTO nabidky (user_id,cislo_full,klient_id,kategorie_id,datum_vystaveni,datum_platnosti,castka_celkem,uvodni_text,poznamka,stav) VALUES (?,?,?,?,?,?,?,?,?,'otevrena')",
                                              (uid,nfull.replace("FV","NAB"),nkid,ncid,nab_dv,nab_pl,ntotal,nab_txt,nab_poz))
                            if not nab_items.empty:
                                for _,r2 in nab_items.iterrows():
                                    if r2.get("Popis položky"): run_command("INSERT INTO nabidka_polozky (nabidka_id,nazev,cena) VALUES (?,?,?)",(nab_id,r2["Popis položky"],float(r2.get("Cena",0))))
                            st.success(f"Nabídka {nfull.replace('FV','NAB')} uložena!"); st.rerun()

        st.divider()
        nabs=run_query("SELECT n.*,k.jmeno FROM nabidky n JOIN klienti k ON n.klient_id=k.id WHERE n.user_id=? ORDER BY n.id DESC",(uid,))
        stav_map={"otevrena":("🔵","Otevřená","q-open"),"prijata":("✅","Přijata","q-accepted"),"odmitnuta":("❌","Odmítnuta","q-declined"),"fakturovana":("🟡","Fakturována","q-invoiced")}
        if not nabs:
            st.info("Zatím žádné nabídky. Vytvořte první výše.")
        for nb in nabs:
            nb=dict(nb)
            ico_s,lbl_s,cls_s=stav_map.get(nb.get('stav','otevrena'),("🔵","?","q-open"))
            expired=""
            try:
                if datetime.strptime(str(nb['datum_platnosti'])[:10],'%Y-%m-%d').date()<date.today() and nb.get('stav')=='otevrena':
                    expired=' <span style="color:#f87171;font-size:.7rem">· Vypršela</span>'
            except: pass
            st.markdown(f"""
<div class="quote-card">
  <div class="quote-header">
    <div>
      <div class="quote-num">{nb.get('cislo_full','')} &nbsp; <span class="q-tag {cls_s}">{ico_s} {lbl_s}</span>{expired}</div>
      <div class="quote-client">{nb['jmeno']} &nbsp;·&nbsp; Platnost do: {fmt_d(nb.get('datum_platnosti',''))}</div>
    </div>
    <div class="quote-amt">{nb.get('castka_celkem',0):,.0f} Kč</div>
  </div>
</div>""",unsafe_allow_html=True)
            with st.expander(f"  Detaily nabídky {nb.get('cislo_full','')}"):
                c1,c2,c3,c4=st.columns(4)
                new_stav=c1.selectbox("Stav",["otevrena","prijata","odmitnuta"],format_func=lambda x:{"otevrena":"Otevřená","prijata":"Přijata","odmitnuta":"Odmítnuta","fakturovana":"Fakturována"}[x],index=["otevrena","prijata","odmitnuta"].index(nb.get('stav','otevrena')) if nb.get('stav') in ["otevrena","prijata","odmitnuta"] else 0,key=f"nst_{nb['id']}")
                if c2.button("Uložit stav",key=f"nst_save_{nb['id']}"): run_command("UPDATE nabidky SET stav=? WHERE id=?",(new_stav,nb['id'])); st.rerun()
                if nb.get('stav') in ('otevrena','prijata') and not nb.get('faktura_id'):
                    if c3.button("→ Převést na fakturu",key=f"nab2fak_{nb['id']}",type="primary"):
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
                if c4.button("🗑 Smazat",key=f"del_nab_{nb['id']}"): run_command("DELETE FROM nabidky WHERE id=?",(nb['id'],)); run_command("DELETE FROM nabidka_polozky WHERE nabidka_id=?",(nb['id'],)); st.rerun()
                nab_its=run_query("SELECT * FROM nabidka_polozky WHERE nabidka_id=?",(nb['id'],)) or []
                if nab_its:
                    for it in nab_its: st.markdown(f"- {it['nazev']} — **{it['cena']:,.0f} Kč**")
                if nb.get('poznamka'): st.caption(f"Poznámka: {nb['poznamka']}")

    # ================================
    # CASHFLOW
    # ================================
    elif "Cashflow" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">💰</div><div class="sec-title">Cashflow & Prognóza</div></div>',unsafe_allow_html=True)
        st.markdown("Přehled očekávaných příjmů a výdajů pro nejbližší tři měsíce.")

        today = date.today()

        inc_30=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0 AND datum_splatnosti BETWEEN ? AND ?",(uid,today.isoformat(),(today+timedelta(30)).isoformat()),True)['sum'] or 0
        inc_60=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0 AND datum_splatnosti BETWEEN ? AND ?",(uid,(today+timedelta(31)).isoformat(),(today+timedelta(60)).isoformat()),True)['sum'] or 0
        inc_90=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0 AND datum_splatnosti BETWEEN ? AND ?",(uid,(today+timedelta(61)).isoformat(),(today+timedelta(90)).isoformat()),True)['sum'] or 0
        overdue_cf=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0 AND datum_splatnosti < ?",(uid,today.isoformat()),True)['sum'] or 0
        paid_month=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=1 AND SUBSTRING(datum_splatnosti,1,7)=?",(uid,today.strftime('%Y-%m')),True)['sum'] or 0

        st.markdown(f"""
<div class="cf-grid">
  <div class="cf-card neg"><div class="cf-lbl">⚠️ Po splatnosti</div><div class="cf-val neg">{overdue_cf:,.0f} Kč</div><div class="cf-sub">okamžitě splatné</div></div>
  <div class="cf-card pos"><div class="cf-lbl">✓ Zaplaceno tento měsíc</div><div class="cf-val pos">{paid_month:,.0f} Kč</div><div class="cf-sub">{today.strftime('%B %Y')}</div></div>
  <div class="cf-card"><div class="cf-lbl">📅 Výhled 90 dní</div><div class="cf-val neu">{inc_30+inc_60+inc_90:,.0f} Kč</div><div class="cf-sub">očekávané příjmy</div></div>
</div>""",unsafe_allow_html=True)

        st.divider()

        tab30,tab60,tab90=st.tabs([f"  30 dní  ({inc_30:,.0f} Kč)",f"  31–60 dní  ({inc_60:,.0f} Kč)",f"  61–90 dní  ({inc_90:,.0f} Kč)"])

        def render_cf_tab(d_from, d_to):
            rows=run_query(
                "SELECT f.castka_celkem,f.datum_splatnosti,f.cislo_full,k.jmeno "
                "FROM faktury f JOIN klienti k ON f.klient_id=k.id "
                "WHERE f.user_id=? AND f.uhrazeno=0 AND f.datum_splatnosti BETWEEN ? AND ? "
                "ORDER BY f.datum_splatnosti ASC",
                (uid, d_from.isoformat(), d_to.isoformat()))
            if not rows:
                st.info("Žádné faktury v tomto období.")
                return
            for r in rows:
                r=dict(r)
                try: dl=(datetime.strptime(str(r['datum_splatnosti'])[:10],'%Y-%m-%d').date()-today).days; dtxt=f"za {dl} dní"
                except: dtxt=""
                st.markdown(f'<div class="cf-row"><div><div class="cf-row-name">{r["jmeno"]} &nbsp; <span style="color:#334155">{r.get("cislo_full","")}</span></div><div class="cf-row-due">Splatnost: {fmt_d(r["datum_splatnosti"])} ({dtxt})</div></div><div class="cf-row-amt" style="color:#34d399">{r["castka_celkem"]:,.0f} Kč</div></div>',unsafe_allow_html=True)

        with tab30: render_cf_tab(today, today+timedelta(30))
        with tab60: render_cf_tab(today+timedelta(31), today+timedelta(60))
        with tab90: render_cf_tab(today+timedelta(61), today+timedelta(90))

        st.divider()
        st.subheader("📈 Příjmy za posledních 6 měsíců")
        pp_db=get_pool(); conn_db=pp_db.getconn()
        try:
            df_cf=pd.read_sql(
                "SELECT datum_vystaveni, castka_celkem, uhrazeno FROM faktury WHERE user_id=%s "
                "AND datum_vystaveni >= %s",
                conn_db, params=(uid, (today.replace(day=1)-timedelta(days=150)).isoformat()))
        finally: pp_db.putconn(conn_db)
        if not df_cf.empty:
            df_cf['dt']=pd.to_datetime(df_cf['datum_vystaveni'])
            df_paid=df_cf[df_cf['uhrazeno']==1].groupby(df_cf['dt'].dt.to_period('M'))['castka_celkem'].sum()
            df_issued=df_cf.groupby(df_cf['dt'].dt.to_period('M'))['castka_celkem'].sum()
            chart_df=pd.DataFrame({'Uhrazeno':df_paid,'Vystaveno':df_issued}).fillna(0)
            chart_df.index=chart_df.index.astype(str)
            st.bar_chart(chart_df)
        else:
            st.info("Žádná data k zobrazení.")

        st.divider()
        st.subheader("💸 Přidejte plánovaný výdaj")
        with st.form("cf_vydaj"):
            c1,c2,c3=st.columns(3)
            cv_d=c1.date_input("Datum",today+timedelta(30)); cv_p=c2.text_input("Popis"); cv_a=c3.number_input("Částka",min_value=0.0,step=100.0)
            cv_k=st.selectbox("Kategorie",["Provoz","Materiál","Služby","Ostatní"])
            if st.form_submit_button("+ Přidat výdaj"):
                run_command("INSERT INTO vydaje (user_id,datum,popis,castka,kategorie) VALUES (?,?,?,?,?)",(uid,cv_d,cv_p,cv_a,cv_k)); st.success("Uloženo"); st.rerun()

    # ================================
    # ČASOVAČ
    # ================================
    elif "Časovač" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">⏱️</div><div class="sec-title">Časovač hodin</div></div>',unsafe_allow_html=True)
        st.markdown("Měřte čas na projektech a přímočaře ho převeďte na fakturační položku.")

        st.markdown('<div class="timer-card">',unsafe_allow_html=True)
        if st.session_state.timer_start is None:
            c1,c2=st.columns(2)
            proj=c1.text_input("Název projektu / popis práce",key="timer_proj_input")
            sazba=c2.number_input("Hodinová sazba (Kč)",min_value=0,value=500,step=50,key="timer_sazba_input")
            if st.button("▶ Spustit měření",type="primary"):
                if proj:
                    st.session_state.timer_start=datetime.now().isoformat()
                    st.session_state.timer_projekt=proj
                    st.session_state.timer_sazba=sazba
                    st.rerun()
                else: st.warning("Zadejte název projektu.")
        else:
            start_dt=datetime.fromisoformat(st.session_state.timer_start)
            elapsed=(datetime.now()-start_dt).total_seconds()
            h=int(elapsed)//3600; m=(int(elapsed)%3600)//60; s=int(elapsed)%60
            st.markdown(f'<div class="timer-label">Měří se: {st.session_state.timer_projekt}</div>',unsafe_allow_html=True)
            st.markdown(f'<div class="timer-display">{h:02d}:{m:02d}:{s:02d}</div>',unsafe_allow_html=True)
            mins=elapsed/60
            odh=mins/60*st.session_state.timer_sazba
            st.markdown(f'<div style="color:#64748b;font-size:.85rem;text-align:center">Odhadovaná částka: <b style="color:#fbbf24">{odh:,.0f} Kč</b> při {st.session_state.timer_sazba} Kč/hod</div>',unsafe_allow_html=True)
            c1,c2=st.columns(2)
            if c1.button("⏹ Zastavit a uložit",type="primary"):
                run_command("INSERT INTO casovac (user_id,projekt,start_ts,end_ts,trvani_min,sazba,poznamka) VALUES (?,?,?,?,?,?,?)",
                           (uid,st.session_state.timer_projekt,st.session_state.timer_start,datetime.now().isoformat(),round(mins,2),st.session_state.timer_sazba,""))
                st.session_state.timer_start=None; st.success(f"Uloženo: {fmt_min(mins)} → {odh:,.0f} Kč"); st.rerun()
            if c2.button("✕ Zahodit"):
                st.session_state.timer_start=None; st.rerun()
        st.markdown('</div>',unsafe_allow_html=True)

        st.divider()
        st.subheader("📋 Záznamy")
        pp=get_pool(); conn=pp.getconn()
        try: df_tim=pd.read_sql("SELECT c.*,k.jmeno as klient FROM casovac c LEFT JOIN klienti k ON c.klient_id=k.id WHERE c.user_id=%s ORDER BY c.id DESC LIMIT 50",conn,params=(uid,))
        finally: pp.putconn(conn)

        if not df_tim.empty:
            df_tim['cas']=df_tim['trvani_min'].apply(fmt_min)
            df_tim['castka']=(df_tim['trvani_min']/60*df_tim['sazba']).round(0)
            df_tim['fakturovano']=df_tim['fakturovano'].map({0:'Ne',1:'Ano ✓'})
            st.dataframe(df_tim[['start_ts','projekt','cas','castka','fakturovano']].rename(columns={'start_ts':'Začátek','projekt':'Projekt','cas':'Čas','castka':'Kč','fakturovano':'Fakturováno'}),hide_index=True,use_container_width=True)

            st.markdown("**Převést záznamy do nové faktury:**")
            nefak=df_tim[df_tim['fakturovano']=='Ne']
            if not nefak.empty:
                sel_ids=st.multiselect("Vyberte záznamy",nefak.apply(lambda x:f"{x['projekt']} – {x['cas']} ({x['castka']:,.0f} Kč)",axis=1).tolist())
                if sel_ids and st.button("→ Přidat jako položky faktury"):
                    for s in sel_ids:
                        proj_name=s.split(" – ")[0]; match=nefak[nefak['projekt']==proj_name]
                        if not match.empty:
                            row2=match.iloc[0]; new_row=pd.DataFrame([{"Popis položky":f"Práce: {row2['projekt']}","Cena":round(row2['castka'],0)}])
                            st.session_state.items_df=pd.concat([st.session_state.items_df,new_row],ignore_index=True)
                    st.success("Položky přidány! Přejděte do Faktur a vystavte."); st.rerun()
        else:
            st.info("Žádné záznamy. Spusťte měření výše.")

        st.divider()
        st.subheader("🗂 Šablony položek")
        st.markdown("Uložte opakované položky pro rychlé přidání do faktury.")
        with st.form("sbl_form"):
            sc1,sc2,sc3=st.columns([3,2,1])
            sn=sc1.text_input("Název položky",placeholder="Konzultace, Vývoj webu…")
            sp=sc2.number_input("Výchozí cena (Kč)",min_value=0.0,step=100.0)
            if sc3.form_submit_button("+ Přidat"):
                if sn: run_command("INSERT INTO item_sablony (user_id,nazev,cena) VALUES (?,?,?)",(uid,sn,sp)); st.rerun()
        for s in (run_query("SELECT * FROM item_sablony WHERE user_id=?",(uid,)) or []):
            c1,c2=st.columns([4,1])
            c1.markdown(f"**{s['nazev']}** — {s['cena']:,.0f} Kč")
            if c2.button("🗑",key=f"delsbl_{s['id']}"): run_command("DELETE FROM item_sablony WHERE id=? AND user_id=?",(s['id'],uid)); st.rerun()

    # ================================
    # OPAKOVANÉ
    # ================================
    elif "Opakované" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">🔄</div><div class="sec-title">Opakované faktury</div></div>',unsafe_allow_html=True)
        st.markdown("Nastavte pravidelné fakturování klientů — měsíčně, čtvrtletně nebo ročně. Systém vás upozorní a vy fakturu vystavíte jedním kliknutím.")

        with st.expander("➕  Nové opakované nastavení"):
            pp=get_pool(); conn=pp.getconn()
            try:
                kli=pd.read_sql("SELECT id,jmeno FROM klienti WHERE user_id=%s",conn,params=(uid,))
                kat=pd.read_sql("SELECT id,nazev FROM kategorie WHERE user_id=%s",conn,params=(uid,))
            finally: pp.putconn(conn)
            if kli.empty: st.warning("Nejprve přidejte klienta.")
            else:
                with st.form("op_form"):
                    c1,c2=st.columns(2)
                    op_name=c1.text_input("Název (interní)",placeholder="Měsíční správa webu")
                    op_interval=c2.selectbox("Interval",["mesicne","ctvrtletne","pololetne","rocne"],format_func=lambda x:{"mesicne":"Měsíčně","ctvrtletne":"Čtvrtletně","pololetne":"Pololetně","rocne":"Ročně"}[x])
                    c3,c4=st.columns(2)
                    op_kl=c3.selectbox("Klient",kli['jmeno'])
                    op_kat="Obecná"
                    if not kat.empty: op_kat=c4.selectbox("Kategorie",kat['nazev'])
                    op_text=st.text_input("Úvodní text faktury","Fakturujeme Vám pravidelnou platbu:")
                    st.markdown("**Položky:**")
                    op_items=st.data_editor(pd.DataFrame(columns=["Popis položky","Cena"]),num_rows="dynamic",use_container_width=True,key="op_items_ed")
                    if st.form_submit_button("Uložit nastavení"):
                        if op_name and not kli[kli['jmeno']==op_kl].empty:
                            kid=int(kli[kli['jmeno']==op_kl]['id'].values[0])
                            cid=int(kat[kat['nazev']==op_kat]['id'].values[0]) if not kat.empty else None
                            items_data=op_items.to_dict(orient='records') if not op_items.empty else []
                            run_command("INSERT INTO opakujici (user_id,nazev,klient_id,kategorie_id,interval_typ,posledni_vytvoreni,aktivni,uvodni_text,polozky_json) VALUES (?,?,?,?,?,?,1,?,?)",
                                       (uid,op_name,kid,cid,op_interval,None,op_text,json.dumps(items_data,default=str)))
                            st.success("Nastavení uloženo!"); st.rerun()
                        else: st.error("Vyplňte název a vyberte klienta.")

        st.divider()
        opak=run_query("SELECT o.*,k.jmeno FROM opakujici o JOIN klienti k ON o.klient_id=k.id WHERE o.user_id=? ORDER BY o.id DESC",(uid,))
        if not opak:
            st.info("Žádná opakovaná fakturace. Přidejte nastavení výše.")
        else:
            interval_map={"mesicne":30,"ctvrtletne":91,"pololetne":182,"rocne":365}
            interval_label={"mesicne":"Měsíčně","ctvrtletne":"Čtvrtletně","pololetne":"Pololetně","rocne":"Ročně"}
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
                else:
                    days_left=0; due_status="overdue"; next_d=date.today()

                status_color={"overdue":"#f87171","soon":"#fbbf24","ok":"#34d399"}[due_status]
                status_text={"overdue":"Čeká na vystavení!","soon":f"Splatné za {days_left} dní","ok":f"Splatné za {days_left} dní"}[due_status]

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
                        if c1.button("📄 Vystavit nyní",key=f"op_vystavit_{op['id']}",type="primary"):
                            kat_all=run_query("SELECT * FROM kategorie WHERE user_id=?",(uid,))
                            cid=op.get('kategorie_id')
                            if not cid and kat_all: cid=kat_all[0]['id']
                            if cid:
                                _,full,_=next_num(cid,uid)
                                total_items=[]
                                try: total_items=json.loads(op.get('polozky_json','[]'))
                                except: pass
                                total=sum(float(it.get('Cena',0)) for it in total_items)
                                fid=run_command("INSERT INTO faktury (user_id,cislo_full,klient_id,kategorie_id,datum_vystaveni,datum_splatnosti,castka_celkem,variabilni_symbol,uvodni_text) VALUES (?,?,?,?,?,?,?,?,?)",
                                              (uid,full,op['klient_id'],cid,date.today(),date.today()+timedelta(14),total,re.sub(r"\D","",full),op.get('uvodni_text','')))
                                for it in total_items:
                                    if it.get('Popis položky'): run_command("INSERT INTO faktura_polozky (faktura_id,nazev,cena) VALUES (?,?,?)",(fid,it['Popis položky'],float(it.get('Cena',0))))
                                run_command("UPDATE kategorie SET aktualni_cislo=aktualni_cislo+1 WHERE id=?",(cid,))
                                run_command("UPDATE opakujici SET posledni_vytvoreni=? WHERE id=?",(date.today().isoformat(),op['id']))
                                cached_pdf.clear(); st.success(f"Faktura {full} vystavena!"); st.rerun()
                    act_val=bool(op.get('aktivni',1))
                    if c2.button("⏸ Pozastavit" if act_val else "▶ Aktivovat",key=f"op_tog_{op['id']}"):
                        run_command("UPDATE opakujici SET aktivni=? WHERE id=?",(0 if act_val else 1,op['id'])); st.rerun()
                    if c3.button("🗑 Smazat",key=f"op_del_{op['id']}"): run_command("DELETE FROM opakujici WHERE id=?",(op['id'],)); st.rerun()
                    if op.get('polozky_json'):
                        try:
                            items=json.loads(op['polozky_json'])
                            if items:
                                st.markdown("**Položky faktury:**")
                                for it in items: st.markdown(f"- {it.get('Popis položky','')} — {float(it.get('Cena',0)):,.0f} Kč")
                        except: pass

    # ================================
    # DASHBOARD
    # ================================
    elif "Dashboard" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">📊</div><div class="sec-title">Přehled podnikání</div></div>',unsafe_allow_html=True)
        tr=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?",(uid,),True)['sum'] or 0
        tp=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=1",(uid,),True)['sum'] or 0
        td=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0",(uid,),True)['sum'] or 0
        cnt=run_query("SELECT COUNT(*) FROM faktury WHERE user_id=?",(uid,),True)['count'] or 0
        t_hours=run_query("SELECT SUM(trvani_min) FROM casovac WHERE user_id=?",(uid,),True)['sum'] or 0
        c1,c2,c3,c4,c5=st.columns(5)
        c1.metric("Celkový obrat",f"{tr:,.0f} Kč"); c2.metric("Zaplaceno",f"{tp:,.0f} Kč",delta=f"{int(tp/tr*100) if tr else 0}%")
        c3.metric("Čeká na platbu",f"{td:,.0f} Kč",delta="-",delta_color="inverse"); c4.metric("Faktur celkem",cnt)
        c5.metric("Hodin v časovači",fmt_min(t_hours))
        st.divider()
        gc1,gc2=st.columns([2,1])
        pp=get_pool(); conn=pp.getconn()
        try:
            with gc1:
                st.subheader("Vývoj v čase")
                df_g=pd.read_sql("SELECT datum_vystaveni,castka_celkem FROM faktury WHERE user_id=%s",conn,params=(uid,))
                if not df_g.empty:
                    df_g['datum']=pd.to_datetime(df_g['datum_vystaveni'])
                    mo=df_g.groupby(df_g['datum'].dt.to_period('M'))['castka_celkem'].sum(); mo.index=mo.index.astype(str)
                    st.bar_chart(mo,color="#fbbf24")
                else: st.info("Žádná data.")
            with gc2:
                st.subheader("TOP 5 klientů")
                df_t=pd.read_sql("SELECT k.jmeno,SUM(f.castka_celkem) as celkem FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=%s GROUP BY k.jmeno ORDER BY celkem DESC LIMIT 5",conn,params=(uid,))
                if not df_t.empty: st.dataframe(df_t.set_index('jmeno').style.format("{:,.0f} Kč"),use_container_width=True)
            st.subheader("Příjmy dle kategorií")
            df_c=pd.read_sql("SELECT k.nazev,SUM(f.castka_celkem) as celkem FROM faktury f JOIN kategorie k ON f.kategorie_id=k.id WHERE f.user_id=%s GROUP BY k.nazev",conn,params=(uid,))
            if not df_c.empty: st.bar_chart(df_c.set_index('nazev'))
        finally: pp.putconn(conn)

    # ================================
    # DANĚ
    # ================================
    elif "Daně" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">🏛️</div><div class="sec-title">Daňová kalkulačka</div></div>',unsafe_allow_html=True)
        years=[r['substring'] for r in run_query("SELECT DISTINCT SUBSTRING(datum_vystaveni,1,4) as substring FROM faktury WHERE user_id=?",(uid,))]
        cy=str(date.today().year)
        if cy not in years: years.append(cy)
        c1,c2=st.columns(2)
        sty=c1.selectbox("Rok",sorted(list(set(years)),reverse=True))
        po=c2.selectbox("Typ činnosti",["80% – Řemeslné živnosti, zemědělství","60% – Ostatní živnosti (nejčastější)","40% – Svobodná povolání, autorská práva","30% – Pronájem majetku"],index=1)
        pp_pct=int(po.split("%")[0])/100
        inc=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND SUBSTRING(datum_vystaveni,1,4)=?",(uid,sty),True)['sum'] or 0
        rex=run_query("SELECT SUM(castka) FROM vydaje WHERE user_id=? AND SUBSTRING(datum,1,4)=?",(uid,sty),True)['sum'] or 0
        fex=inc*pp_pct; tbr=max(0,inc-rex); tbf=max(0,inc-fex); taxr=tbr*.15; taxf=tbf*.15; diff=taxf-taxr
        st.markdown(f'<div class="callout">Příjmy za rok {sty}: <span>{inc:,.0f} Kč</span></div>',unsafe_allow_html=True)
        c1,c2=st.columns(2)
        with c1: st.markdown(f'<div class="tax-c"><div class="tax-title">A) Skutečné výdaje</div><div class="tax-meta">Výdaje: {rex:,.0f} Kč · Základ: {tbr:,.0f} Kč</div><div class="tax-amt">{taxr:,.0f} Kč</div><div class="tax-sub">Daň 15 %</div></div>',unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="tax-c"><div class="tax-title">B) Paušál {int(pp_pct*100)} %</div><div class="tax-meta">Výdaje: {fex:,.0f} Kč · Základ: {tbf:,.0f} Kč</div><div class="tax-amt">{taxf:,.0f} Kč</div><div class="tax-sub">Daň 15 %</div></div>',unsafe_allow_html=True)
        st.divider()
        if taxr<taxf: st.success(f"🏆 Výhodnější jsou SKUTEČNÉ výdaje — ušetříte {diff:,.0f} Kč.")
        elif taxf<taxr: st.success(f"🏆 Výhodnější je PAUŠÁL — ušetříte {abs(diff):,.0f} Kč.")
        else: st.info("Obě varianty vychází stejně.")

    # ================================
    # VÝDAJE
    # ================================
    elif "Výdaje" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">💸</div><div class="sec-title">Evidence výdajů</div></div>',unsafe_allow_html=True)
        with st.form("exp"):
            c1,c2=st.columns(2); ed=c1.date_input("Datum",date.today()); ep=c2.text_input("Popis")
            c3,c4=st.columns(2); ea=c3.number_input("Částka (Kč)",min_value=0.0,step=100.0); ec=c4.selectbox("Kategorie",["Provoz","Materiál","Služby","Ostatní"])
            if st.form_submit_button("+ Přidat"):
                run_command("INSERT INTO vydaje (user_id,datum,popis,castka,kategorie) VALUES (?,?,?,?,?)",(uid,ed,ep,ea,ec)); st.success("Uloženo"); st.rerun()
        pp=get_pool(); conn=pp.getconn()
        try: vy=pd.read_sql("SELECT * FROM vydaje WHERE user_id=%s ORDER BY datum DESC",conn,params=(uid,))
        finally: pp.putconn(conn)
        if not vy.empty:
            st.dataframe(vy[['id','datum','popis','kategorie','castka']],hide_index=True,use_container_width=True)
            cv=vy['castka'].sum(); cp=run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?",(uid,),True)['sum'] or 0
            c1,c2,c3=st.columns(3); c1.metric("Příjmy",f"{cp:,.0f} Kč"); c2.metric("Výdaje",f"{cv:,.0f} Kč",delta=-cv); c3.metric("Hrubý zisk",f"{cp-cv:,.0f} Kč")
            vl=vy.apply(lambda x:f"ID {x['id']}: {x['datum']} – {x['popis']} ({x['castka']} Kč)",axis=1).tolist()
            sd=st.selectbox("Vyberte ke smazání",vl)
            if st.button("🗑 Smazat"):
                did=int(sd.split(":")[0].replace("ID ",""))
                run_command("DELETE FROM vydaje WHERE id=? AND user_id=?",(did,uid)); st.rerun()

    # ================================
    # KLIENTI
    # ================================
    elif "Klienti" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">👥</div><div class="sec-title">Klienti</div></div>',unsafe_allow_html=True)
        rid=st.session_state.form_reset_id
        with st.expander("➕  Přidat klienta"):
            c1,c2=st.columns([3,1]); ico_in=c1.text_input("IČO",key=f"ico_{rid}")
            if c2.button("Načíst ARES",key=f"ares_{rid}"):
                d=get_ares(ico_in)
                if d: st.session_state.ares_data=d; st.success("Načteno ✓")
                else: st.error("Nenalezeno v ARES")
            ad=st.session_state.ares_data
            with st.form("fc"):
                j=st.text_input("Jméno / Firma",ad.get('jmeno','')); a=st.text_area("Adresa",ad.get('adresa',''))
                c1,c2=st.columns(2); i=c1.text_input("IČ",ad.get('ico','')); d2=c2.text_input("DIČ",ad.get('dic',''))
                pz=st.text_area("Poznámka")
                if st.form_submit_button("Uložit"):
                    run_command("INSERT INTO klienti (user_id,jmeno,adresa,ico,dic,poznamka) VALUES (?,?,?,?,?,?)",(uid,j,a,i,d2,pz))
                    reset_forms(); cached_pdf.clear(); st.rerun()
        for k in run_query("SELECT * FROM klienti WHERE user_id=?",(uid,)):
            with st.expander(f"◆  {k['jmeno']}"):
                if k['poznamka']: st.info(k['poznamka'])
                ek=f"edit_k_{k['id']}"
                if ek not in st.session_state: st.session_state[ek]=False
                c1,c2=st.columns(2)
                if c1.button("✏️ Upravit",key=f"bek_{k['id']}"): st.session_state[ek]=True; st.rerun()
                if c2.button("🗑 Smazat",key=f"bdk_{k['id']}"): run_command("DELETE FROM klienti WHERE id=?",(k['id'],)); st.rerun()
                if st.session_state[ek]:
                    with st.form(f"fke_{k['id']}"):
                        nj=st.text_input("Jméno",k['jmeno']); na=st.text_area("Adresa",k['adresa'])
                        ni=st.text_input("IČ",k['ico']); nd=st.text_input("DIČ",k['dic']); np=st.text_area("Poznámka",k['poznamka'])
                        if st.form_submit_button("Uložit"):
                            run_command("UPDATE klienti SET jmeno=?,adresa=?,ico=?,dic=?,poznamka=? WHERE id=?",(nj,na,ni,nd,np,k['id']))
                            st.session_state[ek]=False; cached_pdf.clear(); st.rerun()

    # ================================
    # KATEGORIE
    # ================================
    elif "Kategorie" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">🏷️</div><div class="sec-title">Kategorie</div></div>',unsafe_allow_html=True)
        if not is_pro:
            st.markdown('<div class="pro-card"><h3>🔒 Funkce PRO verze</h3><p style="color:#64748b">Aktivujte v Nastavení.</p></div>',unsafe_allow_html=True)
        else:
            with st.expander("➕  Nová kategorie"):
                with st.form("fcat"):
                    c1,c2=st.columns(2); n=c1.text_input("Název"); p=c2.text_input("Prefix")
                    c3,c4=st.columns(2); s=c3.number_input("Start č.",1); c=c4.color_picker("Barva akcentu (na faktuře)")
                    l=st.file_uploader("Logo (PNG/JPG)")
                    if st.form_submit_button("Uložit"):
                        run_command("INSERT INTO kategorie (user_id,nazev,prefix,aktualni_cislo,barva,logo_blob) VALUES (?,?,?,?,?,?)",(uid,n,p,s,c,proc_logo(l))); cached_pdf.clear(); st.rerun()
        for k in run_query("SELECT * FROM kategorie WHERE user_id=?",(uid,)):
            with st.expander(f"◆  {k['nazev']}  ·  {k['prefix']}"):
                if k['logo_blob']: st.image(bytes(k['logo_blob']),width=80)
                ck=f"edit_cat_{k['id']}"
                if ck not in st.session_state: st.session_state[ck]=False
                c1,c2=st.columns(2)
                if is_pro and c1.button("✏️ Upravit",key=f"bec_{k['id']}"): st.session_state[ck]=True; st.rerun()
                if c2.button("🗑 Smazat",key=f"bdc_{k['id']}"): run_command("DELETE FROM kategorie WHERE id=?",(k['id'],)); cached_pdf.clear(); st.rerun()
                if st.session_state[ck]:
                    with st.form(f"feck_{k['id']}"):
                        c1,c2=st.columns(2); nn=c1.text_input("Název",k['nazev']); np=c2.text_input("Prefix",k['prefix'])
                        c3,c4=st.columns(2); ns=c3.number_input("Číslo",value=k['aktualni_cislo']); nc=c4.color_picker("Barva",k['barva'])
                        nl=st.file_uploader("Nové logo",key=f"ul_{k['id']}")
                        if st.form_submit_button("Uložit"):
                            if nl: run_command("UPDATE kategorie SET nazev=?,prefix=?,aktualni_cislo=?,barva=?,logo_blob=? WHERE id=?",(nn,np,ns,nc,proc_logo(nl),k['id']))
                            else:  run_command("UPDATE kategorie SET nazev=?,prefix=?,aktualni_cislo=?,barva=? WHERE id=?",(nn,np,ns,nc,k['id']))
                            st.session_state[ck]=False; cached_pdf.clear(); st.rerun()

    # ================================
    # NASTAVENÍ
    # ================================
    elif "Nastavení" in menu:
        st.markdown('<div class="sec-hdr"><div class="sec-ico">⚙️</div><div class="sec-title">Nastavení</div></div>',unsafe_allow_html=True)
        res=run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1",(uid,),single=True); c=dict(res) if res else {}

        with st.expander("🔑  Licence & Přístup",expanded=True):
            valid,exp=check_lic(uid)
            if not valid:
                st.markdown('<div class="pro-card"><h3>🚀 Aktivujte PRO verzi</h3><div class="pro-feat-row"><div class="pro-feat">✦ Vlastní barvy faktury</div><div class="pro-feat">✦ Export ISDOC</div><div class="pro-feat">✦ Logo na faktuře</div><div class="pro-feat">✦ Cloud záloha</div></div><div class="pro-price">990 Kč / rok · jsem@michalkochtik.cz</div></div>',unsafe_allow_html=True)
                kk=st.text_input("Licenční klíč")
                if st.button("Aktivovat PRO →"):
                    kdb=run_query("SELECT * FROM licencni_klice WHERE kod=? AND pouzito_uzivatelem_id IS NULL",(kk,),True)
                    if kdb:
                        ne=date.today()+timedelta(days=kdb['dny_platnosti'])
                        run_command("UPDATE users SET license_key=?,license_valid_until=? WHERE id=?",(kk,ne,uid))
                        run_command("UPDATE licencni_klice SET pouzito_uzivatelem_id=? WHERE id=?",(uid,kdb['id']))
                        st.session_state.is_pro=True; st.balloons(); st.rerun()
                    else: st.error("Neplatný klíč.")
            else:
                st.success(f"✅ PRO aktivní do: **{fmt_d(exp)}**")
                if st.button("Deaktivovat"): run_command("UPDATE users SET license_key=NULL,license_valid_until=NULL WHERE id=?",(uid,)); st.session_state.is_pro=False; st.rerun()
            st.divider()
            st.markdown("**Změna hesla**")
            pc1,pc2=st.columns(2); p1=pc1.text_input("Stávající",type="password"); p2=pc2.text_input("Nové",type="password")
            if st.button("Změnit heslo"):
                ud=run_query("SELECT * FROM users WHERE id=?",(uid,),True)
                if ud['password_hash']==hp(p1): run_command("UPDATE users SET password_hash=? WHERE id=?",(hp(p2),uid)); st.success("Změněno.")
                else: st.error("Nesprávné stávající heslo.")

        with st.expander("🏢  Moje Firma"):
            with st.form("setf"):
                c1,c2=st.columns(2); n=c1.text_input("Název firmy",c.get('nazev',dname)); a=c2.text_area("Adresa",c.get('adresa',''))
                c3,c4=st.columns(2); i=c3.text_input("IČO",c.get('ico','')); d=c4.text_input("DIČ",c.get('dic',''))
                c5,c6=st.columns(2); b=c5.text_input("Banka",c.get('banka','')); u=c6.text_input("Číslo účtu",c.get('ucet',''))
                ib=st.text_input("IBAN (pro QR platbu)",c.get('iban',''))
                st.markdown("---")
                st.markdown("**🎨 Šablona faktury**")
                tpl_opts={"1 – Modern Sidebar (barevný pruh vlevo)":1,"2 – Klasik (hlavička nahoře)":2,"3 – Minimální (čistý design)":3}
                cur_tpl=int(c.get('faktura_sablona',1) or 1)
                cur_tpl_label=[k for k,v in tpl_opts.items() if v==cur_tpl]
                cur_tpl_label=cur_tpl_label[0] if cur_tpl_label else list(tpl_opts.keys())[0]
                tpl_sel=st.selectbox("Vzhled PDF faktur",list(tpl_opts.keys()),index=list(tpl_opts.keys()).index(cur_tpl_label))
                tpl_val=tpl_opts[tpl_sel]
                st.caption("Změna se projeví při příštím stažení PDF faktury.")
                if st.form_submit_button("Uložit"):
                    ic=ib.replace(" ","").upper() if ib else ""
                    if c.get('id'): run_command("UPDATE nastaveni SET nazev=?,adresa=?,ico=?,dic=?,banka=?,ucet=?,iban=?,faktura_sablona=? WHERE id=?",(n,a,i,d,b,u,ic,tpl_val,c['id']))
                    else: run_command("INSERT INTO nastaveni (user_id,nazev,adresa,ico,dic,banka,ucet,iban,faktura_sablona) VALUES (?,?,?,?,?,?,?,?,?)",(uid,n,a,i,d,b,u,ic,tpl_val))
                    get_nastaveni.clear(); cached_pdf.clear(); cached_isdoc.clear(); st.rerun()

        with st.expander(f"🔔  Upozornění {'(PRO)' if not is_pro else ''}"):
            if not is_pro: st.markdown('<div class="pro-card"><p style="color:#64748b">Automatická upozornění jsou v PRO verzi.</p></div>',unsafe_allow_html=True)
            else:
                act=st.toggle("Aktivovat",value=bool(c.get('notify_active',0)))
                ca1,ca2=st.columns(2); nd=ca1.number_input("Dní předem",value=c.get('notify_days',3),min_value=1); ne=ca2.text_input("Email",value=c.get('notify_email',''))
                st.markdown("**SMTP**"); preset=st.selectbox("Preset",["-- Vyberte --","Seznam.cz","Gmail","Vlastní"])
                ds=c.get('smtp_server','smtp.seznam.cz'); dp=c.get('smtp_port',465)
                if preset=="Seznam.cz": ds="smtp.seznam.cz"; dp=465
                elif preset=="Gmail": ds="smtp.gmail.com"; dp=465
                ss=st.text_input("Server",value=ds)
                cs1,cs2=st.columns(2); sp=cs1.number_input("Port",value=dp); su=cs2.text_input("Login",value=c.get('smtp_email',''))
                sw=st.text_input("Heslo",value=c.get('smtp_password',''),type="password")
                cx1,cx2=st.columns(2)
                if cx1.button("💾 Uložit"): run_command("UPDATE nastaveni SET notify_active=?,notify_days=?,notify_email=?,smtp_server=?,smtp_port=?,smtp_email=?,smtp_password=? WHERE id=?",(int(act),nd,ne,ss,sp,su,sw,c.get('id'))); st.success("OK")
                if cx2.button("📨 Test"):
                    if send_mail(ne,"Test","Funguje ✓"): st.success("Odesláno")
                    else: st.error("Chyba")

        if is_pro:
            with st.expander("📦  Export ISDOC"):
                cx1,cx2=st.columns(2); ds=cx1.date_input("Od",date.today().replace(day=1)); de=cx2.date_input("Do",date.today())
                if st.button("Připravit ZIP"):
                    invs=run_query("SELECT id,cislo_full FROM faktury WHERE datum_vystaveni BETWEEN %s AND %s AND user_id=%s",(str(ds),str(de),uid))
                    if invs:
                        buf=io.BytesIO()
                        with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as zf:
                            for inv in invs:
                                isd=generate_isdoc(inv['id'],uid)
                                if isd: zf.writestr(f"{inv['cislo_full']}.isdoc",isd)
                        st.download_button("↓ Stáhnout ZIP",buf.getvalue(),"export.zip","application/zip")
                    else: st.warning("Žádné faktury v daném období.")

            with st.expander("💾  Záloha dat"):
                z1,z2=st.columns(2)
                z1.download_button("↓ Export JSON",export_data(uid),"zaloha.json","application/json")
                if z2.button("Odeslat na email"):
                    if send_mail(c.get('notify_email'),"Záloha MojeFaktury","Data v příloze.",export_data(uid),"zaloha.json"): st.success("Odesláno ✓")
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
                        cached_pdf.clear(); cached_isdoc.clear(); st.success("Import dokončen!"); st.rerun()
                    except Exception as ex: st.error(f"Chyba: {ex}")
        else:
            with st.expander("💾  Záloha dat"):
                st.markdown('<div class="pro-card"><p style="color:#64748b">Záloha je dostupná v PRO verzi.</p></div>',unsafe_allow_html=True)
