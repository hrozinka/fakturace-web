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

DB_FILE = 'fakturace_v17_pro.db'

# --- 1. DESIGN (MOBILE FIRST) ---
st.set_page_config(page_title="Fakturace Pro", page_icon="💎", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #0f172a; color: #f8fafc; font-family: sans-serif; }
    
    /* INPUTY */
    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #1e293b !important; border: 1px solid #334155 !important; color: #fff !important;
        border-radius: 12px !important; padding: 12px !important;
    }
    
    /* MENU */
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
    
    /* STATISTIKY */
    .stat-container { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
    .stat-box { 
        background: #1e293b; border-radius: 12px; padding: 15px; flex: 1; min-width: 100px;
        text-align: center; border: 1px solid #334155; box-shadow: 0 4px 6px rgba(0,0,0,0.2);
    }
    .stat-label { font-size: 11px; text-transform: uppercase; color: #94a3b8; margin-bottom: 5px; font-weight: 700; }
    .stat-value { font-size: 20px; font-weight: 800; color: #fff; }
    .text-green { color: #34d399 !important; } .text-red { color: #f87171 !important; } .text-gold { color: #fbbf24 !important; }

    /* TLAČÍTKA */
    .stButton > button { background-color: #334155 !important; color: white !important; border-radius: 10px !important; height: 50px; font-weight: 600; border: none;}
    div[data-testid="stForm"] button[kind="primary"] { background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%) !important; color: #0f172a !important; }
    
    /* MODRÉ INFO BOXY */
    .info-box { background: #1e3a8a; padding: 15px; border-radius: 10px; border-left: 5px solid #60a5fa; margin-bottom: 15px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABÁZE ---
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def run_query(sql, params=(), single=False):
    conn = get_db(); c = conn.cursor(); c.execute(sql, params)
    res = c.fetchone() if single else c.fetchall(); conn.close(); return res

def run_command(sql, params=()):
    conn = get_db(); c = conn.cursor(); c.execute(sql, params); conn.commit(); lid = c.lastrowid; conn.close(); return lid

def init_db():
    conn = get_db(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, full_name TEXT, email TEXT, phone TEXT, license_key TEXT, license_valid_until TEXT, role TEXT DEFAULT 'user', created_at TEXT, last_active TEXT)''')
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

# --- 3. POMOCNÉ FUNKCE (OPRAVENO PARSOVÁNÍ DATA) ---
def hash_password(password): return hashlib.sha256(str.encode(password)).hexdigest()
def remove_accents(s): return "".join([c for c in unicodedata.normalize('NFKD', str(s)) if not unicodedata.combining(c)]) if s else ""

def format_date(d):
    """Bezpečné formátování data, které zvládne i ISO format s časem"""
    if not d or str(d) == 'None': return ""
    try:
        # Pokud je to string (z databáze), ořízneme časovou část
        if isinstance(d, str):
            # Bere jen prvních 10 znaků (YYYY-MM-DD)
            d_str = d[:10]
            d_obj = datetime.strptime(d_str, '%Y-%m-%d')
            return d_obj.strftime('%d.%m.%Y')
        # Pokud je to už datetime/date objekt
        return d.strftime('%d.%m.%Y')
    except:
        return str(d) # Fallback

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

# --- ARES ---
def get_ares_data(ico):
    import urllib3; urllib3.disable_warnings()
    if not ico: return None
    ico = "".join(filter(str.isdigit, str(ico))).zfill(8)
    try:
        url = f"https://ares.gov.cz/ekonomicke-subjekty/v-1/ekonomicke-subjekty/{ico}"
        headers = {"accept": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        r = requests.get(url, headers=headers, verify=False, timeout=5)
        if r.status_code == 200:
            d = r.json(); s = d.get('sidlo', {})
            adr = s.get('textovaAdresa', '')
            if not adr: adr = f"{s.get('nazevUlice','')} {s.get('cisloDomovni','')}/{s.get('cisloOrientacni','')}, {s.get('psc','')} {s.get('nazevObce','')}".strip(' ,/')
            return {"jmeno": d.get('obchodniJmeno', ''), "adresa": adr, "ico": ico, "dic": d.get('dic', '')}
    except: pass
    return None

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
    
    data = run_query("SELECT f.*, k.jmeno as k_jmeno, k.adresa as k_adresa, k.ico as k_ico, k.dic as k_dic, kat.barva, kat.logo_blob FROM faktury f JOIN klienti k ON f.klient_id=k.id JOIN kategorie kat ON f.kategorie_id=kat.id WHERE f.id=? AND f.user_id=?", (faktura_id, uid), single=True)
    if not data: return "Chyba"
    polozky = run_query("SELECT * FROM faktura_polozky WHERE faktura_id=?", (faktura_id,))
    moje = run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1", (uid,), single=True) or {}
    
    pdf = PDF(); pdf.add_page(); pdf.set_font('ArialCS' if os.path.exists('arial.ttf') else 'Arial', '', 10)
    
    if data['logo_blob']:
        try: fn=f"t_{faktura_id}.png"; open(fn,"wb").write(data['logo_blob']); pdf.image(fn,10,10,30); os.remove(fn)
        except: pass
    
    pdf.set_y(40); pdf.cell(95,5,"DODAVATEL:",0,0); pdf.cell(95,5,"ODBĚRATEL:",0,1)
    y = pdf.get_y(); pdf.set_font('', '', 12); pdf.cell(95,5,remove_accents(moje.get('nazev','')),0,1)
    pdf.set_font('', '', 10); pdf.multi_cell(95,5,remove_accents(f"{moje.get('adresa','')}\nIČ: {moje.get('ico','')}\nDIČ: {moje.get('dic','')}"))
    pdf.set_xy(105,y); pdf.set_font('', '', 12); pdf.cell(95,5,remove_accents(data['k_jmeno']),0,1)
    pdf.set_xy(105,pdf.get_y()); pdf.set_font('', '', 10); pdf.multi_cell(95,5,remove_accents(f"{data['k_adresa']}\nIČ: {data['k_ico']}\nDIČ: {data['k_dic']}"))
    
    pdf.ln(10); c=data['barva'].lstrip('#'); r,g,b=tuple(int(c[i:i+2],16) for i in(0,2,4)) if is_pro else (0,0,0)
    pdf.set_fill_color(r,g,b); pdf.rect(10,pdf.get_y(),190,2,'F'); pdf.ln(5)
    
    pdf.set_font('', '', 14); pdf.cell(100,8,f"Faktura c.: {data['cislo_full']}",0,1); pdf.set_font('', '', 10)
    pdf.cell(50,6,"Vystaveno:",0,0); pdf.cell(50,6,format_date(data['datum_vystaveni']),0,1)
    pdf.cell(50,6,"Splatnost:",0,0); pdf.cell(50,6,format_date(data['datum_splatnosti']),0,1)
    pdf.cell(50,6,"Ucet:",0,0); pdf.cell(50,6,str(moje.get('ucet','')),0,1)
    pdf.cell(50,6,"VS:",0,0); pdf.cell(50,6,str(data['variabilni_symbol']),0,1)
    
    pdf.ln(10); pdf.set_fill_color(240); pdf.cell(140,8,"POLOZKA",1,0,'L',True); pdf.cell(50,8,"CENA",1,1,'R',True)
    for p in polozky:
        pdf.cell(140,8,remove_accents(p['nazev']),1); pdf.cell(50,8,f"{p['cena']:.2f} Kc",1,1,'R')
    pdf.ln(5); pdf.set_font('','B',14); pdf.cell(190,10,f"CELKEM: {data['castka_celkem']:.2f} Kc",0,1,'R')
    
    if is_pro and moje.get('iban'):
        try: qr=f"SPD*1.0*ACC:{moje['iban']}*AM:{data['castka_celkem']}*CC:CZK*MSG:{data['cislo_full']}"; img=qrcode.make(qr); img.save("q.png"); pdf.image("q.png",10,pdf.get_y()-20,30); os.remove("q.png")
        except: pass
        
    return pdf.output(dest='S').encode('latin-1','ignore')

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
    c1,c2,c3 = st.columns([1,6,1])
    with c2:
        st.markdown("<h1 style='text-align:center; color:#fbbf24'>💎 Fakturace Pro</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center; color:#94a3b8'>Fakturace v kapse. Rychle, jednoduše, profesionálně.</p>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["PŘIHLÁŠENÍ", "REGISTRACE"])
        with t1:
            with st.form("log"):
                u=st.text_input("Login"); p=st.text_input("Heslo", type="password")
                if st.form_submit_button("Vstoupit", type="primary", use_container_width=True):
                    r = run_query("SELECT * FROM users WHERE username=? AND password_hash=?",(u, hash_password(p)), single=True)
                    if r:
                        st.session_state.user_id=r['id']; st.session_state.role=r['role']; st.session_state.username=r['username']; st.session_state.full_name=r['full_name']; st.session_state.user_email=r['email']
                        valid, exp = check_license_validity(r['id'])
                        st.session_state.is_pro = valid
                        run_command("UPDATE users SET last_active=? WHERE id=?",(datetime.now().isoformat(), r['id'])); st.rerun()
                    else: st.error("Chyba")
        with t2:
            with st.form("reg"):
                f=st.text_input("Jméno"); u=st.text_input("Login"); e=st.text_input("Email"); p=st.text_input("Heslo",type="password")
                if st.form_submit_button("Registrovat", use_container_width=True):
                    try:
                        run_command("INSERT INTO users (username,password_hash,full_name,email,created_at) VALUES (?,?,?,?,?)",(u,hash_password(p),f,e,datetime.now().isoformat()))
                        st.success("Hotovo! Přihlašte se."); 
                    except: st.error("Login obsazen.")
    st.stop()

# --- 9. APP ---
uid=st.session_state.user_id; role=st.session_state.role; is_pro=st.session_state.is_pro
full_name_display = st.session_state.full_name or st.session_state.username

run_command("UPDATE users SET last_active=? WHERE id=?",(datetime.now().isoformat(), uid))

st.sidebar.title(f"👤 {full_name_display}")
if st.sidebar.button("Odhlásit"): st.session_state.user_id=None; st.rerun()

# ADMIN
if role == 'admin':
    st.header("👑 Admin Sekce")
    tabs = st.tabs(["Uživatelé", "Licence", "Statistiky"])
    
    with tabs[0]:
        users = run_query("SELECT * FROM users WHERE role!='admin'")
        for u in users:
            with st.expander(f"{u['username']} ({u['email']})"):
                # RESPONSIVNÍ ZOBRAZENÍ V ADMINU
                st.markdown(f"**Vytvořeno:** {format_date(u['created_at'])}")
                st.markdown(f"**Aktivní:** {format_date(u['last_active'])}")
                st.markdown(f"**Telefon:** {u['phone'] or '---'}")
                
                st.divider()
                st.write("📅 Správa licence")
                
                # Bezpečné načtení data pro Date Input
                def_val = date.today()
                if u['license_valid_until']:
                    try: def_val = datetime.strptime(u['license_valid_until'][:10], '%Y-%m-%d').date()
                    except: pass
                
                lic_till = st.date_input("Platnost do:", value=def_val, key=f"ld_{u['id']}")
                new_key = st.text_input("Klíč", value=u['license_key'] or "", key=f"lk_{u['id']}")
                
                if st.button("💾 Uložit změny", key=f"sv_{u['id']}"):
                    run_command("UPDATE users SET license_valid_until=?, license_key=? WHERE id=?",(lic_till, new_key, u['id']))
                    st.success("Uloženo"); st.rerun()
                
                if st.button("🗑️ Smazat uživatele", key=f"del_{u['id']}", type="primary"):
                    run_command("DELETE FROM users WHERE id=?",(u['id'],)); st.rerun()

    with tabs[1]:
        st.write("Generování nových klíčů")
        c1,c2 = st.columns(2)
        days = c1.number_input("Dny platnosti", value=365)
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
    
    if "Faktury" in menu:
        st.header("Faktury")
        # 1. ROK FILTR
        years = [r[0] for r in run_query("SELECT DISTINCT strftime('%Y', datum_vystaveni) FROM faktury WHERE user_id=?", (uid,))]
        cur_year = str(datetime.now().year)
        if cur_year not in years: years.append(cur_year)
        sel_year = st.selectbox("Rok", sorted(years, reverse=True))
        
        # 2. STATISTIKY (3 BOXY)
        sc_y = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND strftime('%Y', datum_vystaveni)=?", (uid, sel_year), True)[0] or 0
        sc_all = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=?", (uid,), True)[0] or 0
        su_all = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id=? AND uhrazeno=0", (uid,), True)[0] or 0
        
        st.markdown(f"""
        <div class="stat-container">
            <div class="stat-box"><div class="stat-label">OBRAT {sel_year}</div><div class="stat-value text-green">{sc_y:,.0f} Kč</div></div>
            <div class="stat-box"><div class="stat-label">CELKEM (ALL)</div><div class="stat-value text-gold">{sc_all:,.0f} Kč</div></div>
            <div class="stat-box"><div class="stat-label">NEUHRAZENO</div><div class="stat-value text-red">{su_all:,.0f} Kč</div></div>
        </div>
        """, unsafe_allow_html=True)
        
        # 3. FILTR KLIENTA
        clients = ["Všichni"] + [c['jmeno'] for c in run_query("SELECT jmeno FROM klienti WHERE user_id=?", (uid,))]
        sel_cli = st.selectbox("Klient", clients)
        
        # 4. NOVÁ FAKTURA
        with st.expander("➕ Nová faktura"):
            kli = pd.read_sql("SELECT id, jmeno FROM klienti WHERE user_id=?", get_db(), params=(uid,))
            kat = pd.read_sql("SELECT id, nazev FROM kategorie WHERE user_id=?", get_db(), params=(uid,))
            if kli.empty: st.warning("Vytvořte nejdříve klienta.")
            elif not is_pro and kat.empty: run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva) VALUES (?, 'Obecná', 'FV', 1, '#000000')", (uid,)); st.rerun()
            else:
                rid = st.session_state.form_reset_id
                c1,c2 = st.columns(2)
                sk = c1.selectbox("Klient", kli['jmeno'], key=f"k_{rid}")
                sc = c2.selectbox("Kategorie", kat['nazev'], key=f"c_{rid}")
                kid = int(kli[kli['jmeno']==sk]['id'].values[0]); cid = int(kat[kat['nazev']==sc]['id'].values[0])
                _, full, _ = get_next_invoice_number(cid, uid); st.info(f"Doklad: {full}")
                d1,d2 = st.columns(2); dv = d1.date_input("Vystavení", date.today(), key=f"d1_{rid}"); ds = d2.date_input("Splatnost", date.today()+timedelta(14), key=f"d2_{rid}")
                ed = st.data_editor(st.session_state.items_df, num_rows="dynamic", use_container_width=True, key=f"e_{rid}")
                tot = float(pd.to_numeric(ed["Cena"], errors='coerce').fillna(0).sum()); st.markdown(f"### Celkem: {tot:,.2f} Kč")
                if st.button("Vystavit fakturu", type="primary", key=f"b_{rid}"):
                    fid = run_command("INSERT INTO faktury (user_id, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_splatnosti, castka_celkem, variabilni_symbol) VALUES (?,?,?,?,?,?,?,?)", (uid, full, kid, cid, dv, ds, tot, re.sub(r"\D", "", full)))
                    for _, r in ed.iterrows(): 
                        if r["Popis položky"]: run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (fid, r["Popis položky"], float(r["Cena"])))
                    run_command("UPDATE kategorie SET aktualni_cislo = aktualni_cislo + 1 WHERE id = ?", (cid,)); reset_forms(); st.success("Faktura vystavena"); st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        
        # 5. VÝPIS A FILTR
        q = "SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id=k.id WHERE f.user_id=?"
        p = [uid]
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
                
                # EDITACE
                efkey = f"ef_{r['id']}"
                if efkey not in st.session_state: st.session_state[efkey] = False
                if c3.button("Upravit", key=f"be_{r['id']}"): st.session_state[efkey] = True; st.rerun()
                
                if st.session_state[efkey]:
                    with st.form(f"fe_{r['id']}"):
                        nd = st.date_input("Splatnost", pd.to_datetime(r['datum_splatnosti']))
                        nm = st.text_input("Popis", r['muj_popis'] or "")
                        cur_i = pd.read_sql("SELECT nazev as 'Popis položky', cena as 'Cena' FROM faktura_polozky WHERE faktura_id=?", get_db(), params=(r['id'],))
                        ned = st.data_editor(cur_i, num_rows="dynamic", use_container_width=True)
                        if st.form_submit_button("Uložit změny"):
                            ntot = float(pd.to_numeric(ned["Cena"], errors='coerce').fillna(0).sum())
                            run_command("UPDATE faktury SET datum_splatnosti=?, muj_popis=?, castka_celkem=? WHERE id=?", (nd, nm, ntot, r['id']))
                            run_command("DELETE FROM faktura_polozky WHERE faktura_id=?", (r['id'],))
                            for _, rw in ned.iterrows(): 
                                if rw["Popis položky"]: run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (r['id'], rw["Popis položky"], float(rw["Cena"])))
                            st.session_state[efkey] = False; st.rerun()
                
                if st.button("Smazat", key=f"bd_{r['id']}"): run_command("DELETE FROM faktury WHERE id=?",(r['id'],)); st.rerun()

    elif "Klienti" in menu:
        st.header("Klienti")
        rid = st.session_state.form_reset_id
        with st.expander("➕ Přidat klienta"):
            c1,c2 = st.columns([3,1]); ico = c1.text_input("IČO (ARES)", key=f"a_{rid}")
            if c2.button("Načíst", key=f"b_{rid}"):
                d = get_ares_data(ico)
                if d: st.session_state.ares_data = d; st.success("OK")
                else: st.error("Nenalezeno (zkuste zadat ručně)")
            
            ad = st.session_state.ares_data
            with st.form("fc"):
                j=st.text_input("Jméno", ad.get('jmeno','')); a=st.text_area("Adresa", ad.get('adresa',''))
                i=st.text_input("IČ", ad.get('ico','')); d=st.text_input("DIČ", ad.get('dic','')); p=st.text_area("Poznámka")
                if st.form_submit_button("Uložit"):
                    run_command("INSERT INTO klienti (user_id, jmeno, adresa, ico, dic, poznamka) VALUES (?,?,?,?,?,?)", (uid,j,a,i,d,p)); reset_forms(); st.rerun()
        
        for k in run_query("SELECT * FROM klienti WHERE user_id=?", (uid,)):
            with st.expander(k['jmeno']):
                if k['poznamka']: st.info(k['poznamka'])
                # EDIT
                ekey = f"ek_{k['id']}"
                if ekey not in st.session_state: st.session_state[ekey] = False
                c1,c2=st.columns(2)
                if c1.button("Upravit", key=f"bek_{k['id']}"): st.session_state[ekey]=True; st.rerun()
                if c2.button("Smazat", key=f"bdk_{k['id']}"): run_command("DELETE FROM klienti WHERE id=?",(k['id'],)); st.rerun()
                
                if st.session_state[ekey]:
                    with st.form(f"fek_{k['id']}"):
                        nj=st.text_input("Jméno", k['jmeno']); na=st.text_area("Adresa", k['adresa'])
                        ni=st.text_input("IČ", k['ico']); nd=st.text_input("DIČ", k['dic']); np=st.text_area("Poznámka", k['poznamka'])
                        if st.form_submit_button("Uložit"):
                            run_command("UPDATE klienti SET jmeno=?, adresa=?, ico=?, dic=?, poznamka=? WHERE id=?", (nj,na,ni,nd,np,k['id']))
                            st.session_state[ekey]=False; st.rerun()

    elif "Kategorie" in menu:
        st.header("Kategorie")
        with st.expander("➕ Nová kategorie"):
            with st.form("fcat"):
                n=st.text_input("Název"); p=st.text_input("Prefix"); s=st.number_input("Start",1); c=st.color_picker("Barva"); l=st.file_uploader("Logo")
                if st.form_submit_button("Uložit"):
                    run_command("INSERT INTO kategorie (user_id, nazev, prefix, aktualni_cislo, barva, logo_blob) VALUES (?,?,?,?,?,?)", (uid,n,p,s,c,process_logo(l))); st.rerun()
        
        for k in run_query("SELECT * FROM kategorie WHERE user_id=?", (uid,)):
            with st.expander(k['nazev']):
                if st.button("Smazat", key=f"bdc_{k['id']}"): run_command("DELETE FROM kategorie WHERE id=?", (k['id'],)); st.rerun()

    elif "Nastavení" in menu:
        st.header("Nastavení")
        
        # 1. LICENCE
        with st.expander("🔑 Licence & Předplatné", expanded=True):
            valid, exp_date = check_license_validity(uid)
            status_color = "text-green" if valid else "text-red"
            status_text = "AKTIVNÍ PRO" if valid else "FREE VERZE"
            
            st.markdown(f"""
            <div class='stat-box' style='text-align:left'>
                <div class='stat-label'>STAV LICENCE</div>
                <div class='stat-value {status_color}'>{status_text}</div>
                <p>Platnost do: <b>{format_date(exp_date) if valid else '---'}</b></p>
            </div>
            """, unsafe_allow_html=True)
            
            if not valid:
                st.info("💡 Pro zakoupení licence napište na: **jsem@michalkochtik.cz**")
                lic_key = st.text_input("Máte klíč? Zadejte ho zde:")
                if st.button("Aktivovat klíč"):
                    k_db = run_query("SELECT * FROM licencni_klice WHERE kod=? AND pouzito_uzivatelem_id IS NULL", (lic_key,), single=True)
                    if k_db:
                        new_exp = date.today() + timedelta(days=k_db['dny_platnosti'])
                        run_command("UPDATE users SET license_key=?, license_valid_until=? WHERE id=?", (lic_key, new_exp, uid))
                        run_command("UPDATE licencni_klice SET pouzito_uzivatelem_id=? WHERE id=?", (uid, k_db['id']))
                        st.session_state.is_pro = True
                        st.balloons(); st.success(f"Licence aktivována do {format_date(new_exp)}"); st.rerun()
                    else:
                        st.error("Neplatný nebo již použitý klíč.")

        # 2. MOJE FIRMA
        c = run_query("SELECT * FROM nastaveni WHERE user_id=? LIMIT 1", (uid,), single=True) or {}
        with st.expander("🏢 Moje Firma"):
            with st.form("setf"):
                n=st.text_input("Název", c.get('nazev', full_name_display)); a=st.text_area("Adresa", c.get('adresa',''))
                i=st.text_input("IČO", c.get('ico','')); d=st.text_input("DIČ", c.get('dic',''))
                b=st.text_input("Banka", c.get('banka','')); u=st.text_input("Účet", c.get('ucet','')); ib=st.text_input("IBAN", c.get('iban',''))
                em=st.text_input("Email", c.get('email','')); ph=st.text_input("Telefon", c.get('telefon',''))
                if st.form_submit_button("Uložit"):
                    if c.get('id'): run_command("UPDATE nastaveni SET nazev=?, adresa=?, ico=?, dic=?, banka=?, ucet=?, iban=?, email=?, telefon=? WHERE id=?", (n,a,i,d,b,u,ib,em,ph,c['id']))
                    else: run_command("INSERT INTO nastaveni (user_id, nazev, adresa, ico, dic, banka, ucet, iban, email, telefon) VALUES (?,?,?,?,?,?,?,?,?,?)", (uid,n,a,i,d,b,u,ib,em,ph))
                    st.rerun()

        # 3. SMTP & ZÁLOHY
        if is_pro:
            with st.expander("🔔 SMTP (Upozornění)"):
                act = st.toggle("Aktivní", value=bool(c.get('notify_active', 0)))
                ne = st.text_input("Notifikační email", value=c.get('notify_email',''))
                ss = st.text_input("SMTP Server", value=c.get('smtp_server',''))
                sp = st.number_input("SMTP Port", value=c.get('smtp_port', 587))
                se = st.text_input("SMTP Login", value=c.get('smtp_email',''))
                sw = st.text_input("SMTP Heslo", value=c.get('smtp_password',''), type="password")
                if st.button("Uložit SMTP"):
                    run_command("UPDATE nastaveni SET notify_active=?, notify_email=?, smtp_server=?, smtp_port=?, smtp_email=?, smtp_password=? WHERE id=?", (int(act), ne, ss, sp, se, sw, c.get('id'))); st.success("Uloženo")
            
            with st.expander("💾 Zálohování dat"):
                def get_bk():
                    data={}
                    for t in ['nastaveni','klienti','kategorie','faktury','faktura_polozky']:
                         cols = [i[1] for i in get_db().execute(f"PRAGMA table_info({t})")]
                         q = f"SELECT * FROM {t} WHERE user_id=?" if 'user_id' in cols else f"SELECT * FROM {t}"
                         p = (uid,) if 'user_id' in cols else ()
                         if t=='faktura_polozky': q="SELECT fp.* FROM faktura_polozky fp JOIN faktury f ON fp.faktura_id=f.id WHERE f.user_id=?"; p=(uid,)
                         df = pd.read_sql(q, get_db(), params=p)
                         if 'logo_blob' in df.columns: df['logo_blob'] = df['logo_blob'].apply(lambda x: base64.b64encode(x).decode('utf-8') if x else None)
                         data[t] = df.to_dict(orient='records')
                    return json.dumps(data, default=str)
                st.download_button("⬇️ Stáhnout zálohu (JSON)", get_bk(), "zaloha.json", "application/json")
                
                upl = st.file_uploader("⬆️ Obnovit ze zálohy", type="json")
                if upl and st.button("Spustit obnovu"):
                    try:
                        data = json.load(upl)
                        run_command("DELETE FROM nastaveni WHERE user_id=?", (uid,))
                        run_command("DELETE FROM klienti WHERE user_id=?", (uid,))
                        run_command("DELETE FROM kategorie WHERE user_id=?", (uid,))
                        faktury_ids = run_query("SELECT id FROM faktury WHERE user_id=?", (uid,))
                        for f in faktury_ids: run_command("DELETE FROM faktura_polozky WHERE faktura_id=?", (f['id'],))
                        run_command("DELETE FROM faktury WHERE user_id=?", (uid,))
                        for row in data.get('nastaveni', []):
                            run_command("INSERT INTO nastaveni (user_id, nazev, adresa, ico, dic, ucet, banka, email, telefon, iban) VALUES (?,?,?,?,?,?,?,?,?,?)", (uid, row.get('nazev'), row.get('adresa'), row.get('ico'), row.get('dic'), row.get('ucet'), row.get('banka'), row.get('email'), row.get('telefon'), row.get('iban')))
                        for row in data.get('klienti', []):
                            run_command("INSERT INTO klienti (user_id, jmeno, adresa, ico, dic, email, poznamka) VALUES (?,?,?,?,?,?,?)", (uid, row.get('jmeno'), row.get('adresa'), row.get('ico'), row.get('dic'), row.get('email'), row.get('poznamka')))
                        for row in data.get('kategorie', []):
                            blob = base64.b64decode(row.get('logo_blob')) if row.get('logo_blob') else None
                            run_command("INSERT INTO kategorie (user_id, nazev, barva, prefix, aktualni_cislo, logo_blob) VALUES (?,?,?,?,?,?)", (uid, row.get('nazev'), row.get('barva'), row.get('prefix'), row.get('aktualni_cislo'), blob))
                        for row in data.get('faktury', []):
                            new_fid = run_command("INSERT INTO faktury (user_id, cislo, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_duzp, datum_splatnosti, castka_celkem, zpusob_uhrady, variabilni_symbol, cislo_objednavky, uvodni_text, uhrazeno, muj_popis) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (uid, row.get('cislo'), row.get('cislo_full'), row.get('klient_id'), row.get('kategorie_id'), row.get('datum_vystaveni'), row.get('datum_duzp'), row.get('datum_splatnosti'), row.get('castka_celkem'), row.get('zpusob_uhrady'), row.get('variabilni_symbol'), row.get('cislo_objednavky'), row.get('uvodni_text'), row.get('uhrazeno'), row.get('muj_popis')))
                            old_fid = row.get('id')
                            for item in data.get('faktura_polozky', []):
                                if item.get('faktura_id') == old_fid:
                                    run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (new_fid, item.get('nazev'), item.get('cena')))
                        st.success("Data úspěšně obnovena!"); st.rerun()
                    except Exception as e: st.error(f"Chyba importu: {str(e)}")
