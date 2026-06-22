"""
Tasks: ML Training + MLflow Promotion

1. train_ml_model   -- chay train_model.py, log experiment len MLflow
2. promote_to_production -- chuyen model moi nhat sang alias "production"
                            trong MLflow Model Registry
"""

import subprocess
import sys
from pathlib import Path

from prefect import task, get_run_logger

ROOT       = Path(__file__).resolve().parents[2]
ML_APP_DIR = ROOT / "ml_app"

sys.path.insert(0, str(ROOT))


# ── Helper: promote model moi nhat -> alias "production" ──────────────────────

def _promote_to_production(logger) -> None:
    """
    Lay version moi nhat cua MODEL_NAME trong MLflow Registry
    va gan alias 'production' cho no.
    Archive tat ca alias 'production' cu truoc do.

    Dung MLflow Model Aliases (MLflow >= 2.0, thay the deprecated Stages).
    """
    try:
        from mlflow import MlflowClient
        from ml_app.mlflow_setup import TRACKING_URI, MODEL_NAME

        client = MlflowClient(tracking_uri=TRACKING_URI)

        # Lay tat ca version, chon version moi nhat (so lon nhat)
        versions = client.search_model_versions(f"name='{MODEL_NAME}'")
        if not versions:
            logger.warning("No model versions found in registry -- skipping promotion.")
            return

        latest = max(versions, key=lambda v: int(v.version))
        new_version = latest.version

        # Xoa alias 'production' cu neu co
        try:
            current_prod = client.get_model_version_by_alias(MODEL_NAME, "production")
            if current_prod.version != new_version:
                client.delete_registered_model_alias(MODEL_NAME, "production")
                logger.info(
                    "Archived old production: version %s", current_prod.version
                )
        except Exception:
            pass  # Chua co alias 'production' nao

        # Set alias 'production' cho version moi nhat
        client.set_registered_model_alias(MODEL_NAME, "production", new_version)
        logger.info(
            "Promoted '%s' version %s -> alias 'production'",
            MODEL_NAME, new_version,
        )

    except ImportError:
        logger.warning("mlflow not installed -- skipping promotion.")
    except Exception as exc:
        logger.warning("MLflow promotion failed (non-fatal): %s", exc)


# ── Tasks ─────────────────────────────────────────────────────────────────────

@task(
    name="train-ml-model",
    retries=1,
    retry_delay_seconds=60,
)
def train_ml_model() -> None:
    logger = get_run_logger()
    logger.info("Training ML model from feat_delivery_risk ...")

    result = subprocess.run(
        [sys.executable, str(ML_APP_DIR / "train_model.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    if result.stdout:
        logger.info(result.stdout)
    if result.returncode != 0:
        logger.error(result.stderr)
        raise RuntimeError(
            f"train_model.py failed (exit {result.returncode}):\n{result.stderr}"
        )

    logger.info("Training complete -- artifacts saved to ml_app/ml_model/")

    # Sau khi train xong, promote model moi nhat len production
    _promote_to_production(logger)
