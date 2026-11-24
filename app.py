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
st.set_page_config(page_title="VICE AI // LEONIDA NET", page_icon="🌴", layout="wide")

DB_PATH = "vice_users.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, pw TEXT, salt TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, username TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, role TEXT, content TEXT, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

def hash_pw(pw: str, salt: str) -> str:
    return hashlib.sha256((salt + pw).encode()).hexdigest()

def create_session(user: str) -> str:
    tok = os.urandom(20).hex()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO sessions VALUES (?, ?)", (tok, user))
    return tok

def get_session_user(tok: str):
    if not tok:
        return None
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT username FROM sessions WHERE token = ?", (tok,)).fetchone()
    return row[0] if row else None

def delete_session(tok: str):
    if tok:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (tok,))

def register_user(user: str, pw: str):
    u = user.strip().lower()
    if len(u) < 3 or len(pw) < 4:
        return False, "Handle must be 3+ chars and passcode 4+ chars."
    with sqlite3.connect(DB_PATH) as conn:
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (u,)).fetchone():
            return False, "Handle already exists. Use Sign In."
        salt = os.urandom(16).hex()
        conn.execute("INSERT INTO users VALUES (?, ?, ?)", (u, hash_pw(pw, salt), salt))
        msg = f"Welcome to **Vice City Neural Link**, Agent **{u.upper()}**. Your chat block is active."
        conn.execute("INSERT INTO history (username, role, content) VALUES (?, ?, ?)", (u, "assistant", msg))
    return True, "OK"

def auth_user(user: str, pw: str) -> bool:
    u = user.strip().lower()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT pw, salt FROM users WHERE username = ?", (u,)).fetchone()
    return bool(row and hash_pw(pw, row[1]) == row[0])

def load_history(user: str):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT role, content, ts FROM history WHERE username = ? ORDER BY id ASC", (user,)).fetchall()
    return [{"role": r[0], "content": r[1], "ts": r[2]} for r in rows]

def save_msg(user: str, role: str, content: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO history (username, role, content) VALUES (?, ?, ?)", (user, role, content))

def wipe_history(user: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM history WHERE username = ?", (user,))
        msg = f"Memory block wiped for Agent **{user.upper()}**. Fresh slate ready."
        conn.execute("INSERT INTO history (username, role, content) VALUES (?, ?, ?)", (user, "assistant", msg))

init_db()

def svg_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()

AI_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    '<circle cx="50" cy="50" r="48" fill="#180a33" stroke="#00f2fe" stroke-width="4"/>'
    '<path d="M22 48 Q20 82 30 90 L70 90 Q80 82 78 48 Z" fill="#ff71ce"/>'
    '<circle cx="50" cy="48" r="20" fill="#ffece4"/>'
    '<circle cx="43" cy="48" r="4" fill="#00f2fe"/><circle cx="57" cy="48" r="4" fill="#00f2fe"/>'
    '<path d="M46 58 Q50 62 54 58" stroke="#d64579" stroke-width="2" fill="none"/>'
    '<path d="M28 46 Q30 20 50 20 Q70 20 72 46 Q62 32 50 42 Q38 32 28 46 Z" fill="#b967ff"/>'
    '</svg>'
)
USER_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    '<circle cx="50" cy="50" r="48" fill="#180a33" stroke="#ff007f" stroke-width="4"/>'
    '<circle cx="50" cy="38" r="15" fill="#00f2fe"/>'
    '<path d="M24 82 Q50 62 76 82" fill="#ff007f"/>'
    '</svg>'
)
AI_AVATAR = svg_uri(AI_SVG)
USER_AVATAR = svg_uri(USER_SVG)

if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "🌙 Dark Mode"
if "auth" not in st.session_state:
    st.session_state.auth = False
if "user" not in st.session_state:
    st.session_state.user = None
if "msgs" not in st.session_state:
    st.session_state.msgs = []

if not st.session_state.auth:
    tok = st.query_params.get("session", "")
    saved_u = get_session_user(tok)
    if saved_u:
        st.session_state.auth = True
        st.session_state.user = saved_u
        st.session_state.msgs = load_history(saved_u)
    elif tok:
        st.query_params.clear()

# ---------------------------------------------------------------------------
# UI THEME  (visual layer only: CSS, no logic here)
# Vice City sunset + synthwave 3D grid floor, extruded "slab" cards,
# keycap buttons, and high-contrast text on every surface.
# ---------------------------------------------------------------------------
THEME_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Rajdhani:wght@500;600;700&display=swap');

/* ---------- base + 3D world backdrop ---------- */
html, body { background: var(--bg) !important; }
.stApp {
  background: var(--sky) fixed !important;
  color: var(--fg) !important;
  font-family: 'Rajdhani', 'Segoe UI', system-ui, sans-serif;
  font-size: 18px !important;
}
[data-testid='stAppViewContainer'] { background: transparent !important; position: relative; z-index: 1; }
header[data-testid='stHeader'] { background: transparent !important; }
[data-testid='stMain'], .block-container { position: relative; z-index: 1; }

/* retro sun with horizon slices */
.stApp::after {
  content: ""; position: fixed; z-index: 0; pointer-events: none;
  left: 50%; bottom: 27vh; width: min(44vw, 440px); aspect-ratio: 1;
  transform: translateX(-50%); border-radius: 50%;
  background: linear-gradient(180deg, #ffe14d 0%, #ff9a3c 38%, #ff2d95 100%);
  opacity: var(--sun-op);
  -webkit-mask-image: linear-gradient(to bottom, #000 0 52%, transparent 52% 56%, #000 56% 64%, transparent 64% 69%, #000 69% 76%, transparent 76% 82%, #000 82% 88%, transparent 88% 95%, #000 95%);
          mask-image: linear-gradient(to bottom, #000 0 52%, transparent 52% 56%, #000 56% 64%, transparent 64% 69%, #000 69% 76%, transparent 76% 82%, #000 82% 88%, transparent 88% 95%, #000 95%);
}
/* perspective neon grid floor */
.stApp::before {
  content: ""; position: fixed; z-index: 0; pointer-events: none;
  left: -60%; right: -60%; bottom: -8vh; height: 52vh;
  background-image:
    linear-gradient(var(--grid) 2px, transparent 2px),
    linear-gradient(90deg, var(--grid) 2px, transparent 2px);
  background-size: 72px 72px;
  transform: perspective(480px) rotateX(63deg);
  transform-origin: 50% 100%;
  -webkit-mask-image: linear-gradient(to top, #000 25%, transparent 96%);
          mask-image: linear-gradient(to top, #000 25%, transparent 96%);
  animation: gridrun 3.2s linear infinite;
}
@keyframes gridrun { from { background-position: 0 0; } to { background-position: 0 72px; } }

/* ---------- typography ---------- */
p, li, label, .stMarkdown p, [data-testid='stMarkdownContainer'] {
  color: var(--fg) !important; font-size: 1.15rem !important; line-height: 1.55 !important;
}
span, div { color: var(--fg) !important; }
[data-testid='stIconMaterial'] { font-family: 'Material Symbols Rounded' !important; }
h1, h2, h3, h4 {
  font-family: 'Orbitron', 'Segoe UI', sans-serif !important;
  color: var(--fg) !important; letter-spacing: .04em;
  text-shadow: 0 2px 0 var(--edge), 0 0 18px var(--glow);
}
code { color: var(--cyan) !important; background: var(--card-solid) !important; border: 1px solid var(--cyan); border-radius: 6px; }

/* ---------- 3D slab cards ---------- */
.card {
  background: var(--card); backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  border: 2px solid var(--cyan); border-left: 8px solid var(--pink); border-radius: 16px;
  padding: 16px 22px; margin-bottom: 18px;
  box-shadow: 0 2px 0 var(--edge), 0 5px 0 var(--edge), 0 8px 0 var(--edge-deep), 0 18px 34px var(--shadow), 0 0 26px var(--glow);
  transform: perspective(1000px) rotateX(2deg);
  transition: transform .25s ease, box-shadow .25s ease;
}
.card:hover {
  transform: perspective(1000px) rotateX(0deg) translateY(-4px);
  box-shadow: 0 2px 0 var(--edge), 0 5px 0 var(--edge), 0 8px 0 var(--edge-deep), 0 26px 40px var(--shadow), 0 0 36px var(--glow);
}
.card h3 { margin: 4px 0 0 0; font-size: 1.5rem !important; }
.title {
  font-family: 'Orbitron', sans-serif !important; font-weight: 900 !important;
  font-size: 2.2rem !important; letter-spacing: .06em;
  background: var(--title-grad); -webkit-background-clip: text; background-clip: text;
  color: transparent !important; -webkit-text-fill-color: transparent;
  filter: drop-shadow(0 3px 0 var(--edge)) drop-shadow(0 0 14px var(--glow));
}
.sub {
  font-family: 'Orbitron', sans-serif !important; font-size: 1rem !important; font-weight: 700 !important;
  letter-spacing: .14em; color: var(--cyan) !important;
}

/* ---------- inputs ---------- */
div[data-baseweb='select'] > div, div[data-baseweb='input'] > div, input, textarea {
  background: var(--card-solid) !important; color: var(--fg) !important;
  border: 2px solid var(--cyan) !important; border-radius: 10px !important;
  font-family: 'Rajdhani', sans-serif !important; font-size: 1.1rem !important; font-weight: 600 !important;
  box-shadow: inset 0 3px 8px var(--shadow);
}
input::placeholder, textarea::placeholder { color: var(--muted) !important; opacity: 1 !important; }
div[data-baseweb='input'] > div:focus-within, div[data-baseweb='select'] > div:focus-within, textarea:focus {
  border-color: var(--pink) !important; box-shadow: 0 0 0 3px var(--glow), inset 0 3px 8px var(--shadow) !important;
}
div[data-baseweb='popover'] ul, div[data-baseweb='popover'] [role='listbox'], div[data-baseweb='menu'] {
  background: var(--card-solid) !important; border: 2px solid var(--cyan) !important; border-radius: 10px !important;
}
div[data-baseweb='popover'] li, div[data-baseweb='popover'] li * { color: var(--fg) !important; background: transparent !important; }
div[data-baseweb='popover'] li:hover, div[data-baseweb='popover'] li[aria-selected='true'] { background: var(--glow) !important; }

/* chat input dock */
[data-testid='stBottom'], [data-testid='stBottom'] > div { background: transparent !important; }
[data-testid='stChatInput'] {
  background: var(--card-solid) !important; border: 2px solid var(--cyan) !important; border-radius: 16px !important;
  box-shadow: 0 4px 0 var(--edge-deep), 0 14px 30px var(--shadow), 0 0 22px var(--glow);
}
[data-testid='stChatInput'] textarea { border: none !important; box-shadow: none !important; background: transparent !important; }
[data-testid='stChatInput'] button { background: var(--pink) !important; border-radius: 10px !important; }
[data-testid='stChatInput'] button svg { fill: #ffffff !important; color: #ffffff !important; }

/* ---------- chat bubbles: extruded 3D slabs ---------- */
div[data-testid='stChatMessage'] {
  background: var(--card) !important; backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  border: 2px solid var(--pink) !important; border-radius: 16px !important; padding: 16px !important; margin-bottom: 18px !important;
  box-shadow: 4px 4px 0 var(--edge), 8px 8px 0 var(--edge-deep), 0 20px 34px var(--shadow), 0 0 22px var(--glow);
  transform: perspective(1000px) rotateY(-1.4deg);
  transition: transform .25s ease, box-shadow .25s ease;
}
div[data-testid='stChatMessage']:has(img[alt='user avatar']) {
  border-color: var(--cyan) !important; transform: perspective(1000px) rotateY(1.4deg);
  box-shadow: -4px 4px 0 var(--edge), -8px 8px 0 var(--edge-deep), 0 20px 34px var(--shadow), 0 0 22px var(--glow-cyan);
}
div[data-testid='stChatMessage']:has([data-testid='stChatMessageAvatarUser']) {
  border-color: var(--cyan) !important; transform: perspective(1000px) rotateY(1.4deg);
  box-shadow: -4px 4px 0 var(--edge), -8px 8px 0 var(--edge-deep), 0 20px 34px var(--shadow), 0 0 22px var(--glow-cyan);
}
div[data-testid='stChatMessage']:hover { transform: perspective(1000px) rotateY(0deg) translateY(-3px); }
div[data-testid='stChatMessage'] img { border-radius: 50%; box-shadow: 0 0 14px var(--glow); }

/* typing indicator */
.typing {
  display: inline-flex; align-items: center; gap: 10px; padding: 10px 16px; border-radius: 12px;
  background: var(--card-solid); border: 2px solid var(--cyan); font-family: 'Orbitron', sans-serif; font-weight: 700;
  letter-spacing: .08em; box-shadow: 0 4px 0 var(--edge-deep), 0 0 18px var(--glow-cyan);
}
.dot { width: 10px; height: 10px; border-radius: 50%; background: var(--pink); box-shadow: 0 0 10px var(--pink); animation: blink 1s infinite alternate; }
@keyframes blink { from { opacity: .3; transform: scale(.85); } to { opacity: 1; transform: scale(1.1); } }

/* ---------- keycap buttons ---------- */
.stButton > button, div[data-testid='stFormSubmitButton'] > button {
  background: linear-gradient(180deg, #e0147a 0%, #8a1fd1 100%) !important; color: #ffffff !important;
  border: 2px solid var(--cyan) !important; border-radius: 12px !important;
  font-family: 'Orbitron', sans-serif !important; font-weight: 700 !important; letter-spacing: .06em;
  box-shadow: 0 6px 0 #4b1286, 0 12px 20px var(--shadow), 0 0 18px var(--glow);
  transition: transform .12s ease, box-shadow .12s ease, filter .12s ease;
}
.stButton > button p, div[data-testid='stFormSubmitButton'] > button p { color: #ffffff !important; font-family: 'Orbitron', sans-serif !important; font-size: 1rem !important; }
.stButton > button:hover, div[data-testid='stFormSubmitButton'] > button:hover {
  transform: translateY(-2px); filter: brightness(1.12); border-color: var(--cyan) !important;
  box-shadow: 0 8px 0 #4b1286, 0 16px 24px var(--shadow), 0 0 26px var(--glow);
}
.stButton > button:active, div[data-testid='stFormSubmitButton'] > button:active {
  transform: translateY(5px); box-shadow: 0 1px 0 #4b1286, 0 4px 8px var(--shadow);
}

/* ---------- tabs, expanders, containers, alerts ---------- */
button[data-baseweb='tab'] { font-family: 'Orbitron', sans-serif !important; font-weight: 700 !important; }
button[data-baseweb='tab'] p { color: var(--fg) !important; font-family: 'Orbitron', sans-serif !important; font-size: 1rem !important; }
button[data-baseweb='tab'][aria-selected='true'] p { color: var(--cyan) !important; }
div[data-baseweb='tab-highlight'] { background: var(--pink) !important; height: 4px !important; }
div[data-baseweb='tab-border'] { background: var(--edge) !important; }
[data-testid='stExpander'] details {
  background: var(--card) !important; border: 2px solid var(--cyan) !important; border-radius: 14px !important;
  box-shadow: 0 4px 0 var(--edge-deep), 0 12px 24px var(--shadow);
}
[data-testid='stExpander'] summary, [data-testid='stExpander'] summary * { color: var(--fg) !important; font-weight: 700 !important; }
[data-testid='stVerticalBlockBorderWrapper']:has(> div > [data-testid='stVerticalBlock']) { border-color: var(--cyan) !important; }
div[data-testid='stAlert'] {
  background: var(--card-solid) !important; border: 2px solid var(--pink) !important; border-radius: 14px !important;
  box-shadow: 0 4px 0 var(--edge-deep), 0 0 18px var(--glow);
}
div[data-testid='stAlert'] * { color: var(--fg) !important; }

/* ---------- scrollbar + focus + motion ---------- */
::-webkit-scrollbar { width: 12px; height: 12px; }
::-webkit-scrollbar-track { background: var(--card-solid); }
::-webkit-scrollbar-thumb { background: linear-gradient(180deg, var(--pink), var(--cyan)); border-radius: 8px; border: 2px solid var(--card-solid); }
:focus-visible { outline: 3px solid var(--cyan) !important; outline-offset: 2px; }

@media (max-width: 760px) {
  .stApp::after { width: 62vw; bottom: 30vh; }
  .card, div[data-testid='stChatMessage'], div[data-testid='stChatMessage']:has(img[alt='user avatar']) { transform: none; }
  .title { font-size: 1.5rem !important; }
}
@media (prefers-reduced-motion: reduce) {
  .stApp::before, .dot { animation: none !important; }
  .card, div[data-testid='stChatMessage'], .stButton > button { transition: none !important; }
}
"""

def apply_theme(mode: str):
    dark = mode == "🌙 Dark Mode"
    if dark:
        v = {
            "bg": "#0b0618",
            "sky": "linear-gradient(180deg,#0b0618 0%,#1d0b3f 45%,#4a1066 70%,#a3135f 100%)",
            "card": "rgba(24,10,51,0.88)", "card-solid": "#180a33",
            "fg": "#ffffff", "muted": "#cdb9f2",
            "pink": "#ff4da6", "cyan": "#00f2fe",
            "edge": "#6a1fc2", "edge-deep": "#2a0b57",
            "glow": "rgba(255,77,166,0.40)", "glow-cyan": "rgba(0,242,254,0.35)",
            "shadow": "rgba(0,0,0,0.60)", "grid": "rgba(0,242,254,0.55)", "sun-op": "0.55",
            "title-grad": "linear-gradient(90deg,#ffe14d 0%,#ff4da6 50%,#b967ff 100%)",
        }
    else:
        v = {
            "bg": "#fff4fa",
            "sky": "linear-gradient(180deg,#fff4fa 0%,#ffe0f0 50%,#ffd6c2 100%)",
            "card": "rgba(255,255,255,0.93)", "card-solid": "#ffffff",
            "fg": "#1a0b2e", "muted": "#5b4a7a",
            "pink": "#c2005a", "cyan": "#026aa7",
            "edge": "#c58be8", "edge-deep": "#9a5fc4",
            "glow": "rgba(194,0,90,0.25)", "glow-cyan": "rgba(2,106,167,0.28)",
            "shadow": "rgba(60,20,90,0.30)", "grid": "rgba(138,31,209,0.40)", "sun-op": "0.40",
            "title-grad": "linear-gradient(90deg,#c2005a 0%,#8a1fd1 100%)",
        }
    root = ":root{" + "".join(f"--{k}:{val};" for k, val in v.items()) + "}"
    st.markdown("<style>" + root + THEME_CSS + "</style>", unsafe_allow_html=True)

h1, h2 = st.columns([4, 1.3])
with h2:
    st.session_state.theme_mode = st.selectbox("THEME", ["🌙 Dark Mode", "☀️ Light Mode"], index=0 if st.session_state.theme_mode == "🌙 Dark Mode" else 1, label_visibility="collapsed")
apply_theme(st.session_state.theme_mode)

with h1:
    st.markdown('<div class="card"><div class="title">VICE AI // LEONIDA NET</div><div class="sub">LANGCHAIN × OPENROUTER NEURAL INTERFACE</div></div>', unsafe_allow_html=True)

api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
if not api_key:
    try:
        api_key = st.secrets.get("OPENROUTER_API_KEY", "").strip()
    except Exception:
        api_key = ""
if not api_key:
    api_key = st.session_state.get("manual_api_key", "").strip()

if not api_key or "PASTE_YOUR" in api_key:
    st.warning("🔑 **OpenRouter API Key Required:** Enter your key below for this session (never saved to GitHub) or add it to `.env` / Streamlit Secrets.")
    entered_key = st.text_input("OpenRouter API Key", type="password", placeholder="sk-or-v1-...")
    if st.button("ACTIVATE NEURAL LINK"):
        st.session_state.manual_api_key = entered_key.strip()
        st.rerun()

elif not st.session_state.auth:
    _, mid, _ = st.columns([1, 1.6, 1])
    with mid:
        st.markdown('<div class="card"><h3>🔐 AGENT ACCESS TERMINAL</h3><p>Sign in or create an agent handle to open your saved chat block.</p></div>', unsafe_allow_html=True)
        t_in, t_up = st.tabs(["⚡ SIGN IN", "🆕 CREATE AGENT ID"])
        with t_in:
            with st.form("login_f"):
                u_in = st.text_input("Agent Handle")
                p_in = st.text_input("Passcode", type="password")
                if st.form_submit_button("ENTER VICE CITY NET", use_container_width=True):
                    if auth_user(u_in, p_in):
                        clean = u_in.strip().lower()
                        st.query_params["session"] = create_session(clean)
                        st.session_state.auth = True
                        st.session_state.user = clean
                        st.session_state.msgs = load_history(clean)
                        st.rerun()
                    else:
                        st.error("Invalid handle or passcode.")
        with t_up:
            with st.form("reg_f"):
                u_new = st.text_input("Choose Agent Handle (3+ chars)")
                p_new = st.text_input("Create Passcode (4+ chars)", type="password")
                if st.form_submit_button("INITIALIZE AGENT BLOCK", use_container_width=True):
                    ok, msg = register_user(u_new, p_new)
                    if ok:
                        clean = u_new.strip().lower()
                        st.query_params["session"] = create_session(clean)
                        st.session_state.auth = True
                        st.session_state.user = clean
                        st.session_state.msgs = load_history(clean)
                        st.rerun()
                    else:
                        st.error(msg)

else:
    user = st.session_state.user
    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
    with c1:
        page = st.selectbox("NAV", ["💬 Neural Chat Interface", "📊 Telemetry Dashboard"], label_visibility="collapsed")
    MODELS = {
        "OpenRouter Auto Free Router": "openrouter/free",
        "Meta Llama 3.3 70B (Free)": "meta-llama/llama-3.3-70b-instruct:free",
        "Google Gemma 2 9B (Free)": "google/gemma-2-9b-it:free",
        "Mistral 7B Instruct (Free)": "mistralai/mistral-7b-instruct:free",
    }
    with c2:
        model_id = MODELS[st.selectbox("MODEL", list(MODELS.keys()), label_visibility="collapsed")]
    with c3:
        if st.button("WIPE BLOCK", use_container_width=True):
            wipe_history(user)
            st.session_state.msgs = load_history(user)
            st.rerun()
    with c4:
        if st.button("LOGOUT", use_container_width=True):
            delete_session(st.query_params.get("session", ""))
            st.query_params.clear()
            st.session_state.auth = False
            st.session_state.user = None
            st.session_state.msgs = []
            st.rerun()

    tokens = sum(int(len(m["content"].split()) * 1.3) for m in st.session_state.msgs)

    if page == "📊 Telemetry Dashboard":
        st.markdown(f"### ⚡ TELEMETRY HUD // AGENT: `{user.upper()}`")
        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f'<div class="card"><b>AGENT</b><br><h3>{user.upper()}</h3></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="card"><b>MESSAGES</b><br><h3>{len(st.session_state.msgs)}</h3></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="card"><b>EST. TOKENS</b><br><h3>{tokens}</h3></div>', unsafe_allow_html=True)
        masked = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "SECURED"
        m4.markdown(f'<div class="card"><b>LEAK SHIELD</b><br><h3>{masked}</h3></div>', unsafe_allow_html=True)

        st.markdown(f"#### 🗄️ {user.upper()}'S SAVED CHAT MEMORY BLOCK")
        with st.container(border=True):
            for idx, item in enumerate(st.session_state.msgs, 1):
                tag = "🧑 AGENT" if item["role"] == "user" else "🤖 VICE AI"
                st.markdown(f"**`#{idx}` [{item.get('ts', 'SESSION')}] {tag}:** {item['content']}")
    else:
        st.markdown(f'<div class="card">🗄️ <b>MEMORY BLOCK:</b> AGENT [{user.upper()}] | SAVED MESSAGES: {len(st.session_state.msgs)} | REFRESH-LOCKED</div>', unsafe_allow_html=True)
        with st.expander(f"📂 View {user.upper()}'s Saved History Block ({len(st.session_state.msgs)} messages)"):
            for idx, m in enumerate(st.session_state.msgs, 1):
                who = user.upper() if m["role"] == "user" else "VICE AI"
                st.markdown(f"`[{idx}]` **{who}:** {m['content']}")

        for m in st.session_state.msgs:
            with st.chat_message(m["role"], avatar=AI_AVATAR if m["role"] == "assistant" else USER_AVATAR):
                st.markdown(m["content"])

        if prompt := st.chat_input(f"Transmit as {user.upper()} to Vice AI..."):
            save_msg(user, "user", prompt)
            st.session_state.msgs.append({"role": "user", "content": prompt})
            with st.chat_message("user", avatar=USER_AVATAR):
                st.markdown(prompt)

            with st.chat_message("assistant", avatar=AI_AVATAR):
                holder = st.empty()
                holder.markdown('<div class="typing"><span class="dot"></span><span>VICE AI IS TYPING...</span></div>', unsafe_allow_html=True)
                lc_msgs = [SystemMessage(content=f"You are Vice AI, a sharp futuristic assistant speaking with Agent {user}.")]
                for m in st.session_state.msgs:
                    lc_msgs.append(HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"]))
                try:
                    llm = ChatOpenAI(model=model_id, openai_api_key=api_key, openai_api_base="https://openrouter.ai/api/v1", temperature=0.7, streaming=True)
                    reply = ""
                    first = True
                    for chunk in llm.stream(lc_msgs):
                        tok = chunk.content or ""
                        if first and tok:
                            time.sleep(0.35)
                            first = False
                        reply += tok
                        holder.markdown(reply + "▌")
                    holder.markdown(reply)
                    save_msg(user, "assistant", reply)
                    st.session_state.msgs.append({"role": "assistant", "content": reply})
                except Exception as e:
                    holder.empty()
                    st.error(f"Signal disrupted: {e}")
