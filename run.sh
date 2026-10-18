#!/usr/bin/env bash
# ClaimGuard helper.  Usage: ./run.sh setup | train | dashboard | api | stream | test
set -euo pipefail
cd "$(dirname "$0")"

PY=.venv/bin/python
if [[ "$(uname)" == "Darwin" ]]; then
  # XGBoost needs OpenMP on macOS. Use Homebrew's libomp if present, else the copy bundled with scikit-learn.
  if [[ ! -f /opt/homebrew/opt/libomp/lib/libomp.dylib && ! -f /usr/local/opt/libomp/lib/libomp.dylib ]]; then
    OMP_DIR=$(ls -d .venv/lib/python3*/site-packages/sklearn/.dylibs 2>/dev/null | head -1 || true)
    [[ -n "${OMP_DIR}" ]] && export DYLD_LIBRARY_PATH="$PWD/${OMP_DIR}${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
  fi
fi

case "${1:-}" in
  setup)
    if command -v uv >/dev/null; then uv venv --python 3.11 .venv && uv pip install --python $PY -r requirements.txt
    else python3 -m venv .venv && $PY -m pip install -r requirements.txt; fi ;;
  train)     $PY -m claimguard.train "${@:2}" ;;
  dashboard) $PY -m streamlit run dashboard/app.py "${@:2}" ;;
  api)       $PY -m uvicorn claimguard.api:app --port 8000 "${@:2}" ;;
  stream)    $PY -m claimguard.stream "${@:2}" ;;
  test)      $PY -m pytest -q tests ;;
  *) echo "usage: ./run.sh setup | train | dashboard | api | stream | test"; exit 1 ;;
esac
