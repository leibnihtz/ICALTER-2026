#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python}"
RSCRIPT_BIN="${RSCRIPT_BIN:-Rscript}"
export R_LIBS_USER="${R_LIBS_USER:-$(pwd)/.r-lib}"

mkdir -p outputs/tables outputs/figures outputs/models outputs/validation

"$PYTHON_BIN" src/01_validate_data.py
"$PYTHON_BIN" src/07_create_public_dataset.py
"$PYTHON_BIN" src/02_descriptive_analysis.py
"$PYTHON_BIN" src/03_response_time_analysis.py
"$PYTHON_BIN" src/07_spec2_descriptive.py
"$RSCRIPT_BIN" src/04_glmm_models.R
"$RSCRIPT_BIN" src/05_robustness.R
"$RSCRIPT_BIN" src/08_spec2_models.R
"$PYTHON_BIN" src/06_generate_outputs.py
"$PYTHON_BIN" src/09_spec2_report.py
"$PYTHON_BIN" src/10_sanitize_public_outputs.py

echo "Analysis complete. See outputs/VALIDATION_REPORT.md"
