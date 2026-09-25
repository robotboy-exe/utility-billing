#!/usr/bin/env bash
#
# setup-env.sh — Bootstrap the local Python environment for this repo.
#
# Why this script exists (Termux/Android):
#   pip's platform tag here is "android-24-arm64_v8a", so pypi binary wheels
#   (ruff, psycopg-binary, maturin, etc.) do NOT resolve to prebuilt wheels and
#   pip falls back to source builds that need Rust/GCC toolchains. Configured:
#     - Core test deps (sqlalchemy, alembic, pytest, pytest-sqlalchemy) are
#       pure-Python or build cleanly with gcc  -> installed via pip.
#     - ruff is a native Termux package         -> installed via apt.
#     - mypy/pre-commit pull Rust-backed deps (librt, ast-serialize) that stall
#       on this device; they are dev-only extras and are SKIPPED here.
#     - psycopg (PostgreSQL) is only needed for prod/CI validation, not the
#       local SQLite-only pass -> not installed locally.
#
# It is idempotent: safe to run on every fresh clone.
#
# Usage:
#   bash scripts/setup-env.sh          # create .venv + install deps
#   PIP_INDEX_URL=... bash scripts/setup-env.sh   # override mirror

set -euo pipefail

REPO_ROOT="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv"
PYTHON_BIN="${PYTHON:-python3}"

# Optional mirror override (defaults to aliyun; faster/more reliable on this network).
PIP_INDEX_URL="${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"

# Packages that build cleanly here (pure-python or gcc-buildable).
CORE_DEPS=(
  "sqlalchemy>=2.0,<3.0"
  "alembic>=1.13,<2.0"
  "pytest>=7.0,<9.0"
  "pytest-sqlalchemy>=0.2.0"
)

echo "==> repo: $REPO_ROOT"

# 1. Create the venv (in-project; project lives in Termux private fs, no
#    shared-storage lib64 permission issue).
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "==> creating venv at $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
else
  echo "==> venv already exists"
fi

# 2. Fast path: if the core deps already import, skip all network work.
if "$VENV_DIR/bin/python" -c 'import sqlalchemy, alembic, pytest, pytest_sqlalchemy' >/dev/null 2>&1; then
  echo "==> core deps already present; skipping install"
else
  echo "==> installing core deps via pip (index: $PIP_INDEX_URL)"
  "$VENV_DIR/bin/pip" install \
    --index-url "$PIP_INDEX_URL" \
    --timeout 120 \
    --retries 20 \
    "${CORE_DEPS[@]}"
fi

# 3. ruff is a native Termux package (not pip-installable on this platform).
if ! command -v ruff >/dev/null 2>&1; then
  echo "==> installing ruff via apt (Termux native)"
  apt install -y ruff
else
  echo "==> ruff already present: $(command -v ruff)"
fi

# 4. Write .python-version from the interpreter actually in use (pyenv/uv etc.
#    will otherwise try to locate a version that doesn't exist here).
"$VENV_DIR/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' > "$REPO_ROOT/.python-version"
echo "==> .python-version -> $(cat "$REPO_ROOT/.python-version")"

echo
echo "==> Done. Activate with:  source $VENV_DIR/bin/activate"
echo "==> Verify:  $VENV_DIR/bin/python -c 'import sqlalchemy, pytest'"