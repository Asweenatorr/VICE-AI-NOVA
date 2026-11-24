import os
import time
import base64
import hashlib
import sqlite3
import streamlit as st
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

load_dotenv()

st.set_page_config(
    page_title="VICE AI // LEONIDA NET",
    page_icon="🌴",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -----------------------------------------------------------------------------
# SQLITE DATABASE (USERS, PERSISTENT SESSIONS & ISOLATED CHAT BLOCKS)
# -----------------------------------------------------------------------------
DB_PATH = "vice_users.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT, salt TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, username TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, role TEXT, content TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

def hash_pw(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def create_session(username: str) -> str:
    token = os.urandom(24).hex()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO sessions (token, username) VALUES (?, ?)", (token, username))
    return token

def get_session_user(token: str) -> str | None:
    if not token:
        return None
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT username FROM sessions WHERE token = ?", (token,)).fetchone()
    return row[0] if row else None

def delete_session(token: str):
    if token:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))

def register_user(username: str, password: str) -> tuple[bool, str]:
    u = username.strip().lower()
    if len(u) < 3 or len(password) < 4:
        return False, "Handle must be 3+ chars and passcode 4+ chars."
    with sqlite3.connect(DB_PATH) as conn:
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (u,)).fetchone():
            return False, "Agent handle already exists. Use Sign In."
        salt = os.urandom(16).hex()
        conn.execute("INSERT INTO users VALUES (?, ?, ?)", (u, hash_pw(password, salt), salt))
        welcome = f"Welcome to **Vice City Neural Link**, Agent **{u.upper()}**. Your encrypted chat block is active."
        conn.execute("INSERT INTO chat_history (username, role, content) VALUES (?, ?, ?)", (u, "assistant", welcome))
    return True, "Initialized!"

def authenticate_user(username: str, password: str) -> bool:
    u = username.strip().lower()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT password_hash, salt FROM users WHERE username = ?", (u,)).fetchone()
    return bool(row and hash_pw(password, row[1]) == row[0])

def load_history(username: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT role, content, timestamp FROM chat_history WHERE username = ? ORDER BY id ASC", (username,)).fetchall()
    return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in rows]

def save_msg(username: str, role: str, content: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO chat_history (username, role, content) VALUES (?, ?, ?)", (username, role, content))

def wipe_history(username: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM chat_history WHERE username = ?", (username,))
        msg = f"Memory block wiped for Agent **{username.upper()}**. Fresh slate ready."
        conn.execute("INSERT INTO chat_history (username, role, content) VALUES (?, ?, ?)", (username, "assistant", msg))

init_db()

# -----------------------------------------------------------------------------
# AVATARS (ANIME FEMALE AI + USER)
# -----------------------------------------------------------------------------
def to_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.strip().encode()).decode()

AI_AVATAR = to_uri("""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">
  <defs>
    <linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ff007f"/><stop offset="100%" stop-color="#00f2fe"/>
    </linearGradient>
    <linearGradient id="g2" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#ff71ce"/><stop offset="100%" stop-color="#b967ff"/>
    </linearGradient>
  </defs>
  <circle cx="60" cy="60" r="58" fill="url(#g1)"/>
  <circle cx="60" cy="60" r="52" fill="#120822"/>
  <path d="M28 55 Q25 95 36 105 L84 105 Q95 95 92 55 Z" fill="url(#g2)"/>
  <path d="M30 108 Q60 92 90 108 L95 115 L25 115 Z" fill="#1f1135" stroke="#00f2fe" stroke-width="2"/>
  <rect x="53" y="76" width="14" height="16" rx="4" fill="#ffe0d2"/>
  <path d="M38 48 Q38 80 60 83 Q82 80 82 48 Q82 28 60 28 Q38 28 38 48 Z" fill="#ffece4"/>
  <ellipse cx="49" cy="56" rx="5.5" ry="6.5" fill="#1a0b2e"/><ellipse cx="71" cy="56" rx="5.5" ry="6.5" fill="#1a0b2e"/>
  <circle cx="49" cy="57" r="3.5" fill="#00f2fe"/><circle cx="71" cy="57" r="3.5" fill="#00f2fe"/>
  <circle cx="47.5" cy="54" r="1.8" fill="#fff"/><circle cx="69.5" cy="54" r="1.8" fill="#fff"/>
  <path d="M56 69 Q60 73 64 69" stroke="#d64579" stroke-width="2" fill="none" stroke-linecap="round"/>
  <path d="M34 52 Q36 22 60 22 Q84 22 86 52 Q78 36 70 46 Q64 33 60 47 Q54 33 48 46 Q41 36 34 52 Z" fill="url(#g2)"/>
  <rect x="32" y="46" width="6" height="14" rx="3" fill="#00f2fe"/><rect x="82" y="46" width="6" height="14" rx="3" fill="#ff007f"/>
</svg>
""")

USER_AVATAR = to_uri("""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="48" fill="#1a0b2e" stroke="#ff007f" stroke-width="4"/>
  <circle cx="50" cy="38" r="16" fill="#00f2fe"/>
  <path d="M22 84 Q50 62 78 84" fill="#ff007f"/>
</svg>
""")

# -----------------------------------------------------------------------------
# SESSION STATE & REFRESH-SAFE TOKEN RESTORATION
# -----------------------------------------------------------------------------
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "🌙 Dark Mode"
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "messages" not in st.session_state:
    st.session_state.messages = []

if not st.session_state.authenticated:
    token = st.query_params.get("session", "")
    user_from_db = get_session_user(token)
    if user_from_db:
        st.session_state.authenticated = True
        st.session_state.current_user = user_from_db
        st.session_state.messages = load_history(user_from_db)
    elif token:
        st.query_params.clear()

# -----------------------------------------------------------------------------
# DARK MODE & LIGHT MODE HIGH-CONTRAST CSS (LARGE READABLE FONTS)
# -----------------------------------------------------------------------------
def apply_theme(mode: str):
    is_dark = (mode == "🌙 Dark Mode")
    bg = "#0f0722" if is_dark else "#f4f6fb"
    card = "#1b0e36" if is_dark else "#ffffff"
    inp = "#150a2b" if is_dark else "#ffffff"
    fg = "#ffffff" if is_dark else "#111827"
    pink = "#ff4da6" if is_dark else "#d90467"
    cyan = "#00f2fe" if is_dark else "#026aa7"
    border = "#00f2fe" if is_dark else "#d90467"

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;800&family=Plus+Jakarta+Sans:wght@500;600;700&display=swap');
    html, body, [data-testid="stAppViewContainer"], .stApp {{
        background-color: {bg} !important;
        color: {fg} !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 18px !important;
    }}
    [data-testid="stHeader"] {{ background-color: transparent !important; }}
    p, li, span, label, div, .stMarkdown p {{
        color: {fg} !important;
        font-size: 1.1rem !important;
        line-height: 1.65 !important;
    }}
    h1, h2, h3, h4 {{
        color: {fg} !important;
        font-family: 'Orbitron', sans-serif !important;
    }}
    .vice-header {{
        background:
