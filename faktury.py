import sys
import streamlit as st
import sqlite3
import os
import json
import re
import hashlib
from datetime import datetime, date, timedelta
import unicodedata
import io
import base64

# --- 1. KONFIGURACE A CSS ---
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
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABÁZE (SQLITE) ---
APP_DIR = "."
DB_FILE = os.path.join(APP_DIR, 'fakturace_multiuser.db')

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Tabulka uživatelů
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT
    )''')
    # Tabulky dat (všechny mají user_id)
    c.execute('''CREATE TABLE IF NOT EXISTS nastaveni (id INTEGER PRIMARY KEY, user_id INTEGER, nazev TEXT, adresa TEXT, ico TEXT, dic TEXT, ucet TEXT, banka TEXT, email TEXT, telefon TEXT, iban TEXT, smtp_server TEXT, smtp_port INTEGER, smtp_email TEXT, smtp_password TEXT, notify_email TEXT, notify_days INTEGER, notify_active INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS klienti (id INTEGER PRIMARY KEY, user_id INTEGER, jmeno TEXT, adresa TEXT, ico TEXT, dic TEXT, email TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS kategorie (id INTEGER PRIMARY KEY, user_id INTEGER, nazev TEXT, barva TEXT, prefix TEXT, aktualni_cislo INTEGER DEFAULT 1, logo_blob BLOB)''')
    c.execute('''CREATE TABLE IF NOT EXISTS faktury (id INTEGER PRIMARY KEY, user_id INTEGER, cislo INTEGER, cislo_full TEXT, klient_id INTEGER, kategorie_id INTEGER, datum_vystaveni TEXT, datum_duzp TEXT, datum_splatnosti TEXT, castka_celkem REAL, zpusob_uhrady TEXT, variabilni_symbol TEXT, cislo_objednavky TEXT, uvodni_text TEXT, uhrazeno INTEGER DEFAULT 0, muj_popis TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS faktura_polozky (id INTEGER PRIMARY KEY, faktura_id INTEGER, nazev TEXT, cena REAL)''')
    conn.commit()
    conn.close()

if 'db_inited' not in st.session_state:
    init_db()
    st.session_state.db_inited = True

# --- 3. AUTENTIZACE ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def login_user(username, password):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND password_hash = ?', (username, hash_password(password))).fetchone()
    conn.close()
    return user

def register_user(username, password):
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)', (username, hash_password(password), datetime.now().isoformat()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# --- 4. FUNKCE PRO PRÁCI S DATY (FILTROVANÉ PODLE USER_ID) ---
def run_command(sql, params=()):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(sql, params)
    conn.commit()
    last_id = c.lastrowid
    conn.close()
    return last_id

def run_query(sql, params=(), single=False):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(sql, params)
    res = c.fetchone() if single else c.fetchall()
    conn.close()
    return res

def get_my_details(uid):
    res = run_query("SELECT * FROM nastaveni WHERE user_id = ? LIMIT 1", (uid,), single=True)
    return dict(res) if res else {}

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

def get_next_invoice_number(kat_id, uid):
    res = run_query("SELECT prefix, aktualni_cislo FROM kategorie WHERE id = ? AND user_id = ?", (kat_id, uid), single=True)
    return (res['aktualni_cislo'], str(res['aktualni_cislo']), res['prefix']) if res else (0, "Neznámá", "")

def remove_accents(input_str):
    if not input_str: return ""
    return "".join([c for c in unicodedata.normalize('NFKD', str(input_str)) if not unicodedata.combining(c)])

def generate_pdf(faktura_id, uid):
    from fpdf import FPDF
    import qrcode

    class PDF(FPDF):
        def header(self):
            font_path = 'arial.ttf'
            self.font_ok = False
            if os.path.exists(font_path):
                try:
                    self.add_font('ArialCS', '', 'arial.ttf', uni=True)
                    self.add_font('ArialCS', 'B', 'arial.ttf', uni=True)
                    self.set_font('ArialCS', 'B', 24)
                    self.font_ok = True
                except: pass
            if not self.font_ok: self.set_font('Arial', 'B', 24)
            self.set_text_color(50, 50, 50)
            self.cell(0, 10, 'FAKTURA', 0, 1, 'R'); self.ln(5)

    try:
        # Kontrola, zda faktura patří uživateli
        data = run_query("SELECT f.*, k.jmeno as k_jmeno, k.adresa as k_adresa, k.ico as k_ico, k.dic as k_dic, kat.barva, kat.logo_blob FROM faktury f JOIN klienti k ON f.klient_id = k.id JOIN kategorie kat ON f.kategorie_id = kat.id WHERE f.id = ? AND f.user_id = ?", (faktura_id, uid), single=True)
        if not data: return "Faktura nenalezena nebo nemáte oprávnění."
        
        polozky = run_query("SELECT * FROM faktura_polozky WHERE faktura_id = ?", (faktura_id,))
        moje = get_my_details(uid)

        pdf = PDF(); pdf.add_page()
        def stxt(t): return str(t) if getattr(pdf, 'font_ok', False) else remove_accents(str(t) if t else "")
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
        except: r,g,b=100,100,100

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
        
        pdf.set_xy(110, y_d)
        pdf.cell(40, 6, stxt("Banka:"), 0, 0); pdf.cell(50, 6, stxt(moje.get('banka','')), 0, 1)
        pdf.set_xy(110, pdf.get_y()); pdf.cell(40, 6, stxt("Číslo účtu:"), 0, 0); pdf.cell(50, 6, stxt(moje.get('ucet','')), 0, 1)
        pdf.set_xy(110, pdf.get_y()); pdf.cell(40, 6, stxt("Var. symbol:"), 0, 0); pdf.cell(50, 6, str(data['variabilni_symbol']), 0, 1)
        
        pdf.ln(15); 
        if data['uvodni_text']: pdf.set_font(fname, '', 10); pdf.multi_cell(190, 5, stxt(data['uvodni_text']), 0, 'L'); pdf.ln(5)
        
        pdf.set_fill_color(240); pdf.cell(140, 8, stxt(" POLOŽKA / POPIS"), 1, 0, 'L', fill=True); pdf.cell(50, 8, stxt("CENA "), 1, 1, 'R', fill=True); pdf.ln(8)
        for item in polozky:
            xb, yb = pdf.get_x(), pdf.get_y(); pdf.multi_cell(140, 8, stxt(item['nazev']), 0, 'L')
            pdf.set_xy(xb + 140, yb); pdf.cell(50, 8, stxt(f"{item['cena']:,.2f} Kč").replace(",", " "), 0, 1, 'R')
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

# --- 6. PŘIHLAŠOVACÍ OBRAZOVKA ---
if not st.session_state.user_id:
    st.markdown("<div class='auth-container'><h2 style='text-align:center'>🔐 Fakturace Online</h2>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Přihlášení", "Registrace"])
    
    with tab1:
        with st.form("login"):
            u = st.text_input("Uživatelské jméno")
            p = st.text_input("Heslo", type="password")
            if st.form_submit_button("Přihlásit se", type="primary"):
                user = login_user(u, p)
                if user:
                    st.session_state.user_id = user['id']
                    st.session_state.username = user['username']
                    st.rerun()
                else:
                    st.error("Špatné jméno nebo heslo")

    with tab2:
        with st.form("reg"):
            nu = st.text_input("Nové jméno")
            np = st.text_input("Nové heslo", type="password")
            np2 = st.text_input("Heslo znovu", type="password")
            if st.form_submit_button("Vytvořit účet"):
                if np != np2: st.error("Hesla se neshodují")
                elif len(nu) < 3: st.error("Jméno je moc krátké")
                else:
                    if register_user(nu, np): st.success("Účet vytvořen! Nyní se přihlaste.");
                    else: st.error("Toto jméno je již obsazené.")
    
    st.info("ℹ️ Toto je DEMO verze s lokální databází. Na web hostingu se data mohou při restartu smazat.")
    st.stop()

# --- 7. HLAVNÍ APLIKACE (PO PŘIHLÁŠENÍ) ---
uid = st.session_state.user_id
st.sidebar.markdown(f"<div class='user-label'>👤 <b>{st.session_state.username}</b></div>", unsafe_allow_html=True)
if st.sidebar.button("Odhlásit se"):
    st.session_state.user_id = None
    st.rerun()

menu = st.sidebar.radio("Menu", ["Faktury", "Klienti", "Kategorie", "Nastavení"], label_visibility="collapsed")

if menu == "Nastavení":
    st.header("⚙️ Nastavení")
    c = get_my_details(uid)
    with st.expander("🏢 Firemní údaje", expanded=True):
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
            if st.form_submit_button("Uložit"): run_command("INSERT INTO klienti (user_id, jmeno, adresa, ico, dic) VALUES (?,?,?,?,?)", (uid,j,a,i,d)); reset_forms(); st.rerun()
    for r in run_query("SELECT * FROM klienti WHERE user_id=?", (uid,)):
        with st.expander(f"{r['jmeno']}"):
            if st.button("Smazat", key=f"d_{r['id']}"): run_command("DELETE FROM klienti WHERE id=? AND user_id=?", (r['id'], uid)); st.rerun()

elif menu == "Kategorie":
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

elif menu == "Faktury":
    import pandas as pd
    st.header("📊 Přehled")
    cy = datetime.now().year
    sc = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND strftime('%Y', datum_vystaveni) = ?", (uid, str(cy)), True)[0] or 0
    su = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno = 0 AND strftime('%Y', datum_vystaveni) = ?", (uid, str(cy)), True)[0] or 0
    c1, c2 = st.columns(2)
    c1.markdown(f"<div class='stat-box'><div class='stat-num'>{sc:,.0f} Kč</div><div class='stat-sub'>Fakturováno {cy}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='stat-box'><div class='stat-err'>{su:,.0f} Kč</div><div class='stat-sub'>Neuhrazeno</div></div>", unsafe_allow_html=True)
    st.divider()

    rid = st.session_state.form_reset_id
    with st.expander("➕ Nová faktura"):
        kli = pd.read_sql("SELECT id, jmeno FROM klienti WHERE user_id=?", sqlite3.connect(DB_FILE), params=(uid,))
        kat = pd.read_sql("SELECT id, nazev FROM kategorie WHERE user_id=?", sqlite3.connect(DB_FILE), params=(uid,))
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
    df = pd.read_sql("SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id = k.id WHERE f.user_id=? ORDER BY f.id DESC LIMIT 50", sqlite3.connect(DB_FILE), params=(uid,))
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
