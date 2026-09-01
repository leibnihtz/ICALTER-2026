$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -ge 7) {
  $PSNativeCommandUseErrorActionPreference = $true
}
Set-Location $PSScriptRoot

$python = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } elseif (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
$defaultRscript = "C:\Program Files\R\R-4.6.1\bin\Rscript.exe"
$rscript = if ($env:RSCRIPT_BIN) { $env:RSCRIPT_BIN } elseif (Get-Command Rscript -ErrorAction SilentlyContinue) { "Rscript" } elseif (Test-Path $defaultRscript) { $defaultRscript } else { $null }
$env:R_LIBS_USER = if ($env:R_LIBS_USER) { $env:R_LIBS_USER } else { Join-Path $PSScriptRoot ".r-lib" }
New-Item -ItemType Directory -Force -Path $env:R_LIBS_USER | Out-Null

New-Item -ItemType Directory -Force -Path outputs/tables, outputs/figures, outputs/models, outputs/validation | Out-Null

& $python src/01_validate_data.py
& $python src/07_create_public_dataset.py
& $python src/02_descriptive_analysis.py
& $python src/03_response_time_analysis.py
& $python src/07_spec2_descriptive.py

if (-not $rscript) {
  throw "Rscript was not found. Install R or set RSCRIPT_BIN to the full path of Rscript.exe, then rerun this script."
}

& $rscript src/04_glmm_models.R
& $rscript src/05_robustness.R
& $rscript src/08_spec2_models.R
& $python src/06_generate_outputs.py
& $python src/09_spec2_report.py
& $python src/10_sanitize_public_outputs.py

Write-Host "Analysis complete. See outputs/VALIDATION_REPORT.md"
