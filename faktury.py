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
import random
import string
import time
import urllib.request
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from PIL import Image
from fpdf import FPDF

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
    "password": email_pass,
    "display_name": "MojeFakturace"
}

DB_FILE = 'fakturace_v37_final.db'
FONT_URL = "https://github.com/reingart/pyfpdf/raw/master/font/DejaVuSans.ttf"
FONT_FILE = "DejaVuSans.ttf"

# --- 1. DESIGN (MOBILE FIRST) ---
st.set_page_config(page_title="Fakturace Pro", page_icon="💎", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #0f172a; color: #f8fafc; font-family: sans-serif; }
    
    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #1e293b !important; border: 1px solid #334155 !important; color: #fff !important;
        border-radius: 12px !important; padding: 12px !important;
    }
    
    section[data-testid="stSidebar"] .stRadio label {
        background-color: #1e293b !important; padding: 20px !important; margin-bottom: 10px !important;
        border-radius: 12px !important; border: 1px solid #334155 !important;
        color: #e2e8f0 !important; font-weight: 600 !important; font-size: 18px !important;
        display: flex; justify-content: flex-start; cursor: pointer;
    }
    section[data-testid="stSidebar"] .stRadio label[data-checked="true"] {
        background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%) !important;
        color: #0f172a !important; border: none !important; font-weight: 800 !important;
    }
    
    .stat-container { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
    .stat-box { 
        background: #1e293b; border-radius: 12px; padding: 15px; flex: 1; min-width: 100px;
        text-align: center; border: 1px solid #334155; box-shadow: 0 4px 6px rgba(0,0,0,0.2);
    }
    .stat-label { font-size: 11px; text-transform: uppercase; color: #94a3b8; margin-bottom: 5px; font-weight: 700; }
    .stat-value { font-size: 20px; font-weight: 800; color: #fff; }
    .text-green { color: #34d399 !important; } .text-red { color: #f87171 !important; } .text-gold { color: #fbbf24 !important; }

    .stButton > button { background-color: #334155 !important; color: white !important; border-radius: 10px !important; height: 50px; font-weight: 600; border: none;}
    div[data-testid="stForm"] button[kind="primary"] { background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%) !important; color: #0f172a !important; }
    
    .alert-box { border: 2px solid #f87171; background-color: #450a0a; padding: 20px; border-radius: 12px; margin-bottom: 20px; text-align: center; }
    div[data-testid="stExpander"] { background-color: #1e293b !important; border: 1px solid #334155 !important; border-radius: 12px !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABÁZE ---
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def run_query(sql, params=(), single=False):
    conn = get_db(); c = conn.cursor()
    try: c.execute(sql, params); res = c.fetchone() if single else c.fetchall(); return res
    except: return None
    finally: conn.close()

def run_command(sql, params=()):
    conn = get_db(); c = conn.cursor()
    try: c.execute(sql, params); conn.commit(); lid = c.lastrowid; return lid
    except: return None
    finally: conn.close()

def init_db():
    conn = get_db(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, full_name TEXT, email TEXT, phone TEXT, license_key TEXT, license_valid_until TEXT, role TEXT DEFAULT 'user', created_at TEXT, last_active TEXT, force_password_change INTEGER DEFAULT 0)''')
    try: c.execute("ALTER TABLE users ADD COLUMN force_password_change INTEGER DEFAULT 0")
    except: pass

    c.execute('''CREATE TABLE IF NOT EXISTS nastaveni (id INTEGER PRIMARY KEY, user_id INTEGER, nazev TEXT, adresa TEXT, ico TEXT, dic TEXT, ucet TEXT, banka TEXT, email TEXT, telefon TEXT, iban TEXT, smtp_server TEXT, smtp_port INTEGER, smtp_email TEXT, smtp_password TEXT, notify_email TEXT, notify_days INTEGER, notify_active INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS klienti (id INTEGER PRIMARY KEY, user_id INTEGER, jmeno TEXT, adresa TEXT, ico TEXT, dic TEXT, email TEXT, poznamka TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS kategorie (id INTEGER PRIMARY KEY, user_id INTEGER, nazev TEXT, barva TEXT, prefix TEXT, aktualni_cislo INTEGER DEFAULT 1, logo_blob BLOB)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS faktury (id INTEGER PRIMARY KEY, user_id INTEGER, cislo INTEGER, cislo_full TEXT, klient_id INTEGER, kategorie_id INTEGER, datum_vystaveni TEXT, datum_duzp TEXT, datum_splatnosti TEXT, castka_celkem REAL, zpusob_uhrady TEXT, variabilni_symbol TEXT, cislo_objednavky TEXT, uvodni_text TEXT, uhrazeno INTEGER DEFAULT 0, muj_popis TEXT)''')
    try: c.execute("ALTER TABLE faktury ADD COLUMN cislo_full TEXT")
    except: pass
    
    c.execute('''CREATE TABLE IF NOT EXISTS faktura_polozky (id INTEGER PRIMARY KEY, faktura_id INTEGER, nazev TEXT, cena REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS licencni_klice (id INTEGER PRIMARY KEY, kod TEXT UNIQUE, dny_platnosti INTEGER, vygenerovano TEXT, pouzito_uzivatelem_id INTEGER, poznamka TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS email_templates (id INTEGER PRIMARY KEY, name TEXT UNIQUE, subject TEXT, body TEXT)''')
    try: c.execute("INSERT OR IGNORE INTO email_templates (name, subject, body) VALUES ('welcome', 'Vítejte v Fakturace Pro', 'Dobrý den {name},\n\nVáš účet byl úspěšně vytvořen.\n\nAť se daří!\nTým Fakturace Pro')")
    except: pass

    try:
        adm_hash = hashlib.sha256(str.encode(admin_pass_init)).hexdigest()
        c.execute("INSERT OR IGNORE INTO users (username, password_hash, role, full_name, email, phone, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", ("admin", adm_hash, "admin", "Super Admin", "admin@system.cz", "000000000", datetime.now().isoformat()))
    except: pass
    conn.commit(); conn.close()

if 'db_inited' not in st.session_state:
    init_db(); st.session_state.db_inited = True

# --- 3. POMOCNÉ FUNKCE ---
def hash_password(password): return hashlib.sha256(str.encode(password)).hexdigest()
def remove_accents(s): return "".join([c for c in unicodedata.normalize('NFKD', str(s)) if not unicodedata.combining(c)]) if s else ""
def format_date(d):
    if not d or str(d) == 'None': return ""
    try:
        if isinstance(d, str): return datetime.strptime(d[:10], '%Y-%m-%d').strftime('%d.%m.%Y')
        return d.strftime('%d.%m.%Y')
    except: return str(d)

def generate_random_password(length=8): return ''.join(random.choice(string.ascii_letters + string.digits) for i in range(length))
def generate_license_key(): return '-'.join([''.join(random.choices(string.ascii_uppercase + string.digits, k=4)) for _ in range(4)])

def check_license_validity(uid):
    res = run_query("SELECT license_valid_until FROM users WHERE id=?", (uid,), single=True)
    if not res or not res['license_valid_until']: return False, "Žádná"
    try:
        exp = datetime.strptime(str(res['license_valid_until'])[:10], '%Y-%m-%d').date()
        if exp >= date.today(): return True, exp
        return False, exp
    except: return False, "Chyba data"

def get_next_invoice_number(kat_id, uid):
    res = run_query("SELECT prefix, aktualni_cislo FROM kategorie WHERE id = ? AND user_id = ?", (kat_id, uid), single=True)
    if res: return (res['aktualni_cislo'], f"{res['prefix']}{res['aktualni_cislo']}", res['prefix'])
    return (1, "1", "")

def get_ares_data(ico):
    import urllib3; urllib3.disable_warnings()
    if not ico: return None
    ico_clean = "".join(filter(str.isdigit, str(ico))).zfill(8)
    url = f"https://ares.gov.cz/ekonomicke-subjekty/v-1/ekonomicke-subjekty/{ico_clean}"
    headers = {"accept": "application/json", "User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, verify=False, timeout=5)
        if r.status_code == 200:
            d = r.json(); s = d.get('sidlo', {})
            adr = s.get('textovaAdresa', '')
            if not adr: adr = f"{s.get('nazevUlice','')} {s.get('cisloDomovni','')}/{s.get('cisloOrientacni','')}, {s.get('psc','')} {s.get('nazevObce','')}".strip(' ,/')
            return {"jmeno": d.get('obchodniJmeno', ''), "adresa": adr, "ico": ico_clean, "dic": d.get('dic', '')}
    except: pass
    return None

def process_logo(uploaded_file):
    if uploaded_file is None: return None
    try:
        image = Image.open(uploaded_file)
        if image.mode in ("RGBA", "P"): image = image.convert("RGB")
        img_byte_arr = io.BytesIO(); image.save(img_byte_arr, format='PNG'); return img_byte_arr.getvalue()
    except: return None

# --- E-MAILY ---
def send_email_custom(to_email, subject, body):
    if not SYSTEM_EMAIL["enabled"] or not SYSTEM_EMAIL["password"]: return False
    try:
        msg = MIMEMultipart(); msg['From'] = formataddr((SYSTEM_EMAIL["display_name"], SYSTEM_EMAIL["email"])); msg['To'] = to_email; msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP_SSL(SYSTEM_EMAIL["server"], SYSTEM_EMAIL["port"])
        server.login(SYSTEM_EMAIL["email"], SYSTEM_EMAIL["password"])
        server.sendmail(SYSTEM_EMAIL["email"], to_email, msg.as_string()); server.quit()
        return True
    except: return False

def send_welcome_email_db(to_email, full_name):
    if not SYSTEM_EMAIL["enabled"] or not SYSTEM_EMAIL["password"]: return False
    try:
        tpl = run_query("SELECT subject, body FROM email_templates WHERE name='welcome'", single=True)
        if not tpl: subj = "Vítejte"; body = f"Dobrý den {full_name},\n\nVáš účet byl vytvořen."
        else: subj = tpl['subject']; body = tpl['body'].replace("{name}", full_name)
        return send_email_custom(to_email, subj, body)
    except: return False

# --- GENERATOR PDF (S OPRAVOU PÍSMA) ---
def ensure_font():
    """Stáhne font s podporou češtiny, pokud neexistuje"""
    if not os.path.exists(FONT_FILE):
        try:
            # print("Stahuji font...")
            urllib.request.urlretrieve(FONT_URL, FONT_FILE)
            return True
        except:
            return False
    return True

def generate_pdf(faktura_id, uid, is_pro):
    import qrcode
    font_ok = ensure_font()

    # Fallback funkce pro odstranění diakritiky, pokud selže font
    def safe_str(text):
        if not text: return ""
        text = str(text)
        if font_ok: return text # Pokud máme font, vracíme i s háčky
        return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')

    class PDF(FPDF):
        def header(self):
            if font_ok:
                try:
                    self.add_font('DejaVu', '', FONT_FILE, uni=True)
                    self.set_font('DejaVu', '', 24)
                except:
                    self.set_font('Arial', 'B', 24)
            else:
                self.set_font('Arial', 'B', 24)
            
            self.set_text_color(50, 50, 50)
            self.cell(0, 10, 'FAKTURA', 0, 1, 'R')
            self.ln(5)

    try:
        data = run_query("SELECT f.*, k.jmeno as k_jmeno, k.adresa as k_adresa, k.ico as k_ico, k.dic as k_dic, kat.barva, kat.logo_blob, kat.prefix FROM faktury f JOIN klienti k ON f.klient_id=k.id JOIN kategorie kat ON f.kategorie_id=kat.id WHERE f.id=? AND f.user_id=?", (faktura_id, uid), single=True)
        if not data: return None
        
        polozky = run_query("SELECT * FROM faktura_polozky WHERE faktura_id=?", (faktura_id,))
        moje = run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1", (uid,), single=True) or {}
        
        pdf = PDF()
        pdf.add_page()
        
        if font_ok:
            try: pdf.add_font('DejaVu', '', FONT_FILE, uni=True); pdf.set_font('DejaVu', '', 10)
            except: pdf.set_font('Arial', '', 10)
        else:
            pdf.set_font('Arial', '', 10)

        # Logo
        if data['logo_blob']:
            try:
                fn = f"l_{faktura_id}.png"
                with open(fn, "wb") as f: f.write(data['logo_blob'])
                pdf.image(fn, 10, 10, 30)
                os.remove(fn)
            except: pass 

        # Barvy
        r, g, b = 0, 0, 0
        if is_pro and data['barva']:
            try:
                c = data['barva'].lstrip('#')
                r, g, b = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
            except: pass

        cislo_f = data['cislo_full'] if data['cislo_full'] else f"{data['prefix']}{data['cislo']}"

        pdf.set_text_color(100); pdf.set_y(40)
        pdf.cell(95, 5, "DODAVATEL:", 0, 0); pdf.cell(95, 5, "ODBERATEL:", 0, 1)
        pdf.set_text_color(0)
        
        y = pdf.get_y()
        # Dodavatel
        pdf.set_font_size(12); pdf.cell(95, 5, safe_str(moje.get('nazev','')), 0, 1)
        pdf.set_font_size(10); pdf.multi_cell(95, 5, safe_str(f"{moje.get('adresa','')}\nIC: {moje.get('ico','')}\nDIC: {moje.get('dic','')}\n{moje.get('email','')}"))
        
        # Odběratel
        pdf.set_xy(105, y)
        pdf.set_font_size(12); pdf.cell(95, 5, safe_str(data['k_jmeno']), 0, 1)
        pdf.set_xy(105, pdf.get_y())
        pdf.set_font_size(10); pdf.multi_cell(95, 5, safe_str(f"{data['k_adresa']}\nIC: {data['k_ico']}\nDIC: {data['k_dic']}"))
        
        pdf.ln(10)
        pdf.set_fill_color(r, g, b); pdf.rect(10, pdf.get_y(), 190, 2, 'F'); pdf.ln(5)
        
        pdf.set_font_size(14); pdf.cell(100, 8, safe_str(f"Faktura c.: {cislo_f}"), 0, 1)
        pdf.set_font_size(10)
        
        pdf.cell(50, 6, "Vystaveno:", 0, 0); pdf.cell(50, 6, format_date(data['datum_vystaveni']), 0, 1)
        pdf.cell(50, 6, "Splatnost:", 0, 0); pdf.cell(50, 6, format_date(data['datum_splatnosti']), 0, 1)
        pdf.cell(50, 6, "Ucet:", 0, 0); pdf.cell(50, 6, safe_str(moje.get('ucet','')), 0, 1)
        pdf.cell(50, 6, "VS:", 0, 0); pdf.cell(50, 6, safe_str(data['variabilni_symbol']), 0, 1)
        
        pdf.ln(15)
        pdf.set_fill_color(240)
        pdf.cell(140, 8, "POLOZKA", 1, 0, 'L', True); pdf.cell(50, 8, "CENA", 1, 1, 'R', True)
        
        for p in polozky:
            pdf.cell(140, 8, safe_str(p['nazev']), 1)
            pdf.cell(50, 8, f"{p['cena']:.2f} Kc", 1, 1, 'R')
            
        pdf.ln(5)
        pdf.set_font_size(14)
        pdf.cell(190, 10, f"CELKEM: {data['castka_celkem']:.2f} Kc", 0, 1, 'R')
        
        if is_pro and moje.get('iban'):
            try:
                qr_str = f"SPD*1.0*ACC:{moje['iban']}*AM:{data['castka_celkem']}*CC:CZK*MSG:{cislo_f}"
                img = qrcode.make(qr_str)
                fn_qr = f"qr_{faktura_id}.png"
                img.save(fn_qr)
                pdf.image(fn_qr, 10, pdf.get_y()-20, 30)
                os.remove(fn_qr)
            except: pass
            
        # Pokud máme font, není třeba encode latin-1, jinak ano
        if font_ok:
            return pdf.output(dest='S').encode('latin-1') 
        else:
            return pdf.output(dest='S').encode('latin-1', 'ignore')

    except Exception as e:
        print(f"PDF FATAL: {e}")
        return None

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

# --- 8. LOGIN ---
if not st.session_state.user_id:
    col1, col2, col3 = st.columns([1, 10, 1])
    with col2:
        st.markdown("""<div class="login-container"><div style="font-size: 50px; margin-bottom: 10px;">💎</div><div class="login-header">Fakturace Pro</div><div style="color: #94a3b8; margin-bottom: 30px;">Mobilní fakturace nové generace.</div></div>""", unsafe_allow_html=True)
        t1, t2, t3 = st.tabs(["PŘIHLÁŠENÍ", "REGISTRACE", "ZAPOMNĚL JSEM HESLO"])
        with t1:
            with st.form("log"):
                u=st.text_input("Uživatelské jméno"); p=st.text_input("Heslo", type="password")
                if st.form_submit_button("Vstoupit", type="primary", use_container_width=True):
                    r = run_query("SELECT * FROM users WHERE username=? AND password_hash=?",(u, hash_password(p)), single=True)
                    if r:
                        st.session_state.user_id=r['id']; st.session_state.role=r['role']; st.session_state.username=r['username']; st.session_state.full_name=r['full_name']; st.session_state.user_email=r['email']
                        st.session_state.force_pw_change = dict(r).get('force_password_change', 0)
                        valid, exp = check_license_validity(r['id'])
                        st.session_state.is_pro = valid
                        run_command("UPDATE users SET last_active=? WHERE id=?",(datetime.now().isoformat(), r['id'])); st.rerun()
                    else: st.error("Neplatné údaje")
        with t2:
            with st.form("reg"):
                f=st.text_input("Jméno a Příjmení"); u=st.text_input("Login"); e=st.text_input("Email"); t_tel=st.text_input("Telefon"); p=st.text_input("Heslo",type="password")
                if st.form_submit_button("Vytvořit účet", use_container_width=True):
                    try:
                        run_command("INSERT INTO users (username,password_hash,full_name,email,phone,created_at,force_password_change) VALUES (?,?,?,?,?,?,0)",(u,hash_password(p),f,e,t_tel,datetime.now().isoformat()))
                        send_welcome_email_db(e, f)
                        st.success("Hotovo! Přihlašte se."); 
                    except: st.error("Login obsazen.")
        with t3:
            with st.form("forgot"):
                fe = st.text_input("Váš Email")
                if st.form_submit_button("Resetovat heslo", use_container_width=True):
                    usr = run_query("SELECT * FROM users WHERE email=?", (fe,), single=True)
                    if usr:
                        new_pass = generate_random_password()
                        run_command("UPDATE users SET password_hash=?, force_password_change=1 WHERE id=?", (hash_password(new_pass), usr['id']))
                        send_email_custom(fe, "Reset hesla", f"Nové heslo: {new_pass}")
                        st.success("Heslo odesláno.")
                    else: st.error("Email nenalezen.")
    st.stop()

# --- 9. APP ---
uid=st.session_state.user_id; role=st.session_state.role; is_pro=st.session_state.is_pro
full_name_display = st.session_state.full_name or st.session_state.username
run_command("UPDATE users SET last_active=? WHERE id=?",(datetime.now().isoformat(), uid))

if st.session_state.get('force_pw_change', 0) == 1:
    st.markdown("""<div class='alert-box'><h3>⚠️ Změna hesla vyžadována</h3><p>Z bezpečnostních důvodů si musíte změnit heslo.</p></div>""", unsafe_allow_html=True)
    with st.form("force_change"):
        np1 = st.text_input("Nové heslo", type="password")
        np2 = st.text_input("Potvrzení hesla", type="password")
        if st.form_submit_button("Změnit heslo a pokračovat", type="primary"):
            if np1 and np1 == np2:
                run_command("UPDATE users SET password_hash=?, force_password_change=0 WHERE id=?", (hash_password(np1), uid))
                st.session_state.force_pw_change = 0; st.success("Heslo změněno!"); st.rerun()
            else: st.error("Hesla se neshodují.")
    st.stop()

badge = "⭐ PRO" if is_pro else "🆓 FREE"
st.sidebar.markdown(f"""<div class='sidebar-header'><div class='sidebar-user'>{full_name_display}</div><div class='sidebar-role'>{st.session_state.username} | <span class='{ "badge-pro" if is_pro else "badge-free" }'>{badge}</span></div></div>""", unsafe_allow_html=True)

if st.sidebar.button("Odhlásit"): st.session_state.user_id=None; st.rerun()

# ADMIN
if role == 'admin':
    st.header("👑 Admin Sekce")
    tabs = st.tabs(["Uživatelé", "Licence", "Statistiky", "📧 E-mailing"])
    with tabs[0]:
        users = run_query("SELECT * FROM users WHERE role!='admin' ORDER BY id DESC")
        for u in users:
            with st.expander(f"{u['username']} ({u['email']})"):
                st.markdown(f"**Vytvořeno:** {format_date(u['created_at'])} | **Aktivní:** {format_date(u['last_active'])}")
                st.markdown(f"**Telefon:** {u['phone']}")
                
                # OPRAVA DATA V ADMINU
                d_val = u['license_valid_until']
                if d_val:
                    try: d_val_date = datetime.strptime(str(d_val)[:10], '%Y-%m-%d').date()
                    except: d_val_date = date.today()
                else: d_val_date = date.today()

                lic_till = st.date_input("Platnost do:", value=d_val_date, key=f"ld_{u['id']}")
                new_key = st.text_input("Klíč", value=u['license_key'] or "", key=f"lk_{u['id']}")
                if st.button("Uložit změny", key=f"sv_{u['id']}"):
                    run_command("UPDATE users SET license_valid_until=?, license_key=? WHERE id=?",(lic_till, new_key, u['id'])); st.success("Uloženo"); st.rerun()
                if st.button("Smazat", key=f"del_{u['id']}", type="primary"):
                    run_command("DELETE FROM users WHERE id=?",(u['id'],)); st.rerun()
    with tabs[1]:
        st.write("Generování nových klíčů")
        c1,c2 = st.columns(2)
        days = c1.number_input("Dny", value=365)
        note = c2.text_input("Poznámka (pro koho)")
        if st.button("Vygenerovat klíč"):
            key = generate_license_key()
            run_command("INSERT INTO licencni_klice (kod, dny_platnosti, vygenerovano, poznamka) VALUES (?,?,?,?)", (key, days, datetime.now().isoformat(), note))
            st.success(f"Klíč: {key}")
        st.write("Seznam klíčů")
        keys = run_query("SELECT * FROM licencni_klice ORDER BY id DESC")
        for k in keys:
            status = "✅ Volný" if not k['pouzito_uzivatelem_id'] else f"❌ Použit (ID: {k['pouzito_uzivatelem_id']})"
            st.code(f"{k['kod']} | {k['dny_platnosti']} dní | {status} | {k['poznamka']}")
    
    with tabs[3]:
        st.subheader("Uvítací e-mail")
        tpl = run_query("SELECT * FROM email_templates WHERE name='welcome'", single=True)
        if tpl:
            with st.form("welcome_mail"):
                w_subj = st.text_input("Předmět", value=tpl['subject'])
                w_body = st.text_area("Text e-mailu (použij {name} pro jméno)", value=tpl['body'], height=200)
                if st.form_submit_button("Uložit šablonu"):
                    run_command("UPDATE email_templates SET subject=?, body=? WHERE name='welcome'", (w_subj, w_body))
                    st.success("Uloženo")
        st.divider()
        st.subheader("Hromadné rozesílání")
        with st.form("mass_mail"):
            m_subj = st.text_input("Předmět zprávy")
            m_body = st.text_area("Text zprávy", height=200)
            if st.form_submit_button("ODESLAT VŠEM", type="primary"):
                all_users = run_query("SELECT email FROM users WHERE role!='admin' AND email IS NOT NULL")
                if all_users:
                    prog = st.progress(0); total = len(all_users)
                    for i, u_mail in enumerate(all_users):
                        send_email_custom(u_mail['email'], m_subj, m_body)
                        prog.progress((i + 1) / total)
                        time.sleep(0.1)
                    st.success(f"Odesláno {total} uživatelům.")
                else: st.warning("Žádní uživatelé.")

# USER
else:
    menu = st.sidebar.radio(" ", ["📊 Faktury", "👥 Klienti", "🏷️ Kategorie", "⚙️ Nastavení"])
    cnt_inv = run_query("SELECT COUNT(*) FROM faktury WHERE user_id=?", (uid,), single=True)[0]
    
    if "Faktury" in menu:
        st.header("Faktury")
        years = [r[0] for r in run_query("SELECT DISTINCT strftime('%Y', datum_vystaveni) FROM faktury WHERE user_id=?", (uid,))]
        if str(datetime.now().year) not in years: years.append(str(datetime.now().year))
        sel_year = st.selectbox("Rok (Statistika)", sorted(list(set(years)), reverse=True))
        
        sc_y = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND strftime('%Y', datum_vystaveni)=?", (uid, sel_year), True)[0] or 0
        sc_a = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?", (uid,), True)[0] or 0
        su_a = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0", (uid,), True)[0] or 0
        st.markdown(f"<div class='stat-container'><div class='stat-box'><div class='stat-label'>OBRAT {sel_year}</div><div class='stat-value text-green'>{sc_y:,.0f} Kč</div></div><div class='stat-box'><div class='stat-label'>CELKEM</div><div class='stat-value text-gold'>{sc_a:,.0f} Kč</div></div><div class='stat-box'><div class='stat-label'>DLUŽÍ</div><div class='stat-value text-red'>{su_a:,.0f} Kč</div></div></div>", unsafe_allow_html=True)
        
        with st.expander("➕ Nová faktura"):
            kli = pd.read_sql("SELECT id, jmeno FROM klienti WHERE user_id=?", get_db(), params=(uid,))
            kat = pd.read_sql("SELECT id, nazev FROM kategorie WHERE user_id=?", get_db(), params=(uid,))
            if kli.empty: st.warning("Vytvořte klienta.")
            elif not is_pro and kat.empty: run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva) VALUES (?, 'Obecná', 'FV', 1, '#000000')", (uid,)); st.rerun()
            else:
                rid = st.session_state.form_reset_id; c1,c2 = st.columns(2)
                sk = c1.selectbox("Klient", kli['jmeno'], key=f"k_{rid}"); sc = c2.selectbox("Kategorie", kat['nazev'], key=f"c_{rid}")
                k_sub = kli[kli['jmeno']==sk]; c_sub = kat[kat['nazev']==sc]
                if not k_sub.empty and not c_sub.empty:
                    kid = int(k_sub['id'].values[0]); cid = int(c_sub['id'].values[0])
                    _, full, _ = get_next_invoice_number(cid, uid); st.info(f"Doklad: {full}")
                    d1,d2 = st.columns(2); dv = d1.date_input("Vystavení", date.today(), key=f"d1_{rid}"); ds = d2.date_input("Splatnost", date.today()+timedelta(14), key=f"d2_{rid}")
                    ed = st.data_editor(st.session_state.items_df, num_rows="dynamic", use_container_width=True, key=f"e_{rid}")
                    try: tot = float(pd.to_numeric(ed["Cena"], errors='coerce').fillna(0).sum())
                    except: tot = 0.0
                    st.write(f"**Celkem: {tot:,.2f} Kč**")
                    if st.button("Vystavit", type="primary", key=f"b_{rid}"):
                        fid = run_command("INSERT INTO faktury (user_id, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_splatnosti, castka_celkem, variabilni_symbol) VALUES (?,?,?,?,?,?,?,?)", (uid, full, kid, cid, dv, ds, tot, re.sub(r"\D", "", full)))
                        for _, r in ed.iterrows():
                            inam = r.get("Popis položky", ""); iprc = r.get("Cena", 0.0)
                            if inam:
                                try: ip_float = float(iprc)
                                except: ip_float = 0.0
                                run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (fid, inam, ip_float))
                        run_command("UPDATE kategorie SET aktualni_cislo = aktualni_cislo + 1 WHERE id = ?", (cid,)); reset_forms(); st.success("OK"); st.rerun()
                else: st.warning("Vyberte data.")

        st.markdown("<br>", unsafe_allow_html=True)
        clients = ["Všichni"] + [c['jmeno'] for c in run_query("SELECT jmeno FROM klienti WHERE user_id=?", (uid,))]
        sel_cli = st.selectbox("Filtr", clients)
        
        available_years_q = "SELECT DISTINCT strftime('%Y', datum_vystaveni) FROM faktury WHERE user_id=?"
        available_years_p = [uid]
        if sel_cli != "Všichni":
            available_years_q += " AND klient_id=(SELECT id FROM klienti WHERE jmeno=? AND user_id=?)"
            available_years_p.append(sel_cli); available_years_p.append(uid)
        
        av_years = [y[0] for y in run_query(available_years_q, tuple(available_years_p))]
        year_opts = ["Všechny roky"] + sorted(av_years, reverse=True)
        sel_year_filter = st.selectbox("Rok", year_opts)

        if sel_cli != "Všichni":
            sc_k = run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=?", (uid, sel_cli), True)[0] or 0
            su_k = run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=? AND f.uhrazeno=0", (uid, sel_cli), True)[0] or 0
            st.markdown(f"<div class='stat-container'><div class='stat-box'><div class='stat-label'>{sel_cli} CELKEM</div><div class='stat-value text-gold'>{sc_k:,.0f} Kč</div></div><div class='stat-box'><div class='stat-label'>{sel_cli} DLUŽÍ</div><div class='stat-value text-red'>{su_k:,.0f} Kč</div></div></div>", unsafe_allow_html=True)

        q = "SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=?"; p = [uid]
        if sel_cli != "Všichni": q += " AND k.jmeno=?"; p.append(sel_cli)
        if sel_year_filter != "Všechny roky": q += " AND strftime('%Y', f.datum_vystaveni)=?"; p.append(sel_year_filter)
        q += " ORDER BY f.id DESC LIMIT 50"
        
        df_faktury = pd.read_sql(q, get_db(), params=p)
        for index, r in df_faktury.iterrows():
            row = r.to_dict()
            c_full = row.get('cislo_full') if row.get('cislo_full') else f"F{row['id']}"
            with st.expander(f"{'✅' if row['uhrazeno'] else '⏳'} {c_full} | {row['jmeno']} | {row['castka_celkem']:.0f} Kč"):
                c1,c2,c3 = st.columns([1,1,1])
                if row['uhrazeno']: 
                    if c1.button("Zrušit úhradu", key=f"u0_{row['id']}"): run_command("UPDATE faktury SET uhrazeno=0 WHERE id=?",(row['id'],)); st.rerun()
                else: 
                    if c1.button("Zaplaceno", key=f"u1_{row['id']}"): run_command("UPDATE faktury SET uhrazeno=1 WHERE id=?",(row['id'],)); st.rerun()
                
                pdf_bytes = generate_pdf(row['id'], uid, is_pro)
                if pdf_bytes:
                    c2.download_button("PDF", pdf_bytes, f"{c_full}.pdf", "application/pdf", key=f"pd_{row['id']}")
                else:
                    c2.error("Chyba PDF")
                
                f_edit_key = f"edit_f_{row['id']}"
                if f_edit_key not in st.session_state: st.session_state[f_edit_key] = False
                if c3.button("✏️ Upravit", key=f"be_{row['id']}"): st.session_state[f_edit_key] = True; st.rerun()
                if st.session_state[f_edit_key]:
                    with st.form(f"fe_{row['id']}"):
                        nd = st.date_input("Splatnost", pd.to_datetime(row['datum_splatnosti']))
                        nm = st.text_input("Popis", row['muj_popis'] or "")
                        cur_i = pd.read_sql("SELECT nazev as 'Popis položky', cena as 'Cena' FROM faktura_polozky WHERE faktura_id=?", get_db(), params=(row['id'],))
                        ned = st.data_editor(cur_i, num_rows="dynamic", use_container_width=True)
                        if st.form_submit_button("Uložit změny"):
                            ntot = 0.0
                            try: ntot = float(pd.to_numeric(ned["Cena"], errors='coerce').fillna(0).sum())
                            except: pass
                            run_command("UPDATE faktury SET datum_splatnosti=?, muj_popis=?, castka_celkem=? WHERE id=?", (nd, nm, ntot, row['id']))
                            run_command("DELETE FROM faktura_polozky WHERE faktura_id=?", (row['id'],))
                            for idx2, rw in ned.iterrows():
                                iname = rw.get("Popis položky", ""); iprice = rw.get("Cena", 0.0)
                                if iname:
                                    try: ip_float = float(iprice)
                                    except: ip_float = 0.0
                                    run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (row['id'], iname, ip_float))
                            st.session_state[f_edit_key] = False; st.rerun()
                if st.button("Smazat", key=f"bd_{row['id']}"): run_command("DELETE FROM faktury WHERE id=?",(row['id'],)); st.rerun()

    elif "Klienti" in menu:
        st.header("Klienti")
        rid = st.session_state.form_reset_id
        if not is_pro and run_query("SELECT COUNT(*) FROM klienti WHERE user_id=?",(uid,),True)[0] >= 3: st.error("Limit 3 klienti (FREE)")
        else:
            with st.expander("➕ Přidat"):
                c1,c2=st.columns([3,1]); ico=c1.text_input("IČO",key=f"a_{rid}")
                if c2.button("ARES",key=f"b_{rid}"):
                    d=get_ares_data(ico); 
                    if d: st.session_state.ares_data=d; st.success("OK")
                    else: st.error("Nenalezeno (zkuste zadat ručně)")
                ad = st.session_state.ares_data
                with st.form("fc"):
                    j=st.text_input("Jméno", ad.get('jmeno','')); a=st.text_area("Adresa", ad.get('adresa',''))
                    i=st.text_input("IČ", ad.get('ico','')); d=st.text_input("DIČ", ad.get('dic','')); p=st.text_area("Poznámka")
                    if st.form_submit_button("Uložit"): run_command("INSERT INTO klienti (user_id, jmeno, adresa, ico, dic, poznamka) VALUES (?,?,?,?,?,?)", (uid,j,a,i,d,p)); reset_forms(); st.rerun()
        for k in run_query("SELECT * FROM klienti WHERE user_id=?", (uid,)):
            with st.expander(k['jmeno']):
                if k['poznamka']: st.info(k['poznamka'])
                ekey = f"ek_{k['id']}"
                if ekey not in st.session_state: st.session_state[ekey] = False
                c1,c2=st.columns(2)
                if c1.button("✏️ Upravit", key=f"bek_{k['id']}"): st.session_state[ekey] = True; st.rerun()
                if c2.button("Smazat", key=f"bdk_{k['id']}"): run_command("DELETE FROM klienti WHERE id=?",(k['id'],)); st.rerun()
                if st.session_state[ekey]:
                    with st.form(f"fek_{k['id']}"):
                        nj=st.text_input("Jméno", k['jmeno']); na=st.text_area("Adresa", k['adresa'])
                        ni=st.text_input("IČ", k['ico']); nd=st.text_input("DIČ", k['dic']); np=st.text_area("Poznámka", k['poznamka'])
                        if st.form_submit_button("Uložit změny"):
                            run_command("UPDATE klienti SET jmeno=?, adresa=?, ico=?, dic=?, poznamka=? WHERE id=?", (nj,na,ni,nd,np,k['id']))
                            st.session_state[ekey]=False; st.rerun()

    elif "Kategorie" in menu:
        st.header("Kategorie")
        if not is_pro: st.warning("🔒 Pouze pro PRO verzi.")
        else:
            with st.expander("➕ Nová"):
                with st.form("fcat"):
                    n=st.text_input("Název"); p=st.text_input("Prefix"); s=st.number_input("Start",1); c=st.color_picker("Barva"); l=st.file_uploader("Logo")
                    if st.form_submit_button("Uložit"):
                        blob = process_logo(l)
                        run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva, logo_blob) VALUES (?,?,?,?,?,?)", (uid,n,p,s,c,blob)); st.rerun()
        for k in run_query("SELECT * FROM kategorie WHERE user_id=?", (uid,)):
            with st.expander(k['nazev']):
                eckey = f"eck_{k['id']}"
                if eckey not in st.session_state: st.session_state[eckey] = False
                c1,c2 = st.columns(2)
                if is_pro:
                    if c1.button("✏️ Upravit", key=f"bec_{k['id']}"): st.session_state[eckey] = True; st.rerun()
                else: c1.button("🔒 Upravit", disabled=True, key=f"ld_{k['id']}")
                if c2.button("Smazat", key=f"bdc_{k['id']}"): run_command("DELETE FROM kategorie WHERE id=?", (k['id'],)); st.rerun()
                if st.session_state[eckey]:
                    with st.form(f"feck_{k['id']}"):
                        nn=st.text_input("Název", k['nazev']); np=st.text_input("Prefix", k['prefix'])
                        ns=st.number_input("Číslo", value=k['aktualni_cislo']); nc=st.color_picker("Barva", k['barva'])
                        if st.form_submit_button("Uložit změny"):
                            run_command("UPDATE kategorie SET nazev=?, prefix=?, aktualni_cislo=?, barva=? WHERE id=?", (nn,np,ns,nc,k['id']))
                            st.session_state[eckey]=False; st.rerun()

    elif "Nastavení" in menu:
        st.header("Nastavení")
        res = run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1", (uid,), single=True)
        c = dict(res) if res else {}
        
        with st.expander("🔑 Licence", expanded=True):
            valid, exp = check_license_validity(uid)
            st.info(f"Platnost: **{format_date(exp) if valid else 'Neaktivní'}**")
            if not valid:
                k = st.text_input("Klíč")
                if st.button("Aktivovat"): 
                    kdb = run_query("SELECT * FROM licencni_klice WHERE kod=? AND pouzito_uzivatelem_id IS NULL", (k,), True)
                    if kdb:
                        ne = date.today() + timedelta(days=kdb['dny_platnosti'])
                        run_command("UPDATE users SET license_key=?, license_valid_until=? WHERE id=?", (k, ne, uid))
                        run_command("UPDATE licencni_klice SET pouzito_uzivatelem_id=? WHERE id=?", (uid, kdb['id']))
                        st.session_state.is_pro=True; st.balloons(); st.rerun()
                    else: st.error("Neplatný")
            if st.button("Deaktivovat licenci"): run_command("UPDATE users SET license_key=NULL, license_valid_until=NULL WHERE id=?",(uid,)); st.session_state.is_pro=False; st.rerun()
            
            st.divider(); st.write("**Změna hesla**")
            p1=st.text_input("Staré",type="password"); p2=st.text_input("Nové",type="password")
            if st.button("Změnit"):
                u = run_query("SELECT * FROM users WHERE id=?",(uid,),True)
                if u['password_hash']==hash_password(p1): run_command("UPDATE users SET password_hash=? WHERE id=?",(hash_password(p2),uid)); st.success("OK")
                else: st.error("Chyba")

        with st.expander("🏢 Moje Firma"):
            with st.form("setf"):
                n=st.text_input("Název", c.get('nazev', full_name_display)); a=st.text_area("Adresa", c.get('adresa',''))
                i=st.text_input("IČO", c.get('ico','')); d=st.text_input("DIČ", c.get('dic',''))
                b=st.text_input("Banka", c.get('banka','')); u=st.text_input("Účet", c.get('ucet','')); ib=st.text_input("IBAN", c.get('iban',''))
                if st.form_submit_button("Uložit"):
                    ib_cl = ib.replace(" ", "").upper() if ib else ""
                    if c.get('id'): run_command("UPDATE nastaveni SET nazev=?, adresa=?, ico=?, dic=?, banka=?, ucet=?, iban=? WHERE id=?", (n,a,i,d,b,u,ib_cl,c['id']))
                    else: run_command("INSERT INTO nastaveni (user_id, nazev, adresa, ico, dic, banka, ucet, iban) VALUES (?,?,?,?,?,?,?,?)", (uid,n,a,i,d,b,u,ib_cl))
                    st.rerun()
        
        with st.expander(f"🔔 Upozornění {'(PRO)' if not is_pro else ''}"):
            if not is_pro: st.warning("🔒 Pouze pro PRO verzi.")
            else:
                act = st.toggle("Aktivní", value=bool(c.get('notify_active', 0)))
                ne = st.text_input("Email", value=c.get('notify_email',''))
                if st.button("Uložit SMTP"):
                    run_command("UPDATE nastaveni SET notify_active=?, notify_email=? WHERE id=?", (int(act), ne, c.get('id'))); st.success("Uloženo")

        if is_pro:
            with st.expander("💾 Zálohování dat (PRO)"):
                def get_bk():
                    data={}
                    for t in ['nastaveni','klienti','kategorie','faktury','faktura_polozky']:
                        cols = [i[1] for i in get_db().execute(f"PRAGMA table_info({t})")]; q=f"SELECT * FROM {t} WHERE user_id=?"; p=(uid,)
                        if 'user_id' not in cols: q=f"SELECT * FROM {t}"; p=() 
                        if t=='faktura_polozky': q="SELECT fp.* FROM faktura_polozky fp JOIN faktury f ON fp.faktura_id=f.id WHERE f.user_id=?"; p=(uid,)
                        df = pd.read_sql(q, get_db(), params=p)
                        if 'logo_blob' in df.columns: df['logo_blob'] = df['logo_blob'].apply(lambda x: base64.b64encode(x).decode('utf-8') if x else None)
                        data[t] = df.to_dict(orient='records')
                    return json.dumps(data, default=str)
                st.download_button("Export dat", get_bk(), "zaloha.json", "application/json")
                
                upl = st.file_uploader("Import dat", type="json")
                if upl and st.button("Obnovit"):
                    try:
                        d = json.load(upl)
                        run_command("DELETE FROM nastaveni WHERE user_id=?", (uid,))
                        run_command("DELETE FROM klienti WHERE user_id=?", (uid,))
                        run_command("DELETE FROM kategorie WHERE user_id=?", (uid,))
                        faktury_ids = run_query("SELECT id FROM faktury WHERE user_id=?", (uid,))
                        for f in faktury_ids: run_command("DELETE FROM faktura_polozky WHERE faktura_id=?", (f['id'],))
                        run_command("DELETE FROM faktury WHERE user_id=?", (uid,))
                        for row in d.get('nastaveni', []):
                            run_command("INSERT INTO nastaveni (user_id, nazev, adresa, ico, dic, ucet, banka, email, telefon, iban) VALUES (?,?,?,?,?,?,?,?,?,?)", (uid, row.get('nazev'), row.get('adresa'), row.get('ico'), row.get('dic'), row.get('ucet'), row.get('banka'), row.get('email'), row.get('telefon'), row.get('iban')))
                        for row in d.get('klienti', []):
                            run_command("INSERT INTO klienti (user_id, jmeno, adresa, ico, dic, email, poznamka) VALUES (?,?,?,?,?,?,?)", (uid, row.get('jmeno'), row.get('adresa'), row.get('ico'), row.get('dic'), row.get('email'), row.get('poznamka')))
                        for row in d.get('kategorie', []):
                            blob = base64.b64decode(row.get('logo_blob')) if row.get('logo_blob') else None
                            run_command("INSERT INTO kategorie (user_id, nazev, barva, prefix, aktualni_cislo, logo_blob) VALUES (?,?,?,?,?,?)", (uid, row.get('nazev'), row.get('barva'), row.get('prefix'), row.get('aktualni_cislo'), blob))
                        for row in d.get('faktury', []):
                            new_fid = run_command("INSERT INTO faktury (user_id, cislo, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_duzp, datum_splatnosti, castka_celkem, zpusob_uhrady, variabilni_symbol, cislo_objednavky, uvodni_text, uhrazeno, muj_popis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (uid, row.get('cislo'), row.get('cislo_full'), row.get('klient_id'), row.get('kategorie_id'), row.get('datum_vystaveni'), row.get('datum_duzp'), row.get('datum_splatnosti'), row.get('castka_celkem'), row.get('zpusob_uhrady'), row.get('variabilni_symbol'), row.get('cislo_objednavky'), row.get('uvodni_text'), row.get('uhrazeno'), row.get('muj_popis')))
                            old_fid = row.get('id')
                            for item in d.get('faktura_polozky', []):
                                if item.get('faktura_id') == old_fid:
                                    run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (new_fid, item.get('nazev'), item.get('cena')))
                        st.success("Obnoveno!"); st.rerun()
                    except: st.error("Chyba souboru")
        else:
            with st.expander("💾 Zálohování"): st.info("Zálohování dostupné v PRO verzi.")
