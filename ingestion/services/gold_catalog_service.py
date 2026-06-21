"""
Gold Catalog Service

Sync schema của các model trong main_gold (DuckDB) lên metadata_catalog (Supabase).
Tương tự silver_catalog_service nhưng đọc từ main_gold schema.
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

# Map tên model → r2_prefix tương ứng
_R2_PREFIX_MAP = {
    # dimensions
    "dim_customer":  "gold/dimensions",
    "dim_date":      "gold/dimensions",
    "dim_order":     "gold/dimensions",
    "dim_product":   "gold/dimensions",
    # facts
    "fact_order_items": "gold/facts",
    # marts
    "mart_executive_summary":                  "gold/marts/dashboard",
    "mart_customer_summary":                   "gold/marts/dashboard",
    "mart_product_category_sales":             "gold/marts/dashboard",
    "mart_product_discount_impact":            "gold/marts/dashboard",
    "mart_product_discount_impact_by_category":"gold/marts/dashboard",
    "mart_supply_chain_shipping_mode":         "gold/marts/dashboard",
    "mart_supply_chain_region_delay":          "gold/marts/dashboard",
    "mart_ai_monitoring_summary":              "gold/marts/dashboard",
    "mart_ai_monitoring_risk_by_region":       "gold/marts/dashboard",
    "mart_ai_monitoring_risk_by_mode_region":  "gold/marts/dashboard",
    "mart_trend_monthly":                      "gold/marts/dashboard",
    "mart_customer_segment_revenue":           "gold/marts/dashboard",
    # ml
    "feat_customer": "gold/ml",
}


def sync_gold_catalog() -> None:
    """Sync schema của tất cả model trong main_gold vào metadata_catalog."""

    con = duckdb.connect(str(DB_PATH), read_only=True)

    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    con.execute(f"SET s3_access_key_id='{os.getenv('R2_ACCESS_KEY_ID')}'")
    con.execute(f"SET s3_secret_access_key='{os.getenv('R2_SECRET_ACCESS_KEY')}'")
    con.execute(f"SET s3_endpoint='{os.getenv('R2_ENDPOINT_URL', '').replace('https://', '')}'")
    con.execute("SET s3_url_style='path'")
    con.execute("SET s3_region='auto'")
    con.execute("SET s3_use_ssl=true")

    rows = con.execute("""
        SELECT
            table_name,
            column_name,
            data_type
        FROM information_schema.columns
        WHERE table_schema = 'main_gold'
        ORDER BY table_name, ordinal_position
    """).fetchall()

    schema_map = defaultdict(list)
    for table_name, column_name, data_type in rows:
        schema_map[table_name].append({
            "column_name": column_name,
            "data_type": data_type,
        })

    def get_row_count(table_name: str) -> int:
        try:
            return con.execute(
                f"SELECT COUNT(*) FROM main_gold.{table_name}"
            ).fetchone()[0]
        except Exception:
            logger.exception("Failed to count rows for %s", table_name)
            return 0

    for table_name, columns in schema_map.items():
        r2_prefix = _R2_PREFIX_MAP.get(table_name, "gold")
        column_names = [c["column_name"] for c in columns]

        upsert_metadata_catalog(
            dataset_name=table_name,
            layer="gold",
            r2_prefix=r2_prefix,
            file_format="parquet",
            row_count=get_row_count(table_name),
            column_count=len(columns),
            column_names=column_names,
            description=f"Gold model (dbt external): {table_name}",
        )

    logger.info("Synced %d gold tables to metadata_catalog", len(schema_map))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_gold_catalog()
