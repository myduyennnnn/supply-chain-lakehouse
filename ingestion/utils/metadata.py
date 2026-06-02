"""
Metadata utilities

Purpose:
    - Add ingestion metadata columns
    - Generate flat R2 object keys (Bronze = static datasets)
    - Support lineage tracking via metadata columns
"""

from datetime import datetime, timezone
from pathlib import Path
import uuid

import pandas as pd


def generate_run_id() -> str:
    """
    Generate unique ingestion run id.

    Example:
        8d13cb0d-0a61-4c89-b6ef-52fdbec5e0a7
    """
    return str(uuid.uuid4())


def add_ingestion_metadata(
    df: pd.DataFrame,
    source_file: str,
    dataset_name: str,
    run_id: str,
) -> pd.DataFrame:
    """
    Add metadata columns into dataframe.

    Bronze principles:
        - Keep original columns unchanged
        - Add lineage metadata only

    Added columns:
        _ingested_at        — ISO timestamp of ingestion
        _source_file        — original filename
        _dataset_name       — logical dataset name
        _ingestion_run_id   — unique run id for traceability
        _record_status      — future-proof for CDC / soft delete
    """
    df = df.copy()

    now = datetime.now(timezone.utc)

    df["_ingested_at"]       = now.isoformat()
    df["_source_file"]       = source_file
    df["_dataset_name"]      = dataset_name
    df["_ingestion_run_id"]  = run_id
    df["_record_status"]     = "ACTIVE"

    return df


def build_r2_key(
    prefix: str,
    filename: str,
    extension: str,
) -> str:
    """
    Build flat Bronze path.

    Bronze layer lưu static datasets — không partition theo date
    vì data không tăng trưởng hàng ngày. Lineage được track
    qua metadata columns (_ingested_at, _ingestion_run_id).

    Example:
        bronze/dataco/DataCoSupplyChainDataset.parquet
        bronze/clickstream/tokenized_access_logs.parquet
    """
    stem = Path(filename).stem
    return f"{prefix}/{stem}.{extension}"