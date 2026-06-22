"""
Tasks: Silver Layer

1. dbt_run_silver   — chạy dbt models trong models/silver/
2. dbt_test_silver  — chạy dbt tests (unique, not_null, relationships) cho silver
3. log_dbt_silver   — đẩy run_results.json lên Supabase (dbt_run_logs)
4. sync_silver_catalog — sync schema silver từ DuckDB lên metadata_catalog
"""

import subprocess
import sys
from pathlib import Path

from prefect import task, get_run_logger

ROOT = Path(__file__).resolve().parents[2]
DBT_DIR = ROOT / "supply_chain_dbt"

sys.path.insert(0, str(ROOT))

from ingestion.services.dbt_logging_service import log_dbt_run
from ingestion.services.silver_catalog_service import sync_silver_catalog


@task(
    name="dbt-run-silver",
    retries=1,
    retry_delay_seconds=30,
)
def dbt_run_silver() -> None:
    logger = get_run_logger()
    logger.info("Running dbt silver models")

    result = subprocess.run(
        [
            "dbt", "run",
            "--project-dir", str(DBT_DIR),
            "--select", "path:models/silver",
        ],
        check=True,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    logger.info(result.stdout)


@task(name="dbt-test-silver")
def dbt_test_silver() -> None:
    logger = get_run_logger()
    logger.info("Running dbt tests for silver")

    result = subprocess.run(
        [
            "dbt", "test",
            "--project-dir", str(DBT_DIR),
            "--select", "path:models/silver",
        ],
        check=True,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    logger.info(result.stdout)


@task(name="log-dbt-silver")
def log_dbt_silver() -> None:
    logger = get_run_logger()
    logger.info("Logging dbt silver results to Supabase")
    log_dbt_run()


@task(name="sync-silver-catalog")
def sync_silver_catalog_task() -> None:
    logger = get_run_logger()
    logger.info("Syncing silver schema to metadata_catalog")
    sync_silver_catalog()
    logger.info("Silver catalog synced")
