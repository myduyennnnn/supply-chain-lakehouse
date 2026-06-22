"""
System Verification Script
Kiem tra tung layer cua lakehouse theo thu tu:
  1. .env  — bien moi truong bat buoc
  2. R2    — ket noi Cloudflare R2, doc bronze Parquet
  3. Supabase — ket noi, doc metadata_catalog
  4. DuckDB  — mo lakehouse.db, doc gold tables
  5. MLflow  — ket noi tracking server, lay production model
  6. ML artifacts — kiem tra pkl files co day du khong

Chay:
    python scripts/verify_system.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

PASS = "[OK]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"


def section(title: str) -> None:
    print(f"\n{'='*55}")
    print(f"  {title}")
    print('='*55)


def check(label: str, ok: bool, detail: str = "") -> bool:
    icon = PASS if ok else FAIL
    msg  = f"  {icon}  {label}"
    if detail:
        msg += f"  ({detail})"
    print(msg)
    return ok


# ─────────────────────────────────────────────────────────
# 1. ENV VARIABLES
# ─────────────────────────────────────────────────────────
section("1. Environment Variables")

required_vars = {
    "R2_ACCESS_KEY_ID":     "Cloudflare R2 access key",
    "R2_SECRET_ACCESS_KEY": "Cloudflare R2 secret key",
    "R2_ENDPOINT_URL":      "Cloudflare R2 endpoint URL",
    "SUPABASE_URL":         "Supabase project URL",
    "SUPABASE_KEY":         "Supabase anon/service key",
}
optional_vars = {
    "SUPABASE_DB_URL":      "PostgreSQL URL (required for MLflow Option B)",
    "MLFLOW_TRACKING_URI":  "MLflow server URL (default: http://localhost:5000)",
}

env_ok = True
for var, desc in required_vars.items():
    val = os.getenv(var)
    ok  = bool(val)
    env_ok = env_ok and ok
    check(var, ok, f"{desc}" if ok else f"MISSING — {desc}")

print()
for var, desc in optional_vars.items():
    val = os.getenv(var)
    icon = PASS if val else SKIP
    print(f"  {icon}  {var}  ({desc})")


# ─────────────────────────────────────────────────────────
# 2. R2 CONNECTIVITY
# ─────────────────────────────────────────────────────────
section("2. Cloudflare R2 Connectivity")

r2_ok = False
try:
    import boto3
    from botocore.exceptions import ClientError

    endpoint = os.getenv("R2_ENDPOINT_URL", "").replace("https://", "")
    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{endpoint}",
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
    )
    bucket = os.getenv("R2_BUCKET_NAME", "supply-chain-ai-native")
    resp   = s3.list_objects_v2(Bucket=bucket, Prefix="bronze/", MaxKeys=1)
    count  = resp.get("KeyCount", 0)
    r2_ok  = True
    check("R2 bucket accessible", True, f"bucket={bucket}, bronze objects found={count > 0}")
except ImportError:
    check("R2 (boto3)", False, "boto3 not installed — pip install boto3")
except Exception as e:
    check("R2 connection", False, str(e)[:80])


# ─────────────────────────────────────────────────────────
# 3. SUPABASE CONNECTIVITY
# ─────────────────────────────────────────────────────────
section("3. Supabase Connectivity")

sb_ok = False
try:
    from supabase import create_client
    client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

    # Kiem tra cac bang bat buoc
    required_tables = [
        "pipeline_runs", "ingestion_logs",
        "metadata_catalog", "dataset_state", "dbt_run_logs",
    ]
    for tbl in required_tables:
        try:
            resp = client.table(tbl).select("*").limit(1).execute()
            check(f"table: {tbl}", True)
        except Exception as e:
            check(f"table: {tbl}", False, str(e)[:60])

    # Dem so runs
    try:
        runs = client.table("pipeline_runs").select("run_id", count="exact").execute()
        sb_ok = True
        check("pipeline_runs row count", True, f"{runs.count} runs logged")
    except Exception as e:
        check("pipeline_runs count", False, str(e)[:60])

except ImportError:
    check("Supabase (supabase-py)", False, "not installed — pip install supabase")
except Exception as e:
    check("Supabase connection", False, str(e)[:80])


# ─────────────────────────────────────────────────────────
# 4. DUCKDB — LAKEHOUSE.DB
# ─────────────────────────────────────────────────────────
section("4. DuckDB — lakehouse.db Gold Tables")

db_path = ROOT / "lakehouse.db"
db_ok   = False
try:
    import duckdb

    if not db_path.exists():
        check("lakehouse.db exists", False, f"not found at {db_path}")
    else:
        # Read-only=False nen co the INSTALL/LOAD httpfs (need write access to extension dir)
        con = duckdb.connect(str(db_path), read_only=False)

        # Cau hinh httpfs de doc external tables tren R2
        # External gold tables (dim/fact/mart) la Parquet tren R2, can S3 credentials
        r2_endpoint = (
            os.getenv("R2_ENDPOINT_URL", "")
            .replace("https://", "")
            .replace("http://", "")
            .rstrip("/")
        )
        r2_key    = os.getenv("R2_ACCESS_KEY_ID", "")
        r2_secret = os.getenv("R2_SECRET_ACCESS_KEY", "")

        if r2_endpoint and r2_key and r2_secret:
            try:
                con.execute("INSTALL httpfs; LOAD httpfs;")
                con.execute(f"SET s3_endpoint='{r2_endpoint}';")
                con.execute(f"SET s3_access_key_id='{r2_key}';")
                con.execute(f"SET s3_secret_access_key='{r2_secret}';")
                con.execute("SET s3_url_style='path';")
                con.execute("SET s3_use_ssl=true;")
                con.execute("SET s3_region='auto';")
                check("httpfs + R2 credentials set", True, r2_endpoint)
            except Exception as e:
                check("httpfs setup", False, str(e)[:60])
        else:
            print(f"  {SKIP}  httpfs  (R2_ENDPOINT_URL/KEY/SECRET missing — external tables will fail)")

        # ml/features tables: stored directly in lakehouse.db (materialized='table')
        # dim/fact/mart: external Parquet on R2 (materialized='external')
        gold_tables = [
            ("dim_customer",           "external"),
            ("dim_order",              "external"),
            ("dim_product",            "external"),
            ("dim_date",               "external"),
            ("fact_order_items",       "external"),
            ("mart_executive_summary", "external"),
            ("mart_trend_monthly",     "external"),
            ("feat_delivery_risk",     "table"),
        ]
        any_ok = False
        for tbl, kind in gold_tables:
            try:
                n = con.execute(f"SELECT COUNT(*) FROM main_gold.{tbl}").fetchone()[0]
                check(f"main_gold.{tbl}", True, f"{n:,} rows  [{kind}]")
                any_ok = True
            except Exception as e:
                msg = str(e)
                short = msg[:70].replace("\n", " ")
                check(f"main_gold.{tbl}", False, f"[{kind}] {short}")

        con.close()
        db_ok = any_ok

except ImportError:
    check("DuckDB", False, "not installed — pip install duckdb")
except Exception as e:
    check("DuckDB open", False, str(e)[:80])


# ─────────────────────────────────────────────────────────
# 5. ML ARTIFACTS
# ─────────────────────────────────────────────────────────
section("5. ML Model Artifacts (ml_app/ml_model/)")

model_dir = ROOT / "ml_app" / "ml_model"
artifacts = [
    "best_model.pkl",
    "preprocessor.pkl",
    "selected_features.pkl",
    "all_original_features.pkl",
    "X_test_p.pkl",
    "y_test.pkl",
    "results.csv",
]
ml_ok = True
for fname in artifacts:
    fpath = model_dir / fname
    ok    = fpath.exists()
    ml_ok = ml_ok and ok
    size  = f"{fpath.stat().st_size / 1024:.0f} KB" if ok else "missing"
    check(fname, ok, size)

if ml_ok:
    # Kiem tra load model + predict thu
    try:
        import joblib, numpy as np
        model = joblib.load(model_dir / "best_model.pkl")
        feats = joblib.load(model_dir / "selected_features.pkl")
        X_t   = joblib.load(model_dir / "X_test_p.pkl")
        proba = model.predict_proba(X_t[:5])[:, 1]
        check("Model predict (5 samples)", True, f"proba={[round(p,3) for p in proba]}")
    except Exception as e:
        check("Model predict test", False, str(e)[:80])


# ─────────────────────────────────────────────────────────
# 6. MLFLOW
# ─────────────────────────────────────────────────────────
section("6. MLflow Tracking Server")

tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
mlflow_ok = False
try:
    import mlflow
    from mlflow.tracking import MlflowClient

    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)

    # Ket noi co the lay danh sach experiments
    exps = client.search_experiments()
    check("MLflow server reachable", True, f"{tracking_uri} | {len(exps)} experiments")

    # Kiem tra production model
    MODEL_NAME = "delivery-risk-model"
    try:
        prod = client.get_model_version_by_alias(MODEL_NAME, "production")
        check(f"Production model alias", True,
              f"'{MODEL_NAME}' v{prod.version} | run {prod.run_id[:8]}...")
    except Exception:
        check("Production model alias", False,
              "Chua co alias 'production' — chay pipeline --with-ml lan dau")

    mlflow_ok = True

except ImportError:
    print(f"  {SKIP}  MLflow not installed — pip install mlflow")
except Exception as e:
    print(f"  {SKIP}  MLflow server not running ({tracking_uri})")
    print(f"        Start: .\\scripts\\start_mlflow_server.ps1")


# ─────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────
section("SUMMARY")

results = {
    "Environment vars": env_ok,
    "R2 connectivity":  r2_ok,
    "Supabase":         sb_ok,
    "DuckDB gold":      db_ok,
    "ML artifacts":     ml_ok,
    "MLflow server":    mlflow_ok,
}

all_pass = True
for name, ok in results.items():
    icon = PASS if ok else FAIL
    print(f"  {icon}  {name}")
    all_pass = all_pass and ok

print()
if all_pass:
    print("  System fully operational.")
else:
    print("  Some checks failed — fix the [FAIL] items above before running the pipeline.")

print()
