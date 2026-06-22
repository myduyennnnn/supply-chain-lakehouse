# Supply Chain Lakehouse

A modern data lakehouse for supply chain analytics — raw CSV → cloud object store → dimensional model → ML delivery-risk prediction.

## Architecture

```
data/                        Raw CSV files (DataCo Supply Chain dataset)
  └─► Bronze                 CSV → Parquet, uploaded to Cloudflare R2
        └─► Silver (dbt)     Staging / cleaning models, external Parquet on R2
              └─► Gold (dbt) Dims · Facts · Marts · ML Features in DuckDB
                    └─► ML   XGBoost delivery-risk classifier (MLflow tracking)
                          └─► Data Portal  Streamlit dashboard + prediction UI
```

| Layer | Storage | Tool |
|---|---|---|
| Bronze | Cloudflare R2 (`bronze/`) | Python + boto3 |
| Silver | Cloudflare R2 (`silver/`) | dbt-duckdb external |
| Gold — dims/facts/marts | Cloudflare R2 (`gold/`) | dbt-duckdb external |
| Gold — ML features | `lakehouse.db` (local) | dbt-duckdb table |
| ML model | `ml_app/ml_model/` + R2 (`mlflow/`) | scikit-learn + MLflow |
| Metadata / logs | Supabase PostgreSQL | supabase-py |
| MLflow tracking | Supabase PostgreSQL | MLflow 2.x |
| Orchestration | Local / Prefect | Prefect 2.x |

---

## Prerequisites

- **Python 3.11+**
- **Git**
- **Cloudflare R2** account with a bucket named `supply-chain-ai-native`
- **Supabase** project (free tier is enough)
- PowerShell 5.1+ (Windows) or bash (Linux/Mac)

---

## 1. Clone

```bash
git clone <repo-url>
cd supply-chain-lakehouse
```

---

## 2. Create `.env`

```powershell
copy .env.example .env   # Windows
# cp .env.example .env   # Linux / Mac
```

Open `.env` and fill in your credentials:

| Variable | Where to get |
|---|---|
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | Cloudflare Dashboard → R2 → Manage R2 API Tokens → Create Token (Read & Write) |
| `R2_ENDPOINT_URL` | `https://<account_id>.r2.cloudflarestorage.com` |
| `SUPABASE_URL` / `SUPABASE_KEY` | Supabase Dashboard → Settings → API |
| `SUPABASE_DB_URL` | Supabase Dashboard → Settings → Database → Connection String (URI mode) |

---

## 3. Run setup script

One command handles everything: virtualenv, dependencies, `~/.dbt/profiles.yml`, Supabase tables, silver layer init, and connectivity check.

**Windows:**
```powershell
.\setup.ps1
```

**Linux / macOS:**
```bash
bash setup.sh
```

The script runs 8 steps automatically:

| Step | Action |
|---|---|
| 1 | Check Python ≥ 3.11 |
| 2 | Create `.venv` and install `requirements.txt` |
| 3 | Detect `.env`, stop if credentials are missing |
| 4 | Generate `~/.dbt/profiles.yml` from `.env` |
| 5 | Create 5 Supabase tables (idempotent) |
| 6 | Run silver dbt models to register VIEWs in `lakehouse.db`* |
| 7 | Run `verify_system.py` |

> *Silver models read from the existing bronze Parquet on R2 and re-write the same silver Parquet — this is safe and idempotent. It is required so that gold models can reference `main_silver.*` tables in DuckDB.

Expected output at end of setup:
```
[OK]  Environment vars
[OK]  R2 connectivity
[OK]  Supabase
[OK]  DuckDB gold        ← silver VIEWs registered, gold tables readable
[FAIL] ML artifacts      ← normal, model not trained yet
[SKIP] MLflow server     ← normal if server not started yet
```

---

## 7. Push to R2 (one-time, after first run)

After running the pipeline and training the model, push `lakehouse.db` + ML artifacts to R2 so teammates can clone without re-running anything:

```powershell
python scripts/push_lakehouse.py
```

This uploads:
- `lakehouse.db` → `R2/lakehouse/lakehouse.db` (silver + gold VIEWs + feat_delivery_risk table)
- `ml_app/ml_model/*.pkl` → `R2/ml_model/` (trained model + preprocessor + feature lists)

> Teammates who clone after this will have `setup.ps1` download these files automatically — no dbt run, no model training required.

---

## 8. Run the pipeline

### First-time full run (bronze → silver → gold)

```powershell
python orchestration/pipeline.py
```

### Subsequent runs — gold only (bronze data already on R2)

```powershell
python orchestration/pipeline.py --gold-only
```

### Gold + train ML model

```powershell
python orchestration/pipeline.py --gold-only --with-ml
```

### All options

| Flag | Effect |
|---|---|
| *(no flags)* | bronze → silver → gold |
| `--no-bronze` | skip ingestion, run silver + gold |
| `--silver-only` | silver only |
| `--gold-only` | gold only |
| `--with-ml` | include ML feature models + train model |

---

## 9. Train ML model (standalone)

After the gold pipeline has run at least once (`feat_delivery_risk` exists in `lakehouse.db`):

```powershell
python ml_app/train_model.py
```

Artifacts saved to `ml_app/ml_model/`:

| File | Description |
|---|---|
| `best_model.pkl` | Trained model (XGBoost by default) |
| `preprocessor.pkl` | ColumnTransformer (imputer + scaler + encoder) |
| `selected_features.pkl` | Feature names after importance filtering |
| `all_original_features.pkl` | Full original feature list |
| `results.csv` | Comparison of all 5 models |

Then push to R2 so teammates don't need to retrain:
```powershell
python scripts/push_lakehouse.py
```

---

## 10. MLflow tracking server (optional)

MLflow uses **Supabase PostgreSQL** as backend and **Cloudflare R2** as artifact store.

Open a **separate terminal** and keep it running:

```powershell
.\scripts\start_mlflow_server.ps1
```

UI: [http://localhost:5000](http://localhost:5000)

> Requires `SUPABASE_DB_URL` in `.env`. If not set, the pipeline still works — MLflow logging is skipped gracefully.

---

## 11. Data Portal

```powershell
streamlit run data_portal/app.py
```

UI: [http://localhost:8501](http://localhost:8501)

Pages available:

| Page | Description |
|---|---|
| Executive Summary | KPIs, revenue, delivery trends |
| Sales Dashboard | Product & category performance |
| Delivery Risk | Single + batch ML prediction, SHAP explainability |
| ML Registry | MLflow model versions, metrics history |
| Data Catalog | Metadata of all layers |
| Pipeline Monitor | Supabase run logs |

---

## Running multiple services

```
Terminal 1 (keep open):  .\scripts\start_mlflow_server.ps1
Terminal 2 (keep open):  streamlit run data_portal/app.py
Terminal 3 (one-shot):   python orchestration/pipeline.py --gold-only --with-ml
```

---

## Project structure

```
supply-chain-lakehouse/
├── data/                        Raw CSV source files
├── ingestion/                   Bronze ingestion (CSV → R2 Parquet)
├── supply_chain_dbt/            dbt project (silver + gold models)
│   └── models/
│       ├── bronze/              Source references
│       ├── silver/              Staging / cleaning (external on R2)
│       └── gold/
│           ├── dimensions/      dim_customer, dim_order, dim_product, dim_date
│           ├── facts/           fact_order_items
│           ├── marts/           Executive summary, trend, AI monitoring
│           └── ml/features/     feat_delivery_risk, feat_customer (in lakehouse.db)
├── ml_app/
│   ├── train_model.py           Train + evaluate 5 models, log to MLflow
│   ├── mlflow_setup.py          MLflow config constants
│   └── ml_model/                Saved artifacts (gitignored)
├── orchestration/
│   ├── pipeline.py              Main Prefect flow
│   └── tasks/                   bronze / silver / gold / ml tasks
├── data_portal/
│   ├── app.py                   Streamlit entry point
│   └── pages/                   Multi-page UI
├── scripts/
│   ├── start_mlflow_server.ps1  Start MLflow with R2 + Supabase
│   └── verify_system.py         Health check for all layers
├── requirements.txt
└── .env                         Credentials (gitignored, create manually)
```

---

## Tech stack

| Component | Technology |
|---|---|
| Data storage | Cloudflare R2 (S3-compatible) |
| Query engine | DuckDB |
| Transformation | dbt-duckdb |
| Metadata store | Supabase (PostgreSQL) |
| Orchestration | Prefect 2.x |
| ML training | scikit-learn, XGBoost, LightGBM, CatBoost |
| ML tracking | MLflow 2.x |
| Dashboard | Streamlit + Plotly |
| Explainability | SHAP |
