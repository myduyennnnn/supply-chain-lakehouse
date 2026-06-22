"""
Upload lakehouse.db + ml_app/ml_model artifacts to R2.

Run this after the pipeline + training are done so teammates can clone
and skip re-running dbt and ML training entirely.

Usage:
    python scripts/push_lakehouse.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

import os
from botocore.exceptions import ClientError
from ingestion.clients.r2_client import get_r2_client

BUCKET          = os.getenv("R2_BUCKET_NAME", "supply-chain-ai-native")
DB_PATH         = ROOT / "lakehouse.db"
ML_MODEL_DIR    = ROOT / "ml_app" / "ml_model"
R2_LAKEHOUSE_KEY = "lakehouse/lakehouse.db"
R2_ML_PREFIX    = "ml_model/"

ML_FILES = [
    "best_model.pkl",
    "preprocessor.pkl",
    "selected_features.pkl",
    "all_original_features.pkl",
    "X_test_p.pkl",
    "y_test.pkl",
    "results.csv",
]


def _upload(client, local_path: Path, r2_key: str) -> bool:
    size_mb = local_path.stat().st_size / 1024 / 1024
    print(f"  Uploading {local_path.name} ({size_mb:.1f} MB) ...", end=" ", flush=True)
    try:
        client.upload_file(str(local_path), BUCKET, r2_key)
        print(f"OK  ->  s3://{BUCKET}/{r2_key}")
        return True
    except ClientError as exc:
        print(f"FAIL  ({exc})")
        return False


def main() -> None:
    print("\n=== push_lakehouse: upload lakehouse.db + ML artifacts to R2 ===\n")

    try:
        client = get_r2_client()
    except ValueError as exc:
        print(f"[FAIL] {exc}")
        sys.exit(1)

    ok_count = 0
    fail_count = 0

    # ── lakehouse.db ──────────────────────────────────────────────────────────
    print("[1] lakehouse.db")
    if not DB_PATH.exists():
        print(f"  [SKIP] Not found at {DB_PATH} — run the gold pipeline first.")
    else:
        if _upload(client, DB_PATH, R2_LAKEHOUSE_KEY):
            ok_count += 1
        else:
            fail_count += 1

    # ── ML model artifacts ────────────────────────────────────────────────────
    print("\n[2] ML model artifacts")
    any_found = False
    for fname in ML_FILES:
        fpath = ML_MODEL_DIR / fname
        if not fpath.exists():
            continue
        any_found = True
        if _upload(client, fpath, R2_ML_PREFIX + fname):
            ok_count += 1
        else:
            fail_count += 1

    if not any_found:
        print(f"  [SKIP] No files in {ML_MODEL_DIR} — run training first.")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'=' * 55}")
    print(f"  Uploaded: {ok_count}  |  Failed: {fail_count}")
    if fail_count == 0 and ok_count > 0:
        print("\n  Teammates can now clone and run setup.ps1 / setup.sh")
        print("  without re-running dbt or training the model.")
    print(f"{'=' * 55}\n")

    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
