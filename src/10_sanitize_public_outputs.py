from __future__ import annotations

import pandas as pd

from common import MODELS, OUTPUTS, TABLES, add_derived_variables, load_raw_data


def stable_id_map(values: pd.Series, prefix: str) -> dict[str, str]:
    unique = sorted(values.dropna().astype(str).unique())
    width = max(3, len(str(len(unique))))
    return {value: f"{prefix}_{i:0{width}d}" for i, value in enumerate(unique, start=1)}


def main() -> None:
    raw = add_derived_variables(load_raw_data())
    private = raw[raw["timestamp_valid"] & raw["correct"].notna() & raw["response_time_seconds"].notna()].copy()

    question_map = stable_id_map(private["question_id"], "question")
    session_map = stable_id_map(private["session_id"], "session")
    run_map = stable_id_map(private["question_run_id"], "run") if "question_run_id" in private else {}

    replacements = {
        "question_id": question_map,
        "session_id": session_map,
        "question_run_id": run_map,
    }

    for path in [
        TABLES / "question_level_diagnostics.csv",
        TABLES / "question_difficulty.csv",
        TABLES / "session_longitudinal.csv",
    ]:
        if not path.exists():
            continue
        df = pd.read_csv(path)
        for column, mapping in replacements.items():
            if column in df.columns:
                df[column] = df[column].astype(str).map(mapping).fillna(df[column])
        df.to_csv(path, index=False)

    for path in [
        MODELS / "model_diagnostics.csv",
        MODELS / "R3_raw_time_diagnostics_v2.txt",
        OUTPUTS / "VALIDATION_REPORT_V2.md",
        OUTPUTS / "results_summary_v2.json",
    ]:
        if path.exists():
            text = path.read_text(encoding="utf-8")
            text = text.replace("student_id_hash", "student_id")
            path.write_text(text, encoding="utf-8")

    print("Public outputs sanitized.")


if __name__ == "__main__":
    main()
