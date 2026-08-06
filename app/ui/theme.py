"""Accessible visual system for the Streamlit shell."""

import streamlit as st

CSS = """
<style>
  :root { --ink:#172420; --muted:#62736c; --forest:#17624b; --mint:#e9f4ef; --line:#dfe8e3; --paper:#fbfcfb; --amber:#ad6b17; }
  .stApp { background: var(--paper); color: var(--ink); }
  [data-testid="stSidebar"] { background: #102e25; }
  [data-testid="stSidebar"] * { color: #eef7f3; }
  [data-testid="stSidebar"] .stRadio label { padding: .3rem .2rem; }
  .block-container { max-width: 1440px; padding-top: 3.5rem; padding-bottom: 4rem; }
  h1, h2, h3 { color: var(--ink); letter-spacing: -.025em; }
  h1 { font-size: 2.1rem !important; }
  .eyebrow { color: var(--forest); text-transform: uppercase; font-size: .73rem; font-weight: 750; letter-spacing: .11em; }
  .page-subtitle { color: var(--muted); margin-top: -.55rem; margin-bottom: 1.5rem; max-width: 850px; }
  .product-mark { color:#fff; font-size:1.15rem; font-weight:750; margin-bottom:.1rem; }
  .product-tagline { color:#bcd1c9; font-size:.82rem; margin-bottom:1.4rem; }
  .env-label { display:inline-block; color:#bcd1c9; font-size:.72rem; font-weight:650; letter-spacing:.05em; text-transform:uppercase; border:1px solid #2f5a4a; border-radius:999px; padding:.16rem .58rem; margin:.1rem 0 .5rem; }
  .metric-card { background:white; border:1px solid var(--line); border-radius:12px; padding:1rem 1.05rem; min-height:112px; box-shadow:0 1px 2px rgba(16,46,37,.04); }
  .metric-label { color:var(--muted); font-size:.75rem; font-weight:700; text-transform:uppercase; letter-spacing:.055em; }
  .metric-value { color:var(--ink); font-size:1.55rem; font-weight:760; margin:.35rem 0 .2rem; }
  .metric-help { color:var(--muted); font-size:.75rem; line-height:1.25; }
  .insight { border-left:4px solid var(--forest); background:white; border-radius:8px; padding:.9rem 1rem; margin:.55rem 0; border-top:1px solid var(--line); border-right:1px solid var(--line); border-bottom:1px solid var(--line); }
  .insight.critical { border-left-color:#a33434; } .insight.important { border-left-color:#cf7b1b; }
  .insight.attention { border-left-color:#c19a2c; } .insight.informational { border-left-color:#397a9f; }
  .demo-banner { background:#f4efe3; border:1px solid #e3d4b5; border-radius:8px; padding:.55rem .8rem; color:#6b562c; font-size:.82rem; }
  div[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:10px; overflow:hidden; }
  .stButton button, .stFormSubmitButton button, .stDownloadButton button {
    background:#fff; border-color:var(--forest); color:var(--ink);
  }
  .stButton button *, .stFormSubmitButton button *, .stDownloadButton button * { color:inherit; }
  .stButton button:hover, .stFormSubmitButton button:hover, .stDownloadButton button:hover {
    background:var(--mint); border-color:var(--forest); color:var(--ink);
  }
  .stButton button[kind="primary"], .stFormSubmitButton button[kind="primary"] {
    background:var(--forest); border-color:var(--forest); color:#fff;
  }
</style>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
