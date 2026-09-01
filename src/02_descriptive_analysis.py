from __future__ import annotations

import pandas as pd

from common import TABLES, ensure_dirs, load_analysis_data, response_time_summary


def main() -> None:
    ensure_dirs()
    df = load_analysis_data(include_timestamp_invalid=False)

    descriptive = (
        df.groupby(["course", "question_type"], dropna=False)
        .agg(
            students=("student_id_hash", "nunique"),
            questions=("question_id", "nunique"),
            question_runs=("question_run_id", "nunique"),
            responses=("correct", "size"),
            correct=("correct", "sum"),
            mean_response_time=("response_time_seconds", "mean"),
            median_response_time=("response_time_seconds", "median"),
            response_time_sd=("response_time_seconds", "std"),
        )
        .reset_index()
    )
    descriptive["incorrect"] = descriptive["responses"] - descriptive["correct"]
    descriptive["accuracy"] = descriptive["correct"] / descriptive["responses"]
    descriptive = descriptive[
        [
            "course",
            "question_type",
            "students",
            "questions",
            "question_runs",
            "responses",
            "correct",
            "incorrect",
            "accuracy",
            "mean_response_time",
            "median_response_time",
            "response_time_sd",
        ]
    ]
    descriptive.to_csv(TABLES / "table_descriptive.csv", index=False)

    course_summary = (
        df.groupby("course", dropna=False)
        .agg(
            unique_students=("student_id_hash", "nunique"),
            sessions=("session_id", "nunique"),
            unique_questions=("question_id", "nunique"),
            question_runs=("question_run_id", "nunique"),
            responses=("correct", "size"),
            accuracy=("correct", "mean"),
            mean_response_time=("response_time_seconds", "mean"),
            median_response_time=("response_time_seconds", "median"),
        )
        .reset_index()
    )
    course_summary.to_csv(TABLES / "table_course_summary.csv", index=False)

    global_dist = response_time_summary(df).to_frame().T
    global_dist.insert(0, "group", "overall")

    by_course = df.groupby("course").apply(response_time_summary, include_groups=False).reset_index()
    by_course.insert(0, "group", "course")

    by_type = df.groupby("question_type").apply(response_time_summary, include_groups=False).reset_index()
    by_type.insert(0, "group", "question_type")

    by_course_type = (
        df.groupby(["course", "question_type"])
        .apply(response_time_summary, include_groups=False)
        .reset_index()
    )
    by_course_type.insert(0, "group", "course_question_type")

    pd.concat([global_dist, by_course, by_type, by_course_type], ignore_index=True).to_csv(
        TABLES / "response_time_distribution.csv", index=False
    )

    correctness_rt = (
        df.groupby(["course", "question_type", "correctness"])
        .agg(
            n=("response_time_seconds", "size"),
            mean=("response_time_seconds", "mean"),
            median=("response_time_seconds", "median"),
            sd=("response_time_seconds", "std"),
            p25=("response_time_seconds", lambda s: s.quantile(0.25)),
            p75=("response_time_seconds", lambda s: s.quantile(0.75)),
        )
        .reset_index()
    )
    correctness_rt.to_csv(TABLES / "correctness_response_time.csv", index=False)

    question_level = (
        df.groupby(["course", "question_id", "question_run_id", "question_type"])
        .agg(
            n_responses=("correct", "size"),
            accuracy=("correct", "mean"),
            mean_response_time=("response_time_seconds", "mean"),
            median_response_time=("response_time_seconds", "median"),
            mean_correct_response_time=(
                "response_time_seconds",
                lambda s: s[df.loc[s.index, "correct"] == 1].mean(),
            ),
            mean_incorrect_response_time=(
                "response_time_seconds",
                lambda s: s[df.loc[s.index, "correct"] == 0].mean(),
            ),
            median_correct_response_time=(
                "response_time_seconds",
                lambda s: s[df.loc[s.index, "correct"] == 1].median(),
            ),
            median_incorrect_response_time=(
                "response_time_seconds",
                lambda s: s[df.loc[s.index, "correct"] == 0].median(),
            ),
        )
        .reset_index()
    )
    question_level["correct_faster"] = pd.NA
    mask = question_level["median_correct_response_time"].notna() & question_level[
        "median_incorrect_response_time"
    ].notna()
    question_level.loc[mask, "correct_faster"] = (
        question_level.loc[mask, "median_correct_response_time"]
        < question_level.loc[mask, "median_incorrect_response_time"]
    )
    question_level.drop(
        columns=["median_correct_response_time", "median_incorrect_response_time"]
    ).to_csv(TABLES / "question_level_diagnostics.csv", index=False)

    question_difficulty = (
        df.groupby(["question_id", "course", "question_type"])
        .agg(
            n=("correct", "size"),
            accuracy=("correct", "mean"),
            median_response_time=("response_time_seconds", "median"),
        )
        .reset_index()
    )
    question_difficulty.to_csv(TABLES / "question_difficulty.csv", index=False)

    session_order = (
        df[["course", "session_id", "session_started_at"]]
        .drop_duplicates()
        .sort_values(["course", "session_started_at", "session_id"])
    )
    session_order["session_index"] = session_order.groupby("course").cumcount() + 1
    session_longitudinal = (
        df.merge(session_order[["course", "session_id", "session_index"]], on=["course", "session_id"])
        .groupby(["course", "session_id", "session_index"])
        .agg(
            participating_students=("student_id_hash", "nunique"),
            responses=("correct", "size"),
            accuracy=("correct", "mean"),
            median_response_time=("response_time_seconds", "median"),
        )
        .reset_index()
        .sort_values(["course", "session_index"])
    )
    session_longitudinal.to_csv(TABLES / "session_longitudinal.csv", index=False)

    print("Descriptive outputs written.")


if __name__ == "__main__":
    main()
