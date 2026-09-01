from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from common import MODELS, OUTPUTS, TABLES, VALIDATION, ensure_dirs, load_raw_data, response_time_summary


def read_csv_or_empty(path: Path) -> pd.DataFrame:
    if path.exists() and path.stat().st_size > 0:
        return pd.read_csv(path)
    return pd.DataFrame()


def fmt(value, digits: int = 3) -> str:
    if pd.isna(value):
        return "NA"
    if isinstance(value, (int,)) or float(value).is_integer():
        return str(int(value))
    return f"{float(value):.{digits}f}"


def coefficient_records(df: pd.DataFrame, contains: str | None = None) -> list[dict]:
    if df.empty:
        return []
    out = df.copy()
    if contains:
        out = out[out["term"].str.contains(contains, regex=False, na=False)]
    cols = ["term", "odds_ratio", "CI95_lower", "CI95_upper", "p_value"]
    return out[cols].to_dict(orient="records")


def main() -> None:
    ensure_dirs()

    raw = load_raw_data()
    analysis = read_csv_or_empty(VALIDATION / "analysis_dataset.csv")
    analysis_valid = analysis[analysis["timestamp_valid"].astype(str).str.lower().isin(["true", "1"])]
    course_summary = read_csv_or_empty(TABLES / "table_course_summary.csv")
    descriptive = read_csv_or_empty(TABLES / "table_descriptive.csv")
    rt = response_time_summary(analysis_valid)
    diagnostics = read_csv_or_empty(MODELS / "model_diagnostics.csv")
    m2 = read_csv_or_empty(MODELS / "M2_coefficients.csv")
    robustness = read_csv_or_empty(MODELS / "robustness_checks.csv")

    m2_diag = diagnostics[diagnostics["model"] == "M2"].iloc[0].to_dict() if not diagnostics.empty and (diagnostics["model"] == "M2").any() else {}

    accuracy_by_course = {
        str(row["course"]).lower().replace(" ", "_"): float(row["accuracy"])
        for _, row in course_summary.iterrows()
    } if not course_summary.empty else {}

    summary = {
        "dataset": {
            "responses_total": int(len(raw)),
            "responses_analysis": int(len(analysis_valid)),
            "students": int(raw["student_id_hash"].nunique()),
            "courses": int(raw["course"].nunique()),
            "sessions": int(raw["session_id"].nunique()),
            "questions": int(raw["question_id"].nunique()),
            "question_runs": int(raw["question_run_id"].nunique()),
        },
        "response_time": {
            "median": float(rt["median"]),
            "mean": float(rt["mean"]),
            "p95": float(rt["p95"]),
            "max": float(rt["maximum"]),
        },
        "accuracy": {
            "overall": float(analysis_valid["correct"].mean()) if not analysis_valid.empty else None,
            "big_data": accuracy_by_course.get("big_data"),
            "redes_ii": accuracy_by_course.get("redes_ii"),
        },
        "primary_model": {
            "model": "M2",
            "converged": bool(m2_diag.get("converged")) if m2_diag else None,
            "singular": bool(m2_diag.get("singular")) if m2_diag else None,
            "aic": float(m2_diag.get("AIC")) if m2_diag and pd.notna(m2_diag.get("AIC")) else None,
        },
        "main_effects": coefficient_records(m2),
        "interaction_effects": coefficient_records(m2, ":"),
        "robustness": robustness.to_dict(orient="records") if not robustness.empty else {},
    }

    with open(OUTPUTS / "results_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    duplicate_rows = read_csv_or_empty(VALIDATION / "duplicate_responses.csv")
    timestamp_rows = read_csv_or_empty(VALIDATION / "timestamp_anomalies.csv")
    m3 = read_csv_or_empty(MODELS / "M3_coefficients.csv")
    big = read_csv_or_empty(MODELS / "robustness_big_data.csv")
    redes = read_csv_or_empty(MODELS / "robustness_redes_ii.csv")

    accuracy_type = (
        descriptive.groupby("question_type")["correct"].sum()
        / descriptive.groupby("question_type")["responses"].sum()
    ) if not descriptive.empty else pd.Series(dtype=float)

    lines = [
        "# LeibtiMeter / ICALTER 2026 Validation Report",
        "",
        "## Dataset",
        "",
        f"- Rows in raw evaluable dataset: {len(raw)}",
        f"- Rows in main analysis sample: {len(analysis_valid)}",
        f"- Students: {raw['student_id_hash'].nunique()}",
        f"- Courses: {raw['course'].nunique()} ({', '.join(sorted(raw['course'].dropna().unique()))})",
        f"- Sessions: {raw['session_id'].nunique()}",
        f"- Unique questions: {raw['question_id'].nunique()}",
        f"- Question runs: {raw['question_run_id'].nunique()}",
        f"- Duplicate student-question-run responses documented: {len(duplicate_rows)}",
        f"- Timestamp-invalid responses documented and excluded from the main analysis: {len(timestamp_rows)}",
        "",
        "No names, codes, email addresses, IP addresses, device data, or original internal student UUIDs are reported by this pipeline.",
        "",
        "## Descriptive Findings",
        "",
    ]

    for _, row in course_summary.iterrows():
        lines.append(
            f"- {row['course']}: accuracy {fmt(row['accuracy'])}, "
            f"median response time {fmt(row['median_response_time'])} s, "
            f"{int(row['responses'])} responses."
        )

    for question_type, accuracy in accuracy_type.items():
        lines.append(f"- {question_type}: accuracy {fmt(accuracy)}.")

    lines.extend(
        [
            f"- Overall median response time: {fmt(rt['median'])} s.",
            f"- Overall mean response time: {fmt(rt['mean'])} s.",
            f"- Overall P95 response time: {fmt(rt['p95'])} s.",
            "",
            "## Primary GLMM",
            "",
            "Formula: `correct ~ z_log_response_time * question_type + course + (1 | student_id_hash) + (1 | question_id)`.",
            "",
            "Reference categories are determined by R factor ordering with `SingleChoice` as the question-type reference. The model includes random intercepts for students and questions.",
        ]
    )

    if m2_diag:
        lines.extend(
            [
                f"- Converged: {m2_diag.get('converged')}",
                f"- Singular fit: {m2_diag.get('singular')}",
                f"- AIC: {fmt(m2_diag.get('AIC'))}",
                f"- BIC: {fmt(m2_diag.get('BIC'))}",
            ]
        )

    if not m2.empty:
        lines.extend(["", "Fixed effects are reported as odds ratios with Wald 95% confidence intervals:"])
        for _, row in m2.iterrows():
            lines.append(
                f"- {row['term']}: OR {fmt(row['odds_ratio'])} "
                f"[{fmt(row['CI95_lower'])}, {fmt(row['CI95_upper'])}], "
                f"p = {fmt(row['p_value'])}."
            )

    interaction_rows = m2[m2["term"].str.contains(":", regex=False, na=False)] if not m2.empty else pd.DataFrame()
    interaction_answer = "The response-time by question-type interaction should be interpreted from the M2 interaction terms."
    if not interaction_rows.empty:
        sig = interaction_rows[interaction_rows["p_value"] < 0.05]
        if len(sig) > 0:
            interaction_answer = "M2 provides evidence that the association between response time and correctness varies by question type."
        else:
            interaction_answer = "M2 does not provide strong evidence that the association between response time and correctness varies by question type."

    lines.extend(
        [
            "",
            "## Interaction Interpretation",
            "",
            interaction_answer,
            "",
            "This statement is associative and should not be read causally.",
            "",
            "## Cross-Course Validation",
            "",
        ]
    )

    m3_diag = diagnostics[diagnostics["model"] == "M3"].iloc[0].to_dict() if not diagnostics.empty and (diagnostics["model"] == "M3").any() else {}
    if m3_diag:
        lines.append(
            f"M3 was attempted with the cross-course interaction. Converged: {m3_diag.get('converged')}; singular fit: {m3_diag.get('singular')}; AIC: {fmt(m3_diag.get('AIC'))}."
        )
    if not m3.empty:
        course_interactions = m3[m3["term"].str.contains(":course", regex=False, na=False)]
        if len(course_interactions) > 0 and (course_interactions["p_value"] < 0.05).any():
            lines.append("M3 includes at least one statistically detectable course interaction term.")
        else:
            lines.append("M3 does not show strong formal evidence of cross-course interaction in the fitted terms.")

    lines.append("Directional consistency should be judged separately from statistical significance and from formal interaction evidence.")

    for label, frame in [("BIG DATA separate model", big), ("REDES II separate model", redes)]:
        if not frame.empty and "term" in frame.columns:
            rt_row = frame[frame["term"] == "z_log_response_time"]
            if not rt_row.empty:
                row = rt_row.iloc[0]
                lines.append(f"- {label}: z-log-time OR {fmt(row['odds_ratio'])}, p = {fmt(row['p_value'])}.")

    lines.extend(["", "## Robustness", ""])
    if robustness.empty:
        lines.append("Robustness outputs were not available when this report was generated.")
    else:
        for check in robustness["check"].dropna().unique():
            subset = robustness[(robustness["check"] == check) & (robustness["term"] == "z_log_response_time")]
            if subset.empty:
                lines.append(f"- {check}: completed; see `outputs/models/robustness_checks.csv`.")
            else:
                row = subset.iloc[0]
                lines.append(f"- {check}: z-log/raw time OR {fmt(row['odds_ratio'])}, p = {fmt(row['p_value'])}.")

    conclusion = (
        f"Across {len(analysis_valid)} evaluated classroom responses from {raw['student_id_hash'].nunique()} students, "
        "the analysis estimates the observed relationship between response time and correctness while accounting for repeated student responses and question heterogeneity. "
        "The primary mixed-effects model evaluates whether this association differs by question format, with cross-course and robustness checks used as validation rather than as a basis for changing the hypothesis. "
        "Findings should be described as associations observed in this classroom-response dataset, not as causal effects of response time or of LeibtiMeter."
    )
    lines.extend(["", "## Potential Paper Conclusion", "", conclusion])

    with open(OUTPUTS / "VALIDATION_REPORT.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("Final summary and validation report written.")


if __name__ == "__main__":
    main()
