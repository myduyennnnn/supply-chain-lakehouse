"""
Bronze Ingestion Service

Orchestrate ingestion của 1 dataset:
    Validate → Read CSV → Add Metadata → Upload CSV + Parquet → Log Supabase
"""

import os
import time
import logging
from pathlib import Path

import pandas as pd

from ingestion.utils.metadata import (
    add_ingestion_metadata,
    build_r2_key,
)
from ingestion.utils.upload import (
    upload_csv,
    upload_parquet,
)
from ingestion.utils.validation import validate_file
from ingestion.utils.hashing import calculate_file_hash

from ingestion.services.logging_service import (
    log_ingestion,
    upsert_metadata_catalog,
    get_dataset_hash,
    update_dataset_hash,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
R2_BUCKET = os.getenv(
    "R2_BUCKET_NAME",
    "supply-chain-ai-native",
)


def ingest_dataset(
    client,
    filename: str,
    config: dict,
    run_id: str,
) -> dict:
    """
    Ingest 1 dataset lên R2 Bronze.

    Args:
        client   — boto3 R2 client
        filename — tên file CSV trong data/
        config   — config từ INGEST_CONFIG
        run_id   — UUID từ pipeline run

    Returns:
        dict với status, rows, keys
    """

    local_path = DATA_DIR / filename
    skip_parquet = config.get(
        "skip_parquet",
        False,
    )

    start = time.time()

    logger.info("")
    logger.info("-" * 60)
    logger.info("Dataset  : %s", filename)
    logger.info("Desc     : %s", config["description"])
    logger.info("Run ID   : %s", run_id)
    logger.info("-" * 60)

    # ----------------------------------------
    # Validate
    # ----------------------------------------

    if not validate_file(local_path):

        log_ingestion(
            run_id=run_id,
            dataset_name=config["dataset_name"],
            source_file=filename,
            bronze_prefix=config["bronze_prefix"],
            status="FAILED",
            error_message="Validation failed",
            duration_seconds=round(
                time.time() - start,
                3,
            ),
        )

        return {
            "file": filename,
            "status": "FAILED",
            "reason": "Validation failed",
        }

    # ----------------------------------------
    # Change Detection
    # ----------------------------------------

    current_hash = calculate_file_hash(
        local_path
    )

    previous_hash = get_dataset_hash(
        config["dataset_name"]
    )

    if previous_hash == current_hash:

        duration = round(
            time.time() - start,
            3,
        )

        logger.info(
            "No changes detected -> SKIPPED"
        )

        log_ingestion(
            run_id=run_id,
            dataset_name=config["dataset_name"],
            source_file=filename,
            bronze_prefix=config["bronze_prefix"],
            status="SKIPPED",
            duration_seconds=duration,
        )

        return {
            "file": filename,
            "status": "SKIPPED",
            "reason": "No changes detected",
        }

    # ----------------------------------------
    # Read CSV
    # ----------------------------------------

    logger.info(
        "Reading CSV (encoding=%s)...",
        config["encoding"],
    )

    df = pd.read_csv(
        local_path,
        encoding=config["encoding"],
        low_memory=False,
    )

    logger.info(
        "Shape: %s rows × %s columns",
        f"{len(df):,}",
        len(df.columns),
    )

    # ----------------------------------------
    # Add metadata
    # ----------------------------------------

    df = add_ingestion_metadata(
        df=df,
        source_file=filename,
        dataset_name=config["dataset_name"],
        run_id=run_id,
    )

    # ----------------------------------------
    # Build R2 Keys
    # ----------------------------------------

    csv_key = build_r2_key(
        prefix=config["bronze_prefix"],
        filename=filename,
        extension="csv",
    )

    parquet_key = (
        build_r2_key(
            prefix=config["bronze_prefix"],
            filename=filename,
            extension="parquet",
        )
        if not skip_parquet
        else None
    )

    # ----------------------------------------
    # Upload CSV
    # ----------------------------------------

    upload_csv(
        client=client,
        bucket=R2_BUCKET,
        df=df,
        key=csv_key,
    )

    # ----------------------------------------
    # Upload Parquet
    # ----------------------------------------

    if not skip_parquet:

        upload_parquet(
            client=client,
            bucket=R2_BUCKET,
            df=df,
            key=parquet_key,
        )

    else:

        logger.info(
            "Parquet skipped (skip_parquet=True)"
        )

    duration = round(
        time.time() - start,
        3,
    )

    # ----------------------------------------
    # Log Ingestion
    # ----------------------------------------

    log_ingestion(
        run_id=run_id,
        dataset_name=config["dataset_name"],
        source_file=filename,
        bronze_prefix=config["bronze_prefix"],
        status="SUCCESS",
        rows_ingested=len(df),
        csv_key=csv_key,
        parquet_key=parquet_key,
        duration_seconds=duration,
    )

    # ----------------------------------------
    # Metadata Catalog
    # ----------------------------------------

    upsert_metadata_catalog(
        dataset_name=config["dataset_name"],
        layer="bronze",
        r2_prefix=config["bronze_prefix"],
        file_format="parquet",
        row_count=len(df),
        column_count=len(df.columns) - 5,
        column_names=list(df.columns),
        encoding=config["encoding"],
        description=config["description"],
    )

    # ----------------------------------------
    # Update Hash State
    # ----------------------------------------

    update_dataset_hash(
        dataset_name=config["dataset_name"],
        file_hash=current_hash,
        run_id=run_id,
    )

    logger.info(
        "Duration: %.3fs",
        duration,
    )

    return {
        "file": filename,
        "status": "SUCCESS",
        "rows": len(df),
        "dataset_name": config["dataset_name"],
        "csv_key": csv_key,
        "parquet_key": parquet_key,
        "duration": duration,
    }