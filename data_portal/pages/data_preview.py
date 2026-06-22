import streamlit as st
from shared.db import list_tables, load_table

st.title("Data Preview")

layer = st.selectbox("Layer", ["silver", "gold"])
tables = list_tables(layer)

if not tables:
    st.warning(f"Chưa có table nào trong layer '{layer}'")
    st.stop()

selected_table = st.selectbox("Table", tables)
st.subheader(f"{layer}.{selected_table}")

try:
    df = load_table(selected_table, layer=layer)
    col1, col2 = st.columns(2)
    col1.metric("Rows", len(df))
    col2.metric("Columns", len(df.columns))
    st.dataframe(df.head(100), use_container_width=True)
except Exception as e:
    st.error(f"Không đọc được table '{selected_table}': {e}")
