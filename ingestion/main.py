"""
Entry point cho Bronze Layer ingestion.

Flow:

CSV local
    ↓
Validate
    ↓
Add metadata
    ↓
Convert Parquet
    ↓
Upload R2 Bronze
    ↓
Write ingestion log
"""

import logging
import sys
import time

from ingestion.clients.r2_client import (
    get_r2_client,
    validate_r2_credentials,
)
from ingestion.config.datasets import INGEST_CONFIG
from ingestion.services.bronze_ingestion import ingest_dataset
from ingestion.services.logging_service import (
    create_pipeline_run,
    update_pipeline_run,
)
from ingestion.utils.metadata import generate_run_id


# --------------------------------------------------
# Logging
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)


def main():

    logger.info("")
    logger.info("=" * 60)
    logger.info("SUPPLY CHAIN LAKEHOUSE - BRONZE INGESTION")
    logger.info("=" * 60)

    # ----------------------------------------
    # Validate credentials
    # ----------------------------------------

    if not validate_r2_credentials():

        logger.error(
            "Missing R2 credentials. Check .env file."
        )

        sys.exit(1)

    # ----------------------------------------
    # Init pipeline run
    # ----------------------------------------

    run_id = generate_run_id()
    start_time = time.time()

    create_pipeline_run(
        run_id=run_id,
        pipeline_name="bronze_ingestion",
        total_datasets=len(INGEST_CONFIG),
    )

    logger.info(
        "Pipeline Run ID: %s",
        run_id,
    )

    # ----------------------------------------
    # Create R2 client
    # ----------------------------------------

    client = get_r2_client()
    results = []

    # ----------------------------------------
    # Ingest datasets
    # ----------------------------------------

    for dataset_name, config in INGEST_CONFIG.items():

        try:

            result = ingest_dataset(
                client=client,
                filename=dataset_name,
                config=config,
                run_id=run_id,
            )

        except Exception as exc:

            logger.exception(
                "Failed ingesting %s",
                dataset_name,
            )

            result = {
                "file": dataset_name,
                "status": "FAILED",
                "reason": str(exc),
            }

        results.append(result)

    # ----------------------------------------
    # Update pipeline run
    # ----------------------------------------

    failed = [
        r for r in results
        if r["status"] == "FAILED"
    ]

    success_count = len(
        [
            r for r in results
            if r["status"] == "SUCCESS"
        ]
    )

    skipped_count = len(
        [
            r for r in results
            if r["status"] == "SKIPPED"
        ]
    )

    total_rows = sum(
        r.get("rows", 0)
        for r in results
    )

    duration = time.time() - start_time

    update_pipeline_run(
        run_id=run_id,
        status="FAILED" if failed else "SUCCESS",
        success_count=success_count,
        failed_count=len(failed),
        total_rows=total_rows,
        duration_seconds=duration,
    )

    # ----------------------------------------
    # Summary
    # ----------------------------------------

    logger.info("")
    logger.info("=" * 60)
    logger.info("INGEST SUMMARY")
    logger.info("=" * 60)

    for item in results:

        if item["status"] == "SUCCESS":

            logger.info(
                "SUCCESS | %-45s | %s rows",
                item["file"],
                f"{item.get('rows', 0):,}",
            )

        elif item["status"] == "SKIPPED":

            logger.info(
                "SKIPPED | %-45s | %s",
                item["file"],
                item.get(
                    "reason",
                    "No changes detected",
                ),
            )

        else:

            logger.error(
                "FAILED  | %-45s | %s",
                item["file"],
                item.get(
                    "reason",
                    "unknown error",
                ),
            )

    logger.info("")
    logger.info(
        "Success : %s",
        success_count,
    )

    logger.info(
        "Skipped : %s",
        skipped_count,
    )

    logger.info(
        "Failed  : %s",
        len(failed),
    )

    # ----------------------------------------
    # Exit
    # ----------------------------------------

    if failed:

        logger.error(
            "%d dataset(s) failed.",
            len(failed),
        )

        sys.exit(1)

    logger.info("")
    logger.info(
        "Bronze ingestion completed in %.2fs",
        duration,
    )


if __name__ == "__main__":
    main()