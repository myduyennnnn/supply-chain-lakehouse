import os
import sys
import warnings
from datetime import datetime
from pathlib import Path

import duckdb
import joblib
import lightgbm as lgb
import pandas as pd
import numpy as np
from catboost import CatBoostClassifier
from dotenv import load_dotenv
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score, precision_recall_curve
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder, StandardScaler
from xgboost import XGBClassifier

load_dotenv()
warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "ml_model"
DB_PATH = str(BASE_DIR.parent / "lakehouse.db")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE_DIR))
try:
    from mlflow_setup import TRACKING_URI, EXPERIMENT_NAME, MODEL_NAME
    import mlflow
    import mlflow.sklearn
    _MLFLOW_AVAILABLE = True
except ImportError:
    _MLFLOW_AVAILABLE = False


def _log_to_mlflow(best_name, best_model, df_results, all_features, selected_features, train_size, val_size, test_size):
    if not _MLFLOW_AVAILABLE:
        return
    r2_endpoint = os.getenv("R2_ENDPOINT_URL")
    r2_key = os.getenv("R2_ACCESS_KEY_ID")
    r2_secret = os.getenv("R2_SECRET_ACCESS_KEY")
    if not (r2_endpoint and r2_key and r2_secret):
        return
    os.environ.update({
        "MLFLOW_S3_ENDPOINT_URL": r2_endpoint,
        "AWS_ACCESS_KEY_ID": r2_key,
        "AWS_SECRET_ACCESS_KEY": r2_secret,
    })
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name=f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):

        mlflow.log_params({
            "train_rows":                train_size,
            "val_rows":                  val_size,
            "test_rows":                 test_size,
            "n_features_original":       len(all_features),
            "n_features_selected":       len(selected_features),
            "feature_importance_cutoff": 0.005,
            "best_model":                best_name,
        })

        for _, row in df_results.iterrows():
            prefix = row["Model"].lower().replace(" ", "_")
            mlflow.log_metrics({
                f"{prefix}_accuracy":  round(row["Accuracy"],  4),
                f"{prefix}_precision": round(row["Precision"], 4),
                f"{prefix}_recall":    round(row["Recall"],    4),
                f"{prefix}_f1":        round(row["F1-Score"],  4),
                f"{prefix}_auc":       round(row["AUC"],       4),
            })

        mlflow.set_tags({
            "best_model_name": best_name,
            "data_source":     "main_gold.feat_delivery_risk",
        })

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

        for fname in ["results.csv"]:
            fpath = OUTPUT_DIR / fname
            if fpath.exists():
                mlflow.log_artifact(str(fpath), artifact_path="artifacts")


def main():
    print("[1/5] Dang ket noi DuckDB...")
    with duckdb.connect(DB_PATH) as con:
        df = con.execute("SELECT * FROM main_gold.feat_delivery_risk").df()

    target = "late_delivery_risk"
    X = df.drop(columns=[target])
    y = df[target].astype(int)
    ratio = (len(y) - y.sum()) / y.sum()

    print("[2/5] Dang chia tap du lieu...")
    X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.4, stratify=y, random_state=42)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.5, stratify=y_temp, random_state=42)

    num_f = X_train.select_dtypes(include=["int64", "float64"]).columns.tolist()
    cat_f = X_train.select_dtypes(include=["object", "category"]).columns.tolist()
    all_features = num_f + cat_f
    pre = ColumnTransformer([
        ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), num_f),
        ("cat", Pipeline([("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")), ("encoder", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1))]), cat_f)
    ])

    X_train_p = pre.fit_transform(X_train)
    X_val_p = pre.transform(X_val)
    X_test_p = pre.transform(X_test)

    # Feature Selection
    fs_model = XGBClassifier(n_estimators=100, max_depth=6, random_state=42, n_jobs=-1).fit(X_train_p, y_train)
    fi_df = pd.DataFrame({"Feature": all_features, "Importance": fs_model.feature_importances_})
    selected_features = fi_df[fi_df["Importance"] > 0.005]["Feature"].tolist()
    selected_idx = [all_features.index(f) for f in selected_features]

    X_train_p, X_val_p, X_test_p = X_train_p[:, selected_idx], X_val_p[:, selected_idx], X_test_p[:, selected_idx]

    print("[3/5] Dang train cac mo hinh...")
    models = {
        "XGBoost":      XGBClassifier(n_estimators=1000, learning_rate=0.03, max_depth=8, scale_pos_weight=ratio, random_state=42, n_jobs=-1),
        "LightGBM":     LGBMClassifier(n_estimators=1000, learning_rate=0.03, num_leaves=40, scale_pos_weight=ratio, random_state=42, n_jobs=-1, verbose=-1),
        "CatBoost":     CatBoostClassifier(iterations=1000, learning_rate=0.03, depth=8, scale_pos_weight=ratio, random_seed=42, verbose=False),
        "Random Forest": RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=42, n_jobs=-1),
        "Logistic Reg": LogisticRegression(class_weight="balanced", max_iter=5000),
    }

    results = []
    best_f1 = 0
    best_model_obj = None
    best_name = ""
    best_threshold = 0.5

    for name, model in models.items():
        print(f"  -> Dang train {name}...")
        model.fit(X_train_p, y_train)

        probs_val = model.predict_proba(X_val_p)[:, 1]
        precisions, recalls, thresholds = precision_recall_curve(y_val, probs_val)
        idx = np.argmin(np.abs(precisions - recalls))

        probs_test = model.predict_proba(X_test_p)[:, 1]
        preds_test = (probs_test >= thresholds[idx]).astype(int)

        results.append({
            "Model":     name,
            "Accuracy":  accuracy_score(y_test, preds_test),
            "Precision": precision_score(y_test, preds_test),
            "Recall":    recall_score(y_test, preds_test),
            "F1-Score":  f1_score(y_test, preds_test),
            "AUC":       roc_auc_score(y_test, probs_test),
        })

        if results[-1]["F1-Score"] > best_f1:
            best_f1 = results[-1]["F1-Score"]
            best_model_obj = model
            best_name = name
            best_threshold = thresholds[idx]

    df_results = pd.DataFrame(results).sort_values("F1-Score", ascending=False)
    print("\n[Ket qua] Bang xep hang (theo F1-Score):")
    print(df_results.to_string(index=False))
    df_results.to_csv(OUTPUT_DIR / "results.csv", index=False)

    print(f"[4/5] Luu model tot nhat: {best_name} (Threshold: {best_threshold:.4f})")

    joblib.dump(best_model_obj, OUTPUT_DIR / "best_model.pkl")
    joblib.dump(best_threshold, OUTPUT_DIR / "best_threshold.pkl")
    joblib.dump(pre,            OUTPUT_DIR / "preprocessor.pkl")
    joblib.dump(X_test_p,       OUTPUT_DIR / "X_test_p.pkl")
    joblib.dump(y_test,         OUTPUT_DIR / "y_test.pkl")
    joblib.dump(selected_features, OUTPUT_DIR / "selected_features.pkl")
    joblib.dump(all_features,   OUTPUT_DIR / "all_original_features.pkl")

    print("[5/5] Ghi log MLflow...")
    try:
        _log_to_mlflow(
            best_name=best_name,
            best_model=best_model_obj,
            df_results=df_results,
            all_features=all_features,
            selected_features=selected_features,
            train_size=len(X_train),
            val_size=len(X_val),
            test_size=len(X_test),
        )
    except Exception as e:
        print(f"[Loi] Khong the ghi MLflow: {e}")

    print("[Hoan tat] Tien trinh ket thuc thanh cong.")


if __name__ == "__main__":
    main()