"""
Download lakehouse.db + ml_app/ml_model artifacts from R2.

Called automatically by setup.ps1 / setup.sh.
If lakehouse.db is not on R2 yet, exits with code 2 so the setup
script can fall back to running the silver dbt models instead.

Usage:
    python scripts/pull_lakehouse.py
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

BUCKET           = os.getenv("R2_BUCKET_NAME", "supply-chain-ai-native")
DB_PATH          = ROOT / "lakehouse.db"
ML_MODEL_DIR     = ROOT / "ml_app" / "ml_model"
R2_LAKEHOUSE_KEY = "lakehouse/lakehouse.db"
R2_ML_PREFIX     = "ml_model/"

ML_FILES = [
    "best_model.pkl",
    "preprocessor.pkl",
    "selected_features.pkl",
    "all_original_features.pkl",
    "X_test_p.pkl",
    "y_test.pkl",
    "results.csv",
]

# Exit codes
EXIT_OK              = 0
EXIT_CRED_ERROR      = 1
EXIT_LAKEHOUSE_MISSING = 2   # setup script uses this to trigger --silver-only fallback


def _download(client, r2_key: str, dest: Path) -> bool:
    print(f"  Downloading {dest.name} ...", end=" ", flush=True)
    try:
        client.download_file(BUCKET, r2_key, str(dest))
        size_mb = dest.stat().st_size / 1024 / 1024
        print(f"OK  ({size_mb:.1f} MB)")
        return True
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("404", "NoSuchKey"):
            print("NOT FOUND")
        else:
            print(f"FAIL  ({exc})")
        return False


def main() -> int:
    print("\n=== pull_lakehouse: download lakehouse.db + ML artifacts from R2 ===\n")

    try:
        client = get_r2_client()
    except ValueError as exc:
        print(f"[FAIL] {exc}")
        return EXIT_CRED_ERROR

    # ── lakehouse.db ──────────────────────────────────────────────────────────
    print("[1] lakehouse.db")
    lakehouse_ok = _download(client, R2_LAKEHOUSE_KEY, DB_PATH)
    if not lakehouse_ok:
        print("  [INFO] Will fall back to running silver dbt models.")

    # ── ML model artifacts ────────────────────────────────────────────────────
    print("\n[2] ML model artifacts")
    ML_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    ml_count = 0
    for fname in ML_FILES:
        if _download(client, R2_ML_PREFIX + fname, ML_MODEL_DIR / fname):
            ml_count += 1

    if ml_count == 0:
        print("  [INFO] No ML artifacts on R2 yet — train the model first.")
    else:
        print(f"  {ml_count} artifact(s) downloaded to ml_app/ml_model/")

    print()
    return EXIT_OK if lakehouse_ok else EXIT_LAKEHOUSE_MISSING


if __name__ == "__main__":
    sys.exit(main())
