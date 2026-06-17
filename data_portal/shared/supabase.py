"""
Supabase Connection

Dùng cho các page: Catalog, Pipeline Monitoring.
Đọc metadata_catalog, pipeline_runs, ingestion_logs, dbt_run_logs.
"""

import os

import pandas as pd
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


@st.cache_resource
def get_client() -> Client:
    """Khởi tạo Supabase client."""

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("Missing SUPABASE_URL / SUPABASE_KEY")

    return create_client(url, key)


@st.cache_data(ttl=60)
def fetch_table(table_name: str, limit: int = 1000) -> pd.DataFrame:
    """
    Lấy data từ 1 table Supabase, trả về DataFrame.

    Ví dụ: fetch_table("metadata_catalog")
    """

    client = get_client()

    response = (
        client.table(table_name)
        .select("*")
        .limit(limit)
        .execute()
    )

    return pd.DataFrame(response.data)


@st.cache_data(ttl=60)
def fetch_metadata_catalog(layer: str | None = None) -> pd.DataFrame:
    """Lấy metadata_catalog, optional filter theo layer (bronze/silver/gold)."""

    client = get_client()

    query = client.table("metadata_catalog").select("*")

    if layer:
        query = query.eq("layer", layer)

    response = query.execute()

    return pd.DataFrame(response.data)


@st.cache_data(ttl=60)
def fetch_pipeline_runs(limit: int = 20) -> pd.DataFrame:
    """Lấy lịch sử pipeline runs gần nhất."""

    client = get_client()

    response = (
        client.table("pipeline_runs")
        .select("*")
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )

    return pd.DataFrame(response.data)


@st.cache_data(ttl=60)
def fetch_dbt_run_logs(limit: int = 50) -> pd.DataFrame:
    """Lấy log dbt run gần nhất."""

    client = get_client()

    response = (
        client.table("dbt_run_logs")
        .select("*")
        .order("run_at", desc=True)
        .limit(limit)
        .execute()
    )

    return pd.DataFrame(response.data)