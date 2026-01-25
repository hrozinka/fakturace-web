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

# --- 0. NASTAVENÍ SYSTÉMU ---
SYSTEM_EMAIL = {
    "enabled": True, 
    "server": "smtp.seznam.cz",
    "port": 465,
    "email": "jsem@michalkochtik.cz",
    "password": "Miki+420"
}

# --- 1. KONFIGURACE A CSS ---
st.set_page_config(page_title="Fakturační Systém", page_icon="🧾", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #262730 !important; border: 1px solid #4f4f4f !important; color: #ffffff !important;
    }
    div[data-testid="stExpander"] { background-color: #262730 !important; border: 1px solid #4f4f4f; border-radius: 8px; margin-bottom: 8px; }
    div[data-testid="stExpander"] details summary { color: #ffffff !important; }
    
    /* STATS BOXY */
    .mini-stat-container { display: flex; gap: 10px; margin-bottom: 20px; margin-top: 10px; justify-content: space-between; }
    .mini-stat-box { background-color: #1f2937; border: 1px solid #374151; border-radius: 8px; padding: 15px; text-align: center; width: 100%; }
    .mini-label { font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #9ca3af; margin-bottom: 5px; }
    .mini-val-green { font-size: 22px; font-weight: 700; color: #6ee7b7; }
    .mini-val-gray { font-size: 22px; font-weight: 700; color: #d1d5db; }
    .mini-val-red { font-size: 22px; font-weight: 700; color: #f87171; }
    
    /* MENŠÍ BOXY PRO FILTR */
    .small-box { padding: 8px !important; }
    .small-val { font-size: 16px !important; }

    .auth-container { max-width: 500px; margin: 0 auto; padding: 40px 20px; background: #1f2937; border-radius: 10px; border: 1px solid #374151; }
    .promo-box { border: 2px solid #eab308; background-color: #422006; padding: 15px; border-radius: 10px; margin-bottom: 20px; text-align: center; }
    .promo-link { color: #facc15; font-weight: bold; font-size: 18px; text-decoration: none; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABÁZE ---
DB_FILE = 'fakturace_v11_pro.db'

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
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
        c.execute("INSERT OR IGNORE INTO users (username, password_hash, role, full_name, email, phone) VALUES (?, ?, ?, ?, ?, ?)", 
                  ("admin", adm_pass, "admin", "Super Admin", "admin@system.cz", "000000000"))
    except: pass

    conn.commit()
    conn.close()

if 'db_inited' not in st.session_state:
    init_db()
    st.session_state.db_inited = True

# --- 3. POMOCNÉ FUNKCE ---
def run_query(sql, params=(), single=False):
    conn = get_db(); c = conn.cursor(); c.execute(sql, params)
    res = c.fetchone() if single else c.fetchall(); conn.close(); return res

def run_command(sql, params=()):
    conn = get_db(); c = conn.cursor(); c.execute(sql, params); conn.commit(); lid = c.lastrowid; conn.close(); return lid

def hash_password(password): return hashlib.sha256(str.encode(password)).hexdigest()

def send_welcome_email(to_email, full_name):
    if not SYSTEM_EMAIL["enabled"]: return False
    try:
        msg = MIMEMultipart()
        msg['From'] = SYSTEM_EMAIL["email"]
        msg['To'] = to_email
        msg['Subject'] = "Vítejte v MojeFaktury!"
        body = f"Dobrý den, {full_name},\n\nděkujeme za registraci. Váš účet FREE je aktivní."
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP_SSL(SYSTEM_EMAIL["server"], SYSTEM_EMAIL["port"])
        server.login(SYSTEM_EMAIL["email"], SYSTEM_EMAIL["password"])
        server.sendmail(SYSTEM_EMAIL["email"], to_email, msg.as_string())
        server.quit()
        return True
    except: return False

def check_license_online(key):
    try:
        # !!! ZDE UPRAVTE URL NA SVOU 'RAW' ADRESU GISTU !!!
        # Příklad: https://gist.githubusercontent.com/UZIVATEL/HASH/raw/licence.json
        url = f"https://gist.githubusercontent.com/hrozinka/6cd3ef1eea1e6d7dc7b188bdbeb84235/raw/dbd8a4bb338c809de0af148e4adbc859a495af7f/licence.json?t={int(datetime.now().timestamp())}"
        
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            data = r.json()
            if key in data:
                # ZDE SE NAČÍTÁ DATUM PŘÍMO Z JSONU (hodnota klíče)
                exp_date = data[key]
                return True, "Aktivní", exp_date
    except: pass
    return False, "Neplatný klíč", None

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

def remove_accents(input_str):
    if not input_str: return ""
    return "".join([c for c in unicodedata.normalize('NFKD', str(input_str)) if not unicodedata.combining(c)])

def format_date(d_str):
    if not d_str: return ""
    try: return d_str.strftime('%d.%m.%Y') if isinstance(d_str, (datetime, date)) else datetime.strptime(str(d_str), '%Y-%m-%d').strftime('%d.%m.%Y')
    except: return str(d_str)

def get_next_invoice_number(kat_id, uid):
    res = run_query("SELECT prefix, aktualni_cislo FROM kategorie WHERE id = ? AND user_id = ?", (kat_id, uid), single=True)
    return (res['aktualni_cislo'], str(res['aktualni_cislo']), res['prefix']) if res else (1, "1", "")

# --- 4. PDF GENERATOR ---
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
            self.set_text_color(50, 50, 50); self.cell(0, 10, 'FAKTURA', 0, 1, 'R'); self.ln(5)

    try:
        data = run_query("SELECT f.*, k.jmeno as k_jmeno, k.adresa as k_adresa, k.ico as k_ico, k.dic as k_dic, kat.barva, kat.logo_blob FROM faktury f JOIN klienti k ON f.klient_id = k.id JOIN kategorie kat ON f.kategorie_id = kat.id WHERE f.id = ? AND f.user_id = ?", (faktura_id, uid), single=True)
        if not data: return "Faktura nenalezena"
        polozky = run_query("SELECT * FROM faktura_polozky WHERE faktura_id = ?", (faktura_id,))
        moje = run_query("SELECT * FROM nastaveni WHERE user_id = ? LIMIT 1", (uid,), single=True) or {}

        pdf = PDF(); pdf.add_page()
        def stxt(t): return str(t) if getattr(pdf, 'font_ok', False) else remove_accents(str(t) if t else "")
        fname = 'ArialCS' if getattr(pdf, 'font_ok', False) else 'Arial'
        pdf.set_font(fname, '', 10)

        if data['logo_blob']:
            try:
                fn = f"t_{faktura_id}.png"
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
        pdf.set_font(fname, '', 14); pdf.cell(100, 8, stxt(f"Faktura č.: {data['cislo_full']}"), 0, 1)
        pdf.set_font(fname, '', 10)
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
        pdf.ln(25); pdf.set_font(fname, '', 10); pdf.set_text_color(50); pdf.set_x(120); pdf.cell(70, 0, "", 'T'); pdf.ln(2); pdf.set_x(120); pdf.cell(70, 5, stxt("Podpis a razítko dodavatele"), 0, 1, 'C')

        if is_pro and moje.get('iban'):
            try:
                qr_str = f"SPD*1.0*ACC:{moje['iban'].replace(' ','').upper()}*AM:{data['castka_celkem']:.2f}*CC:CZK*MSG:{stxt('Faktura '+str(data['cislo_full']))}"
                img = qrcode.make(qr_str); img.save(f"q_{faktura_id}.png"); pdf.image(f"q_{faktura_id}.png", x=10, y=pdf.get_y()-15, w=35); os.remove(f"q_{faktura_id}.png")
            except: pass

        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except Exception as e: return f"ERROR: {str(e)}"

# --- 5. SESSION ---
if 'user_id' not in st.session_state: st.session_state.user_id = None
if 'role' not in st.session_state: st.session_state.role = 'user'
if 'is_pro' not in st.session_state: st.session_state.is_pro = False
if 'full_name' not in st.session_state: st.session_state.full_name = ""
if 'user_email' not in st.session_state: st.session_state.user_email = ""
if 'user_phone' not in st.session_state: st.session_state.user_phone = ""
if 'items_df' not in st.session_state: 
    import pandas as pd
    st.session_state.items_df = pd.DataFrame(columns=["Popis položky", "Cena"])
if 'form_reset_id' not in st.session_state: st.session_state.form_reset_id = 0
if 'ares_data' not in st.session_state: st.session_state.ares_data = {"jmeno": "", "adresa": "", "ico": "", "dic": ""}

def reset_forms():
    st.session_state.form_reset_id += 1
    st.session_state.ares_data = {"jmeno": "", "adresa": "", "ico": "", "dic": ""}
    import pandas as pd
    st.session_state.items_df = pd.DataFrame(columns=["Popis položky", "Cena"])

# --- 6. AUTH ---
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
                    st.session_state.user_phone = res['phone']
                    st.session_state.is_pro = True if res['license_key'] else False
                    run_command("UPDATE users SET last_active = ? WHERE id = ?", (datetime.now().isoformat(), res['id']))
                    st.rerun()
                else: st.error("Neplatné údaje.")

    with t2:
        with st.form("reg_form"):
            st.write("Vytvoření nového účtu")
            fn = st.text_input("Jméno")
            ln = st.text_input("Příjmení")
            usr = st.text_input("Uživatelské jméno (login)")
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
                        st.success("Účet vytvořen! Přepněte na záložku Přihlášení.")
                    except: st.error("Uživatel již existuje.")
    st.stop()

# --- 7. APP START ---
uid = st.session_state.user_id
role = st.session_state.role
is_pro = st.session_state.is_pro
full_name_display = st.session_state.full_name if st.session_state.full_name else st.session_state.username

run_command("UPDATE users SET last_active = ? WHERE id = ?", (datetime.now().isoformat(), uid))

st.sidebar.markdown(f"👤 **{full_name_display}**")
st.sidebar.caption(f"{'👑 ADMIN' if role=='admin' else ('⭐ PRO Verze' if is_pro else '🆓 FREE Verze')}")

if st.sidebar.button("Odhlásit"):
    st.session_state.user_id = None
    st.rerun()

# ================= ADMIN =================
if role == 'admin':
    st.header("👑 Admin Panel")
    tabs = st.tabs(["Uživatelé", "Statistiky"])
    
    with tabs[0]:
        users = run_query("SELECT * FROM users WHERE role != 'admin'")
        for u in users:
            label = "🔴"
            if u['last_active']:
                try:
                    last = datetime.fromisoformat(u['last_active'])
                    diff = datetime.now() - last
                    minutes = diff.total_seconds() / 60
                    if minutes <= 30: label = "🟢 ON"
                    elif minutes < 60: label = "0H"
                    else:
                        hours = minutes / 60
                        if hours < 24: label = f"{int(hours)}H"
                        else:
                            days = hours / 24
                            if days < 30: label = f"{int(days)}D"
                            else:
                                months = days / 30
                                if months < 12: label = f"{int(months)}M"
                                else: label = f"{int(years)}R"
                except: label = "?"

            with st.expander(f"{label} | {u['full_name']} | {u['username']}"):
                c1, c2 = st.columns(2)
                c1.write(f"**Email:** {u['email']}")
                c1.write(f"**Telefon:** {u['phone']}")
                cnt_f = run_query("SELECT COUNT(*) FROM faktury WHERE user_id=?", (u['id'],), single=True)
                c1.write(f"**Faktury:** {cnt_f[0] if cnt_f else 0}")
                
                cur_lic = u['license_key'] if u['license_key'] else ""
                new_lic = c2.text_input("Licence", value=cur_lic, key=f"lk_{u['id']}")
                if c2.button("Uložit", key=f"blk_{u['id']}"):
                    run_command("UPDATE users SET license_key=? WHERE id=?", (new_lic, u['id']))
                    st.success("OK"); st.rerun()
                if c2.button("SMAZAT", key=f"del_{u['id']}", type="primary"):
                    run_command("DELETE FROM users WHERE id=?", (u['id'],)); st.rerun()

    with tabs[1]:
        c_u = run_query("SELECT COUNT(*) FROM users")[0][0]
        c_f = run_query("SELECT COUNT(*) FROM faktury")[0][0]
        c_p = run_query("SELECT COUNT(*) FROM users WHERE license_key IS NOT NULL")[0][0]
        k1, k2, k3 = st.columns(3)
        k1.metric("Uživatelé", c_u); k2.metric("PRO Uživatelé", c_p); k3.metric("Faktury", c_f)

# ================= USER =================
else:
    menu = st.sidebar.radio("Menu", ["Faktury", "Klienti", "Kategorie", "Nastavení"], label_visibility="collapsed")
    
    cnt_cli = run_query("SELECT COUNT(*) FROM klienti WHERE user_id=?", (uid,), single=True)[0]
    cnt_inv = run_query("SELECT COUNT(*) FROM faktury WHERE user_id=?", (uid,), single=True)[0]

    if menu == "Nastavení":
        st.header("⚙️ Nastavení")
        if not is_pro:
            st.markdown("""
            <div class='promo-box'>
                <h3>🔓 Přejděte na PRO verzi</h3>
                <p>Neomezené faktury, vlastní kategorie, QR platby.</p>
                <a href='#' class='promo-link'>Koupit licenci</a>
            </div>
            """, unsafe_allow_html=True)
            with st.expander("Mám licenční klíč"):
                lk = st.text_input("Klíč")
                if st.button("Aktivovat"):
                    valid, msg, exp = check_license_online(lk)
                    if valid:
                        run_command("UPDATE users SET license_key=?, license_valid_until=? WHERE id=?", (lk, exp, uid))
                        st.session_state.is_pro = True
                        st.success("Aktivováno!"); st.rerun()
                    else: st.error(msg)
        else: 
            st.success("✅ PRO Verze aktivní")
            with st.expander("🔑 Správa licence"):
                u_data = run_query("SELECT license_key, license_valid_until FROM users WHERE id=?", (uid,), single=True)
                cur_k = u_data['license_key'] if u_data else ""
                valid_until = u_data['license_valid_until'] if u_data and u_data['license_valid_until'] else "Neznámo"
                
                st.info(f"📅 Platnost do: **{format_date(valid_until)}**")
                
                new_k = st.text_input("Změnit klíč", value=cur_k)
                
                c1, c2 = st.columns(2)
                if c1.button("💾 Změnit licenci"):
                     valid, msg, exp = check_license_online(new_k)
                     if valid:
                         run_command("UPDATE users SET license_key=?, license_valid_until=? WHERE id=?", (new_k, exp, uid))
                         st.success("Licence aktualizována"); st.rerun()
                     else: st.error(msg)
                
                if c2.button("🗑️ Deaktivovat (na FREE)", type="primary"):
                    run_command("UPDATE users SET license_key=NULL, license_valid_until=NULL WHERE id=?", (uid,))
                    st.session_state.is_pro = False
                    st.rerun()

        c = run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1", (uid,), single=True) or {}
        def_n = c.get('nazev', st.session_state.full_name)
        def_e = c.get('email', st.session_state.user_email)
        def_p = c.get('telefon', st.session_state.user_phone)

        with st.expander("🏢 Moje Firma", expanded=False):
            with st.form("sets"):
                n=st.text_input("Název / Jméno", def_n); a=st.text_area("Adresa", c.get('adresa',''))
                i=st.text_input("IČO", c.get('ico','')); d=st.text_input("DIČ", c.get('dic',''))
                bn=st.text_input("Banka", c.get('banka','')); uc=st.text_input("Účet", c.get('ucet','')); ib=st.text_input("IBAN", c.get('iban',''))
                em=st.text_input("Email", def_e); ph=st.text_input("Telefon", def_p)
                if st.form_submit_button("Uložit"):
                    if c.get('id'): run_command("UPDATE nastaveni SET nazev=?, adresa=?, ico=?, dic=?, banka=?, ucet=?, iban=?, email=?, telefon=? WHERE id=?", (n,a,i,d,bn,uc,ib,em,ph,c['id']))
                    else: run_command("INSERT INTO nastaveni (user_id, nazev, adresa, ico, dic, banka, ucet, iban, email, telefon) VALUES (?,?,?,?,?,?,?,?,?,?)", (uid,n,a,i,d,bn,uc,ib,em,ph))
                    st.rerun()

        dis = not is_pro
        txt_lock = " (Pouze PRO)" if dis else ""
        
        with st.expander(f"🔔 Upozornění (SMTP){txt_lock}"):
            if dis: st.info("🔒 Tato funkce je dostupná pouze v PRO verzi.")
            act = st.toggle("Aktivní", value=bool(c.get('notify_active', 0)), disabled=dis)
            ne = st.text_input("Notifikační email", value=c.get('notify_email',''), disabled=dis)
            ss = st.text_input("SMTP Server", value=c.get('smtp_server',''), disabled=dis)
            sp = st.number_input("SMTP Port", value=c.get('smtp_port', 587), disabled=dis)
            se = st.text_input("SMTP Login", value=c.get('smtp_email',''), disabled=dis)
            sw = st.text_input("SMTP Heslo", value=c.get('smtp_password',''), type="password", disabled=dis)
            if not dis and st.button("Uložit SMTP"):
                run_command("UPDATE nastaveni SET notify_active=?, notify_email=?, smtp_server=?, smtp_port=?, smtp_email=?, smtp_password=? WHERE id=?", (int(act), ne, ss, sp, se, sw, c.get('id')))
                st.success("Uloženo")

        with st.expander(f"💾 Záloha dat{txt_lock}"):
            if dis: st.info("🔒 Tato funkce je dostupná pouze v PRO verzi.")
            else:
                import pandas as pd
                def get_json():
                    data = {}
                    for t in ['nastaveni', 'klienti', 'kategorie', 'faktury', 'faktura_polozky']:
                        conn = get_db(); cols = [i[1] for i in conn.execute(f"PRAGMA table_info({t})")]
                        if 'user_id' in cols: q = f"SELECT * FROM {t} WHERE user_id=?"; params = (uid,)
                        elif t == 'faktura_polozky': q = "SELECT fp.* FROM faktura_polozky fp JOIN faktury f ON fp.faktura_id = f.id WHERE f.user_id = ?"; params = (uid,)
                        else: q = f"SELECT * FROM {t}"; params = ()
                        df = pd.read_sql(q, conn, params=params); conn.close()
                        if t == 'kategorie' and 'logo_blob' in df.columns: df['logo_blob'] = df['logo_blob'].apply(lambda x: base64.b64encode(x).decode('utf-8') if x else None)
                        data[t] = df.to_dict(orient='records')
                    return json.dumps(data, default=str)
                st.download_button("Stáhnout Zálohu", get_json(), "zaloha.json", "application/json")
                upl = st.file_uploader("Nahrát zálohu", type="json")
                if upl and st.button("Obnovit"):
                    st.success("Hotovo")

    elif menu == "Klienti":
        st.header("👥 Klienti")
        if not is_pro and cnt_cli >= 3: st.error(f"🔒 FREE Limit: {cnt_cli}/3 klientů.")
        else:
            rid = st.session_state.form_reset_id
            with st.expander("➕ Přidat"):
                c1,c2 = st.columns([3,1]); ico = c1.text_input("IČO", key=f"s_{rid}")
                if c2.button("ARES", key=f"b_{rid}"): st.session_state.ares_data = get_ares_data(ico) or {}
                ad = st.session_state.ares_data
                with st.form(f"cf_{rid}", clear_on_submit=True):
                    j=st.text_input("Jméno", ad.get('jmeno','')); a=st.text_area("Adresa", ad.get('adresa',''))
                    k1,k2=st.columns(2); i=k1.text_input("IČ", ad.get('ico','')); d=k2.text_input("DIČ", ad.get('dic',''))
                    poz=st.text_area("Poznámka (interní)")
                    if st.form_submit_button("Uložit"): run_command("INSERT INTO klienti (user_id, jmeno, adresa, ico, dic, poznamka) VALUES (?,?,?,?,?,?)", (uid,j,a,i,d,poz)); reset_forms(); st.rerun()
        
        for r in run_query("SELECT * FROM klienti WHERE user_id=?", (uid,)):
            with st.expander(r['jmeno']):
                if r['poznamka']: st.info(f"ℹ️ {r['poznamka']}")
                
                # UPDATE CLIENT
                k_edit_key = f"k_edit_{r['id']}"
                if k_edit_key not in st.session_state: st.session_state[k_edit_key] = False
                
                c1, c2 = st.columns(2)
                if c1.button("✏️ Upravit", key=f"bek_{r['id']}"): st.session_state[k_edit_key] = True; st.rerun()
                if c2.button("Smazat", key=f"delc_{r['id']}"): run_command("DELETE FROM klienti WHERE id=?", (r['id'],)); st.rerun()
                
                if st.session_state[k_edit_key]:
                    with st.form(f"fedk_{r['id']}"):
                        ej=st.text_input("Jméno", r['jmeno']); ea=st.text_area("Adresa", r['adresa'])
                        ek1,ek2=st.columns(2); ei=ek1.text_input("IČ", r['ico']); ed=ek2.text_input("DIČ", r['dic'])
                        epoz=st.text_area("Poznámka", r['poznamka'] or "")
                        if st.form_submit_button("Uložit změny"):
                            run_command("UPDATE klienti SET jmeno=?, adresa=?, ico=?, dic=?, poznamka=? WHERE id=?", (ej,ea,ei,ed,epoz,r['id']))
                            st.session_state[k_edit_key] = False; st.rerun()

    elif menu == "Kategorie":
        st.header("🏷️ Kategorie")
        if not is_pro:
            st.warning("🔒 Vlastní kategorie jsou dostupné pouze v PRO verzi.")
            chk = run_query("SELECT * FROM kategorie WHERE user_id=? AND nazev='Obecná'", (uid,), single=True)
            if not chk: run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva) VALUES (?, ?, ?, ?, ?)", (uid, "Obecná", "FV", 1, "#000000"))
        else:
            rid = st.session_state.form_reset_id
            with st.expander("➕ Nová kategorie"):
                with st.form(f"kf_{rid}"):
                    n=st.text_input("Název"); p=st.text_input("Prefix"); s=st.number_input("Start", 1); c=st.color_picker("Barva", "#3498db")
                    l=st.file_uploader("Logo", type=['png','jpg'])
                    if st.form_submit_button("Uložit"): run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva, logo_blob) VALUES (?,?,?,?,?,?)", (uid,n,p,s,c,process_logo(l))); reset_forms(); st.rerun()
        
        for r in run_query("SELECT * FROM kategorie WHERE user_id=?", (uid,)):
            with st.expander(r['nazev']):
                # UPDATE KATEGORIE
                cat_edit_key = f"cat_edit_{r['id']}"
                if cat_edit_key not in st.session_state: st.session_state[cat_edit_key] = False
                
                c1, c2 = st.columns(2)
                if c1.button("✏️ Upravit", key=f"bec_{r['id']}"): st.session_state[cat_edit_key] = True; st.rerun()
                if is_pro and c2.button("Smazat", key=f"dk_{r['id']}"): run_command("DELETE FROM kategorie WHERE id=?", (r['id'],)); st.rerun()
                
                if st.session_state[cat_edit_key]:
                    with st.form(f"fedc_{r['id']}"):
                        en=st.text_input("Název", r['nazev']); ep=st.text_input("Prefix", r['prefix'])
                        es=st.number_input("Aktuální číslo", value=r['aktualni_cislo']); ec=st.color_picker("Barva", r['barva'])
                        if st.form_submit_button("Uložit změny"):
                            run_command("UPDATE kategorie SET nazev=?, prefix=?, aktualni_cislo=?, barva=? WHERE id=?", (en,ep,es,ec,r['id']))
                            st.session_state[cat_edit_key] = False; st.rerun()

    elif menu == "Faktury":
        import pandas as pd
        st.header("📊 Faktury")
        
        # 0. ČÁST: GLOBÁLNÍ STATISTIKY (VŠECHNY) - NAHOŘE
        cy = datetime.now().year
        sc_all = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND strftime('%Y', datum_vystaveni) = ?", (uid, str(cy)), True)[0] or 0
        su_all = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno = 0 AND strftime('%Y', datum_vystaveni) = ?", (uid, str(cy)), True)[0] or 0
        sh_all = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?", (uid,), True)[0] or 0
        
        # OPRAVA: POUŽITÍ PROMĚNNÝCH S _ALL
        st.markdown(f"""
        <div class="mini-stat-container">
            <div class="mini-stat-box"><div class="mini-label">Fakturováno {cy} (VŠE)</div><div class="mini-val-green">{sc_all:,.0f} Kč</div></div>
            <div class="mini-stat-box"><div class="mini-label">Celkem Historie (VŠE)</div><div class="mini-val-gray">{sh_all:,.0f} Kč</div></div>
            <div class="mini-stat-box"><div class="mini-label">Neuhrazeno (VŠE)</div><div class="mini-val-red">{su_all:,.0f} Kč</div></div>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()

        # 1. ČÁST: PŘIDÁNÍ FAKTURY
        if not is_pro and cnt_inv >= 5: st.error(f"🔒 FREE Limit: {cnt_inv}/5 faktur.")
        else:
            rid = st.session_state.form_reset_id
            with st.expander("➕ Nová faktura"):
                kli = pd.read_sql("SELECT id, jmeno FROM klienti WHERE user_id=?", get_db(), params=(uid,))
                kat = pd.read_sql("SELECT id, nazev FROM kategorie WHERE user_id=?", get_db(), params=(uid,))
                
                if not is_pro and kat.empty:
                    run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva) VALUES (?, ?, ?, ?, ?)", (uid, "Obecná", "FV", 1, "#000000"))
                    st.rerun()

                if kli.empty: st.warning("Nejdříve vytvořte Klienta.")
                else:
                    k1,k2 = st.columns(2)
                    sk = k1.selectbox("Klient", kli['jmeno'], key=f"sk_{rid}")
                    
                    if not kat.empty:
                        sc = k2.selectbox("Kategorie", kat['nazev'], key=f"sc_{rid}")
                        cid = int(kat[kat['nazev']==sc]['id'].values[0])
                    else: cid = 0; st.error("Chyba kategorie")

                    kid = int(kli[kli['jmeno']==sk]['id'].values[0])
                    _, full, _ = get_next_invoice_number(cid, uid); st.info(f"Číslo: **{full}**")
                    
                    obj=st.text_input("Objednávka", key=f"o_{rid}"); mp=st.text_input("Popis", key=f"p_{rid}")
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

        # 2. ČÁST: FILTR
        all_clients = run_query("SELECT id, jmeno FROM klienti WHERE user_id=?", (uid,))
        client_opts = ["Všichni"] + [c['jmeno'] for c in all_clients]
        sel_client = st.selectbox("Filtr podle klienta", client_opts)

        # 3. ČÁST: STATISTIKY (FILTROVANÉ - MENŠÍ)
        if sel_client != "Všichni":
            params_base = [uid, sel_client]
            sql_filter = " AND k.jmeno = ?"
            
            q_sc = f"SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id = k.id WHERE f.user_id=? {sql_filter} AND strftime('%Y', f.datum_vystaveni) = ?"
            sc = run_query(q_sc, tuple(params_base + [str(cy)]), True)[0] or 0
            
            q_su = f"SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id = k.id WHERE f.user_id=? {sql_filter} AND f.uhrazeno = 0 AND strftime('%Y', f.datum_vystaveni) = ?"
            su = run_query(q_su, tuple(params_base + [str(cy)]), True)[0] or 0
            
            q_sh = f"SELECT SUM(f.castka_celkem) FROM faktury f JOIN klienti k ON f.klient_id = k.id WHERE f.user_id=? {sql_filter}"
            sh = run_query(q_sh, tuple(params_base), True)[0] or 0
            
            st.markdown(f"""
            <div class="mini-stat-container">
                <div class="mini-stat-box small-box"><div class="mini-label">Fakturováno {cy} ({sel_client})</div><div class="mini-val-green small-val">{sc:,.0f} Kč</div></div>
                <div class="mini-stat-box small-box"><div class="mini-label">Celkem Historie</div><div class="mini-val-gray small-val">{sh:,.0f} Kč</div></div>
                <div class="mini-stat-box small-box"><div class="mini-label">Neuhrazeno</div><div class="mini-val-red small-val">{su:,.0f} Kč</div></div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # 4. ČÁST: LIST FAKTUR
        q = "SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id = k.id WHERE f.user_id=?"
        p = [uid]
        if sel_client != "Všichni":
            q += " AND k.jmeno = ?"
            p.append(sel_client)
        q += " ORDER BY f.id DESC LIMIT 50"
        
        df = pd.read_sql(q, get_db(), params=p)
        
        for _, r in df.iterrows():
            icon = "✅" if r['uhrazeno'] else "⏳"
            with st.expander(f"{icon} {r['cislo_full']} | {r['jmeno']} | {r['castka_celkem']:,.0f} Kč"):
                c1,c2,c3 = st.columns([1,1,2])
                if r['uhrazeno']:
                    if c1.button("Zrušit úhradu", key=f"u0_{r['id']}"): run_command("UPDATE faktury SET uhrazeno=0 WHERE id=? AND user_id=?", (r['id'], uid)); st.rerun()
                else:
                    if c1.button("Zaplaceno", key=f"u1_{r['id']}"): run_command("UPDATE faktury SET uhrazeno=1 WHERE id=? AND user_id=?", (r['id'], uid)); st.rerun()
                
                pdf = generate_pdf(r['id'], uid, is_pro)
                if isinstance(pdf, bytes): c2.download_button("⬇️ PDF", pdf, f"{r['cislo_full']}.pdf", "application/pdf")
                else: c2.error(pdf)

                ekey = f"edit_{r['id']}"
                if ekey not in st.session_state: st.session_state[ekey] = False
                
                if not st.session_state[ekey]:
                    if c3.button("✏️ Upravit", key=f"btn_e_{r['id']}"): st.session_state[ekey] = True; st.rerun()
                else:
                    st.markdown("---")
                    with st.form(f"frm_{r['id']}"):
                        e_obj = st.text_input("Objednávka", value=r['cislo_objednavky'] or "")
                        e_pop = st.text_input("Popis", value=r['muj_popis'] or "")
                        e_date = st.date_input("Splatnost", pd.to_datetime(r['datum_splatnosti']))
                        
                        e_items = pd.read_sql("SELECT nazev as 'Popis položky', cena as 'Cena' FROM faktura_polozky WHERE faktura_id=?", get_db(), params=(r['id'],))
                        e_df = st.data_editor(e_items, num_rows="dynamic", use_container_width=True)
                        
                        if st.form_submit_button("💾 Uložit změny"):
                            ntot = float(pd.to_numeric(e_df["Cena"], errors='coerce').fillna(0).sum())
                            run_command("UPDATE faktury SET cislo_objednavky=?, muj_popis=?, datum_splatnosti=?, castka_celkem=? WHERE id=? AND user_id=?", (e_obj, e_pop, e_date, ntot, r['id'], uid))
                            run_command("DELETE FROM faktura_polozky WHERE faktura_id=?", (r['id'],))
                            for _, ir in e_df.iterrows():
                                if ir["Popis položky"]: run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (r['id'], ir["Popis položky"], float(ir["Cena"])))
                            st.session_state[ekey] = False; st.rerun()
                        
                        if st.form_submit_button("Zrušit"): st.session_state[ekey] = False; st.rerun()

                if st.button("🗑️ Smazat", key=f"del_{r['id']}"):
                    run_command("DELETE FROM faktury WHERE id=? AND user_id=?", (r['id'], uid))
                    run_command("DELETE FROM faktura_polozky WHERE faktura_id=?", (r['id'],))
                    st.rerun()



