"""
Logging Service

Ghi ingestion tracking vào Supabase:
    - pipeline_runs
    - ingestion_logs
    - metadata_catalog
"""
from typing import Optional

import logging
from datetime import datetime, timezone
from uuid import UUID

from ingestion.clients.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Pipeline Runs
# ──────────────────────────────────────────────

def create_pipeline_run(
    run_id: str,
    pipeline_name: str,
    total_datasets: int,
) -> None:
    """Insert pipeline run với status RUNNING khi bắt đầu."""

    client = get_supabase_client()

    client.table("pipeline_runs").insert({
        "run_id":         run_id,
        "pipeline_name":  pipeline_name,
        "status":         "RUNNING",
        "total_datasets": total_datasets,
    }).execute()

    logger.info("Pipeline run created: %s", run_id)


def update_pipeline_run(
    run_id: str,
    status: str,
    success_count: int,
    skipped_count: int,
    failed_count: int,
    total_rows: int,
    duration_seconds: float,
    error_message: str | None = None,
) -> None:
    """Update pipeline run khi hoàn tất."""

    client = get_supabase_client()

    client.table("pipeline_runs").update({
        "status":           status,
        "success_count":    success_count,
        "skipped_count":    skipped_count,
        "failed_count":     failed_count,
        "total_rows":       total_rows,
        "duration_seconds": round(duration_seconds, 3),
        "error_message":    error_message,
        "finished_at":      datetime.now(timezone.utc).isoformat(),
    }).eq("run_id", run_id).execute()

    logger.info("Pipeline run updated: %s → %s", run_id, status)


# ──────────────────────────────────────────────
# Ingestion Logs
# ──────────────────────────────────────────────

def log_ingestion(
    run_id: str,
    dataset_name: str,
    source_file: str,
    bronze_prefix: str,
    status: str,
    rows_ingested: int | None = None,
    csv_key: str | None = None,
    parquet_key: str | None = None,
    error_message: str | None = None,
    duration_seconds: float | None = None,
) -> None:
    """Insert 1 row vào ingestion_logs sau khi ingest xong 1 file."""

    client = get_supabase_client()

    client.table("ingestion_logs").insert({
        "run_id":           run_id,
        "dataset_name":     dataset_name,
        "source_file":      source_file,
        "bronze_prefix":    bronze_prefix,
        "status":           status,
        "rows_ingested":    rows_ingested,
        "csv_key":          csv_key,
        "parquet_key":      parquet_key,
        "error_message":    error_message,
        "duration_seconds": round(duration_seconds, 3) if duration_seconds else None,
    }).execute()

    logger.info(
        "Ingestion log saved: %s → %s (%s rows)",
        source_file, status, rows_ingested,
    )


# ──────────────────────────────────────────────
# Metadata Catalog
# ──────────────────────────────────────────────

def upsert_metadata_catalog(
    dataset_name: str,
    layer: str,
    r2_prefix: str,
    file_format: str,
    row_count: int,
    column_count: int,
    column_names: list[str],
    encoding: str | None = None,
    description: str | None = None,
) -> None:
    """
    Upsert metadata catalog sau mỗi lần ingest thành công.
    Dùng unique index (dataset_name, layer, file_format) để upsert.
    """

    client = get_supabase_client()

    client.table("metadata_catalog").upsert({
        "dataset_name":  dataset_name,
        "layer":         layer,
        "r2_prefix":     r2_prefix,
        "file_format":   file_format,
        "row_count":     row_count,
        "column_count":  column_count,
        "column_names":  column_names,
        "encoding":      encoding,
        "description":   description,
        "updated_at":    datetime.now(timezone.utc).isoformat(),
    }, on_conflict="dataset_name,layer,file_format").execute()

    logger.info(
        "Metadata catalog upserted: %s / %s / %s",
        dataset_name, layer, file_format,
    )

# ──────────────────────────────────────────────
# Dataset State (Incremental Ingestion)
# ──────────────────────────────────────────────

def get_dataset_hash(
    dataset_name: str,
) -> Optional[str]:
    """
    Lấy hash gần nhất của dataset.

    Returns:
        str | None
    """

    client = get_supabase_client()

    response = (
        client.table("dataset_state")
        .select("file_hash")
        .eq("dataset_name", dataset_name)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]["file_hash"]


def update_dataset_hash(
    dataset_name: str,
    file_hash: str,
    run_id: str,
) -> None:
    """
    Upsert hash mới nhất của dataset.

    Dùng để detect thay đổi file nguồn
    giữa các lần ingest.
    """

    client = get_supabase_client()

    client.table("dataset_state").upsert(
        {
            "dataset_name": dataset_name,
            "file_hash": file_hash,
            "last_run_id": run_id,
            "updated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        },
        on_conflict="dataset_name",
    ).execute()

    logger.info(
        "Dataset hash updated: %s",
        dataset_name,
    )