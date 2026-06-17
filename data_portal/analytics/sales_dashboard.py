import streamlit as st
import plotly.express as px
from shared.db import query

def render():
    st.title("Sales Dashboard")

    df = query("""
        SELECT
            DATE_TRUNC('month', o.order_date)::DATE  AS month,
            SUM(oi.sales)                            AS total_sales,
            SUM(oi.order_profit_per_order)           AS total_profit,
            COUNT(DISTINCT o.order_id)               AS total_orders
        FROM stg_order_items oi
        LEFT JOIN stg_order o ON oi.order_id = o.order_id
        GROUP BY 1
        ORDER BY 1
    """, layer="silver")

    if df.empty:
        st.warning("Không có dữ liệu!")
        return

    # KPI
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Sales",  f"${df['total_sales'].sum():,.0f}")
    col2.metric("Total Profit", f"${df['total_profit'].sum():,.0f}")
    col3.metric("Total Orders", f"{df['total_orders'].sum():,}")

    # Chart
    fig = px.line(df, x="month", y=["total_sales", "total_profit"],
                  title="Doanh thu & Lợi nhuận theo tháng")
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df)