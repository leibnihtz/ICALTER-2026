from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

from common import DATA_PATH, MODELS, OUTPUTS, ROOT, VALIDATION, add_derived_variables, ensure_dirs, load_raw_data


PUBLIC_DATA_PATH = ROOT / "data" / "leibtimeter_public.csv"
VALIDATION_JSON = OUTPUTS / "public_dataset_validation.json"
VALIDATION_MD = OUTPUTS / "PUBLIC_DATASET_VALIDATION.md"

PUBLIC_COLUMNS = [
    "student_id",
    "course",
    "session_id",
    "question_id",
    "question_type",
    "response_time_seconds",
    "is_correct",
]

FORBIDDEN_COLUMNS = {
    "student_id_hash",
    "course_code",
    "term",
    "session_title",
    "session_started_at",
    "opened_at",
    "closed_at",
    "submitted_at",
    "difficulty_level",
    "time_limit_seconds",
    "normalized_response_time",
    "has_correct_answer",
    "question_run_id",
    "display_order",
}


def stable_id_map(values: pd.Series, prefix: str) -> dict[str, str]:
    unique = sorted(values.dropna().astype(str).unique())
    width = max(3, len(str(len(unique))))
    return {value: f"{prefix}_{i:0{width}d}" for i, value in enumerate(unique, start=1)}


def bool_to_public(value) -> int:
    text = str(value).strip().lower()
    if text in {"t", "true", "1", "yes"}:
        return 1
    if text in {"f", "false", "0", "no"}:
        return 0
    raise ValueError(f"Unexpected is_correct value: {value}")


def create_public_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = load_raw_data()
    df = add_derived_variables(raw)
    private = df[df["timestamp_valid"] & df["correct"].notna() & df["response_time_seconds"].notna()].copy()

    student_map = stable_id_map(private["student_id_hash"], "student")
    question_map = stable_id_map(private["question_id"], "question")
    session_map = stable_id_map(private["session_id"], "session")

    public = pd.DataFrame(
        {
            "student_id": private["student_id_hash"].astype(str).map(student_map),
            "course": private["course"],
            "session_id": private["session_id"].astype(str).map(session_map),
            "question_id": private["question_id"].astype(str).map(question_map),
            "question_type": private["question_type"],
            "response_time_seconds": private["response_time_seconds"],
            "is_correct": private["is_correct"].map(bool_to_public),
        }
    )

    if public[PUBLIC_COLUMNS].isna().any().any():
        missing = public.columns[public.isna().any()].tolist()
        raise ValueError(f"Public dataset contains missing values in required columns: {missing}")

    PUBLIC_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    public[PUBLIC_COLUMNS].to_csv(PUBLIC_DATA_PATH, index=False)
    return private, public


def find_rscript() -> str:
    candidates = [
        os.environ.get("RSCRIPT_BIN"),
        shutil.which("Rscript"),
        r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe",
        r"C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise FileNotFoundError("Rscript was not found. Set RSCRIPT_BIN to Rscript.exe.")


def run_model_validation() -> dict:
    r_code = r'''
args <- commandArgs(trailingOnly = TRUE)
root <- args[[1]]
if (nzchar(Sys.getenv("R_LIBS_USER"))) {
  .libPaths(c(Sys.getenv("R_LIBS_USER"), .libPaths()))
}
required <- c("lme4", "readr", "dplyr")
missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing) > 0) stop(paste("Missing packages:", paste(missing, collapse = ", ")))
library(lme4)
library(readr)
library(dplyr)

fit_glmm <- function(formula, data) {
  glmer(
    formula,
    data = data,
    family = binomial(link = "logit"),
    control = glmerControl(optimizer = "bobyqa", optCtrl = list(maxfun = 2e5))
  )
}

private <- read_csv(file.path(root, "outputs", "validation", "analysis_dataset.csv"), show_col_types = FALSE) %>%
  mutate(
    correct = as.integer(correct),
    timestamp_valid = as.logical(timestamp_valid),
    course = factor(course),
    question_type = relevel(factor(question_type), ref = "SingleChoice"),
    student_id = factor(student_id_hash),
    question_id = factor(question_id)
  ) %>%
  filter(timestamp_valid, !is.na(correct), !is.na(response_time_seconds)) %>%
  mutate(
    log_response_time = log1p(response_time_seconds),
    z_log_response_time = as.numeric(scale(log_response_time))
  )

public <- read_csv(file.path(root, "data", "leibtimeter_public.csv"), show_col_types = FALSE) %>%
  mutate(
    correct = as.integer(is_correct),
    course = factor(course, levels = levels(private$course)),
    question_type = relevel(factor(question_type, levels = levels(private$question_type)), ref = "SingleChoice"),
    student_id = factor(student_id),
    question_id = factor(question_id),
    log_response_time = log1p(response_time_seconds),
    z_log_response_time = (log_response_time - mean(log_response_time)) / sd(log_response_time)
  )

private_model <- fit_glmm(
  correct ~ z_log_response_time * question_type + course + (1 | student_id) + (1 | question_id),
  private
)
public_model <- fit_glmm(
  correct ~ z_log_response_time * question_type + course + (1 | student_id) + (1 | question_id),
  public
)

coef_diff <- fixef(private_model) - fixef(public_model)[names(fixef(private_model))]
out <- data.frame(
  private_rows = nrow(private),
  public_rows = nrow(public),
  private_students = dplyr::n_distinct(private$student_id),
  public_students = dplyr::n_distinct(public$student_id),
  private_questions = dplyr::n_distinct(private$question_id),
  public_questions = dplyr::n_distinct(public$question_id),
  private_sessions = dplyr::n_distinct(private$session_id),
  public_sessions = dplyr::n_distinct(public$session_id),
  max_abs_coefficient_difference = max(abs(coef_diff)),
  aic_difference = abs(AIC(private_model) - AIC(public_model)),
  loglik_difference = abs(as.numeric(logLik(private_model)) - as.numeric(logLik(public_model))),
  private_aic = AIC(private_model),
  public_aic = AIC(public_model),
  private_loglik = as.numeric(logLik(private_model)),
  public_loglik = as.numeric(logLik(public_model)),
  private_nobs = nobs(private_model),
  public_nobs = nobs(public_model)
)
cat(jsonlite::toJSON(out, dataframe = "rows", auto_unbox = TRUE, digits = 16))
'''
    rscript = find_rscript()
    env = os.environ.copy()
    env["R_LIBS_USER"] = env.get("R_LIBS_USER", str(ROOT / ".r-lib"))
    with tempfile.NamedTemporaryFile("w", suffix=".R", delete=False, encoding="utf-8") as tmp:
        tmp.write(r_code)
        script_path = tmp.name
    try:
        result = subprocess.run(
            [rscript, script_path, str(ROOT)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
    finally:
        Path(script_path).unlink(missing_ok=True)

    match = re.search(r"\{.*\}", result.stdout, flags=re.S)
    if not match:
        raise RuntimeError(f"Could not parse R validation JSON.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return json.loads(match.group(0))


def validate_public_columns(public: pd.DataFrame) -> dict:
    columns = set(public.columns)
    direct_identifiers_absent = not bool(columns & FORBIDDEN_COLUMNS)
    timestamps_absent = not any("time" in col.lower() and col != "response_time_seconds" for col in public.columns)

    joined_text = "\n".join(public.astype(str).agg(",".join, axis=1).head(200).tolist())
    uuid_like = bool(re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", joined_text, re.I))
    email_like = bool(re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", joined_text))
    ip_like = bool(re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", joined_text))

    return {
        "allowed_columns_only": list(public.columns) == PUBLIC_COLUMNS,
        "direct_identifiers_absent": direct_identifiers_absent,
        "timestamps_absent": timestamps_absent,
        "uuid_like_values_absent": not uuid_like,
        "email_like_values_absent": not email_like,
        "ip_like_values_absent": not ip_like,
    }


def write_reports(private: pd.DataFrame, public: pd.DataFrame, model_validation: dict, privacy: dict) -> None:
    checks = {
        "rows_match": model_validation["private_rows"] == model_validation["public_rows"] == len(public),
        "students_match": model_validation["private_students"] == model_validation["public_students"],
        "questions_match": model_validation["private_questions"] == model_validation["public_questions"],
        "sessions_match": model_validation["private_sessions"] == model_validation["public_sessions"],
        "coefficients_match": model_validation["max_abs_coefficient_difference"] < 1e-10,
        "aic_matches": model_validation["aic_difference"] < 1e-10,
        "loglik_matches": model_validation["loglik_difference"] < 1e-10,
        **privacy,
    }
    reproduces = all(checks.values())

    payload = {
        "private_rows": model_validation["private_rows"],
        "public_rows": model_validation["public_rows"],
        "private_students": model_validation["private_students"],
        "public_students": model_validation["public_students"],
        "private_questions": model_validation["private_questions"],
        "public_questions": model_validation["public_questions"],
        "max_abs_coefficient_difference": model_validation["max_abs_coefficient_difference"],
        "aic_difference": model_validation["aic_difference"],
        "loglik_difference": model_validation["loglik_difference"],
        "reproduces_primary_model": reproduces,
        "checks": checks,
    }
    with open(VALIDATION_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    status = "PASS" if reproduces else "FAIL"
    lines = [
        "# Public Dataset Validation",
        "",
        "## Dataset Size",
        "",
        f"- Private analysis rows: {model_validation['private_rows']}",
        f"- Public rows: {model_validation['public_rows']}",
        f"- Private students: {model_validation['private_students']}",
        f"- Public students: {model_validation['public_students']}",
        f"- Private questions: {model_validation['private_questions']}",
        f"- Public questions: {model_validation['public_questions']}",
        f"- Private sessions: {model_validation['private_sessions']}",
        f"- Public sessions: {model_validation['public_sessions']}",
        "",
        "## Privacy Checks",
        "",
        f"- Only allowed public columns: {privacy['allowed_columns_only']}",
        f"- Direct identifiers absent: {privacy['direct_identifiers_absent']}",
        f"- Exact timestamps absent: {privacy['timestamps_absent']}",
        f"- UUID-like values absent: {privacy['uuid_like_values_absent']}",
        f"- Email-like values absent: {privacy['email_like_values_absent']}",
        f"- IP-like values absent: {privacy['ip_like_values_absent']}",
        "",
        "## Primary Model Reproduction",
        "",
        "Model: `correct ~ z_log_response_time * question_type + course + (1 | student_id) + (1 | question_id)`",
        "",
        f"- Maximum absolute fixed-effect coefficient difference: {model_validation['max_abs_coefficient_difference']:.16g}",
        f"- AIC difference: {model_validation['aic_difference']:.16g}",
        f"- Log-likelihood difference: {model_validation['loglik_difference']:.16g}",
        f"- Private AIC: {model_validation['private_aic']:.16g}",
        f"- Public AIC: {model_validation['public_aic']:.16g}",
        f"- Private logLik: {model_validation['private_loglik']:.16g}",
        f"- Public logLik: {model_validation['public_loglik']:.16g}",
        "",
        f"Public dataset reproduces the reported primary analysis: {status}",
    ]
    with open(VALIDATION_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    ensure_dirs()
    private, public = create_public_dataset()

    if not (VALIDATION / "analysis_dataset.csv").exists():
        private.to_csv(VALIDATION / "analysis_dataset.csv", index=False)

    model_validation = run_model_validation()
    privacy = validate_public_columns(public)
    write_reports(private, public, model_validation, privacy)
    print(f"Public dataset written: {PUBLIC_DATA_PATH}")
    print(f"Validation report written: {VALIDATION_MD}")


if __name__ == "__main__":
    main()
