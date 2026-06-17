"""
Silver Catalog Service

Sync schema của các table/view trong main_silver (DuckDB)
và upsert vào metadata_catalog (Supabase).
"""

import os
import logging
from pathlib import Path
from collections import defaultdict

import duckdb
from dotenv import load_dotenv

from ingestion.services.logging_service import upsert_metadata_catalog

load_dotenv()

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent.parent / "lakehouse.db"


def sync_silver_catalog() -> None:
    """Sync schema của tất cả model trong main_silver vào metadata_catalog."""

    con = duckdb.connect(str(DB_PATH), read_only=True)

    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    con.execute(f"SET s3_access_key_id='{os.getenv('R2_ACCESS_KEY_ID')}'")
    con.execute(f"SET s3_secret_access_key='{os.getenv('R2_SECRET_ACCESS_KEY')}'")
    con.execute(f"SET s3_endpoint='{os.getenv('R2_ENDPOINT_URL').replace('https://', '')}'")
    con.execute("SET s3_url_style='path'")
    con.execute("SET s3_use_ssl=true")


    # 1. LẤY SCHEMA CHUẨN TỪ INFORMATION_SCHEMA
    rows = con.execute("""
        SELECT
            table_name,
            column_name,
            data_type
        FROM information_schema.columns
        WHERE table_schema = 'main_silver'
        ORDER BY table_name, ordinal_position
    """).fetchall()

    # 2. GROUP COLUMNS THEO TABLE
    schema_map = defaultdict(list)

    for table_name, column_name, data_type in rows:
        schema_map[table_name].append({
            "column_name": column_name,
            "data_type": data_type
        })

    # 3. OPTIONAL: ROW COUNT (từ table thật)
    def get_row_count(table_name: str) -> int:
        try:
            return con.execute(
                f"SELECT COUNT(*) FROM main_silver.{table_name}"
            ).fetchone()[0]
        except Exception:
            logger.exception("Failed to count rows for %s", table_name)
            return 0

    # 4. UPSERT METADATA
    for table_name, columns in schema_map.items():

        column_names = [c["column_name"] for c in columns]

        upsert_metadata_catalog(
            dataset_name=table_name,
            layer="silver",
            r2_prefix=f"silver/{table_name.replace('stg_', '')}",
            file_format="parquet",
            row_count=get_row_count(table_name),
            column_count=len(columns),
            column_names=column_names,
            description=f"Silver model (dbt external): {table_name}",
        )

    logger.info("Synced %d silver tables to metadata_catalog", len(schema_map))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_silver_catalog()