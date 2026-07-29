"""Brand styling shared by every dashboard page.

The real "Colonel's Bakery and Restaurant" logo lives at assets/logo.png —
drop a replacement file in that exact path and every page picks it up with
no code changes.
"""

from pathlib import Path

import streamlit as st

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"

PRIMARY = "#C61D24"    # red — matches the real logo
BG_DARK = "#0A0A0A"    # navy/near-black background
SURFACE = "#161616"
TEXT_LIGHT = "#F5F5F7"


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        [data-testid="stSidebar"] {{
            background-color: {BG_DARK};
        }}
        [data-testid="stSidebar"] * {{
            color: {TEXT_LIGHT} !important;
        }}
        [data-testid="stSidebar"] button {{
            border: 1px solid {PRIMARY} !important;
            color: {PRIMARY} !important;
            background-color: transparent !important;
        }}
        .cbr-header {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding-bottom: 0.5rem;
            margin-bottom: 1rem;
            border-bottom: 2px solid {PRIMARY};
        }}
        .cbr-header h1 {{
            font-size: 1.3rem;
            margin: 0;
            color: {TEXT_LIGHT};
        }}
        .cbr-header p {{
            margin: 0;
            font-size: 0.8rem;
            opacity: 0.75;
            color: {TEXT_LIGHT};
        }}
        .stButton>button[kind="primary"] {{
            background-color: {PRIMARY};
            border-color: {PRIMARY};
        }}
        div[data-testid="stMetric"] {{
            background-color: rgba(198, 29, 36, 0.06);
            border: 1px solid rgba(198, 29, 36, 0.25);
            border-radius: 10px;
            padding: 0.75rem 1rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_header() -> None:
    logo_html = ""
    if LOGO_PATH.exists():
        import base64
        b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode()
        logo_html = f'<img src="data:image/png;base64,{b64}" style="height:44px;border-radius:6px;" />'

    st.markdown(
        f"""
        <div class="cbr-header">
            {logo_html}
            <div>
                <h1>Colonel's Bakery &amp; Restaurant</h1>
                <p>Manager Dashboard</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
