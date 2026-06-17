#!/usr/bin/env bash
# Supply Chain Lakehouse - Linux/macOS Setup Script
# Chay: bash setup.sh

set -e

PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=10
VENV_DIR=".venv"

GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"

step()  { echo -e "\n${CYAN}>>> $1${NC}"; }
ok()    { echo -e "    ${GREEN}[OK] $1${NC}"; }
warn()  { echo -e "    ${YELLOW}[CANH BAO] $1${NC}"; }
fail()  { echo -e "    ${RED}[FAIL] $1${NC}"; exit 1; }

# ── 1. Kiem tra Python ────────────────────────────────────────────────────────
step "Kiem tra Python..."

PYTHON_CMD=""
for cmd in python3 python python3.12 python3.11 python3.10; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+')
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -gt "$PYTHON_MIN_MAJOR" ] || \
           ([ "$major" -eq "$PYTHON_MIN_MAJOR" ] && [ "$minor" -ge "$PYTHON_MIN_MINOR" ]); then
            PYTHON_CMD="$cmd"
            ok "$(${cmd} --version) da duoc cai dat ($cmd)"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo ""
    warn "Python >= ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR} chua duoc cai dat."
    echo "    Ubuntu/Debian : sudo apt install python3.11"
    echo "    macOS (brew)  : brew install python@3.11"
    echo "    Python.org    : https://www.python.org/downloads/"
    echo ""
    fail "Vui long cai Python >= ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR} roi chay lai."
fi

# ── 2. Tao virtual environment ────────────────────────────────────────────────
step "Tao virtual environment ($VENV_DIR)..."

if [ -d "$VENV_DIR" ]; then
    ok "Virtual environment da ton tai, bo qua."
else
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    ok "Virtual environment da duoc tao."
fi

# ── 3. Kich hoat venv ─────────────────────────────────────────────────────────
step "Kich hoat virtual environment..."
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"
ok "Virtual environment da kich hoat."

# ── 4. Nang cap pip ───────────────────────────────────────────────────────────
step "Nang cap pip..."
pip install --upgrade pip --quiet
ok "pip da duoc nang cap."

# ── 5. Cai dependencies ───────────────────────────────────────────────────────
step "Cai dat dependencies tu requirements.txt..."

if [ ! -f "requirements.txt" ]; then
    fail "Khong tim thay requirements.txt."
fi

pip install -r requirements.txt
ok "Tat ca dependencies da duoc cai dat."

# ── 6. Cau hinh .env ──────────────────────────────────────────────────────────
step "Kiem tra file .env..."

if [ -f ".env" ]; then
    ok ".env da ton tai."
else
    if [ -f ".env.example" ]; then
        cp .env.example .env
        warn "Da tao .env tu .env.example."
        echo "    Vui long mo file .env va dien day du thong tin credentials:"
        echo "      - R2_ACCESS_KEY_ID"
        echo "      - R2_SECRET_ACCESS_KEY"
        echo "      - SUPABASE_KEY"
        echo "      - ..."
    else
        warn "Khong tim thay .env.example. Tao file .env thu cong."
    fi
fi

# ── 7. Ket qua ────────────────────────────────────────────────────────────────
echo -e "
${GREEN}============================================================
  SETUP HOAN TAT
============================================================${NC}
  De kich hoat venv lan sau:
    source .venv/bin/activate

  De chay bronze ingestion:
    python -m ingestion.main

  Nho dien credentials vao file .env truoc khi chay.
${GREEN}============================================================${NC}
"
