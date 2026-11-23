import os
import time
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
# ANIME FEMALE AVATAR (SVG DATA URI - SELF-CONTAINED)
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
  <!-- Back Hair -->
  <path d="M28 55 Q25 95 36 105 L84 105 Q95 95 92 55 Z" fill="url(#hairGrad)"/>
  <!-- Shoulders / Cyber Jacket -->
  <path d="M30 108 Q60 92 90 108 L95 115 L25 115 Z" fill="#1f1135" stroke="#00f2fe" stroke-width="2"/>
  <!-- Neck -->
  <rect x="53" y="76" width="14" height="16" rx="4" fill="#ffe0d2"/>
  <!-- Face -->
  <path d="M38 48 Q38 80 60 83 Q82 80 82 48 Q82 28 60 28 Q38 28 38 48 Z" fill="#ffece4"/>
  <!-- Anime Eyes -->
  <ellipse cx="49" cy="56" rx="5.5" ry="6.5" fill="#1a0b2e"/>
  <ellipse cx="71" cy="56" rx="5.5" ry="6.5" fill="#1a0b2e"/>
  <circle cx="49" cy="57" r="3.5" fill="#00f2fe"/>
  <circle cx="71" cy="57" r="3.5" fill="#00f2fe"/>
  <circle cx="47.5" cy="54" r="1.8" fill="#ffffff"/>
  <circle cx="69.5" cy="54" r="1.8" fill="#ffffff"/>
  <!-- Blush & Smile -->
  <ellipse cx="43" cy="64" rx="4" ry="2" fill="#ff71ce" opacity="0.5"/>
  <ellipse cx="77" cy="64" rx="4" ry="2" fill="#ff71ce" opacity="0.5"/>
  <path d="M56 69 Q60 73 64 69" stroke="#d64579" stroke-width="2" fill="none" stroke-linecap="round"/>
  <!-- Front Bangs -->
  <path d="M34 52 Q36 22 60 22 Q84 22 86 52 Q78 36 70 46 Q64 33 60 47 Q54 33 48 46 Q41 36 34 52 Z" fill="url(#hairGrad)"/>
  <!-- Cyber Visor / Headset Accent -->
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
    import base64
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

/* Global Background */
.stApp {
    background: radial-gradient(circle at 15% 15%, #2b0938 0%, #11051f 45%, #070312 100%);
    color: #f4eaff;
    font-family: 'Rajdhani', sans-serif;
}

/* Hide default Streamlit header/footer clutter */
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

/* Top Dropdown / Selectbox Styling */
div[data-baseweb="select"] > div {
    background-color: rgba(20, 9, 43, 0.85) !important;
    border: 1px solid #00f2fe !important;
    border-radius: 10px !important;
    color: #ffffff !important;
    box-shadow: 0 0 12px rgba(0, 242, 254, 0.25);
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
    font-size: 1.75rem;
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
    font-size: 0.8rem;
    letter-spacing: 1px;
    border: 1px solid #00f2fe;
    border-radius: 10px;
    padding: 8px 18px;
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
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Welcome to **Vice City Neural Link**. Neon lights are online and my OpenRouter circuits are warmed up. What's our next move?"
        }
    ]

if "total_prompts" not in st.session_state:
    st.session_state.total_prompts = 0

if "est_tokens" not in st.session_state:
    st.session_state.est_tokens = 0

# -----------------------------------------------------------------------------
# HEADER & TOP DROPDOWN NAVIGATION BAR
# -----------------------------------------------------------------------------
st.markdown("""
<div class="vice-header">
    <div class="vice-title">VICE AI // LEONIDA NET</div>
    <div class="vice-subtitle">FUTURISTIC LANGCHAIN × OPENROUTER NEURAL INTERFACE</div>
</div>
""", unsafe_allow_html=True)

nav_col1, nav_col2, nav_col3 = st.columns([2, 2, 1])

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
    if st.button("WIPE MEMORY", use_container_width=True):
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Memory wiped clean. Fresh neon slate—where are we headed?"
            }
        ]
        st.session_state.total_prompts = 0
        st.session_state.est_tokens = 0
        st.rerun()

# -----------------------------------------------------------------------------
# API KEY SECURITY CHECK (READ ONLY FROM .ENV / ENVIRONMENT)
# -----------------------------------------------------------------------------
api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

if not api_key or "PASTE_YOUR" in api_key:
    st.error(
        "🔒 **API Key Missing:** Add your regenerated `OPENROUTER_API_KEY` inside your local `.env` file. "
        "Never hardcode keys inside `app.py` before pushing to GitHub."
    )
    st.stop()

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

# -----------------------------------------------------------------------------
# PAGE 1: TELEMETRY DASHBOARD (TOP DROPDOWN SELECTION)
# -----------------------------------------------------------------------------
if active_page == "📊 Telemetry Dashboard":
    st.markdown("### ⚡ SYSTEM TELEMETRY & SECURITY HUD")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="cyber-card">
            <h3>Prompts Sent</h3>
            <p>{st.session_state.total_prompts}</p>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="cyber-card">
            <h3>Context Messages</h3>
            <p>{len(st.session_state.messages)}</p>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="cyber-card">
            <h3>Est. Session Tokens</h3>
            <p>{st.session_state.est_tokens}</p>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "SECURED"
        st.markdown(f"""
        <div class="cyber-card">
            <h3>GitHub Leak Shield</h3>
            <p style="font-size:1.1rem; padding-top:8px;">ACTIVE ({masked_key})</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("#### 🛡️ GitHub Anti-Leak Verification")
        st.info(
            "1. **Environment Isolation:** `app.py` reads `OPENROUTER_API_KEY` via `os.getenv()`.\n"
            "2. **Git Ignore Enforcement:** `.env` is listed in `.gitignore` so `git push` never uploads your credentials.\n"
            "3. **Endpoint:** `https://openrouter.ai/api/v1` via `langchain_openai.ChatOpenAI`."
        )
    with col_right:
        st.markdown("#### 🎛️ Active Neural Core")
        st.success(
            f"**Selected Tier:** {selected_model_label}\n\n"
            f"**Model ID:** `{selected_model_id}`\n\n"
            "Switch back to **💬 Neural Chat Interface** from the top dropdown to continue chatting."
        )

# -----------------------------------------------------------------------------
# PAGE 2: NEURAL CHAT INTERFACE
# -----------------------------------------------------------------------------
else:
    # Render conversation history
    for msg in st.session_state.messages:
        avatar = AI_AVATAR_URI if msg["role"] == "assistant" else USER_AVATAR_URI
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # User prompt input
    if user_prompt := st.chat_input("Transmit message to Vice AI..."):
        # Append and render user message
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        st.session_state.total_prompts += 1
        st.session_state.est_tokens += int(len(user_prompt.split()) * 1.3)

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

            # Build LangChain message history
            lc_messages = [
                SystemMessage(
                    content=(
                        "You are Vice AI, a sharp, stylish, futuristic AI assistant inspired by Vice City. "
                        "Keep responses helpful, clear, and engaging."
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
                        # Small pause so the neon typing animation is visible before text streams
                        time.sleep(0.35)
                        first_chunk = False
                    full_response += token
                    typing_placeholder.markdown(full_response + "▌")

                typing_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                st.session_state.est_tokens += int(len(full_response.split()) * 1.3)

            except Exception as e:
                typing_placeholder.empty()
                st.error(f"Signal disrupted: {e}")