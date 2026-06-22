"""
MLflow Configuration — Option B
  Backend store : Supabase PostgreSQL  (SUPABASE_DB_URL)
  Artifact store: Cloudflare R2        (R2_* env vars, S3-compatible)
  Tracking URI  : MLFLOW_TRACKING_URI  (default http://localhost:5000)

Env vars cần có trong .env:
  MLFLOW_TRACKING_URI   = http://localhost:5000
  MLFLOW_EXPERIMENT_NAME= delivery-risk-prediction   (optional)
  SUPABASE_DB_URL       = postgresql://postgres.XXX:PWD@host:5432/postgres
  R2_ENDPOINT_URL       = https://<account_id>.r2.cloudflarestorage.com
  R2_ACCESS_KEY_ID      = ...
  R2_SECRET_ACCESS_KEY  = ...
  R2_BUCKET_NAME        = supply-chain-ai-native      (optional override)
"""

import os
from dotenv import load_dotenv

load_dotenv()

TRACKING_URI    = os.getenv("MLFLOW_TRACKING_URI",    "http://localhost:5000")
EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "delivery-risk-prediction")
MODEL_NAME      = "delivery-risk-model"

# S3 artifact root on R2 — mlflow server dùng path này khi khởi động
R2_BUCKET       = os.getenv("R2_BUCKET_NAME", "supply-chain-ai-native")
ARTIFACT_ROOT   = f"s3://{R2_BUCKET}/mlflow/artifacts"
