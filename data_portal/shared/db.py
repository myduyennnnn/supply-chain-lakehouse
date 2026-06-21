"""
DuckDB Connection (S3 Parquet)

Dùng cho các page: Data Preview, Analytics, ML Prediction.
Đọc trực tiếp Parquet trên S3 (bucket supply-chain-ai-native), không cần lakehouse.db local.

Lưu ý: tên biến môi trường giữ nguyên prefix R2_* vì lý do lịch sử,
nhưng giá trị thực tế trỏ tới AWS S3 (không phải Cloudflare R2).
"""

import os

import duckdb
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

R2_BUCKET = os.getenv("R2_BUCKET_NAME")

REQUIRED_ENV = [
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
]

for var in REQUIRED_ENV:
    if not os.getenv(var):
        raise ValueError(f"Missing env variable: {var}")


# ============================================================
# TABLE REGISTRY
#
# Mỗi entry map "tên bảng dùng trong SQL" -> path tương đối
# tính từ root bucket (không gồm bucket name), khớp với
# `location` khai báo trong các dbt model (config materialized='external').
# ============================================================

TABLES = {
    "silver": {
        "stg_customer": "silver/customer/stg_customer.parquet",
        "stg_department": "silver/department/stg_department.parquet",
        "stg_order": "silver/order/stg_order.parquet",
        "stg_order_items": "silver/order_items/stg_order_items.parquet",
        "stg_product": "silver/product/stg_product.parquet",
    },
    "gold": {
        # Dimensions — gold/dimensions/
        "dim_customer": "gold/dimensions/dim_customer.parquet",
        "dim_product": "gold/dimensions/dim_product.parquet",
        "dim_order": "gold/dimensions/dim_order.parquet",
        "dim_date": "gold/dimensions/dim_date.parquet",
        # Facts — gold/facts/
        "fact_order_items": "gold/facts/fact_order_items.parquet",
        # Marts — gold/marts/dashboard/
        "mart_executive_summary": "gold/marts/dashboard/mart_executive_summary.parquet",
        "mart_customer_summary": "gold/marts/dashboard/mart_customer_summary.parquet",
        "mart_product_category_sales": "gold/marts/dashboard/mart_product_category_sales.parquet",
        "mart_product_discount_impact": "gold/marts/dashboard/mart_product_discount_impact.parquet",
        "mart_supply_chain_shipping_mode": "gold/marts/dashboard/mart_supply_chain_shipping_mode.parquet",
        "mart_supply_chain_region_delay": "gold/marts/dashboard/mart_supply_chain_region_delay.parquet",
        "mart_ai_monitoring_summary": "gold/marts/dashboard/mart_ai_monitoring_summary.parquet",
        "mart_ai_monitoring_risk_by_region": "gold/marts/dashboard/mart_ai_monitoring_risk_by_region.parquet",
        "mart_ai_monitoring_risk_by_mode_region": "gold/marts/dashboard/mart_ai_monitoring_risk_by_mode_region.parquet",
        "mart_trend_monthly": "gold/marts/dashboard/mart_trend_monthly.parquet",
        "mart_customer_segment_revenue": "gold/marts/dashboard/mart_customer_segment_revenue.parquet",
        "mart_product_discount_impact_by_category": "gold/marts/dashboard/mart_product_discount_impact_by_category.parquet",
    },
}


def list_tables(layer: str) -> list[str]:
    """Trả về danh sách tên table thuộc 1 layer (silver/gold)."""
    return list(TABLES.get(layer, {}).keys())


def build_r2_path(layer: str, table_name: str) -> str:
    """
    Build path tới Parquet file trên S3, dựa theo TABLES registry
    (khớp 1-1 với `location` khai báo trong từng dbt model).
    """

    layer_tables = TABLES.get(layer, {})

    if table_name not in layer_tables:
        raise ValueError(
            f"Table '{table_name}' chưa được khai báo trong TABLES['{layer}']. "
            f"Các bảng hợp lệ: {list(layer_tables.keys())}"
        )

    relative_path = layer_tables[table_name]
    return f"s3://{R2_BUCKET}/{relative_path}"


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    """Khởi tạo DuckDB connection với S3 (in-memory)."""

    con = duckdb.connect(database=":memory:")

    try:
        con.execute("LOAD httpfs")
    except Exception:
        con.execute("INSTALL httpfs")
        con.execute("LOAD httpfs")

    con.execute(f"SET s3_access_key_id='{os.getenv('R2_ACCESS_KEY_ID')}'")
    con.execute(f"SET s3_secret_access_key='{os.getenv('R2_SECRET_ACCESS_KEY')}'")

    # Endpoint là optional: AWS S3 thật không cần set endpoint thủ công
    # (DuckDB tự suy ra qua region). Chỉ set khi có giá trị, để tương
    # thích ngược với R2/MinIO nếu sau này đổi backend.
    endpoint = os.getenv("R2_ENDPOINT_URL")
    if endpoint:
        con.execute(f"SET s3_endpoint='{endpoint.replace('https://', '')}'")
        con.execute("SET s3_url_style='path'")
        con.execute("SET s3_region='auto'")
    else:
        region = os.getenv("R2_REGION", "us-east-1")
        con.execute(f"SET s3_region='{region}'")
        con.execute("SET s3_url_style='vhost'")

    con.execute("SET s3_use_ssl=true")

    return con


@st.cache_resource
def register_views(layer: str = "silver") -> duckdb.DuckDBPyConnection:
    """
    Tạo view cho từng bảng trong 1 layer, để query có thể JOIN nhiều bảng
    bằng tên (stg_customer, dim_customer, mart_executive_summary, ...)
    thay vì path S3 đầy đủ.
    """

    con = get_connection()

    for table_name in list_tables(layer):
        path = build_r2_path(layer, table_name)
        con.execute(f"""
            CREATE OR REPLACE VIEW {table_name} AS
            SELECT * FROM read_parquet('{path}')
        """)

    return con


@st.cache_data(ttl=300)
def load_table(table_name: str, layer: str = "silver") -> pd.DataFrame:
    """
    Đọc 1 bảng từ S3.

    Ví dụ: load_table("stg_order")
           load_table("mart_executive_summary", layer="gold")
    """

    con = register_views(layer)
    return con.execute(f"SELECT * FROM {table_name}").df()


@st.cache_data(ttl=300)
def query(sql: str, layer: str = "gold", params: dict | None = None) -> pd.DataFrame:
    """
    Chạy SQL tuỳ ý, có thể JOIN nhiều bảng (đã được register qua register_views).

    Hỗ trợ parameterized query để tránh SQL injection: dùng placeholder
    kiểu $tên_param trong SQL (cú pháp named parameter của DuckDB),
    truyền giá trị qua `params`.

    Ví dụ không params:
        query('''
            SELECT customer_segment, COUNT(*)
            FROM dim_customer
            GROUP BY 1
        ''')

    Ví dụ có params:
        query('''
            SELECT * FROM mart_executive_summary
            WHERE order_region IN ($region_0, $region_1)
        ''', params={"region_0": "Asia", "region_1": "Europe"})

    Lưu ý: layer mặc định đổi thành "gold" vì phần lớn dashboard
    giờ đọc từ dim/fact/mart ở tầng gold, không còn query trực tiếp
    staging (stg_*) như trước.
    """

    con = register_views(layer)

    if params:
        return con.execute(sql, params).df()

    return con.execute(sql).df()