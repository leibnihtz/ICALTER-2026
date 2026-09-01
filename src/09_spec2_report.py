from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from common import MODELS, OUTPUTS, TABLES, VALIDATION, ensure_dirs


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() and path.stat().st_size > 0 else pd.DataFrame()


def fmt(value, digits: int = 3) -> str:
    if pd.isna(value):
        return "NA"
    if abs(float(value)) < 0.001 and float(value) != 0:
        return f"{float(value):.2e}"
    return f"{float(value):.{digits}f}"


def sig(value) -> bool:
    return pd.notna(value) and float(value) < 0.05


def direction(value) -> str:
    if pd.isna(value):
        return "unknown"
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "zero"


def first_row(df: pd.DataFrame) -> dict:
    return df.iloc[0].to_dict() if not df.empty else {}


def main() -> None:
    ensure_dirs()
    analysis = read_csv(VALIDATION / "analysis_dataset.csv")
    analysis_valid = analysis[analysis["timestamp_valid"].astype(str).str.lower().isin(["true", "1"])]
    diagnostics = read_csv(MODELS / "model_diagnostics.csv")
    m2 = read_csv(MODELS / "M2_coefficients.csv")
    m3 = read_csv(MODELS / "M3_coefficients.csv")
    lrt12 = read_csv(MODELS / "M1_vs_M2_lrt.csv")
    lrt23 = read_csv(MODELS / "M2_vs_M3_lrt.csv")
    r3 = read_csv(MODELS / "R3_raw_time_coefficients_v2.csv")
    r3_cmp = read_csv(MODELS / "R3_vs_M2_comparison.csv")
    pred = read_csv(MODELS / "M2_predicted_probabilities_v2.csv")
    support = read_csv(TABLES / "response_time_support.csv")
    direction_summary = read_csv(TABLES / "question_direction_summary.csv")
    bands = read_csv(TABLES / "response_time_bands_overall.csv")
    r3_diag_path = MODELS / "R3_raw_time_diagnostics_v2.txt"
    r3_diag_text = r3_diag_path.read_text(encoding="utf-8") if r3_diag_path.exists() else ""

    lrt12_row = first_row(lrt12)
    lrt23_row = first_row(lrt23)
    m2_diag = first_row(diagnostics[diagnostics["model"] == "M2"]) if not diagnostics.empty else {}
    m3_diag = first_row(diagnostics[diagnostics["model"] == "M3"]) if not diagnostics.empty else {}

    tf_term = m2[m2["term"] == "z_log_response_time:question_typeTrueFalse"]
    mc_term = m2[m2["term"] == "z_log_response_time:question_typeMultipleChoice"]
    tf_sig = sig(tf_term.iloc[0]["p_value"]) if not tf_term.empty else False
    mc_sig = sig(mc_term.iloc[0]["p_value"]) if not mc_term.empty else False
    global_interaction_sig = sig(lrt12_row.get("p_value"))
    course_interaction_sig = sig(lrt23_row.get("p_value"))

    tf_question_runs = direction_summary[direction_summary["question_type"] == "TrueFalse"][
        "comparable_question_runs"
    ].sum() if not direction_summary.empty else 0
    all_pred_supported = bool(pred["within_empirical_support"].all()) if not pred.empty else False
    r3_se_ok = bool((r3["se_vcov_abs_difference"].fillna(0) <= 1e-8).all()) if not r3.empty else False
    r3_converged = "Converged: TRUE" in r3_diag_text
    r3_valid = r3_se_ok and r3_converged
    r3_consistent_rows = int(r3_cmp["qualitative_consistency"].sum()) if not r3_cmp.empty else 0
    r3_total_rows = int(len(r3_cmp))
    r3_preserves = r3_total_rows > 0 and r3_consistent_rows == r3_total_rows and r3_valid

    if global_interaction_sig and tf_sig:
        recommended_claim = (
            "The association between response time and answer correctness varies by question format, "
            "with evidence concentrated in the TrueFalse versus SingleChoice contrast."
        )
        decision = "A"
        decision_text = "Strong enough to proceed with the ICALTER paper using the current narrative."
    elif tf_sig:
        recommended_claim = (
            "Evidence for moderation by question format is concentrated in the TrueFalse contrast, "
            "while the global interaction should be reported cautiously."
        )
        decision = "B"
        decision_text = "Paper is viable, but the narrative/title must be narrowed."
    else:
        recommended_claim = (
            "The data support a cautious association-focused analysis, but do not strongly support a broad moderation claim."
        )
        decision = "C"
        decision_text = "Evidence is insufficient; reformulate the research question before writing."

    if not all_pred_supported or not r3_valid:
        decision = "B" if decision == "A" else decision
        decision_text = "Paper is viable, but the narrative/title must be narrowed."
        if global_interaction_sig and tf_sig:
            recommended_claim = (
                "The primary model supports moderation by question format, especially for TrueFalse versus SingleChoice, "
                "but robustness should be reported cautiously because the raw-time R3 model did not fully converge."
            )

    summary = {
        "dataset": {
            "responses_analysis": int(len(analysis_valid)),
            "students": int(analysis_valid["student_id_hash"].nunique()) if not analysis_valid.empty else None,
            "courses": int(analysis_valid["course"].nunique()) if not analysis_valid.empty else None,
            "questions": int(analysis_valid["question_id"].nunique()) if not analysis_valid.empty else None,
        },
        "primary_model": {
            "model": "M2",
            "converged": bool(m2_diag.get("converged")) if m2_diag else None,
            "singular": bool(m2_diag.get("singular")) if m2_diag else None,
            "aic": float(m2_diag.get("AIC")) if m2_diag and pd.notna(m2_diag.get("AIC")) else None,
        },
        "interaction_global_test": lrt12_row,
        "question_type_interactions": {
            "MultipleChoice_vs_SingleChoice": first_row(mc_term),
            "TrueFalse_vs_SingleChoice": first_row(tf_term),
        },
        "cross_course_test": lrt23_row,
        "empirical_support": support.to_dict(orient="records"),
        "question_level_direction": direction_summary.to_dict(orient="records"),
        "robustness_R3": {
            "se_sanity_check_passed": r3_se_ok,
            "converged": r3_converged,
            "usable_as_robustness_evidence": r3_valid,
            "qualitative_consistency_rows": r3_consistent_rows,
            "qualitative_consistency_total": r3_total_rows,
        },
        "recommended_claim": recommended_claim,
        "decision": decision,
    }

    with open(OUTPUTS / "results_summary_v2.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    title_recommendation = "KEEP" if decision == "A" else "MODIFY"
    alt_titles = [
        "Question Format Moderates the Link Between Response Time and Correctness in Classroom Interaction Data",
        "Response Time Is Not a Universal Accuracy Signal: Evidence Across Classroom Question Formats",
        "Timing and Correctness in Real-Time Classroom Responses Across Computing Courses",
    ]

    lines = [
        "# LeibtiMeter / ICALTER 2026 Final Validation Report V2",
        "",
        "## Executive Decision",
        "",
        f"Decision: **{decision}. {decision_text}**",
        "",
        f"Recommended claim: {recommended_claim}",
        "",
        "## Q1. Does M2 fit significantly better than the model without the interaction?",
        "",
        (
            f"Yes. M1 vs M2 LRT: chi-square = {fmt(lrt12_row.get('chisq'))}, "
            f"df = {fmt(lrt12_row.get('df'), 0)}, p = {fmt(lrt12_row.get('p_value'))}, "
            f"delta AIC = {fmt(lrt12_row.get('delta_AIC'))}."
            if global_interaction_sig
            else f"No strong evidence. M1 vs M2 LRT: chi-square = {fmt(lrt12_row.get('chisq'))}, "
            f"df = {fmt(lrt12_row.get('df'), 0)}, p = {fmt(lrt12_row.get('p_value'))}, "
            f"delta AIC = {fmt(lrt12_row.get('delta_AIC'))}."
        ),
        "",
        "## Q2. Which question formats show evidence of a different relationship?",
        "",
    ]

    if not mc_term.empty:
        row = mc_term.iloc[0]
        lines.append(
            f"- MultipleChoice vs SingleChoice: OR {fmt(row['odds_ratio'])} "
            f"[{fmt(row['CI95_lower'])}, {fmt(row['CI95_upper'])}], p = {fmt(row['p_value'])}; "
            f"{'evidence of difference' if mc_sig else 'no strong evidence of difference'}."
        )
    if not tf_term.empty:
        row = tf_term.iloc[0]
        lines.append(
            f"- TrueFalse vs SingleChoice: OR {fmt(row['odds_ratio'])} "
            f"[{fmt(row['CI95_lower'])}, {fmt(row['CI95_upper'])}], p = {fmt(row['p_value'])}; "
            f"{'evidence of difference' if tf_sig else 'no strong evidence of difference'}."
        )

    lines.extend(
        [
            "",
            "## Q3. Is the TrueFalse pattern supported by multiple question runs?",
            "",
            f"TrueFalse comparable question runs with both correct and incorrect responses: {int(tf_question_runs)}.",
        ]
    )
    if not direction_summary.empty:
        for _, row in direction_summary[direction_summary["question_type"] == "TrueFalse"].iterrows():
            lines.append(
                f"- {row['course']}: {int(row['correct_faster_runs'])} correct-faster runs, "
                f"{int(row['incorrect_faster_runs'])} incorrect-faster runs, "
                f"{fmt(row['percentage_correct_faster'])}% correct-faster."
            )

    lines.extend(
        [
            "",
            "This is descriptive validation only, not an inferential test.",
            "",
            "## Q4. Are model predictions shown only in supported regions?",
            "",
            f"{'Yes' if all_pred_supported else 'No'}. Figure 3 v2 uses question-type-specific empirical support, capped at each type's P95 response time.",
        ]
    )
    if not support.empty:
        for _, row in support.iterrows():
            lines.append(
                f"- {row['question_type']}: n = {int(row['n'])}, P95 = {fmt(row['p95'])} s, max = {fmt(row['maximum'])} s."
            )

    lines.extend(
        [
            "",
            "## Q5. Does M3 provide evidence that the pattern differs by course?",
            "",
            (
                f"M2 vs M3 LRT: chi-square = {fmt(lrt23_row.get('chisq'))}, "
                f"df = {fmt(lrt23_row.get('df'), 0)}, p = {fmt(lrt23_row.get('p_value'))}, "
                f"delta AIC = {fmt(lrt23_row.get('delta_AIC'))}."
            ),
        ]
    )
    if course_interaction_sig:
        lines.append("There is formal evidence that the response-time pattern differs by course.")
    else:
        lines.append("There is no strong formal evidence of a course interaction; this is not proof that the courses are identical.")

    lines.extend(
        [
            "",
            "## Q6. Is R3 statistically valid after independent refitting?",
            "",
            f"{'Yes for coefficient extraction, but no as a clean inferential robustness model' if r3_se_ok and not r3_converged else ('Yes' if r3_valid else 'No')}. "
            f"The standard errors from `summary(model)$coefficients` "
            f"{'match' if r3_se_ok else 'do not match'} `sqrt(diag(vcov(model)))` within tolerance.",
        ]
    )
    if not r3.empty:
        max_diff = r3["se_vcov_abs_difference"].max()
        lines.append(f"Maximum SE absolute difference: {fmt(max_diff, 10)}.")
    lines.append(f"R3 convergence status: {'converged' if r3_converged else 'not converged'}.")

    lines.extend(["", "## Q7. Do robustness checks preserve the qualitative conclusion?", ""])
    if r3_preserves:
        lines.append("R3 preserves the qualitative direction of the M2 response-time terms after independent refitting.")
    else:
        lines.append("R3 should not be used as strong robustness evidence because it did not pass all validation requirements.")
    if not r3_cmp.empty:
        for _, row in r3_cmp.iterrows():
            lines.append(
                f"- {row['term_concept']}: M2 {row['M2_direction']} "
                f"({'significant' if row['M2_significant'] else 'not significant'}), "
                f"R3 {row['R3_direction']} "
                f"({'significant' if row['R3_significant'] else 'not significant'}), "
                f"consistent = {row['qualitative_consistency']}."
            )

    lines.extend(
        [
            "",
            "## Q8. Most Defensible Scientific Claim",
            "",
            recommended_claim,
            "",
            "The claim should remain observational and associative. The analysis does not show that response time causes correctness or that LeibtiMeter improves learning.",
            "",
            "## Descriptive Time-Band Check",
            "",
            "Response-time bands are descriptive support for the model and should not be interpreted inferentially.",
        ]
    )
    if not bands.empty:
        for _, row in bands[bands["n"] > 0].iterrows():
            lines.append(
                f"- {row['question_type']} {row['response_time_band']}: n = {int(row['n'])}, accuracy = {fmt(row['accuracy'])}."
            )

    lines.extend(
        [
            "",
            "## Title Recommendation",
            "",
            f"Title recommendation: **{title_recommendation}**",
            "",
        ]
    )
    if title_recommendation == "KEEP":
        lines.append(
            "The candidate title is acceptable because it names the main variables, preserves the question-format framing, and does not imply causality."
        )
    else:
        lines.append(
            "The candidate title is close, but a narrower title would better reflect that the strongest evidence is concentrated in the TrueFalse contrast."
        )
        lines.extend(["", "Alternative titles:"])
        for title in alt_titles:
            lines.append(f"- {title}")

    with open(OUTPUTS / "VALIDATION_REPORT_V2.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("SPEC 2 summary and validation report written.")


if __name__ == "__main__":
    main()
