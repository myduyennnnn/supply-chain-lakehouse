"""
Train Delivery Risk Model

Flow:
  1. Doc feat_delivery_risk tu DuckDB (lakehouse.db)
  2. Split -> Preprocess -> Feature selection (XGBoost importance)
  3. Train 5 models, danh gia tren test set
  4. Luu artifacts local (pkl) -- luon chay du MLflow co down
  5. Log experiment len MLflow (Supabase backend + R2 artifacts)
     -- wrapped trong try/except, khong chan pipeline neu server down
"""

import os
import sys
import warnings
from datetime import datetime
from pathlib import Path

import duckdb
import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from dotenv import load_dotenv
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder, StandardScaler
from xgboost import XGBClassifier

load_dotenv()
warnings.filterwarnings("ignore")

OUTPUT_DIR = Path(__file__).parent / "ml_model"
DB_PATH    = str(Path(__file__).parent.parent / "lakehouse.db")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── MLflow config (import gracefully) ─────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
try:
    from mlflow_setup import TRACKING_URI, EXPERIMENT_NAME, MODEL_NAME
    import mlflow
    import mlflow.sklearn
    _MLFLOW_AVAILABLE = True
except ImportError:
    _MLFLOW_AVAILABLE = False
    print("[!] mlflow not installed -- local pkl only.")


# ── MLflow logging helper ──────────────────────────────────────────────────────

def _log_to_mlflow(
    all_features: list,
    selected_features: list,
    train_size: int,
    val_size: int,
    test_size: int,
    df_results: pd.DataFrame,
    best_name: str,
    best_model,
) -> str | None:
    """
    Log experiment len MLflow.
    Tra ve run_id neu thanh cong, None neu that bai.
    MLflow tu dong register model vao Model Registry voi ten MODEL_NAME.
    """
    if not _MLFLOW_AVAILABLE:
        return None

    # Map R2_* -> AWS_* truoc khi bat ky artifact upload nao xay ra.
    # MLflow S3 artifact client doc AWS_ACCESS_KEY_ID / MLFLOW_S3_ENDPOINT_URL,
    # KHONG doc R2_* truc tiep.
    r2_endpoint = os.getenv("R2_ENDPOINT_URL", "")
    r2_key      = os.getenv("R2_ACCESS_KEY_ID", "")
    r2_secret   = os.getenv("R2_SECRET_ACCESS_KEY", "")

    if not (r2_endpoint and r2_key and r2_secret):
        print("    [!] R2 credentials missing in .env — MLflow artifact upload will fail.")
        return None

    os.environ["MLFLOW_S3_ENDPOINT_URL"] = r2_endpoint
    os.environ["AWS_ACCESS_KEY_ID"]      = r2_key
    os.environ["AWS_SECRET_ACCESS_KEY"]  = r2_secret
    print(f"    R2 credentials mapped  -> MLFLOW_S3_ENDPOINT_URL={r2_endpoint}")

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    run_name = f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Dung explicit run thay vi context manager de co the set FINISHED/FAILED chu dong.
    # Neu de exception tu nhien thoat khoi 'with mlflow.start_run()', MLflow se tu dong
    # danh dau run la FAILED truoc ca khi exception len toi try/except o main().
    run = mlflow.start_run(run_name=run_name)
    run_id = run.info.run_id
    try:
        # ── Params ──────────────────────────────────────────────────────────
        mlflow.log_params({
            "train_rows":                train_size,
            "val_rows":                  val_size,
            "test_rows":                 test_size,
            "n_features_original":       len(all_features),
            "n_features_selected":       len(selected_features),
            "feature_importance_cutoff": 0.005,
            "best_model":                best_name,
        })
        print("    params logged")

        # ── Metrics ─────────────────────────────────────────────────────────
        for _, row in df_results.iterrows():
            prefix = row["Model"].lower().replace(" ", "_")
            mlflow.log_metrics({
                f"{prefix}_accuracy":  round(row["Accuracy"],  4),
                f"{prefix}_precision": round(row["Precision"], 4),
                f"{prefix}_recall":    round(row["Recall"],    4),
                f"{prefix}_f1":        round(row["F1-Score"],  4),
                f"{prefix}_auc":       round(row["AUC"],       4),
            })

        best_row = df_results.iloc[0]
        mlflow.log_metrics({
            "best_accuracy":  round(best_row["Accuracy"],  4),
            "best_precision": round(best_row["Precision"], 4),
            "best_recall":    round(best_row["Recall"],    4),
            "best_f1":        round(best_row["F1-Score"],  4),
            "best_auc":       round(best_row["AUC"],       4),
        })
        print("    metrics logged")

        # ── Tags ─────────────────────────────────────────────────────────────
        mlflow.set_tags({
            "best_model_name": best_name,
            "data_source":     "main_gold.feat_delivery_risk",
        })

        # ── Log model -> Model Registry ──────────────────────────────────────
        # Dung sklearn flavor cho tat ca: XGBClassifier/LGBMClassifier/CatBoost
        # deu la sklearn-compatible estimator, mlflow.sklearn dung pickle -> on dinh.
        # mlflow.xgboost.log_model bi loi _estimator_type voi mot so version
        # XGBoost vi MLflow kiem tra sklearn mixin khi dung native XGBoost format.
        # 'name' thay the 'artifact_path' tu MLflow 2.12+.
        print(f"    uploading model ({best_name}) to R2 artifact store ...")
        mlflow.sklearn.log_model(
            sk_model=best_model,
            name="model",
            registered_model_name=MODEL_NAME,
            skops_trusted_types=[
                "xgboost.core.Booster",
                "xgboost.sklearn.XGBClassifier",
                "lightgbm.basic.Booster",
                "lightgbm.sklearn.LGBMClassifier",
                "catboost.core.CatBoostClassifier",
            ],
        )
        print("    model registered in MLflow Model Registry")

        # ── Log preprocessing artifacts ──────────────────────────────────────
        print("    uploading preprocessing artifacts ...")
        for fname in [
            "preprocessor.pkl",
            "selected_features.pkl",
            "all_original_features.pkl",
            "X_test_p.pkl",
            "y_test.pkl",
            "results.csv",
        ]:
            fpath = OUTPUT_DIR / fname
            if fpath.exists():
                mlflow.log_artifact(str(fpath), artifact_path="artifacts")
        print("    artifacts uploaded")

        mlflow.end_run(status="FINISHED")

    except Exception as exc:
        mlflow.end_run(status="FAILED")
        raise RuntimeError(f"MLflow step failed: {exc}") from exc

    return run_id


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[1] Doc feat_delivery_risk tu {DB_PATH} ...")
    con = duckdb.connect(DB_PATH)
    df  = con.execute("SELECT * FROM main_gold.feat_delivery_risk").df()
    con.close()

    if df.empty:
        raise ValueError("feat_delivery_risk is empty -- run dbt gold ML first.")

    print(f"    -> {df.shape[0]:,} rows | {df.shape[1]} columns")

    target = "late_delivery_risk"
    X      = df.drop(columns=[target])
    y      = df[target].astype(int)
    ratio  = (len(y) - y.sum()) / y.sum()

    # ── Split ────────────────────────────────────────────────────────────────
    print("[2] Train / Val / Test split ...")
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y, test_size=0.15, stratify=y, random_state=42,
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp, test_size=0.1765, stratify=y_temp, random_state=42,
    )
    print(f"    -> train={len(X_train):,} | val={len(X_val):,} | test={len(X_test):,}")

    num_f        = X_train.select_dtypes(include=["int64", "float64"]).columns.tolist()
    cat_f        = X_train.select_dtypes(include=["object", "category"]).columns.tolist()
    all_features = num_f + cat_f
    print(f"    -> {len(num_f)} numeric | {len(cat_f)} categorical features")

    # ── Preprocess + feature selection ───────────────────────────────────────
    print("[3] Fit preprocessor + feature selection ...")
    pre = ColumnTransformer([
        ("num", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler",  StandardScaler()),
        ]), num_f),
        ("cat", Pipeline([
            ("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")),
            ("encoder", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
        ]), cat_f),
    ])

    X_train_p = pre.fit_transform(X_train)
    X_val_p   = pre.transform(X_val)
    X_test_p  = pre.transform(X_test)

    fs_model = XGBClassifier(n_estimators=100, max_depth=6, random_state=42, n_jobs=-1)
    fs_model.fit(X_train_p, y_train)

    fi_df = (
        pd.DataFrame({"Feature": all_features, "Importance": fs_model.feature_importances_})
        .sort_values("Importance", ascending=False)
    )
    selected_features = fi_df[fi_df["Importance"] > 0.005]["Feature"].tolist()
    print(f"    -> {len(selected_features)}/{len(all_features)} features (importance > 0.005)")

    selected_idx = [all_features.index(f) for f in selected_features]
    X_train_p    = X_train_p[:, selected_idx]
    X_val_p      = X_val_p[:,   selected_idx]
    X_test_p     = X_test_p[:,  selected_idx]

    # ── Save artifacts local (luon chay, khong phu thuoc MLflow) ─────────────
    print(f"[4] Luu artifacts vao {OUTPUT_DIR} ...")
    joblib.dump(selected_features, OUTPUT_DIR / "selected_features.pkl")
    joblib.dump(pre,               OUTPUT_DIR / "preprocessor.pkl")
    joblib.dump(all_features,      OUTPUT_DIR / "all_original_features.pkl")
    joblib.dump(X_test_p,          OUTPUT_DIR / "X_test_p.pkl")
    joblib.dump(y_test,            OUTPUT_DIR / "y_test.pkl")

    # ── Train models ──────────────────────────────────────────────────────────
    print("[5] Training models ...")
    models = {
        "XGBoost":       XGBClassifier(n_estimators=500, max_depth=6, scale_pos_weight=ratio, random_state=42, eval_metric="auc"),
        "LightGBM":      LGBMClassifier(n_estimators=500, num_leaves=31, scale_pos_weight=ratio, random_state=42, n_jobs=-1, verbose=-1),
        "CatBoost":      CatBoostClassifier(iterations=500, depth=6, scale_pos_weight=ratio, random_seed=42, verbose=False),
        "Random Forest": RandomForestClassifier(n_estimators=200, max_depth=10, class_weight="balanced", random_state=42),
        "Logistic Reg":  LogisticRegression(class_weight="balanced", max_iter=5000, random_state=42),
    }

    results = []
    for name, model in models.items():
        if name == "XGBoost":
            model.fit(X_train_p, y_train, eval_set=[(X_val_p, y_val)], verbose=False)
        elif name == "LightGBM":
            model.fit(X_train_p, y_train, eval_set=[(X_val_p, y_val)],
                      callbacks=[lgb.early_stopping(30, verbose=False)])
        elif name == "CatBoost":
            model.fit(X_train_p, y_train, eval_set=(X_val_p, y_val), early_stopping_rounds=30)
        else:
            model.fit(X_train_p, y_train)

        probs = model.predict_proba(X_test_p)[:, 1]
        preds = (probs >= 0.5).astype(int)
        results.append({
            "Model":     name,
            "Accuracy":  accuracy_score(y_test, preds),
            "Precision": precision_score(y_test, preds, zero_division=0),
            "Recall":    recall_score(y_test, preds),
            "F1-Score":  f1_score(y_test, preds),
            "AUC":       roc_auc_score(y_test, probs),
        })
        print(f"    OK {name}")

    df_results = pd.DataFrame(results).sort_values("F1-Score", ascending=False)
    df_results.to_csv(OUTPUT_DIR / "results.csv", index=False)

    best_name  = df_results.iloc[0]["Model"]
    best_model = models[best_name]
    joblib.dump(best_model, OUTPUT_DIR / "best_model.pkl")

    print("\n" + "=" * 55)
    print(df_results.to_string(index=False))
    print(f"\nBest model : {best_name}")
    print(f"Artifacts  : {OUTPUT_DIR}")

    # ── Log to MLflow (optional, wrapped in try/except) ───────────────────────
    print("\n[6] Logging to MLflow ...")
    try:
        run_id = _log_to_mlflow(
            all_features=all_features,
            selected_features=selected_features,
            train_size=len(X_train),
            val_size=len(X_val),
            test_size=len(X_test),
            df_results=df_results,
            best_name=best_name,
            best_model=best_model,
        )
        if run_id:
            print(f"    MLflow OK  -> run_id: {run_id}")
            print(f"    Tracking   -> {TRACKING_URI}")
        else:
            print("    MLflow skipped (not installed).")
    except Exception as exc:
        print(f"    MLflow logging failed: {exc}")
        print("    -> Artifacts da duoc luu local, pipeline tiep tuc binh thuong.")


if __name__ == "__main__":
    main()
