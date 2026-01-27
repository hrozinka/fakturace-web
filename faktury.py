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

# Načítání admin hesla ze secrets
try:
    admin_pass_init = st.secrets["ADMIN_INIT_PASS"]
except:
    admin_pass_init = os.getenv("ADMIN_INIT_PASS", "admin")

SYSTEM_EMAIL = {
    "enabled": True, 
    "server": "smtp.seznam.cz",
    "port": 465,
    "email": "jsem@michalkochtik.cz", 
    "password": email_pass,
    "display_name": "MojeFakturace"
}

DB_FILE = 'fakturace_v47_final.db' 
FONT_FILE = 'arial.ttf' 

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
    conn = sqlite3.connect(DB_FILE, timeout=10)
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
    
    try: c.execute("INSERT OR IGNORE INTO email_templates (name, subject, body) VALUES ('welcome', 'Vítejte ve vašem fakturačním systému', 'Dobrý den {name},\n\nVáš účet byl úspěšně vytvořen.\n\nS pozdravem,\nTým MojeFakturace')")
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
    tpl_dict = dict(tpl) if tpl else {}
    s_def = "Vítejte ve vašem fakturačním systému"
    b_def = f"Dobrý den {name},\n\nVáš účet byl úspěšně vytvořen.\n\nS pozdravem,\nTým MojeFakturace"
    s = tpl_dict.get('subject', s_def)
    b = tpl_dict.get('body', b_def).replace("{name}", name)
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

# --- PDF GENERACE ---
def generate_pdf(faktura_id, uid, is_pro):
    use_font = os.path.exists(FONT_FILE)
    
    def txt(text):
        if text is None: return ""
        text = str(text)
        if use_font: return text
        return remove_accents(text)

    # Funkce pro formátování měny (1 000,00)
    def fmt_price(val):
        return f"{val:,.2f}".replace(",", " ").replace(".", ",")

    class PDF(FPDF):
        def header(self):
            if use_font:
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
        raw_data = run_query("SELECT f.*, k.jmeno as k_jmeno, k.adresa as k_adresa, k.ico as k_ico, k.dic as k_dic, kat.barva, kat.logo_blob, kat.prefix FROM faktury f JOIN klienti k ON f.klient_id=k.id JOIN kategorie kat ON f.kategorie_id=kat.id WHERE f.id=? AND f.user_id=?", (faktura_id, uid), single=True)
        if not raw_data: return None
        data = dict(raw_data)
        
        polozky_rows = run_query("SELECT * FROM faktura_polozky WHERE faktura_id=?", (faktura_id,))
        polozky = [dict(p) for p in polozky_rows] if polozky_rows else []
        
        moje_row = run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1", (uid,), single=True)
        moje = dict(moje_row) if moje_row else {}
        
        pdf = PDF()
        pdf.add_page()
        
        if use_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)

        # Logo
        if data.get('logo_blob'):
            try:
                fn = f"l_{faktura_id}.png"
                with open(fn, "wb") as f: f.write(data['logo_blob'])
                pdf.image(fn, 10, 10, 50)
                os.remove(fn)
            except: pass 

        cislo_f = data.get('cislo_full') if data.get('cislo_full') else f"{data.get('prefix','')}{data.get('cislo','')}"
        r, g, b = 0, 0, 0
        if is_pro and data.get('barva'):
            try: c = data['barva'].lstrip('#'); r, g, b = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
            except: pass

        pdf.set_text_color(100)
        pdf.set_y(55)
        pdf.cell(95, 5, "DODAVATEL:", 0, 0); pdf.cell(95, 5, "ODBĚRATEL:", 0, 1); pdf.set_text_color(0)
        y = pdf.get_y()
        
        # --- SESTAVENÍ ADRESY DODAVATELE (bez None/prázdných řádků) ---
        dodavatel_lines = [txt(moje.get('nazev',''))]
        if moje.get('adresa'): dodavatel_lines.append(txt(moje['adresa']))
        if moje.get('ico'): dodavatel_lines.append(txt(f"IČ: {moje['ico']}"))
        if moje.get('dic'): dodavatel_lines.append(txt(f"DIČ: {moje['dic']}"))
        if moje.get('email'): dodavatel_lines.append(txt(moje['email']))
        if moje.get('telefon'): dodavatel_lines.append(txt(moje['telefon']))
        dodavatel_text = "\n".join(dodavatel_lines)

        # Dodavatel (tisk)
        if use_font: pdf.set_font('ArialCS', 'B', 11)
        else: pdf.set_font('Arial', 'B', 11)
        pdf.cell(95, 5, txt(moje.get('nazev','')), 0, 1) # První řádek tučně
        
        if use_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)
        # Tisk zbytku adresy
        pdf.multi_cell(95, 5, "\n".join(dodavatel_lines[1:]))
        
        # --- SESTAVENÍ ADRESY ODBĚRATELE ---
        odberatel_lines = [txt(data.get('k_jmeno',''))]
        if data.get('k_adresa'): odberatel_lines.append(txt(data['k_adresa']))
        if data.get('k_ico'): odberatel_lines.append(txt(f"IČ: {data['k_ico']}"))
        if data.get('k_dic'): odberatel_lines.append(txt(f"DIČ: {data['k_dic']}"))
        
        # Odběratel (tisk)
        pdf.set_xy(105, y)
        if use_font: pdf.set_font('ArialCS', 'B', 11)
        else: pdf.set_font('Arial', 'B', 11)
        pdf.cell(95, 5, txt(data.get('k_jmeno')), 0, 1)
        
        pdf.set_xy(105, pdf.get_y())
        if use_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)
        pdf.multi_cell(95, 5, "\n".join(odberatel_lines[1:]))
        
        pdf.ln(10); pdf.set_fill_color(r, g, b); pdf.rect(10, pdf.get_y(), 190, 2, 'F'); pdf.ln(5)
        
        if use_font: pdf.set_font('ArialCS', 'B', 12)
        else: pdf.set_font('Arial', 'B', 12)
        # UPRAVENO: "Faktura č." místo "c."
        pdf.cell(100, 8, txt(f"Faktura č.: {cislo_f}"), 0, 1)
        
        if use_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)
        pdf.cell(50, 6, "Vystaveno:", 0, 0); pdf.cell(50, 6, format_date(data.get('datum_vystaveni')), 0, 1)
        pdf.cell(50, 6, "Splatnost:", 0, 0); pdf.cell(50, 6, format_date(data.get('datum_splatnosti')), 0, 1)
        
        # Zobrazit účet jen pokud existuje
        if moje.get('ucet'):
            pdf.cell(50, 6, "Ucet:", 0, 0); pdf.cell(50, 6, txt(moje.get('ucet')), 0, 1)
        else:
            pdf.ln(6) # Jen odřádkovat pokud není účet
            
        pdf.cell(50, 6, "VS:", 0, 0); pdf.cell(50, 6, txt(data.get('variabilni_symbol')), 0, 1)
        
        # --- ÚVODNÍ TEXT ---
        uvodni_t = data.get('uvodni_text')
        if uvodni_t:
            pdf.ln(8)
            pdf.multi_cell(190, 5, txt(uvodni_t))
        
        # --- TABULKA POLOŽEK ---
        pdf.ln(10)
        pdf.set_fill_color(240, 240, 240) 
        if use_font: pdf.set_font('ArialCS', 'B', 10)
        else: pdf.set_font('Arial', 'B', 10)
        
        pdf.cell(140, 10, txt("POLOŽKY"), 0, 0, 'L', True)
        pdf.cell(50, 10, "CENA", 0, 1, 'R', True)
        
        if use_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)
        
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        
        for p in polozky:
            nazev = p.get('nazev')
            if not nazev or str(nazev).strip() == "":
                continue 
                
            pdf.cell(140, 8, txt(nazev), 0, 0, 'L')
            # UPRAVENO: Formátování ceny s mezerou
            pdf.cell(50, 8, f"{fmt_price(p.get('cena',0))} {txt('Kč')}", 0, 1, 'R')
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            
        pdf.ln(5)
        if use_font: pdf.set_font('ArialCS', 'B', 14)
        else: pdf.set_font('Arial', 'B', 14)
        
        # UPRAVENO: Formátování ceny celkem
        pdf.cell(190, 10, f"CELKEM: {fmt_price(data.get('castka_celkem',0))} {txt('Kč')}", 0, 1, 'R')
        
        if is_pro and moje.get('iban'):
            try:
                ic = str(moje['iban']).replace(" ", "").upper()
                vs_code = str(data.get('variabilni_symbol', ''))
                msg_val = remove_accents(f"Za sluzby faktura {cislo_f}")
                
                qr = f"SPD*1.0*ACC:{ic}*AM:{data.get('castka_celkem')}*CC:CZK*X-VS:{vs_code}*MSG:{msg_val}"
                q = qrcode.make(qr); fn_q = f"q_{faktura_id}.png"; q.save(fn_q)
                
                pdf.image(fn_q, 10, pdf.get_y()+2, 30)
                os.remove(fn_q)
            except: pass
            
        return pdf.output(dest='S').encode('latin-1')
    except Exception as e:
        print(f"PDF ERROR: {e}")
        return f"CHYBA: {str(e)}"

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
                ld = u['license_valid_until']; val_date = datetime.strptime(str(ld)[:10], '%Y-%m-%d').date() if ld else date.today()
                if ld: st.info(f"Licence do: {format_date(ld)}")
                else: st.warning("Bez licence")
                
                fk = run_query("SELECT * FROM licencni_klice WHERE pouzito_uzivatelem_id IS NULL ORDER BY id DESC")
                key_dict = {f"{k['kod']} ({k['dny_platnosti']} dní) - {k['poznamka']}": k for k in fk}
                sel_key_key = st.selectbox("Přiřadit licenci", ["-- Vyberte klíč --"] + list(key_dict.keys()), key=f"sel_{u['id']}")
                
                if st.button("Aktivovat vybranou licenci", key=f"btn_{u['id']}"):
                    if sel_key_key != "-- Vyberte klíč --":
                        k_data = key_dict[sel_key_key]
                        new_exp = date.today() + timedelta(days=k_data['dny_platnosti'])
                        run_command("UPDATE users SET license_key=?, license
