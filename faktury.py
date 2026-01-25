import sys
import streamlit as st
import sqlite3
import os
import json
import re
import hashlib
import requests
import smtplib
from datetime import datetime, date, timedelta
import unicodedata
import io
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from PIL import Image

# --- 1. KONFIGURACE A CSS (TMAVÝ REŽIM) ---
st.set_page_config(page_title="Fakturační Systém Online", page_icon="🧾", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #262730 !important; border: 1px solid #4f4f4f !important; color: #ffffff !important;
    }
    div[data-testid="stExpander"] { background-color: #262730 !important; border: 1px solid #4f4f4f; border-radius: 8px; margin-bottom: 8px; }
    div[data-testid="stExpander"] details summary { color: #ffffff !important; }
    .stat-box { background-color: #1f2937; padding: 15px; border-radius: 12px; text-align: center; border: 1px solid #374151; height: 100%; min-height: 120px; display: flex; flex-direction: column; justify-content: center; }
    .stat-num { font-size: 28px; font-weight: 800; color: #4ade80; margin: 0; }
    .stat-err { font-size: 28px; font-weight: 800; color: #f87171; margin: 0; }
    .auth-container { max-width: 400px; margin: 0 auto; padding: 40px 20px; background: #1f2937; border-radius: 10px; border: 1px solid #374151; }
    .locked-msg { text-align: center; padding: 50px; color: #9ca3af; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABÁZE ---
APP_DIR = "."
DB_FILE = os.path.join(APP_DIR, 'fakturace_pro.db')

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    # Users table needs license info
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        license_key TEXT,
        license_valid_until TEXT,
        created_at TEXT
    )''')
    # Settings table needs SMTP info
    c.execute('''CREATE TABLE IF NOT EXISTS nastaveni (
        id INTEGER PRIMARY KEY, user_id INTEGER, 
        nazev TEXT, adresa TEXT, ico TEXT, dic TEXT, ucet TEXT, banka TEXT, email TEXT, telefon TEXT, iban TEXT, 
        smtp_server TEXT, smtp_port INTEGER, smtp_email TEXT, smtp_password TEXT, notify_email TEXT, notify_days INTEGER, notify_active INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS klienti (id INTEGER PRIMARY KEY, user_id INTEGER, jmeno TEXT, adresa TEXT, ico TEXT, dic TEXT, email TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS kategorie (id INTEGER PRIMARY KEY, user_id INTEGER, nazev TEXT, barva TEXT, prefix TEXT, aktualni_cislo INTEGER DEFAULT 1, logo_blob BLOB)''')
    c.execute('''CREATE TABLE IF NOT EXISTS faktury (id INTEGER PRIMARY KEY, user_id INTEGER, cislo INTEGER, cislo_full TEXT, klient_id INTEGER, kategorie_id INTEGER, datum_vystaveni TEXT, datum_duzp TEXT, datum_splatnosti TEXT, castka_celkem REAL, zpusob_uhrady TEXT, variabilni_symbol TEXT, cislo_objednavky TEXT, uvodni_text TEXT, uhrazeno INTEGER DEFAULT 0, muj_popis TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS faktura_polozky (id INTEGER PRIMARY KEY, faktura_id INTEGER, nazev TEXT, cena REAL)''')
    
    # Migrace sloupcu (pokud chybi)
    try: c.execute("ALTER TABLE users ADD COLUMN license_key TEXT")
    except: pass
    try: c.execute("ALTER TABLE users ADD COLUMN license_valid_until TEXT")
    except: pass
    
    conn.commit()
    conn.close()

if 'db_inited' not in st.session_state:
    init_db()
    st.session_state.db_inited = True

# --- 3. HELPER FUNCTIONS ---
def run_query(sql, params=(), single=False):
    conn = get_db(); c = conn.cursor(); c.execute(sql, params)
    res = c.fetchone() if single else c.fetchall(); conn.close(); return res

def run_command(sql, params=()):
    conn = get_db(); c = conn.cursor(); c.execute(sql, params); conn.commit(); lid = c.lastrowid; conn.close(); return lid

def hash_password(password): return hashlib.sha256(str.encode(password)).hexdigest()

def check_license_online(key):
    try:
        r = requests.get(f"https://gist.githubusercontent.com/hrozinka/6cd3ef1eea1e6d7dc7b188bdbeb84235/raw/licence.json?t={int(datetime.now().timestamp())}", timeout=5)
        if r.status_code != 200: return False, "Server nedostupný", None
        db = r.json()
        if key in db:
            if not db[key].get("active", True): return False, "Licence zablokována", None
            return True, "Aktivní", db[key].get("exp", "2099-12-31")
        return False, "Neplatný klíč", None
    except: return False, "Chyba připojení", None

def get_my_details(uid):
    res = run_query("SELECT * FROM nastaveni WHERE user_id = ? LIMIT 1", (uid,), single=True)
    return dict(res) if res else {}

def format_date(d_str):
    if not d_str: return ""
    try: return d_str.strftime('%d.%m.%Y') if isinstance(d_str, (datetime, date)) else datetime.strptime(str(d_str), '%Y-%m-%d').strftime('%d.%m.%Y')
    except: return str(d_str)

def get_ares_data(ico):
    import urllib3; urllib3.disable_warnings()
    if not ico: return None
    ico = "".join(filter(str.isdigit, str(ico))).zfill(8)
    try:
        r = requests.get(f"https://ares.gov.cz/ekonomicke-subjekty/v-1/ekonomicke-subjekty/{ico}", headers={"accept": "application/json"}, verify=False, timeout=5)
        if r.status_code == 200:
            d = r.json(); s = d.get('sidlo', {})
            adr = s.get('textovaAdresa', '')
            if not adr: adr = f"{s.get('nazevUlice','')} {s.get('cisloDomovni','')}/{s.get('cisloOrientacni','')}, {s.get('psc','')} {s.get('nazevObce','')}".strip()
            return {"jmeno": d.get('obchodniJmeno', ''), "adresa": adr, "ico": ico, "dic": d.get('dic', '')}
    except: pass
    return None

def process_logo(uploaded_file):
    if not uploaded_file: return None
    try: img = Image.open(uploaded_file); buf = io.BytesIO(); img.save(buf, format='PNG'); return buf.getvalue()
    except: return None

def get_next_invoice_number(kat_id, uid):
    res = run_query("SELECT prefix, aktualni_cislo FROM kategorie WHERE id = ? AND user_id = ?", (kat_id, uid), single=True)
    return (res['aktualni_cislo'], str(res['aktualni_cislo']), res['prefix']) if res else (0, "Neznámá", "")

def remove_accents(input_str):
    if not input_str: return ""
    return "".join([c for c in unicodedata.normalize('NFKD', str(input_str)) if not unicodedata.combining(c)])

def send_email_alert(subject, body, settings):
    if not settings.get('notify_active'): return False, "Vypnuto"
    msg = MIMEMultipart(); msg['From'] = settings['smtp_email']; msg['To'] = settings['notify_email']; msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    try:
        server = smtplib.SMTP(settings['smtp_server'], settings['smtp_port'])
        server.starttls(); server.login(settings['smtp_email'], settings['smtp_password'])
        server.sendmail(settings['smtp_email'], settings['notify_email'], msg.as_string()); server.quit()
        return True, "OK"
    except Exception as e: return False, str(e)

def check_due_invoices(uid):
    s = get_my_details(uid)
    if not s or not s.get('notify_active'): return []
    target = date.today() + timedelta(days=s.get('notify_days', 3))
    rows = run_query("SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id = k.id WHERE f.user_id = ? AND f.uhrazeno = 0", (uid,))
    alerts = []
    for r in rows:
        try:
            spl = datetime.strptime(r['datum_splatnosti'], '%Y-%m-%d').date()
            if spl < date.today() or date.today() <= spl <= target: alerts.append(r)
        except: pass
    return alerts

# --- 4. PDF GENERATOR ---
def generate_pdf(faktura_id, uid):
    from fpdf import FPDF
    import qrcode
    class PDF(FPDF):
        def header(self):
            font_path = 'arial.ttf'; self.font_ok = False
            if os.path.exists(font_path):
                try: self.add_font('ArialCS', '', font_path, uni=True); self.add_font('ArialCS', 'B', font_path, uni=True); self.set_font('ArialCS', 'B', 24); self.font_ok = True
                except: pass
            if not self.font_ok: self.set_font('Arial', 'B', 24)
            self.set_text_color(50, 50, 50); self.cell(0, 10, 'FAKTURA', 0, 1, 'R'); self.ln(5)

    try:
        data = run_query("SELECT f.*, k.jmeno as k_jmeno, k.adresa as k_adresa, k.ico as k_ico, k.dic as k_dic, kat.barva, kat.logo_blob FROM faktury f JOIN klienti k ON f.klient_id = k.id JOIN kategorie kat ON f.kategorie_id = kat.id WHERE f.id = ? AND f.user_id = ?", (faktura_id, uid), single=True)
        if not data: return "Faktura nenalezena"
        polozky = run_query("SELECT * FROM faktura_polozky WHERE faktura_id = ?", (faktura_id,)); moje = get_my_details(uid)
        pdf = PDF(); pdf.add_page()
        def stxt(t): return str(t) if getattr(pdf, 'font_ok', False) else remove_accents(str(t) if t else "")
        fname = 'ArialCS' if getattr(pdf, 'font_ok', False) else 'Arial'
        pdf.set_font(fname, '', 10)

        if data['logo_blob']:
            try: fn = f"t_{faktura_id}.png"; with open(fn, "wb") as f: f.write(data['logo_blob']); pdf.image(fn, x=10, y=10, w=30); os.remove(fn)
            except: pass
        try: c = data['barva'].lstrip('#'); r, g, b = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
        except: r,g,b=100,100,100
        pdf.set_text_color(100); pdf.set_y(40); pdf.cell(95, 5, stxt("DODAVATEL:"), 0, 0); pdf.cell(95, 5, stxt("ODBĚRATEL:"), 0, 1)
        pdf.set_text_color(0); y = pdf.get_y(); pdf.set_font(fname, '', 12); pdf.cell(95, 5, stxt(moje.get('nazev','')), 0, 1)
        pdf.set_font(fname, '', 10); pdf.multi_cell(95, 5, stxt(f"{moje.get('adresa','')}\nIČ: {moje.get('ico','')}\nDIČ: {moje.get('dic','')}\n{moje.get('email','')}"))
        pdf.set_xy(105, y); pdf.set_font(fname, '', 12); pdf.cell(95, 5, stxt(data['k_jmeno']), 0, 1)
        pdf.set_xy(105, pdf.get_y()); pdf.set_font(fname, '', 10); pdf.multi_cell(95, 5, stxt(f"{data['k_adresa']}\nIČ: {data['k_ico']}\nDIČ: {data['k_dic']}"))
        pdf.ln(10); pdf.set_fill_color(r, g, b); pdf.rect(10, pdf.get_y(), 190, 2, 'F'); pdf.ln(5)
        pdf.set_font(fname, '', 14); pdf.cell(100, 8, stxt(f"Faktura č.: {data['cislo_full']}"), 0, 1); pdf.set_font(fname, '', 10)
        pdf.cell(50, 6, stxt("Datum vystavení:"), 0, 0); pdf.cell(50, 6, format_date(data['datum_vystaveni']), 0, 1)
        pdf.cell(50, 6, stxt("Datum splatnosti:"), 0, 0); pdf.cell(50, 6, format_date(data['datum_splatnosti']), 0, 1)
        pdf.set_xy(110, pdf.get_y()-12); pdf.cell(40, 6, stxt("Banka:"), 0, 0); pdf.cell(50, 6, stxt(moje.get('banka','')), 0, 1)
        pdf.set_xy(110, pdf.get_y()); pdf.cell(40, 6, stxt("Číslo účtu:"), 0, 0); pdf.cell(50, 6, stxt(moje.get('ucet','')), 0, 1)
        pdf.set_xy(110, pdf.get_y()); pdf.cell(40, 6, stxt("Var. symbol:"), 0, 0); pdf.cell(50, 6, str(data['variabilni_symbol']), 0, 1)
        pdf.ln(15); 
        if data['uvodni_text']: pdf.multi_cell(190, 5, stxt(data['uvodni_text']), 0, 'L'); pdf.ln(5)
        pdf.set_fill_color(240); pdf.cell(140, 8, stxt(" POLOŽKA / POPIS"), 1, 0, 'L', fill=True); pdf.cell(50, 8, stxt("CENA "), 1, 1, 'R', fill=True); pdf.ln(8)
        for item in polozky:
            xb, yb = pdf.get_x(), pdf.get_y(); pdf.multi_cell(140, 8, stxt(item['nazev']), 0, 'L'); pdf.set_xy(xb + 140, yb); pdf.cell(50, 8, stxt(f"{item['cena']:,.2f} Kč").replace(",", " "), 0, 1, 'R')
            pdf.set_xy(10, max(pdf.get_y(), yb + 8)); pdf.set_draw_color(240); pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(10); pdf.set_draw_color(r, g, b); pdf.set_fill_color(240); pdf.rect(110, pdf.get_y(), 90, 10, 'F')
        pdf.set_font(fname, 'B', 14); pdf.set_xy(110, pdf.get_y()+2); pdf.cell(40, 6, stxt("CELKEM:"), 0, 0); pdf.cell(45, 6, stxt(f"{data['castka_celkem']:,.2f} Kč").replace(",", " "), 0, 1, 'R')
        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except Exception as e: return f"ERROR: {str(e)}"

# --- 5. LOGIKA APLIKACE A SESSION ---
if 'user_id' not in st.session_state: st.session_state.user_id = None
if 'items_df' not in st.session_state: 
    import pandas as pd
    st.session_state.items_df = pd.DataFrame(columns=["Popis položky", "Cena"])
if 'form_reset_id' not in st.session_state: st.session_state.form_reset_id = 0
if 'ares_data' not in st.session_state: st.session_state.ares_data = {"jmeno": "", "adresa": "", "ico": "", "dic": ""}

def reset_forms():
    st.session_state.form_reset_id += 1
    st.session_state.ares_data = {"jmeno": "", "adresa": "", "ico": "", "dic": ""}
    if 'items_df' in st.session_state:
        import pandas as pd
        st.session_state.items_df = pd.DataFrame(columns=["Popis položky", "Cena"])

# --- 6. AUTHENTICATION & LOGIN ---
if not st.session_state.user_id:
    st.markdown("<div class='auth-container'><h2 style='text-align:center'>🔐 Fakturace Online</h2>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Přihlášení", "Registrace"])
    with t1:
        with st.form("l"):
            u = st.text_input("Uživatelské jméno")
            p = st.text_input("Heslo", type="password")
            if st.form_submit_button("Přihlásit"):
                res = run_query("SELECT * FROM users WHERE username=? AND password_hash=?", (u, hash_password(p)), single=True)
                if res:
                    st.session_state.user_id = res['id']
                    st.session_state.username = res['username']
                    # Validace licence při loginu
                    if res['license_key']:
                        valid, msg, exp = check_license_online(res['license_key'])
                        st.session_state.license_active = valid
                    else: st.session_state.license_active = False
                    st.rerun()
                else: st.error("Chyba přihlášení")
    with t2:
        with st.form("r"):
            nu = st.text_input("Jméno")
            np = st.text_input("Heslo", type="password")
            if st.form_submit_button("Vytvořit účet"):
                try: 
                    run_command("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)", (nu, hash_password(np), datetime.now().isoformat()))
                    st.success("Hotovo. Přihlašte se.")
                except: st.error("Jméno obsazeno.")
    st.info("⚠️ DEMO verze (data se mohou smazat).")
    st.stop()

# --- 7. HLAVNÍ APLIKACE ---
uid = st.session_state.user_id
is_active = st.session_state.get('license_active', False)

st.sidebar.markdown(f"<div class='user-label'>👤 <b>{st.session_state.username}</b><br><small>{'✅ PRO Verze' if is_active else '🔒 Uzamčeno'}</small></div>", unsafe_allow_html=True)
if st.sidebar.button("Odhlásit"): st.session_state.user_id = None; st.rerun()

# Logika menu podle licence
if is_active:
    menu = st.sidebar.radio("Menu", ["Faktury", "Klienti", "Kategorie", "Nastavení"], label_visibility="collapsed")
else:
    menu = st.sidebar.radio("Menu", ["Nastavení", "Zamčeno"], label_visibility="collapsed")

if menu == "Zamčeno":
    st.markdown("<div class='locked-msg'><h1>🔒 Aplikace je uzamčena</h1><p>Pro odemknutí funkcí zadejte platný licenční klíč v sekci <b>Nastavení</b>.</p></div>", unsafe_allow_html=True)

elif menu == "Nastavení":
    st.header("⚙️ Nastavení")
    c = get_my_details(uid)
    
    # 1. SEKCE LICENCE (Nejdůležitější pro neaktivní)
    with st.expander("🔑 Aktivace Licence", expanded=not is_active):
        u_row = run_query("SELECT license_key, license_valid_until FROM users WHERE id=?", (uid,), single=True)
        lk = st.text_input("Licenční klíč", value=u_row['license_key'] if u_row['license_key'] else "")
        if st.button("Ověřit a Aktivovat"):
            valid, msg, exp = check_license_online(lk)
            if valid:
                run_command("UPDATE users SET license_key=?, license_valid_until=? WHERE id=?", (lk, exp, uid))
                st.session_state.license_active = True
                st.success(f"Aktivováno! Platnost do: {exp}"); st.rerun()
            else: st.error(msg)

    # Dalsi sekce jen pokud je aktivni, nebo aby videl co dostane? Nechame pristupne nastaveni vzdy.
    with st.expander("🏢 Firemní údaje"):
        with st.form("f1"):
            n=st.text_input("Název", c.get('nazev','')); a=st.text_area("Adresa", c.get('adresa',''))
            c1,c2=st.columns(2); i=c1.text_input("IČO", c.get('ico','')); d=c2.text_input("DIČ", c.get('dic',''))
            c3,c4=st.columns(2); e=c3.text_input("Email", c.get('email','')); t=c4.text_input("Tel", c.get('telefon',''))
            if st.form_submit_button("Uložit"):
                if c.get('id'): run_command("UPDATE nastaveni SET nazev=?, adresa=?, ico=?, dic=?, email=?, telefon=? WHERE id=? AND user_id=?", (n,a,i,d,e,t,c['id'], uid))
                else: run_command("INSERT INTO nastaveni (user_id, nazev, adresa, ico, dic, email, telefon) VALUES (?,?,?,?,?,?,?)", (uid,n,a,i,d,e,t))
                st.rerun()
    
    with st.expander("🏦 Banka"):
        with st.form("f2"):
            b=st.text_input("Banka", c.get('banka','')); u=st.text_input("Účet", c.get('ucet','')); ib=st.text_input("IBAN", c.get('iban',''))
            if st.form_submit_button("Uložit"): run_command("UPDATE nastaveni SET banka=?, ucet=?, iban=? WHERE id=? AND user_id=?", (b,u,ib,c.get('id',0), uid)); st.rerun()

    # VRÁCENO: Upozornění na emaily
    with st.expander("🔔 Upozornění (SMTP)"):
        act = st.toggle("Aktivní", value=bool(c.get('notify_active', 0)))
        ne = st.text_input("Email pro notifikace", value=c.get('notify_email',''))
        ss = st.text_input("SMTP Server", value=c.get('smtp_server','smtp.gmail.com'))
        sp = st.number_input("SMTP Port", value=c.get('smtp_port', 587))
        se = st.text_input("SMTP Login", value=c.get('smtp_email',''))
        sw = st.text_input("SMTP Heslo", value=c.get('smtp_password',''), type="password")
        if st.button("Uložit SMTP"):
            run_command("UPDATE nastaveni SET notify_active=?, notify_email=?, smtp_server=?, smtp_port=?, smtp_email=?, smtp_password=? WHERE id=? AND user_id=?", (int(act), ne, ss, sp, se, sw, c.get('id',0), uid))
            st.success("Uloženo")
        if st.button("Test Emailu"):
            ok, m = send_email_alert("Test", "Test OK", get_my_details(uid))
            st.toast("Odesláno") if ok else st.error(m)

    # VRÁCENO: Zálohování
    with st.expander("💾 Záloha dat"):
        import pandas as pd
        def get_json():
            data = {}
            for t in ['nastaveni', 'klienti', 'kategorie', 'faktury', 'faktura_polozky']:
                # DULEZITE: Export jen pro aktualniho uzivatele
                q = f"SELECT * FROM {t} WHERE user_id=?" if 'user_id' in [i[1] for i in get_db().execute(f"PRAGMA table_info({t})")] else f"SELECT * FROM {t}"
                if t == 'faktura_polozky': # Polozky nemaji user_id, filtrujeme pres faktury
                    q = "SELECT fp.* FROM faktura_polozky fp JOIN faktury f ON fp.faktura_id = f.id WHERE f.user_id = ?"
                
                df = pd.read_sql(q, get_db(), params=(uid,))
                if t == 'kategorie' and 'logo_blob' in df.columns: df['logo_blob'] = df['logo_blob'].apply(lambda x: base64.b64encode(x).decode('utf-8') if x else None)
                data[t] = df.to_dict(orient='records')
            return json.dumps(data, default=str)
        
        st.download_button("Stáhnout Mojí Zálohu", get_json(), f"zaloha_{st.session_state.username}.json", "application/json")
        upl = st.file_uploader("Obnovit ze zálohy", type="json")
        if upl and st.button("Nahrát data"):
            d = json.load(upl)
            conn = get_db(); cur = conn.cursor()
            # Smazat stavajici data uzivatele
            cur.execute("DELETE FROM faktura_polozky WHERE faktura_id IN (SELECT id FROM faktury WHERE user_id=?)", (uid,))
            cur.execute("DELETE FROM faktury WHERE user_id=?", (uid,))
            cur.execute("DELETE FROM klienti WHERE user_id=?", (uid,))
            cur.execute("DELETE FROM kategorie WHERE user_id=?", (uid,))
            cur.execute("DELETE FROM nastaveni WHERE user_id=?", (uid,))
            
            # Import (vynutit user_id)
            for t, rows in d.items():
                if not rows: continue
                if t == 'faktura_polozky': # Polozky nemaji user_id
                    for r in rows: cur.execute("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (r['faktura_id'], r['nazev'], r['cena']))
                elif t in ['nastaveni', 'klienti', 'kategorie', 'faktury']:
                    for r in rows:
                        r['user_id'] = uid # Vynutit moje ID
                        if t == 'kategorie' and r.get('logo_blob'): r['logo_blob'] = base64.b64decode(r['logo_blob'])
                        qs = f"INSERT INTO {t} ({','.join(r.keys())}) VALUES ({','.join(['?']*len(r))})"
                        cur.execute(qs, list(r.values()))
            conn.commit(); conn.close()
            st.success("Data obnovena!"); st.rerun()

elif menu == "Klienti" and is_active:
    st.header("👥 Klienti")
    rid = st.session_state.form_reset_id
    with st.expander("➕ Přidat", expanded=True):
        c1,c2 = st.columns([3,1]); ico = c1.text_input("IČO", key=f"s_{rid}")
        if c2.button("ARES", key=f"b_{rid}"): st.session_state.ares_data = get_ares_data(ico) or {}
        ad = st.session_state.ares_data
        with st.form(f"cf_{rid}", clear_on_submit=True):
            j=st.text_input("Jméno", ad.get('jmeno','')); a=st.text_area("Adresa", ad.get('adresa',''))
            k1,k2=st.columns(2); i=k1.text_input("IČ", ad.get('ico','')); d=k2.text_input("DIČ", ad.get('dic',''))
            if st.form_submit_button("Uložit"): run_command("INSERT INTO klienti (user_id, jmeno, adresa, ico, dic) VALUES (?,?,?,?,?)", (uid,j,a,i,d)); reset_forms(); st.rerun()
    for r in run_query("SELECT * FROM klienti WHERE user_id=?", (uid,)):
        with st.expander(f"{r['jmeno']}"):
            if st.button("Smazat", key=f"d_{r['id']}"): run_command("DELETE FROM klienti WHERE id=? AND user_id=?", (r['id'], uid)); st.rerun()

elif menu == "Kategorie" and is_active:
    st.header("🏷️ Kategorie")
    rid = st.session_state.form_reset_id
    with st.expander("➕ Nová", expanded=False):
        with st.form(f"kf_{rid}"):
            n=st.text_input("Název"); p=st.text_input("Prefix"); s=st.number_input("Start", 1); c=st.color_picker("Barva", "#3498db")
            l=st.file_uploader("Logo", type=['png','jpg'])
            if st.form_submit_button("Uložit"): run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva, logo_blob) VALUES (?,?,?,?,?,?)", (uid,n,p,s,c,process_logo(l))); reset_forms(); st.rerun()
    for r in run_query("SELECT * FROM kategorie WHERE user_id=?", (uid,)):
        with st.expander(f"{r['nazev']}"):
            if st.button("Smazat", key=f"dk_{r['id']}"): run_command("DELETE FROM kategorie WHERE id=? AND user_id=?", (r['id'], uid)); st.rerun()

elif menu == "Faktury" and is_active:
    import pandas as pd
    st.header("📊 Přehled")
    # Alerts
    alerts = check_due_invoices(uid)
    if alerts: st.warning(f"Po splatnosti: {len(alerts)} faktur")
    
    cy = datetime.now().year
    sc = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND strftime('%Y', datum_vystaveni) = ?", (uid, str(cy)), True)[0] or 0
    su = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno = 0 AND strftime('%Y', datum_vystaveni) = ?", (uid, str(cy)), True)[0] or 0
    c1, c2 = st.columns(2)
    c1.markdown(f"<div class='stat-box'><div class='stat-num'>{sc:,.0f} Kč</div><div class='stat-sub'>Fakturováno {cy}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='stat-box'><div class='stat-err'>{su:,.0f} Kč</div><div class='stat-sub'>Neuhrazeno</div></div>", unsafe_allow_html=True)
    st.divider()

    rid = st.session_state.form_reset_id
    with st.expander("➕ Nová faktura"):
        kli = pd.read_sql("SELECT id, jmeno FROM klienti WHERE user_id=?", get_db(), params=(uid,))
        kat = pd.read_sql("SELECT id, nazev FROM kategorie WHERE user_id=?", get_db(), params=(uid,))
        if kli.empty or kat.empty: st.warning("Chybí data (klienti/kategorie)")
        else:
            k1,k2 = st.columns(2); sk = k1.selectbox("Klient", kli['jmeno'], key=f"sk_{rid}"); sc = k2.selectbox("Kategorie", kat['nazev'], key=f"sc_{rid}")
            kid = int(kli[kli['jmeno']==sk]['id'].values[0]); cid = int(kat[kat['nazev']==sc]['id'].values[0])
            _, full, _ = get_next_invoice_number(cid, uid); st.info(f"Číslo: **{full}**")
            k3,k4=st.columns(2); obj=k3.text_input("Objednávka", key=f"o_{rid}"); mp=k4.text_input("Popis", key=f"p_{rid}")
            d1,d2,d3=st.columns(3); dv=d1.date_input("Vystavení", date.today(), key=f"d1_{rid}"); du=d2.date_input("DUZP", date.today(), key=f"d2_{rid}"); ds=d3.date_input("Splatnost", date.today()+timedelta(14), key=f"d3_{rid}")
            zp = st.selectbox("Úhrada", ["Prevodem", "Hotove", "Kartou"], key=f"z_{rid}"); uv = st.text_input("Text", "Fakturujeme Vám:", key=f"t_{rid}")
            ed = st.data_editor(st.session_state.items_df, num_rows="dynamic", use_container_width=True, key=f"ed_{rid}")
            tot = float(pd.to_numeric(ed["Cena"], errors='coerce').fillna(0).sum())
            st.markdown(f"### Celkem: {tot:,.2f} Kč")
            if st.button("Vystavit", type="primary", key=f"b_{rid}"):
                _, f, _ = get_next_invoice_number(cid, uid)
                fid = run_command("INSERT INTO faktury (user_id, cislo, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_duzp, datum_splatnosti, castka_celkem, zpusob_uhrady, variabilni_symbol, cislo_objednavky, uvodni_text, uhrazeno, muj_popis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (uid, 0, f, kid, cid, dv, du, ds, tot, zp, re.sub(r"\D", "", f), obj, uv, 0, mp))
                for _, r in ed.iterrows():
                    if r["Popis položky"]: run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (fid, r["Popis položky"], float(r["Cena"])))
                run_command("UPDATE kategorie SET aktualni_cislo = aktualni_cislo + 1 WHERE id = ? AND user_id = ?", (cid, uid)); st.success("Hotovo"); reset_forms(); st.rerun()

    st.divider()
    df = pd.read_sql("SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id = k.id WHERE f.user_id=? ORDER BY f.id DESC LIMIT 50", get_db(), params=(uid,))
    for _, r in df.iterrows():
        icon = "✅" if r['uhrazeno'] else "⏳"
        with st.expander(f"{r['id']}. {icon} {r['cislo_full']} | {format_date(r['datum_vystaveni'])} | {r['jmeno']} | {r['castka_celkem']:,.0f} Kč"):
            c1,c2 = st.columns([1,1])
            if r['uhrazeno']:
                if c1.button("Zrušit úhradu", key=f"u0_{r['id']}"): run_command("UPDATE faktury SET uhrazeno=0 WHERE id=? AND user_id=?", (r['id'], uid)); st.rerun()
            else:
                if c1.button("Zaplaceno", key=f"u1_{r['id']}"): run_command("UPDATE faktury SET uhrazeno=1 WHERE id=? AND user_id=?", (r['id'], uid)); st.rerun()
            pdf = generate_pdf(r['id'], uid)
            if isinstance(pdf, bytes): c2.download_button("⬇️ Stáhnout PDF", pdf, f"{r['cislo_full']}.pdf", "application/pdf")
            else: c2.error(f"Chyba: {pdf}")
            if st.button("Smazat", key=f"del_{r['id']}"): run_command("DELETE FROM faktury WHERE id=? AND user_id=?", (r['id'], uid)); run_command("DELETE FROM faktura_polozky WHERE faktura_id=?", (r['id'],)); st.rerun()
