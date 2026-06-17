"""
DuckDB Connection (R2 Parquet)

Dùng cho các page: Data Preview, Analytics, ML Prediction.
Đọc trực tiếp Parquet trên Cloudflare R2, không cần lakehouse.db local.
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
    "R2_ENDPOINT_URL",
    "R2_BUCKET_NAME",
]

for var in REQUIRED_ENV:
    if not os.getenv(var):
        raise ValueError(f"Missing env variable: {var}")


TABLES = {
    "silver": [
        "stg_customer",
        "stg_department",
        "stg_order",
        "stg_order_items",
        "stg_product",
    ],
    "gold": [
        "fact_sales",
        "dim_customer",
        "dim_product",
        "dim_date",
    ],
}


def list_tables(layer: str) -> list[str]:
    """Trả về danh sách tên table thuộc 1 layer (silver/gold)."""
    return TABLES.get(layer, [])


def build_r2_path(layer: str, table_name: str) -> str:
    """
    Build path tới Parquet file trên R2.

    Silver: silver/customer/stg_customer.parquet
    Gold:   gold/fact_sales/fact_sales.parquet
    """

    if layer == "silver":
        prefix = table_name.replace("stg_", "")
    else:
        prefix = table_name

    return f"s3://{R2_BUCKET}/{layer}/{prefix}/{table_name}.parquet"


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    """Khởi tạo DuckDB connection với R2 (in-memory)."""

    con = duckdb.connect(database=":memory:")

    try:
        con.execute("LOAD httpfs")
    except Exception:
        con.execute("INSTALL httpfs")
        con.execute("LOAD httpfs")

    con.execute(f"SET s3_access_key_id='{os.getenv('R2_ACCESS_KEY_ID')}'")
    con.execute(f"SET s3_secret_access_key='{os.getenv('R2_SECRET_ACCESS_KEY')}'")
    con.execute(f"SET s3_endpoint='{os.getenv('R2_ENDPOINT_URL').replace('https://', '')}'")
    con.execute("SET s3_url_style='path'")
    con.execute("SET s3_use_ssl=true")

    return con


@st.cache_resource
def register_views(layer: str = "silver") -> duckdb.DuckDBPyConnection:
    """
    Tạo view cho từng bảng trong 1 layer, để query có thể JOIN nhiều bảng
    bằng tên (stg_customer, stg_order, ...) thay vì path R2.
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
    Đọc 1 bảng từ R2.

    Ví dụ: load_table("stg_order")
           load_table("fact_sales", layer="gold")
    """

    con = register_views(layer)
    return con.execute(f"SELECT * FROM {table_name}").df()


@st.cache_data(ttl=300)
def query(sql: str, layer: str = "silver") -> pd.DataFrame:
    """
    Chạy SQL tuỳ ý, có thể JOIN nhiều bảng (đã được register qua register_views).

    Ví dụ:
        query('''
            SELECT customer_segment, COUNT(*)
            FROM stg_customer
            GROUP BY 1
        ''')
    """

    con = register_views(layer)
    return con.execute(sql).df()