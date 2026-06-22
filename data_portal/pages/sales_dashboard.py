import streamlit as st
import plotly.express as px
from shared.db import query

GOLD_THEME = ["#6F42C1", "#007BFF", "#00CCCC", "#0DCAF0", "#17A2B8", "#8A5EDB", "#3395FF"]

def _theme(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#8A8FA8",
        title_font_color="#1E2243",
        title_font_size=16,
        title_font_family="'Outfit', sans-serif",
        margin=dict(l=16, r=16, t=50, b=16),
        xaxis=dict(gridcolor="#EEECf8", zerolinecolor="#EEECf8", showgrid=True),
        yaxis=dict(gridcolor="#EEECf8", zerolinecolor="#EEECf8", showgrid=True),
        legend=dict(bgcolor="rgba(255,255,255,0.75)", bordercolor="#E4E8F5", borderwidth=1),
    )
    return fig
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
    /* Column 3 — Teal */
    [data-testid="column"]:nth-child(3) [data-testid="stMetric"] {
        background: linear-gradient(140deg, #33E0E0 0%, #00CCCC 100%);
    }
    /* Column 4 — Cyan-Teal */
    [data-testid="column"]:nth-child(4) [data-testid="stMetric"] {
        background: linear-gradient(140deg, #30D6F5 0%, #17A2B8 100%);
    }

    /* ── Divider as gradient line ── */
    hr {
        border: none !important;
        height: 2px !important;
        background: linear-gradient(90deg, #6F42C1, #007BFF, #00CCCC) !important;
        opacity: 0.28 !important;
        margin: 3rem 0 !important;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 2px solid #E4E8F5;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border: none;
        padding: 10px 24px 12px;
        color: #8A8FA8;
        font-weight: 700;
        font-size: 1rem;
        border-radius: 10px 10px 0 0;
        transition: color 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover { color: #6F42C1; }
    .stTabs [aria-selected="true"] {
        color: #6F42C1 !important;
        border-bottom: 3px solid #6F42C1 !important;
        background: rgba(111,66,193,0.07) !important;
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

# Cập nhật lại thẻ Header để áp dụng class main-title
st.markdown('<h1 class="main-title">Supply Chain Analytics Dashboard</h1>', unsafe_allow_html=True)

# ── Sidebar filter ─────────────────────────────────────────────────────────────
region_df = query("SELECT DISTINCT order_region FROM mart_executive_summary ORDER BY order_region")
all_regions = region_df["order_region"].tolist()

selected_region = st.sidebar.multiselect("Region", all_regions, default=all_regions)

if not selected_region:
    st.warning("Vui lòng chọn ít nhất 1 region.")
    st.stop()

region_placeholders = ", ".join(f"$region_{i}" for i in range(len(selected_region)))
region_params = {f"region_{i}": r for i, r in enumerate(selected_region)}

# ── Top KPI ───────────────────────────────────────────────────────────────────
kpi = query(
    f"SELECT SUM(total_sales) AS total_sales, SUM(total_profit) AS total_profit, SUM(total_orders) AS total_orders "
    f"FROM mart_executive_summary WHERE order_region IN ({region_placeholders})",
    params=region_params,
)
total_sales   = float(kpi["total_sales"][0] or 0)
total_profit  = float(kpi["total_profit"][0] or 0)
total_orders  = int(kpi["total_orders"][0] or 0)
profit_margin = total_profit / total_sales * 100 if total_sales else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Sales",   f"${total_sales:,.0f}")
c2.metric("Total Profit",  f"${total_profit:,.0f}")
c3.metric("Orders",        f"{total_orders:,}")
c4.metric("Margin %",      f"{profit_margin:.2f}%")

st.write("")

tab_desc, tab_diag = st.tabs(["Descriptive Analytics", "Diagnostic Analytics"])

# ── Tab 1: Descriptive ────────────────────────────────────────────────────────
with tab_desc:

    st.markdown('<div class="section-header">Executive & Customer Analytics</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    with col1:
        df = query(
            f"SELECT department_name, SUM(total_sales) AS total_sales FROM mart_executive_summary "
            f"WHERE order_region IN ({region_placeholders}) GROUP BY department_name ORDER BY total_sales DESC",
            params=region_params,
        )
        st.plotly_chart(_theme(px.bar(df, x="department_name", y="total_sales",
            title="Sales by Department", color_discrete_sequence=[GOLD_THEME[1]])), use_container_width=True)

    with col2:
        df = query("SELECT customer_segment, SUM(total_customers) AS total_customers FROM mart_customer_summary GROUP BY customer_segment")
        fig = px.pie(df, names="customer_segment", values="total_customers",
            title="Customer Segment Distribution", color_discrete_sequence=GOLD_THEME)
        fig.update_traces(hole=.4)
        st.plotly_chart(_theme(fig), use_container_width=True)

    col1b, col2b = st.columns(2)
    with col1b:
        df = query(
            f"SELECT order_region, SUM(total_orders) AS total_orders FROM mart_executive_summary "
            f"WHERE order_region IN ({region_placeholders}) GROUP BY order_region ORDER BY total_orders DESC",
            params=region_params,
        )
        fig = px.pie(df, names="order_region", values="total_orders",
            title="Orders by Region", color_discrete_sequence=GOLD_THEME)
        fig.update_traces(hole=.4)
        st.plotly_chart(_theme(fig), use_container_width=True)

    with col2b:
        df = query("SELECT customer_country, SUM(total_customers) AS total_customers FROM mart_customer_summary GROUP BY customer_country ORDER BY total_customers DESC LIMIT 10")
        st.plotly_chart(_theme(px.bar(df, x="customer_country", y="total_customers",
            title="Top 10 Countries", color_discrete_sequence=[GOLD_THEME[2]])), use_container_width=True)

    st.divider()
    st.markdown('<div class="section-header">Product & Supply Chain Overview</div>', unsafe_allow_html=True)
    col3, col4 = st.columns(2)

    with col3:
        df = query("SELECT category_name, total_sales FROM mart_product_category_sales ORDER BY total_sales DESC LIMIT 15")
        st.plotly_chart(_theme(px.bar(df, x="category_name", y="total_sales",
            title="Top Product Categories", color_discrete_sequence=[GOLD_THEME[0]])), use_container_width=True)

        df = query("SELECT shipping_mode, total_orders FROM mart_supply_chain_shipping_mode ORDER BY total_orders DESC")
        fig = px.pie(df, names="shipping_mode", values="total_orders",
            title="Shipping Mode Distribution", color_discrete_sequence=GOLD_THEME)
        fig.update_traces(hole=.4)
        st.plotly_chart(_theme(fig), use_container_width=True)

    with col4:
        df = query("SELECT order_item_discount_rate, avg_sales FROM mart_product_discount_impact ORDER BY order_item_discount_rate")
        st.plotly_chart(_theme(px.scatter(df, x="order_item_discount_rate", y="avg_sales",
            title="Discount Impact on Sales", color_discrete_sequence=[GOLD_THEME[1]])), use_container_width=True)

        df = query("SELECT order_region, avg_delay FROM mart_supply_chain_region_delay ORDER BY avg_delay DESC")
        st.plotly_chart(_theme(px.bar(df, x="order_region", y="avg_delay",
            title="Average Delay by Region", color_discrete_sequence=[GOLD_THEME[3]])), use_container_width=True)

    st.divider()
    st.markdown('<div class="section-header">AI Monitoring Overview</div>', unsafe_allow_html=True)

    ai = query("SELECT predicted_late, actual_late, violations FROM mart_ai_monitoring_summary")
    ak1, ak2, ak3 = st.columns(3)
    ak1.metric("Predicted Late",   int(ai["predicted_late"][0] or 0))
    ak2.metric("Actual Late",      int(ai["actual_late"][0] or 0))
    ak3.metric("Label Violations", int(ai["violations"][0] or 0))

    st.write("")
    df = query("SELECT order_region, risk_orders FROM mart_ai_monitoring_risk_by_region ORDER BY risk_orders DESC")
    st.plotly_chart(_theme(px.bar(df, x="order_region", y="risk_orders",
        title="High Risk Regions", color_discrete_sequence=["#e67e22"])), use_container_width=True)

# ── Tab 2: Diagnostic ─────────────────────────────────────────────────────────
with tab_diag:

    st.markdown('<div class="section-header">Profitability: Margin by Department</div>', unsafe_allow_html=True)
    st.caption("Combo region × department nào đang lỗ, weighted theo region đang chọn ở sidebar.")

    df = query(
        f"SELECT department_name, SUM(total_sales) AS total_sales, SUM(total_profit) AS total_profit, "
        f"ROUND(SUM(total_profit)/NULLIF(SUM(total_sales),0)*100,2) AS profit_margin_pct "
        f"FROM mart_executive_summary WHERE order_region IN ({region_placeholders}) "
        f"GROUP BY department_name ORDER BY profit_margin_pct ASC",
        params=region_params,
    )
    fig = px.bar(df, x="department_name", y="profit_margin_pct",
        title="Profit Margin % by Department", color="profit_margin_pct",
        color_continuous_scale=["#e74c3c", "#5d4a1a", GOLD_THEME[1]])
    fig.add_hline(y=0, line_dash="dash", line_color="#e5e5e7")
    st.plotly_chart(_theme(fig), use_container_width=True)

    st.divider()
    st.markdown('<div class="section-header">Discount Sensitivity by Category</div>', unsafe_allow_html=True)
    st.caption("Top 8 category theo sales — category nào tăng/giảm sales mạnh nhất khi discount tăng.")

    df = query("""
        SELECT category_name, discount_bucket, avg_sales
        FROM mart_product_discount_impact_by_category
        WHERE category_name IN (
            SELECT category_name FROM mart_product_category_sales ORDER BY total_sales DESC LIMIT 8
        )
        ORDER BY discount_bucket
    """)
    st.plotly_chart(_theme(px.line(df, x="discount_bucket", y="avg_sales", color="category_name",
        title="Discount Impact by Category", markers=True,
        color_discrete_sequence=GOLD_THEME)), use_container_width=True)

    st.divider()
    st.markdown('<div class="section-header">Customer Segment Revenue</div>', unsafe_allow_html=True)
    st.caption("Segment nào thực sự đóng góp sales/profit, không chỉ đếm số lượng customer.")

    df = query("SELECT customer_segment, total_customers, total_sales, total_profit, avg_revenue_per_customer FROM mart_customer_segment_revenue ORDER BY total_sales DESC")
    col5, col6 = st.columns(2)
    with col5:
        st.plotly_chart(_theme(px.bar(df, x="customer_segment", y="total_sales",
            title="Total Sales by Customer Segment", color_discrete_sequence=[GOLD_THEME[2]])), use_container_width=True)
    with col6:
        st.plotly_chart(_theme(px.bar(df, x="customer_segment", y="avg_revenue_per_customer",
            title="Avg Revenue per Customer by Segment", color_discrete_sequence=[GOLD_THEME[4]])), use_container_width=True)

    st.divider()
    st.markdown('<div class="section-header">Trend Over Time</div>', unsafe_allow_html=True)
    st.caption("Biến động sales/profit/delay theo tháng.")

    trend = query("SELECT year, month, month_name, total_sales, total_profit, avg_delay FROM mart_trend_monthly ORDER BY year, month")
    trend["period"] = trend["month_name"].str.slice(0, 3) + " " + trend["year"].astype(str)

    col7, col8 = st.columns(2)
    with col7:
        st.plotly_chart(_theme(px.line(trend, x="period", y=["total_sales", "total_profit"],
            title="Sales & Profit Trend by Month", markers=True,
            color_discrete_sequence=GOLD_THEME)), use_container_width=True)
    with col8:
        st.plotly_chart(_theme(px.line(trend, x="period", y="avg_delay",
            title="Average Delivery Delay Trend by Month", markers=True,
            color_discrete_sequence=[GOLD_THEME[3]])), use_container_width=True)

    st.divider()
    st.markdown('<div class="section-header">Risk & Violations by Shipping Mode × Region</div>', unsafe_allow_html=True)
    st.caption("Model AI dự đoán sai / vi phạm label tập trung ở combo region × shipping_mode nào.")

    df = query("SELECT order_region, shipping_mode, violations FROM mart_ai_monitoring_risk_by_mode_region")
    st.plotly_chart(_theme(px.bar(df, x="shipping_mode", y="violations", color="order_region",
        title="Label Violations by Shipping Mode × Region", barmode="group",
        color_discrete_sequence=GOLD_THEME)), use_container_width=True)
