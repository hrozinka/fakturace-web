import streamlit as st
import sqlite3
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
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from PIL import Image

# --- 0. KONFIGURACE ---
try:
    email_pass = st.secrets["EMAIL_PASSWORD"]
except:
    email_pass = os.getenv("EMAIL_PASSWORD", "")

try:
    admin_pass_init = st.secrets["ADMIN_INIT_PASS"]
except:
    admin_pass_init = "admin"

SYSTEM_EMAIL = {
    "enabled": True, 
    "server": "smtp.seznam.cz",
    "port": 465,
    "email": "jsem@michalkochtik.cz", 
    "password": email_pass 
}

DB_FILE = 'fakturace_v16_mobile.db'

# --- 1. DESIGN A MOBILE ARCHITECTURE (CSS) ---
st.set_page_config(page_title="Fakturace Pro", page_icon="💎", layout="centered")

st.markdown("""
    <style>
    /* === 1. HLAVNÍ STRUKTURA === */
    .stApp { 
        background-color: #0f172a; /* Velmi tmavá modrá/šedá */
        color: #f8fafc; 
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* === 2. MOBILNÍ INPUTY === */
    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input, 
    .stSelectbox div[data-baseweb="select"] {
        background-color: #1e293b !important; 
        border: 1px solid #334155 !important; 
        color: #fff !important;
        border-radius: 12px !important; /* Větší radius jako iOS/Android */
        padding: 12px !important;       /* Větší plocha pro prst */
        font-size: 16px !important;     /* Čitelnost */
    }
    
    /* === 3. MENU - VELKÉ BLOKY === */
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }
    
    section[data-testid="stSidebar"] .stRadio label {
        width: 100% !important;
        display: flex !important;
        justify-content: flex-start !important; /* Zarovnání vlevo */
        align-items: center !important;
        background-color: #1e293b !important;
        padding: 20px 20px !important;      /* Masivní padding */
        margin-bottom: 12px !important;
        border-radius: 16px !important;
        border: 1px solid #334155 !important;
        cursor: pointer;
        color: #e2e8f0 !important;
        font-weight: 600 !important;
        font-size: 18px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        transition: transform 0.1s;
    }
    
    section[data-testid="stSidebar"] .stRadio label:active {
        transform: scale(0.98);
    }

    /* Aktivní položka - Zlatý gradient */
    section[data-testid="stSidebar"] .stRadio label[data-checked="true"] {
        background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%) !important;
        color: #0f172a !important; /* Tmavý text */
        border: none !important;
        font-weight: 800 !important;
        box-shadow: 0 10px 15px -3px rgba(251, 191, 36, 0.3);
    }

    /* === 4. STATISTICKÉ BLOKY (JEDNOTNÝ DESIGN) === */
    .stat-container {
        display: flex;
        gap: 15px;
        margin-bottom: 25px;
        flex-wrap: wrap; /* Zalomení na mobilu */
    }
    
    .stat-box {
        background: #1e293b;
        border-radius: 16px;
        padding: 20px;
        flex: 1;
        min-width: 140px; /* Aby se na mobilu vešly 2 vedle sebe, nebo 1 pod sebe */
        text-align: center;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
    }
    
    .stat-label {
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #94a3b8;
        margin-bottom: 8px;
        font-weight: 600;
    }
    
    .stat-value {
        font-size: 24px;
        font-weight: 800;
        color: #fff;
    }
    
    .text-green { color: #34d399 !important; }
    .text-red { color: #f87171 !important; }
    .text-gold { color: #fbbf24 !important; }

    /* === 5. LOGIN OBRAZOVKA (MODERNÍ) === */
    .login-hero {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 24px;
        padding: 40px 20px;
        text-align: center;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        margin-top: 20px;
        margin-bottom: 30px;
    }
    .hero-title {
        font-size: 32px;
        font-weight: 900;
        background: -webkit-linear-gradient(#fbbf24, #d97706);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 10px;
    }
    .hero-subtitle {
        color: #cbd5e1;
        font-size: 16px;
        line-height: 1.5;
        margin-bottom: 20px;
    }
    .feature-tag {
        display: inline-block;
        background: #334155;
        color: #94a3b8;
        padding: 5px 10px;
        border-radius: 20px;
        font-size: 12px;
        margin: 0 5px;
    }

    /* === 6. TLAČÍTKA === */
    .stButton > button {
        background-color: #334155 !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 20px !important;
        font-weight: 600 !important;
        width: 100%;
    }
    
    /* Primární tlačítko (Zlaté) */
    div[data-testid="stForm"] button[kind="primary"], button[kind="primary"] {
        background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%) !important;
        color: #0f172a !important;
        box-shadow: 0 4px 10px rgba(251, 191, 36, 0.3);
    }

    /* === 7. EXPANDERY === */
    div[data-testid="stExpander"] {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
    }
    div[data-testid="stExpander"] summary {
        color: #f1f5f9 !important;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABÁZE ---
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def run_query(sql, params=(), single=False):
    conn = get_db()
    try:
        c = conn.cursor(); c.execute(sql, params)
        res = c.fetchone() if single else c.fetchall()
        return res
    except: return None
    finally: conn.close()

def run_command(sql, params=()):
    conn = get_db()
    try:
        c = conn.cursor(); c.execute(sql, params); conn.commit()
        lid = c.lastrowid
        return lid
    except Exception as e: st.error(f"DB Error: {e}"); return None
    finally: conn.close()

def init_db():
    conn = get_db(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, full_name TEXT, email TEXT, phone TEXT, license_key TEXT, license_valid_until TEXT, role TEXT DEFAULT 'user', created_at TEXT, last_active TEXT)''')
    try: c.execute("ALTER TABLE users ADD COLUMN last_active TEXT")
    except: pass
    c.execute('''CREATE TABLE IF NOT EXISTS nastaveni (id INTEGER PRIMARY KEY, user_id INTEGER, nazev TEXT, adresa TEXT, ico TEXT, dic TEXT, ucet TEXT, banka TEXT, email TEXT, telefon TEXT, iban TEXT, smtp_server TEXT, smtp_port INTEGER, smtp_email TEXT, smtp_password TEXT, notify_email TEXT, notify_days INTEGER, notify_active INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS klienti (id INTEGER PRIMARY KEY, user_id INTEGER, jmeno TEXT, adresa TEXT, ico TEXT, dic TEXT, email TEXT, poznamka TEXT)''')
    try: c.execute("ALTER TABLE klienti ADD COLUMN poznamka TEXT")
    except: pass
    c.execute('''CREATE TABLE IF NOT EXISTS kategorie (id INTEGER PRIMARY KEY, user_id INTEGER, nazev TEXT, barva TEXT, prefix TEXT, aktualni_cislo INTEGER DEFAULT 1, logo_blob BLOB)''')
    c.execute('''CREATE TABLE IF NOT EXISTS faktury (id INTEGER PRIMARY KEY, user_id INTEGER, cislo INTEGER, cislo_full TEXT, klient_id INTEGER, kategorie_id INTEGER, datum_vystaveni TEXT, datum_duzp TEXT, datum_splatnosti TEXT, castka_celkem REAL, zpusob_uhrady TEXT, variabilni_symbol TEXT, cislo_objednavky TEXT, uvodni_text TEXT, uhrazeno INTEGER DEFAULT 0, muj_popis TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS faktura_polozky (id INTEGER PRIMARY KEY, faktura_id INTEGER, nazev TEXT, cena REAL)''')
    try:
        adm_hash = hashlib.sha256(str.encode(admin_pass_init)).hexdigest()
        c.execute("INSERT OR IGNORE INTO users (username, password_hash, role, full_name, email, phone) VALUES (?, ?, ?, ?, ?, ?)", ("admin", adm_hash, "admin", "Super Admin", "admin@system.cz", "000000000"))
    except: pass
    conn.commit(); conn.close()

if 'db_inited' not in st.session_state:
    init_db(); st.session_state.db_inited = True

# --- 3. POMOCNÉ FUNKCE ---
def hash_password(password): return hashlib.sha256(str.encode(password)).hexdigest()

def remove_accents(input_str):
    if not input_str: return ""
    return "".join([c for c in unicodedata.normalize('NFKD', str(input_str)) if not unicodedata.combining(c)])

def format_date(d_str):
    if not d_str: return ""
    try: return d_str.strftime('%d.%m.%Y') if isinstance(d_str, (datetime, date)) else datetime.strptime(str(d_str), '%Y-%m-%d').strftime('%d.%m.%Y')
    except: return str(d_str)

def process_logo(uploaded_file):
    if not uploaded_file: return None
    try: img = Image.open(uploaded_file); buf = io.BytesIO(); img.save(buf, format='PNG'); return buf.getvalue()
    except: return None

def get_next_invoice_number(kat_id, uid):
    res = run_query("SELECT prefix, aktualni_cislo FROM kategorie WHERE id = ? AND user_id = ?", (kat_id, uid), single=True)
    if res: return (res['aktualni_cislo'], str(res['aktualni_cislo']), res['prefix'])
    return (1, "1", "")

def get_ares_data(ico):
    import urllib3; urllib3.disable_warnings()
    if not ico: return None
    ico_clean = "".join(filter(str.isdigit, str(ico))).zfill(8)
    try:
        url = f"https://ares.gov.cz/ekonomicke-subjekty/v-1/ekonomicke-subjekty/{ico_clean}"
        headers = {"accept": "application/json", "User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, verify=False, timeout=5)
        if r.status_code == 200:
            d = r.json(); s = d.get('sidlo', {})
            text_adresa = s.get('textovaAdresa', '')
            if not text_adresa:
                ulice = s.get('nazevUlice', ''); cislo = f"{s.get('cisloDomovni','')}/{s.get('cisloOrientacni','')}".strip('/')
                if cislo == '/': cislo = s.get('cisloDomovni', '')
                obec = s.get('nazevObce', ''); psc = s.get('psc', '')
                text_adresa = f"{ulice} {cislo}, {psc} {obec}".strip(', ')
            return {"jmeno": d.get('obchodniJmeno', ''), "adresa": text_adresa, "ico": ico_clean, "dic": d.get('dic', '')}
        else: return None
    except: return None

def check_license_online(key):
    try:
        url = f"https://raw.githubusercontent.com/hrozinka/fakturace-web/refs/heads/main/licence.json?t={int(datetime.now().timestamp())}"
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            data = r.json()
            if key in data: return True, "Aktivní", data[key]
    except: pass
    return False, "Neplatný klíč", None

def send_welcome_email(to_email, full_name):
    if not SYSTEM_EMAIL["enabled"] or not SYSTEM_EMAIL["password"]: 
        st.error("Chyba: SMTP heslo není nastaveno."); return False
    try:
        msg = MIMEMultipart(); msg['From'] = SYSTEM_EMAIL["email"]; msg['To'] = to_email; msg['Subject'] = "Vítejte v Fakturace Pro"
        msg.attach(MIMEText(f"Dobrý den, {full_name},\n\nváš účet je aktivní. Ať se daří!\n\nTým Fakturace Pro", 'plain'))
        server = smtplib.SMTP_SSL(SYSTEM_EMAIL["server"], SYSTEM_EMAIL["port"])
        server.login(SYSTEM_EMAIL["email"], SYSTEM_EMAIL["password"])
        server.sendmail(SYSTEM_EMAIL["email"], to_email, msg.as_string()); server.quit()
        return True
    except Exception as e: st.error(f"Chyba SMTP: {e}"); return False

def generate_pdf(faktura_id, uid, is_pro):
    from fpdf import FPDF
    import qrcode
    class PDF(FPDF):
        def header(self):
            self.font_ok = False
            if os.path.exists('arial.ttf'):
                try: self.add_font('ArialCS', '', 'arial.ttf', uni=True); self.add_font('ArialCS', 'B', 'arial.ttf', uni=True); self.set_font('ArialCS', 'B', 24); self.font_ok = True
                except: pass
            if not self.font_ok: self.set_font('Arial', 'B', 24)
            self.set_text_color(50, 50, 50); self.cell(0, 10, 'FAKTURA', 0, 1, 'R'); self.ln(5)
    try:
        data = run_query("SELECT f.*, k.jmeno as k_jmeno, k.adresa as k_adresa, k.ico as k_ico, k.dic as k_dic, kat.barva, kat.logo_blob FROM faktury f JOIN klienti k ON f.klient_id = k.id JOIN kategorie kat ON f.kategorie_id = kat.id WHERE f.id = ? AND f.user_id = ?", (faktura_id, uid), single=True)
        if not data: return "Faktura nenalezena"
        polozky = run_query("SELECT * FROM faktura_polozky WHERE faktura_id = ?", (faktura_id,))
        moje = run_query("SELECT * FROM nastaveni WHERE user_id = ? LIMIT 1", (uid,), single=True) or {}
        pdf = PDF(); pdf.add_page()
        def stxt(t): return str(t) if getattr(pdf, 'font_ok', False) else remove_accents(str(t) if t else "")
        fname = 'ArialCS' if getattr(pdf, 'font_ok', False) else 'Arial'; pdf.set_font(fname, '', 10)
        if data['logo_blob']:
            try: fn = f"t_{faktura_id}.png"; open(fn, "wb").write(data['logo_blob']); pdf.image(fn, x=10, y=10, w=30); os.remove(fn)
            except: pass
        if is_pro:
            try: c = data['barva'].lstrip('#'); r, g, b = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
            except: r,g,b=100,100,100
        else: r,g,b = 0,0,0
        pdf.set_text_color(100); pdf.set_y(40); pdf.cell(95, 5, stxt("DODAVATEL:"), 0, 0); pdf.cell(95, 5, stxt("ODBĚRATEL:"), 0, 1); pdf.set_text_color(0); y = pdf.get_y()
        pdf.set_font(fname, '', 12); pdf.cell(95, 5, stxt(moje.get('nazev','')), 0, 1); pdf.set_font(fname, '', 10); pdf.multi_cell(95, 5, stxt(f"{moje.get('adresa','')}\nIČ: {moje.get('ico','')}\nDIČ: {moje.get('dic','')}\n{moje.get('email','')}"))
        pdf.set_xy(105, y); pdf.set_font(fname, '', 12); pdf.cell(95, 5, stxt(data['k_jmeno']), 0, 1); pdf.set_xy(105, pdf.get_y()); pdf.set_font(fname, '', 10); pdf.multi_cell(95, 5, stxt(f"{data['k_adresa']}\nIČ: {data['k_ico']}\nDIČ: {data['k_dic']}"))
        pdf.ln(10); pdf.set_fill_color(r, g, b); pdf.rect(10, pdf.get_y(), 190, 2, 'F'); pdf.ln(5)
        pdf.set_font(fname, '', 14); pdf.cell(100, 8, stxt(f"Faktura č.: {data['cislo_full']}"), 0, 1); pdf.set_font(fname, '', 10)
        pdf.cell(50, 6, stxt("Datum vystavení:"), 0, 0); pdf.cell(50, 6, format_date(data['datum_vystaveni']), 0, 1)
        pdf.cell(50, 6, stxt("Datum splatnosti:"), 0, 0); pdf.cell(50, 6, format_date(data['datum_splatnosti']), 0, 1)
        pdf.set_xy(110, pdf.get_y()-6); pdf.cell(40, 6, stxt("Banka:"), 0, 0); pdf.cell(50, 6, stxt(moje.get('banka','')), 0, 1)
        pdf.set_xy(110, pdf.get_y()); pdf.cell(40, 6, stxt("Číslo účtu:"), 0, 0); pdf.cell(50, 6, stxt(moje.get('ucet','')), 0, 1)
        pdf.set_xy(110, pdf.get_y()); pdf.cell(40, 6, stxt("Var. symbol:"), 0, 0); pdf.cell(50, 6, str(data['variabilni_symbol']), 0, 1)
        pdf.ln(15); pdf.set_fill_color(240); pdf.cell(140, 8, stxt(" POLOŽKA / POPIS"), 1, 0, 'L', fill=True); pdf.cell(50, 8, stxt("CENA "), 1, 1, 'R', fill=True); pdf.ln(8)
        for item in polozky:
            xb, yb = pdf.get_x(), pdf.get_y(); pdf.multi_cell(140, 8, stxt(item['nazev']), 0, 'L'); pdf.set_xy(xb + 140, yb); pdf.cell(50, 8, stxt(f"{item['cena']:,.2f} Kč").replace(",", " "), 0, 1, 'R'); pdf.set_xy(10, max(pdf.get_y(), yb + 8)); pdf.set_draw_color(240); pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5); pdf.set_font(fname, 'B', 14); pdf.cell(40, 10, "", 0, 0); pdf.cell(150, 10, stxt(f"CELKEM: {data['castka_celkem']:,.2f} Kč").replace(",", " "), 0, 1, 'R')
        if is_pro and moje.get('iban'):
            try: qr_str = f"SPD*1.0*ACC:{moje['iban'].replace(' ','').upper()}*AM:{data['castka_celkem']:.2f}*CC:CZK*MSG:{stxt('Faktura '+str(data['cislo_full']))}"; img = qrcode.make(qr_str); img.save(f"q_{faktura_id}.png"); pdf.image(f"q_{faktura_id}.png", x=10, y=pdf.get_y()-15, w=35); os.remove(f"q_{faktura_id}.png")
            except: pass
        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except Exception as e: return f"ERROR: {str(e)}"

# --- 7. SESSION ---
if 'user_id' not in st.session_state: st.session_state.user_id = None
if 'role' not in st.session_state: st.session_state.role = 'user'
if 'is_pro' not in st.session_state: st.session_state.is_pro = False
if 'full_name' not in st.session_state: st.session_state.full_name = ""
if 'items_df' not in st.session_state: st.session_state.items_df = pd.DataFrame(columns=["Popis položky", "Cena"])
if 'form_reset_id' not in st.session_state: st.session_state.form_reset_id = 0
if 'ares_data' not in st.session_state: st.session_state.ares_data = {}

def reset_forms():
    st.session_state.form_reset_id += 1; st.session_state.ares_data = {}
    st.session_state.items_df = pd.DataFrame(columns=["Popis položky", "Cena"])

# --- 8. LOGIN / LANDING PAGE ---
if not st.session_state.user_id:
    c1, c2, c3 = st.columns([1, 6, 1])
    with c2:
        st.markdown("""
        <div class="login-hero">
            <div style="font-size: 60px; margin-bottom: 20px;">💎</div>
            <div class="hero-title">Fakturace v kapse</div>
            <div class="hero-subtitle">Profesionální fakturační systém pro moderní podnikatele.<br>Rychle, bezpečně a online.</div>
            <div style="margin-bottom: 30px;">
                <span class="feature-tag">✓ ARES napojení</span>
                <span class="feature-tag">✓ QR Platby</span>
                <span class="feature-tag">✓ Statistiky</span>
                <span class="feature-tag">✓ PDF Export</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        t1, t2 = st.tabs(["🔐 PŘIHLÁŠENÍ", "📝 REGISTRACE"])
        with t1:
            with st.form("login_form"):
                u = st.text_input("Uživatelské jméno", placeholder="Login")
                p = st.text_input("Heslo", type="password", placeholder="Heslo")
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("Vstoupit do aplikace", type="primary", use_container_width=True):
                    res = run_query("SELECT * FROM users WHERE username=? AND password_hash=?", (u, hash_password(p)), single=True)
                    if res:
                        st.session_state.user_id = res['id']; st.session_state.username = res['username']; st.session_state.role = res['role']; st.session_state.full_name = res['full_name']; st.session_state.user_email = res['email']; st.session_state.is_pro = True if res['license_key'] else False
                        run_command("UPDATE users SET last_active = ? WHERE id = ?", (datetime.now().isoformat(), res['id'])); st.rerun()
                    else: st.error("Chyba: Neplatné přihlašovací údaje.")
        with t2:
            with st.form("reg_form"):
                c1, c2 = st.columns(2); fn = c1.text_input("Jméno"); ln = c2.text_input("Příjmení"); usr = st.text_input("Login"); mail = st.text_input("Email"); tel = st.text_input("Telefon"); p1 = st.text_input("Heslo", type="password"); p2 = st.text_input("Heslo znova", type="password")
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("Vytvořit účet zdarma", use_container_width=True):
                    if p1 != p2: st.error("Hesla se neshodují.")
                    elif not usr or not mail or not p1: st.error("Vyplňte povinná pole.")
                    else:
                        try:
                            fullname = f"{fn} {ln}".strip()
                            run_command("INSERT INTO users (username, password_hash, full_name, email, phone, created_at, last_active) VALUES (?, ?, ?, ?, ?, ?, ?)", (usr, hash_password(p1), fullname, mail, tel, datetime.now().isoformat(), datetime.now().isoformat()))
                            if send_welcome_email(mail, fullname): st.success("Účet vytvořen! Potvrzení odesláno na email.")
                            else: st.warning("Účet vytvořen, ale email se nepodařilo odeslat (zkontrolujte SMTP).")
                        except: st.error("Uživatel s tímto jménem již existuje.")
    st.stop()

# --- 9. APP ---
uid = st.session_state.user_id; role = st.session_state.role; is_pro = st.session_state.is_pro
full_name_display = st.session_state.full_name or st.session_state.username
run_command("UPDATE users SET last_active = ? WHERE id = ?", (datetime.now().isoformat(), uid))

st.sidebar.markdown(f"<h2 style='text-align:center; color:#fbbf24; margin:0;'>FAKTURACE</h2>", unsafe_allow_html=True)
st.sidebar.caption(f"<div style='text-align:center; margin-bottom:20px; color:#94a3b8;'>{full_name_display}<br>{'👑 ADMIN' if role=='admin' else ('⭐ PRO Verze' if is_pro else '🆓 FREE Verze')}</div>", unsafe_allow_html=True)
if st.sidebar.button("Odhlásit se"): st.session_state.user_id = None; st.rerun()

# --- ADMIN PANEL ---
if role == 'admin':
    st.header("👑 Správa systému")
    tabs = st.tabs(["Uživatelé", "Přehled"])
    
    with tabs[0]:
        users = run_query("SELECT * FROM users WHERE role != 'admin' ORDER BY id DESC")
        for u in users:
            with st.expander(f"👤 {u['username']} (ID: {u['id']})"):
                c1, c2 = st.columns(2)
                c1.text_input("Email", value=u['email'], disabled=True, key=f"em_{u['id']}")
                c1.text_input("Telefon", value=u['phone'], disabled=True, key=f"ph_{u['id']}")
                c1.text_input("Vytvořeno", value=format_date(u['created_at']), disabled=True, key=f"cr_{u['id']}")
                
                c2.text_input("Naposledy online", value=u['last_active'], disabled=True, key=f"la_{u['id']}")
                
                # LICENCE MANAGEMENT
                st.markdown("---")
                st.write("**Správa licence**")
                lc1, lc2 = st.columns(2)
                new_lic_key = lc1.text_input("Licenční klíč", value=u['license_key'] or "", key=f"lk_{u['id']}")
                
                # Datum expirace - ošetření prázdné hodnoty
                def_date = date.today() + timedelta(365)
                if u['license_valid_until']:
                    try: def_date = datetime.strptime(u['license_valid_until'], '%Y-%m-%d').date()
                    except: pass
                
                new_valid_until = lc2.date_input("Platnost do", value=def_date, key=f"ld_{u['id']}")
                
                b1, b2 = st.columns([1, 4])
                if b1.button("💾 Uložit", key=f"sv_{u['id']}"):
                    run_command("UPDATE users SET license_key=?, license_valid_until=? WHERE id=?", (new_lic_key, new_valid_until, u['id']))
                    st.success("Aktualizováno"); st.rerun()
                
                if st.button("🗑️ Smazat uživatele", key=f"del_{u['id']}", type="primary"):
                    run_command("DELETE FROM users WHERE id=?", (u['id'],)); st.rerun()

    with tabs[1]:
        col1, col2 = st.columns(2)
        col1.metric("Uživatelé", run_query("SELECT COUNT(*) FROM users")[0][0])
        col2.metric("Faktury", run_query("SELECT COUNT(*) FROM faktury")[0][0])

# --- USER PANEL ---
else:
    # EMOJI MENU
    menu = st.sidebar.radio(" ", ["📊 Faktury", "👥 Klienti", "🏷️ Kategorie", "⚙️ Nastavení"])
    cnt_cli = run_query("SELECT COUNT(*) FROM klienti WHERE user_id=?", (uid,), single=True)[0]
    cnt_inv = run_query("SELECT COUNT(*) FROM faktury WHERE user_id=?", (uid,), single=True)[0]

    # --- FAKTURY ---
    if "Faktury" in menu:
        st.header("Přehled faktur")
        
        # 1. VELKÉ STATISTIKY (STEJNÝ DESIGN JAKO MALÉ)
        cy = datetime.now().year
        g_sc = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND strftime('%Y', datum_vystaveni) = ?", (uid, str(cy)), True)[0] or 0
        g_su = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno = 0", (uid,), True)[0] or 0
        
        st.markdown(f"""
        <div class="stat-container">
            <div class="stat-box"><div class="stat-label">OBRAT {cy}</div><div class="stat-value text-green">{g_sc:,.0f} Kč</div></div>
            <div class="stat-box"><div class="stat-label">CELKEM DLUŽÍ</div><div class="stat-value text-red">{g_su:,.0f} Kč</div></div>
        </div>
        """, unsafe_allow_html=True)

        if not is_pro and cnt_inv >= 5: st.error("Limit 5 faktur ve FREE verzi.")
        else:
            with st.expander("➕ Nová faktura"):
                kli = pd.read_sql("SELECT id, jmeno FROM klienti WHERE user_id=?", get_db(), params=(uid,))
                kat = pd.read_sql("SELECT id, nazev FROM kategorie WHERE user_id=?", get_db(), params=(uid,))
                if kli.empty: st.warning("Nejdříve vytvořte klienta v sekci Klienti.")
                elif not is_pro and kat.empty: run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva) VALUES (?, 'Obecná', 'FV', 1, '#000000')", (uid,)); st.rerun()
                else:
                    rid = st.session_state.form_reset_id
                    c1, c2 = st.columns(2); sk = c1.selectbox("Klient", kli['jmeno'], key=f"k_{rid}"); sc = c2.selectbox("Kategorie", kat['nazev'], key=f"c_{rid}")
                    kid = int(kli[kli['jmeno']==sk]['id'].values[0]); cid = int(kat[kat['nazev']==sc]['id'].values[0])
                    _, full, _ = get_next_invoice_number(cid, uid); st.info(f"Číslo dokladu: **{full}**")
                    d1, d2 = st.columns(2); dv = d1.date_input("Vystavení", date.today(), key=f"d1_{rid}"); ds = d2.date_input("Splatnost", date.today()+timedelta(14), key=f"d2_{rid}")
                    ed = st.data_editor(st.session_state.items_df, num_rows="dynamic", use_container_width=True, key=f"e_{rid}")
                    tot = float(pd.to_numeric(ed["Cena"], errors='coerce').fillna(0).sum()); st.markdown(f"### Celkem: {tot:,.2f} Kč")
                    if st.button("Vystavit fakturu", type="primary", key=f"b_{rid}"):
                        fid = run_command("INSERT INTO faktury (user_id, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_splatnosti, castka_celkem, variabilni_symbol) VALUES (?,?,?,?,?,?,?,?)", (uid, full, kid, cid, dv, ds, tot, re.sub(r"\D", "", full)))
                        for _, r in ed.iterrows():
                             if r["Popis položky"]: run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (fid, r["Popis položky"], float(r["Cena"])))
                        run_command("UPDATE kategorie SET aktualni_cislo = aktualni_cislo + 1 WHERE id = ?", (cid,)); reset_forms(); st.success("Faktura vystavena"); st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        
        # 3. FILTR A JEHO STATISTIKY
        all_clients = run_query("SELECT id, jmeno FROM klienti WHERE user_id=?", (uid,))
        client_opts = ["Všichni"] + [c['jmeno'] for c in all_clients]
        sel_client = st.selectbox("🔍 Filtrovat podle klienta", client_opts)

        if sel_client != "Všichni":
            q_sc = "SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id = k.id WHERE f.user_id=? AND k.jmeno = ? AND strftime('%Y', f.datum_vystaveni) = ?"
            sc = run_query(q_sc, (uid, sel_client, str(cy)), True)[0] or 0
            q_su = "SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id = k.id WHERE f.user_id=? AND k.jmeno = ? AND f.uhrazeno = 0"
            su = run_query(q_su, (uid, sel_client), True)[0] or 0
            st.markdown(f"""
            <div class="stat-container">
                <div class="stat-box"><div class="stat-label">FAKTUROVÁNO ({sel_client})</div><div class="stat-value text-green">{sc:,.0f} Kč</div></div>
                <div class="stat-box"><div class="stat-label">NEUHRAZENO ({sel_client})</div><div class="stat-value text-red">{su:,.0f} Kč</div></div>
            </div>
            """, unsafe_allow_html=True)

        # 4. SEZNAM
        q_list = f"SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id = k.id WHERE f.user_id=?"
        p_list = [uid]
        if sel_client != "Všichni":
            q_list += " AND k.jmeno = ?"
            p_list.append(sel_client)
        q_list += " ORDER BY f.id DESC LIMIT 50"
        
        for _, r in pd.read_sql(q_list, get_db(), params=p_list).iterrows():
            icon = "✅" if r['uhrazeno'] else "⏳"
            with st.expander(f"{icon} {r['cislo_full']} | {r['jmeno']} | {r['castka_celkem']:,.0f} Kč"):
                c1,c2,c3 = st.columns([1,1,2])
                if r['uhrazeno']: 
                    if c1.button("Zrušit úhradu", key=f"u0_{r['id']}"): run_command("UPDATE faktury SET uhrazeno=0 WHERE id=?", (r['id'],)); st.rerun()
                else: 
                    if c1.button("Zaplaceno", key=f"u1_{r['id']}"): run_command("UPDATE faktury SET uhrazeno=1 WHERE id=?", (r['id'],)); st.rerun()
                
                pdf = generate_pdf(r['id'], uid, is_pro)
                if isinstance(pdf, bytes): c2.download_button("Stáhnout PDF", pdf, f"{r['cislo_full']}.pdf", "application/pdf", key=f"p_{r['id']}")
                else: c2.error("Chyba PDF")
                
                f_edit_key = f"edit_f_{r['id']}"
                if f_edit_key not in st.session_state: st.session_state[f_edit_key] = False
                if c3.button("✏️ Upravit", key=f"bef_{r['id']}"): st.session_state[f_edit_key] = True; st.rerun()
                
                if st.session_state[f_edit_key]:
                    with st.form(f"frm_ef_{r['id']}"):
                        ed1, ed2 = st.columns(2)
                        new_date = ed1.date_input("Splatnost", pd.to_datetime(r['datum_splatnosti']))
                        new_desc = ed2.text_input("Popis", r['muj_popis'] or "")
                        cur_items = pd.read_sql("SELECT nazev as 'Popis položky', cena as 'Cena' FROM faktura_polozky WHERE faktura_id=?", get_db(), params=(r['id'],))
                        edited = st.data_editor(cur_items, num_rows="dynamic", use_container_width=True)
                        if st.form_submit_button("Uložit změny"):
                            new_tot = float(pd.to_numeric(edited["Cena"], errors='coerce').fillna(0).sum())
                            run_command("UPDATE faktury SET datum_splatnosti=?, muj_popis=?, castka_celkem=? WHERE id=?", (new_date, new_desc, new_tot, r['id']))
                            run_command("DELETE FROM faktura_polozky WHERE faktura_id=?", (r['id'],))
                            for _, rw in edited.iterrows():
                                if rw["Popis položky"]: run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (r['id'], rw["Popis položky"], float(rw["Cena"])))
                            st.session_state[f_edit_key] = False; st.rerun()
                
                if st.button("Smazat fakturu", key=f"d_{r['id']}"): run_command("DELETE FROM faktury WHERE id=?", (r['id'],)); st.rerun()

    # --- OSTATNÍ SEKCE (ZACHOVÁNY) ---
    elif "Klienti" in menu:
        st.header("Vaši Klienti")
        if not is_pro and cnt_cli >= 3: st.error("Limit 3 klienti (FREE).")
        else:
            rid = st.session_state.form_reset_id
            with st.expander("➕ Přidat klienta"):
                c1,c2 = st.columns([3,1]); ico_in = c1.text_input("IČO (ARES)", key=f"a_{rid}")
                if c2.button("Načíst", key=f"b_{rid}"):
                    d = get_ares_data(ico_in); 
                    if d: st.session_state.ares_data = d; st.success("OK")
                    else: st.error("IČO nenalezeno")
                ad = st.session_state.ares_data
                with st.form("fc"):
                    j=st.text_input("Jméno", ad.get('jmeno','')); a=st.text_area("Adresa", ad.get('adresa',''))
                    i=st.text_input("IČ", ad.get('ico','')); d=st.text_input("DIČ", ad.get('dic','')); p=st.text_area("Poznámka")
                    if st.form_submit_button("Uložit"):
                        run_command("INSERT INTO klienti (user_id, jmeno, adresa, ico, dic, poznamka) VALUES (?,?,?,?,?,?)", (uid,j,a,i,d,p)); reset_forms(); st.rerun()
        
        for r in run_query("SELECT * FROM klienti WHERE user_id=?", (uid,)):
            with st.expander(r['jmeno']):
                if r['poznamka']: st.info(f"📝 {r['poznamka']}")
                k_edit_key = f"edit_k_{r['id']}"
                if k_edit_key not in st.session_state: st.session_state[k_edit_key] = False
                c1, c2 = st.columns(2)
                if c1.button("✏️ Upravit", key=f"bek_{r['id']}"): st.session_state[k_edit_key] = True; st.rerun()
                if c2.button("Smazat", key=f"delc_{r['id']}"): run_command("DELETE FROM klienti WHERE id=?", (r['id'],)); st.rerun()
                if st.session_state[k_edit_key]:
                    with st.form(f"frm_edit_k_{r['id']}"):
                        ej=st.text_input("Jméno", r['jmeno']); ea=st.text_area("Adresa", r['adresa'])
                        ek1,ek2=st.columns(2); ei=ek1.text_input("IČ", r['ico']); ed=ek2.text_input("DIČ", r['dic'])
                        ep=st.text_area("Poznámka", r['poznamka'] or "")
                        if st.form_submit_button("Uložit změny"):
                            run_command("UPDATE klienti SET jmeno=?, adresa=?, ico=?, dic=?, poznamka=? WHERE id=?", (ej,ea,ei,ed,ep,r['id']))
                            st.session_state[k_edit_key] = False; st.rerun()

    elif "Kategorie" in menu:
        st.header("Kategorie faktur")
        if not is_pro: st.warning("Pouze pro PRO verzi.")
        else:
            with st.expander("➕ Nová kategorie"):
                with st.form("catf"):
                    n=st.text_input("Název"); p=st.text_input("Prefix"); s=st.number_input("Start", 1); c=st.color_picker("Barva", "#3498db"); l=st.file_uploader("Logo")
                    if st.form_submit_button("Uložit"):
                        run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva, logo_blob) VALUES (?,?,?,?,?,?)", (uid,n,p,s,c,process_logo(l))); st.rerun()
        for cat in run_query("SELECT * FROM kategorie WHERE user_id=?", (uid,)):
            with st.expander(f"{cat['nazev']}"):
                c_edit_key = f"edit_cat_{cat['id']}"
                if c_edit_key not in st.session_state: st.session_state[c_edit_key] = False
                c1, c2 = st.columns(2)
                if c1.button("✏️ Upravit", key=f"bec_{cat['id']}"): st.session_state[c_edit_key] = True; st.rerun()
                if c2.button("Smazat", key=f"dc_{cat['id']}"): run_command("DELETE FROM kategorie WHERE id=?", (cat['id'],)); st.rerun()
                if st.session_state[c_edit_key]:
                    with st.form(f"frm_ec_{cat['id']}"):
                        en=st.text_input("Název", cat['nazev']); ep=st.text_input("Prefix", cat['prefix'])
                        es=st.number_input("Číslo", value=cat['aktualni_cislo']); ec=st.color_picker("Barva", cat['barva'])
                        if st.form_submit_button("Uložit změny"):
                            run_command("UPDATE kategorie SET nazev=?, prefix=?, aktualni_cislo=?, barva=? WHERE id=?", (en,ep,es,ec,cat['id']))
                            st.session_state[c_edit_key] = False; st.rerun()

    elif "Nastavení" in menu:
        st.header("Nastavení")
        if not is_pro:
            st.markdown("""<div class='stat-box'><div class='stat-value text-gold'>Upgrade na PRO</div><p>Neomezené faktury, vlastní kategorie, SMTP.</p></div>""", unsafe_allow_html=True)
            lk = st.text_input("Licenční klíč")
            if st.button("Aktivovat"): 
                v,m,e=check_license_online(lk)
                if v: run_command("UPDATE users SET license_key=?, license_valid_until=? WHERE id=?",(lk,e,uid)); st.session_state.is_pro=True; st.rerun()
                else: st.error(m)
        else:
            with st.expander("🔑 Správa licence"):
                u_data = run_query("SELECT license_valid_until FROM users WHERE id=?", (uid,), single=True)
                valid_until = u_data['license_valid_until'] if u_data else None
                st.info(f"✅ Platnost do: **{format_date(valid_until)}**" if valid_until else "✅ Trvalá / Neznámá")
                if st.button("Deaktivovat licenci"): run_command("UPDATE users SET license_key=NULL, license_valid_until=NULL WHERE id=?",(uid,)); st.session_state.is_pro=False; st.rerun()
        
        c = run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1", (uid,), single=True) or {}
        with st.expander("🏢 Moje Firma", expanded=True):
            with st.form("setf"):
                n=st.text_input("Název", c.get('nazev', full_name_display)); a=st.text_area("Adresa", c.get('adresa',''))
                i=st.text_input("IČO", c.get('ico','')); d=st.text_input("DIČ", c.get('dic',''))
                b=st.text_input("Banka", c.get('banka','')); u=st.text_input("Účet", c.get('ucet','')); ib=st.text_input("IBAN", c.get('iban',''))
                em=st.text_input("Email", c.get('email','')); ph=st.text_input("Telefon", c.get('telefon',''))
                if st.form_submit_button("Uložit"):
                    if c.get('id'): run_command("UPDATE nastaveni SET nazev=?, adresa=?, ico=?, dic=?, banka=?, ucet=?, iban=?, email=?, telefon=? WHERE id=?", (n,a,i,d,b,u,ib,em,ph,c['id']))
                    else: run_command("INSERT INTO nastaveni (user_id, nazev, adresa, ico, dic, banka, ucet, iban, email, telefon) VALUES (?,?,?,?,?,?,?,?,?,?)", (uid,n,a,i,d,b,u,ib,em,ph))
                    st.rerun()
        
        if is_pro:
            with st.expander("🔔 SMTP Nastavení"):
                act = st.toggle("Aktivní", value=bool(c.get('notify_active', 0)))
                ne = st.text_input("Notifikační email", value=c.get('notify_email',''))
                ss = st.text_input("SMTP Server", value=c.get('smtp_server',''))
                sp = st.number_input("SMTP Port", value=c.get('smtp_port', 587))
                se = st.text_input("SMTP Login", value=c.get('smtp_email',''))
                sw = st.text_input("SMTP Heslo", value=c.get('smtp_password',''), type="password")
                if st.button("Uložit SMTP"):
                    run_command("UPDATE nastaveni SET notify_active=?, notify_email=?, smtp_server=?, smtp_port=?, smtp_email=?, smtp_password=? WHERE id=?", (int(act), ne, ss, sp, se, sw, c.get('id'))); st.success("Uloženo")
            
            with st.expander("💾 Záloha (Import / Export)"):
                def get_bk():
                    data={}
                    for t in ['nastaveni','klienti','kategorie','faktury','faktura_polozky']:
                         cols = [i[1] for i in get_db().execute(f"PRAGMA table_info({t})")]
                         q = f"SELECT * FROM {t} WHERE user_id=?" if 'user_id' in cols else f"SELECT * FROM {t}"
                         p = (uid,) if 'user_id' in cols else ()
                         if t=='faktura_polozky': q="SELECT fp.* FROM faktura_polozky fp JOIN faktury f ON fp.faktura_id=f.id WHERE f.user_id=?"; p=(uid,)
                         df = pd.read_sql(q, get_db(), params=p)
                         if 'logo_blob' in df.columns: df['logo_blob'] = df['logo_blob'].apply(lambda x: base64.b64encode(x).decode('utf-8') if x else None)
                         data[t] = df.to_dict(orient='records')
                    return json.dumps(data, default=str)
                st.download_button("Exportovat data", get_bk(), "zaloha.json", "application/json")
                upl = st.file_uploader("Nahrát zálohu (JSON)", type="json")
                if upl and st.button("Obnovit ze zálohy"):
                    try:
                        data = json.load(upl)
                        run_command("DELETE FROM nastaveni WHERE user_id=?", (uid,))
                        run_command("DELETE FROM klienti WHERE user_id=?", (uid,))
                        run_command("DELETE FROM kategorie WHERE user_id=?", (uid,))
                        faktury_ids = run_query("SELECT id FROM faktury WHERE user_id=?", (uid,))
                        for f in faktury_ids: run_command("DELETE FROM faktura_polozky WHERE faktura_id=?", (f['id'],))
                        run_command("DELETE FROM faktury WHERE user_id=?", (uid,))
                        for row in data.get('nastaveni', []):
                            run_command("INSERT INTO nastaveni (user_id, nazev, adresa, ico, dic, ucet, banka, email, telefon, iban) VALUES (?,?,?,?,?,?,?,?,?,?)", (uid, row.get('nazev'), row.get('adresa'), row.get('ico'), row.get('dic'), row.get('ucet'), row.get('banka'), row.get('email'), row.get('telefon'), row.get('iban')))
                        for row in data.get('klienti', []):
                            run_command("INSERT INTO klienti (user_id, jmeno, adresa, ico, dic, email, poznamka) VALUES (?,?,?,?,?,?,?)", (uid, row.get('jmeno'), row.get('adresa'), row.get('ico'), row.get('dic'), row.get('email'), row.get('poznamka')))
                        for row in data.get('kategorie', []):
                            blob = base64.b64decode(row.get('logo_blob')) if row.get('logo_blob') else None
                            run_command("INSERT INTO kategorie (user_id, nazev, barva, prefix, aktualni_cislo, logo_blob) VALUES (?,?,?,?,?,?)", (uid, row.get('nazev'), row.get('barva'), row.get('prefix'), row.get('aktualni_cislo'), blob))
                        for row in data.get('faktury', []):
                            new_fid = run_command("INSERT INTO faktury (user_id, cislo, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_duzp, datum_splatnosti, castka_celkem, zpusob_uhrady, variabilni_symbol, cislo_objednavky, uvodni_text, uhrazeno, muj_popis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (uid, row.get('cislo'), row.get('cislo_full'), row.get('klient_id'), row.get('kategorie_id'), row.get('datum_vystaveni'), row.get('datum_duzp'), row.get('datum_splatnosti'), row.get('castka_celkem'), row.get('zpusob_uhrady'), row.get('variabilni_symbol'), row.get('cislo_objednavky'), row.get('uvodni_text'), row.get('uhrazeno'), row.get('muj_popis')))
                            old_fid = row.get('id')
                            for item in data.get('faktura_polozky', []):
                                if item.get('faktura_id') == old_fid:
                                    run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (new_fid, item.get('nazev'), item.get('cena')))
                        st.success("Data obnovena!"); st.rerun()
                    except Exception as e: st.error(f"Chyba importu: {str(e)}")
