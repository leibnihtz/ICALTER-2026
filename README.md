# leibtimeter-learning-analytics

Reproducible statistical analysis pipeline for the ICALTER 2026 LeibtiMeter learning analytics study.

This repository contains the reproducible analysis for a Learning Analytics study of response time and answer correctness across classroom question formats. The pipeline validates the classroom-response dataset, generates descriptive tables and figures, fits mixed-effects logistic models in R, runs robustness checks, and produces machine-readable summaries plus human-readable validation reports.

## ICALTER 2026 paper (v3) — start here

The submitted paper uses **v3**: two terms (2026-1 + 2026-2), two courses (Big Data, Networks II), and concept-level analyses. The frozen version is the tag **`v3.0-paper-freeze`**.

| What | File |
|---|---|
| Analysis plan, committed before any v3 model was fitted | `ANALYSIS_PLAN_v3.md` (commit `0e9131c`) |
| All reported numbers (machine-readable, written by script) | `outputs/results_summary_v3.json` |
| Human-readable results: models, tests, n, robustness | `REPORT_icalter_v3.md` |
| Public dataset (3,227 rows; analysis set = `key_excluded == 0`, 3,109 rows) | `data/public_v3/leibtimeter_public_v3.csv` |
| Figures | `figures/fig1_accuracy_rt_bands_v3.pdf`, `figures/fig2_predicted_m2_v3.pdf` |
| Instrument and data audit (Part A) | `audit/icalter_v3_facts.json`, `audit/a8_reproduce_v2.json` |

### Reproduce the main v3 results from the public dataset

```bash
Rscript src/18_v3_reproduce_from_public.R
```

It fits M1, M2 (primary) and M4 on the public dataset and checks them against `outputs/results_summary_v3.json` (expected output: `Matches results_summary_v3.json: TRUE`). Requires R with `lme4`, `dplyr`, `readr`, `jsonlite`.

Primary model (M2):

```text
correct ~ z_log_rt * question_type + course + term + (1 | student_id) + (1 | question_id)
z_log_rt = scale(log(1 + response_time_seconds)), reference format = SingleChoice
```

M4 adds `(1 | concept_id)`; M5 adds `(1 + z_log_rt | concept_id)`.

### Public v3 dataset

| Variable | Description |
|---|---|
| student_id, session_id, run_id, question_id, concept_id | Synthetic identifiers with no external meaning |
| course, term | Course (BIG DATA, REDES II) and academic term (2026-1, 2026-2) |
| question_type | SingleChoice, TrueFalse, or MultipleChoice |
| response_time_seconds | Server-side time from question opening to submission |
| is_correct | Correctness as scored by the platform at submission time |
| key_excluded | 1 = question excluded for an answer-key error (ANALYSIS_PLAN_v3.md §2.3); kept for the uncorrected-label robustness check |

No names, student codes, emails, IP addresses, device data, internal identifiers, exact timestamps or free text are included. The private pipeline (`src/11`–`src/17`) runs on a pseudonymized production extract that is not published; `src/16_v3_validate_public.R` confirmed that the public dataset reproduces M2 and M4 with Δ = 0 (`outputs/v3/public_validation.json`).

## v2 pipeline (earlier draft, 2026-1 only)

The sections below document the v2 pipeline. `outputs/results_summary_v2.json` is kept unchanged; `audit/a8_reproduce_v2.json` shows that it is reproduced exactly.

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
