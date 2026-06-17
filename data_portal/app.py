import streamlit as st
from analytics import sales_dashboard

st.set_page_config(page_title="Data Portal", layout="wide")

pages = {
    "Overview": [
        st.Page("data_preview/page.py", title="Data Preview"),
    ],
    "Analytics": [
        st.Page(sales_dashboard.render, title="Sales Dashboard"),
    ],
}

pg = st.navigation(pages)
pg.run()