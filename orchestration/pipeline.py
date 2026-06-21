"""
Supply Chain Lakehouse — Main Pipeline

Flow:
    bronze_ingestion
        ↓
    dbt silver → log → dbt test silver → log → sync silver catalog
        ↓
    dbt gold dims → log
    dbt gold facts → log
    dbt gold marts → log
    dbt test gold  → log
    sync gold catalog

QUAN TRỌNG về logging:
    log_dbt_*() phải gọi ngay sau MỖI lệnh dbt riêng lẻ vì dbt ghi đè
    run_results.json sau mỗi lần chạy. Nếu gọi muộn sẽ mất kết quả.

Chạy toàn bộ:
    python orchestration/pipeline.py

Chạy từng layer:
    python orchestration/pipeline.py --no-bronze
    python orchestration/pipeline.py --silver-only
    python orchestration/pipeline.py --gold-only
    python orchestration/pipeline.py --gold-only --with-ml
"""

import argparse
import sys
from pathlib import Path

from prefect import flow, get_run_logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestration.tasks.bronze import bronze_ingestion
from orchestration.tasks.silver import (
    dbt_run_silver,
    dbt_test_silver,
    log_dbt_silver,
    sync_silver_catalog_task,
)
from orchestration.tasks.gold import (
    dbt_run_gold_dims,
    dbt_run_gold_facts,
    dbt_run_gold_marts,
    dbt_run_gold_ml,
    dbt_test_gold,
    log_dbt_gold,
    sync_gold_catalog_task,
)


@flow(
    name="supply-chain-lakehouse",
    description="Bronze ingestion → Silver dbt → Gold dbt",
    log_prints=True,
)
def lakehouse_pipeline(
    run_bronze: bool = True,
    run_silver: bool = True,
    run_gold: bool = True,
    run_ml: bool = False,
) -> None:
    logger = get_run_logger()

    # ── BRONZE ────────────────────────────────────────────────────
    if run_bronze:
        logger.info("═" * 50)
        logger.info("BRONZE — ingestion")
        logger.info("═" * 50)
        bronze_ingestion()
        # pipeline_runs + ingestion_logs + dataset_state + metadata_catalog(bronze)
        # được ghi bởi ingestion/main.py tự động

    # ── SILVER ────────────────────────────────────────────────────
    if run_silver:
        logger.info("═" * 50)
        logger.info("SILVER — dbt transform")
        logger.info("═" * 50)

        dbt_run_silver()
        log_dbt_silver()          # ← log RUN results ngay, trước khi dbt test ghi đè

        dbt_test_silver()
        log_dbt_silver()          # ← log TEST results

        sync_silver_catalog_task()  # ← metadata_catalog(silver)

    # ── GOLD ──────────────────────────────────────────────────────
    if run_gold:
        logger.info("═" * 50)
        logger.info("GOLD — dbt transform")
        logger.info("═" * 50)

        dbt_run_gold_dims()
        log_dbt_gold()            # ← log dims RUN results ngay

        dbt_run_gold_facts()
        log_dbt_gold()            # ← log facts RUN results ngay

        dbt_run_gold_marts()
        log_dbt_gold()            # ← log marts RUN results ngay

        if run_ml:
            dbt_run_gold_ml()
            log_dbt_gold()        # ← log ml RUN results ngay

        dbt_test_gold()
        log_dbt_gold()            # ← log TEST results

        sync_gold_catalog_task()  # ← metadata_catalog(gold)

    logger.info("Pipeline completed.")


# ── CLI entry point ────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Supply Chain Lakehouse Pipeline")

    parser.add_argument("--no-bronze",   action="store_true", help="Skip bronze ingestion")
    parser.add_argument("--no-silver",   action="store_true", help="Skip silver transformation")
    parser.add_argument("--no-gold",     action="store_true", help="Skip gold transformation")
    parser.add_argument("--silver-only", action="store_true", help="Run silver only")
    parser.add_argument("--gold-only",   action="store_true", help="Run gold only")
    parser.add_argument("--with-ml",     action="store_true", help="Include ML feature models")

    args = parser.parse_args()

    run_bronze = not args.no_bronze and not args.silver_only and not args.gold_only
    run_silver = not args.no_silver and not args.gold_only or args.silver_only
    run_gold   = not args.no_gold   and not args.silver_only or args.gold_only

    lakehouse_pipeline(
        run_bronze=run_bronze,
        run_silver=run_silver,
        run_gold=run_gold,
        run_ml=args.with_ml,
    )
