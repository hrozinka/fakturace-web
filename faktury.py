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
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from PIL import Image
from fpdf import FPDF
import qrcode

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

DB_FILE = 'fakturace_v41_pro.db'
FONT_FILE = 'arial.ttf' # Očekáváme soubor lokálně

# --- 1. DESIGN ---
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
    try: c.execute("INSERT OR IGNORE INTO email_templates (name, subject, body) VALUES ('welcome', 'Vítejte v Fakturace Pro', 'Dobrý den {name},\n\nVáš účet byl úspěšně vytvořen.')")
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
    try: return datetime.strptime(d[:10], '%Y-%m-%d').strftime('%d.%m.%Y') if isinstance(d, str) else d.strftime('%d.%m.%Y')
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

def get_ares_data(ico):
    import urllib3; urllib3.disable_warnings()
    if not ico: return None
    ico = "".join(filter(str.isdigit, str(ico))).zfill(8)
    try:
        r = requests.get(f"https://ares.gov.cz/ekonomicke-subjekty/v-1/ekonomicke-subjekty/{ico}", headers={"accept": "application/json", "User-Agent": "Mozilla/5.0"}, verify=False, timeout=5)
        if r.status_code == 200:
            d = r.json(); s = d.get('sidlo', {})
            adr = s.get('textovaAdresa', f"{s.get('nazevUlice','')} {s.get('cisloDomovni','')}/{s.get('cisloOrientacni','')}, {s.get('psc','')} {s.get('nazevObce','')}".strip(' ,/'))
            return {"jmeno": d.get('obchodniJmeno', ''), "adresa": adr, "ico": ico, "dic": d.get('dic', '')}
    except: pass
    return None

def process_logo(uploaded_file):
    if not uploaded_file: return None
    try:
        img = Image.open(uploaded_file)
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        b = io.BytesIO(); img.save(b, format='PNG'); return b.getvalue()
    except: return None

def send_email_custom(to, sub, body):
    if not SYSTEM_EMAIL["enabled"] or not SYSTEM_EMAIL["password"]: return False
    try:
        msg = MIMEMultipart(); msg['From'] = formataddr((SYSTEM_EMAIL["display_name"], SYSTEM_EMAIL["email"])); msg['To'] = to; msg['Subject'] = sub; msg.attach(MIMEText(body, 'plain'))
        s = smtplib.SMTP_SSL(SYSTEM_EMAIL["server"], SYSTEM_EMAIL["port"]); s.login(SYSTEM_EMAIL["email"], SYSTEM_EMAIL["password"]); s.sendmail(SYSTEM_EMAIL["email"], to, msg.as_string()); s.quit(); return True
    except: return False

def send_welcome_email_db(to, name):
    tpl = run_query("SELECT subject, body FROM email_templates WHERE name='welcome'", single=True)
    s, b = (tpl['subject'], tpl['body'].replace("{name}", name)) if tpl else ("Vítejte", f"Dobrý den {name},\n\nVáš účet byl vytvořen.")
    return send_email_custom(to, s, b)

def get_export_data(user_id):
    export_data = {}
    conn = get_db()
    try:
        for t in ['nastaveni', 'klienti', 'kategorie', 'faktury']:
            df = pd.read_sql(f"SELECT * FROM {t} WHERE user_id=?", conn, params=(user_id,))
            if 'logo_blob' in df.columns:
                df['logo_blob'] = df['logo_blob'].apply(lambda x: base64.b64encode(x).decode('utf-8') if x else None)
            export_data[t] = df.to_dict(orient='records')
        df_pol = pd.read_sql("SELECT fp.* FROM faktura_polozky fp JOIN faktury f ON fp.faktura_id=f.id WHERE f.user_id=?", conn, params=(user_id,))
        export_data['faktura_polozky'] = df_pol.to_dict(orient='records')
    except Exception as e: print(f"Export Error: {e}"); return "{}"
    finally: conn.close()
    return json.dumps(export_data, default=str)

# --- GENERACE PDF (OLD SCHOOL STYLE) ---
def generate_pdf(faktura_id, uid, is_pro):
    # Zjistíme, jestli máme font
    use_custom_font = os.path.exists(FONT_FILE)
    
    # Funkce pro text (pokud font nemáme, odstraníme diakritiku)
    def txt(text):
        if not text: return ""
        text = str(text)
        if use_custom_font: return text
        return remove_accents(text)

    class PDF(FPDF):
        def header(self):
            # Nastavení fontu v hlavičce
            if use_custom_font:
                try:
                    self.add_font('ArialCS', '', FONT_FILE, uni=True)
                    self.add_font('ArialCS', 'B', FONT_FILE, uni=True)
                    self.set_font('ArialCS', 'B', 24)
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
        
        # Nastavení fontu pro tělo
        if use_custom_font:
            pdf.set_font('ArialCS', '', 10)
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
            try: c = data['barva'].lstrip('#'); r, g, b = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
            except: pass

        cislo_f = data['cislo_full'] if data['cislo_full'] else f"{data['prefix']}{data['cislo']}"

        pdf.set_text_color(100); pdf.set_y(40)
        pdf.cell(95, 5, "DODAVATEL:", 0, 0); pdf.cell(95, 5, "ODBĚRATEL:", 0, 1); pdf.set_text_color(0)
        y = pdf.get_y()
        
        # Dodavatel
        if use_custom_font: pdf.set_font('ArialCS', 'B', 11)
        else: pdf.set_font('Arial', 'B', 11)
        pdf.cell(95, 5, txt(moje.get('nazev','')), 0, 1)
        
        if use_custom_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)
        pdf.multi_cell(95, 5, txt(f"{moje.get('adresa','')}\nIC: {moje.get('ico','')}\nDIC: {moje.get('dic','')}\n{moje.get('email','')}"))
        
        # Odběratel
        pdf.set_xy(105, y)
        if use_custom_font: pdf.set_font('ArialCS', 'B', 11)
        else: pdf.set_font('Arial', 'B', 11)
        pdf.cell(95, 5, txt(data['k_jmeno']), 0, 1)
        
        pdf.set_xy(105, pdf.get_y())
        if use_custom_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)
        pdf.multi_cell(95, 5, txt(f"{data['k_adresa']}\nIC: {data['k_ico']}\nDIC: {data['k_dic']}"))
        
        pdf.ln(10)
        pdf.set_fill_color(r, g, b); pdf.rect(10, pdf.get_y(), 190, 2, 'F'); pdf.ln(5)
        
        if use_custom_font: pdf.set_font('ArialCS', 'B', 12)
        else: pdf.set_font('Arial', 'B', 12)
        pdf.cell(100, 8, txt(f"Faktura c.: {cislo_f}"), 0, 1)
        
        if use_custom_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)
        pdf.cell(50, 6, "Vystaveno:", 0, 0); pdf.cell(50, 6, format_date(data['datum_vystaveni']), 0, 1)
        pdf.cell(50, 6, "Splatnost:", 0, 0); pdf.cell(50, 6, format_date(data['datum_splatnosti']), 0, 1)
        pdf.cell(50, 6, "Ucet:", 0, 0); pdf.cell(50, 6, txt(moje.get('ucet','')), 0, 1)
        pdf.cell(50, 6, "VS:", 0, 0); pdf.cell(50, 6, txt(data['variabilni_symbol']), 0, 1)
        
        pdf.ln(15)
        pdf.set_fill_color(240)
        pdf.cell(140, 8, "POLOZKA", 1, 0, 'L', True); pdf.cell(50, 8, "CENA", 1, 1, 'R', True)
        
        for p in polozky:
            pdf.cell(140, 8, txt(p['nazev']), 1); pdf.cell(50, 8, f"{p['cena']:.2f} Kc", 1, 1, 'R')
            
        pdf.ln(5)
        if use_custom_font: pdf.set_font('ArialCS', 'B', 14)
        else: pdf.set_font('Arial', 'B', 14)
        pdf.cell(190, 10, f"CELKEM: {data['castka_celkem']:.2f} Kc", 0, 1, 'R')
        
        if is_pro and moje.get('iban'):
            try:
                qr = f"SPD*1.0*ACC:{moje['iban']}*AM:{data['castka_celkem']}*CC:CZK*MSG:{cislo_f}"
                q = qrcode.make(qr); fn_q = f"q_{faktura_id}.png"; q.save(fn_q)
                pdf.image(fn_q, 10, pdf.get_y()-20, 30); os.remove(fn_q)
            except: pass
            
        # DŮLEŽITÉ: encode('latin-1') pro binární string, který Streamlit potřebuje pro stažení
        return pdf.output(dest='S').encode('latin-1')
    except Exception as e:
        print(f"Chyba PDF: {e}")
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
                        send_welcome_email_db(e, f); st.success("Hotovo! Přihlašte se.")
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
    st.markdown("""<div class='alert-box'><h3>⚠️ Změna hesla vyžadována</h3></div>""", unsafe_allow_html=True)
    with st.form("force_change"):
        np1 = st.text_input("Nové heslo", type="password"); np2 = st.text_input("Potvrzení hesla", type="password")
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
        for u in run_query("SELECT * FROM users WHERE role!='admin' ORDER BY id DESC"):
            with st.expander(f"{u['username']} ({u['email']})"):
                st.markdown(f"**Tel:** {u['phone']} | **Aktivní:** {format_date(u['last_active'])}")
                ld = u['license_valid_until']
                val_date = datetime.strptime(str(ld)[:10], '%Y-%m-%d').date() if ld else date.today()
                lic_till = st.date_input("Platnost do:", value=val_date, key=f"ld_{u['id']}")
                new_key = st.text_input("Klíč", value=u['license_key'] or "", key=f"lk_{u['id']}")
                if st.button("Uložit", key=f"sv_{u['id']}"): run_command("UPDATE users SET license_valid_until=?, license_key=? WHERE id=?",(lic_till, new_key, u['id'])); st.rerun()
                if st.button("Smazat", key=f"del_{u['id']}", type="primary"): run_command("DELETE FROM users WHERE id=?",(u['id'],)); st.rerun()
    with tabs[1]:
        days_val = st.number_input("Délka platnosti (dny)", value=365, min_value=1)
        note_val = st.text_input("Poznámka (pro koho)")
        if st.button("Vygenerovat klíč"):
            k = generate_license_key(); run_command("INSERT INTO licencni_klice (kod, dny_platnosti, vygenerovano, poznamka) VALUES (?,?,?,?)", (k, days_val, datetime.now().isoformat(), note_val)); st.success(k)
        for k in run_query("SELECT * FROM licencni_klice ORDER BY id DESC"): st.code(f"{k['kod']} | {k['dny_platnosti']} dní | {'Použit' if k['pouzito_uzivatelem_id'] else 'Volný'} | {k['poznamka']}")
    with tabs[3]:
        tpl = run_query("SELECT * FROM email_templates WHERE name='welcome'", single=True)
        with st.form("wm"):
            ws = st.text_input("Předmět", value=tpl['subject'] if tpl else ""); wb = st.text_area("Text", value=tpl['body'] if tpl else "")
            if st.form_submit_button("Uložit"): run_command("INSERT OR REPLACE INTO email_templates (id, name, subject, body) VALUES ((SELECT id FROM email_templates WHERE name='welcome'), 'welcome', ?, ?)", (ws, wb)); st.success("OK")
        with st.form("mm"):
            ms = st.text_input("Předmět"); mb = st.text_area("Zpráva")
            if st.form_submit_button("Odeslat všem"):
                for u in run_query("SELECT email FROM users WHERE role!='admin' AND email IS NOT NULL"): send_email_custom(u['email'], ms, mb)
                st.success("Odesláno")

# USER
else:
    menu = st.sidebar.radio(" ", ["📊 Faktury", "👥 Klienti", "🏷️ Kategorie", "⚙️ Nastavení"])
    
    if "Faktury" in menu:
        st.header("Faktury")
        years = [r[0] for r in run_query("SELECT DISTINCT strftime('%Y', datum_vystaveni) FROM faktury WHERE user_id=?", (uid,))]
        if str(datetime.now().year) not in years: years.append(str(datetime.now().year))
        
        sy = st.selectbox("Rok (Statistika)", sorted(list(set(years)), reverse=True))
        sc_y = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND strftime('%Y', datum_vystaveni)=?", (uid, sy), True)[0] or 0
        sc_a = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?", (uid,), True)[0] or 0
        su_a = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0", (uid,), True)[0] or 0
        st.markdown(f"<div class='stat-container'><div class='stat-box'><div class='stat-label'>OBRAT {sy}</div><div class='stat-value text-green'>{sc_y:,.0f}</div></div><div class='stat-box'><div class='stat-label'>CELKEM</div><div class='stat-value text-gold'>{sc_a:,.0f}</div></div><div class='stat-box'><div class='stat-label'>DLUŽÍ</div><div class='stat-value text-red'>{su_a:,.0f}</div></div></div>", unsafe_allow_html=True)
        
        with st.expander("➕ Nová faktura"):
            kli = pd.read_sql("SELECT id, jmeno FROM klienti WHERE user_id=?", get_db(), params=(uid,))
            kat = pd.read_sql("SELECT id, nazev FROM kategorie WHERE user_id=?", get_db(), params=(uid,))
            if kli.empty: st.warning("Vytvořte klienta.")
            elif not is_pro and kat.empty: run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva) VALUES (?, 'Obecná', 'FV', 1, '#000000')", (uid,)); st.rerun()
            else:
                rid = st.session_state.form_reset_id; c1,c2 = st.columns(2)
                sk = c1.selectbox("Klient", kli['jmeno'], key=f"k_{rid}"); sc = c2.selectbox("Kategorie", kat['nazev'], key=f"c_{rid}")
                if not kli[kli['jmeno']==sk].empty and not kat[kat['nazev']==sc].empty:
                    kid = int(kli[kli['jmeno']==sk]['id'].values[0]); cid = int(kat[kat['nazev']==sc]['id'].values[0])
                    _, full, _ = get_next_invoice_number(cid, uid); st.info(f"Doklad: {full}")
                    d1,d2 = st.columns(2); dv = d1.date_input("Vystavení", date.today(), key=f"d1_{rid}"); ds = d2.date_input("Splatnost", date.today()+timedelta(14), key=f"d2_{rid}")
                    ed = st.data_editor(st.session_state.items_df, num_rows="dynamic", use_container_width=True, key=f"e_{rid}")
                    if st.button("Vystavit", type="primary", key=f"b_{rid}"):
                        fid = run_command("INSERT INTO faktury (user_id, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_splatnosti, castka_celkem, variabilni_symbol) VALUES (?,?,?,?,?,?,?,?)", (uid, full, kid, cid, dv, ds, float(pd.to_numeric(ed["Cena"], errors='coerce').fillna(0).sum()), re.sub(r"\D", "", full)))
                        for _, r in ed.iterrows(): 
                            if r.get("Popis položky"): run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (fid, r["Popis položky"], float(r.get("Cena", 0))))
                        run_command("UPDATE kategorie SET aktualni_cislo = aktualni_cislo + 1 WHERE id = ?", (cid,)); reset_forms(); st.success("OK"); st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        sel_cli = st.selectbox("Filtr Klient", ["Všichni"] + [c['jmeno'] for c in run_query("SELECT jmeno FROM klienti WHERE user_id=?", (uid,))])
        db_years = [y[0] for y in run_query("SELECT DISTINCT strftime('%Y', datum_vystaveni) FROM faktury WHERE user_id=?", (uid,))]
        sel_yf = st.selectbox("Filtr Rok", ["Všechny"] + sorted(db_years, reverse=True))

        if sel_cli != "Všichni":
            sck = run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=?", (uid, sel_cli), True)[0] or 0
            suk = run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=? AND f.uhrazeno=0", (uid, sel_cli), True)[0] or 0
            st.markdown(f"<div class='stat-container'><div class='stat-box'><div class='stat-label'>{sel_cli}</div><div class='stat-value text-gold'>{sck:,.0f}</div></div><div class='stat-box'><div class='stat-label'>DLUŽÍ</div><div class='stat-value text-red'>{suk:,.0f}</div></div></div>", unsafe_allow_html=True)

        q = "SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=?"; p = [uid]
        if sel_cli != "Všichni": q += " AND k.jmeno=?"; p.append(sel_cli)
        if sel_yf != "Všechny": q += " AND strftime('%Y', f.datum_vystaveni)=?"; p.append(sel_yf)
        
        df_faktury = pd.read_sql(q + " ORDER BY f.id DESC LIMIT 50", get_db(), params=p)
        faktury_list = df_faktury.to_dict('records')
        
        for row in faktury_list:
            cf = row.get('cislo_full') or f"F{row['id']}"
            with st.expander(f"{'✅' if row['uhrazeno'] else '⏳'} {cf} | {row['jmeno']} | {row['castka_celkem']:.0f} Kč"):
                c1,c2,c3 = st.columns([1,1,1])
                if row['uhrazeno']: 
                    if c1.button("Zrušit úhradu", key=f"u0_{row['id']}"): run_command("UPDATE faktury SET uhrazeno=0 WHERE id=?",(row['id'],)); st.rerun()
                else: 
                    if c1.button("Zaplaceno", key=f"u1_{row['id']}"): run_command("UPDATE faktury SET uhrazeno=1 WHERE id=?",(row['id'],)); st.rerun()
                
                pdf = generate_pdf(row['id'], uid, is_pro)
                if pdf: c2.download_button("PDF", pdf, f"{cf}.pdf", "application/pdf", key=f"pd_{row['id']}")
                else: c2.error("Chyba PDF")
                
                if c3.button("Smazat", key=f"bd_{row['id']}"): run_command("DELETE FROM faktury WHERE id=?",(row['id'],)); st.rerun()

    elif "Klienti" in menu:
        st.header("Klienti")
        rid = st.session_state.form_reset_id
        with st.expander("➕ Přidat"):
            c1,c2=st.columns([3,1]); ico=c1.text_input("IČO",key=f"a_{rid}")
            if c2.button("ARES",key=f"b_{rid}"):
                d=get_ares_data(ico); 
                if d: st.session_state.ares_data=d; st.success("OK")
                else: st.error("Nenalezeno")
            ad = st.session_state.ares_data
            with st.form("fc"):
                j=st.text_input("Jméno", ad.get('jmeno','')); a=st.text_area("Adresa", ad.get('adresa',''))
                i=st.text_input("IČ", ad.get('ico','')); d=st.text_input("DIČ", ad.get('dic','')); p=st.text_area("Poznámka")
                if st.form_submit_button("Uložit"): run_command("INSERT INTO klienti (user_id, jmeno, adresa, ico, dic, poznamka) VALUES (?,?,?,?,?,?)", (uid,j,a,i,d,p)); reset_forms(); st.rerun()
        for k in run_query("SELECT * FROM klienti WHERE user_id=?", (uid,)):
            with st.expander(k['jmeno']):
                if k['poznamka']: st.info(k['poznamka'])
                if st.button("Smazat", key=f"bdk_{k['id']}"): run_command("DELETE FROM klienti WHERE id=?",(k['id'],)); st.rerun()

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
                if st.button("Smazat", key=f"bdc_{k['id']}"): run_command("DELETE FROM kategorie WHERE id=?", (k['id'],)); st.rerun()

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
        
        if is_pro:
            with st.expander("💾 Zálohování dat (PRO)"):
                st.download_button("Export dat", get_export_data(uid), "zaloha.json", "application/json")
                upl = st.file_uploader("Import dat", type="json")
                if upl and st.button("Obnovit / Sloučit"):
                    try:
                        d = json.load(upl)
                        client_map = {}; cat_map = {}
                        
                        for r in d.get('nastaveni', []):
                            exist = run_query("SELECT id FROM nastaveni WHERE user_id=?", (uid,), True)
                            if exist: run_command("UPDATE nastaveni SET nazev=?, adresa=?, ico=?, dic=?, ucet=?, banka=?, email=?, telefon=?, iban=? WHERE id=?", (r.get('nazev'), r.get('adresa'), r.get('ico'), r.get('dic'), r.get('ucet'), r.get('banka'), r.get('email'), r.get('telefon'), r.get('iban'), exist['id']))
                            else: run_command("INSERT INTO nastaveni (user_id, nazev, adresa, ico, dic, ucet, banka, email, telefon, iban) VALUES (?,?,?,?,?,?,?,?,?,?)", (uid, r.get('nazev'), r.get('adresa'), r.get('ico'), r.get('dic'), r.get('ucet'), r.get('banka'), r.get('email'), r.get('telefon'), r.get('iban')))
                        
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
                            cid = client_map.get(r.get('klient_id'))
                            kid = cat_map.get(r.get('kategorie_id'))
                            if cid and kid:
                                exist_f = run_query("SELECT id FROM faktury WHERE cislo_full=? AND user_id=?", (r.get('cislo_full'), uid), True)
                                if not exist_f:
                                    new_fid = run_command("INSERT INTO faktury (user_id, cislo, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_duzp, datum_splatnosti, castka_celkem, zpusob_uhrady, variabilni_symbol, cislo_objednavky, uvodni_text, uhrazeno, muj_popis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (uid, r.get('cislo'), r.get('cislo_full'), cid, kid, r.get('datum_vystaveni'), r.get('datum_duzp'), r.get('datum_splatnosti'), r.get('castka_celkem'), r.get('zpusob_uhrady'), r.get('variabilni_symbol'), r.get('cislo_objednavky'), r.get('uvodni_text'), r.get('uhrazeno'), r.get('muj_popis')))
                                    for item in d.get('faktura_polozky', []):
                                        if item.get('faktura_id') == r.get('id'):
                                            run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (new_fid, item.get('nazev'), item.get('cena')))
                        
                        st.success("Hotovo! Data byla sloučena."); st.rerun()
                    except Exception as e: st.error(f"Chyba: {e}")
        else:
            with st.expander("💾 Zálohování"): st.info("Zálohování dostupné v PRO verzi.")
