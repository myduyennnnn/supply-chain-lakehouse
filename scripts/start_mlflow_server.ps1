# Load .env neu co
$envFile = Join-Path (Split-Path $PSScriptRoot -Parent) ".env"
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

$required = @("SUPABASE_DB_URL", "R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
foreach ($var in $required) {
    if (-not [System.Environment]::GetEnvironmentVariable($var)) {
        Write-Error "Missing env var: $var - check your .env file"
        exit 1
    }
}

$env:MLFLOW_S3_ENDPOINT_URL = $env:R2_ENDPOINT_URL
$env:AWS_ACCESS_KEY_ID      = $env:R2_ACCESS_KEY_ID
$env:AWS_SECRET_ACCESS_KEY  = $env:R2_SECRET_ACCESS_KEY

$bucket       = if ($env:R2_BUCKET_NAME) { $env:R2_BUCKET_NAME } else { "supply-chain-ai-native" }
$artifactRoot = "s3://$bucket/mlflow/artifacts"
$backendUri   = $env:SUPABASE_DB_URL

mlflow server `
    --backend-store-uri     $backendUri `
    --default-artifact-root $artifactRoot `
    --host                  0.0.0.0 `
    --port                  5000