"""
dbt Run Logging Service

Parse target/run_results.json sau khi dbt run/test
và ghi log vào Supabase.
"""

import json
import logging
from pathlib import Path

from ingestion.clients.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

DBT_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent / "supply_chain_dbt"
RUN_RESULTS_PATH = DBT_PROJECT_DIR / "target" / "run_results.json"


def log_dbt_run() -> None:
    """Đọc run_results.json và insert vào dbt_run_logs."""

    if not RUN_RESULTS_PATH.exists():
        logger.error("run_results.json not found: %s", RUN_RESULTS_PATH)
        return

    with open(RUN_RESULTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    invocation_id = data["metadata"]["invocation_id"]
    client = get_supabase_client()

    rows = []

    for result in data["results"]:

        unique_id = result["unique_id"]
        parts = unique_id.split(".")
        node_type = parts[0]   # model / test

        # bỏ qua test nodes nếu chỉ muốn log model
        # (comment dòng dưới nếu muốn log cả test)
        # if node_type == "test":
        #     continue

        if node_type == "test":
            model_name = parts[-2]   # tên test, bỏ hash
        else:
            model_name = parts[-1]   # tên model

        adapter_response = result.get("adapter_response", {}) or {}

        rows.append({
            "invocation_id": invocation_id,
            "model_name": model_name,
            "schema_name": node_type,
            "materialization": adapter_response.get("materialization"),
            "status": result["status"],
            "rows_affected": adapter_response.get("rows_affected"),
            "execution_time": round(result["execution_time"], 3),
            "message": result.get("message"),
        })

    if rows:
        client.table("dbt_run_logs").insert(rows).execute()
        logger.info("Logged %d dbt results to Supabase", len(rows))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    log_dbt_run()