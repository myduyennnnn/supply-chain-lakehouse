"""
DuckDB Client

Kết nối DuckDB với Cloudflare R2.

Dùng để:
    - Query trực tiếp Parquet trên R2
    - Silver transformations
    - Gold aggregations
    - Analytics layer
"""

import os
import duckdb

from dotenv import load_dotenv

load_dotenv()


def get_duckdb_connection():
    """
    Khởi tạo DuckDB connection.

    Required environment variables:
        R2_ENDPOINT_URL
        R2_ACCESS_KEY_ID
        R2_SECRET_ACCESS_KEY
    """

    endpoint = os.getenv("R2_ENDPOINT_URL")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")

    if not endpoint:
        raise ValueError("Missing R2_ENDPOINT_URL")

    if not access_key:
        raise ValueError("Missing R2_ACCESS_KEY_ID")

    if not secret_key:
        raise ValueError("Missing R2_SECRET_ACCESS_KEY")

    endpoint = endpoint.replace("https://", "")

    con = duckdb.connect("lakehouse.db")

    # S3/R2 support
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")

    con.execute(f"""
        SET s3_access_key_id='{access_key}';
    """)

    con.execute(f"""
        SET s3_secret_access_key='{secret_key}';
    """)

    con.execute(f"""
        SET s3_endpoint='{endpoint}';
    """)

    con.execute("""
        SET s3_url_style='path';
    """)

    con.execute("""
        SET s3_use_ssl=true;
    """)

    return con