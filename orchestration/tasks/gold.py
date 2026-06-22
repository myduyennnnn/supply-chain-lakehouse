"""
Tasks: Gold Layer

1. dbt_run_gold_dims    — dimensions (dim_customer, dim_date, dim_order, dim_product)
2. dbt_run_gold_facts   — facts (fact_order_items)
3. dbt_run_gold_marts   — dashboard marts (12 mart_*.sql)
4. dbt_run_gold_ml      — ML features (feat_delivery_risk, feat_customer) — local DuckDB table
5. dbt_test_gold        — dbt tests toàn bộ gold layer
6. log_dbt_gold         — đẩy run_results.json lên Supabase (gọi sau mỗi lệnh dbt)
7. sync_gold_catalog    — sync schema gold từ DuckDB lên metadata_catalog

QUAN TRỌNG: log_dbt_gold() phải được gọi ngay sau mỗi lệnh dbt run/test riêng lẻ
vì mỗi lệnh dbt ghi đè run_results.json — nếu gọi muộn sẽ mất kết quả trước đó.
"""

import subprocess
import sys
from pathlib import Path

from prefect import task, get_run_logger

ROOT = Path(__file__).resolve().parents[2]
DBT_DIR = ROOT / "supply_chain_dbt"

sys.path.insert(0, str(ROOT))

from ingestion.services.dbt_logging_service import log_dbt_run
from ingestion.services.gold_catalog_service import sync_gold_catalog


def _dbt_run(select: str, logger) -> None:
    result = subprocess.run(
        [
            "dbt", "run",
            "--project-dir", str(DBT_DIR),
            "--select", select,
        ],
        check=True,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    logger.info(result.stdout)


@task(
    name="dbt-run-gold-dimensions",
    retries=1,
    retry_delay_seconds=30,
)
def dbt_run_gold_dims() -> None:
    logger = get_run_logger()
    logger.info("Running dbt gold dimension models")
    _dbt_run("path:models/gold/dimensions", logger)


@task(
    name="dbt-run-gold-facts",
    retries=1,
    retry_delay_seconds=30,
)
def dbt_run_gold_facts() -> None:
    logger = get_run_logger()
    logger.info("Running dbt gold fact models")
    _dbt_run("path:models/gold/facts", logger)


@task(
    name="dbt-run-gold-marts",
    retries=1,
    retry_delay_seconds=30,
)
def dbt_run_gold_marts() -> None:
    logger = get_run_logger()
    logger.info("Running dbt gold mart models")
    _dbt_run("path:models/gold/marts", logger)


@task(name="dbt-run-gold-ml")
def dbt_run_gold_ml() -> None:
    logger = get_run_logger()
    logger.info("Running dbt gold ML feature models")
    _dbt_run("path:models/gold/ml", logger)


@task(name="dbt-test-gold")
def dbt_test_gold() -> None:
    logger = get_run_logger()
    logger.info("Running dbt tests for gold")
    result = subprocess.run(
        [
            "dbt", "test",
            "--project-dir", str(DBT_DIR),
            "--select", "path:models/gold",
        ],
        check=True,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    logger.info(result.stdout)


@task(name="log-dbt-gold")
def log_dbt_gold() -> None:
    """Đọc run_results.json hiện tại và log lên Supabase. Gọi ngay sau mỗi lệnh dbt."""
    logger = get_run_logger()
    logger.info("Logging dbt gold results to Supabase")
    log_dbt_run()


@task(name="sync-gold-catalog")
def sync_gold_catalog_task() -> None:
    logger = get_run_logger()
    logger.info("Syncing gold schema to metadata_catalog")
    sync_gold_catalog()
    logger.info("Gold catalog synced")
