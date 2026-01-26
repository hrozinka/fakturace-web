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

DB_FILE = 'fakturace_v21_final.db'

# --- 1. DESIGN (MOBILE FIRST + UI/UX) ---
st.set_page_config(page_title="Fakturace Pro", page_icon="💎", layout="centered")

st.markdown("""
    <style>
    /* === ZÁKLAD === */
    .stApp { background-color: #0f172a; color: #f8fafc; font-family: 'Segoe UI', Roboto, sans-serif; }
    
    /* === INPUTY === */
    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #1e293b !important; border: 1px solid #334155 !important; color: #fff !important;
        border-radius: 12px !important; padding: 12px !important;
    }
    
    /* === MENU (SIDEBAR) === */
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }
    
    section[data-testid="stSidebar"] .stRadio label {
        width: 100% !important;
        display: flex !important;
        justify-content: flex-start !important;
        align-items: center !important;
        background-color: #1e293b !important;
        padding: 18px 20px !important; /* Optimální výška pro PC */
        margin-bottom: 8px !important;
        border-radius: 12px !important;
        border: 1px solid #334155 !important;
        cursor: pointer;
        color: #94a3b8 !important;
        font-weight: 600 !important;
        font-size: 16px !important;
        transition: all 0.2s ease;
    }

    /* MOBILNÍ OPTIMALIZACE MENU */
    @media only screen and (max-width: 600px) {
        section[data-testid="stSidebar"] .stRadio label {
            padding: 24px 20px !important; /* Vyšší pro prst */
            margin-bottom: 12px !important;
            font-size: 18px !important;
        }
    }

    /* HOVER & ACTIVE */
    section[data-testid="stSidebar"] .stRadio label:hover {
        border-color: #fbbf24 !important;
        color: #fbbf24 !important;
        background-color: #334155 !important;
    }
    section[data-testid="stSidebar"] .stRadio label[data-checked="true"] {
        background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%) !important;
        color: #0f172a !important; /* Tmavý text na zlaté */
        border: none !important;
        font-weight: 800 !important;
        box-shadow: 0 4px 15px rgba(251, 191, 36, 0.4);
    }

    /* === STATISTIKY === */
    .stat-container { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
    .stat-box { 
        background: #1e293b; border-radius: 16px; padding: 15px; flex: 1; min-width: 120px;
        text-align: center; border: 1px solid #334155; box-shadow: 0 4px 6px rgba(0,0,0,0.2);
    }
    .stat-label { font-size: 12px; text-transform: uppercase; color: #94a3b8; margin-bottom: 5px; font-weight: 700; letter-spacing: 1px; }
    .stat-value { font-size: 22px; font-weight: 800; color: #fff; }
    .text-green { color: #34d399 !important; } .text-red { color: #f87171 !important; } .text-gold { color: #fbbf24 !important; }

    /* === TLAČÍTKA === */
    .stButton > button { background-color: #334155 !important; color: white !important; border-radius: 10px !important; height: 45px; font-weight: 600; border: none; width: 100%;}
    div[data-testid="stForm"] button[kind="primary"], button[kind="primary"] { background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%) !important; color: #0f172a !important; font-weight: 800 !important;}
    
    /* === LOGIN === */
    .login-container { background-color: #1e293b; padding: 40px; border-radius: 24px; border: 1px solid #334155; text-align: center; margin-top: 30px; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5); }
    
    /* === HEADER V SIDEBARU === */
    .sidebar-header { text-align: center; padding-bottom: 20px; border-bottom: 1px solid #334155; margin-bottom: 20px; }
    .sidebar-user { font-size: 18px; font-weight: bold; color: #f1f5f9; }
    .sidebar-role { font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; margin-top: 5px; }
    .badge-pro { background: #fbbf24; color: #000; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 10px; }
    .badge-free { background: #64748b; color: #fff; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 10px; }
    
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
    try:
        c.execute(sql, params); res = c.fetchone() if single else c.fetchall(); return res
    except: return None
    finally: conn.close()

def run_command(sql, params=()):
    conn = get_db(); c = conn.cursor()
    try:
        c.execute(sql, params); conn.commit(); lid = c.lastrowid; return lid
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
    c.execute('''CREATE TABLE IF NOT EXISTS faktura_polozky (id INTEGER PRIMARY KEY, faktura_id INTEGER, nazev TEXT, cena REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS licencni_klice (id INTEGER PRIMARY KEY, kod TEXT UNIQUE, dny_platnosti INTEGER, vygenerovano TEXT, pouzito_uzivatelem_id INTEGER, poznamka TEXT)''')
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

def generate_random_password(length=8):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for i in range(length))

def generate_license_key():
    return '-'.join([''.join(random.choices(string.ascii_uppercase + string.digits, k=4)) for _ in range(4)])

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
    if res:
        full_num = f"{res['prefix']}{res['aktualni_cislo']}"
        return (res['aktualni_cislo'], full_num, res['prefix'])
    return (1, "1", "")

# --- ARES ---
def get_ares_data(ico):
    import urllib3; urllib3.disable_warnings()
    if not ico: return None
    ico_clean = "".join(filter(str.isdigit, str(ico))).zfill(8)
    url = f"https://ares.gov.cz/ekonomicke-subjekty/v-1/ekonomicke-subjekty/{ico_clean}"
    headers = {"accept": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        r = requests.get(url, headers=headers, verify=False, timeout=5)
        if r.status_code == 200:
            d = r.json(); s = d.get('sidlo', {})
            text_adresa = s.get('textovaAdresa', '')
            if not text_adresa:
                ulice = s.get('nazevUlice', ''); cislo = f"{s.get('cisloDomovni','')}/{s.get('cisloOrientacni','')}".strip('/')
                if cislo == '/': cislo = s.get('cisloDomovni', '')
                obec = s.get('nazevObce', ''); psc = s.get('psc', '')
                parts = [p for p in [ulice, cislo, psc, obec] if p]
                text_adresa = ", ".join(parts)
            return {"jmeno": d.get('obchodniJmeno', ''), "adresa": text_adresa, "ico": ico_clean, "dic": d.get('dic', '')}
    except: pass
    return None

def send_email_custom(to_email, subject, body):
    if not SYSTEM_EMAIL["enabled"] or not SYSTEM_EMAIL["password"]: return False
    try:
        msg = MIMEMultipart(); msg['From'] = SYSTEM_EMAIL["email"]; msg['To'] = to_email; msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP_SSL(SYSTEM_EMAIL["server"], SYSTEM_EMAIL["port"])
        server.login(SYSTEM_EMAIL["email"], SYSTEM_EMAIL["password"])
        server.sendmail(SYSTEM_EMAIL["email"], to_email, msg.as_string()); server.quit()
        return True
    except: return False

# --- PDF ---
def generate_pdf(faktura_id, uid, is_pro):
    from fpdf import FPDF; import qrcode
    class PDF(FPDF):
        def header(self):
            if os.path.exists('arial.ttf'): 
                try: self.add_font('ArialCS','','arial.ttf',uni=True); self.add_font('ArialCS','B','arial.ttf',uni=True); self.set_font('ArialCS','B',24)
                except: self.set_font('Arial','B',24)
            else: self.set_font('Arial','B',24)
            self.set_text_color(50,50,50); self.cell(0,10,'FAKTURA',0,1,'R'); self.ln(5)
    try:
        data = run_query("SELECT f.*, k.jmeno as k_jmeno, k.adresa as k_adresa, k.ico as k_ico, k.dic as k_dic, kat.barva, kat.logo_blob FROM faktury f JOIN klienti k ON f.klient_id=k.id JOIN kategorie kat ON f.kategorie_id=kat.id WHERE f.id=? AND f.user_id=?", (faktura_id, uid), single=True)
        if not data: return "Faktura nenalezena"
        polozky = run_query("SELECT * FROM faktura_polozky WHERE faktura_id=?", (faktura_id,))
        moje = run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1", (uid,), single=True) or {}
        pdf = PDF(); pdf.add_page(); pdf.set_font('ArialCS' if os.path.exists('arial.ttf') else 'Arial', '', 10)
        if data['logo_blob']:
            try: fn=f"t_{faktura_id}.png"; open(fn,"wb").write(data['logo_blob']); pdf.image(fn,10,10,30); os.remove(fn)
            except: pass
        if is_pro:
            try: c = data['barva'].lstrip('#'); r, g, b = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
            except: r,g,b=100,100,100
        else: r,g,b = 0,0,0
        pdf.set_text_color(100); pdf.set_y(40); pdf.cell(95,5,"DODAVATEL:",0,0); pdf.cell(95,5,"ODBĚRATEL:",0,1); pdf.set_text_color(0); y = pdf.get_y()
        pdf.set_font('', '', 12); pdf.cell(95,5,remove_accents(moje.get('nazev','')),0,1); pdf.set_font('', '', 10); pdf.multi_cell(95,5,remove_accents(f"{moje.get('adresa','')}\nIČ: {moje.get('ico','')}\nDIČ: {moje.get('dic','')}\n{moje.get('email','')}"))
        pdf.set_xy(105,y); pdf.set_font('', '', 12); pdf.cell(95,5,remove_accents(data['k_jmeno']),0,1); pdf.set_xy(105,pdf.get_y()); pdf.set_font('', '', 10); pdf.multi_cell(95,5,remove_accents(f"{data['k_adresa']}\nIČ: {data['k_ico']}\nDIČ: {data['k_dic']}"))
        pdf.ln(10); pdf.set_fill_color(r, g, b); pdf.rect(10,pdf.get_y(),190,2,'F'); pdf.ln(5)
        pdf.set_font('', '', 14); pdf.cell(100,8,f"Faktura c.: {data['cislo_full']}",0,1); pdf.set_font('', '', 10)
        pdf.cell(50,6,"Vystaveno:",0,0); pdf.cell(50,6,format_date(data['datum_vystaveni']),0,1)
        pdf.cell(50,6,"Splatnost:",0,0); pdf.cell(50,6,format_date(data['datum_splatnosti']),0,1)
        pdf.cell(50,6,"Ucet:",0,0); pdf.cell(50,6,str(moje.get('ucet','')),0,1)
        pdf.cell(50,6,"VS:",0,0); pdf.cell(50,6,str(data['variabilni_symbol']),0,1)
        pdf.ln(15); pdf.set_fill_color(240); pdf.cell(140,8,"POLOZKA",1,0,'L',True); pdf.cell(50,8,"CENA",1,1,'R',True)
        for p in polozky:
            pdf.cell(140,8,remove_accents(p['nazev']),1); pdf.cell(50,8,f"{p['cena']:.2f} Kc",1,1,'R')
        pdf.ln(5); pdf.set_font('','B',14); pdf.cell(190,10,f"CELKEM: {data['castka_celkem']:.2f} Kc",0,1,'R')
        if is_pro and moje.get('iban'):
            try: qr=f"SPD*1.0*ACC:{moje['iban']}*AM:{data['castka_celkem']}*CC:CZK*MSG:{data['cislo_full']}"; img=qrcode.make(qr); img.save("q.png"); pdf.image("q.png",10,pdf.get_y()-20,30); os.remove("q.png")
            except: pass
        return pdf.output(dest='S').encode('latin-1','ignore')
    except: return b"ERROR"

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
                        run_command("INSERT INTO users (username,password_hash,full_name,email,phone,created_at,force_password_change) VALUES (?,?,?,?,?,?,1)",(u,hash_password(p),f,e,t_tel,datetime.now().isoformat()))
                        send_email_custom(e, "Vítejte", f"Dobrý den {f},\nVáš účet byl vytvořen."); st.success("Hotovo! Přihlašte se."); 
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
    tabs = st.tabs(["Uživatelé", "Licence", "Statistiky"])
    with tabs[0]:
        users = run_query("SELECT * FROM users WHERE role!='admin' ORDER BY id DESC")
        for u in users:
            with st.expander(f"{u['username']} ({u['email']})"):
                st.markdown(f"**Vytvořeno:** {format_date(u['created_at'])} | **Aktivní:** {format_date(u['last_active'])}")
                st.markdown(f"**Telefon:** {u['phone']}")
                def_val = date.today(); 
                if u['license_valid_until']:
                    try: def_val = datetime.strptime(str(u['license_valid_until'])[:10], '%Y-%m-%d').date()
                    except: pass
                lic_till = st.date_input("Platnost do:", value=def_val, key=f"ld_{u['id']}")
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

# USER
else:
    menu = st.sidebar.radio(" ", ["📊 Faktury", "👥 Klienti", "🏷️ Kategorie", "⚙️ Nastavení"])
    cnt_inv = run_query("SELECT COUNT(*) FROM faktury WHERE user_id=?", (uid,), single=True)[0]
    
    if "Faktury" in menu:
        st.header("Faktury")
        years = [r[0] for r in run_query("SELECT DISTINCT strftime('%Y', datum_vystaveni) FROM faktury WHERE user_id=?", (uid,))]
        if str(datetime.now().year) not in years: years.append(str(datetime.now().year))
        sel_year = st.selectbox("Rok", sorted(list(set(years)), reverse=True))
        
        sc_y = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND strftime('%Y', datum_vystaveni)=?", (uid, sel_year), True)[0] or 0
        sc_a = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?", (uid,), True)[0] or 0
        su_a = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0", (uid,), True)[0] or 0
        st.markdown(f"<div class='stat-container'><div class='stat-box'><div class='stat-label'>OBRAT {sel_year}</div><div class='stat-value text-green'>{sc_y:,.0f} Kč</div></div><div class='stat-box'><div class='stat-label'>CELKEM</div><div class='stat-value text-gold'>{sc_a:,.0f} Kč</div></div><div class='stat-box'><div class='stat-label'>DLUŽÍ</div><div class='stat-value text-red'>{su_a:,.0f} Kč</div></div></div>", unsafe_allow_html=True)
        
        clients = ["Všichni"] + [c['jmeno'] for c in run_query("SELECT jmeno FROM klienti WHERE user_id=?", (uid,))]
        sel_cli = st.selectbox("Filtr", clients)
        
        with st.expander("➕ Nová faktura"):
            kli = pd.read_sql("SELECT id, jmeno FROM klienti WHERE user_id=?", get_db(), params=(uid,))
            kat = pd.read_sql("SELECT id, nazev FROM kategorie WHERE user_id=?", get_db(), params=(uid,))
            if kli.empty: st.warning("Vytvořte klienta.")
            elif not is_pro and kat.empty: run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva) VALUES (?, 'Obecná', 'FV', 1, '#000000')", (uid,)); st.rerun()
            else:
                rid = st.session_state.form_reset_id; c1,c2 = st.columns(2)
                sk = c1.selectbox("Klient", kli['jmeno'], key=f"k_{rid}"); sc = c2.selectbox("Kategorie", kat['nazev'], key=f"c_{rid}")
                
                # --- OPRAVA CHYBY ZDE ---
                k_sub = kli[kli['jmeno']==sk]; c_sub = kat[kat['nazev']==sc]
                
                if not k_sub.empty and not c_sub.empty:
                    kid = int(k_sub['id'].values[0]); cid = int(c_sub['id'].values[0])
                    _, full, _ = get_next_invoice_number(cid, uid); st.info(f"Doklad: {full}")
                    d1,d2 = st.columns(2); dv = d1.date_input("Vystavení", date.today(), key=f"d1_{rid}"); ds = d2.date_input("Splatnost", date.today()+timedelta(14), key=f"d2_{rid}")
                    ed = st.data_editor(st.session_state.items_df, num_rows="dynamic", use_container_width=True, key=f"e_{rid}")
                    tot = float(pd.to_numeric(ed["Cena"], errors='coerce').fillna(0).sum()); st.write(f"**Celkem: {tot:,.2f} Kč**")
                    
                    if st.button("Vystavit", type="primary", key=f"b_{rid}"):
                        fid = run_command("INSERT INTO faktury (user_id, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_splatnosti, castka_celkem, variabilni_symbol) VALUES (?,?,?,?,?,?,?,?)", (uid, full, kid, cid, dv, ds, tot, re.sub(r"\D", "", full)))
                        for _, r in ed.iterrows(): run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (fid, r["Popis položky"], float(r["Cena"])))
                        run_command("UPDATE kategorie SET aktualni_cislo = aktualni_cislo + 1 WHERE id = ?", (cid,)); reset_forms(); st.success("OK"); st.rerun()
                else: st.warning("Vyberte data.")

        st.markdown("<br>", unsafe_allow_html=True)
        q = "SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=?"; p = [uid]
        if sel_cli != "Všichni": q += " AND k.jmeno=?"; p.append(sel_cli)
        q += " ORDER BY f.id DESC LIMIT 50"
        
        for r in pd.read_sql(q, get_db(), params=p).iterrows():
            with st.expander(f"{'✅' if r['uhrazeno'] else '⏳'} {r['cislo_full']} | {r['jmeno']} | {r['castka_celkem']:.0f} Kč"):
                c1,c2,c3 = st.columns([1,1,1])
                if r['uhrazeno']: 
                    if c1.button("Zrušit úhradu", key=f"u0_{r['id']}"): run_command("UPDATE faktury SET uhrazeno=0 WHERE id=?",(r['id'],)); st.rerun()
                else: 
                    if c1.button("Zaplaceno", key=f"u1_{r['id']}"): run_command("UPDATE faktury SET uhrazeno=1 WHERE id=?",(r['id'],)); st.rerun()
                pdf = generate_pdf(r['id'], uid, is_pro)
                if isinstance(pdf, bytes): c2.download_button("PDF", pdf, f"{r['cislo_full']}.pdf", "application/pdf", key=f"pd_{r['id']}")
                if c3.button("Smazat", key=f"bd_{r['id']}"): run_command("DELETE FROM faktury WHERE id=?",(r['id'],)); st.rerun()

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
                if st.button("Smazat", key=f"bdk_{k['id']}"): run_command("DELETE FROM klienti WHERE id=?",(k['id'],)); st.rerun()

    elif "Kategorie" in menu:
        st.header("Kategorie")
        if not is_pro: st.warning("🔒 Pouze pro PRO verzi.")
        else:
            with st.expander("➕ Nová"):
                with st.form("fcat"):
                    n=st.text_input("Název"); p=st.text_input("Prefix"); s=st.number_input("Start",1); c=st.color_picker("Barva"); l=st.file_uploader("Logo")
                    if st.form_submit_button("Uložit"): run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva, logo_blob) VALUES (?,?,?,?,?,?)", (uid,n,p,s,c,process_logo(l))); st.rerun()
        for k in run_query("SELECT * FROM kategorie WHERE user_id=?", (uid,)):
            with st.expander(k['nazev']):
                if st.button("Smazat", key=f"bdc_{k['id']}"): run_command("DELETE FROM kategorie WHERE id=?", (k['id'],)); st.rerun()

    elif "Nastavení" in menu:
        st.header("Nastavení")
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

        c = run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1", (uid,), single=True) or {}
        with st.expander("🏢 Moje Firma"):
            with st.form("setf"):
                n=st.text_input("Název", c.get('nazev', full_name_display)); a=st.text_area("Adresa", c.get('adresa',''))
                i=st.text_input("IČO", c.get('ico','')); d=st.text_input("DIČ", c.get('dic',''))
                b=st.text_input("Banka", c.get('banka','')); u=st.text_input("Účet", c.get('ucet','')); ib=st.text_input("IBAN", c.get('iban',''))
                if st.form_submit_button("Uložit"):
                    if c.get('id'): run_command("UPDATE nastaveni SET nazev=?, adresa=?, ico=?, dic=?, banka=?, ucet=?, iban=? WHERE id=?", (n,a,i,d,b,u,ib,c['id']))
                    else: run_command("INSERT INTO nastaveni (user_id, nazev, adresa, ico, dic, banka, ucet, iban) VALUES (?,?,?,?,?,?,?,?)", (uid,n,a,i,d,b,u,ib))
                    st.rerun()
        
        with st.expander(f"🔔 Upozornění {'(PRO)' if not is_pro else ''}"):
            if not is_pro: st.warning("🔒 Pouze pro PRO verzi.")
            else:
                act = st.toggle("Aktivní", value=bool(c.get('notify_active', 0)))
                ne = st.text_input("Email", value=c.get('notify_email',''))
                if st.button("Uložit SMTP"):
                    run_command("UPDATE nastaveni SET notify_active=?, notify_email=? WHERE id=?", (int(act), ne, c.get('id'))); st.success("Uloženo")

        with st.expander("💾 Záloha"):
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
