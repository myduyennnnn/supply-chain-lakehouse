import streamlit as st

st.set_page_config(page_title="Supply Chain Data Portal", layout="wide")

pages = {
    "Overview": [
        st.Page("pages/data_preview.py",      title="Data Preview"),
    ],
    "Analytics": [
        st.Page("pages/sales_dashboard.py",   title="Sales Dashboard"),
    ],
    "ML": [
        st.Page("pages/ml_delivery_risk.py",  title="Delivery Risk Prediction"),
    ],
}

pg = st.navigation(pages)
pg.run()
