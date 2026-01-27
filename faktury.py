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
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.utils import formataddr
from PIL import Image
from fpdf import FPDF
import qrcode

# --- 0. KONFIGURACE ---
try:
    admin_pass_init = st.secrets["ADMIN_INIT_PASS"]
    email_pass = st.secrets.get("EMAIL_PASSWORD", "")
except Exception:
    admin_pass_init = os.getenv("ADMIN_INIT_PASS")
    email_pass = os.getenv("EMAIL_PASSWORD", "")

if not admin_pass_init:
    st.error("⛔ CHYBA BEZPEČNOSTI: Není nastaveno heslo ADMIN_INIT_PASS v secrets.toml!")
    st.stop()

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

# --- 1. DESIGN (MODERNÍ + FIX PRO MOBILY) ---
st.set_page_config(page_title="Fakturace Pro v5.13", page_icon="💎", layout="centered")

st.markdown("""
    <style>
    /* 1. GLOBÁLNÍ VYNUCENÍ BAREV (Fix pro Safari/Mobile) */
    .stApp { 
        background-color: #0f172a !important; 
        color: #f8fafc !important; 
        font-family: sans-serif; 
    }
    
    /* Vynucení bílého textu pro všechny běžné elementy */
    h1, h2, h3, h4, h5, h6, p, label, span, div, li {
        color: #f8fafc !important;
    }

    /* 2. VSTUPY (Inputs) */
    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #1e293b !important; 
        border: 1px solid #334155 !important; 
        color: #fff !important; 
        border-radius: 12px !important; 
        padding: 12px !important;
    }
    /* Placeholder text */
    ::placeholder { color: #94a3b8 !important; opacity: 1; }

    /* 3. ZÁLOŽKY (Tabs) - Přihlášení/Registrace */
    button[data-baseweb="tab"] {
        background-color: transparent !important;
    }
    button[data-baseweb="tab"] div p {
        color: #94a3b8 !important; /* Neaktivní tab - šedá */
        font-weight: 600;
    }
    button[data-baseweb="tab"][aria-selected="true"] div p {
        color: #fbbf24 !important; /* Aktivní tab - zlatá */
    }
    
    /* 4. SIDEBAR */
    section[data-testid="stSidebar"] { background-color: #0f172a !important; }
    
    /* Tlačítka v menu - STEJNÁ ŠÍŘKA */
    section[data-testid="stSidebar"] .stRadio label {
        background-color: #1e293b !important; 
        padding: 15px !important; 
        margin-bottom: 8px !important;
        border-radius: 10px !important; 
        border: 1px solid #334155 !important;
        font-weight: 600 !important; 
        font-size: 16px !important; 
        display: flex; 
        justify-content: flex-start; 
        cursor: pointer;
        width: 100% !important; 
        box-sizing: border-box !important;
    }
    section[data-testid="stSidebar"] .stRadio label[data-checked="true"] {
        background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%) !important; 
        color: #0f172a !important; 
        border: none !important; 
        font-weight: 800 !important;
    }
    /* Uvnitř aktivního tlačítka v menu musí být text tmavý */
    section[data-testid="stSidebar"] .stRadio label[data-checked="true"] p {
        color: #0f172a !important;
    }

    /* 5. TLAČÍTKA (Buttons) */
    .stButton > button, [data-testid="stDownloadButton"] > button {
        background-color: #334155 !important; 
        color: #ffffff !important; 
        border-radius: 10px !important; 
        height: 50px; 
        font-weight: 600; 
        border: 1px solid #475569 !important; 
        width: 100%;
    }
    .stButton > button:hover, [data-testid="stDownloadButton"] > button:hover { 
        border-color: #fbbf24 !important; 
        color: #fbbf24 !important; 
    }
    div[data-testid="stForm"] button[kind="primary"] { 
        background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%) !important; 
        color: #0f172a !important; 
        border: none !important; 
    }
    /* Text uvnitř primárního tlačítka musí být tmavý */
    div[data-testid="stForm"] button[kind="primary"] p {
        color: #0f172a !important;
    }

    /* 6. STATISTICKÉ BOXY (DASHBOARD) */
    .stat-container { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; justify-content: space-between; }
    .stat-box { 
        background: #1e293b; border-radius: 12px; padding: 15px; flex: 1; 
        min-width: 140px; text-align: center; border: 1px solid #334155; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.2); 
    }
    .mini-stat-box { 
        background: #334155; border-radius: 8px; padding: 10px; flex: 1; 
        min-width: 100px; text-align: center; border: 1px solid #475569; margin-bottom: 5px; 
    }
    
    @media only screen and (max-width: 768px) {
        .stat-box, .mini-stat-box { min-width: 100% !important; margin-bottom: 10px; }
        .stat-container { flex-direction: column; }
    }

    /* Specifické barvy čísel (musí přebít globální nastavení) */
    .text-green, .text-green span { color: #34d399 !important; } 
    .text-red, .text-red span { color: #f87171 !important; } 
    .text-gold, .text-gold span { color: #fbbf24 !important; }
    
    .stat-label { font-size: 11px; text-transform: uppercase; color: #94a3b8 !important; margin-bottom: 5px; font-weight: 700; }
    .stat-value { font-size: 20px; font-weight: 800; color: #fff !important; }
    
    /* 7. OSTATNÍ KOMPONENTY */
    div[data-testid="stExpander"] { 
        background-color: #1e293b !important; 
        border: 1px solid #334155 !important; 
        border-radius: 12px !important; 
    }
    
    /* Login Page Styling */
    .login-header { font-size: 32px; font-weight: 700; color: #f8fafc !important; margin-bottom: 10px; }
    .login-sub { color: #94a3b8 !important; margin-bottom: 30px; }
    .login-container { text-align: center; padding: 20px; }
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
    c.execute('''CREATE TABLE IF NOT EXISTS nastaveni (id INTEGER PRIMARY KEY, user_id INTEGER, nazev TEXT, adresa TEXT, ico TEXT, dic TEXT, ucet TEXT, banka TEXT, email TEXT, telefon TEXT, iban TEXT, smtp_server TEXT, smtp_port INTEGER, smtp_email TEXT, smtp_password TEXT, notify_email TEXT, notify_days INTEGER, notify_active INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS klienti (id INTEGER PRIMARY KEY, user_id INTEGER, jmeno TEXT, adresa TEXT, ico TEXT, dic TEXT, email TEXT, poznamka TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS kategorie (id INTEGER PRIMARY KEY, user_id INTEGER, nazev TEXT, barva TEXT, prefix TEXT, aktualni_cislo INTEGER DEFAULT 1, logo_blob BLOB)''')
    c.execute('''CREATE TABLE IF NOT EXISTS faktury (id INTEGER PRIMARY KEY, user_id INTEGER, cislo INTEGER, cislo_full TEXT, klient_id INTEGER, kategorie_id INTEGER, datum_vystaveni TEXT, datum_duzp TEXT, datum_splatnosti TEXT, castka_celkem REAL, zpusob_uhrady TEXT, variabilni_symbol TEXT, cislo_objednavky TEXT, uvodni_text TEXT, uhrazeno INTEGER DEFAULT 0, muj_popis TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS faktura_polozky (id INTEGER PRIMARY KEY, faktura_id INTEGER, nazev TEXT, cena REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS licencni_klice (id INTEGER PRIMARY KEY, kod TEXT UNIQUE, dny_platnosti INTEGER, vygenerovano TEXT, pouzito_uzivatelem_id INTEGER, poznamka TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS email_templates (id INTEGER PRIMARY KEY, name TEXT UNIQUE, subject TEXT, body TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS vydaje (id INTEGER PRIMARY KEY, user_id INTEGER, datum TEXT, popis TEXT, castka REAL, kategorie TEXT)''')

    try: c.execute("INSERT OR IGNORE INTO email_templates (name, subject, body) VALUES ('welcome', 'Vítejte ve vašem fakturačním systému', 'Dobrý den {name},\n\nVáš účet byl úspěšně vytvořen.\n\nS pozdravem,\nTým MojeFakturace')")
    except: pass
    
    try:
        adm_hash = hashlib.sha256(str.encode(admin_pass_init)).hexdigest()
        c.execute("INSERT OR IGNORE INTO users (username, password_hash, role, full_name, email, phone, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", ("admin", adm_hash, "admin", "Super Admin", "admin@system.cz", "000000000", datetime.now().isoformat()))
        c.execute("UPDATE users SET password_hash=? WHERE username='admin'", (adm_hash,))
    except Exception as e: print(f"Chyba admin sync: {e}")
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
    url = f"https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}"
    headers = {"accept": "application/json", "User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, verify=False, timeout=5)
        if r.status_code == 200:
            data = r.json(); sidlo = data.get('sidlo', {})
            ulice = sidlo.get('nazevUlice', ''); cislo_dom = sidlo.get('cisloDomovni'); cislo_or = sidlo.get('cisloOrientacni'); obec = sidlo.get('nazevObce', ''); psc = sidlo.get('psc', '')
            cislo_txt = str(cislo_dom) if cislo_dom else ""; 
            if cislo_or: cislo_txt += f"/{cislo_or}"
            adr_parts = []
            if ulice: adr_parts.append(f"{ulice} {cislo_txt}".strip())
            elif cislo_txt and obec: adr_parts.append(f"{obec} {cislo_txt}")
            if psc and obec: adr_parts.append(f"{psc} {obec}")
            plna_adresa = ", ".join(adr_parts)
            if not plna_adresa: plna_adresa = sidlo.get('textovaAdresa', '')
            dic = data.get('dic', '')
            if not dic: dic = data.get('dicId', '')
            return {"jmeno": data.get('obchodniJmeno', ''), "adresa": plna_adresa, "ico": ico, "dic": dic}
    except Exception as e: print(f"ARES Error: {e}")
    return None

def process_logo(uploaded_file):
    if not uploaded_file: return None
    try:
        img = Image.open(uploaded_file)
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        b = io.BytesIO(); img.save(b, format='PNG'); return b.getvalue()
    except: return None

def send_email_custom(to, sub, body, attachment=None, filename="zaloha.json"):
    if not SYSTEM_EMAIL["enabled"] or not SYSTEM_EMAIL["password"]: return False
    try:
        msg = MIMEMultipart(); msg['From'] = formataddr((SYSTEM_EMAIL["display_name"], SYSTEM_EMAIL["email"])); msg['To'] = to; msg['Subject'] = sub
        msg.attach(MIMEText(body, 'plain'))
        if attachment:
            part = MIMEApplication(attachment, Name=filename); part['Content-Disposition'] = f'attachment; filename="{filename}"'; msg.attach(part)
        s = smtplib.SMTP_SSL(SYSTEM_EMAIL["server"], SYSTEM_EMAIL["port"]); s.login(SYSTEM_EMAIL["email"], SYSTEM_EMAIL["password"]); s.sendmail(SYSTEM_EMAIL["email"], to, msg.as_string()); s.quit()
        return True
    except: return False

def send_welcome_email_db(to, name):
    tpl = run_query("SELECT subject, body FROM email_templates WHERE name='welcome'", single=True); tpl_dict = dict(tpl) if tpl else {}
    s = tpl_dict.get('subject', "Vítejte"); b = tpl_dict.get('body', f"Dobrý den {name}").replace("{name}", name)
    return send_email_custom(to, s, b)

def get_export_data(user_id):
    export_data = {}
    conn = get_db()
    try:
        for t in ['nastaveni', 'klienti', 'kategorie', 'faktury', 'vydaje']:
            df = pd.read_sql(f"SELECT * FROM {t} WHERE user_id=?", conn, params=(user_id,))
            if 'logo_blob' in df.columns: df['logo_blob'] = df['logo_blob'].apply(lambda x: base64.b64encode(x).decode('utf-8') if x else None)
            export_data[t] = df.to_dict(orient='records')
        df_pol = pd.read_sql("SELECT fp.* FROM faktura_polozky fp JOIN faktury f ON fp.faktura_id=f.id WHERE f.user_id=?", conn, params=(user_id,))
        export_data['faktura_polozky'] = df_pol.to_dict(orient='records')
    except Exception as e: print(f"Export Error: {e}"); return "{}"
    finally: conn.close()
    return json.dumps(export_data, default=str)

# --- ISDOC & PDF ---
def generate_isdoc(faktura_id, uid):
    data = run_query("SELECT f.*, k.jmeno, k.ico, k.adresa, m.nazev as m_nazev, m.ico as m_ico FROM faktury f JOIN klienti k ON f.klient_id=k.id JOIN nastaveni m ON f.user_id=m.user_id WHERE f.id=?", (faktura_id,), True)
    if not data: return None
    d = dict(data)
    root = ET.Element("Invoice", xmlns="http://isdoc.cz/namespace/2013", version="6.0.1")
    ET.SubElement(root, "DocumentType").text = "1"; ET.SubElement(root, "ID").text = str(d.get('cislo_full', d['id']))
    ET.SubElement(root, "IssueDate").text = str(d['datum_vystaveni']); ET.SubElement(root, "TaxPointDate").text = str(d['datum_duzp']); ET.SubElement(root, "LocalCurrencyCode").text = "CZK"
    sp = ET.SubElement(root, "AccountingSupplierParty"); p = ET.SubElement(sp, "Party"); pn = ET.SubElement(p, "PartyName"); ET.SubElement(pn, "Name").text = str(d.get('m_nazev','')); pi = ET.SubElement(p, "PartyIdentification"); ET.SubElement(pi, "ID").text = str(d.get('m_ico',''))
    cp = ET.SubElement(root, "AccountingCustomerParty"); pc = ET.SubElement(cp, "Party"); pnc = ET.SubElement(pc, "PartyName"); ET.SubElement(pnc, "Name").text = str(d.get('jmeno','')); pic = ET.SubElement(pc, "PartyIdentification"); ET.SubElement(pic, "ID").text = str(d.get('ico',''))
    amt = ET.SubElement(root, "LegalMonetaryTotal"); ET.SubElement(amt, "TaxExclusiveAmount").text = str(d['castka_celkem']); ET.SubElement(amt, "TaxInclusiveAmount").text = str(d['castka_celkem']); ET.SubElement(amt, "PayableAmount").text = str(d['castka_celkem'])
    return ET.tostring(root, encoding='utf-8')

def generate_pdf(faktura_id, uid, is_pro):
    use_font = os.path.exists(FONT_FILE)
    def txt(text): return remove_accents(str(text)) if text else ""
    def fmt_price(val): return f"{val:,.2f}".replace(",", " ").replace(".", ",")
    class PDF(FPDF):
        def header(self):
            if use_font:
                try: self.add_font('ArialCS', '', FONT_FILE, uni=True); self.add_font('ArialCS', 'B', FONT_FILE, uni=True); self.set_font('ArialCS', 'B', 24)
                except: self.set_font('Arial', 'B', 24)
            else: self.set_font('Arial', 'B', 24)
            self.set_text_color(50, 50, 50); self.cell(0, 10, 'FAKTURA', 0, 1, 'R'); self.ln(5)
    try:
        raw_data = run_query("SELECT f.*, k.jmeno as k_jmeno, k.adresa as k_adresa, k.ico as k_ico, k.dic as k_dic, kat.barva, kat.logo_blob, kat.prefix FROM faktury f JOIN klienti k ON f.klient_id=k.id JOIN kategorie kat ON f.kategorie_id=kat.id WHERE f.id=? AND f.user_id=?", (faktura_id, uid), single=True)
        if not raw_data: return None
        data = dict(raw_data)
        polozky = [dict(p) for p in run_query("SELECT * FROM faktura_polozky WHERE faktura_id=?", (faktura_id,))]
        moje = dict(run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1", (uid,), single=True) or {})
        pdf = PDF(); pdf.add_page()
        if use_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)
        if data.get('logo_blob'):
            try: fn = f"l_{faktura_id}.png"; open(fn, "wb").write(data['logo_blob']); pdf.image(fn, 10, 10, 50); os.remove(fn)
            except: pass 
        cislo_f = data.get('cislo_full') or f"{data.get('prefix','')}{data.get('cislo','')}"
        r, g, b = 0, 0, 0
        if is_pro and data.get('barva'):
            try: c = data['barva'].lstrip('#'); r, g, b = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
            except: pass
        pdf.set_text_color(100); pdf.set_y(55)
        pdf.cell(95, 5, "DODAVATEL:", 0, 0); pdf.cell(95, 5, "ODBĚRATEL:", 0, 1); pdf.set_text_color(0); y = pdf.get_y()
        if use_font: pdf.set_font('ArialCS', 'B', 11)
        else: pdf.set_font('Arial', 'B', 11)
        pdf.cell(95, 5, txt(moje.get('nazev','')), 0, 1)
        if use_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)
        dod_lines = [txt(moje.get('adresa',''))] if moje.get('adresa') else []
        if moje.get('ico'): dod_lines.append(txt(f"IČ: {moje['ico']}")); 
        if moje.get('dic'): dod_lines.append(txt(f"DIČ: {moje['dic']}")); 
        if moje.get('email'): dod_lines.append(txt(moje['email']))
        pdf.multi_cell(95, 5, "\n".join(dod_lines))
        pdf.set_xy(105, y)
        if use_font: pdf.set_font('ArialCS', 'B', 11)
        else: pdf.set_font('Arial', 'B', 11)
        pdf.cell(95, 5, txt(data.get('k_jmeno')), 0, 1)
        pdf.set_xy(105, pdf.get_y())
        if use_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)
        odb_lines = [txt(data.get('k_adresa',''))] if data.get('k_adresa') else []
        if data.get('k_ico'): odb_lines.append(txt(f"IČ: {data['k_ico']}")); 
        if data.get('k_dic'): odb_lines.append(txt(f"DIČ: {data['k_dic']}"))
        pdf.multi_cell(95, 5, "\n".join(odb_lines))
        pdf.ln(10); pdf.set_fill_color(r, g, b); pdf.rect(10, pdf.get_y(), 190, 2, 'F'); pdf.ln(5)
        if use_font: pdf.set_font('ArialCS', 'B', 12)
        else: pdf.set_font('Arial', 'B', 12)
        pdf.cell(100, 8, txt(f"Faktura č.: {cislo_f}"), 0, 1)
        if use_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)
        pdf.cell(50, 6, "Vystaveno:", 0, 0); pdf.cell(50, 6, format_date(data.get('datum_vystaveni')), 0, 1)
        pdf.cell(50, 6, "Splatnost:", 0, 0); pdf.cell(50, 6, format_date(data.get('datum_splatnosti')), 0, 1)
        if moje.get('ucet'): pdf.cell(50, 6, "Ucet:", 0, 0); pdf.cell(50, 6, txt(moje.get('ucet')), 0, 1)
        else: pdf.ln(6)
        pdf.cell(50, 6, "VS:", 0, 0); pdf.cell(50, 6, txt(data.get('variabilni_symbol')), 0, 1)
        if data.get('uvodni_text'): pdf.ln(8); pdf.multi_cell(190, 5, txt(data['uvodni_text']))
        pdf.ln(10); pdf.set_fill_color(240, 240, 240) 
        if use_font: pdf.set_font('ArialCS', 'B', 10)
        else: pdf.set_font('Arial', 'B', 10)
        pdf.cell(140, 10, txt("POLOŽKY"), 0, 0, 'L', True); pdf.cell(50, 10, "CENA", 0, 1, 'R', True)
        if use_font: pdf.set_font('ArialCS', '', 10)
        else: pdf.set_font('Arial', '', 10)
        pdf.set_draw_color(200, 200, 200); pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        for p in polozky:
            if not p.get('nazev'): continue
            pdf.cell(140, 8, txt(p.get('nazev')), 0, 0, 'L'); pdf.cell(50, 8, f"{fmt_price(p.get('cena',0))} {txt('Kč')}", 0, 1, 'R'); pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        if use_font: pdf.set_font('ArialCS', 'B', 14)
        else: pdf.set_font('Arial', 'B', 14)
        pdf.cell(190, 10, f"CELKEM: {fmt_price(data.get('castka_celkem',0))} {txt('Kč')}", 0, 1, 'R')
        if is_pro and moje.get('iban'):
            try:
                ic = str(moje['iban']).replace(" ", "").upper(); vs = str(data.get('variabilni_symbol', ''))
                qr = f"SPD*1.0*ACC:{ic}*AM:{data.get('castka_celkem')}*CC:CZK*X-VS:{vs}*MSG:{remove_accents('Faktura '+cislo_f)}"
                q = qrcode.make(qr); fn_q = f"q_{faktura_id}.png"; q.save(fn_q)
                pdf.image(fn_q, 10, pdf.get_y()+2, 30); os.remove(fn_q)
            except: pass
        return pdf.output(dest='S').encode('latin-1')
    except Exception as e: return f"CHYBA: {str(e)}"

# --- 7. SESSION ---
if 'user_id' not in st.session_state: st.session_state.user_id = None
if 'role' not in st.session_state: st.session_state.role = 'user'
if 'is_pro' not in st.session_state: st.session_state.is_pro = False
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
        st.markdown("""<div class="login-container"><div style="font-size: 50px; margin-bottom: 10px;">💎</div><div class="login-header">Fakturace Pro</div><div class="login-sub">Mobilní fakturace nové generace.</div></div>""", unsafe_allow_html=True)
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
                    try: run_command("INSERT INTO users (username,password_hash,full_name,email,phone,created_at,force_password_change) VALUES (?,?,?,?,?,?,0)",(u,hash_password(p),f,e,t_tel,datetime.now().isoformat())); send_welcome_email_db(e, f); st.success("Hotovo! Přihlašte se.")
                    except: st.error("Login obsazen.")
        with t3:
            with st.form("forgot"):
                fe = st.text_input("Váš Email"); 
                if st.form_submit_button("Resetovat heslo", use_container_width=True):
                    usr = run_query("SELECT * FROM users WHERE email=?", (fe,), single=True)
                    if usr:
                        new_pass = generate_random_password()
                        run_command("UPDATE users SET password_hash=?, force_password_change=1 WHERE id=?", (hash_password(new_pass), usr['id']))
                        send_email_custom(fe, "Reset hesla", f"Nové heslo: {new_pass}"); st.success("Heslo odesláno.")
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
                run_command("UPDATE users SET password_hash=?, force_password_change=0 WHERE id=?", (hash_password(np1), uid)); st.session_state.force_pw_change = 0; st.success("Heslo změněno!"); st.rerun()
            else: st.error("Hesla se neshodují.")
    st.stop()

badge = "⭐ PRO" if is_pro else "🆓 FREE"
st.sidebar.markdown(f"""<div class='sidebar-header'><div class='sidebar-user'>{full_name_display}</div><div class='sidebar-role'>{st.session_state.username} | <span class='{ "badge-pro" if is_pro else "badge-free" }'>{badge}</span></div></div>""", unsafe_allow_html=True)
if st.sidebar.button("Odhlásit"): st.session_state.user_id=None; st.rerun()

# ADMIN
if role == 'admin':
    st.header("👑 Admin Dashboard")
    # Statistiky (nepočítat admina)
    u_count = run_query("SELECT COUNT(*) FROM users WHERE role!='admin'", single=True)[0] or 0
    f_count = run_query("SELECT COUNT(*) FROM faktury", single=True)[0] or 0
    t_rev = run_query("SELECT SUM(castka_celkem) FROM faktury", single=True)[0] or 0
    
    avg_u = t_rev / u_count if u_count > 0 else 0
    avg_f = t_rev / f_count if f_count > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Počet uživatelů", u_count)
    c2.metric("Celkový obrat", f"{t_rev:,.0f} Kč")
    c3.metric("Obrat / Uživatel", f"{avg_u:,.0f} Kč")
    c4.metric("Průměrná faktura", f"{avg_f:,.0f} Kč")
    
    st.divider()
    
    tabs = st.tabs(["Uživatelé & Licence", "Generátor klíčů", "📧 E-mailing"])
    
    with tabs[0]:
        st.subheader("📋 Seznam uživatelů")
        # Výpis pro přehled
        for u in run_query("SELECT * FROM users WHERE role!='admin' ORDER BY id DESC"):
            # Určení statusu
            exp_date = u['license_valid_until']
            is_active_lic = False
            if exp_date:
                try: 
                    dobj = datetime.strptime(str(exp_date)[:10], '%Y-%m-%d').date()
                    if dobj >= date.today(): is_active_lic = True
                except: pass
            
            # --- OPRAVA CHYBY S HTML V EXPANDERU (Použití Emoji místo HTML) ---
            status_badge = "⭐ PRO" if is_active_lic else "🆓 FREE"
            
            with st.expander(f"{u['username']} ({u['email']}) | {status_badge}"):
                c1, c2 = st.columns(2)
                c1.write(f"**Jméno:** {u['full_name']}")
                c1.write(f"**Tel:** {u['phone']}")
                c1.write(f"**Vytvořeno:** {format_date(u['created_at'])}")
                
                # Editace platnosti
                current_valid = date.today()
                if u['license_valid_until']:
                    try: current_valid = datetime.strptime(str(u['license_valid_until'])[:10], '%Y-%m-%d').date()
                    except: pass
                
                new_valid = c2.date_input("Manuálně nastavit platnost do:", value=current_valid, key=f"md_{u['id']}")
                if c2.button("💾 Uložit datum", key=f"bd_{u['id']}"):
                    run_command("UPDATE users SET license_valid_until=? WHERE id=?", (new_valid, u['id']))
                    st.success("Datum aktualizováno"); st.rerun()

                # Licence logic
                fk = run_query("SELECT * FROM licencni_klice WHERE pouzito_uzivatelem_id IS NULL ORDER BY id DESC")
                key_dict = {f"{k['kod']} ({k['dny_platnosti']} dní)": k for k in fk}
                sel_key = c2.selectbox("Nebo přiřadit klíč", ["-- Vyberte --"] + list(key_dict.keys()), key=f"sk_{u['id']}")
                
                if c2.button("Aktivovat klíčem", key=f"btn_{u['id']}"):
                    if sel_key != "-- Vyberte --":
                        k_data = key_dict[sel_key]
                        new_exp = date.today() + timedelta(days=k_data['dny_platnosti'])
                        run_command("UPDATE users SET license_key=?, license_valid_until=? WHERE id=?", (k_data['kod'], new_exp, u['id']))
                        run_command("UPDATE licencni_klice SET pouzito_uzivatelem_id=? WHERE id=?", (u['id'], k_data['id']))
                        st.success("Licence aktivována!"); st.rerun()
                
                if st.button("🗑️ Smazat uživatele", key=f"del_{u['id']}", type="primary"):
                    run_command("DELETE FROM users WHERE id=?",(u['id'],)); st.rerun()

    with tabs[1]:
        days_val = st.number_input("Platnost (dny)", value=365, min_value=1); note_val = st.text_input("Poznámka (např. jméno firmy)")
        if st.button("Vygenerovat nový klíč"):
            k = generate_license_key()
            run_command("INSERT INTO licencni_klice (kod, dny_platnosti, vygenerovano, poznamka) VALUES (?,?,?,?)", (k, days_val, datetime.now().isoformat(), note_val)); st.success(f"Vytvořeno: {k}")
        for k in run_query("SELECT * FROM licencni_klice ORDER BY id DESC"): st.code(f"{k['kod']} | {k['dny_platnosti']} dní | {'🔴 Použit' if k['pouzito_uzivatelem_id'] else '🟢 Volný'} | {k['poznamka']}")

    with tabs[2]:
        st.subheader("Šablona uvítacího emailu")
        tpl = run_query("SELECT * FROM email_templates WHERE name='welcome'", single=True); tpl_dict = dict(tpl) if tpl else {}
        with st.form("wm"):
            ws = st.text_input("Předmět", value=tpl_dict.get('subject', '')); wb = st.text_area("Text (použijte {name} pro jméno)", value=tpl_dict.get('body', ''), height=200)
            if st.form_submit_button("Uložit šablonu"): 
                run_command("INSERT OR REPLACE INTO email_templates (id, name, subject, body) VALUES ((SELECT id FROM email_templates WHERE name='welcome'), 'welcome', ?, ?)", (ws, wb)); st.success("OK")
        
        st.divider()
        st.subheader("Hromadné odeslání zprávy")
        with st.form("mm"):
            ms = st.text_input("Předmět"); mb = st.text_area("Zpráva pro všechny uživatele", height=150)
            if st.form_submit_button("Odeslat všem uživatelům"):
                count = 0
                for u in run_query("SELECT email FROM users WHERE role!='admin' AND email IS NOT NULL"): 
                    if send_email_custom(u['email'], ms, mb): count += 1
                st.success(f"Odesláno na {count} emailů.")

# USER
else:
    menu = st.sidebar.radio(" ", ["📊 Faktury", "🏛️ Daně", "💸 Výdaje", "👥 Klienti", "🏷️ Kategorie", "⚙️ Nastavení"])
    
    if "Faktury" in menu:
        t1, t2 = st.tabs(["Přehled & Seznam", "📈 Dashboard"])
        with t1:
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
                        ut = st.text_input("Úvodní text", "Fakturujeme Vám:", key=f"ut_{rid}")
                        ed = st.data_editor(st.session_state.items_df, num_rows="dynamic", use_container_width=True, key=f"e_{rid}")
                        total_sum = float(pd.to_numeric(ed["Cena"], errors='coerce').fillna(0).sum()) if not ed.empty and "Cena" in ed.columns else 0.0
                        st.markdown(f"**💰 Celkem k úhradě: {total_sum:,.2f} Kč**")
                        if st.button("Vystavit", type="primary", key=f"b_{rid}"):
                            fid = run_command("INSERT INTO faktury (user_id, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_splatnosti, castka_celkem, variabilni_symbol, uvodni_text) VALUES (?,?,?,?,?,?,?,?,?)", (uid, full, kid, cid, dv, ds, total_sum, re.sub(r"\D", "", full), ut))
                            for _, r in ed.iterrows(): 
                                if r.get("Popis položky"): run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (fid, r["Popis položky"], float(r.get("Cena", 0))))
                            run_command("UPDATE kategorie SET aktualni_cislo = aktualni_cislo + 1 WHERE id = ?", (cid,)); reset_forms(); st.success("OK"); st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)
            sel_cli = st.selectbox("Filtr Klient", ["Všichni"] + [c['jmeno'] for c in run_query("SELECT jmeno FROM klienti WHERE user_id=?", (uid,))])
            db_years = [y[0] for y in run_query("SELECT DISTINCT strftime('%Y', datum_vystaveni) FROM faktury WHERE user_id=?", (uid,))]
            sel_yf = st.selectbox("Filtr Rok", ["Všechny"] + sorted(db_years, reverse=True))

            if sel_cli != "Všichni":
                cl_all = run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=?", (uid, sel_cli), True)[0] or 0
                cl_due = run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=? AND f.uhrazeno=0", (uid, sel_cli), True)[0] or 0
                cols = st.columns(3)
                cols[0].markdown(f"<div class='mini-stat-box'><div class='stat-label'>CELKEM (HISTORIE)</div><div class='mini-value'>{cl_all:,.0f} Kč</div></div>", unsafe_allow_html=True)
                if sel_yf != "Všechny":
                    cl_yr = run_query("SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? AND k.jmeno=? AND strftime('%Y', f.datum_vystaveni)=?", (uid, sel_cli, sel_yf), True)[0] or 0
                    cols[1].markdown(f"<div class='mini-stat-box'><div class='stat-label'>OBRAT {sel_yf}</div><div class='mini-value text-green'>{cl_yr:,.0f} Kč</div></div>", unsafe_allow_html=True)
                cols[2].markdown(f"<div class='mini-stat-box'><div class='stat-label'>DLUŽÍ</div><div class='mini-value text-red'>{cl_due:,.0f} Kč</div></div>", unsafe_allow_html=True)

            q = "SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=?"; p = [uid]
            if sel_cli != "Všichni": q += " AND k.jmeno=?"; p.append(sel_cli)
            if sel_yf != "Všechny": q += " AND strftime('%Y', f.datum_vystaveni)=?"; p.append(sel_yf)
            
            df_faktury = pd.read_sql(q + " ORDER BY f.id DESC LIMIT 50", get_db(), params=p)
            for row in df_faktury.to_dict('records'):
                cf = row.get('cislo_full') or f"F{row['id']}"
                with st.expander(f"{'✅' if row['uhrazeno'] else '⏳'} {cf} | {row['jmeno']} | {row['castka_celkem']:.0f} Kč"):
                    c1,c2,c3 = st.columns([1,1,1])
                    if row['uhrazeno']: 
                        if c1.button("Zrušit úhradu", key=f"u0_{row['id']}"): run_command("UPDATE faktury SET uhrazeno=0 WHERE id=?",(row['id'],)); st.rerun()
                    else: 
                        if c1.button("Zaplaceno", key=f"u1_{row['id']}"): run_command("UPDATE faktury SET uhrazeno=1 WHERE id=?",(row['id'],)); st.rerun()
                    
                    pdf_output = generate_pdf(row['id'], uid, is_pro)
                    if isinstance(pdf_output, bytes): c2.download_button("PDF", pdf_output, f"{cf}.pdf", "application/pdf", key=f"pd_{row['id']}")
                    
                    if is_pro:
                        isdoc_bytes = generate_isdoc(row['id'], uid)
                        if isdoc_bytes: c2.download_button("ISDOC", isdoc_bytes, f"{cf}.isdoc", "application/xml", key=f"isd_{row['id']}")

                    f_edit_key = f"edit_f_{row['id']}"
                    if f_edit_key not in st.session_state: st.session_state[f_edit_key] = False
                    if c3.button("✏️ Upravit", key=f"be_{row['id']}"): st.session_state[f_edit_key] = True; st.rerun()
                    
                    if st.session_state[f_edit_key]:
                        with st.form(f"fe_{row['id']}"):
                            nd = st.date_input("Splatnost", pd.to_datetime(row['datum_splatnosti']))
                            nm = st.text_input("Popis", row['muj_popis'] or ""); nut = st.text_input("Úvodní text", row['uvodni_text'] or "")
                            cur_i = pd.read_sql("SELECT nazev as 'Popis položky', cena as 'Cena' FROM faktura_polozky WHERE faktura_id=?", get_db(), params=(row['id'],))
                            ned = st.data_editor(cur_i, num_rows="dynamic", use_container_width=True)
                            if st.form_submit_button("Uložit změny"):
                                ntot = float(pd.to_numeric(ned["Cena"], errors='coerce').fillna(0).sum())
                                run_command("UPDATE faktury SET datum_splatnosti=?, muj_popis=?, castka_celkem=?, uvodni_text=? WHERE id=?", (nd, nm, ntot, nut, row['id']))
                                run_command("DELETE FROM faktura_polozky WHERE faktura_id=?", (row['id'],))
                                for _, rw in ned.iterrows():
                                    if rw.get("Popis položky"): run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (row['id'], rw["Popis položky"], float(rw.get("Cena", 0))))
                                st.session_state[f_edit_key] = False; st.rerun()

                    if c3.button("🔄 Duplikovat", key=f"dup_{row['id']}"):
                        new_num, new_full, _ = get_next_invoice_number(row['kategorie_id'], uid)
                        new_fid = run_command("""INSERT INTO faktury (user_id, cislo, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_splatnosti, castka_celkem, variabilni_symbol, uvodni_text, muj_popis) VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (uid, new_num, new_full, row['klient_id'], row['kategorie_id'], date.today(), date.today()+timedelta(14), row['castka_celkem'], re.sub(r"\D", "", new_full), row['uvodni_text'], row['muj_popis']))
                        items = run_query("SELECT * FROM faktura_polozky WHERE faktura_id=?", (row['id'],))
                        for it in items: run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (new_fid, it['nazev'], it['cena']))
                        run_command("UPDATE kategorie SET aktualni_cislo = aktualni_cislo + 1 WHERE id = ?", (row['kategorie_id'],))
                        st.success(f"Faktura {new_full} vytvořena!"); st.rerun()

                    if st.button("Smazat", key=f"bd_{row['id']}"): run_command("DELETE FROM faktury WHERE id=?",(row['id'],)); st.rerun()
        
        with t2:
            st.markdown("### 🚀 Přehled podnikání")
            tot_rev = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?", (uid,), True)[0] or 0
            tot_paid = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=1", (uid,), True)[0] or 0
            tot_due = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0", (uid,), True)[0] or 0
            count_inv = run_query("SELECT COUNT(*) FROM faktury WHERE user_id=?", (uid,), True)[0] or 0
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("Celkem vystaveno", f"{tot_rev:,.0f} Kč"); mc2.metric("Zaplaceno", f"{tot_paid:,.0f} Kč", delta=f"{int(tot_paid/tot_rev*100) if tot_rev else 0} %"); mc3.metric("Dluží klienti", f"{tot_due:,.0f} Kč", delta="-", delta_color="inverse"); mc4.metric("Počet faktur", count_inv)
            st.divider()
            gc1, gc2 = st.columns([2, 1])
            with gc1:
                st.subheader("📈 Vývoj v čase")
                df_g = pd.read_sql("SELECT datum_vystaveni, castka_celkem FROM faktury WHERE user_id=?", get_db(), params=(uid,))
                if not df_g.empty:
                    df_g['datum'] = pd.to_datetime(df_g['datum_vystaveni'])
                    monthly = df_g.groupby(df_g['datum'].dt.to_period('M'))['castka_celkem'].sum()
                    monthly.index = monthly.index.astype(str)
                    st.bar_chart(monthly, color="#fbbf24")
                else: st.info("Zatím žádná data.")
            with gc2:
                st.subheader("🏆 TOP 5 Klientů")
                df_top = pd.read_sql("SELECT k.jmeno, SUM(f.castka_celkem) as celkem FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=? GROUP BY k.jmeno ORDER BY celkem DESC LIMIT 5", get_db(), params=(uid,))
                if not df_top.empty: st.dataframe(df_top.set_index('jmeno').style.format("{:,.0f} Kč"), use_container_width=True)
                else: st.info("Žádní klienti.")
            st.subheader("🍰 Příjmy dle kategorií")
            df_c = pd.read_sql("SELECT k.nazev, SUM(f.castka_celkem) as celkem FROM faktury f JOIN kategorie k ON f.kategorie_id=k.id WHERE f.user_id=? GROUP BY k.nazev", get_db(), params=(uid,))
            if not df_c.empty: st.bar_chart(df_c.set_index('nazev'))

    elif "🏛️ Daně" in menu:
        st.header("🏛️ Daňová kalkulačka (Orientační)")
        
        # 1. Výběr roku
        years = [r[0] for r in run_query("SELECT DISTINCT strftime('%Y', datum_vystaveni) FROM faktury WHERE user_id=?", (uid,))]
        current_year = str(date.today().year)
        if current_year not in years: years.append(current_year)
        
        c_year, c_pausal = st.columns(2)
        sel_tax_year = c_year.selectbox("Vyberte rok", sorted(list(set(years)), reverse=True))
        
        # --- VÝBĚR PAUŠÁLU ---
        pausal_opt = c_pausal.selectbox("Typ činnosti (Paušální výdaje)", [
            "80% - Řemeslné živnosti, zemědělství",
            "60% - Ostatní živnosti (nejčastější)",
            "40% - Svobodná povolání, autorská práva",
            "30% - Pronájem majetku"
        ], index=1)
        pausal_pct = int(pausal_opt.split("%")[0]) / 100
        
        # 2. Načtení dat
        income = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND strftime('%Y', datum_vystaveni)=?", (uid, sel_tax_year), True)[0] or 0
        real_expenses = run_query("SELECT SUM(castka) FROM vydaje WHERE user_id=? AND strftime('%Y', datum)=?", (uid, sel_tax_year), True)[0] or 0
        
        # 3. Výpočty
        flat_expenses = income * pausal_pct
        
        tax_base_real = max(0, income - real_expenses)
        tax_base_flat = max(0, income - flat_expenses)
        
        tax_real = tax_base_real * 0.15
        tax_flat = tax_base_flat * 0.15
        
        diff = tax_flat - tax_real
        
        # 4. Zobrazení
        st.markdown(f"### 💰 Příjmy za rok {sel_tax_year}: **{income:,.0f} Kč**")
        
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("<div class='stat-box'><h4>A) SKUTEČNÉ VÝDAJE</h4>", unsafe_allow_html=True)
            st.write(f"Výdaje: {real_expenses:,.0f} Kč")
            st.write(f"Základ daně: {tax_base_real:,.0f} Kč")
            st.markdown(f"<h2 style='color:#fbbf24'>{tax_real:,.0f} Kč</h2>", unsafe_allow_html=True)
            st.write("Daň (15%)")
            st.markdown("</div>", unsafe_allow_html=True)
            
        with c2:
            st.markdown(f"<div class='stat-box'><h4>B) PAUŠÁL {int(pausal_pct*100)}%</h4>", unsafe_allow_html=True)
            st.write(f"Výdaje: {flat_expenses:,.0f} Kč")
            st.write(f"Základ daně: {tax_base_flat:,.0f} Kč")
            st.markdown(f"<h2 style='color:#fbbf24'>{tax_flat:,.0f} Kč</h2>", unsafe_allow_html=True)
            st.write("Daň (15%)")
            st.markdown("</div>", unsafe_allow_html=True)
            
        st.divider()
        
        # 5. Vyhodnocení
        if tax_real < tax_flat:
            st.success(f"🏆 VÝHODNĚJŠÍ JSOU SKUTEČNÉ VÝDAJE! Ušetříte {diff:,.0f} Kč.")
        elif tax_flat < tax_real:
            st.success(f"🏆 VÝHODNĚJŠÍ JE PAUŠÁL! Ušetříte {abs(diff):,.0f} Kč.")
        else:
            st.info("Obě varianty vychází stejně.")

    elif "Výdaje" in menu:
        st.header("💸 Evidence výdajů")
        with st.form("exp_form"):
            c1, c2 = st.columns(2)
            ex_date = c1.date_input("Datum", date.today()); ex_desc = c2.text_input("Popis (např. Nájem)")
            c3, c4 = st.columns(2)
            ex_amt = c3.number_input("Částka", min_value=0.0, step=100.0); ex_cat = c4.selectbox("Kategorie", ["Provoz", "Materiál", "Služby", "Ostatní"])
            if st.form_submit_button("Uložit výdaj"):
                run_command("INSERT INTO vydaje (user_id, datum, popis, castka, kategorie) VALUES (?,?,?,?,?)", (uid, ex_date, ex_desc, ex_amt, ex_cat))
                st.success("Uloženo"); st.rerun()
        vydaje = pd.read_sql("SELECT * FROM vydaje WHERE user_id=? ORDER BY datum DESC", get_db(), params=(uid,))
        if not vydaje.empty:
            st.dataframe(vydaje[['id', 'datum', 'popis', 'kategorie', 'castka']], hide_index=True, use_container_width=True)
            celkem_vydaje = vydaje['castka'].sum()
            celkem_prijmy = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?", (uid,), True)[0] or 0
            c1, c2, c3 = st.columns(3)
            c1.metric("Příjmy", f"{celkem_prijmy:,.0f} Kč"); c2.metric("Výdaje", f"{celkem_vydaje:,.0f} Kč", delta=-celkem_vydaje); c3.metric("Hrubý zisk", f"{celkem_prijmy - celkem_vydaje:,.0f} Kč")
            
            vydaj_list = vydaje.apply(lambda x: f"ID {x['id']}: {x['datum']} - {x['popis']} ({x['castka']} Kč)", axis=1).tolist()
            if vydaj_list:
                sel_del = st.selectbox("Vyberte výdaj ke smazání", vydaj_list)
                if st.button("Smazat označený výdaj"):
                    del_id = int(sel_del.split(":")[0].replace("ID ", ""))
                    run_command("DELETE FROM vydaje WHERE id=? AND user_id=?", (del_id, uid))
                    st.rerun()

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
                k_edit_key = f"edit_k_{k['id']}"
                if k_edit_key not in st.session_state: st.session_state[k_edit_key] = False
                c1,c2 = st.columns(2)
                if c1.button("✏️ Upravit", key=f"bek_{k['id']}"): st.session_state[k_edit_key] = True; st.rerun()
                if c2.button("Smazat", key=f"bdk_{k['id']}"): run_command("DELETE FROM klienti WHERE id=?",(k['id'],)); st.rerun()
                if st.session_state[k_edit_key]:
                    with st.form(f"fke_{k['id']}"):
                        nj=st.text_input("Jméno", k['jmeno']); na=st.text_area("Adresa", k['adresa'])
                        ni=st.text_input("IČ", k['ico']); nd=st.text_input("DIČ", k['dic']); np=st.text_area("Poznámka", k['poznamka'])
                        if st.form_submit_button("Uložit změny"):
                            run_command("UPDATE klienti SET jmeno=?, adresa=?, ico=?, dic=?, poznamka=? WHERE id=?", (nj,na,ni,nd,np,k['id']))
                            st.session_state[k_edit_key] = False; st.rerun()

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
                if k['logo_blob']: st.image(k['logo_blob'], width=100)
                cat_edit_key = f"edit_cat_{k['id']}"
                if cat_edit_key not in st.session_state: st.session_state[cat_edit_key] = False
                c1,c2 = st.columns(2)
                if is_pro:
                    if c1.button("✏️ Upravit", key=f"bec_{k['id']}"): st.session_state[cat_edit_key] = True; st.rerun()
                if c2.button("Smazat", key=f"bdc_{k['id']}"): run_command("DELETE FROM kategorie WHERE id=?", (k['id'],)); st.rerun()
                
                if st.session_state[cat_edit_key]:
                    with st.form(f"feck_{k['id']}"):
                        nn=st.text_input("Název", k['nazev']); np=st.text_input("Prefix", k['prefix'])
                        ns=st.number_input("Číslo", value=k['aktualni_cislo']); nc=st.color_picker("Barva", k['barva'])
                        nl = st.file_uploader("Nové logo (pokud chcete změnit)", key=f"ul_{k['id']}")
                        if st.form_submit_button("Uložit změny"):
                            if nl:
                                blob = process_logo(nl)
                                run_command("UPDATE kategorie SET nazev=?, prefix=?, aktualni_cislo=?, barva=?, logo_blob=? WHERE id=?", (nn,np,ns,nc,blob,k['id']))
                            else:
                                run_command("UPDATE kategorie SET nazev=?, prefix=?, aktualni_cislo=?, barva=? WHERE id=?", (nn,np,ns,nc,k['id']))
                            st.session_state[cat_edit_key] = False; st.rerun()

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
                st.markdown("### 📧 Nastavení automatického odesílání")
                st.info("💡 **Návod:**\n- **Seznam.cz:** Použijte své heslo. Pokud máte 2FA, použijte heslo aplikace.\n- **Gmail:** Musíte vygenerovat **Heslo aplikace** (App Password) v nastavení Google účtu.\n- **Vlastní:** Zadejte údaje dle vašeho hostingu.")
                
                act = st.toggle("Aktivovat odesílání", value=bool(c.get('notify_active', 0)))
                col_a, col_b = st.columns(2)
                n_days = col_a.number_input("Kolik dní před splatností?", value=c.get('notify_days', 3), min_value=1)
                n_email = col_b.text_input("Váš Email (pro notifikace)", value=c.get('notify_email', ''))

                st.divider()
                st.markdown("### ⚙️ SMTP Server")
                
                preset = st.selectbox("Rychlé nastavení", ["-- Vyberte --", "Seznam.cz", "Gmail", "Vlastní"])
                d_srv = c.get('smtp_server', 'smtp.seznam.cz'); d_prt = c.get('smtp_port', 465)
                if preset == "Seznam.cz": d_srv = "smtp.seznam.cz"; d_prt = 465
                elif preset == "Gmail": d_srv = "smtp.gmail.com"; d_prt = 465
                
                s_server = st.text_input("SMTP Server", value=d_srv)
                c3, c4 = st.columns(2)
                s_port = c3.number_input("Port (SSL)", value=d_prt)
                s_user = c4.text_input("Login (Email)", value=c.get('smtp_email', ''))
                s_pass = st.text_input("Heslo", value=c.get('smtp_password', ''), type="password")

                c5, c6 = st.columns(2)
                if c5.button("💾 Uložit nastavení"):
                    run_command("UPDATE nastaveni SET notify_active=?, notify_days=?, notify_email=?, smtp_server=?, smtp_port=?, smtp_email=?, smtp_password=? WHERE id=?", (int(act), n_days, n_email, s_server, s_port, s_user, s_pass, c.get('id')))
                    st.success("Nastavení uloženo.")
                if c6.button("📨 Odeslat test"):
                    if not s_server or not s_user or not s_pass: st.error("Vyplňte server, email a heslo.")
                    else:
                        try:
                            msg = MIMEMultipart(); msg['From'] = formataddr(("Test Fakturace", s_user)); msg['To'] = n_email; msg['Subject'] = "Testovací email"; msg.attach(MIMEText("Test", 'plain'))
                            server = smtplib.SMTP_SSL(s_server, int(s_port)); server.login(s_user, s_pass); server.sendmail(s_user, n_email, msg.as_string()); server.quit()
                            st.success(f"✅ Email odeslán na {n_email}")
                        except Exception as e: st.error(f"❌ Chyba: {e}")

        if is_pro:
            with st.expander("📦 Export pro účetní (ISDOC ZIP)"):
                st.markdown("Vygeneruje ZIP archiv se všemi fakturami ve formátu ISDOC za vybrané období.")
                c1, c2 = st.columns(2)
                today = date.today(); first_day = today.replace(day=1)
                d_start = c1.date_input("Od", first_day); d_end = c2.date_input("Do", today)

                if st.button("Stáhnout balíček pro účetní"):
                    invoices = run_query("SELECT id, cislo_full FROM faktury WHERE datum_vystaveni BETWEEN ? AND ? AND user_id=?", (d_start, d_end, uid))
                    if not invoices: st.warning("V tomto období nebyly nalezeny žádné faktury.")
                    else:
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            count = 0
                            for inv in invoices:
                                isdoc_bytes = generate_isdoc(inv['id'], uid)
                                if isdoc_bytes:
                                    zip_file.writestr(f"{inv['cislo_full']}.isdoc", isdoc_bytes); count += 1
                        if count > 0:
                            st.success(f"Zpracováno {count} faktur.")
                            st.download_button("📥 Stáhnout ZIP (ISDOC)", zip_buffer.getvalue(), f"export_isdoc_{d_start}_{d_end}.zip", "application/zip")
                        else: st.error("Chyba generování.")

            with st.expander("💾 Zálohování a Cloud (PRO)"):
                st.download_button("Export dat", get_export_data(uid), "zaloha.json", "application/json")
                
                st.divider()
                st.markdown("### ☁️ Odeslat zálohu na Cloud (Email)")
                st.info("Odešle aktuální zálohu dat na váš email. Vyžaduje funkční SMTP nastavení výše.")
                if st.button("📤 Odeslat zálohu na Můj Email"):
                    if not c.get('smtp_server'): st.error("Nejprve nastavte SMTP v sekci Upozornění!")
                    else:
                        json_data = get_export_data(uid)
                        if send_email_custom(c.get('notify_email'), f"Záloha Fakturace {date.today()}", "V příloze je vaše záloha.", json_data, f"zaloha_{date.today()}.json"): st.success("Záloha odeslána!")
                        else: st.error("Chyba při odesílání.")

                st.divider()
                upl = st.file_uploader("Import dat", type="json")
                if upl and st.button("Obnovit / Sloučit"):
                    try:
                        d = json.load(upl); client_map = {}; cat_map = {}
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
                            cid = client_map.get(r.get('klient_id')); kid = cat_map.get(r.get('kategorie_id'))
                            if cid and kid:
                                exist_f = run_query("SELECT id FROM faktury WHERE cislo_full=? AND user_id=?", (r.get('cislo_full'), uid), True)
                                if not exist_f:
                                    new_fid = run_command("INSERT INTO faktury (user_id, cislo, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_duzp, datum_splatnosti, castka_celkem, zpusob_uhrady, variabilni_symbol, cislo_objednavky, uvodni_text, uhrazeno, muj_popis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (uid, r.get('cislo'), r.get('cislo_full'), cid, kid, r.get('datum_vystaveni'), r.get('datum_duzp'), r.get('datum_splatnosti'), r.get('castka_celkem'), r.get('zpusob_uhrady'), r.get('variabilni_symbol'), r.get('cislo_objednavky'), r.get('uvodni_text'), r.get('uhrazeno'), r.get('muj_popis')))
                                    for item in d.get('faktura_polozky', []):
                                        if item.get('faktura_id') == r.get('id'): run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (new_fid, item.get('nazev'), item.get('cena')))
                        st.success("Hotovo! Data byla sloučena."); st.rerun()
                    except Exception as e: st.error(f"Chyba: {e}")
        else:
            with st.expander("💾 Zálohování"): st.info("Zálohování dostupné v PRO verzi.")
