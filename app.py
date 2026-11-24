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
    page_title="VICE AI // LEONIDA NET",
    page_icon="🌴",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------------------------------------------------------
# LOCAL SQLITE DATABASE (USERS, PERSISTENT SESSIONS & ISOLATED CHAT BLOCKS)
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
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users(username)
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

def create_session_token(username: str) -> str:
    token = os.urandom(24).hex()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO sessions (token, username) VALUES (?, ?)", (token, username))
    conn.commit()
    conn.close()
    return token

def get_user_from_token(token: str) -> str | None:
    if not token:
        return None
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username FROM sessions WHERE token = ?", (token,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def delete_session_token(token: str):
    if not token:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

def register_user(username: str, password: str) -> tuple[bool, str]:
    username = username.strip().lower()
    if len(username) < 3 or len(password) < 4:
        return False, "Username must be at least 3 characters and password at least 4 characters."
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE username = ?", (username,))
    if c.fetchone():
        conn.close()
        return False, "Agent handle already exists. Switch to Sign In."
    salt = os.urandom(16).hex()
    pw_hash = hash_password(password, salt)
    c.execute("INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)", (username, pw_hash, salt))
    welcome_msg = (
        f"Welcome to **Vice City Neural Link**, Agent **{username.upper()}**. "
        "Your encrypted chat memory block is active. How can I help you today?"
    )
    c.execute("INSERT INTO chat_history (username, role, content) VALUES (?, ?, ?)", (username, "assistant", welcome_msg))
    conn.commit()
    conn.close()
    return True, "Account initialized!"

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
    reset_msg = f"Memory block wiped for Agent **{username.upper()}**. Fresh slate—what's next?"
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
  <circle cx="50" cy="50" r="48" fill="#1a0b2e" stroke="#ff007f" stroke-width="4"/>
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
# SESSION STATE & PERSISTENT REFRESH RESTORATION
# -----------------------------------------------------------------------------
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "🌙 Dark Mode"
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# Restore session automatically on browser refresh via URL query parameter
if not st.session_state.authenticated:
    url_token = st.query_params.get("session", "")
    restored_user = get_user_from_token(url_token)
    if restored_user:
        st.session_state.authenticated = True
        st.session_state.current_user = restored_user
        st.session_state.
