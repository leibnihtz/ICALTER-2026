# leibtimeter-learning-analytics

Reproducible statistical analysis pipeline for the ICALTER 2026 LeibtiMeter learning analytics study.

This repository contains the reproducible analysis for a Learning Analytics study of response time and answer correctness across classroom question formats. The pipeline validates the classroom-response dataset, generates descriptive tables and figures, fits mixed-effects logistic models in R, runs robustness checks, and produces machine-readable summaries plus human-readable validation reports.

## Input

Place the raw dataset at:

```text
data/leibtimeter_paper_base.csv
```

The public dataset is:

```text
data/leibtimeter_public.csv
```

Identifiers are synthetic. Direct identifying attributes are excluded, exact timestamps are excluded, and analytical variables are preserved exactly. The public dataset is validated against the private analysis sample to confirm that it reproduces the primary statistical model.

The private dataset name `data/leibtimeter_paper_base.csv` is ignored by Git and should not be published.

## Reproduce

On Unix-like systems with Bash:

```bash
bash run_analysis.sh
```

On Windows PowerShell:

```powershell
.\run_analysis.ps1
```

Python dependencies are listed in `requirements.txt`. R scripts require `lme4`, `broom.mixed`, `dplyr`, `readr`, `tidyr`, `ggplot2`, and `scales`.

## Main Model

```text
correct ~ z_log_response_time * question_type
          + course
          + (1 | student_id)
          + (1 | question_id)
```

## Outputs

Key review artifacts are generated under `outputs/`:

- `outputs/VALIDATION_REPORT_V2.md`
- `outputs/PUBLIC_DATASET_VALIDATION.md`
- `outputs/results_summary_v2.json`
- `outputs/public_dataset_validation.json`
- `outputs/tables/table_descriptive.csv`
- `outputs/tables/question_level_diagnostics.csv`
- `outputs/models/M2_coefficients.csv`
- `outputs/models/M3_coefficients.csv`
- `outputs/models/model_diagnostics.csv`
- `outputs/models/M1_vs_M2_lrt.csv`
- `outputs/models/M2_vs_M3_lrt.csv`
- `outputs/models/M2_predicted_probabilities_v2.csv`
- `outputs/figures/fig3_predicted_correctness_v2.pdf`
- `outputs/figures/fig4_accuracy_by_time_band.pdf`

## Scientific Guardrails

This is an observational learning analytics analysis. The pipeline reports associations, not causal effects. It does not remove slow responses from the primary analysis solely because they are outliers, and it keeps timestamp anomalies documented rather than silently deleting them.

## Privacy

The public dataset contains no names, student codes, emails, IP addresses, device metadata, original internal UUIDs, original hashed student identifiers, or exact interaction timestamps.

`outputs/results_summary_v2.json` is the machine-readable frozen result set used to verify numerical values reported in the manuscript.
