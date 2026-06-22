# ============================================================
# Start MLflow Tracking Server — Option B
#   Backend store : Supabase PostgreSQL  ($env:SUPABASE_DB_URL)
#   Artifact store: Cloudflare R2        ($env:R2_* env vars)
#   UI             : http://localhost:5000
#
# Yeu cau:
#   pip install mlflow psycopg2-binary
#
# Them vao .env:
#   SUPABASE_DB_URL = postgresql://postgres.XXXXX:PASSWORD@host:5432/postgres
#   MLFLOW_TRACKING_URI = http://localhost:5000
# ============================================================

# Load .env neu co
$envFile = Join-Path $PSScriptRoot ".." ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
            $key   = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"').Trim("'")
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
    Write-Host "[+] Loaded .env"
}

# Validate bien moi truong bat buoc
$required = @("SUPABASE_DB_URL", "R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
foreach ($var in $required) {
    if (-not [System.Environment]::GetEnvironmentVariable($var)) {
        Write-Error "Missing env var: $var — check your .env file"
        exit 1
    }
}

# Expose R2 credentials cho MLflow artifact store (dung S3-compatible API)
$env:MLFLOW_S3_ENDPOINT_URL  = $env:R2_ENDPOINT_URL
$env:AWS_ACCESS_KEY_ID       = $env:R2_ACCESS_KEY_ID
$env:AWS_SECRET_ACCESS_KEY   = $env:R2_SECRET_ACCESS_KEY

$bucket       = if ($env:R2_BUCKET_NAME) { $env:R2_BUCKET_NAME } else { "supply-chain-ai-native" }
$artifactRoot = "s3://$bucket/mlflow/artifacts"
$backendUri   = $env:SUPABASE_DB_URL
$host_        = "0.0.0.0"
$port         = 5000

Write-Host ""
Write-Host "======================================================"
Write-Host " MLflow Tracking Server"
Write-Host "======================================================"
Write-Host " Backend  : Supabase PostgreSQL"
Write-Host " Artifacts: $artifactRoot"
Write-Host " URL      : http://localhost:$port"
Write-Host "======================================================"
Write-Host ""

mlflow server `
    --backend-store-uri  $backendUri `
    --default-artifact-root $artifactRoot `
    --host $host_ `
    --port $port
