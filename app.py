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
    c.execute
