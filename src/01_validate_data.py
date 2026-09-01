from __future__ import annotations

import json

import pandas as pd

from common import (
    OUTPUTS,
    VALIDATION,
    add_derived_variables,
    ensure_dirs,
    load_raw_data,
    validate_required_columns,
    write_analysis_dataset,
)


def main() -> None:
    ensure_dirs()
    df = load_raw_data()
    validate_required_columns(df)
    df = add_derived_variables(df)

    metrics = {
        "observations": int(len(df)),
        "unique_students": int(df["student_id_hash"].nunique()),
        "courses": int(df["course"].nunique()),
        "sessions": int(df["session_id"].nunique()),
        "question_runs": int(df["question_run_id"].nunique()),
        "unique_questions": int(df["question_id"].nunique()),
        "question_types": sorted(df["question_type"].dropna().unique().tolist()),
        "timestamp_invalid": int((~df["timestamp_valid"]).sum()),
        "analysis_observations": int((df["timestamp_valid"] & df["correct"].notna()).sum()),
    }

    duplicates = df[df.duplicated(["student_id_hash", "question_run_id"], keep=False)].copy()
    duplicates.to_csv(VALIDATION / "duplicate_responses.csv", index=False)

    timestamp_anomalies = df.loc[
        ~df["timestamp_valid"],
        [
            "student_id_hash",
            "course",
            "session_id",
            "question_run_id",
            "question_id",
            "opened_at",
            "submitted_at",
            "closed_at",
            "response_time_seconds",
            "is_correct",
        ],
    ].copy()
    timestamp_anomalies.to_csv(VALIDATION / "timestamp_anomalies.csv", index=False)

    missing = (
        pd.DataFrame(
            {
                "variable": df.columns,
                "missing_count": [int(df[col].isna().sum()) for col in df.columns],
                "missing_percentage": [float(df[col].isna().mean() * 100) for col in df.columns],
            }
        )
        .sort_values(["missing_count", "variable"], ascending=[False, True])
        .reset_index(drop=True)
    )
    missing.to_csv(VALIDATION / "missing_values.csv", index=False)

    analysis_df = df[df["correct"].notna() & df["response_time_seconds"].notna()].copy()
    write_analysis_dataset(analysis_df)

    with open(VALIDATION / "validation_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
