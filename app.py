import os
import time
import base64
import hashlib
import sqlite3
import streamlit as st
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# Load environment variables from local .env file
load_dotenv()

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="VICE AI // NEON TERMINAL",
    page_icon="🌴",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------------------------------------------------------
# LOCAL SQLITE DATABASE FOR USER ACCOUNTS & ISOLATED CHAT HISTORY BLOCKS
# -----------------------------------------------------------------------------
DB_PATH = "vice_users.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users(username)
        )
    """)
    conn.commit()
    conn.close()

def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def register_user(username: str, password: str) -> tuple[bool, str]:
    username = username.strip().lower()
    if len(username) < 3 or len(password) < 4:
        return False, "Username must be at least 3 chars and password at least 4 chars."
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE username = ?", (username,))
    if c.fetchone():
        conn.close()
        return False, "Agent handle already exists. Switch to Sign In."
    salt = os.urandom(16).hex()
    pw_hash = hash_password(password, salt)
    c.execute("INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)", (username, pw_hash, salt))
    # Seed welcome message in user's personal chat block
    welcome_msg = f"Welcome to **Vice City Neural Link**, Agent **{username.upper()}**. Your encrypted chat block is active. What's our next move?"
    c.execute("INSERT INTO chat_history (username, role, content) VALUES (?, ?, ?)", (username, "assistant", welcome_msg))
    conn.commit()
    conn.close()
    return True, "Account initialized! Logging you into Leonida Net..."

def authenticate_user(username: str, password: str) -> bool:
    username = username.strip().lower()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT password_hash, salt FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False
    stored_hash, salt = row
    return hash_password(password, salt) == stored_hash

def load_user_history(username: str) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content, timestamp FROM chat_history WHERE username = ? ORDER BY id ASC", (username,))
    rows = c.fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in rows]

def save_user_message(username: str, role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO chat_history (username, role, content) VALUES (?, ?, ?)", (username, role, content))
    conn.commit()
    conn.close()

def wipe_user_history(username: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM chat_history WHERE username = ?", (username,))
    reset_msg = f"Memory block wiped for Agent **{username.upper()}**. Fresh neon slate—where are we headed?"
    c.execute("INSERT INTO chat_history (username, role, content) VALUES (?, ?, ?)", (username, "assistant", reset_msg))
    conn.commit()
    conn.close()

init_db()

# -----------------------------------------------------------------------------
# ANIME FEMALE AVATAR & USER AVATAR (SELF-CONTAINED SVG DATA URIS)
# -----------------------------------------------------------------------------
ANIME_AVATAR_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ff007f"/>
      <stop offset="50%" stop-color="#7928ca"/>
      <stop offset="100%" stop-color="#00f2fe"/>
    </linearGradient>
    <linearGradient id="hairGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#ff71ce"/>
      <stop offset="100%" stop-color="#b967ff"/>
    </linearGradient>
  </defs>
  <circle cx="60" cy="60" r="58" fill="url(#bgGrad)" stroke="#00f2fe" stroke-width="3"/>
  <circle cx="60" cy="60" r="52" fill="#120822"/>
  <path d="M28 55 Q25 95 36 105 L84 105 Q95 95 92 55 Z" fill="url(#hairGrad)"/>
  <path d="M30 108 Q60 92 90 108 L95 115 L25 115 Z" fill="#1f1135" stroke="#00f2fe" stroke-width="2"/>
  <rect x="53" y="76" width="14" height="16" rx="4" fill="#ffe0d2"/>
  <path d="M38 48 Q38 80 60 83 Q82 80 82 48 Q82 28 60 28 Q38 28 38 48 Z" fill="#ffece4"/>
  <ellipse cx="49" cy="56" rx="5.5" ry="6.5" fill="#1a0b2e"/>
  <ellipse cx="71" cy="56" rx="5.5" ry="6.5" fill="#1a0b2e"/>
  <circle cx="49" cy="57" r="3.5" fill="#00f2fe"/>
  <circle cx="71" cy="57" r="3.5" fill="#00f2fe"/>
  <circle cx="47.5" cy="54" r="1.8" fill="#ffffff"/>
  <circle cx="69.5" cy="54" r="1.8" fill="#ffffff"/>
  <ellipse cx="43" cy="64" rx="4" ry="2" fill="#ff71ce" opacity="0.5"/>
  <ellipse cx="77" cy="64" rx="4" ry="2" fill="#ff71ce" opacity="0.5"/>
  <path d="M56 69 Q60 73 64 69" stroke="#d64579" stroke-width="2" fill="none" stroke-linecap="round"/>
  <path d="M34 52 Q36 22 60 22 Q84 22 86 52 Q78 36 70 46 Q64 33 60 47 Q54 33 48 46 Q41 36 34 52 Z" fill="url(#hairGrad)"/>
  <rect x="32" y="46" width="6" height="14" rx="3" fill="#00f2fe"/>
  <rect x="82" y="46" width="6" height="14" rx="3" fill="#ff007f"/>
</svg>
"""

USER_AVATAR_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="48" fill="#0d061a" stroke="#ff007f" stroke-width="3"/>
  <circle cx="50" cy="38" r="16" fill="#00f2fe"/>
  <path d="M22 84 Q50 62 78 84" fill="#ff007f"/>
</svg>
"""

def svg_to_data_uri(svg_str: str) -> str:
    b64 = base64.b64encode(svg_str.strip().encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64}"

AI_AVATAR_URI = svg_to_data_uri(ANIME_AVATAR_SVG)
USER_AVATAR_URI = svg_to_data_uri(USER_AVATAR_SVG)

# -----------------------------------------------------------------------------
# FUTURISTIC GTA 6 / VICE CITY NEON CSS
# -----------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Rajdhani:wght@400;600;700&display=swap');

.stApp {
    background: radial-gradient(circle at 15% 15%, #2b0938 0%, #11051f 45%, #070312 100%);
    color: #f4eaff;
    font-family: 'Rajdhani', sans-serif;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {background: transparent !important;}

/* Neon Title Banner */
.vice-header {
    background: linear-gradient(90deg, rgba(255,0,127,0.18) 0%, rgba(121,40,202,0.22) 50%, rgba(0,242,254,0.18) 100%);
    border: 1px solid rgba(255, 113, 206, 0.45);
    border-radius: 16px;
    padding: 18px 26px;
    margin-bottom: 16px;
    box-shadow: 0 0 25px rgba(255, 0, 127, 0.25), inset 0 0 20px rgba(0, 242, 254, 0.12);
    backdrop-filter: blur(12px);
}

.vice-title {
    font-family: 'Orbitron', sans-serif;
    font-weight: 900;
    font-size: 2.1rem;
    letter-spacing: 3px;
    background: linear-gradient(90deg, #ff71ce, #ff9a5a, #00f2fe);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    text-transform: uppercase;
}

.vice-subtitle {
    font-family: 'Rajdhani', sans-serif;
    font-size: 1.05rem;
    color: #b8e8ff;
    letter-spacing: 1.5px;
    margin-top: 4px;
}

/* Login Box Container */
.login-box {
    background: rgba(20, 9, 43, 0.85);
    border: 1px solid #00f2fe;
    border-top: 4px solid #ff007f;
    border-radius: 18px;
    padding: 28px;
    box-shadow: 0 0 35px rgba(255, 0, 127, 0.25), 0 0 20px rgba(0, 242, 254, 0.2);
    backdrop-filter: blur(14px);
    margin-top: 10px;
}

/* User Memory Block Box inside Chat */
.memory-block-header {
    background: rgba(0, 242, 254, 0.08);
    border: 1px solid rgba(0, 242, 254, 0.35);
    border-left: 4px solid #00f2fe;
    border-radius: 10px;
    padding: 10px 16px;
    margin-bottom: 14px;
    font-family: 'Orbitron', sans-serif;
    font-size: 0.82rem;
    color: #00f2fe;
    letter-spacing: 1px;
}

/* Top Dropdown / Selectbox Styling */
div[data-baseweb="select"] > div {
    background-color: rgba(20, 9, 43, 0.85) !important;
    border: 1px solid #00f2fe !important;
    border-radius: 10px !important;
    color: #ffffff !important;
    box-shadow: 0 0 12px rgba(0, 242, 254, 0.25);
}

/* Text Inputs on Login Screen */
div[data-baseweb="input"] > div {
    background-color: rgba(14, 6, 30, 0.9) !important;
    border: 1px solid rgba(255, 113, 206, 0.5) !important;
    border-radius: 10px !important;
    color: #ffffff !important;
}

/* Dashboard Metric Cards */
.cyber-card {
    background: rgba(22, 10, 44, 0.78);
    border: 1px solid rgba(0, 242, 254, 0.4);
    border-left: 4px solid #ff007f;
    border-radius: 14px;
    padding: 20px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
    margin-bottom: 14px;
}

.cyber-card h3 {
    font-family: 'Orbitron', sans-serif;
    font-size: 0.85rem;
    color: #ff71ce;
    letter-spacing: 1.5px;
    margin-bottom: 6px;
    text-transform: uppercase;
}

.cyber-card p {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.65rem;
    font-weight: 700;
    color: #00f2fe;
    margin: 0;
}

/* Chat Message Bubbles */
div[data-testid="stChatMessage"] {
    background: rgba(23, 11, 46, 0.72);
    border: 1px solid rgba(255, 113, 206, 0.28);
    border-radius: 16px;
    padding: 14px 18px;
    margin-bottom: 12px;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.35);
    backdrop-filter: blur(8px);
}

/* Chat Input Bar */
div[data-testid="stChatInput"] {
    border: 1px solid #ff007f !important;
    border-radius: 14px !important;
    background-color: rgba(16, 7, 34, 0.92) !important;
    box-shadow: 0 0 18px rgba(255, 0, 127, 0.3);
}

/* Custom Typing Animation */
.typing-container {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 8px 14px;
    border-radius: 12px;
    background: rgba(0, 242, 254, 0.08);
    border: 1px solid rgba(0, 242, 254, 0.35);
    color: #00f2fe;
    font-family: 'Orbitron', sans-serif;
    font-size: 0.82rem;
    letter-spacing: 1px;
}

.typing-dots {
    display: inline-flex;
    gap: 5px;
}

.typing-dots span {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ff007f;
    box-shadow: 0 0 8px #ff007f;
    animation: neonPulse 1.2s infinite ease-in-out;
}

.typing-dots span:nth-child(2) {
    animation-delay: 0.2s;
    background: #b967ff;
    box-shadow: 0 0 8px #b967ff;
}

.typing-dots span:nth-child(3) {
    animation-delay: 0.4s;
    background: #00f2fe;
    box-shadow: 0 0 8px #00f2fe;
}

@keyframes neonPulse {
    0%, 80%, 100% {
        transform: scale(0.65);
        opacity: 0.4;
    }
    40% {
        transform: scale(1.2);
        opacity: 1;
    }
}

/* Neon Buttons */
.stButton > button {
    background: linear-gradient(90deg, #ff007f, #7928ca);
    color: white;
    font-family: 'Orbitron', sans-serif;
    font-size: 0.78rem;
    letter-spacing: 1px;
    border: 1px solid #00f2fe;
    border-radius: 10px;
    padding: 8px 14px;
    transition: all 0.25s ease;
}

.stButton > button:hover {
    box-shadow: 0 0 18px rgba(0, 242, 254, 0.7);
    transform: translateY(-1px);
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SESSION STATE INITIALIZATION
# -----------------------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# -----------------------------------------------------------------------------
# API KEY SECURITY CHECK (READ ONLY FROM .ENV / CLOUD SECRETS)
# -----------------------------------------------------------------------------
api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
if not api_key:
    try:
        api_key = st.secrets.get("OPENROUTER_API_KEY", "").strip()
    except Exception:
        api_key = ""

if not api_key or "PASTE_YOUR" in api_key:
    st.error(
        "🔒 **API Key Missing:** Add your regenerated `OPENROUTER_API_KEY` inside your local `.env` file "
        "(or Streamlit Cloud Secrets). Never hardcode keys inside `app.py` before pushing to GitHub."
    )
    st.stop()

# -----------------------------------------------------------------------------
# HEADER BANNER
# -----------------------------------------------------------------------------
st.markdown("""
<div class="vice-header">
    <div class="vice-title">VICE AI // LEONIDA NET</div>
    <div class="vice-subtitle">FUTURISTIC LANGCHAIN × OPENROUTER NEURAL INTERFACE</div>
</div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# GATEKEEPER: LOGIN & REGISTRATION PAGE BEFORE CHAT INTERFACE
# -----------------------------------------------------------------------------
if not st.session_state.authenticated:
    _, center_col, _ = st.columns([1, 1.4, 1])

    with center_col:
        st.markdown("""
        <div class="login-box">
            <h2 style="font-family:'Orbitron',sans-serif; color:#00f2fe; margin-top:0; letter-spacing:2px;">
                🔐 AGENT ACCESS TERMINAL
            </h2>
            <p style="color:#d8b4fe; font-size:1rem; margin-bottom:16px;">
                Sign in or create an agent handle to unlock your dedicated encrypted chat memory block.
            </p>
        </div>
        """, unsafe_allow_html=True)

        tab_login, tab_register = st.tabs(["⚡ SIGN IN", "🆕 CREATE AGENT ID"])

        with tab_login:
            with st.form("login_form"):
                login_user = st.text_input("Agent Handle (Username)", placeholder="e.g. lucia_vc")
                login_pass = st.text_input("Passcode", type="password", placeholder="••••••••")
                submit_login = st.form_submit_button("ENTER VICE CITY NET", use_container_width=True)

                if submit_login:
                    if authenticate_user(login_user, login_pass):
                        clean_user = login_user.strip().lower()
                        st.session_state.authenticated = True
                        st.session_state.current_user = clean_user
                        st.session_state.messages = load_user_history(clean_user)
                        st.rerun()
                    else:
                        st.error("Access Denied: Invalid agent handle or passcode.")

        with tab_register:
            with st.form("register_form"):
                new_user = st.text_input("Choose Agent Handle", placeholder="Min 3 characters")
                new_pass = st.text_input("Create Passcode", type="password", placeholder="Min 4 characters")
                submit_reg = st.form_submit_button("INITIALIZE AGENT BLOCK", use_container_width=True)

                if submit_reg:
                    ok, msg = register_user(new_user, new_pass)
                    if ok:
                        clean_user = new_user.strip().lower()
                        st.session_state.authenticated = True
                        st.session_state.current_user = clean_user
                        st.session_state.messages = load_user_history(clean_user)
                        st.rerun()
                    else:
                        st.error(msg)

    st.stop()

# -----------------------------------------------------------------------------
# AUTHENTICATED ZONE: TOP DROPDOWN NAVIGATION BAR
# -----------------------------------------------------------------------------
current_user = st.session_state.current_user

nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([2, 2, 1, 1])

with nav_col1:
    active_page = st.selectbox(
        "NAVIGATION HUD",
        options=["💬 Neural Chat Interface", "📊 Telemetry Dashboard"],
        index=0,
        label_visibility="collapsed"
    )

FREE_MODELS = {
    "OpenRouter Auto Free Router": "openrouter/free",
    "Meta Llama 3.3 70B (Free)": "meta-llama/llama-3.3-70b-instruct:free",
    "Google Gemma 2 9B (Free)": "google/gemma-2-9b-it:free",
    "Mistral 7B Instruct (Free)": "mistralai/mistral-7b-instruct:free",
}

with nav_col2:
    selected_model_label = st.selectbox(
        "AI CORE MODEL",
        options=list(FREE_MODELS.keys()),
        index=0,
        label_visibility="collapsed"
    )
    selected_model_id = FREE_MODELS[selected_model_label]

with nav_col3:
    if st.button("WIPE BLOCK", use_container_width=True):
        wipe_user_history(current_user)
        st.session_state.messages = load_user_history(current_user)
        st.rerun()

with nav_col4:
    if st.button("LOGOUT", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.session_state.messages = []
        st.rerun()

# -----------------------------------------------------------------------------
# LANGCHAIN OPENROUTER CLIENT BUILDER
# -----------------------------------------------------------------------------
def get_llm(model_name: str, key: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=model_name,
        openai_api_key=key,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0.7,
        streaming=True,
        default_headers={
            "HTTP-Referer": "http://localhost:8501",
            "X-Title": "Vice AI Local Chatbot",
        },
    )

# Calculate user-specific telemetry
user_prompts_count = sum(1 for m in st.session_state.messages if m["role"] == "user")
est_tokens = sum(int(len(m["content"].split()) * 1.3) for m in st.session_state.messages)

# -----------------------------------------------------------------------------
# PAGE 1: TELEMETRY DASHBOARD & USER SAVED BLOCK INSPECTOR
# -----------------------------------------------------------------------------
if active_page == "📊 Telemetry Dashboard":
    st.markdown(f"### ⚡ TELEMETRY HUD // AGENT: `{current_user.upper()}`")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="cyber-card">
            <h3>Active Agent</h3>
            <p>{current_user.upper()}</p>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="cyber-card">
            <h3>Saved Block Messages</h3>
            <p>{len(st.session_state.messages)}</p>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="cyber-card">
            <h3>Est. Block Tokens</h3>
            <p>{est_tokens}</p>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "SECURED"
        st.markdown(f"""
        <div class="cyber-card">
            <h3>GitHub Leak Shield</h3>
            <p style="font-size:1.05rem; padding-top:8px;">ACTIVE ({masked_key})</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f"#### 🗄️ {current_user.upper()}'S PERSISTENT CHAT MEMORY BLOCK")
    with st.container(border=True):
        for idx, item in enumerate(st.session_state.messages, start=1):
            role_tag = "🧑 AGENT" if item["role"] == "user" else "🤖 VICE AI"
            ts = item.get("timestamp", "SESSION")
            st.markdown(f"**`#{idx}` [{ts}] {role_tag}:** {item['content']}")

# -----------------------------------------------------------------------------
# PAGE 2: NEURAL CHAT INTERFACE (WITH DEDICATED USER HISTORY BLOCK)
# -----------------------------------------------------------------------------
else:
    st.markdown(f"""
    <div class="memory-block-header">
        🗄️ DEDICATED MEMORY BLOCK: AGENT [{current_user.upper()}] &nbsp;|&nbsp;
        STORED TRANSMISSIONS: {len(st.session_state.messages)} &nbsp;|&nbsp;
        STATUS: AUTO-SAVING TO ISOLATED BLOCK
    </div>
    """, unsafe_allow_html=True)

    # Dedicated collapsible block showing the user's saved history log
    with st.expander(f"📂 View {current_user.upper()}'s Saved History Block ({len(st.session_state.messages)} messages)", expanded=False):
        for idx, msg in enumerate(st.session_state.messages, start=1):
            speaker = current_user.upper() if msg["role"] == "user" else "VICE AI"
            st.markdown(f"`[{idx}]` **{speaker}:** {msg['content']}")

    # Main Chat Feed for the logged-in user
    for msg in st.session_state.messages:
        avatar = AI_AVATAR_URI if msg["role"] == "assistant" else USER_AVATAR_URI
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # User prompt input
    if user_prompt := st.chat_input(f"Transmit as {current_user.upper()} to Vice AI..."):
        # Save & append user message to this user's isolated DB block
        save_user_message(current_user, "user", user_prompt)
        st.session_state.messages.append({"role": "user", "content": user_prompt})

        with st.chat_message("user", avatar=USER_AVATAR_URI):
            st.markdown(user_prompt)

        # Render AI response with typing animation + streaming
        with st.chat_message("assistant", avatar=AI_AVATAR_URI):
            typing_placeholder = st.empty()
            typing_placeholder.markdown("""
            <div class="typing-container">
                <div class="typing-dots">
                    <span></span><span></span><span></span>
                </div>
                <span>VICE AI IS TYPING...</span>
            </div>
            """, unsafe_allow_html=True)

            lc_messages = [
                SystemMessage(
                    content=(
                        f"You are Vice AI, a sharp, stylish, futuristic AI assistant inspired by Vice City. "
                        f"You are currently speaking with Agent {current_user}. Keep responses helpful, clear, and engaging."
                    )
                )
            ]
            for m in st.session_state.messages:
                if m["role"] == "user":
                    lc_messages.append(HumanMessage(content=m["content"]))
                else:
                    lc_messages.append(AIMessage(content=m["content"]))

            try:
                llm = get_llm(selected_model_id, api_key)
                full_response = ""
                first_chunk = True

                for chunk in llm.stream(lc_messages):
                    token = chunk.content or ""
                    if first_chunk and token:
                        time.sleep(0.35)
                        first_chunk = False
                    full_response += token
                    typing_placeholder.markdown(full_response + "▌")

                typing_placeholder.markdown(full_response)
                save_user_message(current_user, "assistant", full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})

            except Exception as e:
                typing_placeholder.empty()
                st.error(f"Signal disrupted: {e}")
