import sys
import streamlit as st
import sqlite3
import os
import json
import re
from datetime import datetime, date, timedelta
import unicodedata
import io
import base64

# --- 1. KONFIGURACE A CSS (TMAVÝ REŽIM) ---
st.set_page_config(page_title="Fakturační Systém", page_icon="🧾", layout="centered")

# CSS PRO TMAVÝ VZHLED
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #262730 !important; 
        border: 1px solid #4f4f4f !important;
        color: #ffffff !important;
    }
    div[data-testid="stExpander"] {
        background-color: #262730 !important;
        border: 1px solid #4f4f4f;
        border-radius: 8px;
        margin-bottom: 8px;
    }
    div[data-testid="stExpander"] details summary { color: #ffffff !important; }
    
    /* STATS */
    .mini-stat-container { display: flex; gap: 10px; margin-bottom: 20px; justify-content: space-between; }
    .mini-stat-box { background-color: #111827; border: 1px solid #374151; border-radius: 8px; padding: 10px; text-align: center; width: 100%; }
    .mini-label { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #9ca3af; margin-bottom: 4px; }
    .mini-val-green { font-size: 18px; font-weight: 700; color: #6ee7b7; }
    .mini-val-gray { font-size: 18px; font-weight: 700; color: #d1d5db; }
    .mini-val-red { font-size: 18px; font-weight: 700; color: #f87171; }
    .stat-box { background-color: #1f2937; padding: 15px; border-radius: 12px; text-align: center; border: 1px solid #374151; height: 100%; min-height: 120px; display: flex; flex-direction: column; justify-content: center; }
    .stat-num { font-size: 28px; font-weight: 800; color: #4ade80; margin: 0; }
    .stat-err { font-size: 28px; font-weight: 800; color: #f87171; margin: 0; }
    
    /* USER LABEL */
    .user-label { background-color: #1f2937; padding: 10px; border-radius: 8px; margin-bottom: 20px; text-align: center; border: 1px solid #374151; }
    </style>
""", unsafe_allow_html=True)

# --- 2. INICIALIZACE STAVU ---
if 'form_reset_id' not in st.session_state: st.session_state.form_reset_id = 0
if 'ares_data' not in st.session_state: st.session_state.ares_data = {"jmeno": "", "adresa": "", "ico": "", "dic": ""}
# Items_df inicializujeme později kvůli rychlosti
if 'db_inited' not in st.session_state: st.session_state.db_inited = False

def reset_forms():
    st.session_state.form_reset_id += 1
    st.session_state.ares_data = {"jmeno": "", "adresa": "", "ico": "", "dic": ""}
    if 'items_df' in st.session_state:
        import pandas as pd
        st.session_state.items_df = pd.DataFrame(columns=["Popis položky", "Cena"])

# --- 3. DATABÁZE A CESTY (WEB VERZE) ---
# Na webu nemůžeme používat složku Dokumenty uživatele, použijeme aktuální složku repozitáře
APP_DIR = "." 

DB_FILE = os.path.join(APP_DIR, 'fakturace_v8.db')
BACKUP_DIR = os.path.join(APP_DIR, 'zalohy')
if not os.path.exists(BACKUP_DIR): 
    try: os.makedirs(BACKUP_DIR)
    except: pass

def run_command(sql, params=()):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(sql, params)
        conn.commit()
        return c.lastrowid

def run_query(sql, params=(), single=False):
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(sql, params)
        return c.fetchone() if single else c.fetchall()

def init_db():
    tables = [
        '''CREATE TABLE IF NOT EXISTS nastaveni (id INTEGER PRIMARY KEY, nazev TEXT, adresa TEXT, ico TEXT, dic TEXT, ucet TEXT, banka TEXT, email TEXT, telefon TEXT, iban TEXT, smtp_server TEXT, smtp_port INTEGER, smtp_email TEXT, smtp_password TEXT, notify_email TEXT, notify_days INTEGER, notify_active INTEGER, license_key TEXT, last_license_check TEXT, license_owner TEXT, license_exp TEXT)''',
        '''CREATE TABLE IF NOT EXISTS klienti (id INTEGER PRIMARY KEY, jmeno TEXT, adresa TEXT, ico TEXT, dic TEXT, email TEXT)''',
        '''CREATE TABLE IF NOT EXISTS kategorie (id INTEGER PRIMARY KEY, nazev TEXT, barva TEXT, prefix TEXT, aktualni_cislo INTEGER DEFAULT 1, logo_blob BLOB)''',
        '''CREATE TABLE IF NOT EXISTS faktury (id INTEGER PRIMARY KEY, cislo INTEGER, cislo_full TEXT, klient_id INTEGER, kategorie_id INTEGER, datum_vystaveni TEXT, datum_duzp TEXT, datum_splatnosti TEXT, castka_celkem REAL, zpusob_uhrady TEXT, variabilni_symbol TEXT, cislo_objednavky TEXT, uvodni_text TEXT, uhrazeno INTEGER DEFAULT 0, muj_popis TEXT)''',
        '''CREATE TABLE IF NOT EXISTS faktura_polozky (id INTEGER PRIMARY KEY, faktura_id INTEGER, nazev TEXT, cena REAL)'''
    ]
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        for t in tables: c.execute(t)
        # Migrace
        cols = [
            ("faktury", "muj_popis", "TEXT"), ("nastaveni", "iban", "TEXT"), ("kategorie", "logo_blob", "BLOB"),
            ("nastaveni", "smtp_server", "TEXT"), ("nastaveni", "smtp_port", "INTEGER"),
            ("nastaveni", "smtp_email", "TEXT"), ("nastaveni", "smtp_password", "TEXT"),
            ("nastaveni", "notify_email", "TEXT"), ("nastaveni", "notify_days", "INTEGER"), ("nastaveni", "notify_active", "INTEGER"),
            ("nastaveni", "license_key", "TEXT"), ("nastaveni", "last_license_check", "TEXT"),
            ("nastaveni", "license_owner", "TEXT"), ("nastaveni", "license_exp", "TEXT")
        ]
        for tbl, col, dtype in cols:
            try: c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {dtype}")
            except: pass
        conn.commit()

if not st.session_state.db_inited:
    init_db()
    st.session_state.db_inited = True

# --- 4. RYCHLÉ FUNKCE ---
def get_my_details():
    try:
        res = run_query("SELECT * FROM nastaveni LIMIT 1", single=True)
        return dict(res) if res else {}
    except: return {}

def format_date(d_str):
    if not d_str: return ""
    try:
        if isinstance(d_str, (datetime, date)): return d_str.strftime('%d.%m.%Y')
        return datetime.strptime(str(d_str), '%Y-%m-%d').strftime('%d.%m.%Y')
    except: return str(d_str)

# --- 5. TĚŽKÉ FUNKCE (LAZY IMPORT) ---
def get_ares_data(ico):
    import requests 
    import urllib3
    urllib3.disable_warnings()
    if not ico: return None
    ico = "".join(filter(str.isdigit, str(ico)))
    if len(ico) < 8: ico = ico.zfill(8)
    try:
        r = requests.get(f"https://ares.gov.cz/ekonomicke-subjekty/v-1/ekonomicke-subjekty/{ico}", headers={"accept": "application/json", "User-Agent": "Mozilla/5.0"}, verify=False, timeout=5)
        if r.status_code == 200:
            d = r.json()
            nm = d.get('obchodniJmeno', '')
            s = d.get('sidlo', {})
            adr = s.get('textovaAdresa', '')
            if not adr:
                u, cp, co = s.get('nazevUlice',''), str(s.get('cisloDomovni','')), str(s.get('cisloOrientacni',''))
                n = cp + (f"/{co}" if co != 'None' else "")
                adr = f"{u} {n}, {s.get('psc','')} {s.get('nazevObce','')}".strip()
            return {"jmeno": nm, "adresa": adr, "ico": ico, "dic": d.get('dic', '')}
    except: pass
    return None

def process_logo(uploaded_file):
    from PIL import Image 
    if uploaded_file is None: return None
    try:
        img = Image.open(uploaded_file)
        buf = io.BytesIO(); img.save(buf, format='PNG')
        return buf.getvalue()
    except: return None

def get_next_invoice_number(kat_id):
    try: kat_id = int(kat_id)
    except: return 0, "Chyba", ""
    res = run_query("SELECT prefix, aktualni_cislo FROM kategorie WHERE id = ?", (kat_id,), single=True)
    if not res: return 0, "Neznámá", ""
    return res['aktualni_cislo'], str(res['aktualni_cislo']), res['prefix']

def send_email_alert(subject, body, settings):
    if not settings.get('notify_active'): return False, "Vypnuto"
    import smtplib 
    from email.mime.text import MIMEText 
    from email.mime.multipart import MIMEMultipart
    
    msg = MIMEMultipart()
    msg['From'] = settings['smtp_email']; msg['To'] = settings['notify_email']; msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    try:
        server = smtplib.SMTP(settings['smtp_server'], settings['smtp_port'])
        server.starttls()
        server.login(settings['smtp_email'], settings['smtp_password'])
        server.sendmail(settings['smtp_email'], settings['notify_email'], msg.as_string())
        server.quit()
        return True, "OK"
    except Exception as e: return False, str(e)

def check_due_invoices():
    settings = get_my_details()
    if not settings or not settings.get('notify_active'): return []
    days = settings.get('notify_days', 3)
    target = date.today() + timedelta(days=days)
    rows = run_query("SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id = k.id WHERE f.uhrazeno = 0")
    alerts = []
    for r in rows:
        try:
            spl = datetime.strptime(r['datum_splatnosti'], '%Y-%m-%d').date()
            if spl < date.today(): 
                r = dict(r); r['po_splatnosti'] = True; alerts.append(r)
            elif date.today() <= spl <= target: 
                alerts.append(r)
        except: pass
    return alerts

def export_data_to_json():
    import pandas as pd 
    data = {}
    for t in ['nastaveni', 'klienti', 'kategorie', 'faktury', 'faktura_polozky']:
        df = pd.read_sql(f"SELECT * FROM {t}", sqlite3.connect(DB_FILE))
        if t == 'kategorie' and 'logo_blob' in df.columns:
            df['logo_blob'] = df['logo_blob'].apply(lambda x: base64.b64encode(x).decode('utf-8') if x else None)
        data[t] = df.to_dict(orient='records')
    return json.dumps(data, indent=4, default=str)

def import_data_from_json(json_file):
    try:
        data = json.load(json_file)
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            for t in ['faktura_polozky', 'faktury', 'kategorie', 'klienti', 'nastaveni']:
                c.execute(f"DELETE FROM {t}")
            for table, rows in data.items():
                if not rows: continue
                if table == 'kategorie':
                    for r in rows:
                        if r.get('logo_blob'): r['logo_blob'] = base64.b64decode(r['logo_blob'])
                cols = rows[0].keys(); ph = ', '.join(['?']*len(cols)); cl = ', '.join(cols)
                for r in rows: c.execute(f"INSERT INTO {table} ({cl}) VALUES ({ph})", list(r.values()))
            conn.commit()
        return True
    except: return False

def remove_accents(input_str):
    if not input_str: return ""
    nfkd = unicodedata.normalize('NFKD', str(input_str))
    return "".join([c for c in nfkd if not unicodedata.combining(c)])

def generate_pdf(faktura_id):
    from fpdf import FPDF 
    import qrcode
    
    class PDF(FPDF):
        def header(self):
            font_path = 'arial.ttf' # Hledáme font ve složce aplikace
            self.font_ok = False
            
            # Zkusíme najít arial.ttf v aktuální složce
            if os.path.exists("arial.ttf"):
                try:
                    self.add_font('ArialCS', '', 'arial.ttf', uni=True)
                    self.add_font('ArialCS', 'B', 'arial.ttf', uni=True) 
                    self.set_font('ArialCS', 'B', 24)
                    self.font_ok = True
                except: pass
            
            if not self.font_ok:
                self.set_font('Arial', 'B', 24) # Fallback
                
            self.set_text_color(50, 50, 50)
            self.cell(0, 10, 'FAKTURA', 0, 1, 'R'); self.ln(5)

    try:
        data = run_query("""SELECT f.*, k.jmeno as k_jmeno, k.adresa as k_adresa, k.ico as k_ico, k.dic as k_dic, 
                            kat.barva, kat.logo_blob 
                            FROM faktury f 
                            JOIN klienti k ON f.klient_id = k.id 
                            JOIN kategorie kat ON f.kategorie_id = kat.id 
                            WHERE f.id = ?""", (faktura_id,), single=True)
        if not data: return None
        polozky = run_query("SELECT * FROM faktura_polozky WHERE faktura_id = ?", (faktura_id,))
        moje = get_my_details()

        pdf = PDF(); pdf.add_page()
        
        def stxt(t):
            t = str(t) if t else ""
            return t if getattr(pdf, 'font_ok', False) else remove_accents(t)
        
        fname = 'ArialCS' if getattr(pdf, 'font_ok', False) else 'Arial'
        pdf.set_font(fname, '', 10)

        if data['logo_blob']:
            try:
                fn = f"t_{faktura_id}.png"
                with open(fn, "wb") as f: f.write(data['logo_blob'])
                pdf.image(fn, x=10, y=10, w=30); os.remove(fn)
            except: pass

        try:
            c = data['barva'].lstrip('#')
            r, g, b = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
            fr, fg, fb = int(r+(255-r)*0.9), int(g+(255-g)*0.9), int(b+(255-b)*0.9)
        except: r,g,b=100,100,100; fr,fg,fb=240,240,240

        pdf.set_text_color(100, 100, 100); pdf.set_y(40)
        pdf.cell(95, 5, stxt("DODAVATEL:"), 0, 0); pdf.cell(95, 5, stxt("ODBĚRATEL:"), 0, 1)
        pdf.set_text_color(0, 0, 0); y = pdf.get_y()
        pdf.set_font(fname, '', 12); pdf.cell(95, 5, stxt(moje.get('nazev','')), 0, 1)
        pdf.set_font(fname, '', 10); pdf.multi_cell(95, 5, stxt(f"{moje.get('adresa','')}\nIČ: {moje.get('ico','')}\nDIČ: {moje.get('dic','')}\n{moje.get('email','')}"))
        pdf.set_xy(105, y); pdf.set_font(fname, '', 12); pdf.cell(95, 5, stxt(data['k_jmeno']), 0, 1)
        pdf.set_xy(105, pdf.get_y()); pdf.set_font(fname, '', 10); pdf.multi_cell(95, 5, stxt(f"{data['k_adresa']}\nIČ: {data['k_ico']}\nDIČ: {data['k_dic']}"))
        
        pdf.ln(10); pdf.set_fill_color(r, g, b); pdf.rect(10, pdf.get_y(), 190, 2, 'F'); pdf.ln(5)
        pdf.set_font(fname, '', 14); pdf.cell(100, 8, stxt(f"Faktura č.: {data['cislo_full']}"), 0, 1)
        pdf.set_font(fname, '', 10); y_d = pdf.get_y()
        pdf.cell(50, 6, stxt("Datum vystavení:"), 0, 0); pdf.cell(50, 6, format_date(data['datum_vystaveni']), 0, 1)
        pdf.cell(50, 6, stxt("Datum splatnosti:"), 0, 0); pdf.cell(50, 6, format_date(data['datum_splatnosti']), 0, 1)
        if data['cislo_objednavky']: pdf.cell(50, 6, stxt(f"Objednávka č.: {data['cislo_objednavky']}"), 0, 1)
        else: pdf.ln(6)
        
        pdf.set_xy(110, y_d)
        pdf.cell(40, 6, stxt("Banka:"), 0, 0); pdf.cell(50, 6, stxt(moje.get('banka','')), 0, 1)
        pdf.set_xy(110, pdf.get_y()); pdf.cell(40, 6, stxt("Číslo účtu:"), 0, 0); pdf.cell(50, 6, stxt(moje.get('ucet','')), 0, 1)
        pdf.set_xy(110, pdf.get_y()); pdf.cell(40, 6, stxt("Var. symbol:"), 0, 0); pdf.cell(50, 6, str(data['variabilni_symbol']), 0, 1)
        pdf.set_xy(110, pdf.get_y()); pdf.cell(40, 6, stxt("Způsob úhrady:"), 0, 0); pdf.cell(50, 6, stxt(data['zpusob_uhrady']), 0, 1)
        
        pdf.ln(15)
        if data['uvodni_text']: pdf.set_font(fname, '', 10); pdf.multi_cell(190, 5, stxt(data['uvodni_text']), 0, 'L'); pdf.ln(5)
        
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(140, 8, stxt(" POLOŽKA / POPIS"), 1, 0, 'L', fill=True); pdf.cell(50, 8, stxt("CENA "), 1, 1, 'R', fill=True); pdf.ln(8)
        
        for item in polozky:
            xb, yb = pdf.get_x(), pdf.get_y()
            pdf.multi_cell(140, 8, stxt(item['nazev']), 0, 'L')
            pdf.set_xy(xb + 140, yb)
            pdf.cell(50, 8, stxt(f"{item['cena']:,.2f} Kč").replace(",", " "), 0, 1, 'R')
            pdf.set_xy(10, max(pdf.get_y(), yb + 8))
            pdf.set_draw_color(240, 240, 240); pdf.line(10, pdf.get_y(), 200, pdf.get_y())

        pdf.ln(10); pdf.set_draw_color(r, g, b); pdf.set_fill_color(fr, fg, fb); pdf.set_line_width(0.5)
        bx, by = 110, pdf.get_y(); pdf.rect(bx, by, 90, 14, 'DF'); pdf.set_xy(bx, by + 4)
        pdf.set_font(fname, 'B' if getattr(pdf, 'font_ok', False) else '', 14); pdf.set_text_color(0, 0, 0)
        pdf.cell(40, 6, stxt("CELKEM:"), 0, 0, 'L'); pdf.cell(45, 6, stxt(f"{data['castka_celkem']:,.2f} Kč").replace(",", " "), 0, 1, 'R')
        
        pdf.ln(25); pdf.set_font(fname, '', 10); pdf.set_text_color(50, 50, 50); pdf.set_x(120)
        pdf.cell(70, 0, "", 'T'); pdf.ln(2); pdf.set_x(120); pdf.cell(70, 5, stxt("Podpis a razítko dodavatele"), 0, 1, 'C')
        
        if moje.get('iban'):
            try:
                qr = f"SPD*1.0*ACC:{moje['iban'].replace(' ','').upper()}*AM:{data['castka_celkem']:.2f}*CC:CZK*MSG:{stxt('Faktura '+str(data['cislo_full']))}*X-VS:{str(data['variabilni_symbol'])}"
                img = qrcode.make(qr); img.save(f"q_{faktura_id}.png")
                pdf.image(f"q_{faktura_id}.png", x=10, y=pdf.get_y()-15, w=35); os.remove(f"q_{faktura_id}.png")
            except: pass
        
        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except Exception as e: return f"ERROR: {str(e)}"

# --- 6. LICENČNÍ SYSTÉM (ONLINE GIST) ---
LICENSE_URL = "https://gist.githubusercontent.com/hrozinka/6cd3ef1eea1e6d7dc7b188bdbeb84235/raw/licence.json"

def check_license_online(key):
    import requests # Lazy load
    try:
        cache_buster = f"?t={int(datetime.now().timestamp())}"
        response = requests.get(LICENSE_URL + cache_buster, timeout=5)
        
        if response.status_code != 200:
            return False, "Chyba serveru licencí (kód neodpovídá).", None, None
        
        try:
            valid_keys_db = response.json()
        except:
            response = requests.get(LICENSE_URL, timeout=5)
            valid_keys_db = json.loads(response.text)

        if key in valid_keys_db:
            info = valid_keys_db[key]
            if not info.get("active", True): return False, "Licence byla zablokována / deaktivována.", None, None
            exp_str = info.get("exp", "2099-12-31")
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                if date.today() > exp_date: return False, f"Licence vypršela dne {format_date(exp_date)}.", None, None
            except: pass
            return True, "Platná licence", info.get("note", "Uživatel"), exp_str
        return False, "Tento licenční klíč neexistuje v databázi.", None, None
    except Exception as e:
        return False, f"Chyba připojení k internetu: {str(e)}", None, None

def verify_app_access():
    """Hlavní kontrolní brána."""
    settings = get_my_details()
    if not settings: return "NO_KEY"
    saved_key = settings.get('license_key')
    if not saved_key: return "NO_KEY"
    
    # Na webu kontrolujeme vzdy, neni tu persistentni cache
    valid, msg, owner, exp = check_license_online(saved_key)
    if valid:
        run_command("UPDATE nastaveni SET last_license_check=?, license_owner=?, license_exp=? WHERE id=?", (date.today().strftime("%Y-%m-%d"), owner, exp, settings['id']))
        return True
    return msg 

# --- 7. ZÁMEK APLIKACE ---
access_status = verify_app_access()

if access_status != True:
    st.markdown("<br><br><h1 style='text-align: center;'>🔒 Aktivace Aplikace</h1>", unsafe_allow_html=True)
    if access_status != "NO_KEY": st.error(f"⚠️ {access_status}")
    else: st.info("Pro spuštění aplikace zadejte platný licenční klíč.")
    
    with st.form("lic_form"):
        k = st.text_input("Licenční klíč", placeholder="XXXX-XXXX-XXXX").strip()
        if st.form_submit_button("🚀 Ověřit a Spustit"):
            is_val, txt, owner, exp = check_license_online(k)
            if is_val:
                sets = get_my_details()
                if sets.get('id'): run_command("UPDATE nastaveni SET license_key=?, last_license_check=?, license_owner=?, license_exp=? WHERE id=?", (k, date.today().strftime("%Y-%m-%d"), owner, exp, sets['id']))
                else: run_command("INSERT INTO nastaveni (license_key, last_license_check, license_owner, license_exp) VALUES (?,?,?,?)", (k, date.today().strftime("%Y-%m-%d"), owner, exp))
                st.success(f"Vítejte, {owner}! Spouštím aplikaci..."); st.rerun()
            else: st.error(txt)
    st.stop() 

# ==========================================
# HLAVNÍ APLIKACE
# ==========================================

curr = get_my_details()
owner_display = curr.get('license_owner', 'Uživatel')
st.sidebar.markdown(f"<div class='user-label'>👤 Licence: <b>{owner_display}</b><br><small>✅ Aktivní</small></div>", unsafe_allow_html=True)

st.sidebar.title("Navigace")
menu = st.sidebar.radio("Menu", ["Faktury", "Klienti", "Kategorie", "Nastavení"], label_visibility="collapsed")

if menu == "Nastavení":
    st.header("⚙️ Nastavení")
    c = get_my_details()
    with st.expander("🏢 Firemní údaje", expanded=True):
        with st.form("f1"):
            n=st.text_input("Název", c.get('nazev','')); a=st.text_area("Adresa", c.get('adresa',''))
            c1,c2=st.columns(2); i=c1.text_input("IČO", c.get('ico','')); d=c2.text_input("DIČ", c.get('dic',''))
            c3,c4=st.columns(2); e=c3.text_input("Email", c.get('email','')); t=c4.text_input("Tel", c.get('telefon',''))
            if st.form_submit_button("Uložit"):
                if c.get('id'): run_command("UPDATE nastaveni SET nazev=?, adresa=?, ico=?, dic=?, email=?, telefon=? WHERE id=?", (n,a,i,d,e,t,c['id']))
                else: run_command("INSERT INTO nastaveni (nazev, adresa, ico, dic, email, telefon) VALUES (?,?,?,?,?,?)", (n,a,i,d,e,t))
                st.rerun()
    with st.expander("🏦 Banka"):
        with st.form("f2"):
            b=st.text_input("Banka", c.get('banka','')); u=st.text_input("Účet", c.get('ucet','')); ib=st.text_input("IBAN", c.get('iban',''))
            if st.form_submit_button("Uložit"):
                run_command("UPDATE nastaveni SET banka=?, ucet=?, iban=? WHERE id=?", (b,u,ib,c['id'])); st.rerun()
    
    with st.expander("🔔 Upozornění na splatnost"):
        st.info("Zde nastavíte automatické e-mailové upozornění.")
        active = st.toggle("✅ Povolit odesílání e-mailů", value=bool(c.get('notify_active', 0)))
        if active:
            st.divider(); c1, c2 = st.columns(2)
            notify_email = c1.text_input("📩 Email příjemce", value=c.get('notify_email', ''))
            days = c2.slider("📅 Dní předem", 1, 30, value=c.get('notify_days', 3))
            st.divider(); st.caption("Nastavení SMTP")
            with st.expander("❓ Jak získat heslo aplikace?"): st.markdown("**Gmail:** Zabezpečení -> Dvoufázové ověření -> Hesla aplikací.")
            provider = st.selectbox("Poskytovatel", ["Gmail", "Seznam.cz", "Vlastní"], index=0)
            def_srv = c.get('smtp_server', '') if c.get('smtp_server') else "smtp.gmail.com"
            def_port = c.get('smtp_port', 587) if c.get('smtp_port') else 587
            if provider == "Gmail": def_srv="smtp.gmail.com"; def_port=587
            elif provider == "Seznam.cz": def_srv="smtp.seznam.cz"; def_port=25
            with st.form("notify_form"):
                s_srv = st.text_input("SMTP Server", value=def_srv)
                s_port = st.number_input("SMTP Port", value=def_port)
                s_email = st.text_input("Login Email", value=c.get('smtp_email', ''))
                s_pass = st.text_input("Heslo aplikace", value=c.get('smtp_password', ''), type="password")
                if st.form_submit_button("💾 Uložit"):
                    run_command("UPDATE nastaveni SET notify_active=?, notify_email=?, notify_days=?, smtp_server=?, smtp_port=?, smtp_email=?, smtp_password=? WHERE id=?", (1, notify_email, days, s_srv, s_port, s_email, s_pass, c['id'])); st.success("OK"); st.rerun()
            if st.button("🚀 Test Email"):
                ok, msg = send_email_alert("Test", "Test OK", get_my_details())
                st.toast("Odesláno") if ok else st.error(msg)
        else:
            if st.button("Vypnout"): run_command("UPDATE nastaveni SET notify_active=0 WHERE id=?", (c['id'],)); st.rerun()

    with st.expander("💾 Záloha / Obnova"):
        import pandas as pd
        def get_json():
            data = {}
            for t in ['nastaveni', 'klienti', 'kategorie', 'faktury', 'faktura_polozky']:
                df = pd.read_sql(f"SELECT * FROM {t}", sqlite3.connect(DB_FILE))
                if t == 'kategorie' and 'logo_blob' in df.columns: df['logo_blob'] = df['logo_blob'].apply(lambda x: base64.b64encode(x).decode('utf-8') if x else None)
                data[t] = df.to_dict(orient='records')
            return json.dumps(data, default=str)
        st.download_button("Stáhnout zálohu (JSON)", get_json(), f"zaloha_{date.today()}.json", "application/json")
        upl = st.file_uploader("Nahrát zálohu (JSON)", type="json")
        if upl and st.button("Obnovit data"):
            d = json.load(upl)
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.cursor()
                for t in d.keys(): cur.execute(f"DELETE FROM {t}")
                for t, rows in d.items():
                    if not rows: continue
                    if t == 'kategorie':
                        for r in rows: 
                            if r.get('logo_blob'): r['logo_blob'] = base64.b64decode(r['logo_blob'])
                    c_names = rows[0].keys(); q = f"INSERT INTO {t} ({','.join(c_names)}) VALUES ({','.join(['?']*len(c_names))})"
                    for r in rows: cur.execute(q, list(r.values()))
                conn.commit()
            st.success("Obnoveno!"); st.rerun()
            
    st.divider()
    st.markdown("### 🛠️ Správa Licence")
    with st.expander("🔐 Zobrazit detaily licence"):
        st.write(f"**Klíč:** `{c.get('license_key', '---')}`")
        raw_date = c.get('license_exp', 'Neznámé')
        if raw_date and raw_date != 'Neznámé':
            try: fmt_date = datetime.strptime(raw_date, '%Y-%m-%d').strftime('%d.%m.%Y')
            except: fmt_date = raw_date
        else: fmt_date = "Neznámé"
        st.write(f"**Platnost do:** {fmt_date}")

    if st.button("🗑️ Odhlásit licenci (Zablokovat aplikaci)", type="primary"):
        run_command("UPDATE nastaveni SET license_key=NULL, last_license_check=NULL, license_owner=NULL WHERE id=?", (c['id'],))
        st.warning("Licence odstraněna."); st.rerun()

elif menu == "Klienti":
    st.header("👥 Klienti")
    rid = st.session_state.form_reset_id
    with st.expander("➕ Přidat", expanded=True):
        c1,c2 = st.columns([3,1]); ico = c1.text_input("IČO", key=f"s_{rid}")
        if c2.button("ARES", key=f"b_{rid}"): st.session_state.ares_data = get_ares_data(ico) or {}
        ad = st.session_state.ares_data
        with st.form(f"cf_{rid}", clear_on_submit=True):
            j=st.text_input("Jméno", ad.get('jmeno','')); a=st.text_area("Adresa", ad.get('adresa',''))
            k1,k2=st.columns(2); i=k1.text_input("IČ", ad.get('ico','')); d=k2.text_input("DIČ", ad.get('dic',''))
            if st.form_submit_button("Uložit"): run_command("INSERT INTO klienti (jmeno, adresa, ico, dic) VALUES (?,?,?,?)", (j,a,i,d)); reset_forms(); st.rerun()
    search = st.text_input("Hledat"); q = "SELECT * FROM klienti"; params=()
    if search: q += " WHERE jmeno LIKE ?"; params=(f"%{search}%",)
    for r in run_query(q, params):
        with st.expander(f"{r['jmeno']} (IČ: {r['ico']})"):
            with st.form(f"ec_{r['id']}"):
                nj=st.text_input("Jméno", r['jmeno']); na=st.text_area("Adresa", r['adresa'])
                c1,c2=st.columns(2); ni=c1.text_input("IČ", r['ico']); nd=c2.text_input("DIČ", r['dic'])
                if st.form_submit_button("Upravit"): run_command("UPDATE klienti SET jmeno=?, adresa=?, ico=?, dic=? WHERE id=?", (nj,na,ni,nd,r['id'])); st.rerun()
            if st.button("Smazat", key=f"dc_{r['id']}"): run_command("DELETE FROM klienti WHERE id=?", (r['id'],)); st.rerun()

elif menu == "Kategorie":
    st.header("🏷️ Kategorie")
    rid = st.session_state.form_reset_id
    with st.expander("➕ Nová", expanded=False):
        with st.form(f"kf_{rid}"):
            n=st.text_input("Název"); p=st.text_input("Prefix"); s=st.number_input("Start", 1); c=st.color_picker("Barva", "#3498db")
            l=st.file_uploader("Logo", type=['png','jpg'])
            if st.form_submit_button("Uložit"): run_command("INSERT INTO kategorie (nazev, prefix, aktualni_cislo, barva, logo_blob) VALUES (?,?,?,?,?)", (n,p,s,c,process_logo(l))); reset_forms(); st.rerun()
    for r in run_query("SELECT * FROM kategorie"):
        with st.expander(f"{r['nazev']}"):
            if r['logo_blob']: st.image(r['logo_blob'], width=100)
            with st.form(f"ek_{r['id']}"):
                en=st.text_input("Název", r['nazev']); ep=st.text_input("Prefix", r['prefix']); es=st.number_input("Číslo", value=r['aktualni_cislo'])
                eb=st.color_picker("Barva", r['barva']); el=st.file_uploader("Nové logo", type=['png','jpg'])
                if st.form_submit_button("Upravit"):
                    blob = process_logo(el) if el else r['logo_blob']
                    run_command("UPDATE kategorie SET nazev=?, prefix=?, aktualni_cislo=?, barva=?, logo_blob=? WHERE id=?", (en,ep,es,eb,blob,r['id'])); st.rerun()
            if st.button("Smazat", key=f"dk_{r['id']}"): run_command("DELETE FROM kategorie WHERE id=?", (r['id'],)); st.rerun()

elif menu == "Faktury":
    import pandas as pd # Lazy load tabulky
    if 'items_df' not in st.session_state: st.session_state.items_df = pd.DataFrame(columns=["Popis položky", "Cena"])

    st.header("📊 Přehled")
    cy = datetime.now().year; ly = cy - 1
    sc = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE strftime('%Y', datum_vystaveni) = ?", (str(cy),), True)[0] or 0
    sl = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE strftime('%Y', datum_vystaveni) = ?", (str(ly),), True)[0] or 0
    su = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE uhrazeno = 0 AND strftime('%Y', datum_vystaveni) = ?", (str(cy),), True)[0] or 0
    c1, c2 = st.columns(2)
    with c1: st.markdown(f"<div class='stat-box'><div class='stat-num'>{sc:,.0f} Kč</div><div class='stat-sub'>Fakturováno {cy}<br>Loni: {sl:,.0f} Kč</div></div>", unsafe_allow_html=True)
    with c2: st.markdown(f"<div class='stat-box'><div class='stat-err'>{su:,.0f} Kč</div><div class='stat-sub'>Neuhrazeno ({cy})</div></div>", unsafe_allow_html=True)
    st.divider()

    if st.button("🔍 Zkontrolovat splatnost"):
        alerts = check_due_invoices()
        if alerts:
            st.warning(f"Nalezeno {len(alerts)} faktur.")
            for a in alerts:
                if st.button(f"📧 Upomínka: {a['cislo_full']}", key=f"m_{a['id']}"):
                    ok, msg = send_email_alert(f"Upomínka {a['cislo_full']}", f"Faktura {a['cislo_full']} je po splatnosti.", get_my_details())
                    st.toast("Odesláno") if ok else st.error(msg)
        else: st.info("Vše v pořádku.")

    rid = st.session_state.form_reset_id
    with st.expander("➕ Nová faktura"):
        kli = pd.read_sql("SELECT id, jmeno FROM klienti", sqlite3.connect(DB_FILE))
        kat = pd.read_sql("SELECT id, nazev FROM kategorie", sqlite3.connect(DB_FILE))
        if kli.empty or kat.empty: st.warning("Chybí data")
        else:
            k1,k2 = st.columns(2); sk = k1.selectbox("Klient", kli['jmeno'], key=f"sk_{rid}"); sc = k2.selectbox("Kategorie", kat['nazev'], key=f"sc_{rid}")
            kid = int(kli[kli['jmeno']==sk]['id'].values[0]); cid = int(kat[kat['nazev']==sc]['id'].values[0])
            _, full, _ = get_next_invoice_number(cid); st.info(f"Číslo: **{full}**")
            k3,k4=st.columns(2); obj=k3.text_input("Objednávka", key=f"o_{rid}"); mp=k4.text_input("Popis", key=f"p_{rid}")
            d1,d2,d3=st.columns(3); dv=d1.date_input("Vystavení", date.today(), key=f"d1_{rid}"); du=d2.date_input("DUZP", date.today(), key=f"d2_{rid}"); ds=d3.date_input("Splatnost", date.today()+timedelta(14), key=f"d3_{rid}")
            zp = st.selectbox("Úhrada", ["Prevodem", "Hotove", "Kartou"], key=f"z_{rid}"); uv = st.text_input("Text", "Fakturujeme Vám:", key=f"t_{rid}")
            if 'items_df' not in st.session_state: st.session_state.items_df = pd.DataFrame(columns=["Popis položky", "Cena"])
            ed = st.data_editor(st.session_state.items_df, num_rows="dynamic", width='stretch', column_config={"Cena": st.column_config.NumberColumn("Cena", format="%.2f")}, key=f"ed_{rid}")
            try: tot = float(pd.to_numeric(ed["Cena"], errors='coerce').fillna(0).sum())
            except: tot = 0.0
            st.markdown(f"### Celkem: {tot:,.2f} Kč")
            if st.button("Vystavit", type="primary", key=f"b_{rid}"):
                _, f, _ = get_next_invoice_number(cid)
                fid = run_command("INSERT INTO faktury (cislo, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_duzp, datum_splatnosti, castka_celkem, zpusob_uhrady, variabilni_symbol, cislo_objednavky, uvodni_text, uhrazeno, muj_popis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (0, f, kid, cid, dv, du, ds, tot, zp, re.sub(r"\D", "", f), obj, uv, 0, mp))
                for _, r in ed.iterrows():
                    if r["Popis položky"]: run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (fid, r["Popis položky"], float(r["Cena"])))
                run_command("UPDATE kategorie SET aktualni_cislo = aktualni_cislo + 1 WHERE id = ?", (cid,)); st.success("Hotovo"); reset_forms(); st.rerun()

    st.divider()
    all_clients = pd.read_sql("SELECT jmeno FROM klienti ORDER BY jmeno", sqlite3.connect(DB_FILE))
    flt = st.selectbox("Filtr", ["Všichni"] + all_clients['jmeno'].tolist())
    query = "SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id = k.id"
    params = ()
    if flt != "Všichni": query += " WHERE k.jmeno = ?"; params = (flt,)
    query += " ORDER BY f.id DESC LIMIT 50"
    df = pd.read_sql(query, sqlite3.connect(DB_FILE), params=params)
    if flt != "Všichni":
        c_tot = df['castka_celkem'].sum()
        c_unp = df[df['uhrazeno']==0]['castka_celkem'].sum()
        c_hist = run_query("SELECT SUM(castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id = k.id WHERE k.jmeno = ? AND strftime('%Y', datum_vystaveni) < ?", (flt, str(cy)), True)[0] or 0
        st.markdown(f"""<div class="mini-stat-container"><div class="mini-stat-box"><div class="mini-label">ZOBRAZENO</div><div class="mini-val-green">{c_tot:,.0f} Kč</div></div><div class="mini-stat-box"><div class="mini-label">HISTORIE</div><div class="mini-val-gray">{c_hist:,.0f} Kč</div></div><div class="mini-stat-box"><div class="mini-label">NEUHRAZENO</div><div class="mini-val-red">{c_unp:,.0f} Kč</div></div></div>""", unsafe_allow_html=True)

    for _, r in df.iterrows():
        icon = "✅" if r['uhrazeno'] else "⏳"
        with st.expander(f"{r['id']}. {icon} {r['cislo_full']} | {format_date(r['datum_vystaveni'])} | {r['jmeno']} | {r['castka_celkem']:,.0f} Kč"):
            c1,c2,c3 = st.columns([1,1,2])
            if r['uhrazeno']:
                if c1.button("Zrušit úhradu", key=f"u0_{r['id']}"): run_command("UPDATE faktury SET uhrazeno=0 WHERE id=?", (r['id'],)); st.rerun()
            else:
                if c1.button("Zaplaceno", key=f"u1_{r['id']}"): run_command("UPDATE faktury SET uhrazeno=1 WHERE id=?", (r['id'],)); st.rerun()
            if c2.button("📄 PDF", key=f"pdf_{r['id']}"):
                pdf = generate_pdf(r['id'])
                if isinstance(pdf, bytes): c2.download_button("⬇️ Stáhnout", pdf, f"{r['cislo_full']}.pdf", "application/pdf")
                else: c2.error(pdf)
            
            edit_key = f"e_{r['id']}"
            if edit_key not in st.session_state: st.session_state[edit_key] = False
            if not st.session_state[edit_key]:
                if c3.button("✏️ Upravit", key=f"be_{r['id']}"): st.session_state[edit_key] = True; st.rerun()
            else:
                st.markdown("---")
                with st.form(f"ef_{r['id']}"):
                    eo = st.text_input("Objednávka", value=r['cislo_objednavky'] or "")
                    em = st.text_input("Popis", value=r['muj_popis'] or "")
                    ed = st.date_input("Splatnost", pd.to_datetime(r['datum_splatnosti']))
                    itms = pd.read_sql(f"SELECT nazev as 'Popis položky', cena as 'Cena' FROM faktura_polozky WHERE faktura_id={r['id']}", sqlite3.connect(DB_FILE))
                    eed = st.data_editor(itms, num_rows="dynamic", use_container_width=True)
                    c_save, c_close = st.columns(2)
                    if c_save.form_submit_button("💾 Uložit"):
                        etot = float(pd.to_numeric(eed["Cena"], errors='coerce').fillna(0).sum())
                        run_command("UPDATE faktury SET cislo_objednavky=?, muj_popis=?, datum_splatnosti=?, castka_celkem=? WHERE id=?", (eo, em, ed, etot, r['id']))
                        run_command("DELETE FROM faktura_polozky WHERE faktura_id=?", (r['id'],))
                        for _, er in eed.iterrows():
                            if er["Popis položky"]: run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (r['id'], er["Popis položky"], float(er["Cena"])))
                        st.session_state[edit_key] = False; st.rerun()
                    if c_close.form_submit_button("❌ Zavřít"): st.session_state[edit_key] = False; st.rerun()
            
            if st.button("Smazat", key=f"del_{r['id']}"):
                run_command("DELETE FROM faktury WHERE id=?", (r['id'],)); run_command("DELETE FROM faktura_polozky WHERE faktura_id=?", (r['id'],)); st.rerun()
