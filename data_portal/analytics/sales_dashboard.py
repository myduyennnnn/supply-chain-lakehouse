import streamlit as st
import plotly.express as px
from shared.db import query

def render():
    # ====================================================
    # CUSTOM INJECTED CSS (LUXURY DARK STYLE)
    # ====================================================
    st.html("""
        <style>
            /* Nền tổng thể và font chữ */
            .stApp {
                background-color: #161515 !important;
                color: #e5e5e7 !important;
                font-family: 'Inter', sans-serif;
            }
            
            /* Sidebar Custom */
            [data-testid="stSidebar"] {
                background-color: #1c1b1b !important;
                border-right: 1px solid #332a15;
            }
            
            /* Tựa đề chính (Gold Gradient) */
            .main-title {
                font-size: 2.3rem;
                font-weight: 700;
                background: linear-gradient(45deg, #ffe082, #ffb300);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 2rem;
            }

            /* Tiêu đề Phân Khu (Section Headers) */
            .section-header {
                font-size: 1.4rem;
                font-weight: 600;
                color: #ffe082;
                border-left: 4px solid #ffb300;
                padding-left: 10px;
                margin-top: 2rem;
                margin-bottom: 1rem;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            
            /* Tinh chỉnh các thẻ Metric (Card KPI) */
            [data-testid="stMetricValue"] {
                color: #ffb300 !important;
                font-size: 1.8rem !important;
                font-weight: bold !important;
            }
            [data-testid="stMetricLabel"] {
                color: #b0bec5 !important;
                font-size: 0.85rem !important;
            }
            [data-testid="stMetric"] {
                background-color: #1e1d1d;
                border: 1px solid #3a321a;
                border-radius: 12px;
                padding: 12px 18px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            }
            
            /* Ngăn cách phân khu */
            hr {
                border-color: #332a15 !important;
                margin: 2.5rem 0 !important;
            }

            /* Style cho Tabs */
            .stTabs [data-baseweb="tab-list"] {
                gap: 8px;
            }
            .stTabs [data-baseweb="tab"] {
                background-color: #1e1d1d;
                border-radius: 8px 8px 0 0;
                padding: 10px 18px;
                color: #b0bec5;
            }
            .stTabs [aria-selected="true"] {
                background-color: #2a2310 !important;
                color: #ffe082 !important;
                border-bottom: 2px solid #ffb300;
            }
        </style>
    """)

    # Định dạng bảng màu đồ thị (Gold, Orange, Charcoal)
    GOLD_THEME = ["#ffe082", "#ffb300", "#ffa000", "#ff8f00", "#ff6f00", "#424242", "#212121"]
    
    # Helper đồng bộ layout cho các chart Plotly chìm vào nền tối
    def apply_plot_theme(fig):
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e5e5e7",
            title_font_color="#ffe082",
            margin=dict(l=20, r=20, t=40, b=20),
            xaxis=dict(gridcolor="#2c2514", zerolinecolor="#2c2514"),
            yaxis=dict(gridcolor="#2c2514", zerolinecolor="#2c2514")
        )
        return fig

    # Tiêu đề chính của Dashboard
    st.markdown('<h1 class="main-title">📦 Supply Chain Analytics Dashboard</h1>', unsafe_allow_html=True)

    # ====================================================
    # SIDEBAR FILTER (dùng chung cho cả 2 tab)
    # ====================================================
    region_df = query("""
        SELECT DISTINCT order_region
        FROM mart_executive_summary
        ORDER BY order_region
    """)
    all_regions = region_df["order_region"].tolist()

    selected_region = st.sidebar.multiselect(
        "Region",
        all_regions,
        default=all_regions
    )

    if not selected_region:
        st.warning("Vui lòng chọn ít nhất 1 region.")
        return

    region_placeholders = ", ".join(f"$region_{i}" for i in range(len(selected_region)))
    region_params = {f"region_{i}": region for i, region in enumerate(selected_region)}

    # ====================================================
    # TOP KPI METRICS (headline, hiển thị chung trên cả 2 tab)
    # ====================================================
    kpi = query(
        f"""
        SELECT
            SUM(total_sales)               AS total_sales,
            SUM(total_profit)              AS total_profit,
            SUM(total_orders)              AS total_orders
        FROM mart_executive_summary
        WHERE order_region IN ({region_placeholders})
        """,
        params=region_params
    )

    total_sales = float(kpi["total_sales"][0] or 0)
    total_profit = float(kpi["total_profit"][0] or 0)
    total_orders = int(kpi["total_orders"][0] or 0)
    profit_margin = (total_profit / total_sales * 100 if total_sales > 0 else 0)

    # Khối KPI đầu trang
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Sales", f"${total_sales:,.0f}")
    c2.metric("Total Profit", f"${total_profit:,.0f}")
    c3.metric("Orders", f"{total_orders:,}")
    c4.metric("Margin %", f"{profit_margin:.2f}%")

    st.write("")
    # 2 TAB: DESCRIPTIVE ANALYTICS vs DIAGNOSTIC ANALYTICS
    tab_descriptive, tab_diagnostic = st.tabs(["Descriptive Analytics", "Diagnostic Analytics"])

    # TAB 1: DESCRIPTIVE ANALYTICS — "Cái gì đã xảy ra"
    with tab_descriptive:

        # --- Executive & Customer Analytics ---
        st.markdown('<div class="section-header">Executive & Customer Analytics</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            # Sales by Department (Bar)
            sales_department = query(
                f"""
                SELECT department_name, SUM(total_sales) AS total_sales
                FROM mart_executive_summary
                WHERE order_region IN ({region_placeholders})
                GROUP BY department_name
                ORDER BY total_sales DESC
                """,
                params=region_params
            )
            fig1 = px.bar(
                sales_department, x="department_name", y="total_sales",
                title="Sales by Department", color_discrete_sequence=[GOLD_THEME[1]]
            )
            st.plotly_chart(apply_plot_theme(fig1), use_container_width=True)

        with col2:
            # Customer Segment (Donut)
            segment = query("""
                SELECT customer_segment, SUM(total_customers) AS total_customers
                FROM mart_customer_summary
                GROUP BY customer_segment
            """)
            fig2 = px.pie(
                segment, names="customer_segment", values="total_customers",
                title="Customer Segment Distribution", color_discrete_sequence=GOLD_THEME
            )
            fig2.update_traces(hole=.4)
            st.plotly_chart(apply_plot_theme(fig2), use_container_width=True)

        col1_b, col2_b = st.columns(2)
        with col1_b:
            # Orders by Region (Donut)
            region_orders = query(
                f"""
                SELECT order_region, SUM(total_orders) AS total_orders
                FROM mart_executive_summary
                WHERE order_region IN ({region_placeholders})
                GROUP BY order_region
                ORDER BY total_orders DESC
                """,
                params=region_params
            )
            fig3 = px.pie(
                region_orders, names="order_region", values="total_orders",
                title="Orders by Region", color_discrete_sequence=GOLD_THEME
            )
            fig3.update_traces(hole=.4)
            st.plotly_chart(apply_plot_theme(fig3), use_container_width=True)

        with col2_b:
            # Top 10 Countries (Bar)
            country = query("""
                SELECT customer_country, SUM(total_customers) AS total_customers
                FROM mart_customer_summary
                GROUP BY customer_country
                ORDER BY total_customers DESC
                LIMIT 10
            """)
            fig4 = px.bar(
                country, x="customer_country", y="total_customers",
                title="Top 10 Countries", color_discrete_sequence=[GOLD_THEME[2]]
            )
            st.plotly_chart(apply_plot_theme(fig4), use_container_width=True)

        st.divider()

        # --- Product & Supply Chain Overview ---
        st.markdown('<div class="section-header">Product & Supply Chain Overview</div>', unsafe_allow_html=True)

        col3, col4 = st.columns(2)

        with col3:
            # Top Product Categories (Bar)
            category_sales = query("""
                SELECT category_name, total_sales
                FROM mart_product_category_sales
                ORDER BY total_sales DESC
                LIMIT 15
            """)
            fig5 = px.bar(
                category_sales, x="category_name", y="total_sales",
                title="Top Product Categories", color_discrete_sequence=[GOLD_THEME[0]]
            )
            st.plotly_chart(apply_plot_theme(fig5), use_container_width=True)

            # Shipping Mode (Donut)
            shipping_mode = query("""
                SELECT shipping_mode, total_orders
                FROM mart_supply_chain_shipping_mode
                ORDER BY total_orders DESC
            """)
            fig6 = px.pie(
                shipping_mode, names="shipping_mode", values="total_orders",
                title="Shipping Mode Distribution", color_discrete_sequence=GOLD_THEME
            )
            fig6.update_traces(hole=.4)
            st.plotly_chart(apply_plot_theme(fig6), use_container_width=True)

        with col4:
            # Discount Impact on Sales — tổng quan (Scatter)
            discount = query("""
                SELECT order_item_discount_rate, avg_sales
                FROM mart_product_discount_impact
                ORDER BY order_item_discount_rate
            """)
            fig7 = px.scatter(
                discount, x="order_item_discount_rate", y="avg_sales",
                title="Discount Impact on Sales (overview)", color_discrete_sequence=[GOLD_THEME[1]]
            )
            st.plotly_chart(apply_plot_theme(fig7), use_container_width=True)

            # Average Delay by Region (Bar)
            delay_region = query("""
                SELECT order_region, avg_delay
                FROM mart_supply_chain_region_delay
                ORDER BY avg_delay DESC
            """)
            fig8 = px.bar(
                delay_region, x="order_region", y="avg_delay",
                title="Average Delay by Region", color_discrete_sequence=[GOLD_THEME[3]]
            )
            st.plotly_chart(apply_plot_theme(fig8), use_container_width=True)

        st.divider()

        # --- AI Monitoring Overview ---
        st.markdown('<div class="section-header">AI Monitoring Overview</div>', unsafe_allow_html=True)

        ai_kpi = query("""
            SELECT predicted_late, actual_late, violations
            FROM mart_ai_monitoring_summary
        """)
        ak1, ak2, ak3 = st.columns(3)
        ak1.metric("Predicted Late", int(ai_kpi["predicted_late"][0] or 0))
        ak2.metric("Actual Late", int(ai_kpi["actual_late"][0] or 0))
        ak3.metric("Label Violations", int(ai_kpi["violations"][0] or 0))

        st.write("")

        risk = query("""
            SELECT order_region, risk_orders
            FROM mart_ai_monitoring_risk_by_region
            ORDER BY risk_orders DESC
        """)
        fig9 = px.bar(
            risk, x="order_region", y="risk_orders",
            title="High Risk Regions", color_discrete_sequence=["#e67e22"]
        )
        st.plotly_chart(apply_plot_theme(fig9), use_container_width=True)

    # TAB 2: DIAGNOSTIC ANALYTICS — "Tại sao nó xảy ra"
    with tab_diagnostic:

        # --- Profitability: Margin by Department ---
        st.markdown('<div class="section-header">Profitability: Margin by Department</div>', unsafe_allow_html=True)
        st.caption("Combo region × department nào đang lỗ, weighted theo region đang chọn ở sidebar.")

        margin_dept = query(
            f"""
            SELECT
                department_name,
                SUM(total_sales)  AS total_sales,
                SUM(total_profit) AS total_profit,
                ROUND(SUM(total_profit) / NULLIF(SUM(total_sales), 0) * 100, 2) AS profit_margin_pct
            FROM mart_executive_summary
            WHERE order_region IN ({region_placeholders})
            GROUP BY department_name
            ORDER BY profit_margin_pct ASC
            """,
            params=region_params
        )
        fig10 = px.bar(
            margin_dept, x="department_name", y="profit_margin_pct",
            title="Profit Margin % by Department",
            color="profit_margin_pct",
            color_continuous_scale=["#e74c3c", "#5d4a1a", GOLD_THEME[1]]
        )
        fig10.add_hline(y=0, line_dash="dash", line_color="#e5e5e7")
        st.plotly_chart(apply_plot_theme(fig10), use_container_width=True)

        st.divider()

        # --- Discount Sensitivity by Category ---
        st.markdown('<div class="section-header">Discount Sensitivity by Category</div>', unsafe_allow_html=True)
        st.caption("Top 8 category theo sales — category nào tăng/giảm sales mạnh nhất khi discount tăng.")

        discount_category = query("""
            SELECT category_name, discount_bucket, avg_sales
            FROM mart_product_discount_impact_by_category
            WHERE category_name IN (
                SELECT category_name FROM mart_product_category_sales
                ORDER BY total_sales DESC LIMIT 8
            )
            ORDER BY discount_bucket
        """)
        fig11 = px.line(
            discount_category, x="discount_bucket", y="avg_sales", color="category_name",
            title="Discount Impact by Category", markers=True,
            color_discrete_sequence=GOLD_THEME
        )
        st.plotly_chart(apply_plot_theme(fig11), use_container_width=True)

        st.divider()

        # --- Customer Segment Revenue ---
        st.markdown('<div class="section-header">Customer Segment Revenue</div>', unsafe_allow_html=True)
        st.caption("Segment nào thực sự đóng góp sales/profit, không chỉ đếm số lượng customer.")

        segment_revenue = query("""
            SELECT customer_segment, total_customers, total_sales, total_profit, avg_revenue_per_customer
            FROM mart_customer_segment_revenue
            ORDER BY total_sales DESC
        """)

        col5, col6 = st.columns(2)
        with col5:
            fig14 = px.bar(
                segment_revenue, x="customer_segment", y="total_sales",
                title="Total Sales by Customer Segment", color_discrete_sequence=[GOLD_THEME[2]]
            )
            st.plotly_chart(apply_plot_theme(fig14), use_container_width=True)
        with col6:
            fig15 = px.bar(
                segment_revenue, x="customer_segment", y="avg_revenue_per_customer",
                title="Avg Revenue per Customer by Segment", color_discrete_sequence=[GOLD_THEME[4]]
            )
            st.plotly_chart(apply_plot_theme(fig15), use_container_width=True)

        st.divider()

        # --- Trend Over Time ---
        st.markdown('<div class="section-header">Trend Over Time</div>', unsafe_allow_html=True)
        st.caption("Biến động sales/profit/delay theo tháng, làm nền cho việc drill xuống nguyên nhân.")

        trend = query("""
            SELECT year, month, month_name, total_sales, total_profit, avg_delay
            FROM mart_trend_monthly
            ORDER BY year, month
        """)
        trend["period"] = trend["month_name"].str.slice(0, 3) + " " + trend["year"].astype(str)

        col7, col8 = st.columns(2)
        with col7:
            fig12 = px.line(
                trend, x="period", y=["total_sales", "total_profit"],
                title="Sales & Profit Trend by Month", markers=True,
                color_discrete_sequence=GOLD_THEME
            )
            st.plotly_chart(apply_plot_theme(fig12), use_container_width=True)
        with col8:
            fig13 = px.line(
                trend, x="period", y="avg_delay",
                title="Average Delivery Delay Trend by Month", markers=True,
                color_discrete_sequence=[GOLD_THEME[3]]
            )
            st.plotly_chart(apply_plot_theme(fig13), use_container_width=True)

        st.divider()

        # --- Risk & Violations by Shipping Mode x Region ---
        st.markdown('<div class="section-header">Risk & Violations by Shipping Mode x Region</div>', unsafe_allow_html=True)
        st.caption("Model AI dự đoán sai / vi phạm label tập trung ở combo region x shipping_mode nào.")

        risk_mode_region = query("""
            SELECT order_region, shipping_mode, violations
            FROM mart_ai_monitoring_risk_by_mode_region
        """)
        fig16 = px.bar(
            risk_mode_region, x="shipping_mode", y="violations", color="order_region",
            title="Label Violations by Shipping Mode x Region", barmode="group",
            color_discrete_sequence=GOLD_THEME
        )
        st.plotly_chart(apply_plot_theme(fig16), use_container_width=True)