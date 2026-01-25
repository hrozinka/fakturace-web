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

# --- 0. KONFIGURACE A ZABEZPEČENÍ ---
try:
    email_password = st.secrets["EMAIL_PASSWORD"]
except:
    email_password = os.getenv("EMAIL_PASSWORD", "")

SYSTEM_EMAIL = {
    "enabled": True, 
    "server": "smtp.seznam.cz",
    "port": 465,
    "email": "jsem@michalkochtik.cz",  # Změňte na váš odesílací email
    "password": email_password 
}

DB_FILE = 'fakturace_v11_pro.db'

# --- 1. DESIGN A CSS (TMAVÝ REŽIM) ---
st.set_page_config(page_title="Fakturační Systém", page_icon="🧾", layout="wide")

st.markdown("""
    <style>
    /* === HLAVNÍ BARVY === */
    .stApp { background-color: #0e1117; color: #e5e7eb; }
    
    /* === VSTUPNÍ POLE === */
    /* Sjednocení vzhledu všech inputů do tmavé */
    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input, 
    .stSelectbox div[data-baseweb="select"] {
        background-color: #1f2937 !important; 
        border: 1px solid #374151 !important; 
        color: #e5e7eb !important;
        border-radius: 6px;
    }
    
    /* === EXPANDERY (ROZBALOVACÍ MENU) === */
    /* Odstranění bílého pozadí po rozbalení */
    div[data-testid="stExpander"] {
        background-color: #1f2937 !important;
        border: 1px solid #374151 !important;
        border-radius: 8px;
        color: #e5e7eb !important;
    }
    div[data-testid="stExpander"] details, div[data-testid="stExpander"] summary {
        background-color: transparent !important;
        color: #e5e7eb !important;
    }
    div[data-testid="stExpander"] svg {
        fill: #e5e7eb !important;
    }

    /* === TLAČÍTKA (VČETNĚ DOWNLOAD/PDF) === */
    /* Cílíme na běžná tlačítka I tlačítka pro stahování */
    .stButton > button, div[data-testid="stDownloadButton"] > button {
        background-color: #1f2937 !important;  /* Tmavě šedá */
        color: #e5e7eb !important;            /* Světlý text */
        border: 1px solid #374151 !important; /* Jemný okraj */
        border-radius: 6px;
        transition: all 0.2s ease-in-out;
        width: 100%;
        font-weight: 500;
    }
    
    /* Hover efekt (při najetí myší) */
    .stButton > button:hover, div[data-testid="stDownloadButton"] > button:hover {
        border-color: #eab308 !important;     /* Zlatý okraj */
        color: #eab308 !important;            /* Zlatý text */
        background-color: #111827 !important; /* Tmavší pozadí */
    }
    
    /* Primární akční tlačítka (např. Uložit) - Zlatá výplň */
    div[data-testid="stForm"] button[kind="primary"], button[kind="primary"] {
        background-color: #eab308 !important;
        color: #000000 !important;
        border: none !important;
        font-weight: bold !important;
    }
    div[data-testid="stForm"] button[kind="primary"]:hover {
        background-color: #ca8a04 !important;
    }

    /* === STATISTIKY (MOBILNÍ OPTIMALIZACE) === */
    .mini-stat-container { 
        display: flex; 
        gap: 15px; 
        margin-bottom: 20px; 
        margin-top: 10px; 
        justify-content: space-between; 
        flex-wrap: wrap; 
    }
    
    .mini-stat-box { 
        background-color: #1f2937; 
        border: 1px solid #374151; 
        border-radius: 8px; 
        padding: 20px; 
        text-align: center; 
        flex: 1; 
        min-width: 200px; 
    }
    
    /* Pokud je obrazovka menší než 768px (mobil/tablet), seřaď pod sebe */
    @media only screen and (max-width: 768px) {
        .mini-stat-container {
            flex-direction: column; 
        }
        .mini-stat-box {
            width: 100%; 
            margin-bottom: 10px;
        }
    }

    /* Typografie ve statistikách */
    .mini-label { font-size: 13px; text-transform: uppercase; letter-spacing: 1px; color: #9ca3af; margin-bottom: 8px; }
    .mini-val-green { font-size: 24px; font-weight: 700; color: #34d399; }
    .mini-val-gray { font-size: 24px; font-weight: 700; color: #d1d5db; }
    .mini-val-red { font-size: 24px; font-weight: 700; color: #f87171; }
    
    /* Ostatní styly */
    .auth-container { max-width: 500px; margin: 0 auto; padding: 40px 20px; background: #1f2937; border-radius: 10px; border: 1px solid #374151; }
    .promo-box { border: 2px solid #eab308; background-color: #422006; padding: 15px; border-radius: 10px; margin-bottom: 20px; text-align: center; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABÁZE ---
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def run_query(sql, params=(), single=False):
    """Bezpečné spuštění SQL dotazu"""
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute(sql, params)
        res = c.fetchone() if single else c.fetchall()
        return res
    except Exception as e:
        return None
    finally:
        conn.close()

def run_command(sql, params=()):
    """Bezpečné spuštění příkazu (INSERT/UPDATE/DELETE)"""
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute(sql, params)
        conn.commit()
        lid = c.lastrowid
        return lid
    except Exception as e:
        st.error(f"DB Error: {e}")
        return None
    finally:
        conn.close()

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Tabulky
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT,
        email TEXT,
        phone TEXT,
        license_key TEXT,
        license_valid_until TEXT,
        role TEXT DEFAULT 'user',
        created_at TEXT,
        last_active TEXT
    )''')
    
    # Migrace (pro jistotu, pokud sloupce chybí)
    try: c.execute("ALTER TABLE users ADD COLUMN last_active TEXT")
    except: pass
    
    c.execute('''CREATE TABLE IF NOT EXISTS nastaveni (
        id INTEGER PRIMARY KEY, user_id INTEGER, nazev TEXT, adresa TEXT, ico TEXT, dic TEXT, 
        ucet TEXT, banka TEXT, email TEXT, telefon TEXT, iban TEXT, 
        smtp_server TEXT, smtp_port INTEGER, smtp_email TEXT, smtp_password TEXT, 
        notify_email TEXT, notify_days INTEGER, notify_active INTEGER
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS klienti (
        id INTEGER PRIMARY KEY, user_id INTEGER, jmeno TEXT, adresa TEXT, 
        ico TEXT, dic TEXT, email TEXT, poznamka TEXT
    )''')
    try: c.execute("ALTER TABLE klienti ADD COLUMN poznamka TEXT")
    except: pass

    c.execute('''CREATE TABLE IF NOT EXISTS kategorie (
        id INTEGER PRIMARY KEY, user_id INTEGER, nazev TEXT, barva TEXT, 
        prefix TEXT, aktualni_cislo INTEGER DEFAULT 1, logo_blob BLOB
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS faktury (
        id INTEGER PRIMARY KEY, user_id INTEGER, cislo INTEGER, cislo_full TEXT, 
        klient_id INTEGER, kategorie_id INTEGER, datum_vystaveni TEXT, datum_duzp TEXT, 
        datum_splatnosti TEXT, castka_celkem REAL, zpusob_uhrady TEXT, 
        variabilni_symbol TEXT, cislo_objednavky TEXT, uvodni_text TEXT, 
        uhrazeno INTEGER DEFAULT 0, muj_popis TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS faktura_polozky (
        id INTEGER PRIMARY KEY, faktura_id INTEGER, nazev TEXT, cena REAL
    )''')
    
    # Admin účet
    try:
        adm_pass = hashlib.sha256(str.encode("admin")).hexdigest()
        c.execute("INSERT OR IGNORE INTO users (username, password_hash, role, full_name, email, phone) VALUES (?, ?, ?, ?, ?, ?)", 
                  ("admin", adm_pass, "admin", "Super Admin", "admin@system.cz", "000000000"))
    except: pass

    conn.commit()
    conn.close()

if 'db_inited' not in st.session_state:
    init_db()
    st.session_state.db_inited = True

# --- 3. POMOCNÉ FUNKCE ---
def hash_password(password): 
    return hashlib.sha256(str.encode(password)).hexdigest()

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
    try: 
        img = Image.open(uploaded_file)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
    except: return None

def get_next_invoice_number(kat_id, uid):
    res = run_query("SELECT prefix, aktualni_cislo FROM kategorie WHERE id = ? AND user_id = ?", (kat_id, uid), single=True)
    if res:
        return (res['aktualni_cislo'], str(res['aktualni_cislo']), res['prefix'])
    return (1, "1", "")

# --- 4. ARES API (OPRAVENO) ---
def get_ares_data(ico):
    """Načte data z ARES (v1.0.4) - Opraveno pro rok 2025"""
    import urllib3
    urllib3.disable_warnings()
    
    if not ico: return None
    
    # 1. Čištění IČO (jen čísla, doplnit nuly na 8 znaků)
    ico_clean = "".join(filter(str.isdigit, str(ico)))
    if len(ico_clean) == 0: return None
    ico_final = ico_clean.zfill(8)
    
    try:
        # Nový ARES endpoint
        url = f"https://ares.gov.cz/ekonomicke-subjekty/v-1/ekonomicke-subjekty/{ico_final}"
        
        # NUTNÉ: Hlavičky, jinak ARES vrací 403 Forbidden
        headers = {
            "accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        r = requests.get(url, headers=headers, verify=False, timeout=5)
        
        if r.status_code == 200:
            d = r.json()
            
            # Skládání adresy
            s = d.get('sidlo', {})
            text_adresa = s.get('textovaAdresa', '')
            
            if not text_adresa:
                # Fallback skládání adresy
                ulice = s.get('nazevUlice', '')
                cislo = f"{s.get('cisloDomovni','')}/{s.get('cisloOrientacni','')}".strip('/')
                if cislo == '/': cislo = s.get('cisloDomovni', '')
                obec = s.get('nazevObce', '')
                psc = s.get('psc', '')
                
                parts = [p for p in [ulice, cislo, psc, obec] if p]
                text_adresa = ", ".join(parts) if parts else ""
                
                # Formát: Ulice 123, 11000 Město
                if ulice and cislo and obec:
                    text_adresa = f"{ulice} {cislo}, {psc} {obec}"
            
            return {
                "jmeno": d.get('obchodniJmeno', ''),
                "adresa": text_adresa,
                "ico": ico_final,
                "dic": d.get('dic', '')
            }
        else:
            return None
    except Exception as e:
        print(f"ARES Error: {str(e)}")
        return None

# --- 5. LICENSE CHECK ---
def check_license_online(key):
    try:
        url = f"https://raw.githubusercontent.com/hrozinka/fakturace-web/refs/heads/main/licence.json?t={int(datetime.now().timestamp())}"
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            data = r.json()
            if key in data:
                return True, "Aktivní", data[key]
    except: pass
    return False, "Neplatný klíč", None

def send_welcome_email(to_email, full_name):
    if not SYSTEM_EMAIL["enabled"] or not SYSTEM_EMAIL["password"]: return False
    try:
        msg = MIMEMultipart()
        msg['From'] = SYSTEM_EMAIL["email"]
        msg['To'] = to_email
        msg['Subject'] = "Vítejte v MojeFaktury!"
        body = f"Dobrý den, {full_name},\n\nděkujeme za registraci."
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP_SSL(SYSTEM_EMAIL["server"], SYSTEM_EMAIL["port"])
        server.login(SYSTEM_EMAIL["email"], SYSTEM_EMAIL["password"])
        server.sendmail(SYSTEM_EMAIL["email"], to_email, msg.as_string())
        server.quit()
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
                    self.add_font('ArialCS', '', 'arial.ttf', uni=True)
                    self.add_font('ArialCS', 'B', 'arial.ttf', uni=True)
                    self.set_font('ArialCS', 'B', 24)
                    self.font_ok = True
                except: pass
            if not self.font_ok: self.set_font('Arial', 'B', 24)
            self.set_text_color(50, 50, 50)
            self.cell(0, 10, 'FAKTURA', 0, 1, 'R')
            self.ln(5)

    try:
        data = run_query(
            "SELECT f.*, k.jmeno as k_jmeno, k.adresa as k_adresa, k.ico as k_ico, k.dic as k_dic, kat.barva, kat.logo_blob "
            "FROM faktury f JOIN klienti k ON f.klient_id = k.id JOIN kategorie kat ON f.kategorie_id = kat.id "
            "WHERE f.id = ? AND f.user_id = ?", (faktura_id, uid), single=True)
        
        if not data: return "Faktura nenalezena"
        polozky = run_query("SELECT * FROM faktura_polozky WHERE faktura_id = ?", (faktura_id,))
        moje = run_query("SELECT * FROM nastaveni WHERE user_id = ? LIMIT 1", (uid,), single=True) or {}

        pdf = PDF()
        pdf.add_page()
        
        def stxt(t): return str(t) if getattr(pdf, 'font_ok', False) else remove_accents(str(t) if t else "")
        fname = 'ArialCS' if getattr(pdf, 'font_ok', False) else 'Arial'
        pdf.set_font(fname, '', 10)

        # Logo
        if data['logo_blob']:
            try:
                fn = f"t_{faktura_id}.png"
                with open(fn, "wb") as f: f.write(data['logo_blob'])
                pdf.image(fn, x=10, y=10, w=30)
                os.remove(fn)
            except: pass

        # Barva proužku (jen PRO)
        if is_pro:
            try: c = data['barva'].lstrip('#'); r, g, b = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
            except: r,g,b=100,100,100
        else: r,g,b = 0,0,0

        pdf.set_text_color(100); pdf.set_y(40)
        pdf.cell(95, 5, stxt("DODAVATEL:"), 0, 0); pdf.cell(95, 5, stxt("ODBĚRATEL:"), 0, 1)
        pdf.set_text_color(0); y = pdf.get_y()
        
        # Dodavatel
        pdf.set_font(fname, '', 12); pdf.cell(95, 5, stxt(moje.get('nazev','')), 0, 1)
        pdf.set_font(fname, '', 10); pdf.multi_cell(95, 5, stxt(f"{moje.get('adresa','')}\nIČ: {moje.get('ico','')}\nDIČ: {moje.get('dic','')}\n{moje.get('email','')}"))
        
        # Odběratel
        pdf.set_xy(105, y); pdf.set_font(fname, '', 12); pdf.cell(95, 5, stxt(data['k_jmeno']), 0, 1)
        pdf.set_xy(105, pdf.get_y()); pdf.set_font(fname, '', 10); pdf.multi_cell(95, 5, stxt(f"{data['k_adresa']}\nIČ: {data['k_ico']}\nDIČ: {data['k_dic']}"))
        
        pdf.ln(10); pdf.set_fill_color(r, g, b); pdf.rect(10, pdf.get_y(), 190, 2, 'F'); pdf.ln(5)
        
        # Detaily
        pdf.set_font(fname, '', 14); pdf.cell(100, 8, stxt(f"Faktura č.: {data['cislo_full']}"), 0, 1)
        pdf.set_font(fname, '', 10)
        pdf.cell(50, 6, stxt("Datum vystavení:"), 0, 0); pdf.cell(50, 6, format_date(data['datum_vystaveni']), 0, 1)
        pdf.cell(50, 6, stxt("Datum splatnosti:"), 0, 0); pdf.cell(50, 6, format_date(data['datum_splatnosti']), 0, 1)
        
        pdf.set_xy(110, pdf.get_y()-6)
        pdf.cell(40, 6, stxt("Banka:"), 0, 0); pdf.cell(50, 6, stxt(moje.get('banka','')), 0, 1)
        pdf.set_xy(110, pdf.get_y())
        pdf.cell(40, 6, stxt("Číslo účtu:"), 0, 0); pdf.cell(50, 6, stxt(moje.get('ucet','')), 0, 1)
        pdf.set_xy(110, pdf.get_y())
        pdf.cell(40, 6, stxt("Var. symbol:"), 0, 0); pdf.cell(50, 6, str(data['variabilni_symbol']), 0, 1)
        
        # Tabulka
        pdf.ln(15); pdf.set_fill_color(240)
        pdf.cell(140, 8, stxt(" POLOŽKA / POPIS"), 1, 0, 'L', fill=True)
        pdf.cell(50, 8, stxt("CENA "), 1, 1, 'R', fill=True)
        pdf.ln(8)
        
        for item in polozky:
            xb, yb = pdf.get_x(), pdf.get_y()
            pdf.multi_cell(140, 8, stxt(item['nazev']), 0, 'L')
            pdf.set_xy(xb + 140, yb)
            pdf.cell(50, 8, stxt(f"{item['cena']:,.2f} Kč").replace(",", " "), 0, 1, 'R')
            pdf.set_xy(10, max(pdf.get_y(), yb + 8))
            pdf.set_draw_color(240); pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            
        pdf.ln(5); pdf.set_font(fname, 'B', 14)
        pdf.cell(40, 10, "", 0, 0)
        pdf.cell(150, 10, stxt(f"CELKEM: {data['castka_celkem']:,.2f} Kč").replace(",", " "), 0, 1, 'R')
        
        # QR Kód
        if is_pro and moje.get('iban'):
            try:
                qr_str = f"SPD*1.0*ACC:{moje['iban'].replace(' ','').upper()}*AM:{data['castka_celkem']:.2f}*CC:CZK*MSG:{stxt('Faktura '+str(data['cislo_full']))}"
                img = qrcode.make(qr_str)
                img.save(f"q_{faktura_id}.png")
                pdf.image(f"q_{faktura_id}.png", x=10, y=pdf.get_y()-15, w=35)
                os.remove(f"q_{faktura_id}.png")
            except: pass

        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except Exception as e: return f"ERROR: {str(e)}"

# --- 7. SESSION A STAV ---
if 'user_id' not in st.session_state: st.session_state.user_id = None
if 'role' not in st.session_state: st.session_state.role = 'user'
if 'is_pro' not in st.session_state: st.session_state.is_pro = False
if 'full_name' not in st.session_state: st.session_state.full_name = ""
if 'items_df' not in st.session_state: 
    st.session_state.items_df = pd.DataFrame(columns=["Popis položky", "Cena"])
if 'form_reset_id' not in st.session_state: st.session_state.form_reset_id = 0
if 'ares_data' not in st.session_state: st.session_state.ares_data = {}

def reset_forms():
    st.session_state.form_reset_id += 1
    st.session_state.ares_data = {}
    st.session_state.items_df = pd.DataFrame(columns=["Popis položky", "Cena"])

# --- 8. LOGIN / REGISTRACE ---
if not st.session_state.user_id:
    st.markdown("<div class='auth-container'><h1 style='text-align:center'>Fakturace Online</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["🔐 Přihlášení", "📝 Registrace"])
    
    with t1:
        with st.form("login_form"):
            u = st.text_input("Uživatelské jméno")
            p = st.text_input("Heslo", type="password")
            if st.form_submit_button("Přihlásit se", type="primary"):
                res = run_query("SELECT * FROM users WHERE username=? AND password_hash=?", (u, hash_password(p)), single=True)
                if res:
                    st.session_state.user_id = res['id']
                    st.session_state.username = res['username']
                    st.session_state.role = res['role']
                    st.session_state.full_name = res['full_name']
                    st.session_state.user_email = res['email']
                    st.session_state.is_pro = True if res['license_key'] else False
                    run_command("UPDATE users SET last_active = ? WHERE id = ?", (datetime.now().isoformat(), res['id']))
                    st.rerun()
                else: st.error("Neplatné údaje.")

    with t2:
        with st.form("reg_form"):
            fn = st.text_input("Jméno")
            ln = st.text_input("Příjmení")
            usr = st.text_input("Login")
            mail = st.text_input("Email")
            tel = st.text_input("Telefon")
            p1 = st.text_input("Heslo", type="password")
            p2 = st.text_input("Heslo znova", type="password")
            
            if st.form_submit_button("Registrovat"):
                if p1 != p2: st.error("Hesla se neshodují.")
                elif not mail or not p1 or not usr: st.error("Vyplňte povinné údaje.")
                else:
                    try:
                        fullname = f"{fn} {ln}".strip()
                        run_command("INSERT INTO users (username, password_hash, full_name, email, phone, created_at, last_active) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                                   (usr, hash_password(p1), fullname, mail, tel, datetime.now().isoformat(), datetime.now().isoformat()))
                        send_welcome_email(mail, fullname)
                        st.success("Účet vytvořen!")
                    except: st.error("Uživatel již existuje.")
    st.stop()

# --- 9. HLAVNÍ APLIKACE ---
uid = st.session_state.user_id
role = st.session_state.role
is_pro = st.session_state.is_pro
full_name_display = st.session_state.full_name or st.session_state.username

run_command("UPDATE users SET last_active = ? WHERE id = ?", (datetime.now().isoformat(), uid))

st.sidebar.markdown(f"👤 **{full_name_display}**")
st.sidebar.caption(f"{'👑 ADMIN' if role=='admin' else ('⭐ PRO Verze' if is_pro else '🆓 FREE Verze')}")

if st.sidebar.button("Odhlásit"):
    st.session_state.user_id = None
    st.rerun()

# --- ADMIN PANEL ---
if role == 'admin':
    st.header("👑 Admin Panel")
    tabs = st.tabs(["Uživatelé", "Statistiky"])
    
    with tabs[0]:
        users = run_query("SELECT * FROM users WHERE role != 'admin'")
        for u in users:
            label = "🔴"
            if u['last_active']:
                try:
                    diff = datetime.now() - datetime.fromisoformat(u['last_active'])
                    if diff.total_seconds() < 1800: label = "🟢 ON"
                    else: label = f"{int(diff.total_seconds()/3600)}H"
                except: pass

            with st.expander(f"{label} | {u['full_name']} | {u['username']}"):
                c1, c2 = st.columns(2)
                c1.write(f"Email: {u['email']}")
                cur_lic = u['license_key'] or ""
                new_lic = c2.text_input("Licence", value=cur_lic, key=f"lk_{u['id']}")
                if c2.button("Uložit", key=f"blk_{u['id']}"):
                    run_command("UPDATE users SET license_key=? WHERE id=?", (new_lic, u['id']))
                    st.success("OK"); st.rerun()
                if c2.button("SMAZAT", key=f"del_{u['id']}", type="primary"):
                    run_command("DELETE FROM users WHERE id=?", (u['id'],)); st.rerun()

    with tabs[1]:
        c_u = run_query("SELECT COUNT(*) FROM users")[0][0]
        c_f = run_query("SELECT COUNT(*) FROM faktury")[0][0]
        st.metric("Uživatelé", c_u)
        st.metric("Faktury", c_f)

# --- UŽIVATELSKÁ ZÓNA ---
else:
    menu = st.sidebar.radio("Menu", ["Faktury", "Klienti", "Kategorie", "Nastavení"], label_visibility="collapsed")
    
    cnt_cli = run_query("SELECT COUNT(*) FROM klienti WHERE user_id=?", (uid,), single=True)[0]
    cnt_inv = run_query("SELECT COUNT(*) FROM faktury WHERE user_id=?", (uid,), single=True)[0]

    if menu == "Nastavení":
        st.header("⚙️ Nastavení")
        if not is_pro:
            st.markdown("""<div class='promo-box'><h3>🔓 Přejděte na PRO verzi</h3><p>Neomezené faktury.</p></div>""", unsafe_allow_html=True)
            lk = st.text_input("Licenční klíč")
            if st.button("Aktivovat"):
                valid, msg, exp = check_license_online(lk)
                if valid:
                    run_command("UPDATE users SET license_key=?, license_valid_until=? WHERE id=?", (lk, exp, uid))
                    st.session_state.is_pro = True; st.rerun()
                else: st.error(msg)
        else:
            st.success("✅ PRO Verze aktivní")
        
        c = run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1", (uid,), single=True) or {}
        
        with st.expander("🏢 Moje Firma", expanded=True):
            with st.form("sets"):
                n=st.text_input("Název / Jméno", c.get('nazev', full_name_display))
                a=st.text_area("Adresa", c.get('adresa',''))
                i=st.text_input("IČO", c.get('ico','')); d=st.text_input("DIČ", c.get('dic',''))
                bn=st.text_input("Banka", c.get('banka','')); uc=st.text_input("Účet", c.get('ucet',''))
                ib=st.text_input("IBAN", c.get('iban',''))
                if st.form_submit_button("Uložit"):
                    if c.get('id'): run_command("UPDATE nastaveni SET nazev=?, adresa=?, ico=?, dic=?, banka=?, ucet=?, iban=? WHERE id=?", (n,a,i,d,bn,uc,ib,c['id']))
                    else: run_command("INSERT INTO nastaveni (user_id, nazev, adresa, ico, dic, banka, ucet, iban) VALUES (?,?,?,?,?,?,?,?)", (uid,n,a,i,d,bn,uc,ib))
                    st.rerun()

    elif menu == "Klienti":
        st.header("👥 Klienti")
        if not is_pro and cnt_cli >= 3: st.error("🔒 FREE Limit: 3 klienti.")
        else:
            rid = st.session_state.form_reset_id
            with st.expander("➕ Přidat klienta"):
                c1, c2 = st.columns([3,1])
                ico_input = c1.text_input("Zadejte IČO pro ARES", key=f"s_{rid}")
                if c2.button("Načíst z ARES", key=f"b_{rid}"):
                    data = get_ares_data(ico_input)
                    if data:
                        st.session_state.ares_data = data
                        st.success("Načteno z ARES")
                    else:
                        st.error("IČO nenalezeno nebo chyba ARES.")
                
                ad = st.session_state.ares_data
                with st.form(f"cf_{rid}", clear_on_submit=True):
                    j = st.text_input("Jméno", ad.get('jmeno',''))
                    a = st.text_area("Adresa", ad.get('adresa',''))
                    k1,k2 = st.columns(2)
                    i = k1.text_input("IČ", ad.get('ico',''))
                    d = k2.text_input("DIČ", ad.get('dic',''))
                    poz = st.text_area("Poznámka")
                    if st.form_submit_button("Uložit klienta"):
                        run_command("INSERT INTO klienti (user_id, jmeno, adresa, ico, dic, poznamka) VALUES (?,?,?,?,?,?)", (uid,j,a,i,d,poz))
                        reset_forms(); st.rerun()
        
        for r in run_query("SELECT * FROM klienti WHERE user_id=?", (uid,)):
            with st.expander(r['jmeno']):
                if st.button("Smazat", key=f"delc_{r['id']}"):
                    run_command("DELETE FROM klienti WHERE id=?", (r['id'],)); st.rerun()

    elif menu == "Kategorie":
        st.header("🏷️ Kategorie")
        if not is_pro:
            st.warning("🔒 Pouze PRO verze.")
            if not run_query("SELECT * FROM kategorie WHERE user_id=?", (uid,)):
                run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva) VALUES (?, ?, ?, ?, ?)", (uid, "Obecná", "FV", 1, "#000000"))
        else:
            with st.expander("➕ Nová kategorie"):
                with st.form("kf"):
                    n=st.text_input("Název"); p=st.text_input("Prefix"); s=st.number_input("Start", 1); c=st.color_picker("Barva", "#3498db")
                    l=st.file_uploader("Logo", type=['png','jpg'])
                    if st.form_submit_button("Uložit"):
                        run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva, logo_blob) VALUES (?,?,?,?,?,?)", (uid,n,p,s,c,process_logo(l)))
                        st.rerun()

    elif menu == "Faktury":
        st.header("📊 Faktury")
        
        # Statistiky
        cy = datetime.now().year
        sc = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND strftime('%Y', datum_vystaveni) = ?", (uid, str(cy)), True)[0] or 0
        su = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno = 0", (uid,), True)[0] or 0
        
        st.markdown(f"""
        <div class="mini-stat-container">
            <div class="mini-stat-box"><div class="mini-label">Fakturováno {cy}</div><div class="mini-val-green">{sc:,.0f} Kč</div></div>
            <div class="mini-stat-box"><div class="mini-label">Neuhrazeno</div><div class="mini-val-red">{su:,.0f} Kč</div></div>
        </div>
        """, unsafe_allow_html=True)
        
        # Nová faktura
        if not is_pro and cnt_inv >= 5: st.error("🔒 FREE Limit: 5 faktur.")
        else:
            with st.expander("➕ Vystavit fakturu"):
                kli = pd.read_sql("SELECT id, jmeno FROM klienti WHERE user_id=?", get_db(), params=(uid,))
                kat = pd.read_sql("SELECT id, nazev FROM kategorie WHERE user_id=?", get_db(), params=(uid,))
                
                if kli.empty: st.warning("Nejdříve vytvořte Klienta.")
                elif not is_pro and kat.empty:
                    run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva) VALUES (?, 'Obecná', 'FV', 1, '#000000')")
                    st.rerun()
                else:
                    rid = st.session_state.form_reset_id
                    c1, c2 = st.columns(2)
                    sk = c1.selectbox("Klient", kli['jmeno'], key=f"sk_{rid}")
                    sc = c2.selectbox("Kategorie", kat['nazev'], key=f"sc_{rid}")
                    
                    kid = int(kli[kli['jmeno']==sk]['id'].values[0])
                    cid = int(kat[kat['nazev']==sc]['id'].values[0])
                    
                    _, full, _ = get_next_invoice_number(cid, uid)
                    st.info(f"Číslo: **{full}**")
                    
                    d1,d2 = st.columns(2)
                    dv = d1.date_input("Vystavení", date.today(), key=f"d1_{rid}")
                    ds = d2.date_input("Splatnost", date.today()+timedelta(14), key=f"d2_{rid}")
                    
                    ed = st.data_editor(st.session_state.items_df, num_rows="dynamic", use_container_width=True, key=f"ed_{rid}")
                    tot = float(pd.to_numeric(ed["Cena"], errors='coerce').fillna(0).sum())
                    st.markdown(f"**Celkem: {tot:,.2f} Kč**")
                    
                    if st.button("Vystavit fakturu", type="primary", key=f"b_{rid}"):
                        fid = run_command("INSERT INTO faktury (user_id, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_splatnosti, castka_celkem, variabilni_symbol) VALUES (?,?,?,?,?,?,?,?)", 
                                        (uid, full, kid, cid, dv, ds, tot, re.sub(r"\D", "", full)))
                        for _, r in ed.iterrows():
                            if r["Popis položky"]: run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (fid, r["Popis položky"], float(r["Cena"])))
                        run_command("UPDATE kategorie SET aktualni_cislo = aktualni_cislo + 1 WHERE id = ?", (cid,))
                        reset_forms(); st.success("Vystaveno"); st.rerun()

        st.divider()
        
        # Seznam faktur
        df = pd.read_sql("SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id = k.id WHERE f.user_id=? ORDER BY f.id DESC LIMIT 50", get_db(), params=(uid,))
        
        for _, r in df.iterrows():
            icon = "✅" if r['uhrazeno'] else "⏳"
            with st.expander(f"{icon} {r['cislo_full']} | {r['jmeno']} | {r['castka_celkem']:,.0f} Kč"):
                c1, c2, c3 = st.columns([1,1,2])
                
                # Stav úhrady
                if r['uhrazeno']:
                    if c1.button("Zrušit úhradu", key=f"u0_{r['id']}"):
                        run_command("UPDATE faktury SET uhrazeno=0 WHERE id=?", (r['id'],)); st.rerun()
                else:
                    if c1.button("Zaplaceno", key=f"u1_{r['id']}"):
                        run_command("UPDATE faktury SET uhrazeno=1 WHERE id=?", (r['id'],)); st.rerun()
                
                # PDF Download (Nyní tmavé tlačítko)
                pdf_data = generate_pdf(r['id'], uid, is_pro)
                if isinstance(pdf_data, bytes):
                    c2.download_button("⬇️ Stáhnout PDF", pdf_data, file_name=f"{r['cislo_full']}.pdf", mime="application/pdf", key=f"pdf_{r['id']}")
                else:
                    c2.error("Chyba PDF")
                
                if c3.button("🗑️ Smazat", key=f"del_{r['id']}"):
                    run_command("DELETE FROM faktury WHERE id=?", (r['id'],)); st.rerun()
