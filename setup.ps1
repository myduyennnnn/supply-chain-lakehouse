# Supply Chain Lakehouse — Windows Setup (no venv, system Python)
# Chay: .\setup.ps1

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    [WARN] $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "    [FAIL] $msg" -ForegroundColor Red; exit 1 }

function Get-EnvValue($file, $key) {
    $line = Get-Content $file | Where-Object { $_ -match "^\s*${key}\s*=" } | Select-Object -First 1
    if ($line) { return ($line -split "=", 2)[1].Trim().Trim('"').Trim("'") }
    return ""
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Supply Chain Lakehouse — Setup"                             -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan


# ── 1. Python ────────────────────────────────────────────────────────────────
Write-Step "1. Kiem tra Python >= 3.11..."

$python = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            if ([int]$Matches[1] -gt 3 -or ([int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 11)) {
                $python = $cmd
                Write-Ok "$ver  ->  $((Get-Command $cmd).Source)"
                break
            }
        }
    } catch {}
}
if (-not $python) {
    Write-Fail "Python >= 3.11 khong tim thay. Tai tai https://www.python.org/downloads/ (chon 'Add to PATH')"
}


# ── 2. Dependencies ───────────────────────────────────────────────────────────
Write-Step "2. Cai dat dependencies (requirements.txt)..."

& $python -m pip install --upgrade pip --quiet
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Fail "pip install that bai." }
Write-Ok "Tat ca packages da duoc cai."


# ── 3. .env ───────────────────────────────────────────────────────────────────
Write-Step "3. Kiem tra file .env..."

if (Test-Path ".env") {
    Write-Ok ".env da ton tai."
} else {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Warn "Da sao chep .env.example -> .env"
        Write-Host ""
        Write-Host "  !!! QUAN TRONG: Mo file .env va dien credentials truoc khi tiep tuc:" -ForegroundColor Yellow
        Write-Host "        R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL"        -ForegroundColor Yellow
        Write-Host "        SUPABASE_URL, SUPABASE_KEY, SUPABASE_DB_URL"                    -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  Sau khi dien xong, chay lai: .\setup.ps1" -ForegroundColor Yellow
        exit 0
    } else {
        Write-Fail "Khong tim thay .env hoac .env.example"
    }
}

$missingVars = @()
foreach ($v in @("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT_URL", "SUPABASE_URL", "SUPABASE_KEY")) {
    if (-not (Get-EnvValue ".env" $v)) { $missingVars += $v }
}
if ($missingVars.Count -gt 0) {
    Write-Host "  Cac bien sau chua duoc dien trong .env:" -ForegroundColor Yellow
    foreach ($v in $missingVars) { Write-Host "    - $v" -ForegroundColor Yellow }
    Write-Fail "Dien day du .env roi chay lai script."
}
Write-Ok "Tat ca bien bat buoc da co gia tri."


# ── 4. dbt profiles.yml ───────────────────────────────────────────────────────
Write-Step "4. Sinh ~/.dbt/profiles.yml tu .env..."

$dbtDir      = Join-Path $env:USERPROFILE ".dbt"
$profilePath = Join-Path $dbtDir "profiles.yml"
$dbPath      = (Resolve-Path ".").Path + "\lakehouse.db"
$dbPath      = $dbPath.Replace("\", "/")

$r2Endpoint = (Get-EnvValue ".env" "R2_ENDPOINT_URL") -replace "^https?://", ""
$r2Key      = Get-EnvValue ".env" "R2_ACCESS_KEY_ID"
$r2Secret   = Get-EnvValue ".env" "R2_SECRET_ACCESS_KEY"

if (-not (Test-Path $dbtDir)) { New-Item -ItemType Directory -Path $dbtDir | Out-Null }

@"
supply_chain_dbt:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: $dbPath
      extensions:
        - httpfs
      settings:
        s3_endpoint: '$r2Endpoint'
        s3_access_key_id: '$r2Key'
        s3_secret_access_key: '$r2Secret'
        s3_region: 'auto'
        s3_url_style: 'path'
"@ | Out-File -FilePath $profilePath -Encoding utf8

Write-Ok "Da ghi $profilePath"


# ── 5. Supabase tables ────────────────────────────────────────────────────────
Write-Step "5. Tao Supabase tables (idempotent)..."

$supabaseDbUrl = Get-EnvValue ".env" "SUPABASE_DB_URL"
if (-not $supabaseDbUrl) {
    Write-Warn "SUPABASE_DB_URL chua co trong .env — bo qua (can cho MLflow)."
} else {
    $tmpSql = Join-Path $env:TEMP "sc_init.sql"
    @"
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
"@ | Out-File -FilePath $tmpSql -Encoding utf8

    @"
import psycopg2, sys
sql = open(r'$tmpSql', encoding='utf-8').read()
conn = psycopg2.connect('$supabaseDbUrl')
conn.autocommit = True
cur = conn.cursor()
for stmt in [s.strip() for s in sql.split(';') if s.strip()]:
    cur.execute(stmt)
conn.close()
print('    [OK] Tables created.')
"@ | & $python -
    if ($LASTEXITCODE -ne 0) { Write-Warn "Tao Supabase tables that bai (co the da ton tai)." }
    Remove-Item $tmpSql -ErrorAction SilentlyContinue
}


# ── 6. Download lakehouse.db + ML artifacts tu R2 ────────────────────────────
Write-Step "6. Download lakehouse.db + ML model tu R2..."

& $python scripts/pull_lakehouse.py
$pullExit = $LASTEXITCODE

if ($pullExit -eq 2) {
    Write-Warn "lakehouse.db chua co tren R2. Chay silver dbt de khoi tao..."
    & $python -m orchestration.pipeline --silver-only
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Silver init that bai. Chay tay: python orchestration/pipeline.py --silver-only"
    } else {
        Write-Ok "Silver VIEWs da duoc dang ky trong lakehouse.db"
    }
} elseif ($pullExit -eq 0) {
    Write-Ok "lakehouse.db + ML artifacts da duoc download"
} else {
    Write-Warn "pull_lakehouse.py that bai (exit $pullExit). Kiem tra ket noi R2."
}


# ── 7. Verify ─────────────────────────────────────────────────────────────────
Write-Step "7. Chay verify_system.py..."
& $python scripts/verify_system.py


# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  SETUP HOAN TAT"                                             -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Chay pipeline lan dau (bronze -> silver -> gold):" -ForegroundColor White
Write-Host "    python orchestration/pipeline.py"
Write-Host ""
Write-Host "  Chay gold + train ML:" -ForegroundColor White
Write-Host "    python orchestration/pipeline.py --gold-only --with-ml"
Write-Host ""
Write-Host "  Sau khi train xong, push len R2 cho team:" -ForegroundColor White
Write-Host "    python scripts/push_lakehouse.py"
Write-Host ""
Write-Host "  Khoi dong MLflow server (terminal rieng):" -ForegroundColor White
Write-Host "    .\scripts\start_mlflow_server.ps1"
Write-Host ""
Write-Host "  Khoi dong Data Portal:" -ForegroundColor White
Write-Host "    streamlit run data_portal/app.py"
Write-Host ""
