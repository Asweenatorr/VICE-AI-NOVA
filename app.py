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

def apply_theme(mode: str):
    dark = mode == "🌙 Dark Mode"
    bg = "#0f0722" if dark else "#f4f6fb"
    card = "#1b0e36" if dark else "#ffffff"
    fg = "#ffffff" if dark else "#111827"
    pink = "#ff4da6" if dark else "#d90467"
    cyan = "#00f2fe" if dark else "#026aa7"
    css = (
        f"<style>:root{{--bg:{bg};--card:{card};--fg:{fg};--pink:{pink};--cyan:{cyan};}}"
        "html,body,[data-testid='stAppViewContainer'],.stApp{background:var(--bg)!important;color:var(--fg)!important;font-size:18px!important;}"
        "p,li,span,label,div,.stMarkdown p{color:var(--fg)!important;font-size:1.1rem!important;line-height:1.6!important;}"
        "h1,h2,h3,h4{color:var(--fg)!important;}"
        ".card{background:var(--card);border:2px solid var(--cyan);border-left:6px solid var(--pink);border-radius:14px;padding:16px 20px;margin-bottom:14px;}"
        ".title{font-size:2rem!important;font-weight:800!important;color:var(--pink)!important;}"
        ".sub{font-size:1.05rem!important;font-weight:700!important;color:var(--cyan)!important;}"
        "div[data-baseweb='select']>div,div[data-baseweb='input']>div,input,textarea{background:var(--card)!important;color:var(--fg)!important;border:2px solid var(--cyan)!important;font-size:1.05rem!important;}"
        "div[data-testid='stChatMessage']{background:var(--card)!important;border:2px solid var(--cyan)!important;border-radius:14px!important;padding:14px!important;margin-bottom:12px!important;}"
        ".typing{display:inline-flex;align-items:center;gap:8px;padding:10px 14px;border-radius:10px;background:var(--card);border:2px solid var(--cyan);font-weight:700;}"
        ".dot{width:9px;height:9px;border-radius:50%;background:var(--pink);animation:blink 1s infinite alternate;}"
        "@keyframes blink{from{opacity:0.3;}to{opacity:1;}}"
        ".stButton>button,div[data-testid='stFormSubmitButton']>button{background:linear-gradient(90deg,var(--pink),#7928ca)!important;color:#fff!important;border:2px solid var(--cyan)!important;border-radius:10px!important;}"
        ".stButton>button p,div[data-testid='stFormSubmitButton']>button p{color:#fff!important;}"
        "</style>"
    )
    st.markdown(css, unsafe_allow_html=True)

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
