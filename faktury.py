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
    email_password = st.secrets["EMAIL_PASSWORD"]
except:
    email_password = os.getenv("EMAIL_PASSWORD", "")

SYSTEM_EMAIL = {
    "enabled": True, 
    "server": "smtp.seznam.cz",
    "port": 465,
    "email": "jsem@michalkochtik.cz", 
    "password": email_password 
}

DB_FILE = 'fakturace_v11_pro.db'

# --- 1. DESIGN A UI/UX ---
st.set_page_config(page_title="Fakturační Systém", page_icon="🧾", layout="centered")

st.markdown("""
    <style>
    /* === GLOBÁLNÍ RESET === */
    .stApp { background-color: #111827; color: #f3f4f6; font-family: 'Segoe UI', sans-serif; }
    
    /* === VSTUPNÍ POLE === */
    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input, 
    .stSelectbox div[data-baseweb="select"] {
        background-color: #1f2937 !important; 
        border: 1px solid #374151 !important; 
        color: #f3f4f6 !important;
        border-radius: 10px !important;
        padding: 10px !important;
    }

    /* === MENU - BOXY (VYLEPŠENO PRO MOBIL) === */
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }
    
    section[data-testid="stSidebar"] .stRadio label {
        width: 100% !important;
        display: flex !important;
        justify-content: center !important; /* Centrování textu */
        background-color: #1f2937 !important;
        padding: 18px 10px !important;      /* Vyšší boxy pro lepší klikání na mobilu */
        margin-bottom: 12px !important;
        border-radius: 12px !important;
        border: 1px solid #374151 !important;
        cursor: pointer;
        
        /* TEXT - VYNUCENÁ SVĚTLÁ */
        font-size: 17px !important;         
        font-weight: 700 !important;        
        color: #f3f4f6 !important;          /* Světle šedá až bílá */
        text-align: center !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Hover efekt */
    section[data-testid="stSidebar"] .stRadio label:hover {
        border-color: #eab308 !important;
        color: #eab308 !important;
    }

    /* Aktivní položka - Zlatá */
    section[data-testid="stSidebar"] .stRadio label[data-checked="true"] {
        background: linear-gradient(135deg, #eab308 0%, #ca8a04 100%) !important;
        color: #111827 !important;          /* Tmavý text na zlatém pro kontrast */
        border: none !important;
    }

    /* === LOGIN KARTA === */
    .login-container {
        background-color: #1f2937; padding: 40px; border-radius: 20px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.3); border: 1px solid #374151;
        text-align: center; margin-top: 50px;
    }
    .login-header { font-size: 28px; font-weight: 800; color: #eab308; margin-bottom: 10px; text-transform: uppercase; }

    /* === TLAČÍTKA === */
    .stButton > button {
        background-color: #1f2937 !important; color: #e5e7eb !important;
        border: 1px solid #374151 !important; border-radius: 8px; width: 100%;
    }
    .stButton > button:hover { border-color: #eab308 !important; color: #eab308 !important; }
    div[data-testid="stForm"] button[kind="primary"], button[kind="primary"] {
        background: linear-gradient(135deg, #eab308 0%, #ca8a04 100%) !important;
        color: #111827 !important; border: none !important;
    }

    /* === STATISTIKY === */
    .mini-stat-container { display: flex; gap: 15px; margin-bottom: 25px; flex-wrap: wrap; }
    .mini-stat-box { background: #1f2937; border-radius: 12px; padding: 20px; flex: 1; text-align: center; border: 1px solid #374151; min-width: 140px; }
    .mini-val-green { font-size: 24px; font-weight: 800; color: #34d399; }
    .mini-val-red { font-size: 24px; font-weight: 800; color: #f87171; }
    
    /* === EXPANDERY === */
    div[data-testid="stExpander"] { background-color: #1f2937 !important; border: 1px solid #374151 !important; border-radius: 12px !important; }
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
        adm_pass = hashlib.sha256(str.encode("admin")).hexdigest()
        c.execute("INSERT OR IGNORE INTO users (username, password_hash, role, full_name, email, phone) VALUES (?, ?, ?, ?, ?, ?)", ("admin", adm_pass, "admin", "Super Admin", "admin@system.cz", "000000000"))
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
    try: 
        if isinstance(d_str, (datetime, date)): return d_str.strftime('%d.%m.%Y')
        return datetime.strptime(str(d_str), '%Y-%m-%d').strftime('%d.%m.%Y')
    except: return str(d_str)

def process_logo(uploaded_file):
    if not uploaded_file: return None
    try: img = Image.open(uploaded_file); buf = io.BytesIO(); img.save(buf, format='PNG'); return buf.getvalue()
    except: return None

def get_next_invoice_number(kat_id, uid):
    res = run_query("SELECT prefix, aktualni_cislo FROM kategorie WHERE id = ? AND user_id = ?", (kat_id, uid), single=True)
    if res: return (res['aktualni_cislo'], str(res['aktualni_cislo']), res['prefix'])
    return (1, "1", "")

# --- 4. ARES API ---
def get_ares_data(ico):
    import urllib3
    urllib3.disable_warnings()
    if not ico: return None
    ico_clean = "".join(filter(str.isdigit, str(ico)))
    if len(ico_clean) == 0: return None
    ico_final = ico_clean.zfill(8)
    
    try:
        url = f"https://ares.gov.cz/ekonomicke-subjekty/v-1/ekonomicke-subjekty/{ico_final}"
        headers = {"accept": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
        r = requests.get(url, headers=headers, verify=False, timeout=5)
        
        if r.status_code == 200:
            d = r.json(); s = d.get('sidlo', {})
            text_adresa = s.get('textovaAdresa', '')
            if not text_adresa:
                ulice = s.get('nazevUlice', ''); cislo = f"{s.get('cisloDomovni','')}/{s.get('cisloOrientacni','')}".strip('/')
                if cislo == '/': cislo = s.get('cisloDomovni', '')
                obec = s.get('nazevObce', ''); psc = s.get('psc', '')
                parts = [p for p in [ulice, cislo, psc, obec] if p]
                text_adresa = ", ".join(parts) if parts else ""

            return {"jmeno": d.get('obchodniJmeno', ''), "adresa": text_adresa, "ico": ico_final, "dic": d.get('dic', '')}
        else: return None
    except: return None

# --- 5. LICENCE & EMAIL ---
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
    if not SYSTEM_EMAIL["enabled"] or not SYSTEM_EMAIL["password"]: return False
    try:
        msg = MIMEMultipart(); msg['From'] = SYSTEM_EMAIL["email"]; msg['To'] = to_email; msg['Subject'] = "Vítejte v MojeFaktury!"
        msg.attach(MIMEText(f"Dobrý den, {full_name},\n\nděkujeme za registraci.", 'plain'))
        server = smtplib.SMTP_SSL(SYSTEM_EMAIL["server"], SYSTEM_EMAIL["port"])
        server.login(SYSTEM_EMAIL["email"], SYSTEM_EMAIL["password"])
        server.sendmail(SYSTEM_EMAIL["email"], to_email, msg.as_string()); server.quit()
        return True
    except: return False

# --- 6. PDF GENERATOR ---
def generate_pdf(faktura_id, uid, is_pro):
    from fpdf import FPDF
    import qrcode
    
    class PDF(FPDF):
        def header(self):
            self.font_ok = False
            if os.path.exists('arial.ttf'):
                try: 
                    self.add_font('ArialCS', '', 'arial.ttf', uni=True); self.add_font('ArialCS', 'B', 'arial.ttf', uni=True)
                    self.set_font('ArialCS', 'B', 24); self.font_ok = True
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
            try:
                fn = f"t_{faktura_id}.png"; 
                with open(fn, "wb") as f: f.write(data['logo_blob'])
                pdf.image(fn, x=10, y=10, w=30); os.remove(fn)
            except: pass

        if is_pro:
            try: c = data['barva'].lstrip('#'); r, g, b = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
            except: r,g,b=100,100,100
        else: r,g,b = 0,0,0

        pdf.set_text_color(100); pdf.set_y(40)
        pdf.cell(95, 5, stxt("DODAVATEL:"), 0, 0); pdf.cell(95, 5, stxt("ODBĚRATEL:"), 0, 1)
        pdf.set_text_color(0); y = pdf.get_y()
        pdf.set_font(fname, '', 12); pdf.cell(95, 5, stxt(moje.get('nazev','')), 0, 1)
        pdf.set_font(fname, '', 10); pdf.multi_cell(95, 5, stxt(f"{moje.get('adresa','')}\nIČ: {moje.get('ico','')}\nDIČ: {moje.get('dic','')}\n{moje.get('email','')}"))
        pdf.set_xy(105, y); pdf.set_font(fname, '', 12); pdf.cell(95, 5, stxt(data['k_jmeno']), 0, 1)
        pdf.set_xy(105, pdf.get_y()); pdf.set_font(fname, '', 10); pdf.multi_cell(95, 5, stxt(f"{data['k_adresa']}\nIČ: {data['k_ico']}\nDIČ: {data['k_dic']}"))
        pdf.ln(10); pdf.set_fill_color(r, g, b); pdf.rect(10, pdf.get_y(), 190, 2, 'F'); pdf.ln(5)
        pdf.set_font(fname, '', 14); pdf.cell(100, 8, stxt(f"Faktura č.: {data['cislo_full']}"), 0, 1); pdf.set_font(fname, '', 10)
        pdf.cell(50, 6, stxt("Datum vystavení:"), 0, 0); pdf.cell(50, 6, format_date(data['datum_vystaveni']), 0, 1)
        pdf.cell(50, 6, stxt("Datum splatnosti:"), 0, 0); pdf.cell(50, 6, format_date(data['datum_splatnosti']), 0, 1)
        pdf.set_xy(110, pdf.get_y()-6); pdf.cell(40, 6, stxt("Banka:"), 0, 0); pdf.cell(50, 6, stxt(moje.get('banka','')), 0, 1)
        pdf.set_xy(110, pdf.get_y()); pdf.cell(40, 6, stxt("Číslo účtu:"), 0, 0); pdf.cell(50, 6, stxt(moje.get('ucet','')), 0, 1)
        pdf.set_xy(110, pdf.get_y()); pdf.cell(40, 6, stxt("Var. symbol:"), 0, 0); pdf.cell(50, 6, str(data['variabilni_symbol']), 0, 1)
        pdf.ln(15); pdf.set_fill_color(240); pdf.cell(140, 8, stxt(" POLOŽKA / POPIS"), 1, 0, 'L', fill=True); pdf.cell(50, 8, stxt("CENA "), 1, 1, 'R', fill=True); pdf.ln(8)
        
        for item in polozky:
            xb, yb = pdf.get_x(), pdf.get_y(); pdf.multi_cell(140, 8, stxt(item['nazev']), 0, 'L')
            pdf.set_xy(xb + 140, yb); pdf.cell(50, 8, stxt(f"{item['cena']:,.2f} Kč").replace(",", " "), 0, 1, 'R')
            pdf.set_xy(10, max(pdf.get_y(), yb + 8)); pdf.set_draw_color(240); pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        
        pdf.ln(5); pdf.set_font(fname, 'B', 14); pdf.cell(40, 10, "", 0, 0); pdf.cell(150, 10, stxt(f"CELKEM: {data['castka_celkem']:,.2f} Kč").replace(",", " "), 0, 1, 'R')
        if is_pro and moje.get('iban'):
            try:
                qr_str = f"SPD*1.0*ACC:{moje['iban'].replace(' ','').upper()}*AM:{data['castka_celkem']:.2f}*CC:CZK*MSG:{stxt('Faktura '+str(data['cislo_full']))}"
                img = qrcode.make(qr_str); img.save(f"q_{faktura_id}.png"); pdf.image(f"q_{faktura_id}.png", x=10, y=pdf.get_y()-15, w=35); os.remove(f"q_{faktura_id}.png")
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

# --- 8. LOGIN / AUTH ---
if not st.session_state.user_id:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div class="login-container">
            <div style="font-size: 50px; margin-bottom: 10px;">🧾</div>
            <div class="login-header">Fakturace Online</div>
            <div class="login-sub">Profesionální systém pro vaše podnikání</div>
        </div>
        """, unsafe_allow_html=True)
        
        tab_login, tab_reg = st.tabs(["🔐 Přihlášení", "📝 Registrace"])
        with tab_login:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.form("login_form"):
                u = st.text_input("Uživatelské jméno", placeholder="Váš login")
                p = st.text_input("Heslo", type="password", placeholder="Vaše heslo")
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("Přihlásit se", type="primary", use_container_width=True):
                    res = run_query("SELECT * FROM users WHERE username=? AND password_hash=?", (u, hash_password(p)), single=True)
                    if res:
                        st.session_state.user_id = res['id']; st.session_state.username = res['username']
                        st.session_state.role = res['role']; st.session_state.full_name = res['full_name']
                        st.session_state.user_email = res['email']; st.session_state.is_pro = True if res['license_key'] else False
                        run_command("UPDATE users SET last_active = ? WHERE id = ?", (datetime.now().isoformat(), res['id'])); st.rerun()
                    else: st.error("Neplatné údaje.")

        with tab_reg:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.form("reg_form"):
                c1, c2 = st.columns(2)
                fn = c1.text_input("Jméno"); ln = c2.text_input("Příjmení")
                usr = st.text_input("Login"); mail = st.text_input("Email")
                tel = st.text_input("Telefon")
                p1 = st.text_input("Heslo", type="password"); p2 = st.text_input("Heslo znova", type="password")
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("Vytvořit účet", use_container_width=True):
                    if p1 != p2: st.error("Hesla se neshodují.")
                    else:
                        try:
                            fullname = f"{fn} {ln}".strip()
                            run_command("INSERT INTO users (username, password_hash, full_name, email, phone, created_at, last_active) VALUES (?, ?, ?, ?, ?, ?, ?)", (usr, hash_password(p1), fullname, mail, tel, datetime.now().isoformat(), datetime.now().isoformat()))
                            send_welcome_email(mail, fullname); st.success("Účet vytvořen! Přepněte na přihlášení.")
                        except: st.error("Uživatel existuje.")
    st.stop()

# --- 9. APP ---
uid = st.session_state.user_id; role = st.session_state.role; is_pro = st.session_state.is_pro
full_name_display = st.session_state.full_name or st.session_state.username
run_command("UPDATE users SET last_active = ? WHERE id = ?", (datetime.now().isoformat(), uid))

st.sidebar.markdown(f"<h3 style='text-align:center; color:#eab308; margin-top:0;'>Fakturace</h3>", unsafe_allow_html=True)
st.sidebar.caption(f"<div style='text-align:center; margin-bottom:20px;'>{full_name_display}<br>{'👑 ADMIN' if role=='admin' else ('⭐ PRO Verze' if is_pro else '🆓 FREE Verze')}</div>", unsafe_allow_html=True)

if st.sidebar.button("Odhlásit"): st.session_state.user_id = None; st.rerun()

# --- ADMIN ---
if role == 'admin':
    st.header("👑 Admin"); tabs = st.tabs(["Uživatelé", "Statistiky"])
    with tabs[0]:
        for u in run_query("SELECT * FROM users WHERE role != 'admin'"):
            with st.expander(f"{u['username']}"):
                cur = u['license_key'] or ""; new_lic = st.text_input("Licence", value=cur, key=f"l_{u['id']}")
                if st.button("Uložit", key=f"s_{u['id']}"): run_command("UPDATE users SET license_key=? WHERE id=?", (new_lic, u['id'])); st.rerun()
                if st.button("SMAZAT", key=f"d_{u['id']}"): run_command("DELETE FROM users WHERE id=?", (u['id'],)); st.rerun()
    with tabs[1]:
        st.metric("Uživatelé", run_query("SELECT COUNT(*) FROM users")[0][0]); st.metric("Faktury", run_query("SELECT COUNT(*) FROM faktury")[0][0])

# --- USER ---
else:
    menu = st.sidebar.radio(" ", ["📊 Faktury", "👥 Klienti", "🏷️ Kategorie", "⚙️ Nastavení"])
    
    cnt_cli = run_query("SELECT COUNT(*) FROM klienti WHERE user_id=?", (uid,), single=True)[0]
    cnt_inv = run_query("SELECT COUNT(*) FROM faktury WHERE user_id=?", (uid,), single=True)[0]

    # --- NASTAVENÍ ---
    if "Nastavení" in menu:
        st.header("⚙️ Nastavení")
        if not is_pro:
            st.markdown("""<div class='promo-box'><h3>🔓 Přejděte na PRO verzi</h3></div>""", unsafe_allow_html=True)
            with st.expander("Aktivovat licenci"):
                lk = st.text_input("Klíč"); 
                if st.button("Aktivovat"): 
                    v,m,e=check_license_online(lk); 
                    if v: run_command("UPDATE users SET license_key=?, license_valid_until=? WHERE id=?",(lk,e,uid)); st.session_state.is_pro=True; st.rerun()
                    else: st.error(m)
        else:
            with st.expander("🔑 Správa licence"):
                if st.button("Deaktivovat licenci"): run_command("UPDATE users SET license_key=NULL WHERE id=?",(uid,)); st.session_state.is_pro=False; st.rerun()
        
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
                    run_command("UPDATE nastaveni SET notify_active=?, notify_email=?, smtp_server=?, smtp_port=?, smtp_email=?, smtp_password=? WHERE id=?", (int(act), ne, ss, sp, se, sw, c.get('id')))
                    st.success("Uloženo")
            
            with st.expander("💾 Záloha"):
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
                st.download_button("Stáhnout zálohu", get_bk(), "zaloha.json", "application/json")

    # --- KLIENTI ---
    elif "Klienti" in menu:
        st.header("👥 Klienti")
        if not is_pro and cnt_cli >= 3: st.error("Limit 3 klienti (FREE).")
        else:
            rid = st.session_state.form_reset_id
            with st.expander("➕ Přidat klienta"):
                c1,c2 = st.columns([3,1]); ico_in = c1.text_input("IČO (ARES)", key=f"a_{rid}")
                if c2.button("Načíst", key=f"b_{rid}"):
                    d = get_ares_data(ico_in)
                    if d: st.session_state.ares_data = d; st.success("OK")
                    else: st.error("Nenalezeno")
                
                ad = st.session_state.ares_data
                with st.form("fc"):
                    j=st.text_input("Jméno", ad.get('jmeno','')); a=st.text_area("Adresa", ad.get('adresa',''))
                    i=st.text_input("IČ", ad.get('ico','')); d=st.text_input("DIČ", ad.get('dic','')); p=st.text_area("Poznámka")
                    if st.form_submit_button("Uložit"):
                        run_command("INSERT INTO klienti (user_id, jmeno, adresa, ico, dic, poznamka) VALUES (?,?,?,?,?,?)", (uid,j,a,i,d,p)); reset_forms(); st.rerun()
        
        for r in run_query("SELECT * FROM klienti WHERE user_id=?", (uid,)):
            with st.expander(r['jmeno']):
                # --- EDITACE KLIENTA (NÁVRAT) ---
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

    # --- KATEGORIE ---
    elif "Kategorie" in menu:
        st.header("🏷️ Kategorie")
        if not is_pro:
            st.warning("Pouze pro PRO verzi."); chk = run_query("SELECT * FROM kategorie WHERE user_id=?", (uid,))
            if not chk: run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva) VALUES (?, 'Obecná', 'FV', 1, '#000000')", (uid,))
        else:
            with st.expander("➕ Nová kategorie"):
                with st.form("catf"):
                    n=st.text_input("Název"); p=st.text_input("Prefix"); s=st.number_input("Start", 1); c=st.color_picker("Barva", "#3498db"); l=st.file_uploader("Logo")
                    if st.form_submit_button("Uložit"):
                        run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva, logo_blob) VALUES (?,?,?,?,?,?)", (uid,n,p,s,c,process_logo(l))); st.rerun()
        
        for cat in run_query("SELECT * FROM kategorie WHERE user_id=?", (uid,)):
            with st.expander(f"{cat['nazev']}"):
                # --- EDITACE KATEGORIE (NÁVRAT) ---
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

    # --- FAKTURY ---
    elif "Faktury" in menu:
        st.header("📊 Faktury")
        cy = datetime.now().year
        sc = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND strftime('%Y', datum_vystaveni) = ?", (uid, str(cy)), True)[0] or 0
        su = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno = 0", (uid,), True)[0] or 0
        st.markdown(f"<div class='mini-stat-container'><div class='mini-stat-box'><div class='mini-label'>Fakturováno {cy}</div><div class='mini-val-green'>{sc:,.0f} Kč</div></div><div class='mini-stat-box'><div class='mini-label'>Neuhrazeno</div><div class='mini-val-red'>{su:,.0f} Kč</div></div></div>", unsafe_allow_html=True)

        if not is_pro and cnt_inv >= 5: st.error("Limit 5 faktur (FREE).")
        else:
            with st.expander("➕ Vystavit fakturu"):
                kli = pd.read_sql("SELECT id, jmeno FROM klienti WHERE user_id=?", get_db(), params=(uid,))
                kat = pd.read_sql("SELECT id, nazev FROM kategorie WHERE user_id=?", get_db(), params=(uid,))
                if kli.empty: st.warning("Nejdříve přidejte klienta.")
                elif not is_pro and kat.empty: run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva) VALUES (?, 'Obecná', 'FV', 1, '#000000')", (uid,)); st.rerun()
                else:
                    rid = st.session_state.form_reset_id
                    c1, c2 = st.columns(2); sk = c1.selectbox("Klient", kli['jmeno'], key=f"k_{rid}"); sc = c2.selectbox("Kategorie", kat['nazev'], key=f"c_{rid}")
                    kid = int(kli[kli['jmeno']==sk]['id'].values[0]); cid = int(kat[kat['nazev']==sc]['id'].values[0])
                    _, full, _ = get_next_invoice_number(cid, uid); st.info(f"Číslo: {full}")
                    d1, d2 = st.columns(2); dv = d1.date_input("Vystavení", date.today(), key=f"d1_{rid}"); ds = d2.date_input("Splatnost", date.today()+timedelta(14), key=f"d2_{rid}")
                    ed = st.data_editor(st.session_state.items_df, num_rows="dynamic", use_container_width=True, key=f"e_{rid}")
                    tot = float(pd.to_numeric(ed["Cena"], errors='coerce').fillna(0).sum()); st.write(f"**Celkem: {tot:,.2f} Kč**")
                    if st.button("Vystavit", type="primary", key=f"b_{rid}"):
                        fid = run_command("INSERT INTO faktury (user_id, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_splatnosti, castka_celkem, variabilni_symbol) VALUES (?,?,?,?,?,?,?,?)", (uid, full, kid, cid, dv, ds, tot, re.sub(r"\D", "", full)))
                        for _, r in ed.iterrows():
                             if r["Popis položky"]: run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (fid, r["Popis položky"], float(r["Cena"])))
                        run_command("UPDATE kategorie SET aktualni_cislo = aktualni_cislo + 1 WHERE id = ?", (cid,)); reset_forms(); st.success("Hotovo"); st.rerun()

        st.divider()
        for _, r in pd.read_sql("SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id = k.id WHERE f.user_id=? ORDER BY f.id DESC LIMIT 50", get_db(), params=(uid,)).iterrows():
            icon = "✅" if r['uhrazeno'] else "⏳"
            with st.expander(f"{icon} {r['cislo_full']} | {r['jmeno']} | {r['castka_celkem']:,.0f} Kč"):
                c1,c2,c3 = st.columns([1,1,2])
                if r['uhrazeno']: 
                    if c1.button("Zrušit úhradu", key=f"u0_{r['id']}"): run_command("UPDATE faktury SET uhrazeno=0 WHERE id=?", (r['id'],)); st.rerun()
                else: 
                    if c1.button("Zaplaceno", key=f"u1_{r['id']}"): run_command("UPDATE faktury SET uhrazeno=1 WHERE id=?", (r['id'],)); st.rerun()
                
                pdf = generate_pdf(r['id'], uid, is_pro)
                if isinstance(pdf, bytes): c2.download_button("PDF", pdf, f"{r['cislo_full']}.pdf", "application/pdf", key=f"p_{r['id']}")
                else: c2.error("Chyba PDF")
                
                # --- EDITACE FAKTURY (NÁVRAT) ---
                f_edit_key = f"edit_f_{r['id']}"
                if f_edit_key not in st.session_state: st.session_state[f_edit_key] = False
                
                if c3.button("✏️ Upravit", key=f"bef_{r['id']}"): st.session_state[f_edit_key] = True; st.rerun()
                
                if st.session_state[f_edit_key]:
                    st.markdown("---")
                    st.write("**Editace faktury**")
                    with st.form(f"frm_ef_{r['id']}"):
                        ed1, ed2 = st.columns(2)
                        new_date = ed1.date_input("Splatnost", pd.to_datetime(r['datum_splatnosti']))
                        new_desc = ed2.text_input("Popis (interní)", r['muj_popis'] or "")
                        
                        # Načtení položek
                        current_items = pd.read_sql("SELECT nazev as 'Popis položky', cena as 'Cena' FROM faktura_polozky WHERE faktura_id=?", get_db(), params=(r['id'],))
                        edited_items = st.data_editor(current_items, num_rows="dynamic", use_container_width=True)
                        
                        if st.form_submit_button("Uložit změny"):
                            new_tot = float(pd.to_numeric(edited_items["Cena"], errors='coerce').fillna(0).sum())
                            # Update hlavičky
                            run_command("UPDATE faktury SET datum_splatnosti=?, muj_popis=?, castka_celkem=? WHERE id=?", (new_date, new_desc, new_tot, r['id']))
                            # Smazání starých položek
                            run_command("DELETE FROM faktura_polozky WHERE faktura_id=?", (r['id'],))
                            # Vložení nových
                            for _, row in edited_items.iterrows():
                                if row["Popis položky"]:
                                    run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (r['id'], row["Popis položky"], float(row["Cena"])))
                            st.session_state[f_edit_key] = False; st.rerun()
                
                if st.button("Smazat", key=f"d_{r['id']}"): run_command("DELETE FROM faktury WHERE id=?", (r['id'],)); st.rerun()
