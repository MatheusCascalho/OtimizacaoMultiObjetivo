#!/usr/bin/env bash
# Build the NeuroLKH SWIG extension with Python 3.11.
#
# Upstream setup.sh runs "python3", which on this project is 3.12. The SWIG
# wrapper uses C-API macros removed in 3.12, so this script follows the same
# steps as setup.sh (swig -python LKH.i, then setup.py build_ext) with the
# Python 3.11 interpreter. It also applies the ParetoLab explicit-cost patch
# before compiling. The real layout is third_party/NeuroLKH/SRC_swig, not
# LKH-3.0.6.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NL="${ROOT}/third_party/NeuroLKH"
PY="${NL}/.venv/bin/python"

if [[ ! -x "${PY}" ]]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PY="$(command -v python3.11)"
  else
    echo "python3.11 is required to compile the NeuroLKH SWIG extension" >&2
    exit 1
  fi
fi

if [[ ! -d "${NL}/SRC_swig" ]]; then
  echo "NeuroLKH checkout not found at ${NL}" >&2
  exit 1
fi

export PATH="${NL}/.venv/bin:${PATH}"
if ! command -v swig >/dev/null 2>&1; then
  "${PY}" -m pip install swig
fi

"${PY}" "${ROOT}/scripts/neurolkh/apply_paretolab_lkh_patch.py" "${NL}"

cd "${NL}/SRC_swig"
swig -python LKH.i
"${PY}" setup.py build_ext
cd "${NL}"
shopt -s nullglob
objects=(SRC_swig/build/lib.*/_LKH*.so)
if [[ ${#objects[@]} -eq 0 ]]; then
  echo "SWIG build finished without an _LKH extension" >&2
  exit 1
fi
cp "${objects[@]}" "${NL}/"
cp "${objects[@]}" "${NL}/SRC_swig/"
echo "NeuroLKH SWIG extension built with ${PY}"
