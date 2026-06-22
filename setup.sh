#!/usr/bin/env bash
# Supply Chain Lakehouse — Setup (no venv, system Python)
# Chay: bash setup.sh

set -e

GREEN="\033[0;32m"; CYAN="\033[0;36m"; YELLOW="\033[1;33m"; RED="\033[0;31m"; NC="\033[0m"

step() { echo -e "\n${CYAN}>>> $1${NC}"; }
ok()   { echo -e "    ${GREEN}[OK] $1${NC}"; }
warn() { echo -e "    ${YELLOW}[WARN] $1${NC}"; }
fail() { echo -e "    ${RED}[FAIL] $1${NC}"; exit 1; }

get_env() { grep -E "^\s*${1}\s*=" .env 2>/dev/null | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d "'" | xargs; }

echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  Supply Chain Lakehouse — Setup${NC}"
echo -e "${CYAN}============================================================${NC}"


# ── 1. Python ────────────────────────────────────────────────────────────────
step "1. Kiem tra Python >= 3.11..."

PYTHON=""
for cmd in python3.12 python3.11 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -gt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -ge 11 ]); then
            PYTHON="$cmd"
            ok "$("$cmd" --version)  ->  $(command -v "$cmd")"
            break
        fi
    fi
done

[ -z "$PYTHON" ] && fail "Python >= 3.11 khong tim thay. Cai tai: https://www.python.org/downloads/"


# ── 2. Dependencies ───────────────────────────────────────────────────────────
step "2. Cai dat dependencies (requirements.txt)..."

"$PYTHON" -m pip install --upgrade pip --quiet

# Ubuntu 23.04+ chan pip vao system Python — thu them --break-system-packages neu that bai
if "$PYTHON" -m pip install -r requirements.txt --quiet; then
    ok "Tat ca packages da duoc cai."
else
    warn "Thu lai voi --break-system-packages (Ubuntu 23.04+)..."
    "$PYTHON" -m pip install --break-system-packages -r requirements.txt --quiet
    ok "Tat ca packages da duoc cai."
fi


# ── 3. .env ───────────────────────────────────────────────────────────────────
step "3. Kiem tra file .env..."

if [ -f ".env" ]; then
    ok ".env da ton tai."
else
    if [ -f ".env.example" ]; then
        cp .env.example .env
        warn "Da sao chep .env.example -> .env"
        echo ""
        echo -e "  ${YELLOW}!!! QUAN TRONG: Mo file .env va dien credentials truoc khi tiep tuc:${NC}"
        echo -e "  ${YELLOW}      R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL${NC}"
        echo -e "  ${YELLOW}      SUPABASE_URL, SUPABASE_KEY, SUPABASE_DB_URL${NC}"
        echo ""
        echo "  Sau khi dien xong, chay lai: bash setup.sh"
        exit 0
    else
        fail "Khong tim thay .env hoac .env.example"
    fi
fi

MISSING=""
for v in R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_ENDPOINT_URL SUPABASE_URL SUPABASE_KEY; do
    val=$(get_env "$v")
    [ -z "$val" ] && MISSING="$MISSING\n    - $v"
done
if [ -n "$MISSING" ]; then
    echo -e "${YELLOW}  Cac bien sau chua duoc dien trong .env:${NC}"
    echo -e "$MISSING"
    fail "Dien day du .env roi chay lai script."
fi
ok "Tat ca bien bat buoc da co gia tri."


# ── 4. dbt profiles.yml ───────────────────────────────────────────────────────
step "4. Sinh ~/.dbt/profiles.yml tu .env..."

DBT_DIR="$HOME/.dbt"
PROFILE_PATH="$DBT_DIR/profiles.yml"
DB_PATH="$(pwd)/lakehouse.db"

R2_ENDPOINT=$(get_env "R2_ENDPOINT_URL" | sed 's|^https\?://||')
R2_KEY=$(get_env "R2_ACCESS_KEY_ID")
R2_SECRET=$(get_env "R2_SECRET_ACCESS_KEY")

mkdir -p "$DBT_DIR"

cat > "$PROFILE_PATH" <<EOF
supply_chain_dbt:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: $DB_PATH
      extensions:
        - httpfs
      settings:
        s3_endpoint: '$R2_ENDPOINT'
        s3_access_key_id: '$R2_KEY'
        s3_secret_access_key: '$R2_SECRET'
        s3_region: 'auto'
        s3_url_style: 'path'
EOF

ok "Da ghi $PROFILE_PATH"


# ── 5. Supabase tables ────────────────────────────────────────────────────────
step "5. Tao Supabase tables (idempotent)..."

SUPABASE_DB_URL=$(get_env "SUPABASE_DB_URL")
if [ -z "$SUPABASE_DB_URL" ]; then
    warn "SUPABASE_DB_URL chua co trong .env — bo qua (can cho MLflow)."
else
    "$PYTHON" - <<'PYEOF'
import os, sys
from dotenv import load_dotenv
load_dotenv()

url = os.getenv("SUPABASE_DB_URL", "")
if not url:
    print("    SUPABASE_DB_URL empty, skip.")
    sys.exit(0)

try:
    import psycopg2
except ImportError:
    print("    psycopg2 not installed, skip.")
    sys.exit(0)

sql = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY, run_type TEXT, status TEXT,
    started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ, error_message TEXT
);
CREATE TABLE IF NOT EXISTS ingestion_logs (
    id BIGSERIAL PRIMARY KEY, run_id TEXT, dataset_name TEXT,
    rows_ingested BIGINT, file_size_bytes BIGINT, r2_path TEXT, ingested_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS metadata_catalog (
    id BIGSERIAL PRIMARY KEY, layer TEXT, dataset_name TEXT, r2_path TEXT,
    row_count BIGINT, column_count INT, schema_json JSONB, updated_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS dataset_state (
    dataset_name TEXT PRIMARY KEY, file_hash TEXT, last_updated TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS dbt_run_logs (
    id BIGSERIAL PRIMARY KEY, run_id TEXT, layer TEXT, model_name TEXT,
    status TEXT, execution_time FLOAT, rows_affected BIGINT, logged_at TIMESTAMPTZ
);
"""

conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()
for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
    cur.execute(stmt)
conn.close()
print("    [OK] Tables created.")
PYEOF
fi


# ── 6. Download lakehouse.db + ML artifacts tu R2 ────────────────────────────
step "6. Download lakehouse.db + ML model tu R2..."

"$PYTHON" scripts/pull_lakehouse.py
pull_exit=$?

if [ "$pull_exit" -eq 2 ]; then
    warn "lakehouse.db chua co tren R2. Chay silver dbt de khoi tao lakehouse.db..."
    "$PYTHON" -m orchestration.pipeline --silver-only \
        || warn "Silver init that bai. Chay tay: python orchestration/pipeline.py --silver-only"
    ok "Silver VIEWs da duoc dang ky trong lakehouse.db"
elif [ "$pull_exit" -eq 0 ]; then
    ok "lakehouse.db + ML artifacts da duoc download"
else
    warn "pull_lakehouse.py that bai (exit $pull_exit). Kiem tra ket noi R2."
fi


# ── 7. Verify ─────────────────────────────────────────────────────────────────
step "7. Chay verify_system.py..."
"$PYTHON" scripts/verify_system.py


# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  SETUP HOAN TAT${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "  Chay pipeline lan dau (bronze -> silver -> gold):"
echo "    python orchestration/pipeline.py"
echo ""
echo "  Chay gold + train ML:"
echo "    python orchestration/pipeline.py --gold-only --with-ml"
echo ""
echo "  Sau khi train xong, push len R2 cho team:"
echo "    python scripts/push_lakehouse.py"
echo ""
echo "  Khoi dong MLflow server (terminal rieng):"
echo "    bash scripts/start_mlflow_server.sh"
echo ""
echo "  Khoi dong Data Portal:"
echo "    streamlit run data_portal/app.py"
echo ""
