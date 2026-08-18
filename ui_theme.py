"""
Visual theme for Article Analyzer — a "wire desk" identity: the app reads like
a press-analysis terminal pulling live reports off a wire. Warm ink-black
(or, in light mode, warm parchment) background, a brass/amber accent, a serif
masthead paired with a monospace face for data and labels.

Everything here is presentation only — no business logic. Color tokens are
plain module-level globals that get reassigned by set_theme_mode(); every
function below reads them by name at call time, so callers should always
call set_theme_mode() (if switching modes) before inject_theme()/masthead()/etc.
in the same run.
"""
import html
import streamlit as st

# ---------------------------------------------------------------------------
# Palettes
# ---------------------------------------------------------------------------
DARK_PALETTE = dict(
    INK="#14110D", SURFACE="#1F1A14", SURFACE_BORDER="#3A2F20",
    ACCENT="#E8A33D", ACCENT_DIM="#8A6A2F",
    TEXT="#F2E9DA", TEXT_MUTED="#A69A85",
    POSITIVE="#6FCF97", NEGATIVE="#EB5757", NEUTRAL="#B8AD97",
)

LIGHT_PALETTE = dict(
    INK="#F5EFE2", SURFACE="#FFFFFF", SURFACE_BORDER="#DCD0B4",
    ACCENT="#B8791F", ACCENT_DIM="#D8B274",
    TEXT="#241F16", TEXT_MUTED="#6B6153",
    POSITIVE="#2F9E5B", NEGATIVE="#D64545", NEUTRAL="#8B8272",
)

FONT_DISPLAY = "'Playfair Display', Georgia, serif"
FONT_MONO = "'IBM Plex Mono', 'Courier New', monospace"

# Initialize with dark defaults — overwritten by set_theme_mode() each run.
INK = DARK_PALETTE["INK"]
SURFACE = DARK_PALETTE["SURFACE"]
SURFACE_BORDER = DARK_PALETTE["SURFACE_BORDER"]
ACCENT = DARK_PALETTE["ACCENT"]
ACCENT_DIM = DARK_PALETTE["ACCENT_DIM"]
TEXT = DARK_PALETTE["TEXT"]
TEXT_MUTED = DARK_PALETTE["TEXT_MUTED"]
POSITIVE = DARK_PALETTE["POSITIVE"]
NEGATIVE = DARK_PALETTE["NEGATIVE"]
NEUTRAL = DARK_PALETTE["NEUTRAL"]
SENTIMENT_COLORS = {"Positive": POSITIVE, "Negative": NEGATIVE, "Neutral": NEUTRAL}


def set_theme_mode(dark: bool):
    """Reassign the module-level color tokens. Call before inject_theme()/masthead()/etc."""
    global INK, SURFACE, SURFACE_BORDER, ACCENT, ACCENT_DIM, TEXT, TEXT_MUTED
    global POSITIVE, NEGATIVE, NEUTRAL, SENTIMENT_COLORS
    palette = DARK_PALETTE if dark else LIGHT_PALETTE
    INK = palette["INK"]
    SURFACE = palette["SURFACE"]
    SURFACE_BORDER = palette["SURFACE_BORDER"]
    ACCENT = palette["ACCENT"]
    ACCENT_DIM = palette["ACCENT_DIM"]
    TEXT = palette["TEXT"]
    TEXT_MUTED = palette["TEXT_MUTED"]
    POSITIVE = palette["POSITIVE"]
    NEGATIVE = palette["NEGATIVE"]
    NEUTRAL = palette["NEUTRAL"]
    SENTIMENT_COLORS = {"Positive": POSITIVE, "Negative": NEGATIVE, "Neutral": NEUTRAL}


def inject_theme():
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

        html, body, [class*="css"] {{
            font-family: {FONT_MONO};
        }}

        .stApp {{
            background-color: {INK};
            color: {TEXT};
        }}

        h1, h2, h3 {{
            font-family: {FONT_DISPLAY} !important;
            color: {TEXT} !important;
            letter-spacing: 0.01em;
        }}

        h4, h5, h6 {{
            font-family: {FONT_MONO} !important;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: {ACCENT} !important;
            font-size: 0.85rem !important;
        }}

        p, li, label, span, div {{
            color: {TEXT};
        }}

        .stMarkdown h3 {{
            border-bottom: 1px solid {SURFACE_BORDER};
            padding-bottom: 0.4rem;
            margin-top: 1.6rem;
        }}

        /* --- Sidebar shell --- */
        [data-testid="stSidebar"] {{
            background-color: {SURFACE};
            border-right: 1px solid {SURFACE_BORDER};
        }}
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
            color: {TEXT};
        }}

        /* --- Sidebar nav buttons (robust — no :has()/hidden-label hacks) --- */
        [data-testid="stSidebar"] .stButton {{
            margin-bottom: 2px;
        }}
        [data-testid="stSidebar"] .stButton > button {{
            font-family: {FONT_MONO} !important;
            text-transform: none !important;
            letter-spacing: 0.02em !important;
            font-size: 0.92rem !important;
            text-align: left !important;
            justify-content: flex-start !important;
            width: 100%;
            background-color: transparent !important;
            color: {TEXT_MUTED} !important;
            border: none !important;
            border-left: 3px solid transparent !important;
            border-radius: 3px !important;
            padding: 0.55rem 0.75rem !important;
        }}
        [data-testid="stSidebar"] .stButton > button:hover {{
            background-color: rgba(232, 163, 61, 0.10) !important;
            color: {ACCENT} !important;
        }}
        [data-testid="stSidebar"] .stButton > button[kind="primary"] {{
            background-color: rgba(232, 163, 61, 0.14) !important;
            color: {ACCENT} !important;
            border-left: 3px solid {ACCENT} !important;
            font-weight: 600 !important;
        }}

        /* Dark/light toggle + other sidebar widgets */
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
            font-family: {FONT_MONO};
            font-size: 0.8rem;
            color: {TEXT_MUTED};
        }}

        /* --- Tabs (still used for comment sentiment filters) --- */
        [data-testid="stTabs"] [data-baseweb="tab-list"] {{
            gap: 4px;
            border-bottom: 1px solid {SURFACE_BORDER};
        }}
        [data-testid="stTabs"] button[data-baseweb="tab"] {{
            font-family: {FONT_MONO};
            text-transform: uppercase;
            font-size: 0.8rem;
            letter-spacing: 0.06em;
            color: {TEXT_MUTED};
        }}
        [data-testid="stTabs"] button[aria-selected="true"] {{
            color: {ACCENT} !important;
        }}
        [data-testid="stTabs"] [data-baseweb="tab-highlight"] {{
            background-color: {ACCENT} !important;
        }}

        /* --- Buttons (main content area) --- */
        .main .stButton > button {{
            font-family: {FONT_MONO};
            text-transform: uppercase;
            letter-spacing: 0.06em;
            font-size: 0.8rem;
            background-color: transparent;
            color: {ACCENT};
            border: 1px solid {ACCENT_DIM};
            border-radius: 2px;
            transition: all 0.15s ease;
        }}
        .main .stButton > button:hover {{
            background-color: {ACCENT};
            color: {INK};
            border-color: {ACCENT};
        }}

        /* --- Inputs --- */
        .stTextInput input, .stTextArea textarea, .stNumberInput input {{
            background-color: {SURFACE} !important;
            color: {TEXT} !important;
            border: 1px solid {SURFACE_BORDER} !important;
            font-family: {FONT_MONO} !important;
            border-radius: 2px !important;
        }}

        /* --- Metrics --- */
        [data-testid="stMetric"] {{
            background-color: {SURFACE};
            border: 1px solid {SURFACE_BORDER};
            border-left: 3px solid {ACCENT};
            border-radius: 2px;
            padding: 0.75rem 1rem;
        }}
        [data-testid="stMetricLabel"] {{
            font-family: {FONT_MONO} !important;
            text-transform: uppercase;
            font-size: 0.7rem !important;
            letter-spacing: 0.08em;
            color: {TEXT_MUTED} !important;
        }}
        [data-testid="stMetricValue"] {{
            font-family: {FONT_MONO} !important;
            color: {TEXT} !important;
        }}

        /* --- Bordered containers (dispatch card) --- */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: {SURFACE};
            border: 1px dashed {ACCENT_DIM} !important;
            border-radius: 2px;
        }}

        /* --- Dataframes --- */
        [data-testid="stDataFrame"] {{
            border: 1px solid {SURFACE_BORDER};
            border-radius: 2px;
        }}

        /* --- Expander --- */
        [data-testid="stExpander"] {{
            background-color: {SURFACE};
            border: 1px solid {SURFACE_BORDER};
            border-radius: 2px;
        }}

        /* --- File uploader --- */
        [data-testid="stFileUploader"] section {{
            background-color: {SURFACE};
            border: 1px dashed {SURFACE_BORDER};
            border-radius: 2px;
        }}

        /* --- Alerts --- */
        [data-testid="stAlert"] {{
            border-radius: 2px;
            font-family: {FONT_MONO};
        }}

        hr {{
            border-color: {SURFACE_BORDER} !important;
        }}

        #MainMenu, footer {{ visibility: hidden; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_brand(label):
    """Small wordmark shown above the sidebar nav."""
    st.sidebar.markdown(
        f"""
        <div style="padding: 0.5rem 0.2rem 0.9rem 0.2rem; border-bottom: 1px solid {SURFACE_BORDER};
                    margin-bottom: 0.75rem;">
            <div style="font-family: {FONT_MONO}; text-transform: uppercase; letter-spacing: 0.15em;
                        font-size: 0.65rem; color: {ACCENT};">Article Analyzer</div>
            <div style="font-family: {FONT_DISPLAY}; font-weight: 700; font-size: 1.25rem; color: {TEXT};">
                {label}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def masthead(eyebrow, title, subtitle):
    """The signature element: a wire-dispatch masthead banner."""
    st.markdown(
        f"""
        <div style="border-top: 3px double {ACCENT}; border-bottom: 1px solid {SURFACE_BORDER};
                    padding: 1.1rem 0 1rem 0; margin-bottom: 1.5rem;">
            <div style="font-family: {FONT_MONO}; text-transform: uppercase; letter-spacing: 0.18em;
                        font-size: 0.72rem; color: {ACCENT}; margin-bottom: 0.35rem;">
                {eyebrow}
            </div>
            <div style="font-family: {FONT_DISPLAY}; font-weight: 700; font-size: 2.3rem;
                        color: {TEXT}; line-height: 1.1;">
                {title}
            </div>
            <div style="font-family: {FONT_MONO}; font-size: 0.85rem; color: {TEXT_MUTED};
                        margin-top: 0.5rem;">
                {subtitle}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def dispatch_card():
    """
    Wrap a result in a telex-printout style card.
    Use as: `with dispatch_card(): st.markdown(text)` — native container so
    nested markdown (##, bullets, etc.) renders correctly.
    """
    return st.container(border=True)


def sentiment_chip_row(counts_dict, total):
    """Render Positive / Negative / Neutral as ink-stamp style chips instead of plain numbers."""
    cols = st.columns(len(counts_dict) + 1)
    cols[0].markdown(
        f"""<div style="font-family:{FONT_MONO}; color:{TEXT_MUTED}; font-size:0.7rem;
             text-transform:uppercase; letter-spacing:0.08em; padding-top:1.1rem;">
             Total<br><span style="font-size:1.4rem; color:{TEXT};">{total}</span></div>""",
        unsafe_allow_html=True,
    )
    for col, (label, value) in zip(cols[1:], counts_dict.items()):
        color = SENTIMENT_COLORS.get(label, TEXT_MUTED)
        pct = f"{(value / total * 100):.0f}%" if total else "0%"
        col.markdown(
            f"""
            <div style="border: 1.5px solid {color}; border-radius: 3px; padding: 0.5rem 0.7rem;
                        text-align: center; transform: rotate(-1deg);">
                <div style="font-family:{FONT_MONO}; text-transform:uppercase; font-size:0.65rem;
                            letter-spacing:0.1em; color:{color};">{label}</div>
                <div style="font-family:{FONT_MONO}; font-size:1.3rem; color:{TEXT}; font-weight:600;">
                    {value} <span style="font-size:0.75rem; color:{TEXT_MUTED};">({pct})</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def copy_button(text, key):
    """
    Client-side 'copy to clipboard' button — no Streamlit rerun involved.
    Text is placed in a hidden, HTML-escaped textarea and copied via the
    browser's Clipboard API, so no user content is interpolated into JS.
    """
    safe_text = html.escape(text or "")
    st.markdown(
        f"""
        <div style="margin-top: 0.4rem;">
            <textarea id="copy_src_{key}" style="position:absolute; left:-9999px;">{safe_text}</textarea>
            <button onclick="
                const el = document.getElementById('copy_src_{key}');
                navigator.clipboard.writeText(el.value);
                const btn = document.getElementById('copy_btn_{key}');
                btn.innerText = '✅ Copied';
                setTimeout(() => {{ btn.innerText = '📋 Copy result'; }}, 1500);
            " id="copy_btn_{key}" style="
                font-family: {FONT_MONO}; font-size: 0.75rem; text-transform: uppercase;
                letter-spacing: 0.05em; background: transparent; color: {ACCENT};
                border: 1px solid {ACCENT_DIM}; border-radius: 2px; padding: 0.35rem 0.7rem;
                cursor: pointer;">📋 Copy result</button>
        </div>
        """,
        unsafe_allow_html=True,
    )