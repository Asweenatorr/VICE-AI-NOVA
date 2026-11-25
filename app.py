import os
import time
import base64
import hashlib
import sqlite3
import streamlit as st
import streamlit.components.v1 as components
import re
import io
import html
import httpx
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

# ---------------------------------------------------------------------------
# TOOLKIT HELPERS (PDF reading, image generation, model catalogue, rendering)
# ---------------------------------------------------------------------------
IMG_DIR = "generated_images"
os.makedirs(IMG_DIR, exist_ok=True)
IMG_TAG = re.compile(r"\[\[IMG:([\w\-.]+)\]\]")
OR_BASE = "https://openrouter.ai/api/v1"

PERSONAS = {
    "Vice AI (default)": None,
    "Code Mentor": "You are also a patient senior software engineer: explain clearly, show short code examples and point out pitfalls.",
    "Creative Writer": "You are also an imaginative writer: use vivid language, strong voice and fresh ideas.",
    "Study Tutor": "You are also a friendly tutor: break topics into simple steps, give examples and check understanding.",
    "Concise Analyst": "You are also a sharp analyst: answer briefly, lead with the conclusion, then give key evidence.",
    "Custom": None,
}
LANGS = ["Auto", "English", "Hindi", "Bengali", "Spanish", "French", "German", "Japanese", "Arabic", "Portuguese"]

def extract_pdf(data: bytes, limit: int = 60000):
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", 0, "pypdf is not installed. Run: pip install pypdf"
    try:
        reader = PdfReader(io.BytesIO(data))
        chunks, total = [], 0
        for pg in reader.pages:
            t = pg.extract_text() or ""
            chunks.append(t)
            total += len(t)
            if total >= limit:
                break
        text = "\n".join(chunks)[:limit]
        return text, len(reader.pages), (None if text.strip() else "No selectable text found (scanned PDFs are not supported).")
    except Exception as e:
        return "", 0, f"Could not read PDF: {e}"

@st.cache_data(ttl=3600, show_spinner=False)
def load_models(query: str = ""):
    try:
        r = httpx.get(f"{OR_BASE}/models{query}", timeout=15)
        r.raise_for_status()
        out = []
        for m in r.json().get("data", []):
            arch = m.get("architecture") or {}
            try:
                free = m["id"].endswith(":free") or float((m.get("pricing") or {}).get("prompt", 1)) == 0
            except Exception:
                free = False
            out.append({"id": m["id"], "name": m.get("name", m["id"]), "ctx": m.get("context_length") or 0,
                        "inp": arch.get("input_modalities") or [], "out": arch.get("output_modalities") or [], "free": free})
        return out
    except Exception:
        return []

def _opts(models):
    free = sorted([m for m in models if m["free"]], key=lambda m: -m["ctx"])[:15]
    paid = sorted([m for m in models if not m["free"]], key=lambda m: -m["ctx"])[:15]
    out = {}
    for m in free + paid:
        lab = m["name"] + (" (Free)" if m["free"] else "")
        if lab in out:
            lab = f"{lab} [{m['id']}]"
        out[lab] = m["id"]
    return out

def pdf_model_options():
    opts = {"OpenRouter Auto Free Router": "openrouter/free"}
    opts.update(_opts([m for m in load_models("") if "text" in m["out"] and m["id"] != "openrouter/free"]))
    return opts

def vision_model_options():
    opts = _opts([m for m in load_models("") if "image" in m["inp"] and "text" in m["out"]])
    return opts or {"Google Gemini 2.5 Flash": "google/gemini-2.5-flash"}

def image_model_options():
    ms = load_models("?output_modalities=image")
    opts = _opts(ms)
    mods = {m["id"]: m["out"] for m in ms}
    if not opts:
        opts = {"Google Gemini 2.5 Flash Image": "google/gemini-2.5-flash-image"}
        mods = {"google/gemini-2.5-flash-image": ["image", "text"]}
    return opts, mods

def generate_image(key: str, model: str, modalities, prompt: str, ratio: str):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "modalities": modalities}
    if ratio != "Auto":
        body["image_config"] = {"aspect_ratio": ratio}
    r = httpx.post(f"{OR_BASE}/chat/completions", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=body, timeout=180)
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code}: {r.text[:300]}")
    msg = r.json()["choices"][0]["message"]
    imgs = msg.get("images") or []
    if not imgs:
        return None, "png", (msg.get("content") or "")
    url = imgs[0]["image_url"]["url"]
    if url.startswith("data:"):
        head, b64 = url.split(",", 1)
        data = base64.b64decode(b64)
        ext = "jpg" if ("jpeg" in head or "jpg" in head) else ("webp" if "webp" in head else "png")
    else:
        data, ext = httpx.get(url, timeout=60).content, "png"
    return data, ext, (msg.get("content") or "")

def save_image(data: bytes, ext: str) -> str:
    fname = f"{int(time.time() * 1000)}_{os.urandom(3).hex()}.{ext}"
    with open(os.path.join(IMG_DIR, fname), "wb") as f:
        f.write(data)
    return fname

def render_content(content: str):
    text = IMG_TAG.sub("", content).strip()
    if text:
        st.markdown(text)
    for fn in IMG_TAG.findall(content):
        path = os.path.join(IMG_DIR, os.path.basename(fn))
        if os.path.exists(path):
            st.image(path)
        else:
            st.caption("🖼️ (image file no longer available)")

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
[data-testid='stMain'], .block-container { position: relative; }

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
div[data-baseweb='popover'] > div { background: var(--card-solid) !important; }
div[data-baseweb='popover'] ul, div[data-baseweb='popover'] [role='listbox'], div[data-baseweb='menu'] {
  background: var(--card-solid) !important; border: 2px solid var(--cyan) !important; border-radius: 12px !important;
}
div[data-baseweb='popover'] li, div[data-baseweb='popover'] [role='option'],
div[data-baseweb='popover'] li *, div[data-baseweb='popover'] [role='option'] * {
  background: transparent !important; color: var(--fg) !important; -webkit-text-fill-color: var(--fg) !important; font-weight: 600 !important;
}
div[data-baseweb='popover'] li:hover, div[data-baseweb='popover'] [role='option']:hover,
div[data-baseweb='popover'] li[aria-selected='true'], div[data-baseweb='popover'] [role='option'][aria-selected='true'] { background: var(--glow) !important; }

/* chat input dock */
[data-testid='stBottom'], [data-testid='stBottom'] > div { background: transparent !important; }
[data-testid='stChatInput'] {
  background: var(--card-solid) !important; border: 2px solid var(--cyan) !important; border-radius: 16px !important;
  box-shadow: 0 4px 0 var(--edge-deep), 0 14px 30px var(--shadow), 0 0 22px var(--glow);
}
[data-testid='stChatInput'] div, [data-testid='stChatInput'] div[data-baseweb='textarea'],
[data-testid='stChatInput'] div[data-baseweb='base-input'] { background: var(--card-solid) !important; border-color: transparent !important; }
[data-testid='stChatInput'] textarea, [data-testid='stChatInputTextArea'] {
  background: var(--card-solid) !important; color: var(--fg) !important; -webkit-text-fill-color: var(--fg) !important;
  caret-color: var(--cyan) !important; border: none !important; box-shadow: none !important;
  font-size: 1.15rem !important; font-weight: 600 !important;
}
[data-testid='stChatInput'] textarea::placeholder { color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important; opacity: 1 !important; }
[data-testid='stChatInput'] button { background: var(--pink) !important; border-radius: 10px !important; }
[data-testid='stChatInput'] button svg { fill: #ffffff !important; color: #ffffff !important; }

/* ---------- chat bubbles: extruded 3D slabs (AI = magenta, YOU = cyan-blue) ---------- */
.who-user, .who-ai { display: none !important; }
div[data-testid='stElementContainer']:has(.who-user), div[data-testid='stElementContainer']:has(.who-ai),
div.element-container:has(.who-user), div.element-container:has(.who-ai) { display: none !important; }
div[data-testid='stChatMessage'] {
  background: var(--bub-ai) !important; backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  border: 2px solid var(--pink) !important; border-radius: 16px !important; padding: 16px !important; margin-bottom: 18px !important;
  box-shadow: 4px 4px 0 var(--edge), 8px 8px 0 var(--edge-deep), 0 20px 34px var(--shadow), 0 0 22px var(--glow);
  transform: perspective(1000px) rotateY(-1.4deg);
  transition: transform .25s ease, box-shadow .25s ease;
}
div[data-testid='stChatMessage']:has(.who-user) {
  background: var(--bub-user) !important; border-color: var(--cyan) !important;
  transform: perspective(1000px) rotateY(1.4deg);
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
.stButton > button, div[data-testid='stFormSubmitButton'] > button, [data-testid='stPopover'] button {
  background: linear-gradient(180deg, #e0147a 0%, #8a1fd1 100%) !important; color: #ffffff !important;
  border: 2px solid var(--cyan) !important; border-radius: 12px !important;
  font-family: 'Orbitron', sans-serif !important; font-weight: 700 !important; letter-spacing: .06em;
  box-shadow: 0 6px 0 #4b1286, 0 12px 20px var(--shadow), 0 0 18px var(--glow);
  transition: transform .12s ease, box-shadow .12s ease, filter .12s ease;
}
.stButton > button p, div[data-testid='stFormSubmitButton'] > button p, [data-testid='stPopover'] button p { color: #ffffff !important; font-family: 'Orbitron', sans-serif !important; font-size: 1rem !important; }
.stButton > button:hover, div[data-testid='stFormSubmitButton'] > button:hover, [data-testid='stPopover'] button:hover {
  transform: translateY(-2px); filter: brightness(1.12); border-color: var(--cyan) !important;
  box-shadow: 0 8px 0 #4b1286, 0 16px 24px var(--shadow), 0 0 26px var(--glow);
}
.stButton > button:active, div[data-testid='stFormSubmitButton'] > button:active, [data-testid='stPopover'] button:active {
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

/* ---------- select option lists: dark panel, visible text (light mode gets light panel) ---------- */
div[data-baseweb='popover']:not(:has([data-testid='stPopoverBody'])),
div[data-baseweb='popover']:not(:has([data-testid='stPopoverBody'])) > div,
[data-testid='stSelectboxVirtualDropdown'], [data-testid='stSelectboxVirtualDropdown'] ul,
ul[role='listbox'], div[data-baseweb='menu'] { background: var(--card-solid) !important; }
div[data-baseweb='popover']:not(:has([data-testid='stPopoverBody'])) *,
[data-testid='stSelectboxVirtualDropdown'] *, ul[role='listbox'] * {
  background-color: transparent !important; color: var(--fg) !important; -webkit-text-fill-color: var(--fg) !important;
  font-weight: 600 !important;
}
html body div[data-baseweb='popover'] [role='option']:hover, html body div[data-baseweb='popover'] li:hover,
html body div[data-baseweb='popover'] [role='option'][aria-selected='true'],
html body [data-testid='stSelectboxVirtualDropdown'] [role='option']:hover,
html body [data-testid='stSelectboxVirtualDropdown'] [aria-selected='true'] { background-color: var(--glow) !important; }

/* ---------- right-side toolkit drawer ---------- */
.st-key-tools_panel {
  position: fixed !important; top: 0; right: 0; bottom: 0; width: min(410px, 94vw); height: 100vh; overflow-y: auto; z-index: 1000;
  padding: 70px 20px 40px !important; background: var(--card-solid); border-left: 3px solid var(--cyan);
  box-shadow: -12px 0 40px var(--shadow), 0 0 30px var(--glow-cyan);
  transform: translateX(108%); visibility: hidden;
  transition: transform .4s cubic-bezier(.2,.8,.2,1), visibility 0s linear .4s;
}
[data-testid='stSlider'] [role='slider'] { background: var(--pink) !important; border: 2px solid var(--cyan) !important; }
[data-testid='stSliderThumbValue'], [data-testid='stSliderThumbValue'] * { color: var(--fg) !important; }
[data-testid='stFileUploaderDropzone'] { background: var(--card) !important; border: 2px dashed var(--cyan) !important; border-radius: 12px !important; }
[data-testid='stFileUploaderDropzone'] *, [data-testid='stFileUploader'] small { color: var(--fg) !important; }
[data-testid='stFileUploaderDropzone'] button, .stDownloadButton button {
  background: linear-gradient(180deg, #e0147a 0%, #8a1fd1 100%) !important; color: #ffffff !important;
  border: 2px solid var(--cyan) !important; border-radius: 10px !important; box-shadow: 0 4px 0 #4b1286;
}
[data-testid='stFileUploaderDropzone'] button *, .stDownloadButton button * { color: #ffffff !important; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 4px 0 14px; }
.chip {
  font-family: 'Orbitron', sans-serif; font-size: .78rem; font-weight: 700; letter-spacing: .06em; padding: 5px 12px;
  border-radius: 999px; background: var(--card-solid); border: 2px solid var(--cyan); box-shadow: 0 3px 0 var(--edge-deep), 0 0 12px var(--glow-cyan);
}

/* ---------- dashboard dropdown ---------- */
[data-testid='stPopover'] button svg { fill: #ffffff !important; color: #ffffff !important; }
[data-testid='stPopoverBody'] {
  background: var(--card-solid) !important; border: 2px solid var(--cyan) !important; border-radius: 16px !important;
  min-width: min(580px, 92vw); max-height: 75vh;
  box-shadow: 0 6px 0 var(--edge-deep), 0 22px 44px var(--shadow), 0 0 28px var(--glow-cyan);
}

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
            "shadow": "rgba(0,0,0,0.60)", "bub-user": "linear-gradient(135deg,#064a6e 0%,#0b2b70 100%)", "bub-ai": "linear-gradient(135deg,#7a1070 0%,#3a0b6b 100%)", "grid": "rgba(0,242,254,0.55)", "sun-op": "0.55",
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
            "shadow": "rgba(60,20,90,0.30)", "bub-user": "#d4f1ff", "bub-ai": "#ffdcef", "grid": "rgba(138,31,209,0.40)", "sun-op": "0.40",
            "title-grad": "linear-gradient(90deg,#c2005a 0%,#8a1fd1 100%)",
        }
    root = ":root{" + "".join(f"--{k}:{val};" for k, val in v.items()) + "}"
    st.markdown("<style>" + root + THEME_CSS + "</style>", unsafe_allow_html=True)

BOT_HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700&display=swap" rel="stylesheet">
<style>
html,body{margin:0;height:100%;background:transparent;overflow:hidden;}
#wrap{position:relative;width:100%;height:100%;}
canvas{display:block;width:100%;height:100%;}
#bubble{position:absolute;left:min(calc(50% + 125px),calc(100% - 235px));top:12%;max-width:215px;padding:9px 14px;
 border-radius:16px 16px 16px 4px;background:#180a33;color:#fff;border:2px solid #00f2fe;
 font:700 13px/1.35 'Orbitron',system-ui,sans-serif;letter-spacing:.05em;
 box-shadow:0 4px 0 #6a1fc2,0 0 18px rgba(0,242,254,.45);transition:transform .15s;}
#bubble.pop{transform:scale(1.07);}
</style></head><body><div id="wrap"><canvas id="c"></canvas><div id="bubble">VICE-BOT online 🌴</div></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
(function(){
var wrap=document.getElementById('wrap'),cv=document.getElementById('c'),bubble=document.getElementById('bubble');
if(!window.THREE){bubble.textContent='3D engine offline - check internet';return;}
var RM=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
var renderer;
try{renderer=new THREE.WebGLRenderer({canvas:cv,antialias:true,alpha:true});}
catch(e){bubble.textContent='WebGL unavailable 🌴🤖';return;}
renderer.setPixelRatio(Math.min(2,window.devicePixelRatio||1));
var scene=new THREE.Scene();
var camera=new THREE.PerspectiveCamera(40,1,0.1,100);
camera.position.set(0,0.5,8.6);camera.lookAt(0,0.45,0);
function resize(){var w=wrap.clientWidth||600,h=wrap.clientHeight||260;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();}
resize();window.addEventListener('resize',resize);
if(window.ResizeObserver){new ResizeObserver(resize).observe(wrap);}

/* lights: Vice City neon */
scene.add(new THREE.AmbientLight(0xffd9f2,0.75));
var key=new THREE.DirectionalLight(0xffffff,0.9);key.position.set(3,5,6);scene.add(key);
var pl=new THREE.PointLight(0xff4da6,1.3,20);pl.position.set(-4,2,4);scene.add(pl);
var cl=new THREE.PointLight(0x00f2fe,1.1,20);cl.position.set(4,-1,4);scene.add(cl);

function M(c,o){return new THREE.MeshStandardMaterial(Object.assign({color:c,roughness:0.4,metalness:0.15},o||{}));}
var matHead=M(0xff7ac8,{roughness:0.3}),matBody=M(0x6a2cf0,{roughness:0.35}),
matVisor=M(0x12062b,{roughness:0.12,metalness:0.6,emissive:0x1a0838}),
matPink=M(0xff4da6,{emissive:0xff4da6,emissiveIntensity:0.8}),
matCyanS=M(0x00f2fe,{emissive:0x00f2fe,emissiveIntensity:0.9}),
matGold=M(0xffd54a,{metalness:0.9,roughness:0.25}),matHand=M(0xffece4,{roughness:0.5}),
matLeaf=M(0x2dffb2,{emissive:0x0f9d70,emissiveIntensity:0.6}),matLeaf2=M(0x00f2fe,{emissive:0x0a8fa0,emissiveIntensity:0.6}),
matEye=new THREE.MeshBasicMaterial({color:0x00f2fe}),matMouth=new THREE.MeshBasicMaterial({color:0xff4da6}),
matBlush=new THREE.MeshBasicMaterial({color:0xff4da6,transparent:true,opacity:0.75});

function bellyTex(){
 var c=document.createElement('canvas');c.width=c.height=256;var g=c.getContext('2d');
 var gr=g.createLinearGradient(0,0,0,256);gr.addColorStop(0,'#ffe14d');gr.addColorStop(0.5,'#ff4da6');gr.addColorStop(1,'#6a1fc2');
 g.fillStyle=gr;g.beginPath();g.arc(128,128,126,0,Math.PI*2);g.fill();
 g.fillStyle='rgba(255,240,150,0.95)';g.beginPath();g.arc(128,120,46,0,Math.PI*2);g.fill();
 g.strokeStyle='#180a33';g.lineCap='round';g.lineWidth=8;
 g.beginPath();g.moveTo(98,214);g.quadraticCurveTo(110,150,126,104);g.stroke();
 g.lineWidth=7;
 [[70,96],[84,70],[126,62],[172,74],[186,104]].forEach(function(p){
  g.beginPath();g.moveTo(126,104);g.quadraticCurveTo((126+p[0])/2,p[1]-18,p[0],p[1]+14);g.stroke();});
 return new THREE.CanvasTexture(c);
}

var bot=new THREE.Group();bot.scale.setScalar(0.92);scene.add(bot);
/* body */
var body=new THREE.Mesh(new THREE.SphereGeometry(0.72,32,24),matBody);body.scale.set(1,1.05,0.9);body.position.y=-0.75;bot.add(body);
var belly=new THREE.Mesh(new THREE.CircleGeometry(0.36,40),new THREE.MeshBasicMaterial({map:bellyTex(),transparent:true}));
belly.position.set(0,-0.78,0.668);bot.add(belly);
var collar=new THREE.Mesh(new THREE.TorusGeometry(0.56,0.06,12,40),matGold);collar.rotation.x=Math.PI/2;collar.position.y=-0.3;bot.add(collar);
[-1,1].forEach(function(s){var f=new THREE.Mesh(new THREE.SphereGeometry(0.24,20,16),matPink);f.scale.set(1,0.55,1.35);f.position.set(s*0.3,-1.5,0.12);bot.add(f);});

/* head */
var head=new THREE.Group();head.position.y=0.98;bot.add(head);
var skull=new THREE.Mesh(new THREE.SphereGeometry(1,40,30),matHead);skull.scale.set(1.15,1,1);head.add(skull);
var visor=new THREE.Mesh(new THREE.SphereGeometry(1,40,30),matVisor);visor.scale.set(0.86,0.55,0.5);visor.position.set(0,0.05,0.62);head.add(visor);
var eyes=new THREE.Group();eyes.position.y=0.1;head.add(eyes);
[-1,1].forEach(function(s){var e=new THREE.Mesh(new THREE.SphereGeometry(0.17,20,16),matEye);e.scale.set(1,1.3,0.4);e.position.set(s*0.38,0,1.06);eyes.add(e);});
var smile=new THREE.Mesh(new THREE.TorusGeometry(0.1,0.022,8,24,Math.PI),matMouth);smile.rotation.z=Math.PI;smile.position.set(0,-0.1,1.1);head.add(smile);
var mouthO=new THREE.Mesh(new THREE.SphereGeometry(0.07,16,12),matMouth);mouthO.scale.set(0,0,0.3);mouthO.position.set(0,-0.13,1.09);head.add(mouthO);
[-1,1].forEach(function(s){var b=new THREE.Mesh(new THREE.SphereGeometry(0.1,16,12),matBlush);b.scale.set(1,0.6,0.2);b.position.set(s*0.66,-0.12,0.95);head.add(b);});
/* headphones */
var band=new THREE.Mesh(new THREE.TorusGeometry(1.2,0.05,10,48,Math.PI),matPink);band.scale.set(1,0.86,1);head.add(band);
[-1,1].forEach(function(s){
 var cup=new THREE.Mesh(new THREE.CylinderGeometry(0.34,0.34,0.24,24),matPink);cup.rotation.z=Math.PI/2;cup.position.x=s*1.2;head.add(cup);
 var ring=new THREE.Mesh(new THREE.TorusGeometry(0.26,0.035,10,28),matCyanS);ring.rotation.y=Math.PI/2;ring.position.x=s*1.33;head.add(ring);});
/* palm-leaf antenna */
var ant=new THREE.Group();ant.position.set(0,0.98,0);head.add(ant);
var stem=new THREE.Mesh(new THREE.CylinderGeometry(0.04,0.05,0.45,10),matGold);stem.position.y=0.22;ant.add(stem);
var leaves=new THREE.Group();leaves.position.y=0.46;ant.add(leaves);
var leafGeo=new THREE.ConeGeometry(0.08,0.5,10);leafGeo.translate(0,0.25,0);
for(var i=0;i<5;i++){var pv=new THREE.Group();pv.rotation.y=i*Math.PI*2/5;
 var lf=new THREE.Mesh(leafGeo,i%2?matLeaf2:matLeaf);lf.rotation.z=-1.05;lf.scale.z=0.35;pv.add(lf);leaves.add(pv);}
var ball=new THREE.Mesh(new THREE.SphereGeometry(0.13,20,16),matPink);ball.position.y=0.56;ant.add(ball);

/* arms */
function makeArm(s){var g=new THREE.Group();g.position.set(s*0.82,-0.5,0.05);
 var a=new THREE.Mesh(new THREE.CylinderGeometry(0.12,0.1,0.5,14),matBody);a.position.y=-0.25;
 var h=new THREE.Mesh(new THREE.SphereGeometry(0.17,20,16),matHand);h.position.y=-0.52;g.add(a);g.add(h);bot.add(g);return g;}
var armL=makeArm(-1),armR=makeArm(1);

/* neon floor rings */
var ringA=new THREE.Mesh(new THREE.TorusGeometry(1.0,0.035,8,60),new THREE.MeshBasicMaterial({color:0x00f2fe,transparent:true,opacity:0.9}));
ringA.rotation.x=Math.PI/2;ringA.position.y=-2.0;scene.add(ringA);
var ringB=new THREE.Mesh(new THREE.TorusGeometry(1.45,0.03,8,60),new THREE.MeshBasicMaterial({color:0xff4da6,transparent:true,opacity:0.75}));
ringB.rotation.x=Math.PI/2;ringB.position.y=-2.0;scene.add(ringB);
var glow=new THREE.Mesh(new THREE.CircleGeometry(1.4,40),new THREE.MeshBasicMaterial({color:0xff4da6,transparent:true,opacity:0.14}));
glow.rotation.x=-Math.PI/2;glow.position.y=-2.0;scene.add(glow);

/* keystroke sparks */
var parts=[],pgeo=new THREE.BoxGeometry(0.09,0.09,0.09);
function spawn(){if(RM||parts.length>40)return;
 var m=new THREE.Mesh(pgeo,new THREE.MeshBasicMaterial({color:Math.random()<0.5?0xff4da6:0x00f2fe,transparent:true}));
 m.position.set((Math.random()-0.5)*0.8,0.9+Math.random()*0.3,1.0);
 m.userData={vx:(Math.random()-0.5)*1.5,vy:-1.2-Math.random()*1.2,vz:0.5+Math.random()*0.8,life:1,spin:(Math.random()-0.5)*8};
 scene.add(m);parts.push(m);}

/* ---- typing awareness (reads the Streamlit page that hosts this iframe) ---- */
var P=null,pdoc=null,frame=null;
try{P=window.parent;pdoc=P.document;frame=window.frameElement;void pdoc.body;}catch(e){P=null;pdoc=null;frame=null;}
var S={typedAt:-1e9,sentAt:-1e9,mouseAt:-1e9,mx:0,my:0,el:null,kick:0,typeAmt:0,waveAmt:0,openAmt:0,thinking:false,thinkAmt:0,blink:0,nextBlink:2};
function isField(t){return t&&(t.tagName==='TEXTAREA'||t.tagName==='INPUT');}
function onInput(e){if(!isField(e.target))return;S.el=e.target;S.typedAt=performance.now();S.kick=1;spawn();spawn();}
function onKey(e){if(!isField(e.target))return;S.el=e.target;
 if(e.key==='Enter'&&!e.shiftKey&&e.target.tagName==='TEXTAREA'){S.sentAt=performance.now();}}
function onFocus(e){if(isField(e.target))S.el=e.target;}
function onMove(e){S.mx=e.clientX;S.my=e.clientY;S.mouseAt=performance.now();}
function onMoveLocal(e){var r=frame?frame.getBoundingClientRect():{left:0,top:0};S.mx=e.clientX+r.left;S.my=e.clientY+r.top;S.mouseAt=performance.now();}
var poll=null,raf=null;
if(P&&P.__viceBotCleanup){try{P.__viceBotCleanup();}catch(e){}}
if(pdoc){
 pdoc.addEventListener('input',onInput,true);pdoc.addEventListener('keydown',onKey,true);
 pdoc.addEventListener('focusin',onFocus,true);pdoc.addEventListener('mousemove',onMove,{passive:true});
 poll=setInterval(function(){try{S.thinking=!!pdoc.querySelector('.typing');}catch(e){}},250);
 P.__viceBotCleanup=function(){
  pdoc.removeEventListener('input',onInput,true);pdoc.removeEventListener('keydown',onKey,true);
  pdoc.removeEventListener('focusin',onFocus,true);pdoc.removeEventListener('mousemove',onMove);
  clearInterval(poll);cancelAnimationFrame(raf);};
}
document.addEventListener('mousemove',onMoveLocal,{passive:true});

function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
function lookTarget(now,t){
 var yaw=Math.sin(t*0.5)*0.25,pitch=0.05+Math.sin(t*0.37)*0.08;
 if(S.thinking)return[Math.sin(t*2.2)*0.55,-0.18];
 if(!frame)return[yaw,pitch];
 var fr=frame.getBoundingClientRect(),cx=fr.left+fr.width/2,cy=fr.top+fr.height*0.38,tx=null,ty=null;
 var typing=now-S.typedAt<900,active=false;
 try{active=pdoc&&pdoc.activeElement===S.el;}catch(e){}
 if(S.el&&(typing||active)){
  var r=S.el.getBoundingClientRect(),len=(S.el.value||'').length,span=Math.max(60,r.width-80);
  tx=r.left+30+((len*9)%span);ty=r.top+r.height/2;
 }else if(now-S.mouseAt<4000){tx=S.mx;ty=S.my;}
 if(tx!==null){yaw=clamp((tx-cx)/(fr.width*0.45),-1,1)*0.6;pitch=clamp((ty-cy)/450,-1,1)*0.45;}
 return[yaw,pitch];
}
function setStatus(txt){if(bubble.textContent!==txt){bubble.textContent=txt;bubble.classList.add('pop');setTimeout(function(){bubble.classList.remove('pop');},160);}}

var last=performance.now(),t0=last;
function tick(){
 raf=requestAnimationFrame(tick);
 var now=performance.now(),dt=Math.min(0.05,(now-last)/1000);last=now;var t=(now-t0)/1000;
 var typing=now-S.typedAt<900,waving=now-S.sentAt<1500;
 function k(a){return Math.min(1,dt*a);}
 S.typeAmt+=((typing?1:0)-S.typeAmt)*k(10);
 S.waveAmt+=((waving?1:0)-S.waveAmt)*k(8);
 S.thinkAmt+=((S.thinking?1:0)-S.thinkAmt)*k(6);
 S.openAmt+=((typing?1:(S.thinking?0.45:0))-S.openAmt)*k(12);
 S.kick=Math.max(0,S.kick-dt*3.5);
 var look=lookTarget(now,t),yaw=look[0],pitch=look[1];
 head.rotation.y+=(yaw-head.rotation.y)*k(7);
 head.rotation.x+=(pitch-head.rotation.x)*k(7);
 head.rotation.z=Math.sin(t*1.3)*0.04+S.typeAmt*Math.sin(t*9)*0.03+(waving?Math.sin(t*10)*0.05:0);
 bot.rotation.y=head.rotation.y*0.35;
 bot.position.y=Math.sin(t*1.7)*(RM?0.02:0.12)+(RM?0:S.kick*0.14)+(waving?Math.abs(Math.sin(t*8))*0.1*S.waveAmt:0);
 head.scale.set(1+S.kick*0.04,1-S.kick*0.06,1+S.kick*0.04);
 /* eyes */
 if(t>S.nextBlink){S.blink=1;S.nextBlink=t+2.5+Math.random()*2.5;}
 S.blink=Math.max(0,S.blink-dt*7);
 eyes.scale.y=(1-S.typeAmt*0.3-S.thinkAmt*0.15)*(1-0.9*Math.sin(S.blink*Math.PI));
 eyes.position.x=clamp(yaw*0.1,-0.1,0.1)+Math.sin(t*3)*0.08*S.thinkAmt;
 eyes.position.y=0.1+clamp(-pitch*0.08,-0.08,0.08);
 /* mouth */
 var o=S.openAmt;mouthO.visible=o>0.03;
 mouthO.scale.set(o,o*(0.7+0.3*Math.abs(Math.sin(t*18))),0.3);
 smile.scale.setScalar(Math.max(0.01,1-o*1.1));smile.visible=o<0.9;
 /* antenna */
 ant.rotation.z=Math.sin(t*3)*0.1+S.kick*0.4*Math.sin(t*40);ant.rotation.x=Math.cos(t*2.3)*0.08;
 leaves.rotation.y+=dt*(0.6+S.thinkAmt*6);
 ball.scale.setScalar(1+0.15*Math.sin(t*4)+S.thinkAmt*0.25*Math.sin(t*12));
 matPink.emissiveIntensity=0.8+S.typeAmt*0.5+S.thinkAmt*0.4*Math.abs(Math.sin(t*6));
 /* arms: type on a keyboard, wave on send */
 armL.rotation.x=-1.15*S.typeAmt+Math.sin(t*28)*0.25*S.typeAmt;
 armL.rotation.z=-0.2-Math.sin(t*1.7)*0.04;
 armR.rotation.x=-1.15*S.typeAmt*(1-S.waveAmt)+Math.cos(t*28)*0.25*S.typeAmt*(1-S.waveAmt);
 armR.rotation.z=0.2+2.3*S.waveAmt+Math.sin(t*14)*0.3*S.waveAmt+Math.sin(t*1.7)*0.04;
 /* neon */
 pl.intensity=1.3+S.typeAmt*0.8;
 ringA.scale.setScalar(1+Math.sin(t*2)*0.04+S.kick*0.15);
 ringB.scale.setScalar(1+Math.sin(t*2+1)*0.05+S.typeAmt*0.08);
 /* sparks */
 for(var i=parts.length-1;i>=0;i--){var p=parts[i],u=p.userData;
  p.position.x+=u.vx*dt;p.position.y+=u.vy*dt;p.position.z+=u.vz*dt;p.rotation.x+=u.spin*dt;p.rotation.y+=u.spin*dt;
  u.life-=dt*1.1;p.material.opacity=Math.max(0,u.life);
  if(u.life<=0){scene.remove(p);p.material.dispose();parts.splice(i,1);}}
 /* speech bubble */
 var active=false;try{active=pdoc&&S.el&&pdoc.activeElement===S.el;}catch(e){}
 setStatus(waving?'Transmitting! 📡':S.thinking?'Cooking up a reply... 🍹':typing?'Decoding your signal... ⌨️':active?'Listening... 👂':'VICE-BOT online 🌴');
 renderer.render(scene,camera);
}
tick();
})();
</script></body></html>
"""

def who_tag(role: str) -> str:
    return '<span class="who-ai"></span>' if role == "assistant" else '<span class="who-user"></span>'

components.html(BOT_HTML, height=270)

h1, h3, h4 = st.columns([5, 1.3, 1.3])
apply_theme(st.session_state.get("theme_pick", "🌙 Dark Mode"))

with h1:
    st.markdown('<div class="card"><div class="title">VICE AI</div><div class="sub">LANGCHAIN × OPENROUTER NEURAL INTERFACE</div></div>', unsafe_allow_html=True)

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
    MODELS = {
        "OpenRouter Auto Free Router": "openrouter/free",
        "Meta Llama 3.3 70B (Free)": "meta-llama/llama-3.3-70b-instruct:free",
        "Google Gemma 2 9B (Free)": "google/gemma-2-9b-it:free",
        "Mistral 7B Instruct (Free)": "mistralai/mistral-7b-instruct:free",
    }
    tokens = sum(int(len(m["content"].split()) * 1.3) for m in st.session_state.msgs)

    with h3:
        with st.popover("📊 DASHBOARD", use_container_width=True):
            st.selectbox("THEME", ["🌙 Dark Mode", "☀️ Light Mode"], key="theme_pick")
            page = st.selectbox("NAV", ["💬 Neural Chat Interface", "📊 Telemetry Dashboard"])
            model_id = MODELS[st.selectbox("MODEL", list(MODELS.keys()))]
            b1, b2 = st.columns(2)
            with b1:
                if st.button("WIPE BLOCK", use_container_width=True):
                    wipe_history(user)
                    st.session_state.msgs = load_history(user)
                    st.rerun()
            with b2:
                if st.button("LOGOUT", use_container_width=True):
                    delete_session(st.query_params.get("session", ""))
                    st.query_params.clear()
                    st.session_state.auth = False
                    st.session_state.user = None
                    st.session_state.msgs = []
                    st.rerun()
            st.markdown(f'<div class="card">🗄️ <b>MEMORY BLOCK:</b> AGENT [{user.upper()}] | SAVED MESSAGES: {len(st.session_state.msgs)} | EST. TOKENS: {tokens} | REFRESH-LOCKED</div>', unsafe_allow_html=True)
            st.markdown(f"**📂 {user.upper()}'s Saved History Block ({len(st.session_state.msgs)} messages)**")
            with st.container(height=320):
                for idx, hm in enumerate(st.session_state.msgs, 1):
                    who = user.upper() if hm["role"] == "user" else "VICE AI"
                    st.markdown(f"`[{idx}]` **{who}:** {IMG_TAG.sub('🖼️', hm['content'])}")

    st.session_state.setdefault("tools_open", False)

    def toggle_tools():
        st.session_state.tools_open = not st.session_state.tools_open

    with h4:
        st.button("🧰 TOOLS", use_container_width=True, on_click=toggle_tools, key="tools_btn")
    if st.session_state.tools_open:
        st.markdown("<style>.st-key-tools_panel{transform:translateX(0)!important;visibility:visible!important;transition:transform .4s cubic-bezier(.2,.8,.2,1),visibility 0s!important;}</style>", unsafe_allow_html=True)

    pdf_opts = pdf_model_options()
    vis_opts = vision_model_options()
    img_opts, img_mods = image_model_options()

    with st.container(key="tools_panel"):
        t1, t2 = st.columns([3, 1])
        t1.markdown("### 🧰 TOOLKIT")
        t2.button("✕", on_click=toggle_tools, key="close_tools")

        with st.expander("📄 PDF READER", expanded=True):
            pdf_pick = st.selectbox("PDF reading model", list(pdf_opts.keys()), key="pdf_model_pick")
            pdf_custom = st.text_input("Custom model ID (optional)", key="pdf_custom", placeholder="provider/model-name")
            pdf_file = st.file_uploader("Upload a PDF", type=["pdf"], key="pdf_up")
            if pdf_file is not None:
                sig = (pdf_file.name, pdf_file.size)
                if st.session_state.get("pdf_sig") != sig:
                    with st.spinner("Reading PDF..."):
                        _t, _n, _e = extract_pdf(pdf_file.getvalue())
                    st.session_state.update(pdf_sig=sig, pdf_text=_t, pdf_pages=_n, pdf_err=_e)
            else:
                st.session_state.update(pdf_sig=None, pdf_text="", pdf_pages=0, pdf_err=None)
            if st.session_state.get("pdf_err"):
                st.warning(st.session_state.pdf_err)
            elif st.session_state.get("pdf_text"):
                st.success(f"Loaded {st.session_state.pdf_pages} pages ({len(st.session_state.pdf_text):,} characters).")
            use_pdf = st.toggle("Use this PDF in chat", value=True, key="use_pdf")

        with st.expander("🎨 IMAGE STUDIO"):
            img_pick = st.selectbox("Image generation model", list(img_opts.keys()), key="img_model_pick")
            img_custom = st.text_input("Custom model ID (optional)", key="img_custom", placeholder="provider/model-name")
            img_ratio = st.selectbox("Aspect ratio", ["Auto", "1:1", "16:9", "9:16", "4:3", "3:4"], key="img_ratio")
            image_mode = st.toggle("Image mode: new messages generate images", key="image_mode")

        with st.expander("👁️ IMAGE ANALYSIS"):
            vis_pick = st.selectbox("Vision model", list(vis_opts.keys()), key="vis_model_pick")
            vis_custom = st.text_input("Custom model ID (optional)", key="vis_custom", placeholder="provider/model-name")
            vis_file = st.file_uploader("Attach an image to analyze", type=["png", "jpg", "jpeg", "webp"], key="vis_up")
            if vis_file is not None:
                st.image(vis_file, width=150)
                st.caption("Sent with every message until you remove it.")

        with st.expander("🌐 WEB SEARCH"):
            web_on = st.toggle("Search the web for live answers", key="web_on")

        with st.expander("🎭 PERSONA & STYLE"):
            persona = st.selectbox("Persona", list(PERSONAS.keys()), key="persona")
            custom_prompt = st.text_area("Custom instructions", key="custom_prompt", height=100) if persona == "Custom" else ""
            reply_lang = st.selectbox("Reply language", LANGS, key="reply_lang")
            temp = st.slider("Creativity", 0.0, 1.5, 0.7, 0.05, key="temp")
            max_tok = st.slider("Max reply length (0 = auto)", 0, 4096, 0, 128, key="max_tok")

        with st.expander("💾 EXPORT"):
            export_txt = "\n\n".join(
                f"[{'AGENT' if mm['role'] == 'user' else 'VICE AI'}] {IMG_TAG.sub('[image]', mm['content'])}" for mm in st.session_state.msgs
            )
            st.download_button("Download chat (.txt)", data=export_txt, file_name=f"vice_ai_{user}.txt", mime="text/plain", use_container_width=True)

    img_model_id = img_custom.strip() or img_opts[img_pick]
    cfg = {
        "pdf_model": pdf_custom.strip() or pdf_opts[pdf_pick],
        "pdf_ready": bool(use_pdf and st.session_state.get("pdf_text")),
        "pdf_name": pdf_file.name if pdf_file is not None else "",
        "img_model": img_model_id,
        "img_mods": img_mods.get(img_model_id, ["image", "text"]),
        "img_ratio": img_ratio,
        "image_mode": image_mode,
        "vis_model": vis_custom.strip() or vis_opts[vis_pick],
        "vis_file": vis_file,
        "web": web_on,
        "persona": persona,
        "custom_prompt": custom_prompt,
        "lang": reply_lang,
        "temp": temp,
        "max_tok": max_tok,
    }

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
                st.markdown(f"**`#{idx}` [{item.get('ts', 'SESSION')}] {tag}:** {IMG_TAG.sub('🖼️', item['content'])}")
    else:
        chips = []
        if cfg["image_mode"]:
            chips.append("🎨 IMAGE MODE")
        if cfg["web"]:
            chips.append("🌐 WEB SEARCH")
        if cfg["pdf_ready"]:
            chips.append("📄 " + html.escape(cfg["pdf_name"]))
        if cfg["vis_file"] is not None:
            chips.append("👁️ IMAGE ATTACHED")
        if chips:
            st.markdown('<div class="chips">' + "".join(f'<span class="chip">{c}</span>' for c in chips) + "</div>", unsafe_allow_html=True)

        for m in st.session_state.msgs:
            with st.chat_message(m["role"], avatar=AI_AVATAR if m["role"] == "assistant" else USER_AVATAR):
                st.markdown(who_tag(m["role"]), unsafe_allow_html=True)
                render_content(m["content"])

        placeholder = "Describe the image to generate..." if cfg["image_mode"] else f"Transmit as {user.upper()} to Vice AI..."
        if prompt := st.chat_input(placeholder):
            save_msg(user, "user", prompt)
            st.session_state.msgs.append({"role": "user", "content": prompt})
            with st.chat_message("user", avatar=USER_AVATAR):
                st.markdown(who_tag("user"), unsafe_allow_html=True)
                st.markdown(prompt)

            with st.chat_message("assistant", avatar=AI_AVATAR):
                st.markdown(who_tag("assistant"), unsafe_allow_html=True)
                holder = st.empty()
                holder.markdown('<div class="typing"><span class="dot"></span><span>VICE AI IS TYPING...</span></div>', unsafe_allow_html=True)
                if cfg["image_mode"]:
                    try:
                        img_bytes, ext, note = generate_image(api_key, cfg["img_model"], cfg["img_mods"], prompt, cfg["img_ratio"])
                        if img_bytes:
                            reply = f"🎨 Image generated for: {prompt}\n[[IMG:{save_image(img_bytes, ext)}]]"
                        else:
                            reply = note or "The image model returned no image. Try another model in the toolkit."
                        holder.empty()
                        render_content(reply)
                        save_msg(user, "assistant", reply)
                        st.session_state.msgs.append({"role": "assistant", "content": reply})
                    except Exception as e:
                        holder.empty()
                        st.error(f"Image signal disrupted: {e}")
                else:
                    sys_txt = f"You are Vice AI, a sharp futuristic assistant speaking with Agent {user}."
                    if cfg["persona"] == "Custom":
                        if cfg["custom_prompt"].strip():
                            sys_txt += " " + cfg["custom_prompt"].strip()
                    elif PERSONAS.get(cfg["persona"]):
                        sys_txt += " " + PERSONAS[cfg["persona"]]
                    if cfg["lang"] != "Auto":
                        sys_txt += f" Always reply in {cfg['lang']}."
                    active_model, used = model_id, []
                    if cfg["pdf_ready"]:
                        sys_txt += (f"\n\nThe user attached a PDF named '{cfg['pdf_name']}'. Use it when relevant.\n"
                                    f"--- PDF TEXT START ---\n{st.session_state.pdf_text}\n--- PDF TEXT END ---")
                        active_model = cfg["pdf_model"]
                        used.append("📄 PDF")
                    last_content = prompt
                    if cfg["vis_file"] is not None:
                        mime = cfg["vis_file"].type or "image/png"
                        b64 = base64.b64encode(cfg["vis_file"].getvalue()).decode()
                        last_content = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}]
                        active_model = cfg["vis_model"]
                        used.append("👁️ vision")
                    if cfg["web"]:
                        used.append("🌐 web")
                    used.insert(0, f"🧠 {active_model}")
                    lc_msgs = [SystemMessage(content=sys_txt)]
                    for m in st.session_state.msgs[:-1]:
                        txt = IMG_TAG.sub("[image]", m["content"])
                        lc_msgs.append(HumanMessage(content=txt) if m["role"] == "user" else AIMessage(content=txt))
                    lc_msgs.append(HumanMessage(content=last_content))
                    try:
                        kw = dict(model=active_model, openai_api_key=api_key, openai_api_base=OR_BASE, temperature=cfg["temp"], streaming=True)
                        if cfg["max_tok"]:
                            kw["max_tokens"] = cfg["max_tok"]
                        if cfg["web"]:
                            kw["extra_body"] = {"plugins": [{"id": "web"}]}
                        llm = ChatOpenAI(**kw)
                        reply = ""
                        first = True
                        for chunk in llm.stream(lc_msgs):
                            tok = chunk.content or ""
                            if isinstance(tok, list):
                                tok = "".join(x.get("text", "") if isinstance(x, dict) else str(x) for x in tok)
                            if first and tok:
                                time.sleep(0.35)
                                first = False
                            reply += tok
                            holder.markdown(reply + "▌")
                        holder.markdown(reply)
                        save_msg(user, "assistant", reply)
                        st.session_state.msgs.append({"role": "assistant", "content": reply})
                        st.caption(" · ".join(used))
                    except Exception as e:
                        holder.empty()
                        st.error(f"Signal disrupted: {e}")
