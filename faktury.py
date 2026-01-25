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

# --- 1. KONFIGURACE A CSS ---
st.set_page_config(page_title="Fakturační Systém", page_icon="🧾", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #262730 !important; border: 1px solid #4f4f4f !important; color: #ffffff !important;
    }
    div[data-testid="stExpander"] {
        background-color: #262730 !important; border: 1px solid #4f4f4f; border-radius: 8px; margin-bottom: 8px;
    }
    div[data-testid="stExpander"] details summary { color: #ffffff !important; }
    .stat-box { background-color: #1f2937; padding: 15px; border-radius: 12px; text-align: center; border: 1px solid #374151; height: 100%; min-height: 120px; display: flex; flex-direction: column; justify-content: center; }
    .stat-num { font-size: 28px; font-weight: 800; color: #4ade80; margin: 0; }
    .stat-err { font-size: 28px; font-weight: 800; color: #f87171; margin: 0; }
    .mini-stat-container { display: flex; gap: 10px; margin-bottom: 20px; justify-content: space-between; }
    .mini-stat-box { background-color: #111827; border: 1px solid #374151; border-radius: 8px; padding: 10px; text-align: center; width: 100%; }
    .mini-val-green { font-size: 18px; font-weight: 700; color: #6ee7b7; }
    .user-label { background-color: #1f2937; padding: 10px; border-radius: 8px; margin-bottom: 20px; text-align: center; border: 1px solid #374151; }
    </style>
""", unsafe_allow_html=True)

# --- 2. INICIALIZACE STAVU ---
if 'form_reset_id' not in st.session_state: st.session_state.form_reset_id = 0
if 'ares_data' not in st.session_state: st.session_state.ares_data = {"jmeno": "", "adresa": "", "ico": "", "dic": ""}
if 'db_inited' not in st.session_state: st.session_state.db_inited = False

def reset_forms():
    st.session_state.form_reset_id += 1
    st.session_state.ares_data = {"jmeno": "", "adresa": "", "ico": "", "dic": ""}
    if 'items_df' in st.session_state:
        import pandas as pd
        st.session_state.items_df = pd.DataFrame(columns=["Popis položky", "Cena"])

# --- 3. DATABÁZE A CESTY ---
APP_DIR = "." # Pro webovou verzi
DB_FILE = os.path.join(APP_DIR, 'fakturace_v8.db')

def run_command(sql, params=()):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor(); c.execute(sql, params); conn.commit(); return c.lastrowid

def run_query(sql, params=(), single=False):
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row; c = conn.cursor(); c.execute(sql, params)
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
        cols = [("faktury", "muj_popis", "TEXT"), ("nastaveni", "iban", "TEXT"), ("kategorie", "logo_blob", "BLOB"), ("nastaveni", "smtp_server", "TEXT"), ("nastaveni", "smtp_port", "INTEGER"), ("nastaveni", "smtp_email", "TEXT"), ("nastaveni", "smtp_password", "TEXT"), ("nastaveni", "notify_email", "TEXT"), ("nastaveni", "notify_days", "INTEGER"), ("nastaveni", "notify_active", "INTEGER"), ("nastaveni", "license_key", "TEXT"), ("nastaveni", "last_license_check", "TEXT"), ("nastaveni", "license_owner", "TEXT"), ("nastaveni", "license_exp", "TEXT")]
        for tbl, col, dtype in cols:
            try: c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {dtype}")
            except: pass
        conn.commit()

if not st.session_state.db_inited: init_db(); st.session_state.db_inited = True

# --- 4. FUNKCE ---
def get_my_details():
    try: res = run_query("SELECT * FROM nastaveni LIMIT 1", single=True); return dict(res) if res else {}
    except: return {}

def format_date(d_str):
    if not d_str: return ""
    try: return d_str.strftime('%d.%m.%Y') if isinstance(d_str, (datetime, date)) else datetime.strptime(str(d_str), '%Y-%m-%d').strftime('%d.%m.%Y')
    except: return str(d_str)

def get_ares_data(ico):
    import requests, urllib3; urllib3.disable_warnings()
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
    from PIL import Image; 
    if not uploaded_file: return None
    try:
        img = Image.open(uploaded_file); buf = io.BytesIO(); img.save(buf, format='PNG'); return buf.getvalue()
    except: return None

def get_next_invoice_number(kat_id):
    try: kat_id = int(kat_id)
    except: return 0, "Chyba", ""
    res = run_query("SELECT prefix, aktualni_cislo FROM kategorie WHERE id = ?", (kat_id,), single=True)
    return (res['aktualni_cislo'], str(res['aktualni_cislo']), res['prefix']) if res else (0, "Neznámá", "")

def remove_accents(input_str):
    if not input_str: return ""
    return "".join([c for c in unicodedata.normalize('NFKD', str(input_str)) if not unicodedata.combining(c)])

def generate_pdf(faktura_id):
    from fpdf import FPDF
    import qrcode

    class PDF(FPDF):
        def header(self):
            # OPRAVA PRO WEB: Hledáme font ve složce aplikace, ne ve Windows
            font_name = 'Arial'
            self.font_ok = False
            
            # Zkusíme najít arial.ttf v aktuální složce (musíte ho nahrát na GitHub!)
            if os.path.exists("arial.ttf"):
                try:
                    self.add_font('ArialCS', '', 'arial.ttf', uni=True)
                    self.add_font('ArialCS', 'B', 'arial.ttf', uni=True) # Pro zjednodušení používáme stejný soubor
                    self.set_font('ArialCS', 'B', 24)
                    self.font_ok = True
                    font_name = 'ArialCS'
                except: pass
            
            if not self.font_ok:
                self.set_font('Arial', 'B', 24) # Fallback na standardní font (bez háčků)
                
            self.set_text_color(50, 50, 50)
            self.cell(0, 10, 'FAKTURA', 0, 1, 'R'); self.ln(5)

    try:
        data = run_query("SELECT f.*, k.jmeno as k_jmeno, k.adresa as k_adresa, k.ico as k_ico, k.dic as k_dic, kat.barva, kat.logo_blob FROM faktury f JOIN klienti k ON f.klient_id = k.id JOIN kategorie kat ON f.kategorie_id = kat.id WHERE f.id = ?", (faktura_id,), single=True)
        if not data: return None
        polozky = run_query("SELECT * FROM faktura_polozky WHERE faktura_id = ?", (faktura_id,))
        moje = get_my_details()

        pdf = PDF(); pdf.add_page()
        
        # Funkce pro bezpečný text (pokud nemáme český font, odstraníme diakritiku)
        def stxt(t):
            t = str(t) if t else ""
            return t if getattr(pdf, 'font_ok', False) else remove_accents(t)
        
        fname = 'ArialCS' if getattr(pdf, 'font_ok', False) else 'Arial'
        pdf.set_font(fname, '', 10)

        if data['logo_blob']:
            try:
                fn = f"t_{faktura_id}.png"; 
                with open(fn, "wb") as f: f.write(data['logo_blob'])
                pdf.image(fn, x=10, y=10, w=30); os.remove(fn)
            except: pass

        try:
            c = data['barva'].lstrip('#'); r, g, b = tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
            fr, fg, fb = int(r+(255-r)*0.9), int(g+(255-g)*0.9), int(b+(255-b)*0.9)
        except: r,g,b=100,100,100; fr,fg,fb=240,240,240

        pdf.set_text_color(100); pdf.set_y(40)
        pdf.cell(95, 5, stxt("DODAVATEL:"), 0, 0); pdf.cell(95, 5, stxt("ODBĚRATEL:"), 0, 1)
        pdf.set_text_color(0); y = pdf.get_y(); pdf.set_font(fname, '', 12); pdf.cell(95, 5, stxt(moje.get('nazev','')), 0, 1)
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
        
        pdf.ln(15); 
        if data['uvodni_text']: pdf.set_font(fname, '', 10); pdf.multi_cell(190, 5, stxt(data['uvodni_text']), 0, 'L'); pdf.ln(5)
        
        pdf.set_fill_color(240); pdf.cell(140, 8, stxt(" POLOŽKA / POPIS"), 1, 0, 'L', fill=True); pdf.cell(50, 8, stxt("CENA "), 1, 1, 'R', fill=True); pdf.ln(8)
        for item in polozky:
            xb, yb = pdf.get_x(), pdf.get_y(); pdf.multi_cell(140, 8, stxt(item['nazev']), 0, 'L')
            pdf.set_xy(xb + 140, yb); pdf.cell(50, 8, stxt(f"{item['cena']:,.2f} Kč").replace(",", " "), 0, 1, 'R')
            pdf.set_xy(10, max(pdf.get_y(), yb + 8)); pdf.set_draw_color(240); pdf.line(10, pdf.get_y(), 200, pdf.get_y())

        pdf.ln(10); pdf.set_draw_color(r, g, b); pdf.set_fill_color(fr, fg, fb); pdf.set_line_width(0.5)
        bx, by = 110, pdf.get_y(); pdf.rect(bx, by, 90, 14, 'DF'); pdf.set_xy(bx, by + 4)
        pdf.set_font(fname, 'B' if getattr(pdf, 'font_ok', False) else '', 14); pdf.set_text_color(0)
        pdf.cell(40, 6, stxt("CELKEM:"), 0, 0, 'L'); pdf.cell(45, 6, stxt(f"{data['castka_celkem']:,.2f} Kč").replace(",", " "), 0, 1, 'R')
        
        pdf.ln(25); pdf.set_font(fname, '', 10); pdf.set_text_color(50); pdf.set_x(120)
        pdf.cell(70, 0, "", 'T'); pdf.ln(2); pdf.set_x(120); pdf.cell(70, 5, stxt("Podpis a razítko dodavatele"), 0, 1, 'C')
        
        if moje.get('iban'):
            try:
                qr = f"SPD*1.0*ACC:{moje['iban'].replace(' ','').upper()}*AM:{data['castka_celkem']:.2f}*CC:CZK*MSG:{stxt('Faktura '+str(data['cislo_full']))}*X-VS:{str(data['variabilni_symbol'])}"
                img = qrcode.make(qr); img.save(f"q_{faktura_id}.png"); pdf.image(f"q_{faktura_id}.png", x=10, y=pdf.get_y()-15, w=35); os.remove(f"q_{faktura_id}.png")
            except: pass
        
        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except Exception as e: return f"ERROR: {str(e)}"

# --- 5. LICENCE ---
def check_license(key):
    try:
        r = requests.get(f"https://gist.githubusercontent.com/hrozinka/6cd3ef1eea1e6d7dc7b188bdbeb84235/raw/licence.json?t={int(datetime.now().timestamp())}", timeout=5)
        if r.status_code!=200: return False, "Chyba serveru", None, None
        db = r.json()
        if key in db:
            if not db[key].get("active", True): return False, "Zablokováno", None, None
            return True, "OK", db[key].get("note","Uživatel"), db[key].get("exp","2099-12-31")
        return False, "Neplatný klíč", None, None
    except: return False, "Chyba připojení", None, None

def verify_access():
    s = get_my_details(); key = s.get('license_key')
    if not key: return "NO_KEY"
    if s.get('last_license_check') == datetime.now().strftime("%Y-%m-%d"): return True # Cache na 1 den
    valid, msg, owner, exp = check_license(key)
    if valid: run_command("UPDATE nastaveni SET last_license_check=?, license_owner=?, license_exp=? WHERE id=?", (datetime.now().strftime("%Y-%m-%d"), owner, exp, s['id'])); return True
    return msg

# --- 6. START ---
access = verify_access()
if access != True:
    st.markdown("<br><h1 style='text-align:center'>🔒 Aktivace</h1>", unsafe_allow_html=True)
    if access != "NO_KEY": st.error(f"⚠️ {access}")
    k = st.text_input("Licenční klíč"); 
    if st.button("Aktivovat"):
        val, txt, own, exp = check_license(k)
        if val:
            if get_my_details(): run_command("UPDATE nastaveni SET license_key=?, last_license_check=?, license_owner=?, license_exp=? WHERE id=1", (k, datetime.now().strftime("%Y-%m-%d"), own, exp))
            else: run_command("INSERT INTO nastaveni (license_key, last_license_check, license_owner, license_exp) VALUES (?,?,?,?)", (k, datetime.now().strftime("%Y-%m-%d"), own, exp))
            st.rerun()
        else: st.error(txt)
    st.stop()

# --- 7. GUI ---
curr = get_my_details()
st.sidebar.markdown(f"<div class='user-label'>👤 <b>{curr.get('license_owner','User')}</b></div>", unsafe_allow_html=True)
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
            if st.form_submit_button("Uložit"): run_command("UPDATE nastaveni SET banka=?, ucet=?, iban=? WHERE id=?", (b,u,ib,c['id'])); st.rerun()
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
    if st.button("Odhlásit licenci"): run_command("UPDATE nastaveni SET license_key=NULL WHERE id=?", (c['id'],)); st.rerun()

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
    for r in run_query("SELECT * FROM klienti"):
        with st.expander(f"{r['jmeno']}"):
            if st.button("Smazat", key=f"d_{r['id']}"): run_command("DELETE FROM klienti WHERE id=?", (r['id'],)); st.rerun()

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
            if st.button("Smazat", key=f"dk_{r['id']}"): run_command("DELETE FROM kategorie WHERE id=?", (r['id'],)); st.rerun()

elif menu == "Faktury":
    import pandas as pd
    if 'items_df' not in st.session_state: st.session_state.items_df = pd.DataFrame(columns=["Popis položky", "Cena"])
    st.header("📊 Přehled")
    cy = datetime.now().year
    sc = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE strftime('%Y', datum_vystaveni) = ?", (str(cy),), True)[0] or 0
    su = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE uhrazeno = 0 AND strftime('%Y', datum_vystaveni) = ?", (str(cy),), True)[0] or 0
    c1, c2 = st.columns(2)
    c1.markdown(f"<div class='stat-box'><div class='stat-num'>{sc:,.0f} Kč</div><div class='stat-sub'>Fakturováno {cy}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='stat-box'><div class='stat-err'>{su:,.0f} Kč</div><div class='stat-sub'>Neuhrazeno</div></div>", unsafe_allow_html=True)
    st.divider()

    rid = st.session_state.form_reset_id
    with st.expander("➕ Nová faktura"):
        kli = pd.read_sql("SELECT id, jmeno FROM klienti", sqlite3.connect(DB_FILE))
        kat = pd.read_sql("SELECT id, nazev FROM kategorie", sqlite3.connect(DB_FILE))
        if kli.empty or kat.empty: st.warning("Chybí data (klienti/kategorie)")
        else:
            k1,k2 = st.columns(2); sk = k1.selectbox("Klient", kli['jmeno'], key=f"sk_{rid}"); sc = k2.selectbox("Kategorie", kat['nazev'], key=f"sc_{rid}")
            kid = int(kli[kli['jmeno']==sk]['id'].values[0]); cid = int(kat[kat['nazev']==sc]['id'].values[0])
            _, full, _ = get_next_invoice_number(cid); st.info(f"Číslo: **{full}**")
            k3,k4=st.columns(2); obj=k3.text_input("Objednávka", key=f"o_{rid}"); mp=k4.text_input("Popis", key=f"p_{rid}")
            d1,d2,d3=st.columns(3); dv=d1.date_input("Vystavení", date.today(), key=f"d1_{rid}"); du=d2.date_input("DUZP", date.today(), key=f"d2_{rid}"); ds=d3.date_input("Splatnost", date.today()+timedelta(14), key=f"d3_{rid}")
            zp = st.selectbox("Úhrada", ["Prevodem", "Hotove", "Kartou"], key=f"z_{rid}"); uv = st.text_input("Text", "Fakturujeme Vám:", key=f"t_{rid}")
            ed = st.data_editor(st.session_state.items_df, num_rows="dynamic", use_container_width=True, key=f"ed_{rid}")
            tot = float(pd.to_numeric(ed["Cena"], errors='coerce').fillna(0).sum())
            st.markdown(f"### Celkem: {tot:,.2f} Kč")
            if st.button("Vystavit", type="primary", key=f"b_{rid}"):
                _, f, _ = get_next_invoice_number(cid)
                fid = run_command("INSERT INTO faktury (cislo, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_duzp, datum_splatnosti, castka_celkem, zpusob_uhrady, variabilni_symbol, cislo_objednavky, uvodni_text, uhrazeno, muj_popis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (0, f, kid, cid, dv, du, ds, tot, zp, re.sub(r"\D", "", f), obj, uv, 0, mp))
                for _, r in ed.iterrows():
                    if r["Popis položky"]: run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (fid, r["Popis položky"], float(r["Cena"])))
                run_command("UPDATE kategorie SET aktualni_cislo = aktualni_cislo + 1 WHERE id = ?", (cid,)); st.success("Hotovo"); reset_forms(); st.rerun()

    st.divider()
    df = pd.read_sql("SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id = k.id ORDER BY f.id DESC LIMIT 50", sqlite3.connect(DB_FILE))
    for _, r in df.iterrows():
        icon = "✅" if r['uhrazeno'] else "⏳"
        with st.expander(f"{r['id']}. {icon} {r['cislo_full']} | {format_date(r['datum_vystaveni'])} | {r['jmeno']} | {r['castka_celkem']:,.0f} Kč"):
            c1,c2 = st.columns([1,1])
            if r['uhrazeno']:
                if c1.button("Zrušit úhradu", key=f"u0_{r['id']}"): run_command("UPDATE faktury SET uhrazeno=0 WHERE id=?", (r['id'],)); st.rerun()
            else:
                if c1.button("Zaplaceno", key=f"u1_{r['id']}"): run_command("UPDATE faktury SET uhrazeno=1 WHERE id=?", (r['id'],)); st.rerun()
            pdf = generate_pdf(r['id'])
            if isinstance(pdf, bytes): c2.download_button("⬇️ Stáhnout PDF", pdf, f"{r['cislo_full']}.pdf", "application/pdf")
            else: c2.error(f"Chyba PDF: {pdf}")
            if st.button("Smazat", key=f"del_{r['id']}"): run_command("DELETE FROM faktury WHERE id=?", (r['id'],)); run_command("DELETE FROM faktura_polozky WHERE faktura_id=?", (r['id'],)); st.rerun()
