from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "leibtimeter_paper_base.csv"
OUTPUTS = ROOT / "outputs"
TABLES = OUTPUTS / "tables"
FIGURES = OUTPUTS / "figures"
MODELS = OUTPUTS / "models"
VALIDATION = OUTPUTS / "validation"

REQUIRED_FIELDS = [
    "student_id_hash",
    "course",
    "course_code",
    "term",
    "session_id",
    "session_title",
    "session_started_at",
    "question_run_id",
    "question_id",
    "display_order",
    "time_limit_seconds",
    "opened_at",
    "closed_at",
    "question_type",
    "difficulty_level",
    "has_correct_answer",
    "submitted_at",
    "response_time_seconds",
    "normalized_response_time",
    "is_correct",
]

EXPECTED_QUESTION_TYPES = {"SingleChoice", "MultipleChoice", "TrueFalse"}


def ensure_dirs() -> None:
    for path in [TABLES, FIGURES, MODELS, VALIDATION]:
        path.mkdir(parents=True, exist_ok=True)


def parse_bool(value) -> bool | float:
    if pd.isna(value):
        return np.nan
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"t", "true", "1", "yes", "y"}:
        return True
    if text in {"f", "false", "0", "no", "n"}:
        return False
    return np.nan


def load_raw_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Input dataset not found: {DATA_PATH}")
    return pd.read_csv(DATA_PATH)


def validate_required_columns(df: pd.DataFrame) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in df.columns]
    if missing:
        raise ValueError(f"Required columns are missing: {', '.join(missing)}")

    hard_required = [
        "response_time_seconds",
        "is_correct",
        "student_id_hash",
        "question_id",
        "question_type",
    ]
    empty = [field for field in hard_required if df[field].isna().all()]
    if empty:
        raise ValueError(f"Required columns contain only missing values: {', '.join(empty)}")

    observed_types = set(df["question_type"].dropna().unique())
    unexpected = sorted(observed_types - EXPECTED_QUESTION_TYPES)
    if unexpected:
        raise ValueError(f"Unexpected question_type values: {', '.join(unexpected)}")


def add_derived_variables(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in ["opened_at", "closed_at", "submitted_at", "session_started_at"]:
        out[column] = pd.to_datetime(out[column], utc=True, errors="coerce")

    out["response_time_seconds"] = pd.to_numeric(out["response_time_seconds"], errors="coerce")
    out["is_correct_bool"] = out["is_correct"].map(parse_bool)
    out["correct"] = out["is_correct_bool"].astype("Int64")
    out["log_response_time"] = np.log1p(out["response_time_seconds"])
    sd = out["log_response_time"].std(ddof=1)
    if not np.isfinite(sd) or sd == 0:
        raise ValueError("Cannot standardize log_response_time because its standard deviation is zero or missing.")
    out["z_log_response_time"] = (out["log_response_time"] - out["log_response_time"].mean()) / sd
    out["timestamp_valid"] = (
        out["submitted_at"].notna()
        & out["opened_at"].notna()
        & out["closed_at"].notna()
        & (out["submitted_at"] >= out["opened_at"])
        & (out["submitted_at"] <= out["closed_at"])
    )
    out["correctness"] = np.where(out["correct"] == 1, "Correct", "Incorrect")
    return out


def load_analysis_data(include_timestamp_invalid: bool = False) -> pd.DataFrame:
    df = load_raw_data()
    validate_required_columns(df)
    df = add_derived_variables(df)
    df = df[df["correct"].notna() & df["response_time_seconds"].notna()].copy()
    if not include_timestamp_invalid:
        df = df[df["timestamp_valid"]].copy()
    return df


def response_time_summary(group: pd.DataFrame) -> pd.Series:
    x = group["response_time_seconds"].dropna()
    return pd.Series(
        {
            "minimum": x.min(),
            "p1": x.quantile(0.01),
            "p5": x.quantile(0.05),
            "p25": x.quantile(0.25),
            "median": x.median(),
            "p75": x.quantile(0.75),
            "p95": x.quantile(0.95),
            "p99": x.quantile(0.99),
            "maximum": x.max(),
            "mean": x.mean(),
            "standard_deviation": x.std(ddof=1),
        }
    )


def write_analysis_dataset(df: pd.DataFrame) -> None:
    columns = [
        "student_id_hash",
        "course",
        "course_code",
        "term",
        "session_id",
        "session_title",
        "session_started_at",
        "question_run_id",
        "question_id",
        "display_order",
        "opened_at",
        "closed_at",
        "submitted_at",
        "question_type",
        "response_time_seconds",
        "normalized_response_time",
        "is_correct",
        "correct",
        "log_response_time",
        "z_log_response_time",
        "timestamp_valid",
    ]
    safe_columns = [col for col in columns if col in df.columns]
    df[safe_columns].to_csv(VALIDATION / "analysis_dataset.csv", index=False)
