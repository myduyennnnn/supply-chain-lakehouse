import streamlit as st
from shared.db import list_tables, load_table

st.html("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&display=swap');

    /* ── Base ── */
    .stApp {
        background: linear-gradient(155deg, #F3EFFF 0%, #ECF4FF 50%, #E6FDFC 100%) !important;
        font-family: 'Outfit', sans-serif !important;
        color: #1E2243 !important;
    }

    /* ── Title ── */
    .main-title {
        font-size: 2.8rem;
        font-weight: 900;
        background: linear-gradient(90deg, #6F42C1 0%, #007BFF 55%, #00CCCC 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.5px;
        margin-bottom: 2.5rem;
    }

    /* ── Section Headers ── */
    .section-header {
        font-size: 0.8rem;
        font-weight: 800;
        color: #6F42C1;
        text-transform: uppercase;
        letter-spacing: 2.5px;
        margin: 2.5rem 0 1.5rem;
        padding-left: 14px;
        border-left: 4px solid #007BFF;
    }

    /* ── KPI Cards ── */
    [data-testid="stMetric"] {
        border-radius: 20px;
        padding: 28px 22px;
        border: none !important;
        box-shadow: 0 10px 32px rgba(111,66,193,0.18), 0 2px 8px rgba(0,0,0,0.06);
        overflow: hidden;
        position: relative;
        transition: transform 0.25s ease, box-shadow 0.25s ease;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-7px);
        box-shadow: 0 20px 48px rgba(111,66,193,0.26), 0 6px 16px rgba(0,0,0,0.09);
    }
    [data-testid="stMetric"]::after {
        content: '';
        position: absolute;
        width: 170px; height: 170px;
        border-radius: 50%;
        background: rgba(255,255,255,0.13);
        top: -60px; right: -45px;
        pointer-events: none;
    }

    [data-testid="stMetricValue"] {
        color: #fff !important;
        font-size: 2.3rem !important;
        font-weight: 800 !important;
        position: relative; z-index: 2;
    }
    [data-testid="stMetricLabel"] {
        color: rgba(255,255,255,0.88) !important;
        font-size: 0.78rem !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: 1.4px;
        position: relative; z-index: 2;
    }

    /* Column 1 — Purple */
    [data-testid="column"]:nth-child(1) [data-testid="stMetric"] {
        background: linear-gradient(140deg, #9B6AE0 0%, #6F42C1 100%);
    }
    /* Column 2 — Blue */
    [data-testid="column"]:nth-child(2) [data-testid="stMetric"] {
        background: linear-gradient(140deg, #4AAAFF 0%, #007BFF 100%);
    }

    /* ── Divider as gradient line ── */
    hr {
        border: none !important;
        height: 2px !important;
        background: linear-gradient(90deg, #6F42C1, #007BFF, #00CCCC) !important;
        opacity: 0.28 !important;
        margin: 3rem 0 !important;
    }

    /* ── Selectbox / Inputs ── */
    [data-testid="stSelectbox"] > div > div {
        border-radius: 12px !important;
        border: 1.5px solid #C4B5FD !important;
        background: rgba(255,255,255,0.75) !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 600 !important;
        color: #1E2243 !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    [data-testid="stSelectbox"] > div > div:focus-within {
        border-color: #6F42C1 !important;
        box-shadow: 0 0 0 3px rgba(111,66,193,0.15) !important;
    }

    /* ── Dataframe ── */
    [data-testid="stDataFrame"] {
        border-radius: 16px !important;
        overflow: hidden !important;
        box-shadow: 0 8px 28px rgba(111,66,193,0.12), 0 2px 8px rgba(0,0,0,0.05) !important;
        border: 1px solid #E4E8F5 !important;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(175deg, #1C1050 0%, #0A061F 100%) !important;
    }
    [data-testid="stSidebar"] label { color: #ffffff !important; }
    [data-testid="stSidebarContent"] { color: #ffffff !important; }
    [data-testid="stSidebarContent"] * { color: #ffffff !important; }

    /* ── Captions ── */
    .stCaption p { color: #8A8FA8 !important; font-style: italic; }

    p { color: #1E2243; }
</style>
""")

st.markdown('<h1 class="main-title">Data Preview</h1>', unsafe_allow_html=True)

layer = st.selectbox("Layer", ["silver", "gold"])
tables = list_tables(layer)

if not tables:
    st.warning(f"Chưa có table nào trong layer '{layer}'")
    st.stop()

selected_table = st.selectbox("Table", tables)

st.markdown(f'<div class="section-header">{layer}.{selected_table}</div>', unsafe_allow_html=True)

try:
    df = load_table(selected_table, layer=layer)
    col1, col2 = st.columns(2)
    col1.metric("Rows", len(df))
    col2.metric("Columns", len(df.columns))
    st.dataframe(df.head(100), use_container_width=True)
except Exception as e:
    st.error(f"Không đọc được table '{selected_table}': {e}")
