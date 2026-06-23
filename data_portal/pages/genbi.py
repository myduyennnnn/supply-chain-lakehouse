"""
GenBI Agent — Natural Language → SQL → DuckDB (R2 Parquet)

Dùng Groq (Llama 3.3 70B) để chuyển câu hỏi tiếng Việt thành SQL,
chạy trực tiếp trên gold layer qua httpfs (không cần lakehouse.db).
"""

import os
import re

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

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

    /* ── Sidebar: inline code ── */
    [data-testid="stSidebar"] code {
        background: rgba(255,255,255,0.10) !important;
        color: #00CCCC !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 4px !important;
        padding: 1px 5px !important;
    }

    /* ── Sidebar: sample question buttons ── */
    [data-testid="stSidebar"] .stButton > button {
        background: rgba(255,255,255,0.07) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255,255,255,0.18) !important;
        border-radius: 8px !important;
        font-size: 0.85rem !important;
        text-align: left !important;
        transition: background 0.2s ease, border-color 0.2s ease !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(111,66,193,0.35) !important;
        border-color: #6F42C1 !important;
    }
</style>
""")

# ── R2 paths cho tất cả gold tables ──────────────────────────────────────────
BUCKET = os.getenv("R2_BUCKET_NAME", "supply-chain-ai-native")

GOLD_TABLES = {
    "main_gold.dim_customer":       f"s3://{BUCKET}/gold/dimensions/dim_customer.parquet",
    "main_gold.dim_product":        f"s3://{BUCKET}/gold/dimensions/dim_product.parquet",
    "main_gold.dim_order":          f"s3://{BUCKET}/gold/dimensions/dim_order.parquet",
    "main_gold.dim_date":           f"s3://{BUCKET}/gold/dimensions/dim_date.parquet",
    "main_gold.fact_order_items":   f"s3://{BUCKET}/gold/facts/fact_order_items.parquet",
    "main_gold.mart_executive_summary":                  f"s3://{BUCKET}/gold/marts/dashboard/mart_executive_summary.parquet",
    "main_gold.mart_trend_monthly":                      f"s3://{BUCKET}/gold/marts/dashboard/mart_trend_monthly.parquet",
    "main_gold.mart_customer_summary":                   f"s3://{BUCKET}/gold/marts/dashboard/mart_customer_summary.parquet",
    "main_gold.mart_customer_segment_revenue":           f"s3://{BUCKET}/gold/marts/dashboard/mart_customer_segment_revenue.parquet",
    "main_gold.mart_product_category_sales":             f"s3://{BUCKET}/gold/marts/dashboard/mart_product_category_sales.parquet",
    "main_gold.mart_product_discount_impact":            f"s3://{BUCKET}/gold/marts/dashboard/mart_product_discount_impact.parquet",
    "main_gold.mart_product_discount_impact_by_category": f"s3://{BUCKET}/gold/marts/dashboard/mart_product_discount_impact_by_category.parquet",
    "main_gold.mart_supply_chain_shipping_mode":         f"s3://{BUCKET}/gold/marts/dashboard/mart_supply_chain_shipping_mode.parquet",
    "main_gold.mart_supply_chain_region_delay":          f"s3://{BUCKET}/gold/marts/dashboard/mart_supply_chain_region_delay.parquet",
    "main_gold.mart_ai_monitoring_summary":              f"s3://{BUCKET}/gold/marts/dashboard/mart_ai_monitoring_summary.parquet",
    "main_gold.mart_ai_monitoring_risk_by_region":       f"s3://{BUCKET}/gold/marts/dashboard/mart_ai_monitoring_risk_by_region.parquet",
    "main_gold.mart_ai_monitoring_risk_by_mode_region":  f"s3://{BUCKET}/gold/marts/dashboard/mart_ai_monitoring_risk_by_mode_region.parquet",
}

# ── Schema description làm system prompt ─────────────────────────────────────
SCHEMA_DESCRIPTION = """
Bạn là chuyên gia phân tích dữ liệu chuỗi cung ứng (Supply Chain).
Bạn có quyền truy cập Data Warehouse với các bảng sau trong schema main_gold của DuckDB.
Chỉ viết câu SQL thuần túy, không markdown, không giải thích.
Luôn dùng prefix main_gold. trước tên bảng.
Giới hạn LIMIT 100 nếu không có yêu cầu cụ thể.

=== FACT TABLE ===
main_gold.fact_order_items  -- grain: 1 dòng = 1 order item
  order_item_id, order_id, product_card_id, customer_id
  order_date_key, shipping_date_key          -- FK → dim_date.date_key (YYYYMMDD)
  order_item_quantity     INTEGER
  order_item_product_price DOUBLE
  order_item_discount_amount DOUBLE
  order_item_discount_rate DOUBLE
  sales                   DOUBLE  -- doanh thu thực tế
  order_item_total        DOUBLE
  order_item_profit_ratio DOUBLE
  order_profit            DOUBLE  -- lợi nhuận

=== DIMENSION TABLES ===
main_gold.dim_customer
  customer_id, customer_full_name
  customer_segment  VARCHAR  -- 'Consumer', 'Corporate', 'Home Office'
  customer_city, customer_state, customer_country, customer_street, customer_zipcode

main_gold.dim_product
  product_card_id, product_name, product_price
  product_status_label  VARCHAR  -- 'Active' / 'Inactive'
  category_id, category_name, department_id, department_name

main_gold.dim_order
  order_id, payment_type, order_status
  market        VARCHAR  -- 'Pacific Asia','USCA','Africa','Europe','LATAM'
  order_region, order_country, order_state, order_city
  order_date TIMESTAMP, shipping_date TIMESTAMP
  shipping_mode  VARCHAR  -- 'Standard Class','First Class','Second Class','Same Day'
  delivery_status, days_scheduled, days_actual
  days_diff      INTEGER  -- âm=sớm hạn, dương=muộn
  late_delivery_risk BOOLEAN
  is_actual_late     INTEGER

main_gold.dim_date
  date_key INTEGER (YYYYMMDD), date_day DATE
  year, quarter, month BIGINT
  month_name, day_name VARCHAR
  day_of_month, day_of_week, week_of_year BIGINT

=== MART TABLES (dùng khi câu hỏi về tổng hợp) ===
main_gold.mart_executive_summary
  order_region, department_name, total_orders, total_sales, total_profit, profit_margin_pct

main_gold.mart_trend_monthly
  year, month, month_name, total_orders, total_sales, total_profit, avg_delay

main_gold.mart_customer_segment_revenue
  customer_segment, total_customers, total_sales, total_profit, avg_revenue_per_customer

main_gold.mart_customer_summary
  customer_segment, customer_country, total_customers

main_gold.mart_product_category_sales
  category_name, total_sales

main_gold.mart_product_discount_impact
  order_item_discount_rate, avg_sales

main_gold.mart_product_discount_impact_by_category
  category_name, discount_bucket, order_item_count, avg_sales

main_gold.mart_supply_chain_region_delay
  order_region, avg_delay

main_gold.mart_supply_chain_shipping_mode
  shipping_mode, total_orders

main_gold.mart_ai_monitoring_summary
  predicted_late, actual_late, violations

main_gold.mart_ai_monitoring_risk_by_region
  order_region, risk_orders

main_gold.mart_ai_monitoring_risk_by_mode_region
  order_region, shipping_mode, total_orders, predicted_late, actual_late, violations

=== QUY TẮC ===
1. Dùng mart tables khi câu hỏi về tổng hợp/summary — nhanh hơn JOIN từ fact
2. Dùng fact + dim khi cần chi tiết hoặc mart không đủ cột
3. JOIN fact_order_items với dim_order qua order_id
4. JOIN fact_order_items với dim_customer qua customer_id
5. JOIN fact_order_items với dim_product qua product_card_id
6. JOIN fact_order_items với dim_date qua order_date_key = date_key
"""

SAMPLE_QUESTIONS = [
    "Top 5 sản phẩm doanh thu cao nhất",
    "Doanh thu theo từng thị trường",
    "Tỷ lệ giao hàng muộn theo shipping mode",
    "Top 10 khách hàng mua nhiều nhất",
    "Doanh thu và lợi nhuận theo tháng",
    "Phân khúc khách hàng nào lợi nhuận cao nhất",
    "Khu vực nào có tỷ lệ giao muộn cao nhất",
    "Danh mục sản phẩm nào bán chạy nhất",
]


# DuckDB connection (in-memory, đọc thẳng từ R2)
@st.cache_resource
def get_genbi_connection() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(database=":memory:")

    try:
        con.execute("LOAD httpfs")
    except Exception:
        con.execute("INSTALL httpfs")
        con.execute("LOAD httpfs")

    con.execute(f"SET s3_access_key_id='{os.getenv('R2_ACCESS_KEY_ID')}'")
    con.execute(f"SET s3_secret_access_key='{os.getenv('R2_SECRET_ACCESS_KEY')}'")

    endpoint = os.getenv("R2_ENDPOINT_URL", "")
    if endpoint:
        con.execute(f"SET s3_endpoint='{endpoint.replace('https://', '')}'")
        con.execute("SET s3_url_style='path'")
        con.execute("SET s3_region='auto'")

    con.execute("SET s3_use_ssl=true")

    # Tạo schema main_gold và đăng ký tất cả views
    con.execute("CREATE SCHEMA IF NOT EXISTS main_gold")
    for view_name, s3_path in GOLD_TABLES.items():
        con.execute(
            f"CREATE OR REPLACE VIEW {view_name} AS "
            f"SELECT * FROM read_parquet('{s3_path}')"
        )

    return con


# LLM: text → SQL 
def text_to_sql(question: str, api_key: str) -> str:
    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SCHEMA_DESCRIPTION},
            {"role": "user",   "content": f"Chuyển câu hỏi sau thành SQL:\n{question}\n\nChỉ trả về SQL thuần túy."},
        ],
        temperature=0.1,
        max_tokens=1000,
    )
    sql = response.choices[0].message.content.strip()
    sql = re.sub(r"```sql\n?", "", sql)
    sql = re.sub(r"```\n?", "", sql)
    return sql.strip()


# Auto chart
def render_chart(df: pd.DataFrame) -> None:
    num_cols = df.select_dtypes(include="number").columns.tolist()
    str_cols = df.select_dtypes(include="object").columns.tolist()

    if len(df) < 2 or not num_cols or not str_cols:
        return

    with st.expander("Biểu đồ", expanded=True):
        col1, col2 = st.columns([1, 3])
        with col1:
            chart_col = st.selectbox(
                "Cột giá trị:",
                num_cols,
                key=f"chart_{len(st.session_state.get('messages', []))}",
            )
            chart_type = st.radio("Loại biểu đồ:", ["Bar", "Line", "Pie"], horizontal=True)

        with col2:
            x = str_cols[0]
            if chart_type == "Bar":
                fig = px.bar(df, x=x, y=chart_col, color_discrete_sequence=GOLD_THEME)
            elif chart_type == "Line":
                fig = px.line(df, x=x, y=chart_col, markers=True,
                              color_discrete_sequence=GOLD_THEME)
            else:
                fig = px.pie(df, names=x, values=chart_col,
                             color_discrete_sequence=GOLD_THEME)
            st.plotly_chart(_theme(fig), use_container_width=True)


# Main
def main():
    st.markdown('<h1 class="main-title">GenBI Agent — Hỏi đáp AI</h1>', unsafe_allow_html=True)
    st.caption("Đặt câu hỏi bằng tiếng Việt, AI tự viết SQL và truy vấn data warehouse")
    st.divider()

    api_key = os.getenv("GROQ_API_KEY", "")

    # Sidebar
    with st.sidebar:
        st.markdown("**Bảng có sẵn:**")
        st.markdown("- `fact_order_items`")
        st.markdown("- `dim_customer / product / order / date`")
        st.markdown("- 12 `mart_*` tables")

        st.divider()
        st.markdown("**Câu hỏi mẫu:**")
        for q in SAMPLE_QUESTIONS:
            if st.button(q, use_container_width=True):
                st.session_state["pending_question"] = q

    # Session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "pending_question" not in st.session_state:
        st.session_state.pending_question = ""

    # Hiển thị lịch sử
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                if msg.get("sql"):
                    with st.expander("SQL được tạo", expanded=False):
                        st.code(msg["sql"], language="sql")
                if msg.get("df") is not None:
                    st.success(f"{len(msg['df']):,} dòng")
                    st.dataframe(msg["df"], use_container_width=True)
                if msg.get("error"):
                    st.error(msg["error"])
            else:
                st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("Nhập câu hỏi về dữ liệu chuỗi cung ứng...")

    # Merge sample question click với chat input
    question = user_input or st.session_state.pop("pending_question", "")

    if not question:
        return

    if not api_key:
        st.warning("Vui lòng nhập Groq API Key ở sidebar!")
        return

    # Hiển thị câu hỏi user
    with st.chat_message("user"):
        st.markdown(question)
    st.session_state.messages.append({"role": "user", "content": question})

    # Xử lý + hiển thị kết quả
    with st.chat_message("assistant"):
        with st.spinner("Đang phân tích..."):
            sql = None
            try:
                sql = text_to_sql(question, api_key)

                with st.expander("SQL được tạo", expanded=True):
                    st.code(sql, language="sql")

                con = get_genbi_connection()
                df = con.execute(sql).df()

                st.success(f"{len(df):,} dòng")
                st.dataframe(df, use_container_width=True)
                render_chart(df)

                st.session_state.messages.append({
                    "role": "assistant",
                    "sql": sql,
                    "df": df,
                })

            except Exception as exc:
                st.error(f"{exc}")
                if sql:
                    st.code(sql, language="sql")
                st.session_state.messages.append({
                    "role": "assistant",
                    "sql": sql,
                    "error": str(exc),
                })

    # Xóa lịch sử
    if st.session_state.messages:
        st.divider()
        if st.button("Xóa lịch sử chat", type="secondary"):
            st.session_state.messages = []
            st.rerun()


main()
