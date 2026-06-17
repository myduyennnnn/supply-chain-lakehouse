# Supply Chain Lakehouse - Windows Setup Script
# Chay: .\setup.ps1

$ErrorActionPreference = "Stop"
$PYTHON_MIN = "3.10"
$VENV_DIR = ".venv"

function Write-Step($msg) { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "    [FAIL] $msg" -ForegroundColor Red; exit 1 }

# ── 1. Kiem tra Python ────────────────────────────────────────────────────────
Write-Step "Kiem tra Python..."

$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10)) {
                $pythonCmd = $cmd
                Write-Ok "$ver da duoc cai dat ($cmd)"
                break
            }
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Host @"

    Python >= $PYTHON_MIN chua duoc cai dat hoac khong tim thay trong PATH.
    Tai Python tai: https://www.python.org/downloads/
    Chon "Add Python to PATH" khi cai dat.

"@ -ForegroundColor Yellow
    Write-Fail "Vui long cai Python >= $PYTHON_MIN roi chay lai script nay."
}

# ── 2. Tao virtual environment ────────────────────────────────────────────────
Write-Step "Tao virtual environment ($VENV_DIR)..."

if (Test-Path $VENV_DIR) {
    Write-Ok "Virtual environment da ton tai, bo qua."
} else {
    & $pythonCmd -m venv $VENV_DIR
    Write-Ok "Virtual environment da duoc tao."
}

# ── 3. Kich hoat venv ─────────────────────────────────────────────────────────
Write-Step "Kich hoat virtual environment..."

$activateScript = Join-Path $VENV_DIR "Scripts\Activate.ps1"
if (-not (Test-Path $activateScript)) {
    Write-Fail "Khong tim thay $activateScript. Tao lai venv."
}

& $activateScript
Write-Ok "Virtual environment da kich hoat."

# ── 4. Nang cap pip ───────────────────────────────────────────────────────────
Write-Step "Nang cap pip..."
& python -m pip install --upgrade pip --quiet
Write-Ok "pip da duoc nang cap."

# ── 5. Cai dependencies ───────────────────────────────────────────────────────
Write-Step "Cai dat dependencies tu requirements.txt..."

if (-not (Test-Path "requirements.txt")) {
    Write-Fail "Khong tim thay requirements.txt."
}

& pip install -r requirements.txt
Write-Ok "Tat ca dependencies da duoc cai dat."

# ── 6. Cau hinh .env ──────────────────────────────────────────────────────────
Write-Step "Kiem tra file .env..."

if (Test-Path ".env") {
    Write-Ok ".env da ton tai."
} else {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host @"

    [CANH BAO] Da tao .env tu .env.example.
    Vui long mo file .env va dien day du thong tin credentials:
      - R2_ACCESS_KEY_ID
      - R2_SECRET_ACCESS_KEY
      - SUPABASE_KEY
      - ...

"@ -ForegroundColor Yellow
    } else {
        Write-Host "    [CANH BAO] Khong tim thay .env.example. Tao .env thu cong." -ForegroundColor Yellow
    }
}

# ── 7. Ket qua ────────────────────────────────────────────────────────────────
Write-Host @"

============================================================
  SETUP HOAN TAT
============================================================
  De kich hoat venv lan sau:
    .\.venv\Scripts\Activate.ps1

  De chay bronze ingestion:
    python -m ingestion.main

  Nho dien credentials vao file .env truoc khi chay.
============================================================

"@ -ForegroundColor Green
