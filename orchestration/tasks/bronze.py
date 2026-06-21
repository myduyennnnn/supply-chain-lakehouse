"""
Task: Bronze Ingestion

Validate → hash check → upload CSV + Parquet → log Supabase.
Tích hợp trực tiếp với ingestion.main để tái dùng toàn bộ logic hiện có.
"""

import sys
from pathlib import Path

from prefect import task, get_run_logger

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ingestion.main import main as _run_bronze_ingestion


@task(
    name="bronze-ingestion",
    retries=2,
    retry_delay_seconds=60,
)
def bronze_ingestion() -> None:
    logger = get_run_logger()
    logger.info("Bronze ingestion started")
    _run_bronze_ingestion()
    logger.info("Bronze ingestion completed")
