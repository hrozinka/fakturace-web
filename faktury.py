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
    "password": "Miki+420",
    "logo_url": "https://vasedomena.cz/logo.png" # Doplňte URL vašeho loga
}

# --- 1. KONFIGURACE A CSS ---
st.set_page_config(page_title="Fakturační Systém", page_icon="🧾", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #262730 !important; border: 1px solid #4f4f4f !important; color: #ffffff !important;
    }
    div[data-testid="stExpander"] { background-color: #262730 !important; border: 1px solid #4f4f4f; border-radius: 8px; margin-bottom: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    div[data-testid="stExpander"] details summary { color: #ffffff !important; font-weight: bold; }
    .mini-stat-container { display: flex; gap: 10px; margin-bottom: 20px; justify-content: space-between; }
    .mini-stat-box { background-color: #1f2937; border: 1px solid #374151; border-radius: 8px; padding: 10px; text-align: center; width: 100%; }
    .mini-label { font-size: 11px; text-transform: uppercase; color: #9ca3af; }
    .mini-val-green { font-size: 18px; font-weight: 700; color: #4ade80; }
    .mini-val-gray { font-size: 18px; font-weight: 700; color: #9ca3af; }
    .mini-val-red { font-size: 18px; font-weight: 700; color: #f87171; }
    .status-on { color: #4ade80; font-weight: bold; }
    .status-off { color: #9ca3af; }
    .auth-container { max-width: 500px; margin: 0 auto; padding: 40px 20px; background: #1f2937; border-radius: 10px; border: 1px solid #374151; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABÁZE ---
DB_FILE = 'fakturace_v12_pro.db'

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password_hash TEXT, 
        full_name TEXT, email TEXT, phone TEXT, license_key TEXT, license_valid_until TEXT, 
        role TEXT DEFAULT 'user', created_at TEXT, last_active TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS nastaveni (id INTEGER PRIMARY KEY, user_id INTEGER, nazev TEXT, adresa TEXT, ico TEXT, dic TEXT, ucet TEXT, banka TEXT, email TEXT, telefon TEXT, iban TEXT, smtp_server TEXT, smtp_port INTEGER, smtp_email TEXT, smtp_password TEXT, notify_email TEXT, notify_days INTEGER, notify_active INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS klienti (id INTEGER PRIMARY KEY, user_id INTEGER, jmeno TEXT, adresa TEXT, ico TEXT, dic TEXT, email TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS kategorie (id INTEGER PRIMARY KEY, user_id INTEGER, nazev TEXT, barva TEXT, prefix TEXT, aktualni_cislo INTEGER DEFAULT 1, logo_blob BLOB)''')
    c.execute('''CREATE TABLE IF NOT EXISTS faktury (id INTEGER PRIMARY KEY, user_id INTEGER, cislo INTEGER, cislo_full TEXT, klient_id INTEGER, kategorie_id INTEGER, datum_vystaveni TEXT, datum_duzp TEXT, datum_splatnosti TEXT, castka_celkem REAL, zpusob_uhrady TEXT, variabilni_symbol TEXT, cislo_objednavky TEXT, uvodni_text TEXT, uhrazeno INTEGER DEFAULT 0, muj_popis TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS faktura_polozky (id INTEGER PRIMARY KEY, faktura_id INTEGER, nazev TEXT, cena REAL)''')
    
    adm_pass = hashlib.sha256(str.encode("admin")).hexdigest()
    c.execute("INSERT OR IGNORE INTO users (username, password_hash, role, full_name, email) VALUES (?, ?, ?, ?, ?)", ("admin", adm_pass, "admin", "Super Admin", "jsem@michalkochtik.cz"))
    conn.commit(); conn.close()

init_db()

# --- 3. FUNKCE ---
def run_query(sql, params=(), single=False):
    conn = get_db(); c = conn.cursor(); c.execute(sql, params)
    res = c.fetchone() if single else c.fetchall(); conn.close(); return res

def run_command(sql, params=()):
    conn = get_db(); c = conn.cursor(); c.execute(sql, params); conn.commit(); lid = c.lastrowid; conn.close(); return lid

def hash_password(password): return hashlib.sha256(str.encode(password)).hexdigest()

def update_activity(uid):
    run_command("UPDATE users SET last_active = ? WHERE id = ?", (datetime.now().isoformat(), uid))

def get_time_ago(last_active_str):
    if not last_active_str: return "Nikdy"
    diff = datetime.now() - datetime.fromisoformat(last_active_str)
    s = diff.total_seconds()
    if s < 1800: return "ON"
    if s < 3600: return "1H"
    if s < 86400: return f"{int(s // 3600)}H"
    if s < 2592000: return f"{int(s // 86400)}D"
    if s < 31536000: return f"{int(s // 2592000)}M"
    return f"{int(s // 31536000)}R"

def send_welcome_email(to_email, full_name):
    if not SYSTEM_EMAIL["enabled"]: return
    try:
        msg = MIMEMultipart('related')
        msg['Subject'] = "Vítejte v MojeFaktury"
        msg['From'] = SYSTEM_EMAIL["email"]
        msg['To'] = to_email
        html = f"""<html><body><div style="text-align:center;"><img src="{SYSTEM_EMAIL['logo_url']}" width="150"><br><h2>Vítejte, {full_name}!</h2><p>Váš účet byl úspěšně vytvořen ve verzi <b>FREE</b>.</p></div></body></html>"""
        msg.attach(MIMEText(html, 'html'))
        server = smtplib.SMTP_SSL(SYSTEM_EMAIL["server"], SYSTEM_EMAIL["port"])
        server.login(SYSTEM_EMAIL["email"], SYSTEM_EMAIL["password"])
        server.sendmail(SYSTEM_EMAIL["email"], to_email, msg.as_string())
        server.quit()
    except: pass

def check_license_online(key):
    try:
        url = f"https://gist.githubusercontent.com/hrozinka/6cd3ef1eea1e6d7dc7b188bdbeb84235/raw/licence.json?t={int(datetime.now().timestamp())}"
        r = requests.get(url, timeout=3)
        if r.status_code == 200 and key in r.json(): return True, "Aktivní", "2099-12-31"
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

def generate_pdf(faktura_id, uid, is_pro):
    from fpdf import FPDF
    import qrcode
    class PDF(FPDF):
        def header(self):
            self.font_ok = False
            if os.path.exists('arial.ttf'):
                try: self.add_font('ArialCS', '', 'arial.ttf', uni=True); self.add_font('ArialCS', 'B', 'arial.ttf', uni=True); self.set_font('ArialCS', 'B', 24); self.font_ok = True
                except: pass
            if not self.font_ok: self.set_font('Arial', 'B', 24)
            self.set_text_color(50, 50, 50); self.cell(0, 10, 'FAKTURA', 0, 1, 'R'); self.ln(5)

    try:
        data = run_query("SELECT f.*, k.jmeno as k_jmeno, k.adresa as k_adresa, k.ico as k_ico, k.dic as k_dic, kat.barva, kat.logo_blob FROM faktury f JOIN klienti k ON f.klient_id = k.id JOIN kategorie kat ON f.kategorie_id = kat.id WHERE f.id = ? AND f.user_id = ?", (faktura_id, uid), single=True)
        moje = run_query("SELECT * FROM nastaveni WHERE user_id = ? LIMIT 1", (uid,), single=True) or {}
        polozky = run_query("SELECT * FROM faktura_polozky WHERE faktura_id = ?", (faktura_id,))
        pdf = PDF(); pdf.add_page()
        def stxt(t): return "".join([c for c in unicodedata.normalize('NFKD', str(t)) if not unicodedata.combining(c)]) if not getattr(pdf, 'font_ok', False) else str(t)
        fname = 'ArialCS' if getattr(pdf, 'font_ok', False) else 'Arial'
        pdf.set_font(fname, '', 10)
        
        r,g,b = (0,0,0) if not is_pro else (100,100,100)
        if is_pro:
            try: c_hex = data['barva'].lstrip('#'); r, g, b = tuple(int(c_hex[i:i+2], 16) for i in (0, 2, 4))
            except: pass

        pdf.set_y(40); pdf.cell(95, 5, stxt("DODAVATEL:"), 0, 0); pdf.cell(95, 5, stxt("ODBĚRATEL:"), 0, 1)
        pdf.set_font(fname, '', 12); pdf.cell(95, 5, stxt(moje.get('nazev','')), 0, 1)
        pdf.set_font(fname, '', 10); pdf.multi_cell(95, 5, stxt(f"{moje.get('adresa','')}\nIČ: {moje.get('ico','')}\nDIČ: {moje.get('dic','')}"))
        pdf.set_xy(105, 45); pdf.cell(95, 5, stxt(data['k_jmeno']), 0, 1)
        pdf.set_xy(105, 50); pdf.multi_cell(95, 5, stxt(f"{data['k_adresa']}\nIČ: {data['k_ico']}"))
        pdf.ln(10); pdf.set_fill_color(r, g, b); pdf.rect(10, pdf.get_y(), 190, 2, 'F'); pdf.ln(5)
        pdf.set_font(fname, '', 14); pdf.cell(100, 8, stxt(f"Faktura č.: {data['cislo_full']}"), 0, 1)
        pdf.set_font(fname, '', 10); pdf.cell(0, 6, stxt(f"Splatnost: {format_date(data['datum_splatnosti'])}"), 0, 1)
        pdf.ln(10); pdf.set_fill_color(240); pdf.cell(140, 8, stxt(" Popis"), 1, 0, 'L', True); pdf.cell(50, 8, stxt("Cena"), 1, 1, 'R', True)
        for item in polozky: pdf.cell(140, 8, stxt(item['nazev']), 1); pdf.cell(50, 8, f"{item['cena']:,.2f} Kč", 1, 1, 'R')
        pdf.ln(5); pdf.set_font(fname, 'B', 14); pdf.cell(0, 10, stxt(f"CELKEM: {data['castka_celkem']:,.2f} Kč"), 0, 1, 'R')
        if is_pro and moje.get('iban'):
            qr_s = f"SPD*1.0*ACC:{moje['iban'].replace(' ','').upper()}*AM:{data['castka_celkem']:.2f}*CC:CZK*MSG:{stxt(data['cislo_full'])}"
            img = qrcode.make(qr_s); img.save("q.png"); pdf.image("q.png", x=10, y=pdf.get_y()-10, w=30)
        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except Exception as e: return f"Error: {e}"

# --- 5. AUTH ---
if 'user_id' not in st.session_state: st.session_state.user_id = None

if not st.session_state.user_id:
    st.markdown("<div class='auth-container'><h1 style='text-align:center'>Fakturace Online</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Přihlášení", "Registrace"])
    with t1:
        with st.form("l"):
            u = st.text_input("Uživatelské jméno")
            p = st.text_input("Heslo", type="password")
            if st.form_submit_button("Vstoupit", type="primary"):
                res = run_query("SELECT * FROM users WHERE username=? AND password_hash=?", (u, hash_password(p)), single=True)
                if res:
                    st.session_state.user_id, st.session_state.username, st.session_state.role, st.session_state.full_name = res['id'], res['username'], res['role'], res['full_name']
                    st.session_state.is_pro = True if res['license_key'] else False
                    update_activity(res['id']); st.rerun()
                else: st.error("Chyba přihlášení")
    with t2:
        with st.form("r"):
            f, l = st.text_input("Jméno"), st.text_input("Příjmení")
            u, m = st.text_input("Username (login)"), st.text_input("Email")
            tel, p1 = st.text_input("Telefon"), st.text_input("Heslo", type="password")
            if st.form_submit_button("Registrovat"):
                try:
                    full = f"{f} {l}".strip()
                    run_command("INSERT INTO users (username, password_hash, full_name, email, phone, created_at) VALUES (?,?,?,?,?,?)", (u, hash_password(p1), full, m, tel, datetime.now().isoformat()))
                    send_welcome_email(m, full); st.success("Účet vytvořen!")
                except: st.error("Uživatel již existuje.")
    st.stop()

# --- 6. APP ---
uid = st.session_state.user_id
update_activity(uid)
is_pro = st.session_state.is_pro

st.sidebar.markdown(f"👤 **{st.session_state.full_name}**")
st.sidebar.caption("⭐ PRO Verze" if is_pro else "🆓 FREE Verze")
if st.sidebar.button("Odhlásit"): st.session_state.user_id = None; st.rerun()

# --- ADMIN PANEL ---
if st.session_state.role == 'admin':
    st.header("👑 Admin Panel")
    t1, t2 = st.tabs(["Uživatelé", "Statistiky"])
    with t1:
        usrs = run_query("SELECT * FROM users WHERE role != 'admin'")
        for u in usrs:
            ago = get_time_ago(u['last_active'])
            status = f"<span class='status-on'>{ago}</span>" if ago == "ON" else f"<span class='status-off'>{ago}</span>"
            with st.expander(f"{u['full_name']} ({u['username']}) - {ago}"):
                st.markdown(f"Status: {status}", unsafe_allow_html=True)
                st.write(f"📧 {u['email']} | 📞 {u['phone']} | 🔑 `{u['license_key'] or 'FREE'}`")
                if st.button("Smazat", key=f"d_{u['id']}"): run_command("DELETE FROM users WHERE id=?", (u['id'],)); st.rerun()
    with t2:
        c_u = run_query("SELECT COUNT(*) FROM users WHERE role != 'admin'", single=True)[0]
        c_f = run_query("SELECT COUNT(*) FROM faktury WHERE user_id IN (SELECT id FROM users WHERE role!='admin')", single=True)[0]
        vol = run_query("SELECT SUM(castka_celkem) FROM faktury WHERE user_id IN (SELECT id FROM users WHERE role!='admin')", single=True)[0] or 0
        k1, k2, k3 = st.columns(3)
        k1.metric("Uživatelé", int(c_u)); k2.metric("Faktury", int(c_f)); k3.metric("Objem", f"{vol:,.0f} Kč")

# --- USER PANEL ---
else:
    menu = st.sidebar.radio("Menu", ["Faktury", "Klienti", "Kategorie", "Nastavení"], label_visibility="collapsed")
    
    if menu == "Nastavení":
        st.header("⚙️ Nastavení")
        if not is_pro:
            st.markdown("<div class='promo-box'><h3>🔓 Odemkněte PRO verzi</h3><p>Neomezené faktury, QR kódy a barvy.</p><a href='#' class='promo-link'>Koupit licenci zde</a></div>", unsafe_allow_html=True)
            lk = st.text_input("Licenční klíč")
            if st.button("Aktivovat PRO"):
                v, m, ex = check_license_online(lk)
                if v:
                    run_command("UPDATE users SET license_key=?, license_valid_until=? WHERE id=?", (lk, ex, uid))
                    run_command("DELETE FROM kategorie WHERE user_id=? AND nazev='Obecná'", (uid,))
                    st.session_state.is_pro = True; st.success("Aktivováno!"); st.rerun()
        
        c = run_query("SELECT * FROM nastaveni WHERE user_id=?", (uid,), single=True) or {}
        with st.form("firma"):
            u = run_query("SELECT * FROM users WHERE id=?", (uid,), single=True)
            n=st.text_input("Název", c.get('nazev', u['full_name'])); a=st.text_area("Adresa", c.get('adresa',''))
            i=st.text_input("IČO", c.get('ico','')); uc=st.text_input("Účet", c.get('ucet','')); ib=st.text_input("IBAN", c.get('iban',''))
            em=st.text_input("Email", c.get('email', u['email'])); tel=st.text_input("Telefon", c.get('telefon', u['phone']))
            if st.form_submit_button("Uložit"):
                if c: run_command("UPDATE nastaveni SET nazev=?, adresa=?, ico=?, ucet=?, iban=?, email=?, telefon=? WHERE user_id=?", (n,a,i,uc,ib,em,tel,uid))
                else: run_command("INSERT INTO nastaveni (user_id, nazev, adresa, ico, ucet, iban, email, telefon) VALUES (?,?,?,?,?,?,?,?)", (uid,n,a,i,uc,ib,em,tel))
                st.rerun()
        
        with st.expander("💾 Záloha / Upozornění (Pouze PRO)", expanded=False):
            if not is_pro: st.warning("🔒 Funkce dostupná pouze v PRO verzi.")
            st.write("Zde bude nastavení SMTP a export JSON jako dříve.")

    elif menu == "Klienti":
        st.header("👥 Klienti")
        cnt = run_query("SELECT COUNT(*) FROM klienti WHERE user_id=?", (uid,), single=True)[0]
        if not is_pro and cnt >= 3: st.error("FREE Limit: 3 klienti.")
        else:
            with st.expander("➕ Přidat klienta"):
                ico = st.text_input("IČO"); ares = get_ares_data(ico) if st.button("Hledat v ARES") else None
                with st.form("cl"):
                    nj = st.text_input("Jméno", ares['jmeno'] if ares else ""); na = st.text_area("Adresa", ares['adresa'] if ares else "")
                    if st.form_submit_button("Uložit"): run_command("INSERT INTO klienti (user_id, jmeno, adresa, ico) VALUES (?,?,?,?)", (uid, nj, na, ico)); st.rerun()
        for r in run_query("SELECT * FROM klienti WHERE user_id=?", (uid,)):
            with st.expander(r['jmeno']):
                if st.button("Smazat", key=f"dc_{r['id']}"): run_command("DELETE FROM klienti WHERE id=?", (r['id'],)); st.rerun()

    elif menu == "Kategorie":
        st.header("🏷️ Kategorie")
        if not is_pro:
            st.info("🔒 Vlastní kategorie pouze v PRO. Používá se 'Obecná' (černá).")
            if not run_query("SELECT * FROM kategorie WHERE user_id=? AND nazev='Obecná'", (uid,), single=True):
                run_command("INSERT INTO kategorie (user_id, nazev, prefix, barva) VALUES (?,?,'FV','#000000')", (uid, "Obecná"))
        else:
            with st.expander("➕ Nová kategorie"):
                with st.form("ka"):
                    nk, np, nb = st.text_input("Název"), st.text_input("Prefix", "FV"), st.color_picker("Barva")
                    if st.form_submit_button("Uložit"): run_command("INSERT INTO kategorie (user_id, nazev, prefix, barva) VALUES (?,?,?,?)", (uid, nk, np, nb)); st.rerun()
        for r in run_query("SELECT * FROM kategorie WHERE user_id=?", (uid,)): st.write(f"• {r['nazev']} ({r['prefix']})")

    elif menu == "Faktury":
        st.header("📊 Faktury")
        all_c = run_query("SELECT * FROM klienti WHERE user_id=?", (uid,))
        sel_c = st.selectbox("Filtr klientů", ["Všichni"] + [k['jmeno'] for k in all_c])
        
        # Stats
        q = "SELECT SUM(castka_celkem), COUNT(*) FROM faktury WHERE user_id=?"
        p = [uid]
        if sel_c != "Všichni": q += " AND klient_id = (SELECT id FROM klienti WHERE jmeno=?)"; p.append(sel_c)
        res = run_query(q, p, single=True)
        st.markdown(f"""<div class='mini-stat-container'><div class='mini-stat-box'><div class='mini-label'>Suma ({sel_c})</div><div class='mini-val-green'>{res[0] or 0:,.0f} Kč</div></div><div class='mini-stat-box'><div class='mini-label'>Počet</div><div class='mini-val-gray'>{res[1]}</div></div></div>""", unsafe_allow_html=True)

        cnt_f = run_query("SELECT COUNT(*) FROM faktury WHERE user_id=?", (uid,), single=True)[0]
        if not is_pro and cnt_f >= 5: st.error("FREE Limit: 5 faktur.")
        else:
            with st.expander("➕ Nová faktura"):
                with st.form("fa"):
                    kl = st.selectbox("Klient", [k['jmeno'] for k in all_c])
                    kat = run_query("SELECT * FROM kategorie WHERE user_id=?", (uid,))
                    ka = st.selectbox("Kategorie", [x['nazev'] for x in kat])
                    obj, pop = st.text_input("Objednávka"), st.text_input("Popis položky")
                    cena = st.number_input("Cena", 0); spl = st.date_input("Splatnost", date.today()+timedelta(14))
                    if st.form_submit_button("Vystavit"):
                        kid = run_query("SELECT id FROM klienti WHERE jmeno=?", (kl,), single=True)[0]
                        kaid = run_query("SELECT id FROM kategorie WHERE nazev=?", (ka,), single=True)[0]
                        k_prefix = run_query("SELECT prefix, aktualni_cislo FROM kategorie WHERE id=?", (kaid,), single=True)
                        full_num = f"{k_prefix[0]}{str(k_prefix[1]).zfill(4)}"
                        fid = run_command("INSERT INTO faktury (user_id, cislo_full, klient_id, kategorie_id, datum_vystaveni, datum_splatnosti, castka_celkem, cislo_objednavky, uhrazeno) VALUES (?,?,?,?,?,?,?,?,0)", (uid, full_num, kid, kaid, date.today().isoformat(), spl.isoformat(), cena, obj))
                        run_command("INSERT INTO faktura_polozky (faktura_id, nazev, cena) VALUES (?,?,?)", (fid, pop, cena))
                        run_command("UPDATE kategorie SET aktualni_cislo = aktualni_cislo + 1 WHERE id=?", (kaid,))
                        st.rerun()
        
        faks = run_query("SELECT f.*, k.jmeno FROM faktury f JOIN klienti k ON f.klient_id = k.id WHERE f.user_id=? ORDER BY f.id DESC", (uid,))
        for f in faks:
            icon = "✅" if f['uhrazeno'] else "⏳"
            with st.expander(f"{icon} {f['cislo_full']} | {f['jmeno']} | {f['castka_celkem']} Kč"):
                c1, c2, c3 = st.columns(3)
                if c1.button("Uhrazeno", key=f"pay_{f['id']}"): run_command("UPDATE faktury SET uhrazeno=1 WHERE id=?", (f['id'],)); st.rerun()
                pdf = generate_pdf(f['id'], uid, is_pro)
                c2.download_button("Stáhnout PDF", pdf, f"{f['cislo_full']}.pdf")
                if c3.button("Smazat", key=f"df_{f['id']}"): run_command("DELETE FROM faktury WHERE id=?", (f['id'],)); st.rerun()
